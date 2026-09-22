# Project workspace — implementation design

**Document class:** Informative application design  
**Maturity:** EXPERIMENTAL; initial implementation  
**Date:** 2026-09-22  
**Draft reference baseline:** GR-100/110/200/210 Working Draft 0.3  
**Decision:** [ADR-0007](../../../decisions/ADR-0007-git-backed-project-workspace.md)

**Historical scope:** The text below records the initial `gsp-workspace/0.1` design and its original gaps. The current graph/module/transaction architecture is in [graph_workspace_design.md](../../../docs/planning/graph_workspace_design.md) and [ADR-0008](../../../decisions/ADR-0008-record-graphs-transactions-and-modules.md). That extension replaces the implementation restrictions on single-role records, structured relations, attachments, revision categories, migration and project graph views; the broader epistemic, governance, custody and legal limitations remain. See the current [operation guide](README.md).

## Purpose and supported use

The application lets a person register, sign in, create private projects, and record qualified accounts within a project. A person can revise a record with a reason, inspect its retained versions, export the project's current snapshot as JSON, or download its complete reachable history as a Git bundle. Its immediate purpose is to make trajectory recording usable enough to examine the programme's proposed distinctions and practical burden.

The application does not claim conformance to any GR draft. It implements selected recording functions with declared information limits. Choosing a role or filling a field does not establish occurrence, target identity, evidential warrant, ethical acceptability, or legal effect. A project's owner-assigned record status is separate from the represented effect's modality and from any independent review.

## Components and storage authority

| Component | Responsibility | Authority boundary |
|---|---|---|
| Browser interface | Registration, login, project navigation, recording, revision, history, and export | User input is validated again by the server; a visible interface control is not an authorization rule |
| Flask application | Authentication, access checks, validation, server audit attribution, and bounded Git operations | The trusted server mediates every project operation |
| SQLite | Accounts, credential verification material, sessions, and project ownership/index lookup | Authentication and access data stay outside project content history |
| Per-project bare Git repository | Project manifest and JSON records, retained through commits | The committed project snapshot is authoritative for project content; the database is not a second record-content store |

Projects are private to their owning account through this application. The first version provides no project invitation, shared editing, public link, or Git push/fetch service. An authorized owner can download a Git bundle and clone it locally. Host filesystem access remains an administrative trust boundary. The application is bounded to 1,000 records per project and limits request and field sizes; these are prototype resource limits, not GR requirements.

The storage design avoids a shared writable checkout. A mutation reads the current project tree, creates new content/tree/commit objects, and conditionally advances one project reference using the previously read commit. Git documents the conditional old-object check in [`update-ref`](https://git-scm.com/docs/git-update-ref). A competing successful update causes a conflict; the client can reload and reconsider its edit. This prevents one accepted write from silently replacing an intervening accepted write through the application. It does not authenticate represented observations or make all infrastructure operations atomic.

An object written before an unsuccessful reference update can remain unreachable in Git storage. It is not an accepted project revision. A crash between repository initialization and database registration can also require operator reconciliation. Recovery must inspect the authoritative committed project manifest and access records; an orphan repository is not automatically published or assigned to another account. Database and Git backups need a consistent recovery procedure before operational dependence.

## Recording semantics

Field names below describe the application's narrow data model, not a standardized interchange vocabulary. Project and record JSON declare `schema_version: gsp-workspace/0.1`. The server controls record identifiers, audit account identifiers, and recording timestamps.

| Information | Application representation | Interpretation and limit |
|---|---|---|
| Stable record reference | `id` | Identifies this application record; does not establish target identity |
| Account content | `title`, `content` | Recorder's description; a compound account can still require finer claim separation |
| Primary recording role | `record_type`: Entity, State, Event, Process, Relation, Property | One primary role per record; overlapping target descriptions can use linked records; role-specific criteria are not fully enforced |
| Epistemic mode | `epistemic_mode`: observed, reported, inferred, interpreted, retrospective | A primary account mode, not a truth rating; combined modes require qualification in prose |
| Asserted modality | `modality`: realized, intended, possible, unrealized, unknown | Describes the asserted effect or occurrence, separately from how it is known |
| Recorder's status | `status`: unreviewed, contested, revised, withdrawn | Owner-assigned description; not an independent assessment or institutional case state |
| Attributed source | `attributed_to` | Reported observer, speaker, source, collective, or explicit uncertainty; distinct from the signed-in recorder |
| Method and grounds | `method`, `evidence` | Supplied method description and grounds/references; no automatic evidence verification, external retrieval, or preserved evidence attachment |
| Qualification | `uncertainty`, `alternatives` | Space for limits and competing accounts; empty content does not establish certainty or absence of alternatives |
| Generative context | `conditions`, `consequences` | Enabling/constraining context and asserted effects; no mechanism, beneficial effect, or completed repair is inferred automatically |
| Represented time | `occurred_at` | Recorder-supplied occurrence/target-time description, distinct from server recording time; uncertainty can be stated in the description |
| Cross-references | `related_records` | Links within the project; a link does not establish identity, causation, support, or a typed Relation |
| Audit information | Server-assigned creation/update time and recording-account identifiers | Captures application activity under the server's clock and access model; does not verify real-world identity or independent time |
| Revision rationale | Reason supplied with the revision and retained in its history | Explains the edit; the first version does not structurally classify target, evidence, and descriptive-regime changes |

A Relation can be recorded as a separately referenceable record with its own account and history. The cross-reference list is a navigation facility. It does not replace a Relation record when that relation's own properties or history matter, nor does it yet provide structured relation participants and identity criteria.

The selected mode, modality, and status can coexist. For example, a recorder can describe a realized event through retrospective reconstruction while marking its account contested and explaining the dispute. If both inference and reconstruction matter, the primary mode alone is insufficient; the content and method explain their separate contributions. This known limitation is a candidate input to a richer information-model specification.

## History, conflict, and export behavior

The authoritative current project is a Git commit containing its manifest and records. An accepted record revision preserves the record identifier and creates a new commit with its reason and accountable recording actor. Earlier snapshots remain accessible while their commits are retained. Ordering in this history is recording order; the account can describe an earlier occurrence or an uncertain time.

Updates carry `expected_head`, the project revision the client edited, and `revision_reason`. A stale update is rejected instead of being automatically merged. This is project-wide conflict detection: even an intervening change to another record can require a reload. The conservative boundary keeps the first implementation's behavior explicit. The application does not expose branch creation, concurrent interpretation branches, semantic merging, or a claim that the latest account has the best evidence.

History and historical record reads pass through the same project ownership checks as current reads. A revision identifier is a locator, not a permission token. A version inspected in the application needs to belong to that project's retained history. The history endpoint returns the latest 100 revisions affecting the selected record. It is not a project-wide timeline or a complete browser listing of longer histories; the Git bundle permits examination of the complete reachable history with Git tools.

The JSON export is a current snapshot identified by its source project revision. It contains project records and their available qualifications. It does not contain credentials, authentication sessions, prior snapshots, externally referenced evidence, or confirmation that downstream recipients obtained later corrections. It is a local experimental format, not GR-130 conformity or a complete repository backup.

The separate Git bundle contains the main reference and its complete reachable commit history. It therefore contains earlier and withdrawn account content, revision reasons, and recorded actor names/identifiers, even when the current snapshot no longer displays the earlier formulation. It does not contain the account/session database, authentication credentials, access configuration, or unreachable objects from unsuccessful writes. The owner can clone the bundle for independent inspection, but the bundle alone does not restore a complete running service.

## Traceability to draft needs

Each row identifies a design relationship, not a fulfilled requirement. Exact obligations and conditional triggers remain in the cited 0.3 sources: [GR-100](../../../standards/GR-100-foundations-vocabulary/GR-100.tex), [GR-110](../../../standards/GR-110-recording-requirements/GR-110.tex), [GR-200](../../../standards/GR-200-epistemic-recording/GR-200.tex), and [GR-210](../../../standards/GR-210-evidence-interpretation/GR-210.tex).

| Draft references | Implemented contribution | Material gap or assessment boundary |
|---|---|---|
| R110-001; E200-001 | Project name/description, identifier, owner, version, and private access boundary | No complete collection declaration, purpose/claim-selection assessment, descriptive-regime register, or allocation of independent institutional responsibilities |
| V100-005/010/011; R110-006/009 | Stable records, primary operational role, first-class Relation records, cross-references | Target identity and role admissibility criteria remain descriptive; linked records are not a tested multi-role semantics or a metamodel mapping |
| V100-016; R110-012; E200-005 | Separate primary epistemic mode, modality, and owner-assigned status | Limited mode vocabulary; combined modes, perspective, and assessment disposition are not comprehensively structured |
| E200-004/029/030 | Separate authenticated recorder and attributed source; method field | No verified source identity, complete attribution/transformation chain, instrument version, calibration record, or observation window |
| V100-006; R110-008; E200-008 | Represented time separate from application creation/update time | Observation, acquisition, assessment, intervals, and uncertain ordering lack separate structured fields |
| E200-006/010/011/014/015 | Method, supplied evidence text, uncertainty, and alternatives | No separate versioned material items, claim-relative evidence-role assignments, assessor record, custody chain, or completed examination of alternatives |
| R110-010/015/017/058/112 | Conditions, consequences, and alternative-account descriptions | No automatic generative attribution; no structured link-specific evidence, counterfactuals, recirculation stages, or generativity-return assessment |
| V100-007; R110-020/021; E200-017/038 | Retained revisions, accountable actor/time, required revision reason, accessible earlier versions | No structured classification of revision grounds, parallel interpretation branches, independent retention guarantee, or dependent-claim follow-up |
| R110-025/085/087/092; E200-023/043 | Owner-only access across current content and history; credentials kept out of project history | No per-record disclosure, protected-source arrangement, retention schedule, selective erasure, legal hold, or backup disposition workflow |
| R110-029/030/093; E200-026 | Qualified record presentation and current export identified by source revision | No complete transformation/omission declaration, standardized interchange validation, external correction delivery, or observed user-comprehension assessment |
| R110-023/082; E200-021; C210-005/009/013/048 | The owner can describe a dispute and revise their account | No third-party intake, responsible independent reviewer, service periods, notice, appeal, evidence determination, or operative GR-210 case procedure |
| R110-032/033/034/099; E200-002/045/049 | Tests can examine application behavior and distinguish selected checks from a whole-package claim | No per-requirement conformance dossier; passing application tests does not establish the full GR-200 dependency or any unqualified draft-conformity claim |

## Security, custody, and participation boundaries

The server authenticates each account and checks ownership on project, record, history, and both export operations. Authentication credentials and session state are not project records. Password verification uses Werkzeug's scrypt hashing. Browser session cookies carry opaque random tokens; SQLite retains their SHA-256 digests with a twelve-hour absolute expiration. Session identifiers and anti-forgery tokens rotate at authentication changes. Anonymous sessions also receive anti-forgery protection for login and registration. Cookies use HttpOnly and SameSite=Lax; Secure is configurable for HTTPS deployment. Authentication throttling uses server-observed direct IP addresses and an email digest, without trusting arbitrary forwarded headers.

Write requests require the application's anti-forgery protection as well as authorization. Content is presented as text rather than executed as user-supplied HTML. Git receives bounded arguments and server-controlled repository paths. The initial configuration binds to loopback, limits trusted hostnames to localhost and the IPv4/IPv6 loopback addresses, and sets a content security policy. These controls address ordinary application attack surfaces; deployment controls still matter. Flask's [security guidance](https://flask.palletsprojects.com/en/stable/web-security/) addresses complementary browser, cookie, request, and resource protections. Configuration and operating instructions accompany the implementation. The initial release does not offer email verification, account recovery, or a claim of production readiness.

An authenticated account is not a verified person or qualified reviewer. Attribution to a different person does not imply their consent or endorsement. A host administrator can read stored content and rewrite or delete repository history. This version offers no encryption-at-rest, signed record attestations, trusted timestamps, or independently witnessed history. A commit hash identifies retained content within Git's model; it does not establish the truth of that content.

Withdrawal is an account status, not erasure. Earlier record content can persist in Git objects, repository copies, and backups. Exports place another copy under the recipient's control. The application cannot establish the removal of those copies. A project owner therefore needs a purpose and permission basis appropriate to what they choose to record; the application does not determine that legal or institutional basis.

The first version is suitable for bounded local experimentation with material appropriate to these limits. Organizational use involving other people's consequential records requires agreed custody, access, retention, recovery, participation, and review arrangements. Such arrangements are not created by deployment or by a technical conformance label.

## Follow-on design questions

The following are OPEN or DEFERRED rather than hidden capabilities:

- **OPEN — Shared access:** membership, roles, invitations, revoked access to history, exports, and disclosure of protected sources.
- **OPEN — Representation:** separate claims/material/evidence-role objects; combined epistemic modes; target and observation times; typed missingness; role criteria; parallel accounts and revision grounds.
- **OPEN — Retention and recovery:** authorized selective erasure, repository copies, backup restoration, orphan initialization, and consistency across database and Git.
- **DEFERRED — Review practice:** actual challenge intake, reviewer independence, service clocks, replies, reasoned disposition, notification, and repair follow-up.
- **DEFERRED — Interchange:** migration, import validation, attachment custody, independent implementations, and promotion of stable elements into a separately reviewed Specification.

The next empirical step is to record a bounded case, revise it after new evidence, inspect what another intended reader can reconstruct, and measure the burden and missing distinctions. Results can inform the draft programme through its development procedure. They do not automatically convert this implementation into an adopted model.
