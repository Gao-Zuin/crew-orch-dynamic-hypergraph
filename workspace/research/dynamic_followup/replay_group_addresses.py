"""Bounded recorded communication replay; no Unity actions or forced communication."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ORCH/crew-algorithms'))
from crew_algorithms.wildfire_alg.core.token_guard import guarded_chat_completion
from crew_algorithms.wildfire_alg.coordination.soft_task_graph import SoftTaskGraph
from openai import OpenAI


def main():
    run, output = map(Path, sys.argv[1:])
    output.mkdir(parents=True, exist_ok=False)
    events = [json.loads(line) for line in (run / 'run/events.jsonl').open()]
    start = next(e for e in events if e['event_type'] == 'RUN_STARTED')
    commit = next(e for e in events if e['event_type'] == 'TASK_GRAPH_COMMITTED')
    world = next(e for e in events if e['event_type'] == 'TASK_WORLD_SNAPSHOT')
    chunk = next(c for c in (Path(start['payload']['result_path']) / 'Agent_1/chats.txt').read_text().split('END CHAT')
                 if c.strip().startswith('Sending Messages'))
    user = chunk.split('user\n-----\n', 1)[1].split('\n-----\n\nassistant\n-----\n', 1)[0]
    recorded = chunk.split('assistant\n-----\n', 1)[1].split('\n-----', 1)[0]
    source = run.parents[1] / 'workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/algorithms/Embodied/utils.py'
    function = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'communication_round')
    assignment = next(n for n in function.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'system_message' for t in n.targets))
    agent = SimpleNamespace(id=1, cfg=SimpleNamespace(envs=SimpleNamespace(map_size=world['payload']['mission_rules']['map_size'])))
    system = eval(compile(ast.Expression(assignment.value), str(source), 'eval'), {'agent': agent})
    base = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
    candidate = deepcopy(base)
    marker = '[TASK GROUP — ADVISORY]\n'
    prefix, suffix = user.split(marker, 1)
    context, end = json.JSONDecoder().raw_decode(suffix)
    context['group_directory'] = [{k: edge[k] for k in ('id', 'members', 'leader')} for edge in commit['payload']['edges']]
    tail = suffix[end:]
    tail = tail.replace('Omit target for within-group messages.', 'Use the exact group IDs and coordinator IDs in group_directory for addressing.\nOmit target for within-group messages.')
    candidate[-1]['content'] = prefix + marker + json.dumps(context, ensure_ascii=False) + tail
    manifest = {'source_run': str(run), 'agent': '1', 'step': 0, 'repeats_per_variant': 3,
                'recorded_response': recorded, 'only_difference': 'Current group address directory and exact addressing sentence, same as Cycle012',
                'endpoint': 'Existing routing accepts or rejects generated message endpoints; no forced communication or task performance claim',
                'baseline_sha256': hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    graph = SoftTaskGraph(lambda *_: None)
    graph.observe(dict(world['payload'], evidence_id=world['event_id']))
    graph.apply(commit['payload']['proposal'])
    def routes(text):
        scoped = list(re.finditer(r'<EDGE\s+id="([^"]+)"(?:\s+target="([^"]+)")?\s*>(.*?)</EDGE>', text, re.DOTALL))
        packets = [(m.group(1), m.group(2), m.group(3)) for m in scoped]
        rest = text
        for match in reversed(scoped): rest = rest[:match.start()] + rest[match.end():]
        packets.append((graph.active['1'], None, rest))
        rows = []
        for source_id, target, body in packets:
            members = graph.edges.get(target or source_id, {}).get('members', [])
            for recipient in graph.live_agents() - {'1'}:
                direct = re.search(fr'<AGENT_{recipient}>.*?</AGENT_{recipient}>', body, re.DOTALL)
                broadcast = re.search(r'<GLOBAL>.*?</GLOBAL>', body, re.DOTALL)
                for exists in (bool(direct), bool(broadcast) and recipient in members):
                    if exists:
                        allowed, reason = graph.route('1', recipient, source_id, target)
                        rows.append(dict(source=source_id, target=target or source_id, recipient=recipient, allowed=allowed, reason=reason))
        return rows
    key = json.loads(Path('/data/gzy/MAS/mindcraft/keys.json').read_text())['DEEPSEEK_API_KEY']
    summary = []
    with OpenAI(api_key=key, base_url='https://api.deepseek.com', timeout=90, max_retries=1) as client:
        for repeat in range(3):
            for name, messages in (('baseline', base), ('with_directory', candidate)):
                response = guarded_chat_completion(client, model='deepseek-chat', messages=messages, temperature=0,
                    extra_body={'chat_template_kwargs': {'enable_thinking': False}})
                text = response.choices[0].message.content
                row = {'repeat': repeat, 'variant': name, 'messages': messages, 'response': text,
                       'routes': routes(text), 'input_tokens': response.usage.prompt_tokens, 'output_tokens': response.usage.completion_tokens}
                (output / f'{repeat}_{name}.json').write_text(json.dumps(row, indent=2, ensure_ascii=False))
                summary.append({k: v for k, v in row.items() if k not in ('messages', 'response')})
                (output / 'summary.json').write_text(json.dumps(summary, indent=2))
                print(json.dumps(summary[-1]), flush=True)


if __name__ == '__main__':
    main()
