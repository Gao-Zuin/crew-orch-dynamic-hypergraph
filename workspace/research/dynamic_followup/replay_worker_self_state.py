"""Replay one logged action prompt with/without existing own-state evidence."""
import argparse
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ORCH/crew-algorithms"))
from crew_algorithms.wildfire_alg.core.token_guard import guarded_chat_completion
from openai import OpenAI


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--agent", type=str, default="5")
    parser.add_argument("--step", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    events = []
    for line in (args.run / "run/events.jsonl").open():
        try:
            events.append(json.loads(line))
        except ValueError:
            break
    worlds = {(e["payload"]["step"], e["payload"]["phase"]): e for e in events
              if e["event_type"] == "TASK_WORLD_SNAPSHOT"}
    current = worlds[args.step, "before_action"]
    previous = worlds[args.step - 1, "before_action"]
    action = next(e for e in events if e["event_type"] == "ACTION_STARTED"
                  and e["action_id"] == f"t{args.step - 1}-agent{args.agent}")
    start = next(e for e in events if e["event_type"] == "RUN_STARTED")
    chats = Path(start["payload"]["result_path"]) / f"Agent_{args.agent}/chats.txt"
    chunks = [c for c in chats.read_text().split("END CHAT") if c.strip().startswith("Choosing Action")]
    # This fixture has no skipped/aboard rounds. Verify logged count and position.
    if current["payload"]["nodes"][args.agent]["facts"].get("in_helicopter"):
        raise ValueError("fixture requires an active worker")
    chosen = chunks[args.step]
    user = chosen.split("user\n-----\n", 1)[1].split("\n-----\n\nassistant\n-----\n", 1)[0]
    recorded_response = chosen.split("assistant\n-----\n", 1)[1].split("\n-----", 1)[0]
    node = current["payload"]["nodes"][args.agent]
    prior = previous["payload"]["nodes"][args.agent]
    evidence = {"step": args.step, "position": node["position"], "resources": node["resources"],
                "cached_current_cell": node["facts"].get("current_cell"),
                "current_cell_source": node["facts"].get("current_cell_source"),
                "map_memory": node["facts"].get("map_memory"),
                "previous_action": {"command": action["payload"]["action"],
                                    "resources_before": prior["resources"],
                                    "resources_after": node["resources"],
                                    "source": "recorded own runtime state, not a teammate report"}}
    # Recover the original system string from the run's isolated source copy.
    source = args.run.parents[1] / "workspace/ORCH/crew-algorithms/crew_algorithms/wildfire_alg/algorithms/Embodied/utils.py"
    tree = ast.parse(source.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "action_round")
    assignment = next(n for n in function.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "system_message" for t in n.targets))
    agent = SimpleNamespace(id=int(args.agent), cfg=SimpleNamespace(envs=SimpleNamespace(map_size=current["payload"]["mission_rules"]["map_size"])))
    system = eval(compile(ast.Expression(assignment.value), str(source), "eval"), {"agent": agent})
    baseline = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    candidate = deepcopy(baseline)
    candidate[-1]["content"] += "\n\n[RECORDED OWN STATE AND LAST ACTION RESULT]\n" + json.dumps(evidence, ensure_ascii=False)
    manifest = {"source_run": str(args.run.resolve()), "agent": args.agent, "step": args.step,
                "snapshot_event": current["event_id"], "previous_action_event": action["event_id"],
                "recorded_response": recorded_response,
                "baseline_prompt_sha256": hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest(),
                "only_difference": "append existing own-state and previous-action evidence; no instruction, veto or teammate private state",
                "qualification": "control-only action choice replay; no translation or Unity execution"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    key = json.loads(Path("/data/gzy/MAS/mindcraft/keys.json").read_text())["DEEPSEEK_API_KEY"]
    rows = []
    with OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=90, max_retries=1) as client:
        for repeat in range(args.repeats):
            for variant, messages in (("baseline", baseline), ("with_own_state", candidate)):
                response = guarded_chat_completion(client, model="deepseek-chat", messages=messages,
                    temperature=0, extra_body={"chat_template_kwargs": {"enable_thinking": False}})
                text = response.choices[0].message.content
                match = re.search(r"<action>\s*(.*?)\s*</action>", text, re.DOTALL)
                row = {"repeat": repeat, "variant": variant, "messages": messages, "response": text,
                       "action": match.group(1).strip() if match else None,
                       "input_tokens": response.usage.prompt_tokens,
                       "output_tokens": response.usage.completion_tokens}
                (args.output / f"{repeat}_{variant}.json").write_text(json.dumps(row, indent=2, ensure_ascii=False))
                rows.append({k: v for k, v in row.items() if k != "messages"})
                (args.output / "summary.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
                print(json.dumps({k: v for k, v in row.items() if k not in ("messages", "response")}), flush=True)


if __name__ == "__main__":
    main()
