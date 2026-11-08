"""Static, physically grounded ability descriptions for organization decisions."""

ATOM_BY_TYPE = {
    0: ('walk', 'cut_one_tree', 'spray_from_tank', 'refill_empty_tank', 'carry_civilian'),
    1: ('drive', 'clear_trees_on_route'),
    2: ('fly_scout',),
    3: ('fly_transport', 'carry_firefighters', 'deploy_water_below', 'refill_heli_water'),
}

ATOM_SEMANTICS = {
    'walk': 'Firefighter moves on ground; tree density can slow travel.',
    'cut_one_tree': 'Firefighter cuts one tree at its current cell per command.',
    'spray_from_tank': 'Firefighter sprays with positive tank water; refill may require travel.',
    'refill_empty_tank': 'Firefighter refills only when empty at a real water source.',
    'carry_civilian': 'Firefighter picks up and later drops a civilian at safety.',
    'drive': 'Bulldozer moves on ground; clearing while moving halves travel speed.',
    'clear_trees_on_route': 'Bulldozer clears trees along its route while moving.',
    'fly_scout': 'Drone flies and observes nearby map; it cannot extinguish or transport.',
    'fly_transport': 'Helicopter flies; pickup and dropoff consume separate actions.',
    'carry_firefighters': 'Helicopter transports at most five firefighters, not civilians directly.',
    'deploy_water_below': 'Helicopter deploys its own water beneath it, not into another tank.',
    'refill_heli_water': 'Helicopter refills at a water source when it carries no passengers.',
}

SHARING_SEMANTICS = (
    'A worker may advise multiple collaboration edges and join more than one edge. '
    'It performs only one physical action at a time and has exactly one active edge. '
    'Multiple memberships do not duplicate the worker or its water/passenger capacity.'
)


def catalog_for_nodes(nodes):
    atoms = set()
    by_agent = {}
    for agent, node in nodes.items():
        kind = node.get('facts', {}).get('agent_type')
        keys = ATOM_BY_TYPE.get(kind, ())
        by_agent[agent] = list(keys)
        atoms.update(keys)
    return by_agent, {key: ATOM_SEMANTICS[key] for key in sorted(atoms)}
