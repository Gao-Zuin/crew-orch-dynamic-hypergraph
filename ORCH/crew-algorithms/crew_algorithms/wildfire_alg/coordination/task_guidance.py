"""Shared, static environment facts and advisory organization guidance.

No live world state, action gates, forced regrouping, or issue lifecycle.
"""

from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=None)
def orch_knowledge_context(level=None):
    """Static ORCH knowledge plus actual single-command capabilities, no world feed."""
    base = Path(__file__).resolve().parents[1] / "algorithms"
    knowledge = json.loads((base / "ORCH/prompts/management/knowledge_base.json").read_text())["knowledge_base"]
    general = knowledge["general"]["information"]
    specific = knowledge.get(level, {}).get("information", [])
    additions = [line for line in specific if line not in general]
    abilities = []
    for kind in ("firefighter", "bulldozer", "drone", "helicopter"):
        text = (base / f"Embodied/prompts/descriptions/{kind}_description.txt").read_text()
        abilities.append(kind.upper() + ":\n" + "\n".join(line.strip() for line in text.splitlines() if line.strip()))
    return ("[SHARED STATIC ENVIRONMENT KNOWLEDGE — ORCH source]\n"
            "These are environment facts and operational recommendations, not live observations. "
            "Apply mission-specific requirements only to that mission: the two-scout fire-confirmation "
            "requirement concerns Scout Fire, not every firefighting or rescue mission. "
            "Safety distances and avoiding repeat spraying are planning advice, not new action gates; "
            "reassess with current observations.\n"
            + "\n".join("- " + line for line in general)
            + ("\n[ORCH notes for this mission]\n" + "\n".join("- " + line for line in additions) if additions else "")
            + "\n[ALL PROFESSIONS — actual single-command action menus]\n"
            + "\n\n".join(abilities)
            + "\nThese commands do not complete arbitrary-distance travel or multi-tree cutting in one step. "
            "Use the following precise action semantics when interpreting the original ORCH notes.\n"
            + WORLD_RULES)


def observed_key_features(grid, position, map_range):
    """ORCH-style coordinate assistance using only this agent's supplied grid."""
    kinds = {"i": "Ignited", "f": "On Fire", "e": "Extinguishing",
             "x": "Extinguished", "C": "Civilians", "w": "Water sources", "B": "Buildings"}
    cells = {name: [] for name in kinds.values()}
    radius = map_range // 2
    for row_index, row in enumerate((grid or "").strip().splitlines()):
        for column_index, raw in enumerate(row.split(",")):
            name = kinds.get(raw.strip().strip("*'"))
            if name:
                cells[name].append((position[0] - radius + column_index,
                                    position[1] - radius + row_index))
    lines = []
    for name, coordinates in cells.items():
        if not coordinates:
            continue
        if len(coordinates) <= 5:
            value = ", ".join(str(p) for p in coordinates)
        else:
            xs, ys = zip(*coordinates)
            value = f"region ({min(xs)},{min(ys)}) to ({max(xs)},{max(ys)}); not every cell in the region contains this feature"
        lines.append(f"{name} ({len(coordinates)}): {value}")
    return ("KEY FEATURES IN THE SUPPLIED LOCAL GRID (computed coordinates, not a global map):\n"
            + ("\n".join(lines) if lines else "No listed features in this grid."))

WORLD_RULES = """CREW action semantics (use these facts rather than job-name assumptions):
- A firefighter moves a few cells per command, cuts ONE tree in its current
  cell, carries/drops civilians, sprays water, and refills from a real water
  source. Cutting does not need water. A cell marked 1/2/3 has that many trees;
  one Cut or a previous visit does not mean the cell is cleared. Re-observe 0
  before reporting it cleared. Quoted numbers are wet terrain, not water sources.
- Firefighter refill works only with an EMPTY tank, setting it to 5 near a
  water-source cell. With 1-4 water, repeated refill does not top up the tank:
  use the remaining water productively or continue feasible work. A positive tank
  is usable: travel and spraying do not require a FULL tank. An old 'refill first'
  suggestion does not make topping up possible. Do not wait at or repeatedly
  return to a source solely to top up a positive tank; choose useful work instead.
  Do not infer
  refill success from issuing the command; compare your observed water count.
- A drone only moves and observes. It cannot cut, spray, transfer water, carry
  firefighters, or pick up civilians. Report positions and uncertainty.
- A helicopter transports FIREFIGHTERS (up to 5), not civilians. It must have
  zero water to pick up firefighters and no passengers to refill its water.
  It may deploy one water below to wet/suppress terrain. This does not refill
  a firefighter's tank or create a water-source cell. Nobody has an agent-to-agent
  water-transfer action. Coordinate direct aerial suppression or actual transport.
  It CAN transport a firefighter who is already carrying a civilian: pick up that
  firefighter, fly to the safe location, drop the firefighter, and have the
  firefighter drop the civilian there. This is not direct civilian pickup.
- A bulldozer moves and clears trees along its route; it is not a water carrier.
- Moving toward a coordinate does not mean arriving there. Check actual position.
  An extinguished ignition point does not prove its surrounding fire front is gone.
  For civilians, carrying, reaching safety, and actually dropping off are distinct.
- Commands and chat confirmations are not physical outcomes. Prefer current
  observations over remembered plans or repeated claims. A second report quoting
  a group goal or another report is not independent confirmation. State uncertainty
  when results cannot be verified; do not invent transfers, pickups, or completion.
"""

ORGANIZATION_GUIDANCE = """Use the smallest useful organization for actual work:
One mixed-role group is a good starting point for one shared objective. Different
professions (scouting, spraying, refilling, transport) are often complementary
roles within that group, not reasons to create a separate edge for each job title.
Split when independently executable objectives really need parallel responsibility
and there are enough agents to do them. A new event need not create a new edge.
Preserve useful work, not redundant group boundaries: merge or retire an edge
whose independent work is finished or whose survivors now work with another team.
There is no fixed edge-count limit. Explain the independent work when adding an edge.
Reconsider old boundaries after attrition: a scout-only or refill-only edge is not
an independent operation just because its job title differs. Fold supporting roles
into the mixed team they actually serve when a separate group adds no useful
responsibility. Do not describe an edge as retired or merged while returning it
unchanged in the JSON; the returned memberships and goals must match your reason.
Give each target a clear primary worker/team; avoid copying the same target list
into different groups unless you explain the actual joint work. Multiple membership
is useful for a real shared role; saying 'bridge' in advice does not grant membership.
Leaders coordinate and can work themselves, not merely wait at a water source.
For a common list of targets, distribute concrete next targets among the workers
of a mixed group. Do not put the entire list in one team and create a second
'overflow' team to repeat it. If splitting cutting teams, partition primary targets
instead. A task like 'do assigned work' for everyone is not a concrete allocation
when the mission already supplies coordinates.
"""
