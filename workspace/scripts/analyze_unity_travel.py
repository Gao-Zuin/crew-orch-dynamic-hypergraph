"""Summarize observed movement from no-model Unity navigation probes."""
import argparse
import json
from math import dist
from pathlib import Path

TYPE_NAME = {0: 'firefighter', 1: 'bulldozer', 2: 'drone', 3: 'helicopter'}


def summarize(path):
    data = json.loads(path.read_text())
    samples = data['samples_before_action']
    if not samples:
        raise ValueError(f'no samples in {path}')
    target = data['target']
    rows = []
    for index, first in enumerate(samples[0]['workers']):
        positions = [sample['workers'][index]['position'] for sample in samples]
        if any(sample['workers'][index]['agent_id'] != first['agent_id'] for sample in samples):
            raise ValueError('worker identity changed during probe')
        lengths = [round(dist(a, b), 2) for a, b in zip(positions, positions[1:])]
        arrival = next((sample['step'] for sample, position in zip(samples, positions)
                        if dist(position, target) < 0.5), None)
        rows.append({'agent_id': first['agent_id'], 'type': TYPE_NAME[first['agent_type']],
                     'start': positions[0], 'target': target,
                     'start_distance_cells': round(dist(positions[0], target), 2),
                     'first_observed_arrival_step': arrival,
                     'step_displacements_cells': lengths,
                     'max_observed_step_displacement_cells': max(lengths, default=0),
                     'path_length_observed_cells': round(sum(lengths), 2)})
    return {'seed': data['seed'], 'level': data['level'], 'rows': rows,
            'scope': 'repeated low-level navigate to one coordinate; one Unity seed/route; before-action samples, no task operations'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('travel_files', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = [summarize(path) for path in args.travel_files]
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps([{'seed': row['seed'], 'arrivals': {
        worker['type']: worker['first_observed_arrival_step'] for worker in row['rows']}}
        for row in result]))


if __name__ == '__main__':
    main()
