"""LLM organization controller: mission-driven membership, review and changes."""
import json
import re
import time

from .task_hypergraph import ProposalError, require


SYSTEM = """You organize an embodied CREW-Wildfire mission using TASK-STAGE HYPEREDGES.
You are a control-plane planner, not an extra embodied worker. Do not partition
by geography alone. Create cooperation units from goals, prerequisite tasks,
capabilities, resources and concrete interdependencies. Choose a worker leader
for each edge and explain why its members must cooperate. Different edges can
operate concurrently. A worker can belong to multiple edges (bridge/liaison),
but assign exactly ONE execution_edge per live worker for its physical action.
Other memberships provide context and explicit cross-edge coordination only.
Each edge is ONE current cooperative substage with a meaningful exit, not a
whole serial mission packed into a member's instruction. Keep later substages
as pending responsibilities, then create successors when the current substage
actually finishes. Do not add unnecessary support edges or future objectives.

Every call: inspect the latest world and every current edge's checks; judge each
check separately, cite supplied event IDs, distinguish observed facts from
messages/intentions, and review each old edge exactly once. Numeric predicate
verdicts must match the supplied exact results. Semantic checks must be unknown
when evidence is insufficient. Do not declare work done because messages say so.
An exact check's description must state ONLY the condition its fields actually
evaluate. Never describe "A OR B" with one position/resource/reward predicate;
the schema cannot evaluate that disjunction. In particular, once workers have
left a water source, "near water" is NOT a check for progressing toward a fire.
Revise the edge's checks to its current stage destination (or use a semantic
check whose verdict stays unknown until supported) rather than treating a
false origin-position predicate as a completed staging milestone.
The field unacknowledged_events lists NEW commands/announcements since the last
accepted graph. Address each one explicitly. A command is evidence of an
injected event, not proof of its physical effect; use the current world snapshot
to judge effects. Assign an affected live edge and a concrete worker instruction
for each event. New fire at a known coordinate must be considered alongside
existing fire, with responsibilities updated or a reasoned defer decision.
A replan for start_fire must assign at least one ACTIVE execution owner whose
member task explicitly names the new x,y coordinates. A waiting future edge
alone is not a response. Keep agents on old fire work where feasible.
If you create a NEW edge for that fire, at least one agent must execute in it
NOW; a future-only response edge is not sufficient.
For known-fire suppression, retain at least one ACTIVE task naming the original
fire coordinates too, while fire_active remains true; the shared map cannot
prove a particular local fire is out.
While fire_active remains true, keep an ACTIVE execution owner for every
announced fire in event_commands_and_announcements on EACH later revision.
Cross-edge links are directed messages between DISTINCT agents. A leaders link
is unusable if both edge leaders are the same worker; use a shared-agent link
from the liaison's active edge to an edge with another recipient instead.
For two-way exchange, provide TWO links with opposite source/target directions
and a distinct receiving worker on each route. A one-way link must not be
described as a two-way exchange.
In EVERY old-edge review and EVERY check result put world.evidence_id in its
evidence list. To keep an edge unchanged, copy its fields exactly and use
'continue'; if you change goal, members, leader, tasks, rules, communication,
checks or dependencies, use 'revise'. You may update historical context without
claiming that its old summary is a fresh observation.

Represent a stage transition by retiring its old edge and creating successor
edge(s) with new IDs, new goals/context and explicit handoffs. For ongoing work
keep IDs stable; membership/rules/task changes require 'revise'. No silent drops
of unfinished work. Copy every pending obligation into successors unless it is
explicitly resolved with evidence. Pass essential context in handoffs. Completed
edge IDs are immutable. 'abort' means work not completed, never success.
If the old edge's checks do not cover part of its stated goal (for example,
"position crew" with only observation checks), do not mark it complete on
those checks alone. Either keep its stage and revise tasks/checks, or retire
it as 'revise' with all unfinished parts transferred to successor edges.
Do not blindly preserve an impossible phase: revise the plan while retaining
hard safety/resource rules and unfulfilled mission responsibilities.

Only use supplied worker IDs. No virtual managers, no invented workers. Include
all live workers, using an explicit standby/support edge if necessary. Exclude
offline members, replace a lost leader, and transfer their unfinished work.
Keep the organization as small as actual dependencies allow. For one known fire
with equivalent firefighters, one cooperation edge can include all of them with
different responsibilities. Do not force scouting, water and standby edges
without a task reason. A known fire location does not require two-agent scouting
confirmation unless that is the mission objective.
Dependencies may reference completed predecessors OR another current edge.
An edge waiting for a predecessor cannot execute physical actions until that
predecessor has a completed review and retires. Include future cooperation
units when helpful, assigning waiting workers to their own waiting edge.
The same carrier may belong to current and future edges but executes only the
current one. Dependency graph must be acyclic. Preserve waiting responsibilities.

Output ONLY a JSON object with these fields:
{
 "based_on_version": <input graph_version>, "evidence_id": <world.evidence_id>,
 "reason": "reason for organization/changes",
 "reviews": [{"edge_id":"old id", "verdict":"continue|revise|complete|abort|blocked",
   "reason":"...", "evidence":[event_id],
   "checks":[{"id":"old check id", "verdict":"met|unmet|unknown", "evidence":[event_id]}]}],
 "edges": [{"id":"stable unique task-stage id", "stage":"stage name", "goal":"concrete goal",
   "reason":"why these capabilities/members cooperate", "members":["1","2"],
   "leader":"1", "tasks":{"1":"specific responsibility", "2":"specific responsibility"},
   "rules":["applicable hard rules and execution constraints"],
   "communication":"all_to_all|leader_star",
   "context":{"summary":"current facts vs hypotheses", "pending":["unfinished responsibility"]},
   "checks":[{"id":"c1", "description":"testable completion condition", "kind":"semantic"}],
   "depends_on":[]}],
 "active":{"1":"edge id","2":"edge id"},
 "links":[{"source":"edge id","target":"edge id","mode":"leaders|shared",
   "shared_agent":"only for shared mode", "rule":"what information/coordination must cross"}],
 "handoffs":[{"source":"retired edge id","target":"successor edge id",
   "context":"facts, prior progress and unfinished coordination", "pending":["obligation copied into target"]}],
 "event_acknowledgements":[{"command":<exact object from unacknowledged_events>,
   "decision":"replan|defer", "reason":"effect observed or still uncertain",
   "instruction":"concrete instruction passed to affected workers",
   "affected_edges":["live edge id"], "evidence":[<world.evidence_id>]}],
 "resolved":[{"edge_id":"old edge", "obligation":"exact old pending text",
   "reason":"how completed/invalidated", "evidence":[event_id]}]
}
Additional check kinds for observable comparisons:
reward: {id,description,kind:'reward',field:0..12,op:'eq|ge|le',value:number}
resource: {id,description,kind:'resource',subject:'worker id',field:'water|firefighters_carried|civilian_carried',op:'eq|ge|le',value:number}
position: {id,description,kind:'position',subject:'worker id',op:'near',value:[x,y],radius:number}
fact: {id,description,kind:'fact',subject:'worker id',field:'in_helicopter',op:'eq',value:true|false}
world: {id,description,kind:'world',field:'fire_active|fire_has_been_observed',op:'eq',value:true|false}
For all/any members replace subject with subjects:['1','2',...],quantifier:'all|any'.
Never describe 'all members' while checking only one subject. For transport,
use delivered reward counter when checking actual delivery, NOT passenger or
carrier position alone. Position can match while passengers remain aboard.
Prefer observable checks when mission criteria expose counters, resource levels
or destinations. Use semantic checks for conditions not observable through those
fields. A map memory cell is NOT guaranteed current visibility. Unknown is not
safe and is not success. If hazard changes invalidate a route, replace the edge's
task immediately; old membership does not authorize continuing an unsafe plan.
Reward indices: 0 exploration,1 trees burned,2 total trees cut,3 extinguished,
4 correct target clearing score,5 civilians rescued,6 firefighters transported,
7 civilians scouted,8 fire scouted,9 water scouted,10 agents destroyed,
11 civilians destroyed,12 buildings destroyed.
For scouting, reward[8] counts agents seeing fire concurrently NOW; >=2
verifies the mission's simultaneous confirmation. fire_active only establishes
that fire exists somewhere, not that an agent knows its location.
When separate edges tackle separate fires, global reward[3] and fire_active
cannot prove that ONE specific fire was suppressed. Give each local edge a
semantic completion check for its own fire; keep its verdict unknown until
direct local evidence supports it. Global fire_active=false can check the
combined mission, not either local team's achievement by itself.
If local fire status is unavailable, a valid simpler organization is one
ongoing all-fires edge: revise specific member tasks so groups respond to old
and new coordinates, and retain global checks for the COMBINED goal. Do not
change the existing edge's stage name or erase exact pending obligations just
to reassign its members; update tasks/context and acknowledge the new event.
Initial proposal has reviews=[], links/handoffs/resolved may be [].
If unacknowledged_events is empty, event_acknowledgements=[]. Otherwise include
one acknowledgement per exact event object; omitted events reject the proposal.
An initial proposal MUST have handoffs=[] and resolved=[] because no old edge
has retired. Later, add a handoff only when removing an old edge and creating
a successor. For fire suppression, fire_active=false can hold before ignition;
require evidence that fire began, such as trees_burned reward[1]>=1, before
calling suppression complete.
"""

REVIEW_SYSTEM = """Independently review the proposed CREW-Wildfire task graph.
Use the supplied mission, current world, old graph, exact_checks and event
reports. Reject only a concrete contradiction: a mission duty is lost, an
action is impossible under observed capability/resource/capacity, a hard safety
rule is broken, an edge completion is claimed without evidence, a check's scope
does not match its stated goal, or a new event is ignored. Name the edge and
the specific supplied fact for each issue. If none, accept.

The proposal is a plan for FUTURE work. Formation does not require its checks
to be met now or future success to be guaranteed. Exploring, approaching a
reported hazard, and refilling are valid actions without a guaranteed route or
backup. Do not infer travel consumes water, new water sources are required,
or a fixed number of agents is insufficient without supplied evidence.
Helicopter capacity is 5; carried passengers are not delivered passengers.
Within-edge all_to_all works without links. A link is directed. Waiting edges,
overlap, and standby are valid; handoffs occur only when an old edge retires.

An injected fire command is a report, not proof of its physical effect. It
must still be acknowledged with affected workers instructed to investigate or
respond. Global reward[3] and fire_active cannot certify that one PARTICULAR
fire was extinguished when two fires exist. A local semantic check is valid
while the edge is active; it stays unknown until local evidence supports it.
Do not reject a local team because exact per-fire telemetry is unavailable.
One combined all-fires edge with different member duties for each fire and
global completion checks is also valid. Accept it when it preserves both
incident responsibilities and makes no local completion claim from global
metrics. For that COMBINED goal, fire_active=false after ignition is exact
evidence that every active fire is gone; do not demand per-fire attribution.
Follow world.mission_rules.validator_success_rule. For game_type 3 or 5 the
validator requires ALL active fires to end, so a reported second fire is part
of the mission even if the initial task sentence names only the first fire.
Investigating a reported coordinate is appropriate before direct observation.
Reward[8]>=2 verifies simultaneous scouting only when that is the mission.

Return ONLY JSON {"accepted":true|false,"issues":["specific factual issue"],
"edge_reviews":[{"edge_id":"each candidate edge","accepted":true|false,
"reason":"short evidence-based judgment"}]}. Review every candidate edge.
Use at most five distinct issues. If accepted, issues must be [].
"""


class LLMTaskPolicy:
    def __init__(self, model, url, api_key, emit, transport=None):
        self.model, self.url, self.api_key, self.emit = model, url, api_key, emit
        self.transport = transport
        self.client = None

    def _call(self, messages, global_data, role):
        self.emit(f"TASK_{role}_REQUEST", {"messages": messages})
        if self.transport:
            content, usage = self.transport(messages)
        else:
            from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError
            if self.client is None:
                self.client = OpenAI(api_key=self.api_key, base_url=self.url, timeout=90, max_retries=1)
            for attempt in range(3):
                try:
                    response = self.client.chat.completions.create(model=self.model, messages=messages,
                        temperature=0, response_format={"type": "json_object"}, max_tokens=8192)
                    break
                except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
                    self.emit("TASK_MODEL_CALL_FAILED", {"role": role, "attempt": attempt,
                              "exception_type": type(exc).__name__, "cause_type": type(exc.__cause__).__name__})
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
            content, usage = response.choices[0].message.content, response.usage
        if isinstance(usage, dict):
            input_tokens, output_tokens = usage["prompt_tokens"], usage["completion_tokens"]
        else:
            input_tokens, output_tokens = usage.prompt_tokens, usage.completion_tokens
        global_data["api_calls"] += 1
        global_data["input_tokens"] += input_tokens
        global_data["output_tokens"] += output_tokens
        self.emit(f"TASK_{role}_RESPONSE", {"content": content, "input_tokens": input_tokens,
                                         "output_tokens": output_tokens})
        return content

    def close(self):
        if self.client is not None:
            self.client.close()

    def _normalize_change_labels(self, graph, proposal):
        """Correct a review enum when the same LLM supplied revised edge fields.

        The task and every changed field remain the model's proposal.  The
        independent verifier sees the corrected proposal before commitment.
        """
        candidates = {e.get("id"): e for e in proposal.get("edges", []) if isinstance(e, dict)}
        tracked = ("stage", "goal", "members", "leader", "tasks", "rules",
                   "communication", "checks", "depends_on")
        for review in proposal.get("reviews", []):
            eid = review.get("edge_id")
            if review.get("verdict") != "continue" or eid not in graph.edges or eid not in candidates:
                continue
            changed = [key for key in tracked if candidates[eid].get(key) != graph.edges[eid].get(key)]
            if changed and "stage" not in changed:
                review["verdict"] = "revise"
                self.emit("TASK_REVIEW_LABEL_NORMALIZED", {"edge_id": eid, "from": "continue",
                                                            "to": "revise", "changed_fields": changed})

    def _preserve_retained_obligations(self, graph, proposal):
        """Keep old pending duties on an edge unless the LLM resolved them."""
        candidates = {e.get("id"): e for e in proposal.get("edges", []) if isinstance(e, dict)}
        resolved = {(r.get("edge_id"), r.get("obligation")) for r in proposal.get("resolved", [])
                    if isinstance(r, dict)}
        for eid, old in graph.edges.items():
            if eid not in candidates:
                continue
            context = candidates[eid].get("context")
            if not isinstance(context, dict) or not isinstance(context.get("pending"), list):
                continue
            missing = [obligation for obligation in old["context"]["pending"]
                       if obligation not in context["pending"] and (eid, obligation) not in resolved]
            if missing:
                context["pending"].extend(missing)
                self.emit("TASK_PENDING_NORMALIZED", {"edge_id": eid, "obligations": missing})

    def _preserve_handoff_obligations(self, graph, proposal):
        """Conservatively attach omitted duties to model-selected successors."""
        candidates = {e.get("id"): e for e in proposal.get("edges", []) if isinstance(e, dict)}
        handoffs = proposal.get("handoffs", [])
        if not isinstance(handoffs, list):
            return
        resolved = {(r.get("edge_id"), r.get("obligation")) for r in proposal.get("resolved", [])
                    if isinstance(r, dict)}
        for eid, old in graph.edges.items():
            if eid in candidates:
                continue
            receivers = [h for h in handoffs if isinstance(h, dict) and h.get("source") == eid and
                         h.get("target") in candidates and isinstance(h.get("pending"), list)]
            if not receivers:
                continue
            missing = [duty for duty in old["context"]["pending"]
                       if (eid, duty) not in resolved and not any(duty in h["pending"] for h in receivers)]
            if missing:
                for handoff in receivers:
                    handoff["pending"].extend(missing)
                self.emit("TASK_HANDOFF_PENDING_NORMALIZED", {"source": eid,
                    "targets": [h["target"] for h in receivers], "obligations": missing})
            for handoff in receivers:
                context = candidates[handoff["target"]].get("context")
                if not isinstance(context, dict) or not isinstance(context.get("pending"), list):
                    continue
                absent = [duty for duty in handoff["pending"] if duty not in context["pending"]]
                if absent:
                    context["pending"].extend(absent)
                    self.emit("TASK_HANDOFF_RECEIVER_NORMALIZED", {"source": eid,
                        "target": handoff["target"], "obligations": absent})

    def _ground_exact_check_verdicts(self, graph, proposal):
        """Bind model check judgments to the current authoritative snapshot."""
        for review in proposal.get("reviews", []):
            old = graph.edges.get(review.get("edge_id"))
            if old is None or not isinstance(review.get("checks"), list):
                continue
            by_id = {item.get("id"): item for item in review["checks"] if isinstance(item, dict)}
            for check in old["checks"]:
                if check["kind"] == "semantic" or check["id"] not in by_id:
                    continue
                result = by_id[check["id"]]
                exact = graph.evaluate(check)
                expected = "unknown" if exact is None else "met" if exact else "unmet"
                refs = result.get("evidence")
                if not isinstance(refs, list):
                    refs = []
                current = graph.world["evidence_id"]
                new_refs = refs if current in refs else refs + [current]
                if result.get("verdict") != expected or new_refs != refs:
                    self.emit("TASK_EXACT_CHECK_NORMALIZED", {"edge_id": review["edge_id"],
                        "check_id": check["id"], "prior_verdict": result.get("verdict"),
                        "verdict": expected, "prior_evidence": refs, "evidence": new_refs})
                    result["verdict"] = expected
                    result["evidence"] = new_refs

    def decide(self, graph, global_data):
        state = graph.decision_state()
        state["exact_checks"] = {eid: {c["id"]: graph.evaluate(c) for c in e["checks"]}
                                  for eid, e in graph.edges.items()}
        base_messages = [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": json.dumps(state, ensure_ascii=False)}]
        messages = base_messages
        prior_errors = []
        # New external events may require a full split/handoff rather than a
        # routine edit, so allow two more atomic schema repairs at that boundary.
        attempts = 8 if graph.unacknowledged_events() else 3
        for attempt in range(attempts):
            content = self._call(messages, global_data, "ORGANIZER")
            try:
                proposal = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip()))
                self._preserve_retained_obligations(graph, proposal)
                self._preserve_handoff_obligations(graph, proposal)
                self._normalize_change_labels(graph, proposal)
                self._ground_exact_check_verdicts(graph, proposal)
                graph.validate(proposal)
                review_messages = [{"role": "system", "content": REVIEW_SYSTEM},
                                   {"role": "user", "content": json.dumps({"state": state, "proposal": proposal}, ensure_ascii=False)}]
                review_content = self._call(review_messages, global_data, "VERIFIER")
                review = json.loads(review_content)
                by_edge = {r["edge_id"]: r for r in review["edge_reviews"]}
                candidate_ids = {e["id"] for e in proposal["edges"]}
                require(candidate_ids <= set(by_edge) and
                        len(by_edge) == len(review["edge_reviews"]), "verifier must review all candidate edges")
                if set(by_edge) - candidate_ids:
                    self.emit("TASK_VERIFIER_EXTRA_REVIEWS_IGNORED",
                              {"retired_or_other_edge_ids": sorted(set(by_edge) - candidate_ids)})
                verified = (review.get("accepted") is True and review.get("issues") == [] and
                            all(by_edge[eid].get("accepted") is True for eid in candidate_ids))
                exact_completion_only = all(
                    r.get("verdict") in {"continue", "revise", "blocked"} or
                    (r.get("verdict") == "complete" and
                     all(check["kind"] != "semantic" for check in graph.edges[r["edge_id"]]["checks"]))
                    for r in proposal["reviews"])
                urgent_replan = (exact_completion_only and
                                 ((any(event.get("action") == "start_fire" for event in graph.unacknowledged_events()) and
                                   any(a.get("decision") == "replan" for a in proposal.get("event_acknowledgements", []))) or
                                  bool(graph.ongoing_fire_events())))
                if not verified and urgent_replan:
                    self.emit("TASK_VERIFIER_ADVISORY_REJECTION", {"issues": review.get("issues"),
                        "candidate_edge_ids": sorted(candidate_ids),
                        "reason": "ongoing fire plan passed structural duties; any completed old edge has only currently met exact checks and conserved pending duties"})
                else:
                    require(verified, "Independent LLM verifier rejected: " + json.dumps(review.get("issues")))
                graph.apply(proposal)
                return True
            except (ValueError, TypeError, KeyError) as exc:
                self.emit("TASK_PROPOSAL_REJECTED", {"reason": str(exc), "attempt": attempt})
                repair = str(exc)
                if "new stage must use successor" in repair:
                    repair += " Keep old stage if retaining its ID, or retire it and create a NEW ID with a handoff."
                elif "duplicate directed link" in repair:
                    repair += " Keep only one link per ordered (source,target) pair."
                elif "receiver must accept handoff obligations" in repair:
                    repair += " Copy each handoff.pending string EXACTLY into its target edge context.pending."
                elif "retirement must transfer all pending" in repair:
                    repair += " Copy every unresolved old context.pending string EXACTLY into successor handoff.pending and target context.pending."
                elif "predicate needs current world evidence" in repair:
                    repair += f" Include world.evidence_id={graph.world['evidence_id']} in EVERY numeric predicate check evidence."
                elif "new fire needs an active execution owner" in repair:
                    repair += " Assign an agent NOW to an affected edge, and put the new x,y coordinates in that agent's task. A waiting edge alone cannot respond."
                elif "new fire cooperation edge must have an active owner" in repair:
                    repair += " Assign at least one agent's physical execution_edge to the new-fire edge NOW, or handle both fires in a revised existing active edge."
                elif "new/ongoing fire needs an active execution owner" in repair:
                    repair += " Keep a current physical owner whose task names this fire's x,y coordinates while fire_active remains true."
                elif "cross-edge link has no distinct receiver" in repair:
                    repair += " A leader cannot message itself. Use a shared-agent link from the liaison's active edge toward an edge with a DIFFERENT receiving member, or omit the unused link."
                elif "exact check description cannot claim an unmodeled OR alternative" in repair:
                    repair += " A single exact predicate cannot test alternatives. Describe only its actual field/op/value, or use separate checks/semantic evidence; stage position checks should target the destination, not an origin already left."
                elif "bridge must belong to both edges" in repair:
                    repair += " The shared_agent MUST appear in both source.members and target.members. Otherwise use a leaders link with distinct leader IDs, or omit the link."
                elif "Independent LLM verifier rejected" in repair and any(
                        r.get("verdict") == "complete" for r in proposal.get("reviews", [])):
                    repair += " If stage completion is uncertain, retire the old edge with verdict='revise', create successor edge IDs, and hand off EVERY unresolved pending duty; do not claim 'complete'."
                elif "only by scouting" in repair or "only observed" in repair:
                    repair += " Assign current responders to investigate AND suppress the new incident if confirmed; a combined all-fires edge may use global fire_active=false as its completion check."
                prior_errors.append(repair[:1400])
                messages = base_messages + [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": "The latest proposal was rejected atomically. Correct these issues: " +
                     json.dumps(prior_errors[-5:], ensure_ascii=False) +
                     ". Return a corrected FULL JSON proposal, not a patch. Re-read the CURRENT world and unacknowledged_events."}]
        return False
