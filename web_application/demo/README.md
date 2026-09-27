# River Commons demonstration

**Class:** Informative application example and reproduction guide  
**Status:** Synthetic demonstration for the experimental generalized application  
**Scenario:** `river-commons/1`

River Commons is a fictional inquiry into shared care of a garden: how an encounter opens a possibility, how a provisional arrangement changes, and how accounts of those changes are questioned and revised. Every person, institution, place, observation and source file is invented. The example makes no claim about a real community or legal arrangement.

Start with the [visualized spacetime walkthrough](../../docs/gallery/README.md#see-the-visualized-spacetime): see the event partial order, compare ontology topologies at two boundaries, then follow the garden and stewardship trajectories. The gallery also shows the record graph, temporal editor, retained files and historical contradictions. Its screenshots come from the running application, using ordinary controls.

## What the project contains

The project contains 31 records, all six operational recording roles, notes, six retained source files and a deliberately nonchronological recording history.

| Primary role | Records | Examples |
|---|---:|---|
| Entity | 4 | The garden, residents' circle and stewardship team |
| State | 5 | Trial access, revised access and changing stewardship arrangements |
| Event | 5 | Encounter, access agreement, workday, review and an observation with no usable temporal anchor |
| Process | 1 | Learning to care for a shared place |
| Relation | 12 | Seven qualified relationship accounts and five event-order accounts |
| Property | 4 | Contextual location, unknown water suitability, proposed capacity and disputed workload |

Four event-order claims are active in the final account. A fifth is withdrawn after it creates a contradictory chronology. The withdrawn record and its earlier assessment remain available in history.

Six materials in [materials/](materials/) are attached through the normal file API: encounter notes, an access memorandum, water observations, a review summary, an attendance ledger and a chronology reconciliation. They contain synthetic evidence for the story, not independent verification of it.

## Follow the story

The seeder preserves five narrative stages, followed by one attachment transaction:

1. **Begin with the later review.** The first record describes the end-of-trial review. Earlier occurrences have not yet been recorded.
2. **Add retrospective context.** Record the encounter, agreement and workday, their participants, and explicit event precedence. The independent water observation remains unordered.
3. **Describe scoped accounts.** Add successive and competing State accounts, contextual Properties, first-class Relations, an unrealized alternative and temporal extents.
4. **Preserve a contradiction.** An imported index is mistakenly interpreted as placing the review before the encounter. The historical temporal projection reports a cycle and does not invent a consistent cut.
5. **Revise the account.** Withdraw the mistaken order claim and correct reported review attendance from 18 entries to 16 distinct attendees. Both earlier assertions remain inspectable.
6. **Retain the materials.** Save the six fictional files alongside their associated records in one project revision.

Recording order and represented event order therefore differ visibly. The correction changes the recorded account; it does not change what happened in the fictional review.

## Explore the visualized spacetime

Here, **space is the topology of applicable ontology records**, and an event boundary selects which temporal extents apply. A contextual location Property, **A place beside the footpath**, provides a geographical description within the story. It does not define the coordinates of this visualization.

Keep **Current project** selected so every view below uses the same retained revision. In **Spacetime**:

1. **Read the event partial order.** Follow the arrows from **The riverside encounter**, through two branches (**A provisional access agreement** and **The first shared workday**), to **A shared review**. No claim orders the two middle events relative to one another. **An independent water observation** is incomparable with all four. Neither graph columns nor the absence of arrows assert simultaneity.
2. **Select the trial boundary.** Choose **Before all**, then mark **A provisional access agreement** as passed. Its predecessor, the encounter, is included automatically: 2 of 5 events have passed. The ontology topology contains 10 records, including **A garden open for a trial** and **A provisional stewardship arrangement**. The workday remains outside this selected cut because it is not an established predecessor of the agreement.
3. **Select the review boundary.** Mark **A shared review** as passed. Both branches and the encounter are included: 4 of 5 events have passed. The topology contains 13 records. Trial access and the provisional arrangement have ended; **Access under a revised rota**, **Care shared through a rota** and **A renewed agreement to care** are applicable. The independent observation remains outside the cut and unordered.
4. **Follow the subject trajectories.** In **Record trajectories**, inspect the garden's State descriptions: **Access not yet arranged**, **A garden open for a trial**, then **Access under a revised rota**. Their inclusive starts and exclusive ends connect them to the agreement and review boundaries. Compare the stewardship team's informal and rotating-care descriptions, together with the contested workload concern.

The [gallery's two boundary screenshots](../../docs/gallery/README.md#the-ontology-topology-changes-with-the-selected-boundary) make this comparison visible, with the actual boundary labels and selected State accounts. Choosing cuts and viewing trajectories do not save project revisions. These projections apply recorded extents; they do not infer event effects or causation.

Unknown water applicability remains indeterminate, and the proposed six beds remain unscoped. A subject grouping connects descriptions without independently establishing identity, continuity or agreement among them. A consistent cut is a selected event boundary, not evidence that every applicable description shared a physical clock instant.

## Inspect the accounts and their preservation

In **Graph**, select **A provisional stewardship arrangement** and open **Relation** to inspect its three participant roles. Open **Notes** or **Files** for associated context and material. The higher-order relation **Access is more than an open gate** refers to accounts being qualified, making its epistemic role explicit.

Select **A garden open for a trial**, open **Time & trajectory**, and choose **Revise temporal extent** to inspect its inclusive agreement boundary, exclusive review boundary, subject and stated basis. Cancel to keep the demonstration unchanged.

Finally, use the **Project revision** selector to open the stage whose reason begins **Retain a contested chronology claim**. Its event-order cycle prevents a consistent topology projection. Returning to the current project shows the withdrawn claim alongside the remaining active order. Record **History** and **Read full account** expose the preservation and attribution details.

## Create the demonstration

Use the complete application/infrastructure checkout and the development environment described in the [application guide](../../README.md#install-and-run). From `applicative_infrastructure/`, install the environment if needed:

```powershell
python common/tools/setup_application.py generalized --dev
```

If the generalized application is not already running, start it in another terminal:

```powershell
python common/tools/run_application.py generalized
```

Then create or resume the demo through its local HTTP API:

```powershell
& .runtime/environments/generalized/Scripts/python.exe gr_generalized_application/web_application/demo/seed.py
```

The default origin is `http://127.0.0.1:8000`. Use `--base-url http://127.0.0.1:8002` when the application runs on another local port. The client accepts local HTTP origins only. On Linux/WSL, use `.runtime/environments/generalized/bin/python` instead of the Windows interpreter path.

The script creates a separate **Demo curator** account with an `example.test` email address and a generated password, then creates its private project through the ordinary API. It prints the project link and the path to local sign-in details. It does not select another user's project.

Credentials, project identifiers, transaction-recovery data and accepted revision identifiers are kept in the ignored file:

```text
applicative_infrastructure/.runtime/demo/river-commons.json
```

Read that file locally when signing in to explore the project. It contains a plaintext generated demo password; do not add it to source control or include it in screenshots. The actual account database and project Git repository remain in the application's configured runtime.

Rerunning the seeder resumes recorded stages and retries a pending transaction with its original identifier. It does not reset the project. If registration was interrupted before confirmation, it first tries the saved credentials and retries registration only when no account or project has been confirmed. If other edits have advanced the demo, the script stops rather than overwriting them. A different server or scenario is also rejected while this manifest belongs to the existing demonstration. Preserve the manifest together with the relevant runtime if you need to resume that instance later.

## Reproduce the gallery

After seeding, run from `applicative_infrastructure/`:

```powershell
& .runtime/environments/generalized/Scripts/python.exe gr_generalized_application/web_application/demo/capture.py --browser msedge
```

The development dependencies include Playwright. The default browser is installed Microsoft Edge; `--browser chrome` uses installed Chrome, and `--browser chromium` uses a separately installed Playwright Chromium browser.

The capture script signs in using the private manifest, reads the actual project and operates ordinary UI controls. It opens the temporal editor and selects a synthetic upload file, then discards both drafts. It checks that the project head is unchanged, rejects captured browser errors and checks the narrow viewport for horizontal overflow.

The script writes ten PNG images and a public `manifest.json` into [the gallery directory](../../docs/gallery/). The manifest records the synthetic scenario, capture time, application source commit, project head, viewport dimensions and image hashes; it excludes credentials. Five preview images are synchronized into each of the programme and infrastructure repositories' `docs/gallery/` directories: the record graph, event order, earlier topology, later topology and subject trajectories. The [gallery maintenance table](../../docs/gallery/README.md#capture-and-preview-maintenance) gives the exact canonical-to-preview filename mapping. These deliberate copies let parent READMEs render locally and on GitHub across submodule boundaries. Regenerate previews through this script instead of editing the copies independently.

The graph overview uses the visible search query **care**, showing 11 of the 31 records. That filter makes the pictured relationships readable; the other records remain in the project. The capture script arranges those visible nodes into a local display grid, equivalent to dragging them into position; it does not change records or invent connections. Desktop captures use a 1680 × 1120 viewport and the mobile capture uses 430 × 1050. Scrolling, selected cuts and graph layout affect presentation without creating project revisions.

## Source and limits

- [scenario.py](scenario.py) describes deterministic record identifiers, staged operations and attachment inputs.
- [seed.py](seed.py) submits those stages through authenticated, CSRF-protected application endpoints and verifies the scenario's principal temporal distinctions.
- [capture.py](capture.py) produces the actual UI images and synchronizes parent previews.

This example illustrates implemented recording and projection behavior. It does not simulate unrecorded event effects, infer causation from precedence, establish a common physical clock, or demonstrate factual truth or formal Standard conformance. Its unresolved access concerns, unknown observation scope and unrealized alternative are part of the example rather than missing setup steps.
