"""Execute the real IL repair on a runnable fixture, including failure paths."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CECIL = Path("/usr/lib/mono/gac/Mono.Cecil/0.11.0.0__0738eb9f132ed756/Mono.Cecil.dll")
TOOL = ROOT / "research/dynamic_followup/GuardSprayVisual.cs"
FIXTURE = '''
using System;
namespace UnityEngine {
    public class Object {
        public bool Destroyed;
        public static implicit operator bool(Object o) { return !ReferenceEquals(o, null) && !o.Destroyed; }
    }
    public class ParticleSystem : Object { public int Stops; public void Stop() { Stops++; } }
    public class GameObject : Object {
        public ParticleSystem Particle;
        public T GetComponent<T>() where T : class { return Particle as T; }
    }
    public struct Vector2 {}
}
namespace Examples.Wildfire {
    public class Cell { public UnityEngine.GameObject fire; public int State; }
    public class MapManager {
        public Cell cell; public int Counter;
        public bool Anchor(UnityEngine.Object value) { return value; }
        public void SprayWater(UnityEngine.Vector2 pos, float radius, float angle, UnityEngine.Vector2 aim) {
            var currCell = cell;
            currCell.State = 5;
            Counter++;
            currCell.fire.GetComponent<UnityEngine.ParticleSystem>().Stop();
            Counter += 10;
        }
    }
}
class Test {
    static void Check(UnityEngine.GameObject obj, int expectedStops) {
        var map = new Examples.Wildfire.MapManager { cell = new Examples.Wildfire.Cell { fire = obj } };
        map.SprayWater(new UnityEngine.Vector2(), 3, 60, new UnityEngine.Vector2());
        if (map.Counter != 11 || map.cell.State != 5) throw new Exception("simulation updates changed");
        if (obj != null && obj.Particle != null && obj.Particle.Stops != expectedStops)
            throw new Exception("visual stop count changed");
    }
    static void Main() {
        Check(null, 0);
        Check(new UnityEngine.GameObject(), 0);
        Check(new UnityEngine.GameObject { Destroyed = true, Particle = new UnityEngine.ParticleSystem() }, 0);
        Check(new UnityEngine.GameObject { Particle = new UnityEngine.ParticleSystem { Destroyed = true } }, 0);
        Check(new UnityEngine.GameObject { Particle = new UnityEngine.ParticleSystem() }, 1);
        Console.WriteLine("all five visual cases preserve simulation state");
    }
}
'''


@unittest.skipUnless(shutil.which("mcs") and shutil.which("mono") and CECIL.exists(), "Mono/Cecil required")
class ManagedVisualGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.tool = self.directory / "patch.exe"
        self.original = self.directory / "original.exe"
        cs = self.directory / "fixture.cs"
        cs.write_text(FIXTURE)
        subprocess.run(["mcs", "-r:" + str(CECIL), "-out:" + str(self.tool), str(TOOL)], check=True, capture_output=True)
        subprocess.run(["mcs", "-out:" + str(self.original), str(cs)], check=True, capture_output=True)
        self.digest = hashlib.sha256(self.original.read_bytes()).hexdigest()

    def patch(self, output, digest=None):
        return subprocess.run(["mono", str(self.tool), str(self.original), str(output), digest or self.digest],
                              capture_output=True, text=True)

    def test_repaired_missing_and_healthy_visuals_preserve_world_updates(self):
        old = subprocess.run(["mono", str(self.original)], capture_output=True, text=True)
        self.assertNotEqual(old.returncode, 0)
        self.assertIn("NullReferenceException", old.stderr)
        repaired = self.directory / "repaired.exe"
        patched = self.patch(repaired)
        self.assertEqual(patched.returncode, 0, patched.stderr)
        self.assertIn("UnchangedOtherMethodBodies=", patched.stdout)
        run = subprocess.run(["mono", str(repaired)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("all five visual cases", run.stdout)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), self.digest)

    def test_wrong_input_hash_is_rejected_without_output(self):
        output = self.directory / "unexpected.exe"
        self.assertNotEqual(self.patch(output, "0" * 64).returncode, 0)
        self.assertFalse(output.exists())

    def test_in_place_overwrite_is_rejected(self):
        self.assertNotEqual(self.patch(self.original).returncode, 0)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), self.digest)


if __name__ == "__main__":
    unittest.main()
