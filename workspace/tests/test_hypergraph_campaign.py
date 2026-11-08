"""Offline checks for frozen order, partial-data accounting and paired analysis."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hypergraph_campaign import case_plan, summarize_case, analyze, is_static_build_file
from audit_hypergraph_run import audit

ROOT = Path(__file__).resolve().parents[1]


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((ROOT / "research/hypergraph_v1/spec.json").read_text())

    def test_frozen_case_order_is_balanced_and_paired(self):
        cases = case_plan(self.spec)
        self.assertEqual(len(cases), 16)
        self.assertEqual(len({c["case_id"] for c in cases}), 16)
        for offset in range(4):
            self.assertEqual({cases[4 * i + offset]["id"] for i in range(4)},
                             {a["id"] for a in self.spec["arms"]})
        for task in self.spec["task_seed_pairs"]:
            paired = [c for c in cases if c["level"] == task["level"] and c["seed"] == task["seed"]]
            self.assertEqual(len(paired), 4)
            self.assertEqual({c["max_steps"] for c in paired}, {task["max_steps"]})

    def test_missing_case_not_reported_as_measured_success(self):
        case = case_plan(self.spec)[0]
        with tempfile.TemporaryDirectory() as directory:
            row = summarize_case(case, Path(directory))
            self.assertFalse(row["terminal"])
            self.assertIsNone(row["task_success"])
            self.assertIsNone(row["final_goal_fraction"])
            self.assertFalse(row["usage_complete"])

    def test_partial_trace_kept_with_observed_token_lower_bound(self):
        case = case_plan(self.spec)[0]
        events = [dict(event_type="TASK_VALIDATED", payload={"observation_phase": "before_action", "success": False,
                                                            "rewards": [0] * 13}),
                  dict(event_type="LLM_USAGE", input_tokens=10, output_tokens=2)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
            (path / "status.json").write_text(json.dumps(dict(terminal=True, error="timeout", audit_passed=False)))
            row = summarize_case(case, path)
            self.assertTrue(row["terminal"])
            self.assertEqual(row["total_tokens"], 12)
            self.assertEqual(row["error"], "timeout")
            self.assertFalse(row["usage_complete"])
            self.assertIsNone(row["task_success"])

    def test_final_post_action_success_not_lost(self):
        case = case_plan(self.spec)[0]
        rewards = [0] * 13
        rewards[8] = 2
        events = [dict(event_type="TASK_VALIDATED", payload={"observation_phase": "after_action", "success": True,
                                                            "rewards": rewards}),
                  dict(event_type="RUN_FINISHED", payload={})]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
            (path / "status.json").write_text(json.dumps(dict(terminal=True, audit_passed=True)))
            row = summarize_case(case, path)
            self.assertTrue(row["task_success"])
            self.assertEqual(row["final_goal_fraction"], 1)

    def test_intention_to_evaluate_retains_all_missing_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            manifest = {"spec": self.spec, "cases": case_plan(self.spec)}
            (path / "manifest.json").write_text(json.dumps(manifest))
            report = analyze(path)
            self.assertEqual(report["planned_cases"], 16)
            self.assertEqual(report["terminal_cases"], 0)
            self.assertEqual(len(report["paired"]), 12)
            self.assertTrue(all(p["differences"]["task_success"] is None for p in report["paired"]))

    def test_real_gate_artifact_auditor(self):
        # Retained development artifacts provide a regression fixture, if present.
        path = ROOT / "benchmark_runs/hypergraph_gate_v4/P_scout/events.jsonl"
        if not path.exists():
            self.skipTest("historical gate not installed")
        self.assertTrue(audit(path)["passed"])
        with tempfile.TemporaryDirectory() as directory:
            events = [json.loads(line) for line in path.read_text().splitlines()]
            events = [e for e in events if e["event_type"] != "MESSAGE_DELIVERED"]
            broken = Path(directory) / "broken.jsonl"
            broken.write_text("\n".join(json.dumps(e) for e in events))
            self.assertFalse(audit(broken)["passed"])

    def test_runtime_timer_not_frozen_as_build_code(self):
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
            timer = build / "Unity_Data/ML-Agents/Timers/Wildfire_timers.json"
            timer.parent.mkdir(parents=True)
            timer.write_text("{}")
            code = build / "Unity_Data/Managed/Assembly-CSharp.dll"
            code.parent.mkdir(parents=True)
            code.write_bytes(b"code")
            config = build / "Unity_Data/StreamingAssets/config.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}")
            self.assertFalse(is_static_build_file(timer, build))
            self.assertTrue(is_static_build_file(code, build))
            self.assertTrue(is_static_build_file(config, build))

    def test_dynamic_fire_has_no_fabricated_progress_denominator(self):
        case = {**case_plan(self.spec)[0], "target_reward_index": None, "target_units": None}
        events = [dict(event_type="TASK_VALIDATED", payload={"observation_phase": phase,
                  "success": False, "rewards": [0] * 13})
                  for phase in ("before_action", "after_action")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
            row = summarize_case(case, path)
            self.assertIsNone(row["final_goal_fraction"])
            self.assertIsNone(row["goal_fraction_auc_observed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
