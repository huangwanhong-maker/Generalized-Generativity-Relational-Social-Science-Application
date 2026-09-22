# Generalized GR application

**Class:** Application and development guide  
**Status:** Experimental application; gsp-record-protocol/0.2 and gsp.general/0.2

The generalized application is a local web workspace for recording situations, their relations, the grounds of accounts about them, and their subsequent revision. A visual graph lets users create and connect records, inspect their modules and return to a coherent historical view.

It is one application within the Generativity Standards Program. The programme's operational recording roles and working specifications inform its model; neither saving a record nor passing its validation establishes factual truth or formal Standard conformance.

## Current capabilities

- Register and sign in; create multiple private projects, each with its own record Git repository.
- Create records with overlapping Entity, State, Event, Process, Relation and Property roles, attributed context, knowledge basis, uncertainty and alternatives.
- Create first-class Relations with named participants and qualified direction/reference scope; connect to an existing record or create a record and its relation in one save.
- Explore, select, filter and arrange the graph or browse a record list. Layout choices affect the display without creating record revisions.
- Attach notes and retained files through record modules, replace material, or detach its current association with an attributed reason.
- Revise records with a reason and change category; inspect historical labels, relations, modules and file bytes at one selected revision.
- Export JSON metadata, a material-bearing snapshot ZIP, or a Git bundle of reachable project history.
- Preview and explicitly migrate a legacy workspace while preserving earlier revisions.

The [web application guide](web_application/README.md) gives the detailed interaction model, resource limits and account behavior. A Relation can itself have properties, notes, files and history. The graph's position and arrows add no causal, epistemic or legal meaning beyond the records they present.

## Source repository and dependencies

~~~text
gr_generalized_application/             This application Git repository
├── README.md  LICENSE  CONTRIBUTORS.md
└── web_application/
    ├── run.py                         Local Waitress entry point
    ├── generative_app/                Flask application, templates and interface
    ├── tests/                         API and opt-in browser journeys
    ├── requirements.lock             Application dependency versions
    ├── DESIGN.md
    └── TESTING.md
~~~

This repository is a submodule of [applicative_infrastructure](../README.md). It consumes the sibling [record-protocol package](../common/packages/gsp_record_protocol/README.md) and [Git-store package](../common/packages/gsp_git_store/README.md). Common tools and packages belong to the infrastructure repository; this application does not depend on academia.

The supported setup expects the infrastructure checkout with its submodules initialized. Cloning this application alone obtains its source but not the common packages or setup tools. Programme [specifications](../../specifications/) and [design decisions](../../decisions/ADR-0008-record-graphs-transactions-and-modules.md) are available in the complete programme checkout.

Application source commits and user project commits are separate histories. A parent infrastructure commit pins the application revision; runtime project repositories retain the users' record revisions.

## Install and run

Requirements: Python 3.11 or later and Git on PATH. No Node build, hosted fonts or external service is needed for the interface. Its vendored Cytoscape.js component includes its own notice and source manifest.

From the **parent infrastructure directory**:

~~~powershell
python common/tools/setup_application.py generalized --dev
python common/tools/run_application.py generalized
~~~

Open **http://127.0.0.1:8000**. On Linux/WSL, use the system's Python 3 command. The setup tool creates the generalized environment, installs the common packages and application dependencies, and optionally installs test tools. No default account is created; registration is available in the interface.

The launcher binds to loopback, accepts a different port and stops with Ctrl+C:

~~~powershell
python common/tools/run_application.py generalized --port 8002
~~~

The application has independent account/session storage and the gsp_session cookie. Existing credentials from the local migration remain in that runtime; a fresh source clone has no migrated account data.

## Records, configuration and recovery

~~~text
applicative_infrastructure/.runtime/generalized/
├── accounts.sqlite3                 Users, sessions, ownership and rate limits
└── repositories/
    └── <project-uuid>.git/           Bare Git repository for one user project
~~~

The GSP_DATA_DIR environment variable selects another absolute runtime path. GSP_COOKIE_SECURE and GSP_TRUSTED_HOSTS configure HTTPS-only cookies and accepted request hosts; details are in the [configuration guide](web_application/README.md#configuration).

A transaction publishes record changes, retained assets and its receipt atomically. If another edit advances the project, the application rejects a stale save and preserves the user's draft for reconciliation. Retrying an unchanged transaction can recover its original receipt.

Revision and withdrawal retain earlier text in Git history. Detaching a file removes the current association, while earlier descriptors and bytes can remain retrievable. A project bundle includes reachable history but excludes accounts and application ownership; it is an inspection/export artifact, not a complete running-service backup. Importing arbitrary edited Git history is not implemented.

For a complete backup, stop the writer and copy the entire runtime, including the account database, journals and project repositories. Restore a matched runtime and application version together. Source submodule updates do not transfer or convert these records. The [infrastructure recovery guide](../README.md#data-and-recovery) describes the retained relocation backups.

## Verification

After development setup, from this application directory on PowerShell:

~~~powershell
& ../.runtime/environments/generalized/Scripts/python.exe -m pytest -c web_application/pytest.ini web_application/tests ../common/packages/gsp_record_protocol/tests ../common/packages/gsp_git_store/tests --basetemp ../.runtime/test-output/generalized -q
~~~

Use bin/python on POSIX. The temporary-output directory is disposable and must not contain valuable records. Set GSP_BROWSER to msedge for the three browser journeys if Edge is installed. See [TESTING.md](web_application/TESTING.md) for browser alternatives and [shared verification](../common/conformance/README.md) for scope.

The migration's combined generalized/common run passed **128 tests**, including three browser journeys. Its [verification report](../common/design/migration_verification.md) records the tested revision and preservation boundary.

## Current limits and development

The application currently provides owner-private projects. Sharing, invitations, email verification, password recovery, selective erasure, remote synchronization, independent custody witnessing and a formal contestation workflow remain outside the implemented experience. Public hosting requires deployment-specific administration and operating controls. The [web guide](web_application/README.md) documents size limits, exports and failure recovery.

Academia remains a separate native GRRP application; a shared domain adapter is future work. Preserve the distinction between retained material and assessed evidence, the account owner's status choice and independent review, and application attribution and authenticated external identity.

Commit application edits here, then update its pinned commit in infrastructure and the infrastructure pin in the programme. Changes to common packages belong in infrastructure. Link conceptual changes to programme requirements and ADRs rather than redefining GR theory in application code alone.

## License and contributors

Project-authored material is available under the [MIT License](LICENSE), with copyright held by contributors recorded in [CONTRIBUTORS.md](CONTRIBUTORS.md). See [LICENSE.md](LICENSE.md) for scope and retained third-party notices. The license does not assign rights over records or uploaded files created by application users.
