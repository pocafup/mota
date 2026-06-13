"""
全程 6360 token 追踪：找到 MT3(5,9) 首次被踩到的 token 编号。
同时追踪英雄每次进入 MT3 的时刻和落点。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA   = Path(__file__).parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

def decode_all():
    lz = LZString()
    route_path = next(Path(__file__).parent.glob("51_*.h5route"))
    outer = json.loads(lz.decompressFromBase64(route_path.read_text(encoding="utf-8").strip()))
    return parse_rle_route(lz.decompressFromBase64(outer["route"]))

def make_state():
    hi = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    fl = load_floor(FLOORS / "MT1.json")
    hero = HeroState(x=hi["loc"]["x"], y=hi["loc"]["y"], hp=hi["hp"], atk=hi["atk"], def_=hi["def"],
                     keys={}, items=dict(hi.get("items",{})), flags=dict(hi.get("flags",{})))
    return GameState(hero=hero, floors={"MT1":fl}, current_floor="MT1",
                     floor_ids=FLOOR_IDS, visited_floors={"MT1"}, pending_floor_change=None, _floors_dir=FLOORS)

def main():
    tokens = decode_all()
    state = make_state()

    mt3_entries = []
    mt3_at_59 = None
    ambush_fired = None

    for i, tok in enumerate(tokens):
        prev_floor = state.current_floor
        prev_xy = (state.hero.x, state.hero.y)

        try:
            state = step(state, tok)
        except Exception as e:
            print(f"[{i}] EXCEPTION: {e}")
            break

        cur_floor = state.current_floor
        cur_xy = (state.hero.x, state.hero.y)

        # 进入 MT3
        if cur_floor == "MT3" and prev_floor != "MT3":
            kind = "fly" if tok.startswith("FLOOR:") else "stair"
            mt3_entries.append((i, tok, kind, cur_xy, dict(state.hero.keys)))

        # 踩上 MT3(5,9)
        if cur_floor == "MT3" and cur_xy == (5, 9) and mt3_at_59 is None:
            mt3_at_59 = (i, tok, dict(state.hero.keys), state.hero.atk)

        # 伏击触发
        if state.hero.atk == 10 and ambush_fired is None:
            ambush_fired = (i, tok, cur_floor, cur_xy)
            print(f"\n★ 伏击触发！token[{i}]={tok!r} floor={cur_floor} pos={cur_xy} ATK=10")
            break

    print("\n─── MT3 所有进入记录 ───")
    for i, tok, kind, xy, keys in mt3_entries[:20]:
        print(f"  [{i:4d}] {tok!r:14s} [{kind}] 落点={xy}  keys={keys}")
    if len(mt3_entries) > 20:
        print(f"  ...共 {len(mt3_entries)} 次")

    print()
    if mt3_at_59:
        i, tok, keys, atk = mt3_at_59
        print(f"首次踩上 MT3(5,9): token[{i}]={tok!r}  keys={keys}  ATK={atk}")
        print(f"  {'伏击应已触发' if atk == 10 else '伏击未触发（模拟器 bug）'}")
    else:
        print("英雄全程从未踩上 MT3(5,9)！")
        print("  → 路线模拟严重偏离，英雄根本没有走到伏击格")

    print()
    if not ambush_fired:
        print("伏击从未触发（ATK 从未降至 10）")
    print(f"\n最终: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) ATK={state.hero.atk} HP={state.hero.hp}")

if __name__ == "__main__":
    main()
