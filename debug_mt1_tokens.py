"""
decoded[55..114] のトークン一覧とシミュレータでの hero 位置を表示。
MT1 出口 (1,1) に近づく瞬間を特定する。
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

    print("=== トークン一覧 decoded[55:115] ===")
    print(f"tokens[55:65]  = {tokens[55:65]}")
    print(f"tokens[65:75]  = {tokens[65:75]}")
    print(f"tokens[75:85]  = {tokens[75:85]}")
    print(f"tokens[85:95]  = {tokens[85:95]}")
    print(f"tokens[95:105] = {tokens[95:105]}")
    print(f"tokens[105:115]= {tokens[105:115]}")
    print()

    for tok in tokens[:55]:
        state = step(state, tok)
    print(f"[54] 後: {state.current_floor}({state.hero.x},{state.hero.y}) HP={state.hero.hp}")
    print()

    # decoded[55..114] を全表示（no-op も含む）
    for i in range(55, 115):
        tok = tokens[i]
        px, py, pf = state.hero.x, state.hero.y, state.current_floor

        blk = ""
        if tok in ("U","D","L","R"):
            r = block_reason(state, tok)
            if r: blk = f" BLK:{r}"

        state = step(state, tok)
        moved = (state.hero.x != px or state.hero.y != py or state.current_floor != pf)
        floor_str = f"→{state.current_floor}" if state.current_floor != pf else ""
        hp_str = f" HP={state.hero.hp}" if state.hero.hp != 1000 else ""
        keys_str = f" k={dict(state.hero.keys)}" if state.hero.keys else ""
        tag = " *MOVE*" if moved else ""
        print(f"[{i:3d}] {tok!r:12s} ({px},{py})→({state.hero.x},{state.hero.y}){blk}{floor_str}{hp_str}{keys_str}{tag}")

    print()
    print(f"[114] 後: {state.current_floor}({state.hero.x},{state.hero.y}) HP={state.hero.hp} keys={dict(state.hero.keys)}")

if __name__ == "__main__":
    main()
