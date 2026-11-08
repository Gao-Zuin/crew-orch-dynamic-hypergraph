"""Verify environment action semantics reach the actual worker request offline."""
from pathlib import Path
import os
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

PACKAGE = Path(__file__).resolve().parents[1] / "ORCH/crew-algorithms"
sys.path.insert(0, str(PACKAGE))
from crew_algorithms.wildfire_alg.algorithms.Embodied import utils


class EmbodiedActionPromptTests(unittest.TestCase):
    def test_official_refill_prompt_is_preserved_without_blocking_action(self):
        cfg = SimpleNamespace(envs=SimpleNamespace(llm_model="custom", llm_url="unused", map_size=80))
        agent = SimpleNamespace(id=1, type=0, cfg=cfg, api_key="test", past_actions=[],
                                chat_history={}, current_task="Suppress fire",
                                last_perception="At (15,22), water=3", last_position=[15, 22],
                                extra_variables=[0, 3, 0], log_chat=Mock())
        data = dict(large_model="test", api_calls=0, input_tokens=0, output_tokens=0)
        response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            choices=[SimpleNamespace(message=SimpleNamespace(content="<action>Refill water</action>"))])
        translated = utils.Action(type=6, param_1=0, param_2=0, description="Refill water")
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(PACKAGE)
        with patch.object(utils, "OpenAI"), \
                patch.object(utils, "guarded_chat_completion", return_value=response) as completion, \
                patch.object(utils, "translate_action", return_value=translated):
            action = utils.action_round(agent, data)
        prompt = completion.call_args.kwargs["messages"][-1]["content"]
        self.assertIn("Refill water. You must be on a water source.", prompt)
        self.assertIn("Move a few steps in the the direction", prompt)
        self.assertNotIn("does not top up", prompt)
        # Original prompt and physical action translation remain unchanged.
        self.assertEqual(action, [4, 15, 22])


if __name__ == "__main__":
    unittest.main()
