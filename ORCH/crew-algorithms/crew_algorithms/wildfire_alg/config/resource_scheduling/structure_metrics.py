"""Evidence-linked early response metrics for one ORCH HT event stream."""
import argparse
import json
import math
from pathlib import Path


def summarize(path, fire=(80, 80), radius=12, deployment_budget=None):
    notice_step = None
    notice_source = None
    current_step = None
    prior_topology = None
    graph_change = None
    first_region_action = None
    first_field_entry = None
    first_two_field_entry = None
    first_local_cue = None
    first_source_view_fire = None
    action_count = 0
    with Path(path).open() as stream:
        lines = stream.readlines()
    for line in lines:
        event = json.loads(line)
        kind, payload = event.get('event_type'), event.get('payload', {})
        if kind == 'TASK_WORLD_SNAPSHOT':
            current_step = payload['step']
            if notice_step is None and payload['phase'] == 'after_action' and any(
                    e.get('action') == 'start_fire' for e in payload.get('event_commands_and_announcements', [])):
                notice_step = current_step
                notice_source = 'snapshot_announced_command'
            if notice_step is not None and payload['phase'] == 'after_action':
                field_ids = {aid for aid, node in payload.get('nodes', {}).items()
                             if (node.get('online') and node.get('facts', {}).get('agent_type') == 0
                                 and node.get('position') and math.dist(node['position'], fire) <= radius)}
                if first_field_entry is None and field_ids:
                    first_field_entry = current_step
                if first_two_field_entry is None and len(field_ids) >= 2:
                    first_two_field_entry = current_step
        elif kind == 'TASK_ENVIRONMENT_NOTICE' and payload.get('event', {}).get('action') in ('start_fire', 'fire_alert'):
            notice_step = payload.get('step', current_step)
            notice_source = 'environment_notice'
        elif kind == 'TASK_LOCAL_EVENT_CUE_DELIVERED':
            if first_local_cue is None:
                first_local_cue = payload.get('step', current_step)
        elif kind == 'TASK_SOURCE_VIEW_FIRE_SIGHTING':
            if first_source_view_fire is None:
                first_source_view_fire = payload.get('step', current_step)
        elif kind == 'TASK_GRAPH_COMMITTED':
            edges = payload.get('edges', [])
            proposal = payload.get('proposal', {})
            topology = {'members': {e['id']: sorted(e['members']) for e in edges},
                        'leaders': {e['id']: e['leader'] for e in edges},
                        'active': proposal.get('active', {})}
            if (notice_step is not None and prior_topology is not None and topology != prior_topology
                    and graph_change is None):
                graph_change = current_step
            prior_topology = topology
        elif kind == 'ACTION_STARTED':
            action_count += 1
            if (notice_step is not None and first_region_action is None and
                    payload.get('action', [None])[0] in (0, 1)):
                action = payload['action']
                if len(action) >= 3 and math.dist(action[1:3], fire) <= radius:
                    first_region_action = payload.get('timestep', current_step)
    def delay(step):
        return None if notice_step is None or step is None else step - notice_step
    return {'notice_step': notice_step, 'notice_source': notice_source, 'first_topology_change_step': graph_change,
            'first_local_cue_step': first_local_cue,
            'notice_to_local_cue': delay(first_local_cue),
            'first_source_view_fire_step': first_source_view_fire,
            'notice_to_source_view_fire': delay(first_source_view_fire),
            'notice_to_topology_change': delay(graph_change),
            'first_new_region_action_step': first_region_action,
            'notice_to_new_region_action': delay(first_region_action),
            'first_firefighter_entry_step': first_field_entry,
            'notice_to_firefighter_entry': delay(first_field_entry),
            'first_two_firefighters_in_region_step': first_two_field_entry,
            'notice_to_two_firefighters_in_region': delay(first_two_field_entry),
            'deployment_budget_steps': deployment_budget,
            'deployment_by_deadline': ('unknown' if notice_step is None or deployment_budget is None
                                      else first_two_field_entry is not None and
                                      first_two_field_entry <= notice_step + deployment_budget),
            'action_count': action_count,
            'new_fire_physical_effect': ('fire_cell_seen_near_event_in_source_defined_own_view'
                                         if first_source_view_fire is not None else 'unknown'),
            'new_fire_suppression': 'unknown',
            'deployment_interpretation': 'two live firefighter positions in region; arrival does not prove helicopter transport or fire control',
            'qualification': 'Own-view sighting is positive local fire evidence near the submitted event, not a complete origin or suppression proof; positions and action destinations remain response proxies.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('events', type=Path)
    parser.add_argument('--x', type=int, default=80)
    parser.add_argument('--y', type=int, default=80)
    parser.add_argument('--radius', type=float, default=12)
    parser.add_argument('--deployment-budget', type=int)
    args = parser.parse_args()
    print(json.dumps(summarize(args.events, (args.x, args.y), args.radius, args.deployment_budget), indent=2))


if __name__ == '__main__':
    main()
