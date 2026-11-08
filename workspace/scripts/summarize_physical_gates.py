"""Rebuild geometry eligibility from archived no-model Unity gate reports."""
import argparse
import json
from math import dist
from pathlib import Path


def load_case(root, seed, scarce):
    name = f'seed{seed}' if scarce is None else f'seed{seed}_R{scarce}'
    path = root / name
    report = json.loads((path / 'report.json').read_text())
    manager_path = path / 'manager_observation.json'
    manager = json.loads(manager_path.read_text()) if manager_path.exists() else None
    return report, manager


def manager_goals(manager):
    if manager is None:
        return None
    raw = manager['raw_manager_prefix']
    return {'fire': raw[16:18], 'water': raw[18:20], 'civilian_cluster': raw[20:22]}


def summarize(root, seeds, family, minimum_distance=40):
    rows = []
    for seed in seeds:
        if family == 'structure':
            report, _ = load_case(root, seed, None)
            original = report['original_fire']
            new = report['new_fire']
            separation = round(dist(original, new), 2) if original else None
            eligible = bool(report['event_ignition_supported'] and separation is not None
                            and separation >= minimum_distance)
            rows.append({'seed': seed, 'original_fire': original, 'new_fire': new,
                         'separation_cells': separation,
                         'event_ignition_supported': report['event_ignition_supported'],
                         'independent_front_geometry_gate': eligible})
        else:
            scarce, scarce_manager = load_case(root, seed, 1)
            sufficient, sufficient_manager = load_case(root, seed, 0)
            original = scarce['original_fire']
            new = scarce['new_fire']
            separation = round(dist(original, new), 2) if original else None
            same_fire = original == sufficient['original_fire']
            goals1 = manager_goals(scarce_manager)
            goals0 = manager_goals(sufficient_manager)
            same_goals = goals1 == goals0 if goals1 is not None and goals0 is not None else None
            fire_matches_manager = (goals1['fire'] == original and goals0['fire'] == original
                                    if goals1 is not None and goals0 is not None else None)
            supported = scarce['event_ignition_supported'] and sufficient['event_ignition_supported']
            eligible = bool(supported and same_fire and separation is not None
                            and separation >= minimum_distance and same_goals is True
                            and fire_matches_manager is True)
            rows.append({'seed': seed, 'scarce_goals': goals1, 'sufficient_goals': goals0,
                         'same_initial_goals': same_goals,
                         'original_fire_matches_manager': fire_matches_manager,
                         'new_fire': new,
                         'separation_cells': separation, 'event_ignition_supported_both': supported,
                         'independent_front_geometry_gate': eligible})
    return {'family': family, 'report_source': str(root),
            'minimum_separation_cells': minimum_distance,
            'selected_seeds': [row['seed'] for row in rows if row['independent_front_geometry_gate']],
            'candidates': rows,
            'scope': '10-step NOOP Unity ignition and initial geometry only; no task solvability or policy effect'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--family', choices=('structure', 'composite'), required=True)
    parser.add_argument('--seeds', type=int, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.root, args.seeds, args.family)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_seeds': result['selected_seeds'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
