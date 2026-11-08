import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ORCH/crew-algorithms'))
from crew_algorithms.wildfire_alg.config.build_config import create_level_presets, update_config


class SchedulingEntryTests(unittest.TestCase):
    def test_explicit_family_is_visible_to_standard_runner(self):
        with patch.dict(os.environ, {'CREW_RESOURCE_SCHEDULING_FAMILY': 'structure',
                                     'CREW_RESOURCE_SCHEDULING_DEADLINE': 'urgent'}):
            levels = create_level_presets()
        self.assertIn('Structure_D1_R1_urgent', levels)
        self.assertIn('Structure_D0_R0', levels)
        self.assertEqual(levels['Structure_D0_R0']['scheduled_events'], [])
        cfg = {}
        update_config(levels['Structure_D1_R1_urgent'], 42, cfg)
        self.assertEqual(cfg['starting_drone_agents'], 1)
        self.assertEqual(len(cfg['scheduled_events']), 1)
        self.assertEqual(cfg['scheduled_events'][0]['timestep'], 8)

    def test_default_table_does_not_add_experimental_levels(self):
        with patch.dict(os.environ, {}, clear=True):
            levels = create_level_presets()
        self.assertNotIn('Structure_D1_R1', levels)

    def test_unknown_family_fails(self):
        with patch.dict(os.environ, {'CREW_RESOURCE_SCHEDULING_FAMILY': 'missing'}):
            with self.assertRaises(ValueError):
                create_level_presets()


if __name__ == '__main__':
    unittest.main()
