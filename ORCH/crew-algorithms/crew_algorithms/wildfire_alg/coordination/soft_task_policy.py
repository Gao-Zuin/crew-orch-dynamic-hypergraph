"""LLM suggestions for task-led groups; failed suggestions never stop workers."""
import json
import re

from .soft_task_graph import PlanError
from .task_guidance import orch_knowledge_context, ORGANIZATION_GUIDANCE


SYSTEM = """Suggest a small task-led collaboration graph for CREW-Wildfire.
The graph is advice, not permission to act. Group by concrete cooperation needs,
not distance alone. Respond to reported events and requests, keep existing work visible,
and do not claim an action happened merely because it was planned or reported.
Use only observed agent IDs. Every online agent must be a member of at least one
group and assigned to exactly one active group. A group leader is one of its
members. Keep responsibilities clear; change groups when the work needs it.
Return JSON only:
Copy based_on_version from the input version and evidence_id from the input
evidence_id exactly, as integers. The zeros in the schema example are not values
to reuse unless the current input actually contains zero.
{"based_on_version": 0, "evidence_id": 0, "reason": "brief reason",
 "edges": [{"id": "stable id", "goal": "current shared goal",
 "members": ["1"], "leader": "1", "tasks": {"1": "suggested next work"},
 "advice": "optional coordination advice"}], "active": {"1": "stable id"}}
You receive the initial mission, a capability/availability roster, official environment
event notices, and leader reports. Official notices arrive directly from the environment
after its event step returns; they do not require a worker to discover or relay them.
Use their announced changes and new objectives when reviewing responsibility and
priorities. Update group goals, member tasks and advice to communicate your decision.
Workers receive these notices via the center before their next action round.
An announced fire location is not a live fire-front map or proof of suppression;
use field reports for its current extent, access conditions and response outcomes.
The roster is runtime availability metadata, not a stream of local observations.
Only official notices and field reports supply new world facts; positions, resources
and obstacles outside an official notice require field reports. Do not
invent them or infer them from audit evidence IDs. Consider the leaders' local
analysis and requested help. Keep useful work going; restructuring is optional.
A worker may belong to multiple groups to bridge real cooperation, while retaining
exactly one active assignment. Do not add overlapping membership without a task reason.
Do not add execution-permission, approval, receipt or resolution state machines.
""" + "\n" + ORGANIZATION_GUIDANCE


class SoftTaskPolicy:
    def __init__(self, model, url, api_key, emit, transport=None, static_context=None):
        self.model, self.url, self.api_key, self.emit = model, url, api_key, emit
        self.transport = transport
        self.client = None
        self.static_context = static_context if static_context is not None else orch_knowledge_context()

    def _call(self, messages, global_data):
        self.emit("TASK_ORGANIZER_REQUEST", {"messages": messages})
        if self.transport:
            content, usage = self.transport(messages)
        else:
            from openai import OpenAI
            if self.client is None:
                self.client = OpenAI(api_key=self.api_key, base_url=self.url, timeout=90, max_retries=1)
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0,
                response_format={"type": "json_object"}, max_tokens=4096,
                **({"extra_body": {"thinking": {"type": "disabled"}}} if self.model.startswith(("deepseek-flash", "deepseek-v4-pro")) else {}))
            from ..core.token_guard import record_api_usage
            record_api_usage(response)
            content, usage = response.choices[0].message.content, response.usage
        inp = usage["prompt_tokens"] if isinstance(usage, dict) else usage.prompt_tokens
        out = usage["completion_tokens"] if isinstance(usage, dict) else usage.completion_tokens
        global_data["api_calls"] += 1
        global_data["input_tokens"] += inp
        global_data["output_tokens"] += out
        self.emit("TASK_ORGANIZER_RESPONSE", {"content": content,
                  "input_tokens": inp, "output_tokens": out})
        return content

    def close(self):
        if self.client is not None:
            self.client.close()

    def decide(self, graph, global_data):
        if not graph.live_agents():
            graph.ensure_fallback()
            return True
        if not graph.needs_plan():
            return True
        state = graph.decision_state()
        local_alert = any(n.get("event", {}).get("action") == "fire_alert"
                          for n in state.get("environment_notices", []))
        local_instruction = (
            "\nA fire_alert gives no location. The center must obtain coordinates from "
            "worker reports; do not infer them from event IDs, prior seeds, or the "
            "static task design. A nearby worker may receive a private coordinate "
            "cue, but that cue is not proof of active fire.\n") if local_alert else ""
        messages = [{"role": "system", "content": SYSTEM + local_instruction + "\n\n" + self.static_context},
                    {"role": "user", "content": json.dumps(state, ensure_ascii=False)}]
        if graph.fixed_groups and graph.version > 0:
            messages.insert(1, {"role": "system", "content":
                "This experiment freezes existing group IDs, members, leaders, and active "
                "assignments. Preserve those fields exactly. You may update each group's "
                "goal, member tasks, and advice using the latest world evidence. Do not "
                "create or retire a group. An external registered intervention, if any, "
                "changes only membership before this call."})
        try:
            content = self._call(messages, global_data)
            proposal = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip()))
            graph.apply(proposal)
            return True
        except (ValueError, TypeError, KeyError, PlanError) as exc:
            self.emit("TASK_PROPOSAL_REJECTED", {"reason": str(exc)[:300]})
            return False
