"""Separate presets for the ORCH event runtime."""
from copy import deepcopy
import json
from pathlib import Path


def create_level_presets(deadline_profile=None, family="focused"):
    """Optionally announce a candidate deadline; stock runner does not score it."""
    if deadline_profile not in (None, 'relaxed', 'urgent'):
        raise ValueError('deadline_profile must be relaxed, urgent, or None')
    if family not in ('focused', 'combined', 'structure', 'composite'):
        raise ValueError('family must be focused, combined, structure, or composite')
    filename = {'focused': 'focused_tasks.json', 'combined': 'tasks.json',
                'structure': 'structure_matrix.json',
                'composite': 'composite_matrix.json'}[family]
    rows = json.loads(Path(__file__).with_name(filename).read_text())
    result = {}
    for row in rows:
        preset = deepcopy(row['preset'])
        if deadline_profile and preset["scheduled_events"]:
            contract = row['design']['deadline_profiles'][deadline_profile]
            preset['name'] += '_' + deadline_profile
            preset['description'] += (
                f" Original goal due by step {contract['original_goal_due_step']}. "
                f"On additional fire release, complete within {contract['new_goal_budget_steps']} "
                f"decision steps: {contract['new_goal']}")
            preset['scheduled_events'][0]['announcement'] += (
                f" New priority: {contract['new_goal']} Complete within "
                f"{contract['new_goal_budget_steps']} decision steps of verified ignition; "
                f"then resume original work, due by step {contract['original_goal_due_step']}.")
        result[preset['name']] = preset
    return result
