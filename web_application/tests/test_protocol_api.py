"""Cross-layer tests: authenticated HTTP, shared semantics, real Git and bytes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import io
import json
import sqlite3
from uuid import uuid4
import zipfile

import pytest
from werkzeug.datastructures import MultiDict
from gsp_protocol import PROTOCOL_VERSION

from generative_app import COOKIE, create_app, utcnow
from gsp_git_store import StoreError
from test_app import app, csrf, project, register, record_data


def uid():
    return str(uuid4())


def record(title="A participant", role="Entity"):
    return {"id": uid(), "title": title, "content": "An attributed provisional account.",
            "record_type": role, "epistemic_mode": "reported"}


def tx(head, operations, reason="Record a qualified connection"):
    return {"protocol_version": PROTOCOL_VERSION, "transaction_id": uid(), "expected_head": head,
            "reason": reason, "change_categories": ["description"], "operations": operations}


def post(client, pid, transaction, files=None):
    url = f"/api/projects/{pid}/transactions"
    if files is None:
        return client.post(url, json=transaction, headers=csrf(client))
    data = {"transaction": json.dumps(transaction)}
    data.update({name: (io.BytesIO(value), name + ".bin") for name, value in files.items()})
    return client.post(url, data=data, headers=csrf(client))


def relation(participants):
    result = record("An enabling relationship", "Relation")
    result["record_roles"] = ["Relation", "Entity"]
    result["modules"] = {"gsp.relation": {"version": "1", "required": False, "data": {
        "predicate": "enabled", "participants_complete": False, "participant_limitations": "Other contributors are unknown.",
        "participants": [{"id": uid(), "record_id": rid, "role": role, "reference_scope": "represented_target", "orientation": "undirected"} for rid, role in participants]
    }}}
    return result


def attach(rid, value, file_id=None, op="file.attach"):
    return {"op": op, "record_id": rid, "file_id": file_id or uid(), "part": "material",
            "filename": "source evidence.txt", "media_type": "text/plain", "sha256": hashlib.sha256(value).hexdigest(), "byte_length": len(value)}


def setup(client):
    register(client)
    return project(client)


def test_atomic_graph_forward_higher_order_repeated_participants_and_pinned_labels(app):
    client = app.test_client()
    p = setup(client)
    first, second = record("First participant"), record("Second participant")
    rel = relation([(first["id"], "initiator"), (second["id"], "partner"), (first["id"], "recipient")])
    higher = relation([(rel["id"], "interpreted relation"), (rel["id"], "qualified relation")])
    transaction = tx(p["head"], [{"op": "record.create", "record": r} for r in [higher, rel, first, second]])
    saved = post(client, p["id"], transaction)
    assert saved.status_code == 201, saved.json
    head = saved.json["head"]
    graph = client.get(f"/api/projects/{p['id']}/graph").json
    assert graph["head"] == head and len(graph["nodes"]) == 4 and len(graph["edges"]) == 5
    assert all(e["kind"] == "incidence" for e in graph["edges"])
    updated = post(client, p["id"], tx(head, [{"op": "record.update", "record_id": first["id"], "changes": {"title": "Renamed participant"}}]))
    assert updated.status_code == 201, updated.json
    old = client.get(f"/api/projects/{p['id']}/graph?revision={head}").json
    assert next(n for n in old["nodes"] if n["id"] == first["id"])["label"] == "First participant"
    assert old["current_head"] == updated.json["head"]
    snapshot = client.get(f"/api/projects/{p['id']}?revision={head}").json
    assert snapshot["head"] == head and len(snapshot["records"]) == 4
    history = client.get(f"/api/projects/{p['id']}/records/{first['id']}/history?revision={head}").json["history"]
    assert len(history) == 1 and history[0]["commit"] == head


def test_receipt_replay_after_later_edit_and_restart_and_changed_request_rejected(app):
    client = app.test_client()
    p = setup(client)
    r = record()
    transaction = tx(p["head"], [{"op": "record.create", "record": r}])
    saved = post(client, p["id"], transaction)
    later = post(client, p["id"], tx(saved.json["head"], [{"op": "record.update", "record_id": r["id"], "changes": {"title": "Later title"}}]))
    restarted = create_app({"TESTING": True, "DATA_DIR": app.config["DATA_DIR"]}).test_client()
    restarted.set_cookie(COOKIE, client.get_cookie(COOKIE).value)
    replay = post(restarted, p["id"], transaction)
    assert replay.status_code == 200 and replay.json["replayed"] is True
    assert replay.json["head"] == saved.json["head"]
    assert restarted.get(f"/api/projects/{p['id']}").json["head"] == later.json["head"]
    changed = deepcopy(transaction)
    changed["reason"] = "Changed semantic request"
    response = post(restarted, p["id"], changed)
    assert response.status_code == 409 and response.json["error"]["code"] == "transaction_id_reused"
    receipt = restarted.get(f"/api/projects/{p['id']}/transactions/{transaction['transaction_id']}").json
    assert receipt["head"] == saved.json["head"] and receipt["receipt"]["actor"]["id"]


def test_files_atomic_replace_detach_historical_access_and_precise_package(app):
    client = app.test_client()
    p = setup(client)
    r, original, replacement = record(), b"First retained bytes", b"New interpretation and material"
    operation = attach(r["id"], original)
    initial = tx(p["head"], [{"op": "record.create", "record": r}, operation])
    saved = post(client, p["id"], initial, {"material": original})
    assert saved.status_code == 201, saved.json
    head = saved.json["head"]
    endpoint = f"/api/projects/{p['id']}/records/{r['id']}/files/{operation['file_id']}"
    response = client.get(endpoint)
    assert response.data == original and response.headers["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in response.headers["Content-Disposition"]
    replaced = post(client, p["id"], tx(head, [attach(r["id"], replacement, operation["file_id"], "file.replace")]), {"material": replacement})
    assert replaced.status_code == 201, replaced.json
    assert client.get(endpoint).data == replacement
    assert client.get(endpoint + "?revision=" + head).data == original
    package = client.get(f"/api/projects/{p['id']}/package")
    with zipfile.ZipFile(io.BytesIO(package.data)) as archive:
        paths = archive.namelist()
        assert "assets/" + hashlib.sha256(replacement).hexdigest() in paths
        assert "assets/" + hashlib.sha256(original).hexdigest() not in paths
        assert not any(path.startswith(".gsp/") for path in paths)
    detached = post(client, p["id"], tx(replaced.json["head"], [{"op": "file.detach", "record_id": r["id"], "file_id": operation["file_id"]}]))
    assert detached.status_code == 201, detached.json
    assert client.get(endpoint).status_code == 404
    assert client.get(endpoint + "?revision=" + head).data == original
    replay = post(client, p["id"], initial, {"material": original})
    assert replay.status_code == 200 and replay.json["head"] == head


def test_bad_bytes_and_storage_failure_publish_nothing(app, monkeypatch):
    client = app.test_client()
    p = setup(client)
    r = record()
    operation = attach(r["id"], b"expected")
    transaction = tx(p["head"], [{"op": "record.create", "record": r}, operation])
    response = post(client, p["id"], transaction, {"material": b"wrong"})
    assert response.status_code == 400, response.json
    store = app.extensions["git_store"]
    assert store.head(p["id"]) == p["head"]
    def fail(*args, **kwargs):
        raise StoreError("Internal detail")
    monkeypatch.setattr(store, "_publish", fail)
    response = post(client, p["id"], transaction, {"material": b"expected"})
    assert response.status_code == 503 and b"Internal detail" not in response.data
    assert store.head(p["id"]) == p["head"] and store.transaction_receipt(p["id"], transaction["transaction_id"]) is None


def test_opaque_optional_module_preserved_by_compatibility_edit(app):
    client = app.test_client()
    p = setup(client)
    r = record()
    opaque = {"version": "8", "required": False, "data": {"unfamiliar": ["source-specific", {"value": 7}]}}
    saved = post(client, p["id"], tx(p["head"], [{"op": "record.create", "record": r}]))
    assert saved.status_code == 201, saved.json
    # Simulate retained content produced by a future capable implementation;
    # this client deliberately cannot introduce or reinterpret unknown modules.
    store = app.extensions["git_store"]
    future = store.get_record(p["id"], r["id"])["record"]
    future["modules"]["example.future"] = opaque
    head = store.write_record(p["id"], future, future["recorded_by"], saved.json["head"], "Fixture from future producer")
    result = client.put(f"/api/projects/{p['id']}/records/{r['id']}", json={**record_data(head), "revision_reason": "Clarify the account"}, headers=csrf(client))
    assert result.status_code == 200, result.json
    assert result.json["record"]["modules"]["example.future"] == opaque
    assert "Entity" in result.json["record"]["record_roles"]
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{p['id']}/package").data)) as archive:
        manifest = json.loads(archive.read("package.json"))
        assert any(w.get("module_id") == "example.future" for w in manifest["warnings"])
        assert "opaque modules" in manifest["limitations"]
        retained = json.loads(archive.read(f"records/{r['id']}.json"))
        assert retained["modules"]["example.future"] == opaque
    future = result.json["record"]
    future["modules"]["example.future"]["required"] = True
    head = store.write_record(p["id"], future, future["recorded_by"], result.json["head"], "Required future capability fixture")
    refused = post(client, p["id"], tx(head, [{"op": "record.create", "record": record()}]))
    assert refused.status_code == 400 and store.head(p["id"]) == head


@pytest.mark.parametrize("raw", ['{"transaction_id":"one","transaction_id":"two"}', '{"x":NaN}', '{"x":1e999}', '{"x":"\\ud800"}'])
def test_strict_json_is_rejected_without_mutation(app, raw):
    client = app.test_client()
    p = setup(client)
    response = client.post(f"/api/projects/{p['id']}/transactions", data=raw, content_type="application/json", headers=csrf(client))
    assert response.status_code == 400
    assert app.extensions["git_store"].head(p["id"]) == p["head"]


def test_multipart_rejects_duplicate_extra_parts_and_filename_paths(app):
    client = app.test_client()
    p = setup(client)
    r = record()
    operation = attach(r["id"], b"x")
    transaction = tx(p["head"], [{"op": "record.create", "record": r}, operation])
    data = MultiDict([("transaction", json.dumps(transaction)), ("material", (io.BytesIO(b"x"), "a")), ("material", (io.BytesIO(b"x"), "b"))])
    assert client.post(f"/api/projects/{p['id']}/transactions", data=data, headers=csrf(client)).status_code == 400
    assert post(client, p["id"], transaction, {"material": b"x", "extra": b"x"}).status_code == 400
    operation["filename"] = "../escape.txt"
    assert post(client, p["id"], transaction, {"material": b"x"}).status_code == 400
    assert app.extensions["git_store"].head(p["id"]) == p["head"]


def test_new_routes_are_owner_scoped_and_unreachable_revision_rejected(app):
    client, other = app.test_client(), app.test_client()
    p = setup(client)
    register(other, "outsider@example.test")
    for suffix in ("/graph", "/history", "/migration", "/package", f"/transactions/{uid()}", f"/records/{uid()}/files/{uid()}"):
        assert other.get(f"/api/projects/{p['id']}{suffix}").status_code == 404
    assert post(other, p["id"], tx(p["head"], [{"op": "record.create", "record": record()}])).status_code == 404
    for suffix in ("", "/graph", "/package", "/export"):
        assert client.get(f"/api/projects/{p['id']}{suffix}?revision={'f'*40}").status_code == 404


def test_explicit_legacy_migration_preserves_old_revisions_and_neutral_links(app):
    client = app.test_client()
    user = register(client)["user"]
    actor = {"id": user["id"], "display_name": user["display_name"]}
    pid = uid()
    legacy = {"id": pid, "name": "Earlier workspace", "description": "", "created_at": utcnow(), "created_by": actor, "schema_version": "gsp-workspace/0.1", "visibility": "private"}
    with sqlite3.connect(app.config["DATA_DIR"] / "accounts.sqlite3") as conn:
        conn.execute("INSERT INTO projects VALUES(?,?,?)", (pid, actor["id"], legacy["created_at"]))
    store = app.extensions["git_store"]
    head = store.create_project(legacy, actor)
    from gsp_protocol import prepare_transaction
    # Create an authentic old-format fixture independently of HTTP mutation.
    modern = {"project": {**legacy, "schema_version": "gsp-workspace/0.2"}, "records": [], "head": head}
    a = record()
    b = {**record("Earlier unstructured relation", "Relation"), "related_records": [a["id"]]}
    candidate = prepare_transaction(modern, tx(head, [{"op": "record.create", "record": a}, {"op": "record.create", "record": b}]), actor, utcnow())["snapshot"]
    for item in candidate["records"]:
        item["schema_version"] = "gsp-workspace/0.1"
        item.pop("record_roles")
        item.pop("modules")
        head = store.write_record(pid, item, actor, head, "Legacy fixture")
    assert client.get(f"/api/projects/{pid}").json["legacy"] is True
    assert store.head(pid) == head
    response = client.post(f"/api/projects/{pid}/records", json=record_data(head), headers=csrf(client))
    assert response.status_code == 400 and response.json["error"]["code"] == "migration_required"
    response = client.put(f"/api/projects/{pid}/records/{a['id']}", json={**record_data(head), "revision_reason": "Must migrate first"}, headers=csrf(client))
    assert response.status_code == 400 and response.json["error"]["code"] == "migration_required"
    preview = client.get(f"/api/projects/{pid}/migration").json
    assert preview["needed"] and preview["neutral_references"] == 1 and preview["unstructured_relations"] == 1
    transaction = tx(head, [{"op": "project.migrate"}], "Adopt experimental protocol with no inferred semantic links")
    transaction["change_categories"] = ["migration"]
    migrated = post(client, pid, transaction)
    assert migrated.status_code == 201, migrated.json
    assert client.get(f"/api/projects/{pid}").json["legacy"] is False
    assert store.snapshot(pid, head)["project"]["schema_version"] == "gsp-workspace/0.1"
    graph = client.get(f"/api/projects/{pid}/graph").json
    assert len(graph["edges"]) == 1 and graph["edges"][0]["kind"] == "reference"


def test_concurrent_identical_requests_publish_once_and_replay(app):
    client = app.test_client()
    p = setup(client)
    transaction = tx(p["head"], [{"op": "record.create", "record": record()}])
    cookie = client.get_cookie(COOKIE).value
    headers = csrf(client)
    def submit(_):
        concurrent_client = app.test_client()
        concurrent_client.set_cookie(COOKIE, cookie)
        response = concurrent_client.post(f"/api/projects/{p['id']}/transactions", json=transaction, headers=headers)
        return response.status_code, response.json
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(status for status, _ in results) == [200, 201], results
    assert results[0][1]["head"] == results[1][1]["head"]
    assert len(client.get(f"/api/projects/{p['id']}/history").json["history"]) == 2


def test_retry_race_between_first_receipt_lookup_and_snapshot(app, monkeypatch):
    from gsp_protocol import prepare_transaction
    client = app.test_client()
    p = setup(client)
    transaction = tx(p["head"], [{"op": "record.create", "record": record()}])
    store = app.extensions["git_store"]
    snapshot = store.snapshot(p["id"])
    actor = snapshot["project"]["created_by"]
    prepared = prepare_transaction(snapshot, transaction, actor, utcnow())
    lookup, first_call = store.transaction_receipt, True
    committed = []
    def racing_lookup(pid, tid):
        nonlocal first_call
        if first_call:
            first_call = False
            assert lookup(pid, tid) is None
            committed.append(store.commit_transaction(pid, prepared["snapshot"], prepared["receipt"], actor, p["head"]))
            return None
        return lookup(pid, tid)
    monkeypatch.setattr(store, "transaction_receipt", racing_lookup)
    response = post(client, p["id"], transaction)
    assert response.status_code == 200 and response.json["replayed"] is True, response.json
    assert response.json["head"] == committed[0]


def test_upload_byte_limit_returns413_without_publication(app):
    client = app.test_client()
    p = setup(client)
    r = record()
    value = b"x" * (10 * 1024 * 1024 + 1)
    operation = attach(r["id"], b"x")  # Actual stream, not a claimed length, controls HTTP resource use.
    transaction = tx(p["head"], [{"op": "record.create", "record": r}, operation])
    response = post(client, p["id"], transaction, {"material": value})
    assert response.status_code == 413, response.json
    assert app.extensions["git_store"].head(p["id"]) == p["head"]
