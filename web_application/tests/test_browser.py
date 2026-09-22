"""Opt-in end-to-end test: GSP_BROWSER=msedge (or chrome/chromium)."""
import os
from pathlib import Path
import threading

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("GSP_BROWSER"), reason="Set GSP_BROWSER to run the local browser integration test.")


def test_full_browser_journey_and_conflicting_edits(tmp_path):
    from playwright.sync_api import expect, sync_playwright
    from waitress import create_server
    from generative_app import create_app

    app = create_app({"DATA_DIR": tmp_path / "browser-data", "TESTING": True})
    server = create_server(app, host="127.0.0.1", port=0, threads=4)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.effective_port}"
    artifacts = Path(__file__).resolve().parents[4] / "build/webapp-review"
    artifacts.mkdir(parents=True, exist_ok=True)
    errors = []
    channel = os.environ["GSP_BROWSER"]
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, **({"channel": channel} if channel != "chromium" else {}))
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" and "Content Security Policy" in message.text else None)
            page.goto(url)
            expect(page.locator("#auth-form")).to_be_visible()
            page.screenshot(path=str(artifacts / "01-registration.png"), full_page=True)
            page.locator('[name="display_name"]').fill("Pilot researcher")
            page.locator('[name="email"]').fill("browser-pilot@example.test")
            page.locator('[name="password"]').fill("browser verification passphrase")
            page.locator('#auth-form button[type="submit"]').click()
            expect(page.locator('[data-action="new-project"]').first).to_be_visible()
            page.locator('[data-action="new-project"]').first.click()
            page.locator('#project-form [name="name"]').fill("Community garden inquiry")
            page.locator('#project-form [name="description"]').fill("An authored test project tracing encounters, uncertain evidence, and possibilities.")
            page.locator('#project-form button[type="submit"]').click()
            expect(page.locator("h1")).to_have_text("Community garden inquiry")
            project_url = page.url
            page.locator('[data-action="new-record"]').first.click()
            page.locator('#record-form [name="title"]').fill("An encounter changes the question")
            content = 'A conversation suggested an alternative planting plan. <img src=x onerror="window.injected=1">'
            page.locator('#record-form [name="content"]').fill(content)
            page.locator('[name="record_type"]').select_option("Event")
            page.locator('[name="epistemic_mode"]').select_option("reported")
            page.locator('[name="modality"]').select_option("realized")
            page.locator("summary").filter(has_text="Perspective & evidence").click()
            page.locator('[name="attributed_to"]').fill("A participant's account")
            page.locator('[name="uncertainty"]').fill("Reported retrospectively; no contemporaneous notes are available.")
            page.locator('#record-form button[type="submit"]').click()
            expect(page.locator(".inspector-header h2")).to_have_text("An encounter changes the question")
            page.locator('[data-graph-action="full-record"]').click()
            expect(page.locator(".old-revision")).to_be_visible()
            page.locator('[data-action="current-revision"]').click()
            expect(page.locator("h1")).to_have_text("An encounter changes the question")
            expect(page.locator('[data-action="edit-record"]')).to_be_visible()
            record_url = page.url
            expect(page.locator(".record-content")).to_have_text(content)
            assert page.evaluate("window.injected") is None
            assert page.locator(".record-content img").count() == 0

            page.locator('[data-action="edit-record"]').click()
            page.locator('#record-form [name="title"]').fill("A possible change in the planting plan")
            page.locator('[name="revision_reason"]').fill("Separated the reported encounter from the proposed practical response.")
            page.locator('#record-form button[type="submit"]').click()
            expect(page.locator("h1")).to_have_text("A possible change in the planting plan")
            expect(page.locator('[data-action="view-revision"]')).to_have_count(2)
            page.locator('[data-action="view-revision"]').last.click()
            expect(page.locator(".old-revision")).to_be_visible()
            expect(page.locator("h1")).to_have_text("An encounter changes the question")
            expect(page.locator('[data-action="edit-record"]')).to_have_count(0)
            page.locator('[data-action="current-revision"]').click()
            expect(page.locator("h1")).to_have_text("A possible change in the planting plan")

            # Two tabs edit the same loaded version. The losing draft stays visible.
            other = context.new_page()
            other.goto(record_url)
            expect(other.locator('[data-action="edit-record"]')).to_be_visible()
            page.locator('[data-action="edit-record"]').click()
            page.locator('#record-form [name="title"]').fill("My draft remains available")
            page.locator('[name="revision_reason"]').fill("Reconcile after another tab updates the record.")
            other.locator('[data-action="edit-record"]').click()
            other.locator('#record-form [name="title"]').fill("An independent edit in another tab")
            other.locator('[name="revision_reason"]').fill("Additional context arrived.")
            other.locator('#record-form button[type="submit"]').click()
            expect(other.locator("h1")).to_have_text("An independent edit in another tab")
            page.locator('#record-form button[type="submit"]').click()
            expect(page.locator(".conflict-panel")).to_be_visible()
            expect(page.locator('#record-form [name="title"]')).to_have_value("My draft remains available")
            page.locator("#compare-latest").click()
            expect(page.locator("#conflict-preview")).to_contain_text("An independent edit in another tab")
            page.locator("#keep-draft").click()
            page.locator('#record-form button[type="submit"]').click()
            expect(page.locator("h1")).to_have_text("My draft remains available")
            page.screenshot(path=str(artifacts / "02-record-history.png"), full_page=True)
            other.close()

            page.goto(project_url)
            expect(page.locator("h1")).to_have_text("Community garden inquiry")
            page.locator("#record-search").fill("no match here")
            expect(page.locator("#record-list")).not_to_contain_text("My draft remains available")
            page.locator("#record-search").fill("")
            expect(page.locator("#record-list")).to_contain_text("My draft remains available")
            page.locator(".export-menu > summary").click()
            with page.expect_download() as snapshot:
                page.get_by_role("link", name="Records as JSON").click()
            assert snapshot.value.suggested_filename.endswith(".json")
            with page.expect_download() as history:
                page.get_by_role("link", name="Complete Git history").click()
            assert history.value.suggested_filename.endswith(".bundle")
            page.screenshot(path=str(artifacts / "03-project.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(artifacts / "04-mobile-project.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.locator('[data-action="logout"]').click()
            expect(page.locator("#auth-form")).to_be_visible()
            page.locator('[data-action="login-tab"]').click()
            page.locator('[name="email"]').fill("browser-pilot@example.test")
            page.locator('[name="password"]').fill("browser verification passphrase")
            page.locator('#auth-form button[type="submit"]').click()
            expect(page.locator("#record-list")).to_contain_text("My draft remains available")
            assert not errors, errors
            context.close()
            browser.close()
    finally:
        server.close()
        server.task_dispatcher.shutdown()
        thread.join(timeout=5)
