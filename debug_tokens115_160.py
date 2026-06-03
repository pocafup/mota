"""打印 token[115..160] 逐格详情，重点分析 CHOICE:0 和 (11,7) 附近行为。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step, WALL_TILES, SPECIAL_DOOR, DOOR_KEY_MAP

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
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    fl = load_floor(FLOORS / "MT1.json")
    hero = HeroState(x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
                     hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
                     keys={}, items=dict(hero_init.get("items", {})), flags=dict(hero_init.get("flags", {})))
    return GameState(hero=hero, floors={"MT1": fl}, current_floor="MT1",
                     floor_ids=FLOOR_IDS, visited_floors={"MT1"}, pending_floor_change=None, _floors_dir=FLOORS)

def block_why(state, direction):
    fl = state.floor; dx, dy = _DIR[direction]; nx, ny = state.hero.x+dx, state.hero.y+dy
    rows, cols = len(fl.terrain), len(fl.terrain[0]) if fl.terrain else 0
    if not (0<=ny<rows and 0<=nx<cols): return "OOB"
    t, e = fl.terrain[ny][nx], fl.entities[ny][nx]
    if t in WALL_TILES: return f"wall(t={t})"
    if t == SPECIAL_DOOR: return f"special_door"
    if e in fl._tile_to_enemy: return f"enemy(e={e})"
    if e in fl._tile_to_item: return ""
    if e in fl._tile_to_entity: return f"npc(e={e})"
    if t in DOOR_KEY_MAP:
        k=DOOR_KEY_MAP[t]; return "" if state.hero.keys.get(k,0)>0 else f"door(t={t},need={k},have={state.hero.keys.get(k,0)})"
    return ""

def main():
    tokens = decode_all()
    state = make_state()
    for tok in tokens[:115]: state = step(state, tok)
    print(f"token[114] 后: {state.current_floor}({state.hero.x},{state.hero.y}) keys={dict(state.hero.keys)}")
    print(f"tokens[115..160]: {tokens[115:161]}")
    print()
    for i in range(115, 161):
        tok = tokens[i]
        px, py, pf = state.hero.x, state.hero.y, state.current_floor
        pk = dict(state.hero.keys)
        blk = ""
        if tok in ("U","D","L","R") and not state.floor._event_intercepting:
            r = block_why(state, tok)
            if r and "enemy" not in r: blk = f" BLOCKED:{r}"
        state = step(state, tok)
        key_d = {k: state.hero.keys.get(k,0)-pk.get(k,0) for k in set(list(state.hero.keys)+list(pk)) if state.hero.keys.get(k,0)!=pk.get(k,0)}
        k_str = "".join(f" [{k}{'+' if d>0 else ''}{d}]" for k,d in key_d.items())
        floor_str = f" →{state.current_floor}" if state.current_floor!=pf else ""
        print(f"[{i:3d}] {tok!r:12s} {pf}({px},{py})→({state.hero.x},{state.hero.y}){blk}{k_str}{floor_str}")

if __name__ == "__main__":
    main()
