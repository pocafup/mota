"""
诊断：找到 MT3(5,9) 伏击在全程重放中为何从未触发。
输出所有楼层切换记录 + MT3 上的每一步英雄坐标。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA   = Path(__file__).parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))


def _decode_all_tokens() -> list[str]:
    def decompress(s: str) -> str:
        return LZString().decompressFromBase64(s)
    route_path = next(Path(__file__).parent.glob("51_*.h5route"))
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    return parse_rle_route(decompress(outer["route"]))


def make_initial_state() -> GameState:
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"],
        y=hero_init["loc"]["y"],
        hp=hero_init["hp"],
        atk=hero_init["atk"],
        def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0),
        gold=hero_init.get("gold", 0),
        keys={},
        items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero,
        floors={"MT1": floor},
        current_floor="MT1",
        floor_ids=FLOOR_IDS,
        visited_floors={"MT1"},
        pending_floor_change=None,
        _floors_dir=FLOORS,
    )


def main():
    tokens = _decode_all_tokens()
    print(f"总 token 数: {len(tokens)}")

    state = make_initial_state()
    prev_floor = state.current_floor
    prev_pos = (state.hero.x, state.hero.y)

    mt3_steps = []         # MT3 上的每步 (tok_idx, tok, x, y)
    floor_changes = []     # 所有楼层切换

    for i, tok in enumerate(tokens):
        try:
            state = step(state, tok)
        except Exception as e:
            print(f"[{i}] EXCEPTION: {e} | tok={tok!r} | floor={state.current_floor} pos=({state.hero.x},{state.hero.y})")
            break

        cur_floor = state.current_floor
        cur_pos   = (state.hero.x, state.hero.y)

        # 记录楼层切换
        if cur_floor != prev_floor:
            floor_changes.append((i, tok, prev_floor, prev_pos, cur_floor, cur_pos))

        # 记录 MT3 上每一步
        if cur_floor == "MT3":
            mt3_steps.append((i, tok, cur_pos[0], cur_pos[1]))

        # 伏击触发
        if state.hero.atk == 10:
            print(f"\n*** 伏击触发！token[{i}]={tok!r} ATK=10 HP={state.hero.hp} floor={state.current_floor} pos={cur_pos}")
            break

        prev_floor = cur_floor
        prev_pos   = cur_pos

    print("\n─── 楼层切换记录（共 %d 次）───" % len(floor_changes))
    for i, tok, f_from, p_from, f_to, p_to in floor_changes:
        print(f"  [{i:4d}] tok={tok!r:12s} {f_from}({p_from[0]},{p_from[1]}) → {f_to}({p_to[0]},{p_to[1]})")

    print("\n─── MT3 上的步骤（共 %d 步）───" % len(mt3_steps))
    if len(mt3_steps) == 0:
        print("  （英雄从未停留在 MT3）")
    else:
        # 打印每个连续 MT3 段落
        seg_start = 0
        for j in range(len(mt3_steps)):
            if j == len(mt3_steps) - 1 or mt3_steps[j+1][0] != mt3_steps[j][0] + 1:
                seg = mt3_steps[seg_start:j+1]
                print(f"  段 {seg_start}..{j}: tok[{seg[0][0]}..{seg[-1][0]}]")
                for idx, tok, x, y in seg:
                    print(f"    [{idx}] {tok!r} → ({x},{y})")
                seg_start = j + 1

    print("\n─── 最终状态 ───")
    print(f"  floor={state.current_floor}  pos=({state.hero.x},{state.hero.y})")
    print(f"  ATK={state.hero.atk}  DEF={state.hero.def_}  HP={state.hero.hp}")
    print(f"  伏击触发: {'是' if state.hero.atk == 10 else '否（bug）'}")


if __name__ == "__main__":
    main()
