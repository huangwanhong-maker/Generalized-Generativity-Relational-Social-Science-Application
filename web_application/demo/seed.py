"""Create or resume the synthetic River Commons demo through the ordinary HTTP API.

Passwords and accepted project heads stay in the ignored infrastructure runtime.
No existing user project is selected or rewritten by this script.
"""
from __future__ import annotations

import argparse
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path
import secrets
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor, ProxyHandler
from uuid import uuid4

from scenario import build_scenario

INFRA = Path(__file__).resolve().parents[3]
STATE_FILE = INFRA / ".runtime/demo/river-commons.json"
SCENARIO = "river-commons/1"


class APIError(RuntimeError):
    def __init__(self, status, message):
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


class Client:
    def __init__(self, base_url):
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("Use a local HTTP application origin for this synthetic demo.")
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
        self.csrf = None

    def request(self, method, path, payload=None, *, files=None, binary=False):
        headers, body = {}, None
        if method != "GET":
            if not self.csrf:
                self.request("GET", "/api/session")
            headers["X-CSRF-Token"] = self.csrf
        if files:
            boundary = "gsp-demo-" + uuid4().hex
            parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"transaction\"\r\nContent-Type: application/json\r\n\r\n".encode(), json.dumps(payload).encode(), b"\r\n"]
            for name, material_path in files.items():
                parts += [f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"material.bin\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode(), Path(material_path).read_bytes(), b"\r\n"]
            parts += [f"--{boundary}--\r\n".encode()]
            body = b"".join(parts)
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        elif payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            with self.opener.open(Request(self.base_url + path, data=body, headers=headers, method=method), timeout=90) as response:
                if binary:
                    return response.read()
                result = json.load(response)
        except HTTPError as error:
            detail = json.loads(error.read()).get("error", {})
            raise APIError(error.code, detail.get('message', 'Request failed')) from None
        if "csrf_token" in result:
            self.csrf = result["csrf_token"]
        return result


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".pending.json")
    temporary.write_bytes((json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    temporary.replace(STATE_FILE)


def transact(client, state, stage, files=None):
    if stage["key"] in state["revisions"]:
        return
    pending = state.get("pending")
    if pending and pending["key"] != stage["key"]:
        raise RuntimeError("Resume the pending demo stage before another stage.")
    if not pending:
        latest = client.request("GET", f"/api/projects/{state['project_id']}")
        if latest["head"] != state["head"]:
            raise RuntimeError("The demo was edited outside this script. Preserve those edits; use a separate demo runtime to recreate it.")
        pending = {"key": stage["key"], "transaction": {
            "protocol_version": "gsp-record-protocol/0.2", "transaction_id": str(uuid4()),
            "expected_head": state["head"], "reason": stage["reason"],
            "change_categories": stage.get("change_categories", ["description"]),
            "operations": stage["operations"],
        }}
        state["pending"] = pending
        save_state(state)
    result = client.request("POST", f"/api/projects/{state['project_id']}/transactions", pending["transaction"], files=files)
    state["head"] = result["head"]
    state["revisions"][stage["key"]] = result["head"]
    state.pop("pending", None)
    save_state(state)
    print("Preserved demo stage:", stage["key"], result["head"][:10])


def verify(client, state, scenario):
    base = f"/api/projects/{state['project_id']}"
    snapshot = client.request("GET", base + "?revision=" + state["head"])
    roles = {role for record in snapshot["records"] for role in record["record_roles"]}
    if roles != {"Entity", "State", "Event", "Process", "Relation", "Property"}:
        raise RuntimeError("The demonstration must cover all six operational roles.")
    current = client.request("GET", base + "/spacetime?revision=" + state["head"])
    earlier = client.request("GET", base + "?revision=" + state["revisions"]["late_review"])
    ids = {record["id"] for record in earlier["records"]}
    if scenario["view"]["review_event"] not in ids or scenario["view"]["early_event"] in ids:
        raise RuntimeError("The initial revision must preserve a later event before earlier events are recorded.")
    conflict = client.request("GET", base + "/spacetime?revision=" + state["revisions"]["conflicting_order"])
    if not current["consistent"] or conflict["consistent"]:
        raise RuntimeError("Expected a consistent current account and an inspectable historical cycle.")
    before = client.request("POST", base + "/spacetime?revision=" + state["head"], {"after": [scenario["view"]["agreement_event"]]})
    later = client.request("POST", base + "/spacetime?revision=" + state["head"], {"after": [scenario["view"]["review_event"]]})
    if before["cut"]["included"] == later["cut"]["included"] or before["topology"]["nodes"] == later["topology"]["nodes"] or client.request("GET", base)["head"] != state["head"]:
        raise RuntimeError("Cut selection must change the view while preserving the accepted project head.")
    if len(snapshot["records"]) != len(scenario["records"]):
        raise RuntimeError("The retained demo inventory differs from its authored scenario.")
    file_count = sum(len(record.get("modules", {}).get("gsp.files", {}).get("data", {}).get("items", [])) for record in snapshot["records"])
    if file_count != len(scenario["attachments"]):
        raise RuntimeError("The demonstration's retained materials are incomplete.")
    for attachment in scenario["attachments"]:
        download = client.request("GET", base + f"/records/{attachment['record_id']}/files/{attachment['file_id']}?revision=" + state["head"], binary=True)
        if download != Path(attachment["path"]).read_bytes():
            raise RuntimeError("A downloaded demo material differs from its authored source.")
    state["verification"] = {"record_count": len(snapshot["records"]), "roles": sorted(roles),
        "event_count": len(current["events"]), "order_count": len(current["orders"]), "file_count": file_count,
        "revision_count": len(state["revisions"]), "downloaded_materials_match": True,
        "earlier_topology_count": len(before["topology"]["nodes"]), "later_topology_count": len(later["topology"]["nodes"]),
        "historical_cycle_preserved": True, "retrospective_insertion_verified": True,
        "cut_reads_preserve_head": True}
    save_state(state)
    return state["verification"]


def seed(base_url):
    scenario = build_scenario()
    client = Client(base_url)
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if state.get("scenario") != SCENARIO or state.get("base_url") != client.base_url:
            raise RuntimeError("The private demo manifest belongs to another scenario or server.")
        try:
            client.request("POST", "/api/auth/login", {"email": state["email"], "password": state["password"]})
        except APIError as error:
            if error.status != 401 or state.get("account_created") or state.get("project_id"):
                raise
            # The first request may have failed before registration reached the
            # server. Reuse the saved identity; a lost successful response would
            # instead have been recovered by the login above.
            client.request("POST", "/api/auth/register", {key: state[key] for key in ("email", "password", "display_name")})
    else:
        state = {"scenario": SCENARIO, "base_url": client.base_url, "email": f"river-commons-{secrets.token_hex(4)}@example.test",
                 "password": secrets.token_urlsafe(27), "display_name": "Demo curator", "revisions": {},
                 "ids": scenario["ids"], "view": scenario["view"]}
        # Save the account recovery information before making an HTTP mutation.
        save_state(state)
        client.request("POST", "/api/auth/register", {key: state[key] for key in ("email", "password", "display_name")})
    state["account_created"] = True
    save_state(state)
    if "project_id" not in state:
        project = client.request("POST", "/api/projects", scenario["project"])["project"]
        state.update(project_id=project["id"], head=project["head"], project_name=project["name"])
        state["revisions"]["project_created"] = project["head"]
        save_state(state)
    for stage in scenario["stages"]:
        transact(client, state, stage)
    operations, files = [], {}
    for index, attachment in enumerate(scenario["attachments"]):
        path = Path(attachment["path"])
        value = path.read_bytes()
        part = f"material{index}"
        operations.append({"op": "file.attach", "record_id": attachment["record_id"], "file_id": attachment["file_id"],
                           "part": part, "filename": attachment["filename"], "media_type": attachment["media_type"],
                           "byte_length": len(value), "sha256": hashlib.sha256(value).hexdigest()})
        files[part] = path
    transact(client, state, {"key": "retained_material", "reason": "DEMO: retain the fictional source materials alongside their attributed accounts.",
                            "change_categories": ["evidence_or_interpretation"], "operations": operations}, files)
    report = verify(client, state, scenario)
    print(json.dumps(report, indent=2))
    print("Demo project:", client.base_url + "/#/projects/" + state["project_id"])
    print("Private local sign-in details:", STATE_FILE)
    return state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    arguments = parser.parse_args()
    seed(arguments.base_url)
