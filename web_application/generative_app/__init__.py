"""Experimental project workspace. Account authority is separate from Git records."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from uuid import UUID, uuid4

from flask import Flask, g, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from gsp_protocol import PROFILE, PROTOCOL_VERSION, SCHEMA_VERSION, ProtocolError, normalize_snapshot

from gsp_git_store import Conflict, GitStore, LimitExceeded, NotFound, StoreError
from .protocol_api import register_protocol_routes, strict_json

COOKIE = "gsp_session"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / ".runtime" / "generalized"
EDITABLE = {
    "title", "content", "record_type", "epistemic_mode", "modality", "status",
    "attributed_to", "method", "evidence", "uncertainty", "alternatives",
    "conditions", "consequences", "occurred_at", "related_records",
}
ENUMS = {
    "record_type": ("Entity", "State", "Event", "Process", "Relation", "Property"),
    "epistemic_mode": ("observed", "reported", "inferred", "interpreted", "retrospective"),
    "modality": ("realized", "intended", "possible", "unrealized", "unknown"),
    "status": ("unreviewed", "contested", "revised", "withdrawn"),
}


class APIError(Exception):
    def __init__(self, status, code, message, fields=None):
        self.status, self.code, self.message, self.fields = status, code, message, fields


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def identifier(value):
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise APIError(404, "not_found", "This item is not available.") from None
    return value


def text_field(data, key, maximum, required=False, default=""):
    value = data.get(key, default)
    if not isinstance(value, str):
        raise APIError(400, "validation", "Check the highlighted field.", {key: "Use text."})
    value = value.strip()
    if (required and not value) or len(value) > maximum or "\x00" in value:
        message = f"Use {'1' if required else '0'}–{maximum} characters."
        raise APIError(400, "validation", "Check the highlighted field.", {key: message})
    return value


def payload(allowed):
    if not request.is_json:
        raise APIError(415, "json_required", "Send a JSON request.")
    try:
        if request.content_length and request.content_length > 128 * 1024:
            raise APIError(413, "request_limit", "This request is too large.")
        data = strict_json(request.get_data())
        # JSON permits surrogate escapes which cannot be persisted as UTF-8.
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise APIError(400, "validation", "Use valid Unicode text and a simple JSON object.") from None
    if not isinstance(data, dict):
        raise APIError(400, "validation", "Send a JSON object.")
    if set(data) - allowed:
        raise APIError(400, "validation", "The request contains unsupported fields.")
    return data


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATA_DIR=os.environ.get("GSP_DATA_DIR", str(DEFAULT_DATA_DIR)),
        COOKIE_SECURE=os.environ.get("GSP_COOKIE_SECURE") == "1",
        TRUSTED_HOSTS=[h.strip() for h in os.environ.get("GSP_TRUSTED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if h.strip()],
        MAX_CONTENT_LENGTH=22 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=1100 * 1024,
        MAX_FORM_PARTS=10,
        SESSION_SECONDS=12 * 60 * 60,
        AUTH_IP_LIMIT=50,
        AUTH_ACCOUNT_LIMIT=12,
        AUTH_WINDOW=15 * 60,
        MAX_RECORDS=1000,
    )
    if config:
        app.config.update(config)
    root = Path(app.config["DATA_DIR"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    database = root / "accounts.sqlite3"
    store = GitStore(root)
    app.extensions["git_store"] = store

    @contextmanager
    def db():
        conn = sqlite3.connect(database, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    with db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id),
                csrf_token TEXT NOT NULL, expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS projects_owner ON projects(owner_id);
            CREATE TABLE IF NOT EXISTS auth_attempts (
                scope TEXT NOT NULL, attempted_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS attempts_lookup ON auth_attempts(scope, attempted_at);
        """)

    def public_user(user):
        return {k: user[k] for k in ("id", "display_name", "email")} if user else None

    def new_session(user_id=None):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expiry = int(time.time()) + app.config["SESSION_SECONDS"]
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
            if g.session:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (g.session["token_hash"],))
            conn.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest(token), user_id, csrf, expiry))
            g.user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone() if user_id else None
        g.session = {"token_hash": digest(token), "csrf_token": csrf, "expires_at": expiry, "user_id": user_id}
        g.new_cookie = token

    def session_body():
        return {"user": public_user(g.user), "csrf_token": g.session["csrf_token"]}

    @app.before_request
    def load_session_and_check_csrf():
        g.session = g.user = None
        g.new_cookie = None
        if not request.path.startswith("/api/"):
            return
        cookie = request.cookies.get(COOKIE, "")
        if cookie and len(cookie) <= 128:
            with db() as conn:
                g.session = conn.execute("SELECT * FROM sessions WHERE token_hash=? AND expires_at>?", (digest(cookie), int(time.time()))).fetchone()
                if g.session and g.session["user_id"]:
                    g.user = conn.execute("SELECT * FROM users WHERE id=?", (g.session["user_id"],)).fetchone()
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = request.headers.get("X-CSRF-Token", "")
            if not g.session or not supplied.isascii() or not secrets.compare_digest(supplied, g.session["csrf_token"]):
                raise APIError(403, "csrf", "Your session changed or expired. Refresh the page and try again.")
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                raise APIError(403, "origin", "This request came from a different site.")

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if getattr(g, "new_cookie", None):
            response.set_cookie(COOKIE, g.new_cookie, max_age=app.config["SESSION_SECONDS"], httponly=True, secure=app.config["COOKIE_SECURE"], samesite="Lax", path="/")
        return response

    @app.errorhandler(APIError)
    def api_error(exc):
        error = {"code": exc.code, "message": exc.message}
        if exc.fields:
            error["fields"] = exc.fields
        response = jsonify(error=error)
        response.status_code = exc.status
        if exc.status == 429:
            response.headers["Retry-After"] = str(app.config["AUTH_WINDOW"])
        return response

    @app.errorhandler(StoreError)
    def git_error(exc):
        if isinstance(exc, LimitExceeded):
            return api_error(APIError(413, "storage_limit", str(exc)))
        if isinstance(exc, Conflict):
            return api_error(APIError(409, "conflict", "This project changed since you opened it. Your edits have not been saved. Review the latest version before trying again."))
        if isinstance(exc, NotFound):
            return api_error(APIError(404, "not_found", "This record or revision is not available."))
        app.logger.error("Git storage operation failed (%s)", type(exc).__name__)
        return api_error(APIError(503, "storage", "The record store is unavailable. No successful save has been confirmed. Please try again."))

    @app.errorhandler(ProtocolError)
    def protocol_error(exc):
        return api_error(APIError(400, exc.code, exc.message, exc.fields))

    @app.errorhandler(sqlite3.Error)
    def database_error(exc):
        app.logger.error("Account database operation failed (%s)", type(exc).__name__)
        return api_error(APIError(503, "database", "The workspace is temporarily unavailable. Please try again."))

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return api_error(APIError(exc.code or 500, "http_error", "The request could not be processed."))

    def authenticated(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not g.user:
                raise APIError(401, "authentication", "Sign in to continue.")
            return fn(*args, **kwargs)
        return wrapped

    def authorize(project_id):
        identifier(project_id)
        with db() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id=? AND owner_id=?", (project_id, g.user["id"])).fetchone()
        if not row:
            raise APIError(404, "not_found", "This project is not available.")

    def actor():
        return {"id": g.user["id"], "display_name": g.user["display_name"]}

    protocol = register_protocol_routes(app, store, authenticated, authorize, actor, utcnow, APIError, identifier)

    def project_view(snapshot):
        return {**snapshot["project"], "head": snapshot["head"], "record_count": len(snapshot["records"])}

    def auth_rate_limit(email):
        now = int(time.time())
        scopes = [("ip:" + digest(request.remote_addr or "unknown"), app.config["AUTH_IP_LIMIT"]),
                  ("email:" + digest(email), app.config["AUTH_ACCOUNT_LIMIT"])]
        blocked = False
        with db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM auth_attempts WHERE attempted_at<=?", (now-app.config["AUTH_WINDOW"],))
            for scope, limit in scopes:
                count = conn.execute("SELECT COUNT(*) FROM auth_attempts WHERE scope=?", (scope,)).fetchone()[0]
                if count >= limit:
                    blocked = True
            if not blocked:
                conn.executemany("INSERT INTO auth_attempts VALUES(?,?)", [(scope, now) for scope, _ in scopes])
        if blocked:
            raise APIError(429, "rate_limit", "Too many sign-in attempts. Please wait 15 minutes before trying again.")

    def credentials(data):
        email = text_field(data, "email", 254, True).casefold()
        password = data.get("password")
        if not isinstance(password, str) or not 1 <= len(password) <= 1024:
            raise APIError(400, "validation", "Check your password.", {"password": "Use 1–1024 characters."})
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise APIError(400, "validation", "Enter a valid email address.", {"email": "Enter a valid email address."})
        auth_rate_limit(email)
        return email, password

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/session")
    def get_session():
        if not g.session:
            new_session()
        return jsonify(session_body())

    @app.post("/api/auth/register")
    def register():
        data = payload({"display_name", "email", "password"})
        email, password = credentials(data)
        name = text_field(data, "display_name", 80, True)
        if any(ord(char) < 32 for char in name):
            raise APIError(400, "validation", "Use a single-line display name.")
        if len(password) < 12:
            raise APIError(400, "validation", "Choose a longer password.", {"password": "Use at least 12 characters."})
        user_id = str(uuid4())
        password_hash = generate_password_hash(password, method="scrypt")
        try:
            with db() as conn:
                conn.execute("INSERT INTO users VALUES(?,?,?,?,?)", (user_id, email, name, password_hash, utcnow()))
        except sqlite3.IntegrityError:
            raise APIError(409, "registration", "This email cannot be registered. Try signing in.") from None
        new_session(user_id)
        return jsonify(session_body()), 201

    # Perform the same password work for an unknown email to reduce timing disclosure.
    dummy_password_hash = generate_password_hash(secrets.token_urlsafe(32), method="scrypt")

    @app.post("/api/auth/login")
    def login():
        email, password = credentials(payload({"email", "password"}))
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        valid = check_password_hash(user["password_hash"] if user else dummy_password_hash, password)
        if not user or not valid:
            raise APIError(401, "credentials", "Email or password is incorrect.")
        new_session(user["id"])
        return jsonify(session_body())

    @app.post("/api/auth/logout")
    def logout():
        new_session()
        return jsonify(session_body())

    @app.get("/api/projects")
    @authenticated
    def list_projects():
        with db() as conn:
            rows = conn.execute("SELECT id FROM projects WHERE owner_id=? ORDER BY created_at DESC,id", (g.user["id"],)).fetchall()
        return jsonify(projects=[project_view(store.snapshot(row["id"])) for row in rows])

    @app.post("/api/projects")
    @authenticated
    def create_project():
        data = payload({"name", "description"})
        project = {"id": str(uuid4()), "name": text_field(data, "name", 120, True),
                   "description": text_field(data, "description", 2000), "created_at": utcnow(),
                   "created_by": actor(), "schema_version": SCHEMA_VERSION, "visibility": "private",
                   "protocol_version": PROTOCOL_VERSION, "profile": PROFILE}
        with db() as conn:
            conn.execute("INSERT INTO projects VALUES(?,?,?)", (project["id"], g.user["id"], project["created_at"]))
            head = store.create_project(project, actor())
        return jsonify(project={**project, "head": head, "record_count": 0}), 201

    @app.get("/api/projects/<project_id>")
    @authenticated
    def get_project(project_id):
        authorize(project_id)
        snapshot = protocol["read_snapshot"](project_id)
        return jsonify({**snapshot, "project": project_view(snapshot)})

    def record_fields(data, snapshot):
        record = {"title": text_field(data, "title", 160, True), "content": text_field(data, "content", 20000, True)}
        for key, options in ENUMS.items():
            value = data.get(key, {"modality": "unknown", "status": "unreviewed"}.get(key))
            if value not in options:
                raise APIError(400, "validation", "Choose a valid recording option.", {key: "Choose one of the available options."})
            record[key] = value
        for key, maximum in {"attributed_to": 300, "method": 2000, "evidence": 5000, "uncertainty": 3000,
                             "alternatives": 3000, "conditions": 3000, "consequences": 3000, "occurred_at": 100}.items():
            record[key] = text_field(data, key, maximum)
        related = data.get("related_records", [])
        if not isinstance(related, list) or len(related) > 50 or any(not isinstance(item, str) for item in related):
            raise APIError(400, "validation", "Choose up to 50 related records in this project.")
        available = {item["id"] for item in snapshot["records"]}
        if any(item not in available for item in related) or len(set(related)) != len(related):
            raise APIError(400, "validation", "Related records must be distinct records from this project.")
        record["related_records"] = related
        return record

    def checked_snapshot(project_id, data):
        snapshot = store.snapshot(project_id)
        head = data.get("expected_head")
        if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
            raise APIError(400, "validation", "Open the current project before saving.", {"expected_head": "A complete project revision is required."})
        if head != snapshot["head"]:
            raise Conflict("The project has changed.")
        if snapshot["project"].get("schema_version") != SCHEMA_VERSION:
            raise APIError(400, "migration_required", "Preview and explicitly migrate this earlier project before making changes.")
        return snapshot

    def compatibility_transaction(project_id, snapshot, operations, reason):
        return protocol["execute"](project_id, {
            "protocol_version": PROTOCOL_VERSION, "transaction_id": str(uuid4()),
            "expected_head": snapshot["head"], "reason": reason,
            "change_categories": ["description"], "operations": operations,
        })

    @app.post("/api/projects/<project_id>/records")
    @authenticated
    def create_record(project_id):
        authorize(project_id)
        data = payload(EDITABLE | {"expected_head"})
        snapshot = checked_snapshot(project_id, data)
        if len(snapshot["records"]) >= app.config["MAX_RECORDS"]:
            raise APIError(400, "record_limit", "This experimental workspace supports up to 1,000 records per project.")
        if snapshot["project"].get("schema_version") == SCHEMA_VERSION:
            record = {**record_fields(data, snapshot), "id": str(uuid4())}
            result = compatibility_transaction(project_id, snapshot, [{"op": "record.create", "record": record}], "Initial record: " + record["title"])
            return jsonify({**store.get_record(project_id, record["id"], result["head"]), "transaction_id": result["transaction_id"]}), 201

    @app.get("/api/projects/<project_id>/records/<record_id>")
    @authenticated
    def get_record(project_id, record_id):
        authorize(project_id)
        identifier(record_id)
        revision = request.args.get("revision")
        if revision is not None and not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise APIError(400, "validation", "Choose a complete revision from this record's history.")
        snapshot = normalize_snapshot(store.snapshot(project_id, revision))
        record = next((r for r in snapshot["records"] if r["id"] == record_id), None)
        if record is None:
            raise NotFound("Record not available")
        return jsonify(record=record, head=snapshot["head"], current_head=store.head(project_id))

    @app.put("/api/projects/<project_id>/records/<record_id>")
    @authenticated
    def update_record(project_id, record_id):
        authorize(project_id)
        identifier(record_id)
        data = payload(EDITABLE | {"expected_head", "revision_reason"})
        snapshot = checked_snapshot(project_id, data)
        previous = next((r for r in snapshot["records"] if r["id"] == record_id), None)
        if not previous:
            raise APIError(404, "not_found", "This record is not available.")
        reason = text_field(data, "revision_reason", 2000, True)
        if snapshot["project"].get("schema_version") == SCHEMA_VERSION:
            changes = record_fields(data, snapshot)
            changes["record_roles"] = sorted(set(previous["record_roles"]) | {changes["record_type"]})
            result = compatibility_transaction(project_id, snapshot, [{"op": "record.update", "record_id": record_id, "changes": changes}], reason)
            return jsonify({**store.get_record(project_id, record_id, result["head"]), "transaction_id": result["transaction_id"]})

    @app.get("/api/projects/<project_id>/records/<record_id>/history")
    @authenticated
    def record_history(project_id, record_id):
        authorize(project_id)
        identifier(record_id)
        return jsonify(history=store.history(project_id, record_id, protocol["revision_arg"]()))

    @app.get("/api/projects/<project_id>/export")
    @authenticated
    def export_project(project_id):
        authorize(project_id)
        snapshot = store.snapshot(project_id, protocol["revision_arg"]())
        snapshot["exported_at"] = utcnow()
        snapshot["export_scope"] = "Selected project snapshot metadata only; attachment bytes are excluded. Use the snapshot package for referenced material or the Git bundle for full history."
        data = (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        return send_file(io.BytesIO(data), mimetype="application/json", as_attachment=True, download_name=f"generativity-{project_id}.json")

    @app.get("/api/projects/<project_id>/bundle")
    @authenticated
    def export_bundle(project_id):
        authorize(project_id)
        return protocol["download"](store.bundle_file(project_id), f"generativity-{project_id}.bundle", "application/octet-stream")

    return app
