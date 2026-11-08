"""Exercise the real Agent chat API used by typed messages and public notices."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ORCH/crew-algorithms'))
from crew_algorithms.wildfire_alg.algorithms.Embodied import utils

class TypedChatChannels(unittest.TestCase):
    def test_actual_agent_accepts_edge_and_public_notice_channels_and_prunes_normally(self):
        agent=utils.Agent.__new__(utils.Agent)
        agent.chat_history={'GLOBAL':[]}
        agent.add_message('EDGE:airlift','AGENT_2','ready',0)
        agent.add_message('ENVIRONMENT','PUBLIC_ANNOUNCEMENT','new civilians',1)
        self.assertEqual(agent.chat_history['EDGE:airlift'],[('AGENT_2','ready',0)])
        agent.clean_messages(2,1)
        self.assertEqual(agent.chat_history['EDGE:airlift'],[])
        self.assertEqual(len(agent.chat_history['ENVIRONMENT']),1)

if __name__=='__main__':unittest.main()
