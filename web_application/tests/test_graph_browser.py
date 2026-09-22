"""Opt-in browser evidence for graph semantics, modules and snapshot integrity."""
import os
from pathlib import Path
import threading

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("GSP_BROWSER"), reason="Set GSP_BROWSER to run graph browser journeys.")


@pytest.fixture
def graph_page(tmp_path):
    from generative_app import create_app
    from playwright.sync_api import expect, sync_playwright
    from waitress import create_server

    server = create_server(create_app({"DATA_DIR": tmp_path / "graph-browser", "TESTING": True}), host="127.0.0.1", port=0, threads=4)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    errors = []
    try:
        with sync_playwright() as playwright:
            channel = os.environ["GSP_BROWSER"]
            browser = playwright.chromium.launch(headless=True, **({"channel": channel} if channel != "chromium" else {}))
            context = browser.new_context(viewport={"width": 1440, "height": 1050})
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" and "Content Security Policy" in message.text else None)
            page.goto(f"http://127.0.0.1:{server.effective_port}")
            page.locator("[name=display_name]").fill("Graph researcher")
            page.locator("[name=email]").fill("graph-browser@example.test")
            page.locator("[name=password]").fill("graph browser verification passphrase")
            page.locator("#auth-form button[type=submit]").click()
            page.locator("[data-action=new-project]").first.click()
            page.locator("#project-form [name=name]").fill("A shared garden inquiry")
            page.locator("#project-form [name=description]").fill("Exploring encounters, joint care, and the limits of a shared account.")
            page.locator("#project-form button[type=submit]").click()
            expect(page.locator("#graph-canvas")).to_be_visible()
            yield page
            assert not errors, errors
            context.close()
            browser.close()
    finally:
        server.close()
        server.task_dispatcher.shutdown()
        thread.join(timeout=5)


def project_id(page):
    return page.url.split("#/projects/")[1].split("/")[0].split("?")[0]


def snapshot(page):
    return page.evaluate("async id => (await fetch('/api/projects/' + id)).json()", project_id(page))


def create_record(page, title, role="Entity"):
    from playwright.sync_api import expect

    page.locator("[data-action=new-record]").first.click()
    page.locator("#record-form [name=title]").fill(title)
    page.locator("#record-form [name=content]").fill(f"An attributed account of {title.lower()}, open to later revision.")
    page.locator("#record-form [name=record_type]").select_option(role)
    page.locator("#record-form [name=epistemic_mode]").select_option("reported")
    page.locator("#record-form button[type=submit]").click()
    expect(page.locator(".inspector-header h2")).to_have_text(title)
    return next(record for record in snapshot(page)["records"] if record["title"] == title)


def select_record(page, record_id):
    from playwright.sync_api import expect

    if page.locator("[data-graph-action=deselect]").count():
        page.locator("[data-graph-action=deselect]").click()
    page.locator("#record-selector").select_option(record_id)
    expect(page.locator(".inspector-header")).to_be_visible()


def save_module(page, reason):
    from playwright.sync_api import expect

    page.locator("#module-form [name=reason]").fill(reason)
    page.locator("#module-form button[type=submit]").click()
    expect(page.locator("#editor-dialog")).not_to_be_visible()


def test_multi_participant_higher_order_graph_and_atomic_connected_creation(graph_page):
    from playwright.sync_api import expect

    page = graph_page
    collective = create_record(page, "Neighborhood collective")
    occasion = create_record(page, "Planting day", "Event")
    garden = create_record(page, "Shared garden")

    page.locator("[data-graph-action=connect]").click()
    # Select the remaining participants on the actual canvas; the current garden is already picked.
    for target in [collective, occasion]:
        position = page.locator("#graph-canvas").evaluate("(element, id) => element._cyreg.cy.getElementById(id).renderedPosition()", target["id"])
        page.locator("#graph-canvas").click(position=position)
    expect(page.locator("#connect-instructions")).to_contain_text("3 selected")
    page.locator("[data-graph-action=review-connection]").click()
    page.locator("#module-form [name=title]").fill("Participation in the garden")
    page.locator("#module-form [name=content]").fill("Three participants are named; other participants may still be absent from the account.")
    page.locator("#module-form [name=epistemic_mode]").select_option("reported")
    page.locator("#module-form [name=predicate]").fill("participation")
    while page.locator(".participant-editor").count() < 3:
        page.locator("#add-participant").click()
    for index, (record, role) in enumerate([(collective, "participant"), (occasion, "occasion"), (garden, "site")]):
        fieldset = page.locator(".participant-editor").nth(index)
        fieldset.locator("[name=participant_record]").select_option(record["id"])
        fieldset.locator("[name=participant_role]").fill(role)
    page.locator("[name=participants_complete]").select_option("incomplete")
    page.locator("[name=participant_limitations]").fill("Other contributors have not yet supplied their accounts.")
    save_module(page, "Distinguish participant roles without claiming the account is complete.")
    expect(page.locator(".inspector-header h2")).to_have_text("Participation in the garden")
    page.locator("[data-inspector-tab=relation]").click()
    expect(page.locator(".participant-card")).to_have_count(3)
    first_relation = next(record for record in snapshot(page)["records"] if record["title"] == "Participation in the garden")

    # A relation can participate in another relation, and that relation can reference itself.
    page.locator("[data-graph-action=relation-form]").click()
    page.locator("#module-form [name=title]").fill("Review of the participation account")
    page.locator("#module-form [name=content]").fill("This is an account-level review relation, including its own reflexive scope.")
    page.locator("#module-form [name=epistemic_mode]").select_option("interpreted")
    page.locator("#module-form [name=predicate]").fill("reviews")
    page.locator(".participant-editor").first.locator("[name=participant_role]").fill("account under review")
    page.locator(".participant-editor").first.locator("[name=participant_scope]").select_option("record")
    page.locator("#add-participant").click()
    second = page.locator(".participant-editor").nth(1)
    second.locator("[name=participant_record]").select_option(label="This relation (self-reference) · Relation")
    second.locator("[name=participant_role]").fill("reflexive review")
    second.locator("[name=participant_scope]").select_option("record")
    page.locator("[name=participants_complete]").select_option("complete")
    save_module(page, "Make the distinction between records and represented targets explicit.")
    expect(page.locator(".inspector-header h2")).to_have_text("Review of the participation account")
    higher = next(record for record in snapshot(page)["records"] if record["title"] == "Review of the participation account")
    assert [item["record_id"] for item in higher["modules"]["gsp.relation"]["data"]["participants"]] == [first_relation["id"], higher["id"]]

    # Creating an account and its relation is a single accepted project revision.
    select_record(page, collective["id"])
    before = snapshot(page)["head"]
    page.locator("[data-graph-action=create-connected]").click()
    page.locator("#record-form [name=title]").fill("A possible next season")
    page.locator("#record-form [name=content]").fill("An intended continuation, rather than a completed outcome.")
    page.locator("#record-form [name=record_type]").select_option("Process")
    page.locator("#record-form [name=record_roles][value=State]").check()
    page.locator("#record-form [name=epistemic_mode]").select_option("interpreted")
    page.locator("#record-form [name=modality]").select_option("possible")
    page.locator("[name=connection_predicate]").fill("could enable")
    page.locator("[name=connection_content]").fill("The collective may enable a continuation, subject to its participants' agreement.")
    page.locator("[name=connection_new_role]").fill("possible continuation")
    page.locator("[name=connection_existing_role]").fill("enabling condition")
    page.locator("[name=connection_completeness]").select_option("incomplete")
    page.locator("[name=connection_limitations]").fill("Other enabling conditions are not yet recorded.")
    page.locator("#record-form [name=change_category]").select_option("evidence_or_interpretation")
    page.locator("#record-form button[type=submit]").click()
    expect(page.locator(".inspector-header h2")).to_have_text("A possible next season")
    after = snapshot(page)
    assert len(after["records"]) == 7
    created = next(record for record in after["records"] if record["title"] == "A possible next season")
    assert set(created["record_roles"]) == {"Process", "State"}
    paired_relation = next(record for record in after["records"] if record["title"] == "A possible next season · could enable")
    assert not paired_relation["modules"]["gsp.relation"]["data"]["participants_complete"]
    history = page.evaluate("async id => (await fetch('/api/projects/' + id + '/history')).json()", project_id(page))["history"]
    assert history[1]["commit"] == before

    # Local display changes cannot write project history. Keyboard selection is equivalent to canvas selection.
    page.locator("[data-graph-action=arrange]").click()
    page.locator("#record-filter").select_option("Relation")
    expect(page.locator("#graph-filter-summary")).to_contain_text("4 records")
    assert snapshot(page)["head"] == after["head"]
    page.locator("#record-filter").select_option("")
    select_record(page, first_relation["id"])
    page.locator("[data-inspector-tab=relation]").click()
    expect(page.locator(".participant-card")).to_have_count(3)
    # Opening a node draft directly on the canvas does not create an ontological record.
    page.locator("#graph-canvas").dblclick(position={"x": 20, "y": 20})
    expect(page.locator("#record-form")).to_be_visible()
    page.locator("#record-form [name=title]").fill("An uncommitted canvas draft")
    page.once("dialog", lambda prompt: prompt.accept())
    page.locator("#record-form [data-action=close-dialog]").click()
    expect(page.locator("#editor-dialog")).not_to_be_visible()
    assert snapshot(page)["head"] == after["head"]
    artifacts = Path(__file__).resolve().parents[4] / "build/webapp-review"
    artifacts.mkdir(parents=True, exist_ok=True)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(artifacts / "graph-multi-participant.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator("[data-graph-action=fit]").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(artifacts / "graph-mobile.png"), full_page=True)


def test_file_replacement_history_and_lost_response_retry(graph_page, tmp_path):
    from playwright.sync_api import expect

    page = graph_page
    record = create_record(page, "Field account", "Event")
    page.locator("[data-graph-action=enable-files]").click()
    save_module(page, "Retain supplied source material beside the account.")
    page.locator("[data-inspector-tab=files]").click()
    page.locator("[data-graph-action=attach-file]").click()
    page.locator("#retained-upload").set_input_files({"name": "field-notes.txt", "mimeType": "text/plain", "buffer": b"Initial field notes."})
    save_module(page, "Retain the original material without independent verification.")
    expect(page.locator(".file-download")).to_contain_text("field-notes.txt")
    attachment_head = snapshot(page)["head"]
    page.locator("[data-graph-action=replace-file]").click()
    page.locator("#retained-upload").set_input_files({"name": "revised-notes.txt", "mimeType": "text/plain", "buffer": b"Revised field notes."})
    save_module(page, "A revised supplied file replaces the current reference.")
    expect(page.locator(".file-download")).to_contain_text("revised-notes.txt")
    current_head = snapshot(page)["head"]

    page.locator("#project-revision").select_option(attachment_head)
    expect(page.locator(".old-revision")).to_be_visible()
    expect(page.locator(".file-download")).to_contain_text("field-notes.txt")
    expect(page.locator("[data-graph-action=attach-file]")).to_have_count(0)
    expect(page.locator("[data-action=new-record]").first).to_be_disabled()
    with page.expect_download() as old_download:
        page.locator(".file-download").click()
    old_path = tmp_path / "old-notes.txt"
    old_download.value.save_as(old_path)
    assert old_path.read_bytes() == b"Initial field notes."
    page.locator("[data-inspector-tab=history]").click()
    expect(page.locator("[data-project-revision]").first).to_have_attribute("data-project-revision", attachment_head)
    page.locator("[data-graph-action=current]").click()
    expect(page.locator(".old-revision")).to_have_count(0)
    expect(page.locator("#graph-head")).to_have_text(current_head[:10])
    page.locator("[data-inspector-tab=overview]").click()
    page.locator("[data-graph-action=enable-notes]").click()

    # The server commits the transaction, then its response is deliberately lost.
    # Retrying the unchanged form must send the same ID and recover the receipt.
    sent = []
    def lose_response(route):
        sent.append(route.request.post_data_json)
        route.fetch()
        route.abort("failed")

    page.route("**/transactions", lose_response, times=1)
    page.locator("#module-form [name=reason]").fill("Enable retained notes with a recoverable transaction.")
    page.locator("#module-form button[type=submit]").click()
    expect(page.locator("#module-form .form-error")).to_contain_text("Retry without changing")
    committed_head = snapshot(page)["head"]
    # A different accepted edit advances the project before this client retries.
    later = page.evaluate("""async ({pid, rid, head}) => {
        const session = await (await fetch('/api/session')).json();
        const response = await fetch('/api/projects/' + pid + '/transactions', {
            method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token},
            body: JSON.stringify({protocol_version: 'gsp-record-protocol/0.2', transaction_id: crypto.randomUUID(),
                expected_head: head, reason: 'An independent client supplies a later description.',
                change_categories: ['description'], operations: [{op: 'record.update', record_id: rid,
                changes: {title: 'A later field account'}}]})});
        return {status: response.status, data: await response.json()};
    }""", {"pid": project_id(page), "rid": record["id"], "head": committed_head})
    assert later["status"] == 201, later
    later_head = later["data"]["head"]
    retries = []
    def observe_retry(route):
        retries.append(route.request.post_data_json)
        route.continue_()

    page.route("**/transactions", observe_retry, times=1)
    page.locator("#module-form button[type=submit]").click()
    expect(page.locator("#editor-dialog")).not_to_be_visible()
    expect(page.locator("[data-inspector-tab=notes]")).to_be_visible()
    assert sent[0]["transaction_id"] == retries[0]["transaction_id"]
    assert snapshot(page)["head"] == later_head
    expect(page.locator(".old-revision")).to_be_visible()
    expect(page.locator("#graph-head")).to_have_text(committed_head[:10])
    expect(page.locator("[data-action=new-record]").first).to_be_disabled()
    expect(page.locator("[data-graph-action=edit-notes]")).to_have_count(0)
    page.locator("[data-graph-action=current]").click()
    expect(page.locator(".inspector-header h2")).to_have_text("A later field account")
    expect(page.locator(".old-revision")).to_have_count(0)
    assert any(item["id"] == record["id"] for item in snapshot(page)["records"])
