"""
Schema self-check for MT2-MT10.
Feeds each floor's monsters (from map scan) into sim/combat.py.
Verifies field compatibility and reports damage.
Does NOT assert killability—hero stats are starting values and many
MT2-10 monsters require upgraded stats to defeat.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.combat import Monster, PlayerState, compute_combat

DATA = Path(__file__).parent.parent / "data" / "games51"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def monster_from_json(entry: dict) -> Monster:
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


def test_schema_mt2_10_monsters():
    monsters_db = load_json(DATA / "monsters.json")
    tiles_db    = load_json(DATA / "tiles.json")
    hero_init   = load_json(DATA / "hero_init.json")

    hero = PlayerState(
        hp=hero_init["hp"],
        atk=hero_init["atk"],
        def_=hero_init["def"],
        mdef=hero_init["mdef"],
    )

    enemy_tile_to_id = {
        int(tid): info["id"]
        for tid, info in tiles_db["enemys"].items()
    }

    missing_monsters = []
    all_results = {}
    crash_errors = []

    for n in range(2, 11):
        floor_id = f"MT{n}"
        floor = load_json(DATA / "floors" / f"{floor_id}.json")
        floor_map = floor["map"]

        seen = set()
        for row in floor_map:
            for cell in row:
                if cell in enemy_tile_to_id:
                    seen.add(enemy_tile_to_id[cell])

        floor_results = []
        for enemy_id in sorted(seen):
            if enemy_id not in monsters_db:
                missing_monsters.append((floor_id, enemy_id))
                continue
            entry = monsters_db[enemy_id]
            monster = monster_from_json(entry)
            try:
                result = compute_combat(hero, monster)
                floor_results.append({
                    "id": enemy_id,
                    "name": entry["name"],
                    "stats": f"HP={entry['hp']} ATK={entry['atk']} DEF={entry['def']}",
                    "damage": result.damage,
                    "turns": result.turn,
                    "killable": result.damage is not None,
                })
            except Exception as e:
                crash_errors.append((floor_id, enemy_id, str(e)))

        all_results[floor_id] = floor_results

    # Print report
    print(f"\nMT2-10 combat schema check (hero ATK={hero.atk} DEF={hero.def_} HP={hero.hp})")
    print(f"{'Floor':<6} {'Monster':<22} {'Stats':<30} {'Damage':>8} {'Turns':>6} {'Kill':>6}")
    print("-" * 82)
    for floor_id, results in all_results.items():
        for r in results:
            print(
                f"{floor_id:<6} {r['name']:<22} {r['stats']:<30} "
                f"{str(r['damage']):>8} {str(r['turns']):>6} {str(r['killable']):>6}"
            )

    # Assertions: no crashes, no missing monsters, damage >= 0 for killable
    assert not crash_errors, f"Combat crashed: {crash_errors}"
    assert not missing_monsters, f"Monsters in maps but not in monsters.json: {missing_monsters}"

    for floor_id, results in all_results.items():
        for r in results:
            if r["killable"]:
                assert r["damage"] >= 0, \
                    f"{floor_id}/{r['id']} damage={r['damage']} is negative"

    # Summary of unkillable monsters (expected for high-def enemies)
    unkillable = [(fid, r["id"], r["stats"]) for fid, rs in all_results.items()
                  for r in rs if not r["killable"]]
    if unkillable:
        print(f"\nMonsters unkillable by starting hero (expected on higher floors):")
        for fid, mid, stats in unkillable:
            print(f"  {fid} {mid}: {stats}")

    print("\nAll assertions passed.")
