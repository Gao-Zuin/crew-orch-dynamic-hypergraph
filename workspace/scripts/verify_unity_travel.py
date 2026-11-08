"""Run a no-model Unity movement probe and archive its observed positions."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CWD = ROOT / 'ORCH/crew-algorithms'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--steps', type=int, default=10)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    case = args.output.resolve()
    if case.exists():
        raise FileExistsError(case)
    case.mkdir(parents=True)
    env = os.environ.copy()
    for key in ('HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy'):
        env.pop(key, None)
    env.update(NO_PROXY='localhost,127.0.0.1,172.23.0.50',
               no_proxy='localhost,127.0.0.1,172.23.0.50',
               CREW_RESOURCE_SCHEDULING_FAMILY='composite',
               CREW_BENCHMARK_MAX_STEPS=str(args.steps),
               CREW_NOOP_TRAVEL_PROBE_PATH=str(case / 'travel.json'),
               PYTHONPATH='.', SDL_VIDEODRIVER='dummy',
               LD_PRELOAD=str(ROOT / 'build/rootless_nakama_redirect.so'))
    cmd = [str(ROOT / '.conda/crew-orch/bin/python'), '-m',
           'crew_algorithms.wildfire_alg.algorithms.NOOP',
           'envs.level=Composite_D0_R1', f'envs.seed={args.seed}',
           'envs.no_graphics=true']
    with (case / 'runner.log').open('w') as stream:
        proc = subprocess.Popen(cmd, cwd=CWD, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = proc.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
            code = 'timeout'
    completed = code == 0 and 'TEST COMPLETE' in (case / 'runner.log').read_text(errors='replace')
    if not completed or not (case / 'travel.json').exists():
        raise RuntimeError(f'travel probe failed; see {case / "runner.log"}')
    data = json.loads((case / 'travel.json').read_text())
    print(json.dumps({'completed': completed, 'seed': data['seed'],
                      'samples': len(data['samples_before_action']),
                      'output': str(case / 'travel.json')}))


if __name__ == '__main__':
    main()
