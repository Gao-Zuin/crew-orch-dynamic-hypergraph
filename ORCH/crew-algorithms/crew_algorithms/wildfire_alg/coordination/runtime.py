"""Opt-in hooks around the EXISTING Embodied agent loop.

CREW_HYPERGRAPH_ARM unset: no hooks. P/SHADOW log but do not alter prompts,
delivery or actions. HA injects ephemeral evidence; HR also routes messages.
HG is reserved for explicitly labelled protocol-stress tests. HF is unsupported
because Unity observations do not expose unambiguous physical collector IDs.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import time

from .hypergraph import Coordinator
from .crew_adapter import encode_observation, SpatialPolicy, validate_low_level_action


class RuntimeBridge:
    def __init__(self, cfg, path, arm):
        if arm == "HF":
            raise ValueError("HF physical handoff is not observable in this Unity interface")
        if arm == "HG" and os.getenv("CREW_HYPERGRAPH_PROTOCOL_STRESS") != "1":
            raise ValueError("HG requires an explicitly labelled protocol-stress run")
        self.cfg, self.arm = cfg, arm
        self.session = f"{cfg.envs.timestamp}-process-{os.getpid()}"
        event_path = Path(os.environ.get("CREW_HYPERGRAPH_EVENT_PATH", str(Path(path) / "hypergraph_events.jsonl")))
        self.c = Coordinator(self.session, cfg.envs.level, int(cfg.envs.seed), arm, event_path)
        self.policy = SpatialPolicy()
        self.nominal_edges = {}
        self.step = 0
        self.pending_actions = {}
        self.recovery_feedback = {}
        self.tokens_before = (0, 0)
        self.last_validation = None
        self.global_data = None
        self.intervention = os.getenv("CREW_HYPERGRAPH_INTERVENTION", "none")
        if self.intervention not in {"none", "projector_off", "leader_shuffle"}:
            raise ValueError("Unknown topology intervention")
        self.c.emit("RUN_STARTED", {"model": cfg.envs.model_name, "max_steps": cfg.envs.max_steps,
                                   "result_path": str(Path(path).resolve()),
                                   "intervention": self.intervention,
                                   "context_profile": "task_hypergraph_reports_v5" if arm == "HT" else "compact_v5",
                                   "suite": "task_hypergraph" if arm == "HT" else "protocol_stress" if arm == "HG" else "benchmark_faithful"})

    @classmethod
    def from_environment(cls, cfg, path):
        arm = os.getenv("CREW_HYPERGRAPH_ARM")
        if arm == "HT":
            from .task_runtime import TaskRuntimeBridge
            return TaskRuntimeBridge(cfg, path)
        return cls(cfg, path, arm) if arm else None

    def observe(self, state, agents, game_data, phase):
        from crew_algorithms.wildfire_alg.core.alg_utils import get_agent_observations, check_game_done
        observed_at = time.monotonic()
        live_ids = {str(agent.id) for agent in agents}
        for missing in set(self.c.nodes) - live_ids:
            if self.c.nodes[missing]["online"]:
                self.c.offline(missing, "REMOVED_FROM_RUNTIME")
        for agent in agents:
            observation = get_agent_observations(state, agent.id)
            if observation["agent_type"] >= 4:
                self.c.offline(str(agent.id), "DESTROYED")
                continue
            self.c.observe(encode_observation(str(agent.id), observation, self.c.task_id,
                                              self.session, observed_at))
        if self.intervention == "leader_shuffle":
            # Keep the nominal policy's memory separate from intervened leaders;
            # otherwise each repeated observation would rotate the leader again.
            from types import SimpleNamespace
            nominal = SimpleNamespace(nodes=self.c.nodes, fresh=self.c.fresh, edges=self.nominal_edges)
            proposal = self.policy.predict(nominal)
            self.nominal_edges = {e["id"]: deepcopy(e) for e in proposal["edges"]}
        else:
            proposal = self.policy.predict(self.c)
        if self.intervention == "leader_shuffle":
            # Same memberships/edge sizes; rotate leader deterministically by seed.
            for edge in proposal["edges"]:
                primary = [a for a in edge["members"] if proposal["active"].get(a) == edge["id"]]
                if len(primary) > 1:
                    choices = [a for a in primary if a != edge["leader"]]
                    edge["leader"] = choices[self.c.seed % len(choices)]
        self.c.commit_topology(proposal)
        validator_data = {"rewards": game_data["rewards"], "game_data": game_data,
                          "score": game_data["score"]}
        if self.global_data is not None and "civilian_target" in self.global_data:
            validator_data["civilian_target"] = self.global_data["civilian_target"]
        success = check_game_done(validator_data, self.cfg.envs, game_data["score"])
        self.last_validation = {"timestep": self.step, "observation_phase": phase,
                                     "success": bool(success), "rewards": game_data["rewards"],
                                     "fire_active": game_data.get("fire_active"),
                                     "civilian_target": validator_data.get("civilian_target"),
                                     "validator": "core.alg_utils.check_game_done"}
        self.c.emit("TASK_VALIDATED", self.last_validation)
        return success

    def before_step(self, state, agents, game_data, step, global_data):
        self.global_data = global_data
        self.step = step
        self.runtime_agents = {str(a.id): a for a in agents}
        self.tokens_before = (global_data["input_tokens"], global_data["output_tokens"])
        self.observe(state, agents, game_data, "before_action")

    def prompt(self, agent_id, original):
        if self.arm in {"P", "SHADOW"}:
            return original
        context = "" if self.intervention == "projector_off" else (
            self.c.context(str(agent_id)) if self.arm == "HG" else
            self.c.compact_context(str(agent_id), routing=self.arm == "HR"))
        feedback = self.recovery_feedback.get(str(agent_id), "")
        return original + "\n\n" + context + ("\n[RECOVERY FEEDBACK] " + feedback if feedback else "")

    def dispatch(self, agent, content, global_data):
        """Same XML parser/history format as Embodied, with explicit delivery events."""
        global_match = re.search(r"<GLOBAL>\s*(.*?)\s*</GLOBAL>", content, re.DOTALL)
        global_msg = global_match.group(1).strip() if global_match else None
        sender = str(agent.id)
        timestep = global_data.get("time")
        failed_recipients = {}
        for recipient in global_data.get("agents", []):
            if recipient.id == agent.id:
                # Preserve original baseline self-global history behavior.
                agent.add_message("GLOBAL", f"AGENT_{agent.id}", global_msg, timestep)
                continue
            match = re.search(fr"<AGENT_{recipient.id}>\s*(.*?)\s*</AGENT_{recipient.id}>", content, re.DOTALL)
            messages = []
            if match:
                messages.append((False, match.group(1).strip()))
            if global_msg:
                messages.append((True, global_msg))
            for broadcast, msg in messages:
                def deliver(recipient=recipient, msg=msg, broadcast=broadcast):
                    recipient.add_message("GLOBAL" if broadcast else f"AGENT_{agent.id}",
                                          f"AGENT_{agent.id}", msg, timestep)
                    if not broadcast:
                        agent.add_message(f"AGENT_{recipient.id}", f"AGENT_{agent.id}", msg, timestep)
                ok, reason = self.c.send(sender, str(recipient.id), msg, deliver,
                                         enforce=self.arm in {"HR", "HG"},
                                         propagate_failure=self.arm in {"P", "SHADOW"})
                if not ok:
                    failed_recipients[str(recipient.id)] = reason
        if failed_recipients:
            feedback = "Messages not delivered: " + json.dumps(failed_recipients, sort_keys=True)
            self.recovery_feedback[sender] = feedback
            agent.add_message("GLOBAL", "ROUTING_FEEDBACK", feedback, timestep)
        # Natural-language claim extraction is deliberately NOT a truth oracle.
        # Record the raw claim stream; semantic contradiction scoring requires
        # structured assertions or manually audited spans, not a guessed regex.
        self.c.emit("COMMUNICATION_GENERATED", {"raw_output": content, "timestep": timestep}, sender)

    def action_started(self, agent, action):
        aid = f"t{self.step}-agent{agent.id}"
        snapshot = deepcopy(self.c.nodes.get(str(agent.id)))
        self.pending_actions[str(agent.id)] = (aid, list(action) if action is not None else None, snapshot)
        self.c.emit("ACTION_STARTED", {"action": action, "timestep": self.step}, str(agent.id), action_id=aid)

    def hard_notice(self, sender, event_type, payload):
        """Deliver runtime evidence to the local leader; never merely log 'sent'."""
        edge = self.c.edges.get(self.c.active.get(sender))
        leader = edge["leader"] if edge else None
        receiver = getattr(self, "runtime_agents", {}).get(leader)
        if leader == sender:
            self.c.emit("HARD_EVENT_LOCAL", {"type": event_type, **payload}, sender)
            return
        if receiver is None:
            self.c.emit("ESCALATION_UNAVAILABLE", {"type": event_type, "leader": leader}, sender)
            return
        content = "[VERIFIED RUNTIME EVENT] " + json.dumps({"type": event_type, "agent": sender, **payload})
        ok, reason = self.c.send(sender, leader, content,
            lambda: receiver.add_message("GLOBAL", "HYPERGRAPH_EVENT", content, self.step), hard_event=True)
        self.c.emit("ESCALATION_SENT" if ok else "ESCALATION_FAILED",
                    {"type": event_type, "leader": leader, "reason": reason}, sender)

    def guard(self, agent, action, retry):
        if self.arm != "HG" or action is None:
            return action
        if not self.c.fresh(str(agent.id)):
            self.c.emit("GUARD_ABSTAINED", {"reason": "stale observation"}, str(agent.id))
            return action
        snapshot = self.c.nodes[str(agent.id)]
        allowed, reason = validate_low_level_action(snapshot, action)
        if allowed:
            return action
        self.c.emit("GUARD_REJECTED", {"action": action, "reason": reason}, str(agent.id))
        self.recovery_feedback[str(agent.id)] = reason
        self.hard_notice(str(agent.id), "GUARD_REJECTED", {"reason": reason})
        recovered = retry()  # The independent LLM chooses recovery, not the graph.
        if recovered is not None and validate_low_level_action(snapshot, recovered)[0]:
            self.c.emit("RECOVERY_ACTION_SELECTED", {"action": recovered}, str(agent.id))
            return recovered
        self.c.emit("RECOVERY_RETRY_EXHAUSTED", {"action": recovered}, str(agent.id))
        return [0, *snapshot["position"]]  # Safe hold; not silently called success.

    def after_step(self, state, agents, game_data, global_data):
        self.observe(state, agents, game_data, "after_action")
        for agent, (aid, action, before) in self.pending_actions.items():
            after = self.c.nodes.get(agent)
            delta = {key: {"before": before.get(key), "after": after.get(key)}
                     for key in ("position", "resources", "facts", "online")
                     if before and after and before.get(key) != after.get(key)}
            self.c.emit("ACTION_COMPLETED", {"action": action, "verified_local_delta": delta,
                                            "note": "env.step returned; command completion is not task completion"},
                        agent, action_id=aid)
            if not delta:
                self.c.emit("ACTION_NO_EFFECT", {"action": action,
                    "observability": "no change in encoded local snapshot; global effects may be unobserved"}, agent, action_id=aid)
                intentional_hold = bool(action and before and action == [0, *before["position"]])
                if self.arm == "HG" and not intentional_hold:
                    self.hard_notice(agent, "ACTION_NO_EFFECT", {"action": action,
                        "qualification": "no local delta, not proof of no global effect"})
        self.pending_actions.clear()
        self.recovery_feedback.clear()
        self.c.emit("LLM_USAGE", {"timestep": self.step, "cumulative_api_calls": global_data["api_calls"]},
                    input_tokens=global_data["input_tokens"] - self.tokens_before[0],
                    output_tokens=global_data["output_tokens"] - self.tokens_before[1])
        self.tokens_before = (global_data["input_tokens"], global_data["output_tokens"])

    def finish(self, global_data):
        # A successful mission can exit after before_step organized, without
        # reaching after_step. Flush that call without recounting a full round.
        current = (global_data["input_tokens"], global_data["output_tokens"])
        if current != self.tokens_before:
            self.c.emit("LLM_USAGE", {"timestep": self.step,
                        "cumulative_api_calls": global_data["api_calls"], "phase": "finish"},
                        input_tokens=current[0] - self.tokens_before[0],
                        output_tokens=current[1] - self.tokens_before[1])
            self.tokens_before = current
        if self.last_validation is not None:
            self.c.emit("TASK_VALIDATED", {**self.last_validation, "observation_phase": "episode_end",
                                          "source_observation_phase": self.last_validation["observation_phase"]})
        self.c.emit("RUN_FINISHED", {"input_tokens": global_data["input_tokens"],
                                     "output_tokens": global_data["output_tokens"],
                                     "api_calls": global_data["api_calls"]})
