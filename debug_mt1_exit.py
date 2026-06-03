"""
decoded[115..155] の詳細トレース。
目的：hero が MT1(11,7) から U×6 を実行して (11,1) → staircase に到達するか確認。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import (GameState, HeroState, load_floor, step,
                           WALL_TILES, SPECIAL_DOOR, DOOR_KEY_MAP)

DATA   = Path(__file__).parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
_DIR = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}

def decode_all():
    lz = LZString()
    route_path = next(Path(__file__).parent.glob("51_*.h5route"))
    outer = json.loads(lz.decompressFromBase64(route_path.read_text(encoding="utf-8").strip()))
    return parse_rle_route(lz.decompressFromBase64(outer["route"]))

def make_state():
    hi = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    fl = load_floor(FLOORS / "MT1.json")
    hero = HeroState(x=hi["loc"]["x"], y=hi["loc"]["y"],
                     hp=hi["hp"], atk=hi["atk"], def_=hi["def"],
                     keys={}, items=dict(hi.get("items",{})),
                     flags=dict(hi.get("flags",{})))
    return GameState(hero=hero, floors={"MT1":fl}, current_floor="MT1",
                     floor_ids=FLOOR_IDS, visited_floors={"MT1"},
                     pending_floor_change=None, _floors_dir=FLOORS)

def block_reason(state, direction):
    fl = state.floor
    dx, dy = _DIR[direction]
    nx, ny = state.hero.x + dx, state.hero.y + dy
    rows, cols = len(fl.terrain), len(fl.terrain[0]) if fl.terrain else 0
    if not (0 <= ny < rows and 0 <= nx < cols): return "OOB"
    t, e = fl.terrain[ny][nx], fl.entities[ny][nx]
    if t in WALL_TILES: return f"WALL(t={t})"
    if t == SPECIAL_DOOR: return "SPEC_DOOR"
    if e in fl._tile_to_enemy: return ""
    if t in DOOR_KEY_MAP:
        k = DOOR_KEY_MAP[t]
        return "" if state.hero.keys.get(k, 0) > 0 else f"DOOR(need={k},have=0)"
    return ""

def main():
    tokens = decode_all()
    state = make_state()

    # decoded[0..114] を高速実行
    for tok in tokens[:115]:
        state = step(state, tok)

    print(f"[114] 後: {state.current_floor}({state.hero.x},{state.hero.y}) keys={dict(state.hero.keys)} HP={state.hero.hp}")
    print()

    # decoded[115..154] を全部表示（no-op も含む）
    for i in range(115, 155):
        tok = tokens[i]
        px, py, pf = state.hero.x, state.hero.y, state.current_floor

        blk = ""
        if tok in ("U","D","L","R") and state.current_floor == "MT1":
            r = block_reason(state, tok)
            if r: blk = f" BLOCKED:{r}"

        state = step(state, tok)

        moved = (state.hero.x != px or state.hero.y != py or state.current_floor != pf)
        floor_str = f" →{state.current_floor}" if state.current_floor != pf else ""
        intercept = " [INT]" if state.floor._event_intercepting else ""
        keys_str = f" keys={dict(state.hero.keys)}" if state.hero.keys else ""

        pos_arrow = f"{pf}({px},{py})→({state.hero.x},{state.hero.y})"
        print(f"[{i:3d}] {tok!r:12s} {pos_arrow}{blk}{floor_str}{intercept}{keys_str}  HP={state.hero.hp}")

    print()
    print(f"[154] 後: {state.current_floor}({state.hero.x},{state.hero.y}) keys={dict(state.hero.keys)} HP={state.hero.hp}")
    print(f"token[115:125]={tokens[115:125]}")
    print(f"token[125:135]={tokens[125:135]}")
    print(f"token[135:145]={tokens[135:145]}")
    print(f"token[145:155]={tokens[145:155]}")

if __name__ == "__main__":
    main()
