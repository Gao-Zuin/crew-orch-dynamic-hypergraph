"""Ensure serial cases retain native engine errors after shared logs change."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dynamic_followup_batch import capture_unity_logs
import dynamic_followup_batch


class NativeLogCaptureTests(unittest.TestCase):
    def test_explicit_build_is_linked_and_recorded_with_its_hash(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            for directory in ("scripts", "tests", "ORCH/crew-algorithms", "build", ".conda/crew-orch"):
                (source / directory).mkdir(parents=True)
            (source / "build/rootless_nakama_redirect.so").write_bytes(b"test-only placeholder")
            selected = root / "independent_build"
            assembly = selected / "Unity_Data/Managed/Assembly-CSharp.dll"
            assembly.parent.mkdir(parents=True)
            assembly.write_bytes(b"independent managed artifact")
            (selected / "Unity.x86_64").write_bytes(b"test executable placeholder")
            output = root / "batch"
            case = dynamic_followup_batch.CASES[1]
            with patch.object(dynamic_followup_batch, "ROOT", source):
                dynamic_followup_batch.prepare(output, [case], selected)
            plan = json.loads((output / "plan.json").read_text())
            self.assertEqual(plan["build"], str(selected.resolve()))
            self.assertEqual(plan["assembly_sha256"], hashlib.sha256(assembly.read_bytes()).hexdigest())
            linked = output / "workspace/ORCH/crew-dojo/Builds/Wildfire-StandaloneLinux64-Server"
            self.assertEqual(linked.resolve(), selected.resolve())
            self.assertEqual([c["id"] for c in plan["cases"]], [case[0]])

    def test_next_case_cannot_overwrite_captured_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "workspace/ORCH/UnityLogs/Player-0.log"
            source.parent.mkdir(parents=True)
            original = "fire start True\nNullReferenceException: visual missing\n  at MapManager.SprayWater\n"
            source.write_text(original)
            result = capture_unity_logs(root / "workspace", root / "case")
            self.assertEqual(result["exception_count"], 1)
            source.write_text("next case started\n")
            self.assertEqual((root / "case/unity_logs/Player-0.log").read_text(), original)
            self.assertTrue(result["logs_available"])


if __name__ == "__main__":
    unittest.main()
