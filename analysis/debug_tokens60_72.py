"""
追踪 token[60..72]：逐格打印英雄位置、层号、ATK、HP。
同时打印 token[0..72] 完整轨迹（用于找偏离点）。
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
    print(f"token[60..72]: {tokens[60:73]}")
    print()

    state = make_initial_state()
    print(f"初始: {state.current_floor}({state.hero.x},{state.hero.y}) "
          f"ATK={state.hero.atk} DEF={state.hero.def_} HP={state.hero.hp}")

    for i, tok in enumerate(tokens[:73]):
        prev_floor = state.current_floor
        prev_x, prev_y = state.hero.x, state.hero.y
        prev_atk = state.hero.atk

        try:
            state = step(state, tok)
        except Exception as e:
            print(f"[{i:3d}] {tok!r:14s} EXCEPTION: {e}")
            break

        marker = ""
        if state.hero.atk != prev_atk:
            marker = f"  *** ATK 变化: {prev_atk}→{state.hero.atk}"
        if state.current_floor != prev_floor:
            marker += f"  [楼层切换: {prev_floor}→{state.current_floor}]"

        # 详细模式：token[55..72]
        if i >= 55 or state.current_floor != "MT1":
            print(f"[{i:3d}] {tok!r:14s} {prev_floor}({prev_x},{prev_y})→{state.current_floor}({state.hero.x},{state.hero.y})"
                  f"  ATK={state.hero.atk} HP={state.hero.hp}{marker}")
        else:
            print(f"[{i:3d}] {tok!r:14s} → {state.current_floor}({state.hero.x},{state.hero.y}){marker}")

    print()
    print("─── 最终状态 ───")
    print(f"  floor={state.current_floor}  pos=({state.hero.x},{state.hero.y})")
    print(f"  ATK={state.hero.atk}  DEF={state.hero.def_}  HP={state.hero.hp}")
    print(f"  伏击已触发: {'是 ✓' if state.hero.atk == 10 else '否 ✗（bug）'}")


if __name__ == "__main__":
    main()
