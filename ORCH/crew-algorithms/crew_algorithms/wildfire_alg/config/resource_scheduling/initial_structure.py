"""Deterministic initial graph for matched fixed/adaptive organization arms."""


def build_initial_structure(nodes, evidence_id, version=0, composite=False):
    live = {str(a): n for a, n in nodes.items() if n.get('online')}
    kinds = {kind: sorted((a for a, n in live.items()
                           if n.get('facts', {}).get('agent_type') == code), key=int)
             for kind, code in (('firefighter', 0), ('bulldozer', 1),
                                ('drone', 2), ('helicopter', 3))}
    if len(kinds['firefighter']) < 4 or not kinds['drone']:
        raise ValueError('structural initial graph requires >=4 firefighters and >=1 drone')
    roster = set().union(*map(set, kinds.values()))
    if roster != set(live):
        raise ValueError('unexpected worker type in structural initial graph')
    firefighters = kinds['firefighter']
    split = (len(firefighters) + 1) // 2
    first = firefighters[:split] + kinds['bulldozer']
    recon_leader = firefighters[split]
    # With two scouts, give the initial rescue/support team its own expert.
    # Otherwise the sufficient-resource control would start with the same
    # cross-edge dependency as the scarce-resource condition.
    second = firefighters[split + 1:] + kinds['helicopter'] + kinds['drone'][1:]
    recon = [recon_leader, kinds['drone'][0]]
    groups = [
        ('original_fire', first, first[0], 'Contain the original fire and maintain a workable firebreak.'),
        ('support', second, second[0],
         'Find and rescue initial civilians while the original fire team contains fire.'
         if composite else 'Prepare water and transport support for the original fire.'),
        ('recon', recon, recon_leader, 'Scout locally and report confirmed hazards.'),
    ]
    edges = [{'id': eid, 'goal': goal, 'members': members, 'leader': leader,
              'tasks': {}, 'advice': 'Report observations and resource needs through your group.'}
             for eid, members, leader, goal in groups if members]
    active = {a: edge['id'] for edge in edges for a in edge['members']}
    assert len(active) == len(live)
    return {'based_on_version': version, 'evidence_id': evidence_id,
            'reason': 'matched deterministic initial organization',
            'edges': edges, 'active': active}
