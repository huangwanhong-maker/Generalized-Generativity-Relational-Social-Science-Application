"""Authenticated HTTP binding for the independent experimental record protocol."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from flask import jsonify, request, send_file
from gsp_protocol import (
    PROTOCOL_VERSION, SCHEMA_VERSION, capabilities, normalize_snapshot,
    prepare_transaction, project_graph, request_digest, validate_transaction, validate_snapshot,
)

from gsp_git_store import Conflict, NotFound

JSON_LIMIT = 1024 * 1024
FILE_LIMIT = 10 * 1024 * 1024
REQUEST_FILE_LIMIT = 20 * 1024 * 1024


def strict_json(raw):
    """Reject representations whose duplicate keys or numeric values are ambiguous."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON member")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("Non-finite JSON number")

    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if not isinstance(result, dict):
        raise ValueError("Expected an object")
    return result


def register_protocol_routes(app, store, authenticated, authorize, actor, utcnow, APIError, identifier):
    def revision_arg():
        revision = request.args.get("revision")
        if revision is not None and not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise APIError(400, "validation", "Choose a complete project revision.")
        return revision

    def read_snapshot(project_id):
        raw = store.snapshot(project_id, revision_arg())
        snapshot = normalize_snapshot(raw)
        snapshot["current_head"] = store.head(project_id)
        return snapshot

    def replay_result(project_id, tx, digest):
        found = store.transaction_receipt(project_id, tx["transaction_id"])
        if found is None:
            return None
        receipt = found["receipt"]
        if receipt.get("actor", {}).get("id") != actor()["id"] or receipt.get("request_digest") != digest:
            raise APIError(409, "transaction_id_reused", "This transaction identifier already belongs to a different request. Review your draft and save it as a new transaction.")
        return {"head": found["head"], "transaction_id": tx["transaction_id"], "receipt": receipt, "replayed": True}

    def execute(project_id, tx, files_meta=None, assets=None):
        """Caller authenticates/authorizes first; all mutation paths share this fence."""
        files_meta = files_meta or {}
        validate_transaction(tx)
        digest = request_digest(tx, files_meta)
        replay = replay_result(project_id, tx, digest)
        if replay:
            return replay
        snapshot = store.snapshot(project_id)
        if snapshot["head"] != tx["expected_head"]:
            replay = replay_result(project_id, tx, digest)
            if replay:
                return replay
            raise Conflict("Project changed before validation")
        prepared = prepare_transaction(snapshot, tx, actor(), utcnow(), files_meta)
        try:
            head = store.commit_transaction(project_id, prepared["snapshot"], prepared["receipt"], actor(), tx["expected_head"], assets=assets)
        except Conflict:
            # A concurrent identical submission can win publication while this
            # request prepares its tree. Resolve that accepted receipt first.
            replay = replay_result(project_id, tx, digest)
            if replay:
                return replay
            raise
        return {"head": head, "transaction_id": tx["transaction_id"], "receipt": prepared["receipt"], "replayed": False}

    def load_transaction():
        parts = {}
        if request.is_json:
            raw = request.get_data()
        elif request.mimetype == "multipart/form-data":
            if set(request.form) != {"transaction"} or len(request.form.getlist("transaction")) != 1:
                raise APIError(400, "multipart", "Provide exactly one transaction JSON field.")
            raw = request.form["transaction"]
            if len(request.files) > 8:
                raise APIError(413, "file_limit", "Attach at most eight files in one save.")
            for name in request.files:
                values = request.files.getlist(name)
                if len(values) != 1 or name == "transaction":
                    raise APIError(400, "multipart", "Each binary part needs a unique name.")
                parts[name] = values[0]
        else:
            raise APIError(415, "content_type", "Send JSON or a multipart transaction with files.")
        if len(raw.encode("utf-8") if isinstance(raw, str) else raw) > JSON_LIMIT:
            raise APIError(413, "transaction_limit", "The transaction description exceeds one MiB.")
        try:
            tx = strict_json(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise APIError(400, "validation", "Use a JSON object with unique fields, finite numbers and valid Unicode.") from None
        validate_transaction(tx)
        expected = [op["part"] for op in tx["operations"] if op["op"] in {"file.attach", "file.replace"}]
        if len(set(expected)) != len(expected) or set(expected) != set(parts):
            raise APIError(400, "multipart", "The binary parts must match the file operations exactly.")
        return tx, parts

    @app.get("/api/protocol")
    def get_protocol():
        result = capabilities()
        result["http_binding"] = {"file_bytes": FILE_LIMIT, "request_file_bytes": REQUEST_FILE_LIMIT,
                                  "transaction_json_bytes": JSON_LIMIT, "file_parts": 8,
                                  "snapshot_json_bytes": 32 * 1024 * 1024,
                                  "resource_json_bytes": 2 * 1024 * 1024,
                                  "retained_asset_bytes": 128 * 1024 * 1024}
        return jsonify(result)

    @app.post("/api/projects/<project_id>/transactions")
    @authenticated
    def transact(project_id):
        authorize(project_id)
        tx, parts = load_transaction()
        with tempfile.TemporaryDirectory(prefix="gsp-upload-") as folder:
            files_meta, assets, total = {}, {}, 0
            for index, (name, part) in enumerate(parts.items()):
                target = Path(folder) / str(index)
                size, hasher = 0, hashlib.sha256()
                with target.open("wb") as output:
                    while chunk := part.stream.read(64 * 1024):
                        size += len(chunk)
                        total += len(chunk)
                        if size > FILE_LIMIT or total > REQUEST_FILE_LIMIT:
                            raise APIError(413, "file_limit", "Use files up to 10 MiB each and 20 MiB in one save.")
                        hasher.update(chunk)
                        output.write(chunk)
                sha = hasher.hexdigest()
                files_meta[name] = {"sha256": sha, "byte_length": size}
                assets[sha] = target
            result = execute(project_id, tx, files_meta, assets)
        return jsonify(result), 200 if result["replayed"] else 201

    @app.get("/api/projects/<project_id>/transactions/<transaction_id>")
    @authenticated
    def get_transaction(project_id, transaction_id):
        authorize(project_id)
        identifier(transaction_id)
        found = store.transaction_receipt(project_id, transaction_id)
        if not found:
            raise NotFound("Transaction not found")
        return jsonify(found)

    @app.get("/api/projects/<project_id>/graph")
    @authenticated
    def get_graph(project_id):
        authorize(project_id)
        snapshot = read_snapshot(project_id)
        return jsonify({**project_graph(snapshot), "current_head": snapshot["current_head"], "legacy": snapshot["legacy"]})

    @app.get("/api/projects/<project_id>/history")
    @authenticated
    def project_history(project_id):
        authorize(project_id)
        return jsonify(history=store.project_history(project_id))

    @app.get("/api/projects/<project_id>/migration")
    @authenticated
    def migration_preview(project_id):
        authorize(project_id)
        snapshot = normalize_snapshot(store.snapshot(project_id))
        return jsonify(needed=snapshot["legacy"], head=snapshot["head"],
                       from_version=snapshot["project"].get("schema_version"), to_version=SCHEMA_VERSION,
                       record_count=len(snapshot["records"]),
                       unstructured_relations=sum("Relation" in r["record_roles"] and "gsp.relation" not in r["modules"] for r in snapshot["records"]),
                       neutral_references=sum(len(r.get("related_records", [])) for r in snapshot["records"]),
                       limitations=["Earlier revisions remain unchanged.", "Neutral references remain neutral; no structured relation, evidence or missing attribution is invented.", "Migration is one explicit, attributed transaction."])

    def download(handle, name, mimetype):
        # Werkzeug's file wrapper closes on response completion/disconnection.
        try:
            response = send_file(handle, mimetype=mimetype, as_attachment=True, download_name=name, conditional=False, etag=False)
        except BaseException:
            handle.close()
            raise
        response.call_on_close(handle.close)
        return response

    def checked_asset(project_id, item, revision):
        handle = store.asset_file(project_id, item["sha256"], revision)
        size, hasher = 0, hashlib.sha256()
        try:
            while chunk := handle.read(64 * 1024):
                hasher.update(chunk)
                size += len(chunk)
            if size != item["byte_length"] or hasher.hexdigest() != item["sha256"]:
                from gsp_git_store import StoreError
                raise StoreError("Retained bytes disagree with descriptor")
            handle.seek(0)
            return handle
        except BaseException:
            handle.close()
            raise

    @app.get("/api/projects/<project_id>/records/<record_id>/files/<file_id>")
    @authenticated
    def get_file(project_id, record_id, file_id):
        authorize(project_id)
        identifier(record_id)
        identifier(file_id)
        snapshot = read_snapshot(project_id)
        record = next((r for r in snapshot["records"] if r["id"] == record_id), None)
        module = record.get("modules", {}).get("gsp.files", {}) if record else {}
        if module.get("version") != "1":
            raise NotFound("File module not available")
        item = next((i for i in module["data"]["items"] if i["file_id"] == file_id), None)
        if item is None:
            raise NotFound("File not present in this record revision")
        return download(checked_asset(project_id, item, snapshot["head"]), item["filename"], "application/octet-stream")

    @app.get("/api/projects/<project_id>/package")
    @authenticated
    def export_package(project_id):
        authorize(project_id)
        # Use exact stored representations, not display adaptation, for interchange.
        snapshot = store.snapshot(project_id, revision_arg())
        validation = validate_snapshot(snapshot)
        output = tempfile.TemporaryFile(mode="w+b")
        try:
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                manifest = {"protocol_version": PROTOCOL_VERSION, "scope": "selected_snapshot_with_referenced_material",
                            "head": snapshot["head"], "exported_at": utcnow(),
                            "warnings": validation["warnings"],
                            "limitations": "Includes material referenced by supported gsp.files version 1 descriptors. Dependencies inside opaque modules are not reconstructed. Excludes transaction receipts, earlier revisions and unreferenced retained assets. This package is not a full history backup."}
                for path, data in [("package.json", manifest), ("project.json", snapshot["project"])]:
                    archive.writestr(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                copied = set()
                for record in snapshot["records"]:
                    archive.writestr(f"records/{record['id']}.json", json.dumps(record, ensure_ascii=False, indent=2) + "\n")
                    module = record.get("modules", {}).get("gsp.files", {})
                    if module.get("version") != "1":
                        continue
                    for item in module["data"]["items"]:
                        if item["sha256"] in copied:
                            continue
                        with checked_asset(project_id, item, snapshot["head"]) as handle, archive.open("assets/" + item["sha256"], "w") as member:
                            shutil.copyfileobj(handle, member, 64 * 1024)
                        copied.add(item["sha256"])
            output.seek(0)
            return download(output, f"generativity-{project_id}-{snapshot['head'][:12]}.zip", "application/zip")
        except BaseException:
            output.close()
            raise

    return {"execute": execute, "read_snapshot": read_snapshot, "revision_arg": revision_arg, "download": download}
