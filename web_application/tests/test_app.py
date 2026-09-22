"""Authorization, session and revision behavior against real isolated Git repositories."""
import json
import sqlite3
import time

import pytest

from generative_app import COOKIE, create_app
from gsp_git_store import StoreError

PASSWORD = "a sufficiently long test passphrase"


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATA_DIR": tmp_path / "data", "AUTH_IP_LIMIT": 100})


def csrf(client):
    return {"X-CSRF-Token": client.get("/api/session").json["csrf_token"]}


def register(client, email="author@example.test"):
    response = client.post("/api/auth/register", json={"display_name": "Researcher <A>", "email": email, "password": PASSWORD}, headers=csrf(client))
    assert response.status_code == 201, response.json
    return response.json


def project(client, name="A project"):
    response = client.post("/api/projects", json={"name": name, "description": "Uncertain observations"}, headers=csrf(client))
    assert response.status_code == 201, response.json
    return response.json["project"]


def record_data(head):
    return {"title": "An observed encounter", "content": "The explanation is provisional.",
            "record_type": "Event", "epistemic_mode": "retrospective", "modality": "realized",
            "status": "contested", "attributed_to": "A source distinct from the recorder",
            "uncertainty": "Incomplete evidence", "method": "Retrospective inference",
            "occurred_at": "Approximately spring 2025", "expected_head": head}


def save_record(client, p):
    response = client.post(f"/api/projects/{p['id']}/records", json=record_data(p["head"]), headers=csrf(client))
    assert response.status_code == 201, response.json
    return response.json


def test_registration_session_rotation_password_hash_and_logout(app):
    client = app.test_client()
    anonymous = csrf(client)["X-CSRF-Token"]
    old_cookie = client.get_cookie(COOKIE).value
    result = register(client)
    assert result["user"]["email"] == "author@example.test"
    assert result["csrf_token"] != anonymous
    assert client.get_cookie(COOKIE).value != old_cookie
    with sqlite3.connect(app.config["DATA_DIR"] / "accounts.sqlite3") as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        assert stored.startswith("scrypt:") and PASSWORD not in stored
        assert client.get_cookie(COOKIE).value not in str(conn.execute("SELECT * FROM sessions").fetchall())
    replay = app.test_client()
    replay.set_cookie(COOKIE, old_cookie)
    assert replay.get("/api/projects").status_code == 401
    signed_in_cookie = client.get_cookie(COOKIE).value
    out = client.post("/api/auth/logout", headers=csrf(client))
    assert out.status_code == 200 and out.json["user"] is None
    replay.set_cookie(COOKIE, signed_in_cookie)
    assert replay.get("/api/projects").status_code == 401
    assert client.get("/api/projects").status_code == 401
    wrong = client.post("/api/auth/login", json={"email": "author@example.test", "password": "incorrect"}, headers=csrf(client))
    assert wrong.status_code == 401
    good = client.post("/api/auth/login", json={"email": "AUTHOR@EXAMPLE.TEST", "password": PASSWORD}, headers=csrf(client))
    assert good.status_code == 200


def test_csrf_origin_content_type_and_headers(app):
    client = app.test_client()
    response = client.get("/api/session")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert client.post("/api/auth/register", json={}).status_code == 403
    headers = csrf(client)
    headers["Origin"] = "https://another.example"
    assert client.post("/api/auth/logout", headers=headers).status_code == 403
    assert client.post("/api/auth/login", data="{}", headers=csrf(client)).status_code == 415
    assert client.get("/api/session", headers={"Host": "attacker.example"}).status_code == 400


def test_expired_session_cannot_read_or_mutate(app):
    client = app.test_client()
    register(client)
    token = csrf(client)
    with sqlite3.connect(app.config["DATA_DIR"] / "accounts.sqlite3") as conn:
        conn.execute("UPDATE sessions SET expires_at=?", (int(time.time()) - 1,))
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json={"name": "forbidden"}, headers=token).status_code == 403


def test_each_project_route_checks_ownership_including_past_revisions(app):
    owner, other = app.test_client(), app.test_client()
    register(owner)
    p = project(owner)
    saved = save_record(owner, p)
    pid, rid = p["id"], saved["record"]["id"]
    register(other, "other@example.test")
    assert other.get("/api/projects").json == {"projects": []}
    for suffix in ("", "/export", "/bundle", f"/records/{rid}", f"/records/{rid}/history", f"/records/{rid}?revision={saved['head']}"):
        assert other.get(f"/api/projects/{pid}{suffix}").status_code == 404
    assert other.post(f"/api/projects/{pid}/records", json=record_data(saved["head"]), headers=csrf(other)).status_code == 404
    assert other.put(f"/api/projects/{pid}/records/{rid}", json={}, headers=csrf(other)).status_code == 404
    assert other.get("/api/projects/not-a-uuid").status_code == 404


def test_revision_history_conflict_restart_and_exports(app):
    client = app.test_client()
    user = register(client)["user"]
    p = project(client, "Research & reconstruction")
    saved = save_record(client, p)
    rid = saved["record"]["id"]
    endpoint = f"/api/projects/{p['id']}/records/{rid}"
    updated = {**record_data(saved["head"]), "title": "A revised interpretation", "revision_reason": "A second source qualified the observation."}
    result = client.put(endpoint, json=updated, headers=csrf(client))
    assert result.status_code == 200, result.json
    record = result.json["record"]
    assert record["recorded_by"]["id"] == user["id"]
    assert record["created_at"] == saved["record"]["created_at"]
    assert record["attributed_to"] != user["display_name"]
    assert client.get(endpoint + "?revision=" + saved["head"]).json["record"]["title"] == "An observed encounter"
    stale = client.put(endpoint, json=updated, headers=csrf(client))
    assert stale.status_code == 409 and stale.json["error"]["code"] == "conflict"
    assert client.get(endpoint).json["record"]["title"] == "A revised interpretation"
    history = client.get(endpoint + "/history").json["history"]
    assert len(history) == 2 and history[0]["reason"] == updated["revision_reason"]
    export = client.get(f"/api/projects/{p['id']}/export")
    assert export.status_code == 200 and "attachment" in export.headers["Content-Disposition"]
    assert json.loads(export.data)["records"][0]["id"] == rid
    bundle = client.get(f"/api/projects/{p['id']}/bundle")
    assert bundle.status_code == 200 and bundle.data.startswith(b"# v2 git bundle")
    restarted = create_app({"TESTING": True, "DATA_DIR": app.config["DATA_DIR"]}).test_client()
    restarted.set_cookie(COOKIE, client.get_cookie(COOKIE).value)
    assert restarted.get(endpoint).json["record"]["title"] == "A revised interpretation"


def test_input_validation_and_cross_project_record_links(app):
    client = app.test_client()
    register(client)
    p1, p2 = project(client), project(client)
    one = save_record(client, p1)
    endpoint = f"/api/projects/{p2['id']}/records"
    body = record_data(p2["head"])
    for change in ({"record_type": "AbsoluteReality"}, {"status": "legally_proven"}, {"recorded_by": {"id": "fake"}},
                   {"related_records": [one["record"]["id"]]}, {"title": ""}, {"content": "x" * 20001}):
        assert client.post(endpoint, json={**body, **change}, headers=csrf(client)).status_code == 400
    assert client.get(f"/api/projects/{p2['id']}").json["records"] == []
    new_head = one["head"]
    related = client.post(f"/api/projects/{p1['id']}/records", json={**record_data(new_head), "related_records": [one["record"]["id"]]}, headers=csrf(client))
    assert related.status_code == 201
    record_url = f"/api/projects/{p1['id']}/records/{one['record']['id']}"
    assert client.put(record_url, json=record_data(related.json["head"]), headers=csrf(client)).status_code == 400
    assert client.get(record_url + "?revision=main~1").status_code == 400


def test_failed_save_returns_error_without_visible_change(app, monkeypatch):
    client = app.test_client()
    register(client)
    p = project(client)
    store = app.extensions["git_store"]
    before = store.snapshot(p["id"])
    def fail(*args, **kwargs):
        raise StoreError("private details never shown")
    monkeypatch.setattr(store, "_publish", fail)
    response = client.post(f"/api/projects/{p['id']}/records", json=record_data(p["head"]), headers=csrf(client))
    assert response.status_code == 503
    assert b"private details" not in response.data
    assert store.snapshot(p["id"]) == before


def test_rate_limit_is_persistent_and_blocks_password_work(tmp_path):
    config = {"TESTING": True, "DATA_DIR": tmp_path / "rate-data", "AUTH_ACCOUNT_LIMIT": 2}
    app = create_app(config)
    client = app.test_client()
    body = {"email": "unknown@example.test", "password": "wrong"}
    for _ in range(2):
        assert client.post("/api/auth/login", json=body, headers=csrf(client)).status_code == 401
    new_client = create_app(config).test_client()
    response = new_client.post("/api/auth/login", json=body, headers=csrf(new_client))
    assert response.status_code == 429 and response.headers["Retry-After"] == "900"


def test_duplicate_registration_and_short_password(app):
    client = app.test_client()
    register(client)
    fields = {"email": "author@example.test", "password": PASSWORD, "display_name": "Another name"}
    assert client.post("/api/auth/register", json=fields, headers=csrf(client)).status_code == 409
    fields.update(email="new@example.test", password="short")
    assert client.post("/api/auth/register", json=fields, headers=csrf(client)).status_code == 400


def test_secure_cookie_configuration(tmp_path):
    client = create_app({"TESTING": True, "DATA_DIR": tmp_path / "secure-data", "COOKIE_SECURE": True}).test_client()
    assert "; Secure;" in client.get("/api/session").headers["Set-Cookie"]


def test_malformed_unicode_is_rejected_without_rejecting_valid_unicode(app):
    client = app.test_client()
    headers = csrf(client)
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": "é"}).status_code == 403
    body = {"email": "unicode@example.test", "password": "abcdefghijk\ud800", "display_name": "Researcher"}
    assert client.post("/api/auth/register", json=body, headers=headers).status_code == 400
    body.update(password=PASSWORD, display_name="研究者 🌱")
    assert client.post("/api/auth/register", json=body, headers=headers).status_code == 201
    p = project(client, "生成と記録 🌱")
    record = {**record_data(p["head"]), "title": "観察 🌿", "content": "Révision — 不確かさを保持する。"}
    saved = client.post(f"/api/projects/{p['id']}/records", json=record, headers=csrf(client))
    assert saved.status_code == 201 and saved.json["record"]["title"] == "観察 🌿"
