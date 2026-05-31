"""
Schema self-check: feed monsters.json + MT1 floor data into sim/combat.py.
Verifies field compatibility and computes damage for all MT1 monsters.
Hero: initial state from hero_init.json (HP=1000, ATK=100, DEF=100, mdef=0).
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.combat import Monster, PlayerState, compute_combat

DATA = Path(__file__).parent.parent / "data" / "games51"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def monster_from_json(entry: dict) -> Monster:
    """Convert monsters.json entry to sim/combat.py Monster."""
    special = entry.get("special", [])
    if isinstance(special, int):
        special = [special] if special != 0 else []

    return Monster(
        id=entry["id"],
        name=entry["name"],
        hp=entry["hp"],
        atk=entry["atk"],
        def_=entry["def"],
        special=special,
        n=entry.get("n", 0),
        value=entry.get("value", 0.0),
        add=entry.get("add", False),
        atkValue=entry.get("atkValue", 0.1),
        defValue=entry.get("defValue", 0.9),
        damage=entry.get("damage", 0),
    )


def test_schema_mt1_monsters():
    monsters_db = load_json(DATA / "monsters.json")
    floor = load_json(DATA / "floors" / "MT1.json")
    hero_init = load_json(DATA / "hero_init.json")

    hero = PlayerState(
        hp=hero_init["hp"],
        atk=hero_init["atk"],
        def_=hero_init["def"],
        mdef=hero_init["mdef"],
    )

    # Collect unique monster IDs from MT1 map via tiles.json
    tiles_db = load_json(DATA / "tiles.json")
    enemy_tile_to_id = {
        int(tid): info["id"]
        for tid, info in tiles_db["enemys"].items()
    }

    mt1_map = floor["map"]
    seen_enemies = set()
    for row in mt1_map:
        for cell in row:
            if cell in enemy_tile_to_id:
                seen_enemies.add(enemy_tile_to_id[cell])

    print(f"MT1 enemies found in map: {sorted(seen_enemies)}")
    assert seen_enemies, "No enemies found in MT1 map"

    results = []
    for enemy_id in sorted(seen_enemies):
        assert enemy_id in monsters_db, f"Enemy '{enemy_id}' not in monsters.json"
        entry = monsters_db[enemy_id]
        monster = monster_from_json(entry)
        result = compute_combat(hero, monster)

        results.append({
            "id": enemy_id,
            "name": entry["name"],
            "monster_stats": f"HP={entry['hp']} ATK={entry['atk']} DEF={entry['def']}",
            "damage": result.damage,
            "turns": result.turn,
            "killable": result.damage is not None,
            "effects": result.effects,
        })

    print("\nMT1 combat self-check (hero ATK=100 DEF=100 HP=1000 mdef=0):")
    print(f"{'Monster':<20} {'Stats':<30} {'Damage':>8} {'Turns':>6} {'Killable':>9}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['name']:<20} {r['monster_stats']:<30} "
            f"{str(r['damage']):>8} {str(r['turns']):>6} {str(r['killable']):>9}"
        )

    # Sanity assertions
    for r in results:
        # All MT1 monsters should be killable by starting hero
        assert r["killable"], f"{r['id']} should be killable by starting hero"
        # Damage should be non-negative
        assert r["damage"] >= 0, f"{r['id']} damage={r['damage']} is negative"
        # MT1 basic monsters have no specials → no post-combat effects
        fx = r["effects"]
        assert not (fx.poison or fx.weak or fx.curse or fx.explode), \
            f"{r['id']} unexpectedly has post-combat effects: {fx}"

    print("\nAll assertions passed.")
    return results
