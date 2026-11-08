"""External benchmark observer; leaves algorithm prompts and control flow intact.

The sole policy override is the declared common sampling temperature (zero).
All returned API usage and action-boundary states are logged, including step 20.
"""
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import time
from types import SimpleNamespace


def install_sdk_observer(emit):
    from openai.resources.chat.completions import Completions, AsyncCompletions

    def request(kwargs):
        recorded = {k: kwargs[k] for k in ("model", "messages", "temperature", "max_tokens", "tools") if k in kwargs}
        recorded["requested_temperature"] = kwargs.get("temperature")
        kwargs["temperature"] = 0
        recorded["temperature"] = 0
        emit("LLM_REQUEST", recorded)

    def response(value):
        if not hasattr(value, "model_dump"):
            raise RuntimeError("Streaming response unsupported by benchmark observer")
        emit("LLM_RESPONSE", value.model_dump(mode="json"))
        return value

    sync_create, async_create = Completions.create, AsyncCompletions.create

    def sync(self, *args, **kwargs):
        request(kwargs)
        return response(sync_create(self, *args, **kwargs))

    async def asynchronous(self, *args, **kwargs):
        request(kwargs)
        return response(await async_create(self, *args, **kwargs))

    Completions.create, AsyncCompletions.create = sync, asynchronous


def main():
    algorithm = sys.argv.pop(1)
    output = Path(os.environ["ARCH_OBSERVER_PATH"])
    lock = threading.Lock()
    stream = output.open("x", encoding="utf-8")

    def emit(kind, payload):
        with lock:
            stream.write(json.dumps({"event_type": kind, "time": time.time(), "payload": payload}, ensure_ascii=False) + "\n")
            stream.flush()

    install_sdk_observer(emit)
    from crew_algorithms.wildfire_alg.core import alg_utils, utils
    original_make = utils.make_env

    class EnvironmentObserver:
        def __init__(self, env, cfg):
            self.env, self.cfg, self.step_number = env, SimpleNamespace(envs=cfg), 0

        def __getattr__(self, name):
            return getattr(self.env, name)

        def snapshot(self, state, phase):
            data = alg_utils.parse_game_data(state, self.cfg)
            agents = []
            count = sum(getattr(self.cfg.envs, f"starting_{kind}_agents", 0) for kind in ("firefighter", "bulldozer", "drone", "helicopter"))
            # Unity reserves 51 slots (metadata + up to 50 agents), including
            # inactive padding. Validate configured worker slots, not padding.
            for index in range(1, count + 1):
                obs = alg_utils.get_agent_observations(state, index)
                if self.step_number == 0 and obs["agent_type"] not in (0, 1, 2, 3):
                    raise RuntimeError(f"Configured worker {index} is not active at reset")
                agents.append({k: obs[k] for k in ("position", "agent_type", "extra_variables")})
            emit("STATE", {"step": self.step_number, "phase": phase, "rewards": data["rewards"],
                           "fire_active": data.get("fire_active"), "agents": agents,
                           "task_success": alg_utils.check_game_done({"rewards": data["rewards"], "fire_active": data.get("fire_active", True)}, self.cfg.envs, 0)})

        def reset(self, *args, **kwargs):
            state = self.env.reset(*args, **kwargs)
            try:
                self.snapshot(state, "initial")
            except BaseException:
                self.env.close()
                raise
            return state

        def step(self, state):
            emit("ACTION", {"step": self.step_number, "actions": state["agents"]["action"].detach().cpu().tolist()})
            result = self.env.step(state)
            self.step_number += 1
            self.snapshot(result["next"], "after_action")
            return result

    utils.make_env = lambda cfg, *args, **kwargs: EnvironmentObserver(original_make(cfg, *args, **kwargs), cfg)
    emit("START", {"algorithm": algorithm, "temperature": 0})
    try:
        runpy.run_module(f"crew_algorithms.wildfire_alg.algorithms.{algorithm}", run_name="__main__")
    finally:
        emit("OBSERVER_CLOSED", {})
        stream.close()


if __name__ == "__main__":
    main()
