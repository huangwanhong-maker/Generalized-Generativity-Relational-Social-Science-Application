"""Capture the real synthetic demo UI and synchronize README preview images.

Requires the dev Playwright dependency and an installed browser. This uses normal
controls, scrolling and display layout; it does not alter record content or styles.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from playwright.sync_api import expect, sync_playwright

from scenario import build_scenario
from seed import Client, INFRA, STATE_FILE

APPLICATION = Path(__file__).resolve().parents[2]
GALLERY = APPLICATION / "docs/gallery"


def capture(channel="msedge"):
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    client = Client(state["base_url"])
    client.request("POST", "/api/auth/login", {"email": state["email"], "password": state["password"]})
    base = f"/api/projects/{state['project_id']}"
    before = client.request("GET", base)
    if before["head"] != state["head"]:
        raise RuntimeError("The demo has changed since seeding. Preserve those edits before regenerating its gallery.")
    scenario = build_scenario()
    view = scenario["view"]
    GALLERY.mkdir(parents=True, exist_ok=True)
    images, errors = [], []
    expect.set_options(timeout=30000)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, **({"channel": channel} if channel != "chromium" else {}))
        context = browser.new_context(viewport={"width": 1680, "height": 1120}, device_scale_factor=1, reduced_motion="reduce")
        session = context.request.get(state["base_url"] + "/api/session").json()
        login = context.request.post(state["base_url"] + "/api/auth/login", data={"email": state["email"], "password": state["password"]}, headers={"X-CSRF-Token": session["csrf_token"]})
        if not login.ok:
            raise RuntimeError("The browser could not sign in to the synthetic demo account.")
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" and "Content Security Policy" in message.text else None)

        def ready():
            page.evaluate("() => document.fonts.ready")
            page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")

        def shot(filename, caption, locator=None):
            ready()
            path = GALLERY / filename
            (locator or page).screenshot(path=str(path), animations="disabled")
            images.append({"file": filename, "caption": caption, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
            print("Captured:", filename)

        def open_project():
            page.goto(state["base_url"] + "/#/projects/" + state["project_id"])
            expect(page.locator("#snapshot-label")).to_contain_text("current snapshot")
            expect(page.locator("#graph-canvas")).to_be_visible()
            page.wait_for_function("count => document.querySelector('#graph-canvas')?._cyreg?.cy?.nodes().length === count", arg=state["verification"]["record_count"])

        def select_record(identifier, tab=None):
            close = page.locator('[data-graph-action="deselect"]')
            if close.count():
                close.click()
            page.locator("#record-selector").select_option(identifier)
            expect(page.locator(".inspector-header")).to_be_visible()
            if tab:
                page.locator(f'[data-inspector-tab="{tab}"]').click()

        def scroll_temporal(selector):
            # Scroll the actual panel, leaving the project identity and selected
            # revision in the browser frame; no CSS is injected for captures.
            page.locator("#spacetime-panel").evaluate("(panel, selector) => {const target=panel.querySelector(selector); panel.scrollTop += target.getBoundingClientRect().top-panel.getBoundingClientRect().top-18;}", selector)
            page.evaluate("window.scrollTo(0, 270)")
            ready()

        def choose_cut(event_id):
            page.locator('[data-st-action="before-all"]').click()
            expect(page.locator("#spacetime-cut-status")).to_contain_text("0 of")
            page.locator(f'[data-st-cut="{event_id}"]').check()
            expect(page.locator(f'[data-st-cut="{event_id}"]')).to_be_enabled()
            expect(page.locator("#spacetime-cut-status")).not_to_contain_text("0 of")

        open_project()
        select_record(view["focus_relation"], "relation")
        query = view.get("graph_query", "")
        if query:
            page.locator("#record-search").fill(query)
        # Use ordinary canvas positions, like manually dragging the visible
        # nodes. A deterministic grid keeps disconnected accounts readable;
        # it changes only this browser's display layout, never record data.
        page.locator("#graph-canvas").evaluate("""canvas => {
            const cy = canvas._cyreg.cy;
            cy.nodes(':visible').layout({name: 'grid', cols: 4,
                avoidOverlap: true, spacingFactor: 1.25,
                animate: false, fit: true, padding: 45}).run();
            cy.nodes(':visible').first().emit('dragfree');
        }""")
        page.locator('[data-graph-action="fit"]').click()
        page.evaluate("window.scrollTo(0, 90)")
        shot("01-record-graph.png", "The retained record graph and a first-class Relation with named participants; any active search filter is shown in the interface.")

        page.locator('[data-graph-view="spacetime"]').click()
        expect(page.locator("#spacetime-cut-status")).to_be_visible()
        select_record(view["early_event"], "temporal")
        choose_cut(view["agreement_event"])
        page.locator("#spacetime-panel").evaluate("panel => panel.scrollTop=0")
        page.evaluate("window.scrollTo(0, 220)")
        shot("02-event-order.png", "Explicit event precedence contains a branch and an unordered observation. An earlier occurrence was recorded after the review event.")

        select_record(view["focus_state"], "temporal")
        coverage = page.locator(".spacetime-coverage")
        if coverage.get_attribute("open") is not None:
            coverage.locator("summary").click()
        scroll_temporal(".spacetime-frontier")
        expect(page.locator("#spacetime-topology-summary")).to_contain_text("10 records")
        shot("03-earlier-topology.png", "Ontology topology after the access-agreement event, under the current retained account. Coverage remains inspectable.")

        choose_cut(view["review_event"])
        select_record(scenario["ids"]["state_access_revised"], "temporal")
        coverage = page.locator(".spacetime-coverage")
        if coverage.get_attribute("open") is not None:
            coverage.locator("summary").click()
        scroll_temporal(".spacetime-frontier")
        expect(page.locator("#spacetime-topology-summary")).to_contain_text("13 records")
        shot("04-later-topology.png", "A later event cut at the same Git revision changes scoped topology and State applicability; choosing a cut creates no revision.")

        select_record(view["focus_state"], "temporal")
        scroll_temporal(".spacetime-trajectories")
        shot("05-subject-trajectories.png", "Successive and competing descriptions are grouped by their explicitly recorded subject, with their event bounds and presence classifications.")

        page.locator('[data-graph-action="edit-temporal"]').click()
        expect(page.locator("#module-form")).to_be_visible()
        shot("06-temporal-editor.png", "The actual temporal-extent editor preserves inclusive start, exclusive end, subject grouping and the stated basis.", page.locator("#editor-dialog"))
        page.locator('#module-form [data-action="close-dialog"]').click()
        expect(page.locator("#editor-dialog")).not_to_be_visible()

        page.locator('[data-graph-view="graph"]').click()
        select_record(view.get("focus_files", view["focus_relation"]), "files")
        page.evaluate("window.scrollTo(0, 210)")
        shot("07-retained-files.png", "Fictional source material is retained beside an account, with download access and custody metadata.")
        page.locator('[data-graph-action="attach-file"]').click()
        page.locator("#retained-upload").set_input_files(str(scenario["attachments"][0]["path"]))
        shot("08-file-upload.png", "The native styled upload chooser with a synthetic file selected. This screenshot-only draft is discarded, not saved.", page.locator("#editor-dialog"))
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator('#module-form [data-action="close-dialog"]').click()
        expect(page.locator("#editor-dialog")).not_to_be_visible()

        page.locator('[data-graph-view="spacetime"]').click()
        page.locator("#project-revision").select_option(state["revisions"]["conflicting_order"])
        expect(page.locator(".old-revision")).to_be_visible()
        expect(page.locator("#spacetime-cut-status")).to_contain_text("Cut unavailable")
        select_record(view["withdrawn_order"], "history")
        expect(page.locator(".history-list")).to_be_visible()
        page.locator("#spacetime-panel").evaluate("panel => panel.scrollTop=0")
        page.evaluate("window.scrollTo(0, 210)")
        shot("09-preserved-conflict.png", "A pinned historical account preserves conflicting event orders. The current account withdraws the contradictory claim without erasing this revision.")

        page.locator("#project-revision").select_option("")
        expect(page.locator("#snapshot-label")).to_contain_text("current snapshot")
        expect(page.locator("#spacetime-cut-status")).not_to_contain_text("Cut unavailable")
        page.wait_for_function("() => document.querySelector('#spacetime-event-canvas')?._cyreg?.cy?.nodes().length === 5")
        select_record(view["early_event"], "temporal")
        page.set_viewport_size({"width": 430, "height": 1050})
        page.locator("#spacetime-panel").evaluate("panel => panel.scrollTop=0")
        page.locator('[aria-labelledby="event-order-title"]').scroll_into_view_if_needed()
        page.evaluate("window.scrollBy(0, -100)")
        if page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"):
            raise RuntimeError("The mobile demo overflows the viewport.")
        shot("10-mobile-workspace.png", "The same project on a narrow viewport, with the event-order view and ordinary workspace controls.")
        context.close()
        browser.close()

    if errors:
        raise RuntimeError("Browser errors during capture: " + "; ".join(errors))
    if client.request("GET", base)["head"] != before["head"]:
        raise RuntimeError("Screenshot capture unexpectedly changed the project head.")
    # Each parent repository owns deliberate preview copies so its README
    # renders locally and on GitHub without following a submodule image path.
    previews = {"01-record-graph.png": "generalized-record-graph.png",
                "02-event-order.png": "generalized-spacetime.png",
                "03-earlier-topology.png": "generalized-spacetime-earlier.png",
                "04-later-topology.png": "generalized-spacetime-later.png",
                "05-subject-trajectories.png": "generalized-spacetime-trajectories.png"}
    for parent in (INFRA, INFRA.parent):
        destination = parent / "docs/gallery"
        destination.mkdir(parents=True, exist_ok=True)
        for source, target in previews.items():
            shutil.copyfile(GALLERY / source, destination / target)
    manifest = {"scenario": state["scenario"], "synthetic": True, "captured_at": datetime.now(timezone.utc).isoformat(),
        "application_source_commit": subprocess.check_output(["git", "-C", str(APPLICATION), "rev-parse", "HEAD"], text=True).strip(),
        "project_head": before["head"], "verification": state["verification"], "browser_channel": channel,
        "desktop_viewport": {"width": 1680, "height": 1120}, "mobile_viewport": {"width": 430, "height": 1050},
        "record_mutations_during_capture": 0, "images": images, "parent_preview_copies": previews}
    (GALLERY / "manifest.json").write_bytes((json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print("Verified capture preserved the accepted project head; synchronized parent previews.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", default="msedge", help="Installed msedge/chrome, or Playwright chromium")
    capture(parser.parse_args().browser)
