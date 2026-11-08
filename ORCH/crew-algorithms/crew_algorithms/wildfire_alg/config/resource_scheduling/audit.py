"""Conservative offline audit for ORCH resource scheduling presets and event logs."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TYPE = {'firefighter': 0, 'bulldozer': 1, 'drone': 2, 'helicopter': 3}
SPEED_PER_STEP = {'drone': 20, 'helicopter': 30, 'bulldozer': 8}


def audit_presets(rows):
    reports = []
    for row in rows:
        preset, design = row['preset'], row['design']
        kind = design['focus_resource']
        events = preset['scheduled_events']
        errors = []
        if preset['game_type'] not in (3, 5):
            errors.append('unsupported game type')
        expected = ['start_fire'] if preset['game_type'] == 3 else ['start_fire', 'spawn_civilians_5']
        if [e['action'] for e in events] != expected:
            errors.append('unexpected events')
        if any(not (0 <= e[k] < preset['map_size']) for e in events for k in ('x', 'y')):
            errors.append('event outside map')
        if len({e['timestep'] for e in events}) != len(events):
            errors.append('colliding event steps')
        if preset['starting_' + kind + '_agents'] != design['capacity']:
            errors.append('capacity mismatch')
        if design['capacity'] not in (1, 2):
            errors.append('unsupported capacity')
        for profile, contract in design['deadline_profiles'].items():
            if contract['new_goal_due_step'] != events[0]['timestep'] + contract['new_goal_budget_steps']:
                errors.append(profile + ' deadline mismatch')
            if contract['new_goal_due_step'] >= contract['original_goal_due_step']:
                errors.append(profile + ' deadline reaches original horizon')
        diagonal = math.sqrt(2) * (preset['map_size'] - 1)
        lower = math.ceil(diagonal / SPEED_PER_STEP[kind])
        reports.append({'id': row['id'], 'resource': kind, 'capacity': design['capacity'],
                        'nominal_full_map_travel_steps': lower,
                        'urgent_budget': design['deadline_profiles']['urgent']['new_goal_budget_steps'],
                        'errors': errors,
                        'confounds': (['fire and five civilians added together'] if preset['game_type'] == 5 else [])
                                     + ['source scenario has no fixed initial goal location'],
                        'completion_observability': 'insufficient_from_existing_global_rewards',
                        'feasibility': 'unverified_requires_release_state_and_scripted_schedule'})
    return reports


def audit_events(path, new_fire=(70, 70), radius=8):
    """Return evidence status; shared map cells cannot prove fresh direct visibility."""
    snapshots, actions = [], []
    for line in Path(path).open():
        item = json.loads(line)
        if item.get('event_type') == 'TASK_WORLD_SNAPSHOT':
            snapshots.append(item['payload'])
        elif item.get('event_type') == 'ACTION_COMPLETED':
            actions.append(item)
    after = [s for s in snapshots if s.get('phase') == 'after_action']
    submitted = [s for s in after if any(e.get('action') == 'start_fire' for e in
                 s.get('event_commands_and_announcements', []))]
    candidates = []
    for s in submitted:
        for worker_id, node in s.get('nodes', {}).items():
            if node.get('facts', {}).get('agent_type') != TYPE['drone'] or not node.get('online'):
                continue
            cells = node.get('facts', {}).get('map_memory', {}).get('cells', {}).get('fire', [])
            if any(math.dist(cell, new_fire) <= radius for cell in cells):
                candidates.append({'step': s['step'], 'worker_id': worker_id,
                                   'evidence': 'shared_accumulated_map_only'})
    return {'snapshots': len(snapshots), 'completed_actions': len(actions),
            'event_announced_in_snapshot': bool(submitted),
            'new_fire_physical_effect': 'unknown', 'drone_direct_observation': 'unknown',
            'new_goal_completion': 'unknown', 'shared_map_candidates': candidates[:10],
            'reason': 'event announcement is not ignition proof; cached map has no observer or freshness'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', type=Path)
    parser.add_argument('--fire-x', type=int, default=70)
    parser.add_argument('--fire-y', type=int, default=70)
    args = parser.parse_args()
    reports = audit_presets(json.loads((ROOT / 'tasks.json').read_text()) +
                            json.loads((ROOT / 'focused_tasks.json').read_text()))
    result = {'presets': reports, 'error_count': sum(len(x['errors']) for x in reports)}
    if args.events:
        result['trajectory'] = audit_events(args.events, (args.fire_x, args.fire_y))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result['error_count']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
