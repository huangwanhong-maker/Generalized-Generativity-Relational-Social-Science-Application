# Generativity workspace

**Document class:** Software implementation guide  
**Status:** EXPERIMENTAL; application schema `gsp-workspace/0.2`, protocol `gsp-record-protocol/0.2`; 2026-09-22.

A working web application for private projects, connected records, retained files and revisable accounts. Explore an interactive graph, select a record to inspect its modules, and create attributed relations through participant controls. Each project has its own Git repository. This is an experimental implementation informed by the programme's Working Drafts, not an adopted Standard or a conformance claim.

## Run locally

Requirements: Python 3.11 or later and Git on `PATH`. Python 3.12 and Git for Windows were used for development. The interface needs no Node build, external fonts or hosted services. Cytoscape.js is vendored locally with its MIT license and source/hash manifest under `generative_app/static/vendor/`.

From the programme root, use the shared setup and launch tools:

```powershell
python applicative_infrastructure/common/tools/setup_application.py generalized --dev
python applicative_infrastructure/common/tools/run_application.py generalized
```

Open **http://127.0.0.1:8000**. The setup tool recreates the application's own environment and installs both shared packages. It handles Windows extended paths for nested dependencies; the same commands also work with `python3` on Linux or WSL. No demonstration account or default password is installed. Existing migrated accounts and sessions remain available.

The launcher uses Waitress, binds to loopback by default and resolves source/data locations independently of the shell's working directory. Use `--port 8002` if the default port is occupied. Stop it with Ctrl+C. Development previews record their process ID and logs under `build/application-servers/` at the programme root.

## What you can do

- Register, sign in and sign out; sessions expire after 12 hours.
- Create multiple private projects, each accessible only to its creator through the application.
- Add records with overlapping recording roles, content, primary knowledge basis, occurrence/modality and owner-assigned status.
- Record attributed sources, methods, evidence references, uncertainty, alternatives, enabling/constraining conditions and consequences.
- Explore the graph or record list; select nodes, filter, pan, zoom, arrange and fit the view. Layout is a local display preference and creates no record revision.
- Create a Relation record with named participant roles, record/target reference scope, direction and completeness qualifications. Add further participants or relate a Relation to another record. Create a new record and its connection in one save.
- Add retained notes and files through a record's modules. Replace a file or detach its current reference with an attributed reason.
- Revise a record with a reason and change category; inspect its previous versions and the project's latest 100 revision entries. Historical views pin labels, relationships, modules and file bytes to the same revision.
- Export selected-revision metadata as JSON, download a snapshot ZIP with material referenced by supported file modules, or a Git bundle containing complete reachable project history.
- Preview and explicitly migrate an earlier workspace. Reading a project never migrates it; earlier revisions remain unchanged.

Retained files are material, not automatically assessed evidence. The application does not fetch evidence URLs. A selected status such as `contested` describes the owner's account; it does not establish an independent review finding. The form records one primary knowledge basis; use method/context fields to preserve qualifications and mixed bases. The graph's placement and arrows establish no additional causal, evidential, ethical or legal meaning.

If another edit advances the project while your form is open, saving returns a conflict and preserves the draft. Review the latest version and reconcile before saving again. This applies across records in the same project. A retry of an unchanged transaction uses its original identifier; the server returns the original receipt if it already succeeded. Editing the request creates a new transaction identity.

## Where records live

By default, private application data is stored outside the source files in ignored `applicative_infrastructure/.runtime/generalized/`:

```text
.runtime/generalized/
  accounts.sqlite3              # users, password hashes, sessions, ownership, rate limits
  repositories/
    <project-uuid>.git/          # bare Git repository, one per project
```

Each repository contains `project.json`, `records/<record-uuid>.json`, `.gsp/protocol.json`, `.gsp/transactions/<transaction-uuid>.json`, and `assets/<sha256>` on its `main` branch. A transaction publishes its records, material and receipt atomically. Git commits attribute saves to the account's display name and a pseudonymous account identifier, not its login email. Account passwords and session tokens are never placed in project repositories. Record text can itself contain personal information supplied by the author.

Changing a record or marking it withdrawn preserves its earlier text in history. Detaching a file removes the current record association; retained bytes and earlier descriptors remain available through history. A history bundle includes that earlier content and retained material. Git hashes and application attribution do not establish factual truth, independently authenticated identity or an immutable archive against the server operator.

To inspect a downloaded bundle, replace the example filename with your download:

```powershell
git clone .\generativity-PROJECT-ID.bundle .\project-history
git -C .\project-history log
```

That checkout is an inspection copy. Importing edits back into the application is not implemented. JSON excludes all attachment bytes. Snapshot ZIPs exclude older revisions, receipts and unreferenced retained assets; their manifests disclose unsupported module dependencies. A Git bundle preserves project history but does not include accounts or application ownership. None of these exports alone is a complete running-service backup.

For a complete local backup, stop the server and copy the entire data directory, including the SQLite database and any journal files, plus repositories. Restore the whole directory with the same application version into a controlled location. Crash recovery across initial Git-repository creation and the SQLite ownership transaction remains a manual administration task; an interrupted creation can leave an inaccessible orphan repository. Individual record writes publish atomically through Git reference comparison.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `GSP_DATA_DIR` | `applicative_infrastructure/.runtime/generalized` | Absolute path recommended for a different private data location |
| `GSP_COOKIE_SECURE` | unset | Set to `1` when serving exclusively over HTTPS |
| `GSP_TRUSTED_HOSTS` | `localhost,127.0.0.1,[::1]` | Comma-separated request hostnames |

Only use a data directory controlled by the application administrator. Protect filesystem access; private project access here is application authorization, not encryption at rest. The server deliberately does not trust forwarded client-IP headers. There is no production proxy configuration included.

The current version has no invitations, sharing, email verification, password recovery, account deletion, selective erasure, independently witnessed custody, remote Git synchronization or formal contestation workflow. The academia application is a subsequent adapter/upgrade project; it has not been modified here.

The HTTP/Git binding allows 1,000 records per project, 100 operations per transaction, 32 incidences per Relation, eight binary parts, 10 MiB per file, 20 MiB combined uploaded bytes and 128 MiB retained asset bytes in the main tree. Transaction JSON is limited to 1 MiB; resource JSON to 2 MiB and aggregate snapshot JSON to 32 MiB. Core account/compatibility requests retain a 128 KiB bound. Logical retained-asset limits exclude Git metadata and unreachable prepared objects and are not a physical disk quota. Public hosting needs deployment-specific TLS, registration controls, recovery, operational quotas, monitoring and an exercised retention/backup policy.

## Verification and design

Install test tools with the setup command's `--dev` option. The [shared verification guide](../../common/conformance/README.md) gives the combined package/API/browser command; [TESTING.md](TESTING.md) retains the original graph-release evidence and current reproduction instructions.

Tests use isolated temporary databases and real Git repositories. The browser test is opt-in; its instructions and observed results are recorded in [TESTING.md](TESTING.md).

The [current design](../../../docs/planning/graph_workspace_design.md) and [ADR-0008](../../../decisions/ADR-0008-record-graphs-transactions-and-modules.md) connect manuscript interpretation, user interaction and architecture. The [academia review](../../../docs/reviews/academia_application_reference.md) records useful patterns and incompatibilities without copying its implementation. [DESIGN.md](DESIGN.md) retains the earlier design and initial traceability baseline.

The reusable [protocol package](../../common/packages/gsp_record_protocol/README.md), [GR-SPEC-120](../../../specifications/GR-SPEC-120-information-model/GR-SPEC-120.md) and [GR-SPEC-130](../../../specifications/GR-SPEC-130-interchange/GR-SPEC-130.md) define the experimental model and binding. Official implementation references include [Git update-ref](https://git-scm.com/docs/git-update-ref/2.45.0), [Flask security guidance](https://flask.palletsprojects.com/en/stable/web-security/) and [Cytoscape.js](https://js.cytoscape.org/).
