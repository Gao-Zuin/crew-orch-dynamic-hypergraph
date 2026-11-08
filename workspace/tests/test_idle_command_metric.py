"""Execute the actual runner counter block without importing/starting Unity."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "ORCH/crew-algorithms/crew_algorithms/wildfire_alg/algorithms/Embodied/__main__.py"


class IdleCommandMetricTests(unittest.TestCase):
    def count(self, action, position, aboard=False):
        tree = ast.parse(SOURCE.read_text())
        block = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                     and any(isinstance(child, ast.AugAssign)
                             and isinstance(child.target, ast.Name)
                             and child.target.id == "cumulative_idle_steps"
                             for child in node.body))
        code = compile(ast.Module(body=[block], type_ignores=[]), str(SOURCE), "exec")
        values = {"action_array": action, "agent": SimpleNamespace(last_position=position),
                  "_is_helicopter_passenger": aboard, "cumulative_idle_steps": 0}
        exec(code, values)
        return values["cumulative_idle_steps"]

    def test_navigation_is_not_an_idle_command(self):
        self.assertEqual(self.count([0, 41, 59], [8, 24]), 0)

    def test_same_grid_hold_is_an_idle_command(self):
        self.assertEqual(self.count([0, 8.0, 24.0], (8, 24)), 1)

    def test_passenger_hold_is_excluded(self):
        self.assertEqual(self.count([0, 8, 24], [8, 24], aboard=True), 0)

    def test_non_movement_skill_is_excluded(self):
        self.assertEqual(self.count([3, 8, 24], [8, 24]), 0)


if __name__ == "__main__":
    unittest.main()
