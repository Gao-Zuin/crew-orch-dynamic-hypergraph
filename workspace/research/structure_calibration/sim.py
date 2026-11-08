"""Deterministic mechanism check: shared expert, local reports, mutable edges.

This is a calibration fixture, not a CREW-Wildfire result or an LLM policy.
"""
from dataclasses import dataclass, asdict
import argparse
import json


@dataclass(frozen=True)
class Scenario:
    dynamic: bool
    scarce_scout: bool
    adaptive_edges: bool
    release: int = 4
    emergency_due: int = 9
    original_due: int = 15


def simulate(scenario):
    if scenario.release >= scenario.emergency_due:
        raise ValueError('emergency deadline must follow release')
    scouts = ['scout_west'] + ([] if scenario.scarce_scout else ['scout_east'])
    edges = {'west': ['west_leader', 'west_firefighter_2', 'west_firefighter_3',
                      'west_firefighter_4', 'west_dozer', 'scout_west'],
             'east': ['east_leader', 'east_firefighter_2', 'east_firefighter_3',
                      'east_firefighter_4', 'east_dozer']}
    if 'scout_east' in scouts:
        edges['east'].append('scout_east')
    history = []
    second_west_scan = None
    east_notice = None
    east_finish = None
    scout_arrival = None
    scout_departure = None
    route = None
    for step in range(scenario.original_due + 1):
        if scenario.dynamic and step == scenario.release:
            history.append({'step': step, 'event': 'emergency_alert',
                            'content': 'Possible fire in eastern sector; exact location unknown.'})
            if scenario.scarce_scout:
                scout_departure = step
                if scenario.adaptive_edges:
                    edges['east'].append('scout_west')
                    history.append({'step': step, 'event': 'edge_added',
                                    'worker': 'scout_west', 'edge': 'east'})
        if step == 2:
            history.append({'step': step, 'event': 'west_scan', 'worker': 'scout_west'})
        if scenario.dynamic:
            if scenario.scarce_scout:
                scout_arrival = scenario.release + 2
                observer = 'scout_west'
                observation = scout_arrival
                # Fixed topology can use the faster organizer path: scout ->
                # recon leader -> center, which updates the east task after
                # queued delivery. A shared member reaches east directly.
                route = ['scout_west', 'east_leader'] if scenario.adaptive_edges else [
                    'scout_west', 'recon_leader', 'organizer']
                if step == observation:
                    history.append({'step': step, 'event': 'local_observation',
                                    'worker': observer, 'content': 'Active fire seen at eastern ridge.'})
            else:
                observer = 'scout_east'
                observation = scenario.release
                route = ['scout_east', 'east_leader']
                if step == observation:
                    history.append({'step': step, 'event': 'local_observation',
                                    'worker': observer, 'content': 'Active fire seen at eastern ridge.'})
            delivery = observation + len(route) - 1
            if step == delivery:
                east_notice = step
                history.append({'step': step, 'event': 'report_delivered',
                                'route': route, 'content': 'Active fire seen at eastern ridge.'})
            if east_notice is not None and step == east_notice + 2:
                east_finish = step
                history.append({'step': step, 'event': 'east_suppressed',
                                'workers': ['east_firefighter_2', 'east_dozer']})
        if scenario.scarce_scout and scenario.dynamic:
            # One scout returns after its message is delivered. The original
            # west task still needs a second observation, so it is not free.
            return_scan = (scenario.release + 2) + (1 if scenario.adaptive_edges else 2) + 2
        else:
            return_scan = 9
        if step == return_scan:
            second_west_scan = step
            history.append({'step': step, 'event': 'west_scan', 'worker': 'scout_west'})
    original_finished = second_west_scan is not None and second_west_scan <= scenario.original_due
    new_finished = not scenario.dynamic or (east_finish is not None and east_finish <= scenario.emergency_due)
    return {'scenario': asdict(scenario), 'roster_size': 10 + len(scouts),
            'initial_edges': {'west': 6, 'east': 5 + (0 if scenario.scarce_scout else 1)},
            'final_east_members': edges['east'],
            'east_report_route': route, 'east_report_step': east_notice,
            'east_finished_step': east_finish,
            'original_finished': original_finished, 'emergency_met_deadline': new_finished,
            'both_objectives_met': original_finished and new_finished,
            'events': history}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dynamic', type=int, choices=(0, 1), required=True)
    parser.add_argument('--scarce', type=int, choices=(0, 1), required=True)
    parser.add_argument('--adaptive', type=int, choices=(0, 1), required=True)
    args = parser.parse_args()
    print(json.dumps(simulate(Scenario(bool(args.dynamic), bool(args.scarce), bool(args.adaptive))), indent=2))


if __name__ == '__main__':
    main()
