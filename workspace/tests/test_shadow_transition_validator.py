"""Tests for the non-blocking transition shadow validator."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "orch_paper"))
from shadow_transition_validator import (  # noqa: E402
    complete_active, interrupt, local_labels, official_labels,
)


class ShadowTransitionValidatorTests(unittest.TestCase):
    def test_incomplete_add_is_preserved_not_hard_blocked(self):
        labels = official_labels({"status_decision": "ADD_PHASES",
                                  "reported_phase_percent": 40})
        self.assertEqual(labels, ["PRESERVE_CURRENT_AND_INSERT_INTERRUPT"])

    def test_capability_and_interrupt_labels_can_overlap(self):
        labels = official_labels({"status_decision": "ADD_PHASES",
                                  "reported_phase_percent": 0,
                                  "out_of_domain_new_phases": ["hack server"]})
        self.assertEqual(labels, ["FILTER_UNSUPPORTED_GENERATED_PHASES",
                                  "PRESERVE_CURRENT_AND_INSERT_INTERRUPT"])

    def test_interrupt_resumes_old_work_before_future(self):
        state = {"active": "A", "future": ["B"], "suspended": []}
        interrupted = interrupt(state, "X")
        self.assertEqual(interrupted, {"active": "X", "future": ["B"],
                                       "suspended": ["A"]})
        self.assertEqual(complete_active(interrupted),
                         {"active": "A", "future": ["B"], "suspended": []})

    def test_local_sequence_uses_environment_evidence(self):
        self.assertEqual(local_labels({"prerequisite_state_at_assignment":
                                      "INFEASIBLE_POSITIVE_TANK_TOP_UP",
                                      "downstream_action_before_refill_evidence_steps": [3],
                                      "downstream_action_after_refill_steps": []}),
                         ["INFEASIBLE_TOP_UP_DEPARTED_WITH_USABLE_WATER"])


if __name__ == "__main__":
    unittest.main()
