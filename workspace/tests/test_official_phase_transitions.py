"""Unit tests for the official ORCH phase-transition audit."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "orch_paper"))
from analyze_official_phase_transitions import (  # noqa: E402
    phase_start, simulate_add_phases_queue, transition_summary,
)


class OfficialPhaseTransitionTests(unittest.TestCase):
    def test_phase_start_stops_at_previous_phase(self):
        statuses = [
            {"timestep": 1, "phase": "refill"},
            {"timestep": 2, "phase": "move"},
            {"timestep": 3, "phase": "move"},
            {"timestep": 4, "phase": "move"},
        ]
        self.assertEqual(phase_start(statuses, 3), 2)

    def test_unfinished_add_without_resume_is_separate_from_next_phase(self):
        summary = transition_summary([
            {"reported_phase_percent": 40, "status_decision": "NEXT_PHASE",
             "old_phase_later_resumed_exactly": False},
            {"reported_phase_percent": 0, "status_decision": "ADD_PHASES",
             "old_phase_later_resumed_exactly": False,
             "new_phases_added": ["urgent"],
             "transitioned_to_newly_added_phase": False},
        ])
        self.assertEqual(summary["next_phase_while_reported_below_100"], 1)
        self.assertEqual(summary["unfinished_add_phase_never_resumed_exactly"], 1)
        self.assertEqual(summary["add_events_did_not_enter_newly_added_phase"], 1)

    def test_add_phases_appends_new_work_behind_existing_future(self):
        state = simulate_add_phases_queue("A", ["B"], ["X"])
        self.assertEqual(state, {"current_phase": "B", "future_phases": ["X"],
                                 "phase_history": ["A"]})


if __name__ == "__main__":
    unittest.main()
