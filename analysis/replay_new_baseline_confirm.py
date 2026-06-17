"""全新实例独立重放新基准存档 51_20260616144514.h5route，确认端态（CLAUDE.md 正确性铁律）。

只读：LZString 解码 → 从 MT1 起点(hero_init.json)逐 token 送入 sim.step → 报终态。
不改任何产品码。重放范式照 tests/test_replay_mt1_mt11.py（已验证）。

明确用新存档（目录另有 51_20260529133740 / 51_roundtrip_full，不靠 glob 第一个）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
SAVE = ROOT / "51_20260616144514.h5route"


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def main() -> None:
    raw = SAVE.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    tokens = parse_rle_route(decompress(outer["route"]))

    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
        hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0), gold=hero_init.get("gold", 0),
        keys={}, items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    state = GameState(
        hero=hero, floors={"MT1": floor}, current_floor="MT1",
        floor_ids=FLOOR_IDS, visited_floors={"MT1"},
        pending_floor_change=None, _floors_dir=FLOORS,
    )

    applied = blocked = 0
    floor_visits = [state.current_floor]
    atk_min = state.hero.atk
    trail = []
    for idx, tok in enumerate(tokens):
        before = (state.current_floor, state.hero.x, state.hero.y)
        state = step(state, tok)
        if state.current_floor != floor_visits[-1]:
            floor_visits.append(state.current_floor)
        atk_min = min(atk_min, state.hero.atk)
        if tok in ("U", "D", "L", "R"):
            after = (state.current_floor, state.hero.x, state.hero.y)
            if after != before:
                applied += 1
            else:
                blocked += 1
        if idx >= len(tokens) - 25:
            h = state.hero
            trail.append(f"[{idx}] {tok:9s} {state.current_floor} "
                         f"({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} GOLD={h.gold}")

    h = state.hero
    print(f"meta name={outer.get('name')!r} seed={outer.get('seed')}")
    print(f"tokens={len(tokens)}")
    print(f"RULD applied={applied} blocked={blocked}")
    print(f"floor={state.current_floor} pos=({h.x},{h.y})")
    print(f"HP={h.hp} ATK={h.atk} DEF={h.def_} MDEF={h.mdef} GOLD={h.gold}")
    print(f"keys={dict(h.keys)}")
    print(f"dead={state.dead} won={state.won}")
    print(f"\natk_min（验 MT3 伏击应=10）={atk_min}")
    print(f"楼层访问序列: {' '.join(floor_visits)}")
    print("末段 25 步轨迹:")
    for line in trail:
        print("  " + line)


if __name__ == "__main__":
    main()
