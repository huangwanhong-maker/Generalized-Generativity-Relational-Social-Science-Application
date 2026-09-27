"""Represented event time is independent of authenticated, retained Git history."""
import sqlite3

from generative_app import utcnow
from test_app import app, csrf, register
from test_protocol_api import post, record, setup, tx, uid


def order(before, after):
    result = record("Reported precedence", "Relation")
    result["modules"] = {
        "gsp.event_order": {"version": "1", "required": True, "data": {"before": before, "after": after}},
        "gsp.relation": {"version": "1", "required": False, "data": {
            "predicate": "precedes", "participants_complete": True,
            "participants": [
                {"id": uid(), "record_id": before, "role": "before", "orientation": "in", "reference_scope": "represented_target"},
                {"id": uid(), "record_id": after, "role": "after", "orientation": "out", "reference_scope": "represented_target"},
            ],
        }},
    }
    return result


def extent(start, end, subject=None):
    data = {"start": start, "end": end, "basis": "Witness report; continuity is a provisional interpretation."}
    if subject:
        data["subject_record_id"] = subject
    return {"version": "1", "required": True, "data": data}


def create(client, pid, head, *records):
    response = post(client, pid, tx(head, [{"op": "record.create", "record": r} for r in records]))
    assert response.status_code == 201, response.json
    return response.json["head"]


def cut(client, pid, after, head=None):
    suffix = f"?revision={head}" if head else ""
    return client.post(f"/api/projects/{pid}/spacetime{suffix}", json={"after": after}, headers=csrf(client))


def test_retrospective_event_order_and_cuts_do_not_change_git_history(app):
    client = app.test_client()
    p = setup(client)
    early, late, unrelated = record("Early", "Event"), record("Late", "Event"), record("Unordered", "Event")
    first = create(client, p["id"], p["head"], late)
    subject = record("A described institution")
    state = record("Open", "State")
    state["modules"] = {"gsp.temporal_extent": extent(
        {"kind": "event", "event_id": early["id"]}, {"kind": "event", "event_id": late["id"]}, subject["id"])}
    head = create(client, p["id"], first, early, unrelated, subject, state, order(early["id"], late["id"]))
    store = app.extensions["git_store"]
    history = store.project_history(p["id"])
    result = cut(client, p["id"], [late["id"]], head)
    assert result.status_code == 200, result.json
    data = result.json
    assert data["projection"] == "gsp.spacetime/1" and data["head"] == head
    assert set(data["cut"]["included"]) == {early["id"], late["id"]}
    assert data["cut"]["derived"] == [early["id"]]
    assert data["cut"]["frontier"] == [late["id"]]
    ranks = {e["id"]: e["rank"] for e in data["events"]}
    assert ranks[early["id"]] < ranks[late["id"]]
    assert {x["record_id"]: x["presence"] for x in data["presence"]}[state["id"]] == "ended"
    during = cut(client, p["id"], [early["id"]], head).json
    assert [n["id"] for n in during["topology"]["nodes"]] == [state["id"]]
    assert during["trajectories"] == [{"subject_record_id": subject["id"], "record_ids": [state["id"]]}]
    before = cut(client, p["id"], [], head).json
    assert before["cut"]["included"] == [] and before["topology"]["nodes"] == []
    all_events = client.get(f"/api/projects/{p['id']}/spacetime").json
    assert all_events["cut"]["requested"] is None and len(all_events["cut"]["included"]) == 3
    old = client.get(f"/api/projects/{p['id']}/spacetime?revision={first}").json
    assert [e["id"] for e in old["events"]] == [late["id"]]
    assert old["orders"] == [] and old["current_head"] == head
    assert store.head(p["id"]) == head and store.project_history(p["id"]) == history


def test_conflicting_orders_are_retained_and_historical_projection_is_stable(app):
    client = app.test_client()
    p = setup(client)
    a, b = record("A", "Event"), record("B", "Event")
    head = create(client, p["id"], p["head"], a, b, order(a["id"], b["id"]))
    conflict = order(b["id"], a["id"])
    latest = create(client, p["id"], head, conflict)
    url = f"/api/projects/{p['id']}/spacetime"
    data = client.get(url).json
    assert data["consistent"] is False and data["cut"] is None and data["topology"] is None
    assert data["diagnostics"] and len(data["orders"]) == 2
    assert all(e["rank"] is None for e in data["events"])
    assert client.get(url + f"?revision={head}").json["consistent"] is True
    assert len(client.get(f"/api/projects/{p['id']}/graph").json["nodes"]) == 4
    response = post(client, p["id"], tx(latest, [{"op": "record.update", "record_id": conflict["id"], "changes": {"status": "withdrawn"}}]))
    assert response.status_code == 201, response.json
    resolved = client.get(url).json
    assert resolved["consistent"] is True and len(resolved["orders"]) == 2
    assert next(r for r in resolved["orders"] if r["id"] == conflict["id"])["active"] is False
    assert client.get(url + f"?revision={latest}").json["consistent"] is False


def test_unscoped_unknown_and_unbounded_are_distinct(app):
    client = app.test_client()
    p = setup(client)
    unknown, unbounded, unscoped = record("Unknown"), record("Within account scope"), record("Unscoped")
    unknown["modules"] = {"gsp.temporal_extent": extent({"kind": "unknown"}, {"kind": "unbounded"})}
    unbounded["modules"] = {"gsp.temporal_extent": extent({"kind": "unbounded"}, {"kind": "unbounded"})}
    head = create(client, p["id"], p["head"], unknown, unbounded, unscoped)
    data = cut(client, p["id"], [], head).json
    presence = {x["record_id"]: x["presence"] for x in data["presence"]}
    assert presence == {unknown["id"]: "indeterminate", unbounded["id"]: "active", unscoped["id"]: "unscoped"}
    assert [n["id"] for n in data["topology"]["nodes"]] == [unbounded["id"]]


def test_spacetime_authorization_csrf_and_revision_fences(app):
    client, other, anonymous = app.test_client(), app.test_client(), app.test_client()
    p = setup(client)
    register(other, "outsider@example.test")
    url = f"/api/projects/{p['id']}/spacetime"
    assert anonymous.get(url).status_code == 401
    assert other.get(url).status_code == 404
    assert cut(other, p["id"], []).status_code == 404
    assert client.post(url, json={"after": []}).status_code == 403
    for revision, status in [("main", 400), ("f" * 40, 404)]:
        assert client.get(url + "?revision=" + revision).status_code == status
        assert cut(client, p["id"], [], revision).status_code == status


def test_spacetime_query_rejects_ambiguous_or_excessive_input(app):
    client = app.test_client()
    p = setup(client)
    ordinary = record("Not an event")
    head = create(client, p["id"], p["head"], ordinary)
    url = f"/api/projects/{p['id']}/spacetime"
    headers = csrf(client)
    for raw in [b'{}', b'[]', b'{"after":[],"after":[]}', b'{"after":null}', b'{"after":[],"extra":1}',
                b'{"after":[NaN]}', b'{"after":["\\ud800"]}', b'{"after":[{}]}']:
        assert client.post(url, data=raw, content_type="application/json", headers=headers).status_code == 400
    for after in [[uid()], [ordinary["id"]], [uid()] * 1001]:
        assert cut(client, p["id"], after).status_code == 400
    assert client.post(url, data="after=[]", headers=headers).status_code == 415
    assert client.post(url, data=b" " * 65537, content_type="application/json", headers=headers).status_code == 413
    assert app.extensions["git_store"].head(p["id"]) == head


def test_legacy_projection_is_read_only_without_implicit_migration(app):
    client = app.test_client()
    user = register(client)["user"]
    actor = {"id": user["id"], "display_name": user["display_name"]}
    pid = uid()
    legacy = {"id": pid, "name": "Earlier workspace", "description": "", "created_at": utcnow(),
              "created_by": actor, "schema_version": "gsp-workspace/0.1", "visibility": "private"}
    with sqlite3.connect(app.config["DATA_DIR"] / "accounts.sqlite3") as conn:
        conn.execute("INSERT INTO projects VALUES(?,?,?)", (pid, actor["id"], legacy["created_at"]))
    store = app.extensions["git_store"]
    head = store.create_project(legacy, actor)
    response = cut(client, pid, [])
    assert response.status_code == 200 and response.json["legacy"] is True
    assert store.head(pid) == head
    assert store.snapshot(pid)["project"]["schema_version"] == "gsp-workspace/0.1"
