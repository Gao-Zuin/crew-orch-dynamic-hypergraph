"""Paired, completeness-gated analysis of the D x R x organization matrix."""
import argparse
import json
from pathlib import Path
from structure_metrics import summarize

STRUCTURE_SEEDS = (42, 256, 503, 819)
COMPOSITE_SEEDS = (42, 256, 503, 314)


def read_case(path, dynamic, scarce, arm, seed, prefix="Structure"):
    if not path.exists():
        return {'status': 'missing', 'events_path': str(path)}
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    kinds = {e['event_type'] for e in events}
    starts = [e for e in events if e['event_type'] == 'RUN_STARTED']
    initial = [e for e in events if e['event_type'] == 'TASK_STRUCTURAL_INITIAL_PLAN']
    ht_starts = [e for e in events if e['event_type'] == 'TASK_HYPERGRAPH_STARTED']
    snapshots = [e['payload'] for e in events if e['event_type'] == 'TASK_WORLD_SNAPSHOT'
                 and e['payload'].get('phase') == 'after_action']
    status = 'complete' if 'RUN_FINISHED' in kinds and snapshots else 'incomplete'
    expected = f'{prefix}_D{dynamic}_R{scarce}'
    if not starts or starts[0].get('task_id') != expected or starts[0].get('task_seed') != seed:
        status = 'identity_mismatch'
    if len(initial) != 1:
        status = 'initial_graph_missing_or_duplicate'
    if len(ht_starts) != 1 or ht_starts[0]['payload'].get('fixed_groups') != (arm == 'fixed'):
        status = 'organization_arm_mismatch'
    if ht_starts and not ht_starts[0]['payload'].get('structural_initial_plan'):
        status = 'structural_initial_plan_disabled'
    signature = None
    if initial:
        p = initial[0]['payload']['proposal']
        signature = {'edges': [{k: e[k] for k in ('id', 'members', 'leader')}
                               for e in p['edges']], 'active': p['active']}
    metrics = summarize(path) if dynamic else None
    if dynamic and (not metrics or metrics['notice_step'] is None):
        status = 'dynamic_notice_missing'
    run_config = {key: starts[0]['payload'].get(key) for key in
                  ('model', 'max_steps', 'intervention', 'context_profile')} if starts else None
    local_config = {key: ht_starts[0]['payload'].get(key) for key in
                    ('local_event_info', 'local_event_radius', 'structural_initial_plan', 'round_delivery')} if ht_starts else None
    return {'status': status, 'events_path': str(path), 'initial_graph': signature,
            'run_config': run_config, 'local_config': local_config,
            'last_step': snapshots[-1]['step'] if snapshots else None,
            'last_fire_active_global': snapshots[-1].get('fire_active') if snapshots else None,
            'response': metrics}


def analyze(root, seeds=None, local=1, round_delivery=1, family="structure"):
    if family not in ("structure", "composite"):
        raise ValueError("family must be structure or composite")
    if seeds is None:
        seeds = STRUCTURE_SEEDS if family == 'structure' else COMPOSITE_SEEDS
    prefix = "Structure" if family == "structure" else "Composite"
    cells = {}
    pairs = []
    for seed in seeds:
        for dynamic in (0, 1):
            for scarce in (0, 1):
                key = f'D{dynamic}R{scarce}_seed{seed}'
                cases = {}
                for arm in ('fixed', 'adaptive'):
                    path = root / f'{prefix}_D{dynamic}_R{scarce}_seed{seed}_{arm}_local{local}' / 'events.jsonl'
                    cases[arm] = read_case(path, dynamic, scarce, arm, seed, prefix)
                cells[key] = cases
                fixed, adaptive = cases['fixed'], cases['adaptive']
                if fixed['status'] != 'complete' or adaptive['status'] != 'complete':
                    pairs.append({'cell': key, 'status': 'unusable',
                                  'reason': f"fixed={fixed['status']}, adaptive={adaptive['status']}"})
                    continue
                if fixed['run_config'] != adaptive['run_config'] or fixed['local_config'] != adaptive['local_config']:
                    pairs.append({'cell': key, 'status': 'unusable', 'reason': 'run configuration mismatch'})
                    continue
                if bool(fixed['local_config']['round_delivery']) != bool(round_delivery):
                    pairs.append({'cell': key, 'status': 'unusable', 'reason': 'communication timing arm mismatch'})
                    continue
                if bool(fixed['local_config']['local_event_info']) != bool(local):
                    pairs.append({'cell': key, 'status': 'unusable', 'reason': 'information arm mismatch'})
                    continue
                if fixed['initial_graph'] != adaptive['initial_graph']:
                    pairs.append({'cell': key, 'status': 'unusable', 'reason': 'initial graph mismatch'})
                    continue
                if fixed['last_step'] != adaptive['last_step']:
                    pairs.append({'cell': key, 'status': 'unusable', 'reason': 'different completed horizons'})
                    continue
                if dynamic and (fixed['response']['notice_step'] != adaptive['response']['notice_step'] or
                                fixed['response']['notice_step'] != 8):
                    pairs.append({'cell': key, 'status': 'unusable', 'reason': 'event timing mismatch'})
                    continue
                result = {'cell': key, 'status': 'matched', 'horizon': fixed['last_step']}
                if dynamic:
                    for metric in ('notice_to_topology_change', 'notice_to_new_region_action',
                                   'notice_to_source_view_fire',
                                   'notice_to_firefighter_entry', 'notice_to_two_firefighters_in_region'):
                        a = adaptive['response'][metric]
                        f = fixed['response'][metric]
                        result[metric + '_adaptive_minus_fixed'] = a - f if a is not None and f is not None else None
                pairs.append(result)
    return {'seeds': list(seeds), 'family': family, 'local_event_info': local,
            'round_delivery': round_delivery, 'cases': cells, 'pairs': pairs,
            'matched_pairs': sum(x['status'] == 'matched' for x in pairs),
            'causal_scope': 'response proxies only; no per-fire suppression outcome or model/prompt hash gate'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('--seeds', type=int, nargs='+')
    p.add_argument('--local', type=int, choices=(0, 1), default=1)
    p.add_argument('--round-delivery', type=int, choices=(0, 1), default=1)
    p.add_argument('--output', type=Path)
    p.add_argument('--family', choices=('structure', 'composite'), default='structure')
    a = p.parse_args()
    result = analyze(a.root, a.seeds, a.local, a.round_delivery, a.family)
    content = json.dumps(result, indent=2)
    if a.output:
        a.output.write_text(content + '\n')
    else:
        print(content)


if __name__ == '__main__':
    main()
