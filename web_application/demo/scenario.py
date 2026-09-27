"""A deterministic, entirely fictional inquiry for the generalized application.

This module only describes data. It performs no HTTP requests, writes no runtime
data, and creates no credentials. Submit ``stages`` in order to retain the
deliberate retrospective recording and correction history. Attach materials
through the normal file API; do not construct retained file descriptors here.
"""

from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid5


NAMESPACE = UUID("78904f67-73a3-45ac-b9a8-39e6b78464c4")
MATERIALS = Path(__file__).resolve().parent / "materials"


def build_scenario():
    """Return fresh project metadata, staged operations and attachment inputs.

    ``records`` contains initial create payloads, before the final corrections.
    ``ids`` and ``view`` give capture scripts stable record identifiers. Reusing
    these identifiers across distinct demo projects does not equate their
    represented subjects. Every account and attachment is synthetic.
    """
    ids, records, stages = {}, {}, []

    def identifier(key):
        return ids.setdefault(key, str(uuid5(NAMESPACE, key)))

    def module(data, required=False):
        return {"version": "1", "required": required, "data": data}

    def boundary(key):
        return {"kind": key} if key in {"unbounded", "unknown"} else {
            "kind": "event", "event_id": identifier(key)}

    def scope(start="unbounded", end="unbounded", subject=None, basis=None):
        data = {
            "start": boundary(start), "end": boundary(end),
            "basis": basis or (
                "Synthetic case convention: this description applies within the bounded spring inquiry. "
                "An event boundary expresses the stated account, not an independently established change. "
                "Unbounded means no additional boundary is asserted within this inquiry."),
        }
        if subject:
            data["subject_record_id"] = identifier(subject)
        return module(data, required=True)

    def record(key, title, role, content, **extra):
        value = {
            "id": identifier(key), "title": title, "record_type": role,
            "record_roles": [role], "content": content,
            "epistemic_mode": "reported", "status": "unreviewed", "modality": "realized",
            "attributed_to": "River Commons inquiry group (fictional)",
            "method": "Synthetic teaching account; no fieldwork or real participants are represented.",
            "uncertainty": "Invented for demonstration. Within the story, attribution and review remain distinct from factual verification.",
            "modules": {},
            **extra,
        }
        records[key] = value
        return value

    def notes(value, text):
        value["modules"]["gsp.notes"] = module({"text": text})
        return value

    def temporal(value, start="unbounded", end="unbounded", subject=None, basis=None):
        value["modules"]["gsp.temporal_extent"] = scope(start, end, subject, basis)
        return value

    def relation(key, title, predicate, participants, content, *, start="unbounded",
                 end="unbounded", subject=None, scope_kind="represented_target", **extra):
        value = record(key, title, "Relation", content, **extra)
        value["modules"]["gsp.relation"] = module({
            "predicate": predicate,
            "predicate_definition": "An attributed relationship within this fictional inquiry; inspect the account for its grounds and limitations.",
            "participants_complete": False,
            "participant_limitations": "Only participants relevant to this teaching account are included; this is not a census of possible contributors.",
            "participants": [{
                "id": str(uuid5(NAMESPACE, f"{key}/participant/{index}")),
                "record_id": identifier(target), "role": role,
                "reference_scope": scope_kind, "orientation": "undirected",
            } for index, (target, role) in enumerate(participants)],
            "context": "SYNTHETIC River Commons shared garden inquiry.",
            "identity_criterion": "This bounded relationship account and its specified participant roles; continuity requires interpretation.",
        })
        return temporal(value, start, end, subject)

    def order(key, title, before, after, content, **extra):
        value = relation(key, title, "precedes", [(before, "before"), (after, "after")], content, **extra)
        value["modules"].pop("gsp.temporal_extent")
        data = value["modules"]["gsp.relation"]["data"]
        data["participants_complete"] = True
        data["participant_limitations"] = ""
        data["participants"][0]["orientation"] = "in"
        data["participants"][1]["orientation"] = "out"
        value["modules"]["gsp.event_order"] = module({
            "before": identifier(before), "after": identifier(after)}, required=True)
        return value

    def stage(key, reason, keys=(), operations=(), categories=("description",)):
        stages.append({"key": key, "reason": reason, "change_categories": list(categories),
                       "operations": [{"op": "record.create", "record": deepcopy(records[k])} for k in keys]
                       + deepcopy(list(operations))})

    # The review is deliberately recorded before its reported antecedents.
    notes(record("review", "A shared review", "Event",
                 "At the close of the fictional spring trial, participants reviewed access, workload and water use. "
                 "The initial summary reports 18 participants and proposes a revised stewardship rota. "
                 "Some residents question whether access was equally usable. This is a report of a review, not proof of agreement.",
                 occurred_at="Late spring, fictional case year",
                 evidence="Initial review summary; the source ledger is reconciled in a later recording revision.",
                 alternatives="A longer trial, a smaller rota and ending the inquiry were discussed."),
          "Start here: this later event is the first account committed. Earlier encounters are added retrospectively. "
          "Use revision history to inspect the later correction from 18 to 16 distinct attendees.")
    stage("late_review", "Begin the synthetic inquiry with its later review account, before earlier events are recorded.", ["review"])

    # Persistent subject accounts provide contextual anchors, not timeless existence.
    temporal(record("garden", "River Commons garden", "Entity",
                    "A fictional riverside plot used to explore shared care, access and stewardship. The described subject is the plot "
                    "within the spring inquiry, not a legal parcel or an ownership determination.",
                    evidence="Invented site sketch and inquiry brief."))
    temporal(record("residents", "Residents' circle", "Entity",
                    "A fictional, informal circle of nearby residents asking how care of a shared place can be organized. Participation changes during the inquiry; "
                    "the label does not imply unanimous views or that every resident is represented."))
    temporal(record("stewards", "Stewardship team", "Entity",
                    "A fictional rotating team that organizes access and practical care. Continuity is attributed to a shared remit "
                    "and handover practice, rather than fixed membership."))
    temporal(record("water_coop", "Water cooperative", "Entity",
                    "A fictional cooperative invited to advise on watering, resource sharing and care. Its participation is not "
                    "a certification of water quality, ownership or legal compliance."))

    record("encounter", "The riverside encounter", "Event",
           "Residents and prospective stewards report meeting beside the disused plot and recognizing a possibility for shared inquiry. "
           "The discussion opened questions about access and care; it did not itself establish rights or an obligation to participate.",
           epistemic_mode="retrospective", occurred_at="Early spring, fictional case year",
           evidence="Synthetic encounter notes, reconstructed after the shared review.",
           conditions="A publicly accessible path allowed a contingent meeting.",
           consequences="Participants described a new possibility for collaboration; this is their interpretation of the encounter.")
    record("agreement", "A provisional access agreement", "Event",
           "The fictional team and cooperative report recording a limited access arrangement for an exploratory trial. "
           "This account represents an institutional understanding within the story. It creates no real permission, duty or legal status.",
           occurred_at="During spring, fictional case year",
           evidence="Synthetic access memorandum.",
           uncertainty="The order relative to the public-edge workday is not established by the retained material.")
    record("workday", "The first shared workday", "Event",
           "Participants report clearing debris and marking accessible routes along the publicly accessible edge of the plot. "
           "This activity is described separately from permission to use the interior. Its order relative to the access agreement remains open.",
           occurred_at="During spring, fictional case year",
           evidence="Synthetic workday notes and material ledger.",
           uncertainty="The occurrence is reported retrospectively; its relation to the access agreement is deliberately unordered.")
    record("observation", "An independent water observation", "Event",
           "A cooperative observer reports an informal check near the plot. The retained copy gives no usable temporal anchor. "
           "The event is intentionally incomparable with the other four events; an absent order claim is not a claim of simultaneity.",
           occurred_at="Date not established",
           evidence="Synthetic water-observations.csv; entries illustrate incomplete observation context.",
           uncertainty="Sampling time, calibration and comparability are not established.")
    notes(temporal(record("inquiry", "Learning to care for a shared place", "Process",
                          "A bounded fictional inquiry that connects encounters, provisional arrangements, practical work and revision. "
                          "Its reported contribution is a greater capacity to ask and revisit shared questions, alongside unresolved workload and access concerns.",
                          epistemic_mode="interpreted",
                          conditions="Volunteer attention, a place to meet and permission to question the initial arrangement.",
                          consequences="A revised rota and a continuing review practice are proposed; sustainable benefit remains unestablished."),
                   "encounter", "unbounded", "garden"),
          "This process account does not infer causation from event precedence. The graph retains participants and relationships; "
          "Spacetime projects explicitly scoped accounts. Neither view reconstructs unrecorded transformations automatically.")
    order("before_encounter_agreement", "Encounter before agreement", "encounter", "agreement",
          "The fictional access memorandum refers back to the riverside encounter. This supports the stated precedence within the account.")
    order("before_encounter_workday", "Encounter before workday", "encounter", "workday",
          "The synthetic workday notes describe the encounter as preceding the activity. No causal sufficiency is claimed.")
    order("before_agreement_review", "Agreement before review", "agreement", "review",
          "The review considers the provisional arrangement already in use. This places that agreement before the review in the retained account.")
    order("before_workday_review", "Workday before review", "workday", "review",
          "The review discusses completed public-edge work. This order claim does not order the workday relative to the access agreement.")
    stage("retrospective_context", "Add earlier accounts and an explicit branching event order; preserve the observation without an invented temporal position.",
          ["garden", "residents", "stewards", "water_coop", "encounter", "agreement", "workday", "observation", "inquiry",
           "before_encounter_agreement", "before_encounter_workday", "before_agreement_review", "before_workday_review"])

    # Separate state accounts retain the subject trajectory without editing history away.
    temporal(record("state_access_closed", "Access not yet arranged", "State",
                    "The fictional plot is described as lacking a shared interior-access arrangement before the provisional agreement. "
                    "This is a limited account of the inquiry's arrangement, not a finding about general public access or legal ownership."),
             "unbounded", "agreement", "garden")
    notes(temporal(record("state_access_trial", "A garden open for a trial", "State",
                          "During the trial, the team describes limited interior access under a provisional arrangement. "
                          "Step-free access and key availability remain contested. This state ends at the review boundary within this account.",
                          status="contested", evidence="Synthetic access memorandum and residents' questions.",
                          alternatives="Nominal opening and practically usable access may require different state descriptions."),
                   "agreement", "review", "garden"),
          "Scope: after the access-agreement event and before the review event. Selecting the agreement in Spacetime includes its "
          "predecessor automatically. It does not include the incomparable workday without an additional selection.")
    temporal(record("state_access_revised", "Access under a revised rota", "State",
                    "After the shared review, the fictional team reports testing a revised key rota and a clearer route description. "
                    "Whether these arrangements remove unequal access is not established.", status="revised",
                    evidence="Synthetic corrected review summary."), "review", "unbounded", "garden")
    temporal(record("state_team_forming", "An informal team taking shape", "State",
                    "From the encounter to the review, stewardship is described as an informal arrangement with uncertain workload allocation. "
                    "Continuity with the later rota is an attributed organizational judgment."), "encounter", "review", "stewards")
    temporal(record("state_team_rotating", "Care shared through a rota", "State",
                    "The review account describes a named handover practice and rotating duties. This account preserves a proposed capacity "
                    "for continuing care while leaving sustained participation and unequal burdens open.", epistemic_mode="interpreted"),
             "review", "unbounded", "stewards")

    temporal(record("property_location", "A place beside the footpath", "Property",
                    "Within an invented site sketch, the plot is described as beside the river footpath and behind a low boundary wall. "
                    "This is a contextual geographical description. No real coordinates or actual location are represented.",
                    evidence="Synthetic inquiry brief; no surveyed map."), subject="garden")
    temporal(record("property_water", "Water suitability remains unknown", "Property",
                    "The fictional observer notes visible sediment in an informal sample. Suitability for any use is not established; "
                    "the observation must not be read as a safety assessment or a measured change.",
                    epistemic_mode="observed", status="contested",
                    attributed_to="Water cooperative observer (fictional)",
                    method="Invented visual observation; no laboratory method, calibration or field sampling occurred.",
                    evidence="Synthetic water-observations.csv.",
                    uncertainty="The start and end of applicability are both unknown; uncertainty is retained in Spacetime."),
             "unknown", "unknown", "water_coop")
    record("property_capacity", "Six proposed shared beds", "Property",
           "An undated sketch proposes six planting beds. The number describes a design proposal, not a count of constructed beds. "
           "No temporal extent is declared, so this account remains unscoped context.", modality="intended",
           evidence="Invented design note.", alternatives="Fewer larger beds, a path-only project or no cultivation.")
    temporal(record("property_burden", "Who carries the work?", "Property",
                    "At the review, residents interpret the distribution of tasks as uneven. The account preserves a normative concern "
                    "and its perspective; it is not a legal judgment or a verified quantitative inequality measure.",
                    epistemic_mode="interpreted", status="contested",
                    attributed_to="Residents' circle review participants (fictional)",
                    evidence="Synthetic review discussion; incomplete participation data."), "review", "unbounded", "stewards")

    relation("relation_inquiry", "A shared inquiry takes shape", "participates in inquiry",
             [("residents", "people raising questions"), ("stewards", "practical organizers"),
              ("garden", "place under inquiry"), ("inquiry", "bounded process")],
             "A multi-participant account relates residents, stewards, a place and an inquiry into shared care. Their roles differ. "
             "Participation does not imply agreement or complete representation.", start="encounter")
    notes(relation("relation_trial", "A provisional stewardship arrangement", "coordinates provisional access",
                   [("stewards", "organizing group"), ("garden", "place cared for"), ("water_coop", "advising participant")],
                   "The fictional trial arrangement connects practical access, care and advice. It is a first-class Relation account, "
                   "with its own temporal scope, evidence and potential history. It is not proof of ownership or a binding legal instrument.",
                   start="agreement", end="review", subject="garden", status="contested"),
          "Inspect the three participant roles and the attached memorandum. A later higher-order relation qualifies this account. "
          "The trial arrangement is retained when a revised arrangement is described.")
    relation("relation_revised", "A renewed agreement to care", "coordinates revised stewardship",
             [("stewards", "rota organizers"), ("residents", "participants in review"),
              ("garden", "place cared for"), ("water_coop", "resource adviser")],
             "The review produces a reported revised arrangement. Its participant roles and temporal scope are recorded explicitly. "
             "Continued participation and realized benefit remain questions for subsequent observation.",
             start="review", subject="garden", status="revised")
    relation("relation_materials", "Resources offered for practical care", "offers resources for",
             [("water_coop", "resource contributor"), ("stewards", "recipient and coordinator"), ("garden", "intended place of use")],
             "The cooperative reportedly offers containers and advice during the practical trial. The record distinguishes a contribution claim "
             "from a conclusion that the resources caused a successful outcome.", start="workday")
    relation("relation_qualification", "Access is more than an open gate", "qualifies an earlier account",
             [("relation_trial", "account being qualified"), ("state_access_trial", "state description under discussion"),
              ("property_burden", "related concern"), ("review", "review account")],
             "A higher-order epistemic relationship links the provisional arrangement account to a contested state description and a review concern. "
             "These incidences reference records, not an assertion that record objects are the represented institutions.",
             start="review", scope_kind="record", epistemic_mode="interpreted", status="contested")
    relation("relation_observation", "An observation with missing context", "qualifies knowledge about",
             [("observation", "reported observation"), ("property_water", "uncertain description"), ("water_coop", "attributed observer group")],
             "The reported observation and uncertain property account are retained together. Their association does not supply missing "
             "sampling time or establish the order of the observation relative to the inquiry events.",
             start="unknown", end="unknown", epistemic_mode="interpreted")
    relation("relation_alternative", "An unchosen commercial garden", "proposes an unrealized alternative",
             [("residents", "proposers in discussion"), ("garden", "possible site"), ("stewards", "possible organizers")],
             "The fictional review considered a subscription garden and did not pursue it. This account preserves an unrealized branch "
             "of the possibility field. It does not assert that a commercial arrangement existed.",
             start="unknown", end="unknown", modality="unrealized",
             alternatives="A shared inquiry with periodic review remained the stated direction.",
             conditions="Costs, unequal access and volunteer capacity were unresolved.")
    stage("scoped_accounts", "Describe state trajectories, contextual properties, structured relationships and an unrealized alternative without inferring event effects.",
          ["state_access_closed", "state_access_trial", "state_access_revised", "state_team_forming", "state_team_rotating",
           "property_location", "property_water", "property_capacity", "property_burden", "relation_inquiry", "relation_trial",
           "relation_revised", "relation_materials", "relation_qualification", "relation_observation", "relation_alternative"])

    order("withdrawn_order", "A disputed reverse chronology", "review", "encounter",
          "A fictional imported index incorrectly places the review before the encounter. This claim is retained as contested, even though "
          "it contradicts the existing order. The resulting cycle must remain inspectable until the account is revised.",
          status="contested", epistemic_mode="reported",
          evidence="Synthetic imported index; item order was mistaken for event order.")
    stage("conflicting_order", "Retain a contested chronology claim and its contradiction; do not silently discard uncomfortable evidence.",
          ["withdrawn_order"], categories=("evidence_or_interpretation",))
    stage("corrected_account", "Correct the review attendance account and withdraw the mistaken reverse order; preserve both earlier versions in Git history.",
          operations=[
              {"op": "record.update", "record_id": identifier("review"), "changes": {
                  "status": "revised",
                  "content": "At the close of the fictional spring trial, participants reviewed access, workload and water use. "
                             "A later reconciliation identifies 16 distinct attendees: two repeated ledger entries had inflated the initial count of 18. "
                             "The team reports testing a revised stewardship rota. Residents' questions about practically usable access remain open. "
                             "The correction revises the recorded account; it does not change what happened at the review.",
                  "evidence": "Synthetic review-summary.txt and attendance-ledger.csv. The prior 18-person report remains in revision history.",
                  "uncertainty": "The ledger is invented for demonstration. Within the case, duplicate removal does not establish representativeness, agreement or completeness.",
              }},
              {"op": "record.update", "record_id": identifier("withdrawn_order"), "changes": {
                  "status": "withdrawn",
                  "content": "Withdrawn: a fictional imported index was ordered by entry, not by the represented events. Its placement of the review "
                             "before the encounter is no longer relied on. The prior contradictory assertion remains in the preceding revision; "
                             "withdrawal does not delete the record or establish that every remaining claim is correct.",
                  "evidence": "Comparison of synthetic encounter notes, review references and the imported index convention.",
              }},
          ], categories=("evidence_or_interpretation",))

    attachment_inputs = [
        ("encounter_notes", "encounter", "encounter-notes.txt", "text/plain"),
        ("access_memorandum", "relation_trial", "access-memorandum.txt", "text/plain"),
        ("water_observations", "observation", "water-observations.csv", "text/csv"),
        ("review_summary", "review", "review-summary.txt", "text/plain"),
        ("attendance_ledger", "review", "attendance-ledger.csv", "text/csv"),
        ("chronology_reconciliation", "review", "chronology-reconciliation.txt", "text/plain"),
    ]
    return {
        "project": {
            "name": "River Commons — a shared garden inquiry",
            "description": "SYNTHETIC DEMO · A fictional inquiry into shared care, access and changing possibilities. "
                           "Explore 31 accounts, all six recording roles, an event partial order, subject trajectories, evidence files, "
                           "a contested chronology and a retained correction. No real people, location, institution or field observations are represented.",
        },
        "ids": ids,
        "records": deepcopy(list(records.values())),
        "stages": stages,
        "attachments": [{
            "key": key, "record_id": identifier(target),
            "file_id": str(uuid5(NAMESPACE, "attachment/" + key)),
            "filename": filename, "media_type": media_type, "path": MATERIALS / filename,
        } for key, target, filename, media_type in attachment_inputs],
        "view": {
            "subject": identifier("garden"), "focus_relation": identifier("relation_trial"),
            "focus_state": identifier("state_access_trial"), "early_event": identifier("encounter"),
            "focus_files": identifier("review"), "graph_query": "care",
            "agreement_event": identifier("agreement"), "workday_event": identifier("workday"),
            "review_event": identifier("review"), "unordered_event": identifier("observation"),
            "withdrawn_order": identifier("withdrawn_order"),
        },
    }
