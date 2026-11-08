"""Five explicit communication intents; no acknowledgement or issue lifecycle."""
import re

INSTRUCTIONS = '''
Communication uses these tags only (replace edge IDs and agent IDs with values
from your group context). A GROUP without to broadcasts within that edge:
<GROUP edge="edge-id">brief group update</GROUP>
<GROUP edge="edge-id" to="member-id">message for a current member</GROUP>
<REPORT edge="edge-id">new observation or obstacle for this edge's leader</REPORT>
<LEADER edge="my-edge" to="other-edge">request or information for the other leader</LEADER>
<ORGANIZER edge="my-edge">analysis and requested organizational change</ORGANIZER>
Do not use GLOBAL, AGENT_n, or EDGE tags. There is no whole-team broadcast.
You may send from any edge you belong to; your active action assignment stays
unchanged. REPORT goes to that edge's leader, not automatically to the center.
Only that edge's leader may use LEADER or ORGANIZER. In <justification>, analyze
new reports against your own observations: choose to handle locally with your
own next action, coordinate members via GROUP, consult another leader via LEADER,
or escalate via ORGANIZER if a resource/role/group change is needed. Escalation
must include your analysis, what local work can continue, and what help/change
is needed; do not merely relay the report. No escalation is required if local
coordination covers all relevant work. A new mission objective outside your edge
is not automatically someone else's responsibility. If no current edge covers it,
or local coordination cannot supply the needed capability, report that gap via
ORGANIZER while useful local work continues. Ask for coverage, not necessarily
a new edge: the organizer may change tasks, merge groups, share a member, or split.
Distinguish observations from guesses and plans.
Report important discoveries, blocked work or changed objectives promptly using
REPORT; leaders may also act on their own observations. Avoid repeating an
unchanged report without useful new information. Output <justification>...</justification>
then zero or more message tags. Sending a message is not a physical action.
Use the CURRENT memberships, directory and concrete route examples below/above;
old chat does not grant current membership. GROUP to an agent requires that agent
to be in that edge. To reach another group's worker, leaders consult that group's
leader via LEADER; other members REPORT the request to their own leader.
REPORT addresses your own edge leader, not a leader in another edge. If you are
that leader, REPORT would address yourself; use LEADER or ORGANIZER as appropriate.
If you lead two edges you can coordinate both directly through their GROUP tags.
Use one clear route per coordination need; do not duplicate a cross-group request
as both GROUP and LEADER. Knowing an agent ID does not make it a group member.
When work is observed complete, duplicated, or persistently ineffective, tell the
responsible leader; leaders inform the organizer when task ownership should change.
Keep past reports as historical evidence, not as proof of today's resources or roles.
'''


def dispatch(bridge, agent, content):
    sender = str(agent.id)
    bridge.c.emit("COMMUNICATION_GENERATED", {"raw_output": content,
                  "timestep": bridge.step}, sender)
    reasoning = re.search(r'<justification>(.*?)</justification>', content, re.DOTALL)
    led = [e['id'] for e in bridge.graph.edges.values() if e['leader'] == sender]
    if led:
        bridge.c.emit("TASK_LEADER_ANALYSIS", {"edges": led, "step": bridge.step,
                      "analysis": reasoning.group(1).strip() if reasoning else "",
                      "raw_output": content}, sender)
    # Reasoning is never interpreted as a request to send a message.
    body = re.sub(r'<justification>.*?</justification>', '', content, flags=re.DOTALL)
    if re.search(r'<(?:GLOBAL|AGENT_\w+|EDGE)\b', body):
        bridge.c.emit("TASK_LEGACY_TAG_IGNORED", {"step": bridge.step,
                      "reason": "typed group/report protocol has no GLOBAL alias"}, sender)
    for match in re.finditer(r'<(GROUP|REPORT|LEADER|ORGANIZER)\b([^>]*)>(.*?)</\1>', body, re.DOTALL):
        kind, attributes, text = match.groups()
        attrs = dict(re.findall(r'(\w+)\s*=\s*["\']([^"\']*)["\']', attributes))
        source = attrs.get('edge'); edge = bridge.graph.edges.get(source)
        text = text.strip()
        reason = None; target = source; recipients = []
        if not text or not edge or sender not in edge['members']:
            reason = 'nonempty text and membership in the named edge are required'
        elif kind in {'LEADER', 'ORGANIZER'} and edge['leader'] != sender:
            reason = 'this intent requires the named edge leader'
        elif kind == 'ORGANIZER':
            bridge.deliver_organizer_report(sender, source, text)
            continue
        elif kind == 'REPORT':
            recipients = [edge['leader']]
        elif kind == 'LEADER':
            target = attrs.get('to'); other = bridge.graph.edges.get(target)
            if not other or target == source:
                reason = 'LEADER to must name another existing edge'
            else:
                recipients = [other['leader']]
        elif attrs.get('to'):
            recipient = attrs['to'].removeprefix('AGENT_')
            if recipient not in edge['members']:
                reason = 'GROUP to must be a member of the named edge'
            else:
                recipients = [recipient]
        else:
            recipients = edge['members']
        if reason:
            # Diagnostic only: no retry, delivery state, response tracking or hold.
            bridge.c.emit('TASK_MESSAGE_INVALID', {'message_type': kind, 'source': source,
                          'reason': reason, 'step': bridge.step}, sender)
            agent.add_message('ENVIRONMENT', 'COMMUNICATION_FORMAT',
                f'Not sent: {kind} from edge {source}: {reason}. '
                'Use the current route examples; this is a local format error, '
                'not a physical action or an instruction to wait.', bridge.step)
            continue
        for recipient in recipients:
            if recipient == sender or recipient not in bridge.runtime_agents:
                continue
            bridge.deliver_routed_message(sender, recipient, source, target, text, kind)
