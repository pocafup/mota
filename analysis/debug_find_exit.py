"""
decoded[0..400] を実行し、最初に floor が変わる瞬間を見つける。
また (1,1) に近づく / 踏む瞬間も全てログ。
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

def main():
    tokens = decode_all()
    state  = make_state()

    floor_change_found = False
    row1_visits = []

    for i, tok in enumerate(tokens[:600]):
        px, py, pf = state.hero.x, state.hero.y, state.current_floor

        try:
            state = step(state, tok)
        except Exception as e:
            print(f"[{i}] EXCEPTION on {tok!r}: {e}")
            break

        cf = state.current_floor
        cx, cy = state.hero.x, state.hero.y

        # 楼層変化を探す
        if cf != pf:
            print(f"\n★ FLOOR CHANGE at token[{i}] = {tok!r}")
            print(f"   {pf}({px},{py}) → {cf}({cx},{cy})")
            floor_change_found = True
            break

        # row1 に入った
        if cf == "MT1" and cy == 1 and cy != py:
            row1_visits.append((i, tok, cx, cy))
            print(f"[{i:4d}] {tok!r:12s} MT1 row1! ({px},{py})→({cx},{cy})")

        # (1,1) に到達
        if cf == "MT1" and cx == 1 and cy == 1:
            print(f"\n★ hero at MT1(1,1) at token[{i}] = {tok!r}")
            floor_change_found = True
            break

    if not floor_change_found:
        print(f"\n--- 600 tokens 内に楼層変化なし ---")
        print(f"最終: {state.current_floor}({state.hero.x},{state.hero.y})")
        print(f"Row1 訪問: {len(row1_visits)} 回")
        for v in row1_visits:
            print(f"  {v}")

    # token[155:250] を表示（参考）
    print(f"\ntokens[155:165]={tokens[155:165]}")
    print(f"tokens[165:175]={tokens[165:175]}")
    print(f"tokens[175:185]={tokens[175:185]}")
    print(f"tokens[185:195]={tokens[185:195]}")
    print(f"tokens[195:210]={tokens[195:210]}")
    print(f"tokens[210:225]={tokens[210:225]}")
    print(f"tokens[225:240]={tokens[225:240]}")
    print(f"tokens[240:255]={tokens[240:255]}")
    print(f"tokens[255:270]={tokens[255:270]}")
    print(f"tokens[270:290]={tokens[270:290]}")

if __name__ == "__main__":
    main()
