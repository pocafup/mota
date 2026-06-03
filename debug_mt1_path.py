"""
打印 token[86..200] 英雄轨迹，专注于 MT1 内的关键事件：
钥匙变化、门的开启、楼梯触发。找到英雄如何离开 MT1。
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

    # 先重放到 token[85]
    state = make_initial_state()
    for tok in tokens[:86]:
        state = step(state, tok)
    print(f"token[85] 后: {state.current_floor}({state.hero.x},{state.hero.y}) keys={dict(state.hero.keys)}")
    print()

    # 继续追踪 [86..200]，打印所有非阻塞移动和关键事件
    prev_keys = dict(state.hero.keys)
    prev_pos = (state.hero.x, state.hero.y)
    prev_floor = state.current_floor
    prev_hp = state.hero.hp

    for i in range(86, min(201, len(tokens))):
        tok = tokens[i]
        state = step(state, tok)

        cur_pos = (state.hero.x, state.hero.y)
        cur_floor = state.current_floor
        key_change = {k: state.hero.keys.get(k, 0) - prev_keys.get(k, 0) for k in
                      set(list(state.hero.keys.keys()) + list(prev_keys.keys()))
                      if state.hero.keys.get(k, 0) != prev_keys.get(k, 0)}
        hp_change = state.hero.hp - prev_hp

        moved = cur_pos != prev_pos or cur_floor != prev_floor
        interesting = moved or key_change or hp_change != 0 or tok.startswith(("FLOOR:", "ITEM:", "CHOICE:"))

        if interesting:
            key_str = "".join(f" [{k}{'+' if d > 0 else ''}{d}]" for k, d in key_change.items())
            hp_str = f" [HP{'+' if hp_change > 0 else ''}{hp_change}]" if hp_change != 0 else ""
            floor_str = f" [FLOOR→{cur_floor}]" if cur_floor != prev_floor else ""
            print(f"[{i:4d}] {tok!r:14s} ({prev_pos[0]},{prev_pos[1]})→({cur_pos[0]},{cur_pos[1]}){key_str}{hp_str}{floor_str}")

        prev_keys = dict(state.hero.keys)
        prev_pos = cur_pos
        prev_floor = cur_floor
        prev_hp = state.hero.hp

    print()
    print(f"token[200] 后: {state.current_floor}({state.hero.x},{state.hero.y})")
    print(f"  keys={dict(state.hero.keys)}  HP={state.hero.hp}  ATK={state.hero.atk}")
    print(f"  fly flag: {state.hero.flags.get('fly')}")


if __name__ == "__main__":
    main()
