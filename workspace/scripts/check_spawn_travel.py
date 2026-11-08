"""Nominal, optimistic travel bounds from audited initial worker positions."""
import argparse
import json
from math import ceil, dist
from pathlib import Path

CELLS_PER_STEP = {0: 12, 1: 8, 2: 20, 3: 30}
TYPE_NAME = {0: 'firefighter', 1: 'bulldozer', 2: 'drone', 3: 'helicopter'}


def summarize_case(case):
    audit = json.loads((case / 'manager_observation.json').read_text())
    workers = audit['initial_workers']
    raw = audit['raw_manager_prefix']
    targets = {'original_fire': raw[16:18], 'new_fire': [80, 80],
               'water': raw[18:20], 'civilian_cluster': raw[20:22]}
    by_type = {}
    for worker_type, name in TYPE_NAME.items():
        candidates = [worker for worker in workers if worker['agent_type'] == worker_type]
        target_bounds = {}
        for target_name, target in targets.items():
            if candidates:
                nearest = min(candidates, key=lambda worker: dist(worker['position'], target))
                distance = dist(nearest['position'], target)
                bound = {'nearest_worker': nearest['agent_id'], 'distance_cells': round(distance, 2),
                         'straight_line_steps_to_coordinate': ceil(distance / CELLS_PER_STEP[worker_type])}
                target_bounds[target_name] = bound
        by_type[name] = target_bounds
    return {'level': audit['level'], 'seed': audit['seed'], 'targets': targets,
            'initial_workers': workers, 'nearest_travel': by_type,
            'assumption': 'source nominal 2 simulated seconds per high-level step; straight-line empty-terrain travel to exact target coordinate',
            'inference_limit': 'coordinate travel is not a task deadline bound: scouts may observe from a distance; release-time positions, loading, cutting, suppression and deployed step timing need trajectory verification'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = [summarize_case(case) for case in args.cases]
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps([{'level': row['level'], 'seed': row['seed']} for row in result]))


if __name__ == '__main__':
    main()
