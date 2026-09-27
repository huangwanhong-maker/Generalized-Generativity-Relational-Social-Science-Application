"""Browser evidence for occurrence order, cuts, topology and retained conflicts."""
import os
from pathlib import Path

import pytest

from test_graph_browser import create_record, graph_page, project_id, save_module, select_record, snapshot

pytestmark = pytest.mark.skipif(not os.environ.get("GSP_BROWSER"), reason="Set GSP_BROWSER for temporal browser journeys.")


def show_spacetime(page):
    from playwright.sync_api import expect

    page.locator('[data-graph-view="spacetime"]').click()
    expect(page.locator("#spacetime-cut-status")).to_be_visible()


def create_order(page, before, after, title):
    from playwright.sync_api import expect

    show_spacetime(page)
    page.locator('#spacetime-panel [data-graph-action="temporal-order"]').click()
    page.locator('#module-form [name="before"]').select_option(before["id"])
    page.locator('#module-form [name="after"]').select_option(after["id"])
    page.locator('#module-form [name="order_title"]').fill(title)
    page.locator('#module-form [name="order_content"]').fill("A participant retrospectively describes the first event as earlier, subject to review.")
    page.locator('#module-form [name="order_epistemic_mode"]').select_option("reported")
    page.locator('#module-form [name="order_modality"]').select_option("realized")
    save_module(page, "Preserve this attributed precedence claim independently of recording order.")
    expect(page.locator(".inspector-header h2")).to_have_text(title)
    expect(page.locator("#spacetime-cut-status")).to_be_visible()
    return next(record for record in snapshot(page)["records"] if record["title"] == title)


def temporal_extent(page, record, start, end, subject=None):
    from playwright.sync_api import expect

    select_record(page, record["id"])
    page.locator('[data-inspector-tab="temporal"]').click()
    page.locator('[data-graph-action="edit-temporal"]').click()
    for name, bound in [("start", start), ("end", end)]:
        page.locator(f'#module-form [name="{name}_kind"]').select_option("event" if isinstance(bound, dict) else bound)
        if isinstance(bound, dict):
            page.locator(f'#module-form [name="{name}_event"]').select_option(bound["id"])
    if subject:
        page.locator('#module-form [name="subject_record_id"]').select_option(subject["id"])
    page.locator('#module-form [name="temporal_basis"]').fill("The community account locates this description between the named events; the grouping remains attributed.")
    save_module(page, "Record event boundaries and their explicit scope.")
    expect(page.locator("#spacetime-cut-status")).to_be_visible()


def assert_topology_nodes_separate(page, identifiers):
    boxes = page.locator("#spacetime-topology-canvas").evaluate("""(element, ids) =>
        ids.map(id => element._cyreg.cy.getElementById(id).renderedBoundingBox())
    """, identifiers)
    assert all(box["w"] > 0 and box["h"] > 0 for box in boxes)
    for index, left in enumerate(boxes):
        for right in boxes[index + 1:]:
            assert (left["x2"] <= right["x1"] or right["x2"] <= left["x1"]
                    or left["y2"] <= right["y1"] or right["y2"] <= left["y1"]), boxes


def test_spacetime_mixed_components_keep_nodes_separate():
    """Connected and isolated wide nodes stay readable in the real renderer."""
    from playwright.sync_api import expect, sync_playwright

    static = Path(__file__).resolve().parents[1] / "generative_app/static"
    with sync_playwright() as playwright:
        channel = os.environ["GSP_BROWSER"]
        browser = playwright.chromium.launch(headless=True, **({"channel": channel} if channel != "chromium" else {}))
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.set_content('<div id="spacetime-panel" style="width:350px"></div>')
        for name in ["style.css", "spacetime.css"]:
            page.add_style_tag(path=str(static / name))
        for name in ["vendor/cytoscape.min.js", "spacetime.js"]:
            page.add_script_tag(path=str(static / name))
        page.evaluate("""() => {
            const records = ['Linked account', 'Related account', 'Separate account'].map((title, i) => ({id: String(i), title}));
            const head = 'a'.repeat(40);
            const data = {head, consistent: true, events: [], orders: [], extents: [], trajectories: [],
                cut: {included: [], frontier: []}, diagnostics: [], limitations: [],
                presence: records.map(record => ({record_id: record.id, presence: 'active'})),
                topology: {nodes: records.map(record => ({id: record.id, label: record.title, record_roles: ['Entity']})),
                    edges: [{id: 'reference:0:1', source: '0', target: '1', kind: 'reference', orientation: 'undirected'}]}};
            const view = GSPSpaceTime.mount(document.querySelector('#spacetime-panel'), {
                api: async () => data, base: '', esc: value => String(value), icon: () => '',
                errorText: error => error.message, selectRecord: () => {}, isReadOnly: () => true});
            view.setSnapshot(head, records); view.show(true);
        }""")
        expect(page.locator("#spacetime-topology-summary")).to_contain_text("3 records")
        assert_topology_nodes_separate(page, ["0", "1", "2"])
        assert page.locator("#spacetime-topology-canvas").evaluate("element => element._cyreg.cy.edges().length") == 1
        page.set_viewport_size({"width": 1440, "height": 1050})
        assert_topology_nodes_separate(page, ["0", "1", "2"])
        browser.close()


def test_reverse_recording_order_consistent_cuts_and_historical_topology(graph_page):
    from playwright.sync_api import expect

    expect.set_options(timeout=20000)
    page = graph_page
    later = create_record(page, "Garden closes", "Event")
    earlier = create_record(page, "Garden opens", "Event")
    incomparable = create_record(page, "A separately reported meeting", "Event")
    before_order = snapshot(page)["head"]
    order = create_order(page, earlier, later, "Opening precedes closure")
    subject = create_record(page, "Community garden", "Entity")
    state = create_record(page, "Garden available for shared work", "State")
    temporal_extent(page, subject, "unbounded", "unbounded")
    temporal_extent(page, state, earlier, later, subject)
    saved = snapshot(page)

    # Neither the commit order nor UUID ordering controls the temporal rank.
    positions = page.locator("#spacetime-event-canvas").evaluate("(element, ids) => ids.map(id => element._cyreg.cy.getElementById(id).position().x)", [earlier["id"], later["id"]])
    assert positions[0] < positions[1]
    expect(page.locator("#spacetime-panel")).to_contain_text("incomparable events are not necessarily simultaneous")
    expect(page.locator(f'[data-st-presence="{state["id"]}"]')).to_contain_text("ended")
    expect(page.locator(f'[data-st-presence="{incomparable["id"]}"]')).to_contain_text("unscoped")

    page.locator('[data-st-action="before-all"]').click()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("0 of 3")
    expect(page.locator(f'[data-st-presence="{state["id"]}"]')).to_contain_text("not started")
    # A failed query retry retains the requested cut instead of jumping to all events.
    page.route("**/spacetime?revision=*", lambda route: route.fulfill(status=503, content_type="application/json", body='{"error":{"message":"Temporarily unavailable for this test."}}'), times=1)
    page.locator(f'[data-st-cut="{later["id"]}"]').check()
    expect(page.locator("#spacetime-panel .error-box")).to_contain_text("Temporarily unavailable")
    page.locator('[data-st-action="retry"]').click()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("2 of 3")
    expect(page.locator(f'[data-st-cut="{incomparable["id"]}"]')).not_to_be_checked()
    page.locator('[data-st-action="before-all"]').click()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("0 of 3")
    page.locator(f'[data-st-cut="{earlier["id"]}"]').check()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("1 of 3")
    expect(page.locator(f'[data-st-presence="{state["id"]}"]')).to_contain_text("active")
    assert page.locator("#spacetime-topology-canvas").evaluate("(element, id) => element._cyreg.cy.getElementById(id).length", state["id"]) == 1
    assert_topology_nodes_separate(page, [subject["id"], state["id"]])
    expect(page.locator(".spacetime-trajectories")).to_contain_text(subject["title"])

    # Passing the later event includes its earlier event; clearing the earlier
    # event clears the dependent successor and preserves an unrelated event.
    page.locator(f'[data-st-cut="{incomparable["id"]}"]').check()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("2 of 3")
    page.locator(f'[data-st-cut="{later["id"]}"]').check()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("3 of 3")
    page.locator(f'[data-st-cut="{earlier["id"]}"]').uncheck()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("1 of 3")
    expect(page.locator(f'[data-st-cut="{later["id"]}"]')).not_to_be_checked()
    expect(page.locator(f'[data-st-cut="{incomparable["id"]}"]')).to_be_checked()
    page.locator('[data-st-action="before-all"]').click()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("0 of 3")
    page.locator(f'[data-st-cut="{later["id"]}"]').check()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("2 of 3")
    expect(page.locator(f'[data-st-cut="{earlier["id"]}"]')).to_be_checked()
    assert snapshot(page)["head"] == saved["head"]

    # A historical revision never borrows the later ordering accounts or extents.
    page.locator("#project-revision").select_option(before_order)
    expect(page.locator(".old-revision")).to_be_visible()
    expect(page.locator(".spacetime-orders summary")).to_contain_text("0 recorded ordering")
    expect(page.locator('#spacetime-panel [data-graph-action="temporal-order"]')).to_be_disabled()
    assert page.locator(f'[data-st-presence="{state["id"]}"]').count() == 0
    select_record(page, earlier["id"])
    page.locator('[data-inspector-tab="temporal"]').click()
    assert page.locator('[data-graph-action="edit-temporal"]').count() == 0
    page.locator('[data-graph-action="current"]').click()
    expect(page.locator(".spacetime-orders summary")).to_contain_text("1 recorded ordering")
    page.locator('[data-st-action="before-all"]').click()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("0 of 3")
    page.locator(f'[data-st-cut="{earlier["id"]}"]').check()
    expect(page.locator(f'[data-st-presence="{state["id"]}"]')).to_contain_text("active")
    artifacts = Path(__file__).resolve().parents[4] / "build/webapp-review"
    artifacts.mkdir(parents=True, exist_ok=True)
    page.locator("#main").focus()
    page.evaluate("window.scrollTo(0, 0)")
    page.locator("#spacetime-panel").evaluate("element => element.scrollTop = 0")
    page.screenshot(path=str(artifacts / "spacetime-desktop.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert_topology_nodes_separate(page, [subject["id"], state["id"]])
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(artifacts / "spacetime-mobile.png"), full_page=True)
    assert snapshot(page)["head"] == saved["head"]
    assert order["modules"]["gsp.event_order"]["required"] is True


def test_conflicting_orders_are_preserved_and_repaired_by_withdrawal(graph_page):
    from playwright.sync_api import expect

    expect.set_options(timeout=20000)
    page = graph_page
    first = create_record(page, "Reported first encounter", "Event")
    second = create_record(page, "Reported second encounter", "Event")
    original_order = create_order(page, first, second, "Account A: first before second")
    # A conflict review rebases hidden relation qualifications as well as the
    # project head, while keeping the user's visible form edits.
    page.locator('[data-inspector-tab="temporal"]').click()
    page.locator('[data-graph-action="edit-order"]').click()
    page.locator('#module-form [name="order_content"]').fill("A revised attributed account, preserving the newly supplied qualifications.")
    changed = page.evaluate("""async ({pid, record}) => {
        const session = await (await fetch('/api/session')).json();
        const snapshot = await (await fetch('/api/projects/' + pid)).json();
        const module = record.modules['gsp.relation'];
        module.data.context = 'Concurrent context supplied by another reviewer.';
        module.data.participants_complete = false;
        module.data.participant_limitations = 'The named pair does not exhaust the wider event context.';
        const response = await fetch('/api/projects/' + pid + '/transactions', {
            method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token},
            body: JSON.stringify({protocol_version: 'gsp-record-protocol/0.2', transaction_id: crypto.randomUUID(),
                expected_head: snapshot.head, reason: 'Add qualified context from a separate review.',
                change_categories: ['evidence_or_interpretation'], operations: [{op: 'module.set',
                record_id: record.id, module_id: 'gsp.relation', module}]})});
        return {status: response.status, data: await response.json()};
    }""", {"pid": project_id(page), "record": original_order})
    assert changed["status"] == 201, changed
    page.locator('#module-form [name="reason"]').fill("Revise the account while preserving the reviewed qualifications.")
    page.locator('#module-form button[type="submit"]').click()
    expect(page.locator(".transaction-conflict")).to_contain_text("The project changed")
    page.locator("#module-review-latest").click()
    page.locator("#module-use-latest").click()
    page.locator('#module-form button[type="submit"]').click()
    expect(page.locator("#editor-dialog")).not_to_be_visible()
    revised_order = next(item for item in snapshot(page)["records"] if item["id"] == original_order["id"])
    assert revised_order["modules"]["gsp.relation"]["data"]["context"] == "Concurrent context supplied by another reviewer."
    assert revised_order["modules"]["gsp.relation"]["data"]["participants_complete"] is False
    assert revised_order["modules"]["gsp.relation"]["data"]["participant_limitations"] == "The named pair does not exhaust the wider event context."
    assert revised_order["content"].startswith("A revised attributed account")
    conflicting = create_order(page, second, first, "Account B: second before first")
    conflict_head = snapshot(page)["head"]
    expect(page.locator("#spacetime-diagnostics")).to_contain_text("cannot define a consistent cut")
    expect(page.locator("#spacetime-cut-status")).to_contain_text("Cut unavailable")
    expect(page.locator('[data-st-action="before-all"]')).to_be_disabled()
    assert any(record["id"] == conflicting["id"] for record in snapshot(page)["records"])
    page.locator('[data-inspector-tab="overview"]').click()
    page.locator('[data-graph-action="edit-selected"]').click()
    page.locator('#record-form [name="status"]').select_option("withdrawn")
    page.locator('#record-form [name="revision_reason"]').fill("The source corrects the second ordering claim; retain its earlier form.")
    page.locator('#record-form button[type="submit"]').click()
    expect(page.locator("#editor-dialog")).not_to_be_visible()
    expect(page.locator("#spacetime-cut-status")).to_contain_text("2 of 2")
    expect(page.locator("#spacetime-diagnostics")).not_to_contain_text("cannot define a consistent cut")
    page.locator("#project-revision").select_option(conflict_head)
    expect(page.locator("#spacetime-diagnostics")).to_contain_text("cannot define a consistent cut")
    expect(page.locator(".old-revision")).to_be_visible()


def test_selected_empty_file_is_an_unsaved_draft(graph_page):
    from playwright.sync_api import expect

    expect.set_options(timeout=20000)
    page = graph_page
    create_record(page, "An account with retained materials")
    page.locator('[data-graph-action="enable-files"]').click()
    save_module(page, "Enable material retention beside the account.")
    page.locator('[data-inspector-tab="files"]').click()
    saved_head = snapshot(page)["head"]

    # Empty native file inputs must not look dirty merely because FormData
    # constructs a fresh empty File with a new timestamp each time.
    page.locator('[data-graph-action="attach-file"]').click()
    page.locator('#module-form [data-action="close-dialog"]').click()
    expect(page.locator("#editor-dialog")).not_to_be_visible()

    # A selected zero-byte file is still a draft and can be kept after Cancel.
    page.locator('[data-graph-action="attach-file"]').click()
    page.locator("#retained-upload").set_input_files({"name": "empty-notes.txt", "mimeType": "text/plain", "buffer": b""})
    prompts = []
    def keep_file(prompt):
        prompts.append(prompt.message)
        prompt.dismiss()
    page.once("dialog", keep_file)
    page.locator('#module-form [data-action="close-dialog"]').click()
    expect(page.locator("#editor-dialog")).to_be_visible()
    assert len(prompts) == 1 and "unsaved" in prompts[0]
    assert page.locator("#retained-upload").evaluate("input => input.files[0].name") == "empty-notes.txt"
    page.once("dialog", lambda prompt: prompt.accept())
    page.locator('#module-form [data-action="close-dialog"]').click()
    expect(page.locator("#editor-dialog")).not_to_be_visible()
    assert snapshot(page)["head"] == saved_head
