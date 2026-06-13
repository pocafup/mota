"""
追踪全程 6360 个 token：记录所有非 fly 楼梯切层（changeFloor via stair），
找到英雄第一次经楼梯进入 MT3 的 token 编号。
同时记录每次楼层切换（包括 fly 和 stair）的摘要。
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
    state = make_initial_state()

    first_mt3_stair = None
    floor_changes = []  # (idx, tok, from_floor, from_pos, to_floor, to_pos, kind)

    for i, tok in enumerate(tokens):
        prev_floor = state.current_floor
        prev_pos = (state.hero.x, state.hero.y)

        try:
            state = step(state, tok)
        except Exception as e:
            print(f"[{i}] EXCEPTION: {e} tok={tok!r}")
            break

        cur_floor = state.current_floor
        cur_pos = (state.hero.x, state.hero.y)

        if cur_floor != prev_floor:
            kind = "fly" if tok.startswith("FLOOR:") else "stair/event"
            floor_changes.append((i, tok, prev_floor, prev_pos, cur_floor, cur_pos, kind))
            if cur_floor == "MT3" and kind == "stair/event" and first_mt3_stair is None:
                first_mt3_stair = (i, tok, prev_floor, prev_pos, cur_pos)

        # 伏击
        if state.hero.atk == 10:
            print(f"\n*** 伏击触发！token[{i}]={tok!r} ATK=10 floor={state.current_floor} pos={cur_pos}")
            break

        if i > 500:  # 保险：500 token 内找不到就报告
            break

    print("─── 楼层切换（前500 token）───")
    for rec in floor_changes:
        i, tok, f_from, p_from, f_to, p_to, kind = rec
        print(f"  [{i:4d}] {tok!r:14s} {f_from}({p_from[0]},{p_from[1]}) → {f_to}({p_to[0]},{p_to[1]}) [{kind}]")

    print()
    if first_mt3_stair:
        i, tok, f_from, p_from, p_to = first_mt3_stair
        print(f"首次经楼梯入 MT3: token[{i}]={tok!r}  from {f_from}{p_from}  landed at MT3{p_to}")
    else:
        print("在前 500 token 内，英雄从未经楼梯进入 MT3（仅 fly 方式）。")

    print()
    print(f"最终状态: floor={state.current_floor} pos=({state.hero.x},{state.hero.y})")
    print(f"  ATK={state.hero.atk}  HP={state.hero.hp}")


if __name__ == "__main__":
    main()
