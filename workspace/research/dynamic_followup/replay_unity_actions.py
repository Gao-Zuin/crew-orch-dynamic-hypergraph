"""Replay recorded commands in a fresh isolated Unity instance, with no LLM."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--source-events", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=17)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.package.resolve()))
    import torch
    from hydra import compose, initialize_config_dir
    from crew_algorithms.wildfire_alg.algorithms.Embodied.__main__ import Config
    from crew_algorithms.wildfire_alg.config.build_config import create_level_presets, update_config, EVENT_ACTION_MAP
    from crew_algorithms.wildfire_alg.core.alg_utils import get_agent_observations, parse_game_data
    from crew_algorithms.wildfire_alg.core.utils import make_env
    from crew_algorithms.envs.channels import ToggleTimestepChannel

    events = []
    for line in args.source_events.open():
        try:
            events.append(json.loads(line))
        except ValueError:
            break
    commands = {}
    after = {}
    for event in events:
        if event["event_type"] == "ACTION_STARTED":
            step = int(event["action_id"].split("-")[0][1:])
            commands.setdefault(step, {})[int(event["agent_id"])] = event["payload"]["action"]
        elif event["event_type"] == "TASK_WORLD_SNAPSHOT" and event["payload"]["phase"] == "after_action":
            after[event["payload"]["step"]] = event["payload"]
    if any(step not in after or step not in commands for step in range(args.steps)):
        raise ValueError("requested prefix is not fully recorded")
    level, seed = events[0]["task_id"], events[0]["task_seed"]
    with initialize_config_dir(version_base=None, config_dir=str(args.package.resolve() / "crew_algorithms/conf")):
        cfg = compose(config_name="wildfire_alg")
    cfg.envs.level = level
    preset = create_level_presets()[level]
    update_config(preset=preset, seed=seed, config=cfg.envs, log_trajectory=False)
    cfg.envs.unity_server_build_path_linux = str(args.build.resolve() / "Unity.x86_64")
    cfg.envs.no_graphics = True
    cfg.envs.log_folder_path = str(args.output.resolve() / "native_logs")
    cfg.envs.render_folder_path = str(args.output.resolve())
    cfg.envs.algorithm = "action_replay"
    cfg.envs.timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    assembly = args.build / "Unity_Data/Managed/Assembly-CSharp.dll"
    manifest = {"level": level, "seed": seed, "steps": args.steps, "llm_calls": 0,
                "build": str(args.build.resolve()), "source_events": str(args.source_events.resolve()),
                "assembly_sha256": hashlib.sha256(assembly.read_bytes()).hexdigest(),
                "qualification": "fresh seeded command replay, not a restored world checkpoint or policy evaluation"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    env = None
    rows = []
    try:
        env = make_env(cfg.envs, ToggleTimestepChannel(uuid.uuid4()), "cpu")
        state = env.reset()
        for step in range(args.steps):
            actions = [[0, 0, 0] for _ in range(cfg.envs.num_agents)]
            for agent, command in commands[step].items():
                actions[agent] = command
            scheduled = [e for e in preset.get("scheduled_events", []) if e["timestep"] == step]
            if scheduled:
                event = scheduled[0]
                actions[0] = [EVENT_ACTION_MAP[event["action"]], event.get("x", 0), event.get("y", 0)]
            state["agents"]["action"] = torch.tensor(actions, dtype=torch.float32)
            next_state = env.step(state)
            state["agents"]["observation"] = next_state["next"]["agents"]["observation"]
            game = parse_game_data(state, cfg)
            nodes = {}
            for agent in sorted(commands[step]):
                obs = get_agent_observations(state, agent)
                nodes[str(agent)] = {"type": obs["agent_type"], "position": obs["position"],
                                     "extra": obs["extra_variables"]}
            row = {"step": step, "rewards": game["rewards"], "fire_active": game["fire_active"],
                   "source_rewards": after[step]["rewards"], "nodes": nodes}
            rows.append(row)
            (args.output / "states.json").write_text(json.dumps(rows, indent=2))
            print(step, game["rewards"], flush=True)
    finally:
        if env is not None:
            env.close()
    native = args.output / "native_logs/Player-0.log"
    exceptions = [line for line in native.read_text(errors="replace").splitlines() if "Exception:" in line]
    result = {"completed_steps": len(rows), "llm_calls": 0, "exception_count": len(exceptions),
              "exception_headings": exceptions, "last_rewards": rows[-1]["rewards"]}
    (args.output / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
