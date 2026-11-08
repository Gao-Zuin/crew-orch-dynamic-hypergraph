"""Compile the real source visual block with minimal null-object fixtures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "WILDFIRE-ORCH/crew-dojo/Unity/Assets/Examples/Wildfire/Scripts/MapManager.cs"


@unittest.skipUnless(shutil.which("mcs") and shutil.which("mono"), "Mono compiler/runtime required")
class SprayVisualTests(unittest.TestCase):
    def test_optional_particle_object_and_component_can_be_missing(self):
        text = SOURCE.read_text()
        spray = text.split("public void SprayWater(", 1)[1]
        block = spray.split("//GameObject.Destroy(currCell.fire);", 1)[1].split(
            "mapData.colourMap[texture_coordinate]", 1)[0]
        fixture = '''
using System;
class ParticleSystem { public int Stops; public void Stop() { Stops++; } }
class GameObject {
    public ParticleSystem Particle;
    public T GetComponent<T>() where T : class { return Particle as T; }
}
class Cell { public GameObject fire; }
class Test {
    static void Render(Cell currCell) { BLOCK }
    static void Main() {
        Render(new Cell());
        Render(new Cell { fire = new GameObject() });
        var particle = new ParticleSystem();
        Render(new Cell { fire = new GameObject { Particle = particle } });
        if (particle.Stops != 1) throw new Exception("healthy visual must stop once");
        Console.WriteLine("missing object, missing component, healthy particle: OK");
    }
}
'''.replace("BLOCK", block)
        with tempfile.TemporaryDirectory() as directory:
            cs, exe = Path(directory) / "test.cs", Path(directory) / "test.exe"
            cs.write_text(fixture)
            subprocess.run(["mcs", "-out:" + str(exe), str(cs)], check=True, capture_output=True)
            result = subprocess.run(["mono", str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("healthy particle: OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
