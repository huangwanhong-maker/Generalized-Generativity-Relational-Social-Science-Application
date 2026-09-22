# Application verification

**Document class:** Informative implementation verification record  
**Status:** EXPERIMENTAL; observed checks, 2026-09-22.

## Observed results

The following checks passed against the local implementation. They establish the tested behavior in this environment, not a comprehensive security audit, accessibility conformance, standards conformance, or observed institutional practice.

### Graph protocol release, schema 0.2

The combined non-browser run passed **125 tests**, with three opt-in browser journeys skipped in that command. The checks exercise the shared package together with the real storage/API implementation:

| Check | Result | Scope |
|---|---|---|
| Independent protocol package | 53 passed | Role overlap; same-batch references; unary, cyclic, repeated, parallel and higher-order incidence; opaque modules; profile guards; explicit migration; canonical digests; exact identifiers; byte descriptors and budgets; packaged schema and CLI |
| Real-Git storage | 46 passed | Original storage regressions plus atomic graph/files/receipt publication, failure, racing writers, durable receipts, historical replacement/detachment, long paths, batch reads, quotas, supported binding manifests and bundle restoration |
| Flask API | 26 passed | Original account/authorization regressions plus atomic graphs, pinned labels/material, durable replay/restart, altered transaction IDs, deterministic retry races, verified uploads and limits, exact multipart/JSON parsing, migration-only legacy mutation and precise ZIP scope |
| Browser journeys | 3 passed | Registration and two-tab conflict regression; actual canvas selection and blank-canvas draft creation; multi-participant, higher-order and self relations; explicit completeness and change category; notes/files; pinned historical replacement bytes; lost-response replay after a later edit; list/keyboard alternatives and mobile layout |
| JavaScript and dependencies | Passed | Both application scripts passed `node --check`; `pip check` found no broken requirements |
| Publication/navigation integrity | Passed within stated scope | Local Markdown links resolve; 45 new bounded Working Draft clause IDs are unique; historical validation dossier checks remain valid |

The browser trio passed independently with `GSP_BROWSER=msedge`. After final focus, canvas and historical-replay corrections, the two affected journeys passed again individually. Browser review artifacts use authored test accounts and isolated data, not the user's project. The live preview was refreshed after an offline copy of its existing data directory; its existing legacy project remained readable and unmigrated. This backup operation is not a general restoration certification.

Important defects identified during this cycle included legacy compatibility routes bypassing explicit migration, an identical-request race between receipt lookup and snapshot loading, undeclared opaque-module export limitations, permissive trailing-newline identifier patterns, and unsupported binding manifests being overwritten. Regression checks now cover those cases. Browser integration also required a local external stylesheet rule for the vendored graph renderer under the existing CSP and a renderer resize after connection controls change the canvas position. A recovered receipt for an earlier successful save now remains explicitly historical when newer edits exist; the browser does not label that older accepted snapshot current.

### Initial schema 0.1 baseline (historical)

The earlier observed results below are retained as the initial implementation baseline; current graph scope is described above.

| Check | Result | Scope |
|---|---|---|
| Real-Git storage integration | 22 passed | Historical content, authorship/reasons, stale and concurrent writers, unreachable revisions, project isolation, path/ref input, isolated Git environment, failed writes, bundle restoration, and long Windows paths |
| Flask API integration | 11 passed | Registration/login/logout, session rotation/revocation/expiry, password hashing, CSRF/origin/host checks, ownership on all project routes, revision reasons/conflicts, restart persistence, exports, validation, related-record boundaries, rate limits and Unicode handling |
| Browser journey | 1 passed | Registration, project creation, record creation/revision, historical viewing, two-tab conflict/reconciliation, draft preservation, safe HTML-text display, search, both downloads, mobile layout, logout and login |
| JavaScript syntax | Passed | `node --check applicative_infrastructure/gr_generalized_application/web_application/generative_app/static/app.js` |
| Installed Python dependencies | Passed | `python -m pip check` reported no broken requirements |
| Visual review | Four screenshots inspected | Registration, record/history, desktop project, and 390-pixel mobile project; no observed overlap or horizontal overflow in these views |

The tests ran on Windows with Python 3.12.10, Git 2.50.0.windows.1, Flask 3.1.3, Waitress 3.0.2, pytest 9.1.1 and Playwright 1.63.0 using the installed Microsoft Edge in headless mode. The runtime dependency versions are retained in [requirements.lock](requirements.lock).

Browser screenshots are generated under `build/webapp-review/` at the repository root. Their project and account content is authored test data, isolated from the application's private runtime directory. The visible HTML-looking string is an intentional injection probe verified to remain text, not an image element or executed script.

## Infrastructure relocation verification (2026-09-22)

The relocated application and both common packages passed the combined suite: **128 passed**, including all three Edge browser journeys, with isolated test data and the new Python environment. The Git-store implementation remains byte-identical to the source before extraction. Storage tests now live with the reusable Git package; application tests import it through its public package. See the [migration evidence](../../common/design/migration_verification.md) for runtime preservation and academia checks.

## Reproduce

From the repository root in PowerShell:

```powershell
python applicative_infrastructure/common/tools/setup_application.py generalized --dev
.\applicative_infrastructure\.runtime\environments\generalized\Scripts\python.exe -m pytest -c applicative_infrastructure/gr_generalized_application/web_application/pytest.ini applicative_infrastructure/gr_generalized_application/web_application/tests --basetemp build/webapp-tests
.\applicative_infrastructure\.runtime\environments\generalized\Scripts\python.exe -m pytest applicative_infrastructure/common/packages/gsp_record_protocol/tests --basetemp build/protocol-tests
```

The browser test is skipped unless `GSP_BROWSER` is set. To include the browser journey using an installed Microsoft Edge:

```powershell
$env:GSP_BROWSER='msedge'
.\applicative_infrastructure\.runtime\environments\generalized\Scripts\python.exe -m pytest -c applicative_infrastructure/gr_generalized_application/web_application/pytest.ini applicative_infrastructure/gr_generalized_application/web_application/tests --basetemp build/webapp-tests-with-browser
```

Use `chrome` for installed Google Chrome, or install Playwright Chromium with `python -m playwright install chromium` and set `GSP_BROWSER=chromium`. Browser checks start and stop an isolated Waitress server on a dynamically allocated loopback port; they do not require the ordinary application to be running. The chosen `--basetemp` directory is disposable test output; do not point it at application data or other valuable files.

The release integration command for all non-browser tests is:

```powershell
.\applicative_infrastructure\.runtime\environments\generalized\Scripts\python.exe -m pytest -c applicative_infrastructure/gr_generalized_application/web_application/pytest.ini applicative_infrastructure/gr_generalized_application/web_application/tests applicative_infrastructure/common/packages/gsp_record_protocol/tests applicative_infrastructure/common/packages/gsp_git_store/tests --basetemp build/graph-release-tests -q
```

The graph browser journey generates `build/webapp-review/graph-multi-participant.png` and `graph-mobile.png`. The earlier manual smoke review generated `graph-desktop.png` and `graph-relation.png`. Pointer, form and list interactions are exercised; assistive-technology evaluation and measured user comprehension remain open.

## Defects found and corrected

- A non-ASCII CSRF header reached a comparison requiring ASCII text. The API now rejects it with 403 rather than a server error.
- JSON containing an unpaired Unicode surrogate could reach password hashing or persistent storage. The API now rejects malformed Unicode with 400, while the regression test preserves valid Japanese, accented text and emoji.
- Browser integration exposed Git for Windows rejecting a long absolute `--git-dir` with `'$GIT_DIR' too big`, even with long-path configuration enabled. Repository operations now run from the selected bare repository using `--git-dir=.`. A storage regression exercises the long path without shortening the test location.
- Interface review corrected skip-navigation hash handling and invalidated pending route responses on logout, so those responses cannot re-render a signed-out workspace.

The Git storage tests deliberately leave unreachable objects when publication fails; the old main reference and current snapshot remain unchanged. Such objects are not accepted revisions and do not appear in the exported reachable history. This behavior is distinct from crash recovery across project creation and account ownership, which remains an operational limitation described in the [design](DESIGN.md).
