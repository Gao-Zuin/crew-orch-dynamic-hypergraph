"""No-model Unity ignition gate for selected structure-matrix seeds."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CWD = ROOT / 'ORCH/crew-algorithms'
UNITY_LOG = ROOT / 'ORCH/UnityLogs/Player-0.log'


def first_successful_fire_location(text_log):
    """Skip rejected spawn candidates; use the first location followed by success."""
    for candidate in re.finditer(r'fire location\s*(\d+)\s*,\s*(\d+)', text_log):
        trailing = text_log[candidate.end():]
        result = re.search(r'fire start (True|False)', trailing)
        next_candidate = re.search(r'fire location', trailing)
        if result and (not next_candidate or result.start() < next_candidate.start()) and result[1] == 'True':
            return [int(candidate[1]), int(candidate[2])]
    return None


def run_seed(seed, output, timeout, family="structure", scarce=1):
    case = (output / f'seed{seed}_R{scarce}').resolve()
    if case.exists():
        raise FileExistsError(case)
    case.mkdir(parents=True)
    env = os.environ.copy()
    for key in ('HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy'):
        env.pop(key, None)
    env.update(NO_PROXY='localhost,127.0.0.1,172.23.0.50',
               no_proxy='localhost,127.0.0.1,172.23.0.50',
               CREW_RESOURCE_SCHEDULING_FAMILY=family,
               CREW_BENCHMARK_MAX_STEPS='10', PYTHONPATH='.', SDL_VIDEODRIVER='dummy',
               LD_PRELOAD=str(ROOT / 'build/rootless_nakama_redirect.so'),
               CREW_NOOP_MANAGER_AUDIT_PATH=str(case / 'manager_observation.json'))
    prefix = {'structure': 'Structure', 'composite': 'Composite'}[family]
    cmd = [str(ROOT / '.conda/crew-orch/bin/python'), '-m',
           'crew_algorithms.wildfire_alg.algorithms.NOOP',
           f'envs.level={prefix}_D1_R{scarce}', f'envs.seed={seed}', 'envs.no_graphics=true']
    with (case / 'runner.log').open('w') as stream:
        proc = subprocess.Popen(cmd, cwd=CWD, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
            code = 'timeout'
    run_text = (case / 'runner.log').read_text(errors='replace')
    log = UNITY_LOG.read_bytes() if UNITY_LOG.exists() else b''
    (case / 'Player-0.log').write_bytes(log)
    text_log = log.decode(errors='replace')
    original = first_successful_fire_location(text_log)
    fire_success = len(re.findall(rb'fire start True', log))
    event_submitted = '[EVENT] t=8:' in run_text
    completed = 'TEST COMPLETE' in run_text and code == 0
    report = {'seed': seed, 'family': family, 'scarce': scarce, 'runner_exit': code, 'completed': completed,
              'event_submitted': event_submitted,
              'original_fire': original,
              'original_fire_parse': 'first fire location followed by fire start True before next candidate',
              'new_fire': [80, 80],
              'unity_true_ignitions': fire_success,
              'event_ignition_supported': completed and event_submitted and fire_success >= 3,
              'unity_log_sha256': hashlib.sha256(log).hexdigest()}
    (case / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('seeds', type=int, nargs='+')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'benchmark_runs/structure_matrix_physical_gate_20261106')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--family', choices=('structure', 'composite'), default='structure')
    parser.add_argument('--scarce', type=int, choices=(0, 1), default=1)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        report = run_seed(seed, args.output, args.timeout, args.family, args.scarce)
        print(json.dumps(report), flush=True)
        if not report['completed']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
