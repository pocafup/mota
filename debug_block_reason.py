"""
诊断：打印每一步的阻塞原因（terrain/entity/door/key），找 token[0..85] 里哪一步走错了。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import (
    GameState, HeroState, load_floor, step,
    WALL_TILES, SPECIAL_DOOR, DOOR_KEY_MAP,
)

DATA   = Path(__file__).parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
_DIR = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}


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


def block_reason(state: GameState, direction: str) -> str:
    """返回移动被阻塞的原因，或 '' 表示可通行。"""
    floor = state.floor
    dx, dy = _DIR[direction]
    nx, ny = state.hero.x + dx, state.hero.y + dy
    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    if not (0 <= ny < rows and 0 <= nx < cols):
        return "out_of_bounds"
    t = floor.terrain[ny][nx]
    e = floor.entities[ny][nx]
    if t in WALL_TILES:
        return f"WALL(t={t})"
    if t == SPECIAL_DOOR:
        return f"SPECIAL_DOOR(t={t})"
    if e in floor._tile_to_enemy:
        m_id = floor._tile_to_enemy[e]
        return f"ENEMY(e={e} id={m_id}) [would fight]"
    if e in floor._tile_to_item:
        return ""  # item = passable, picks up
    if e in floor._tile_to_entity:
        return f"NPC/entity(e={e})"
    if t in DOOR_KEY_MAP:
        key_id = DOOR_KEY_MAP[t]
        has = state.hero.keys.get(key_id, 0)
        if has > 0:
            return ""  # has key, can open
        return f"DOOR(t={t},key={key_id},have={has})"
    return ""  # passable


def main():
    tokens = _decode_all_tokens()
    state = make_initial_state()

    print(f"初始: {state.current_floor}({state.hero.x},{state.hero.y})  keys={dict(state.hero.keys)}")

    for i, tok in enumerate(tokens[:86]):
        prev_x, prev_y = state.hero.x, state.hero.y
        prev_floor = state.current_floor
        prev_keys = dict(state.hero.keys)

        # 分析阻塞（在 step 之前）
        block = ""
        if tok in ("U", "D", "L", "R") and not state.floor._event_intercepting:
            br = block_reason(state, tok)
            if br and "ENEMY" not in br:  # enemy = fight, not truly blocked
                block = f" BLOCKED:{br}"

        state = step(state, tok)

        moved = (state.hero.x != prev_x or state.hero.y != prev_y or state.current_floor != prev_floor)
        key_change = {k: state.hero.keys.get(k, 0) - prev_keys.get(k, 0) for k in
                      set(list(state.hero.keys.keys()) + list(prev_keys.keys()))
                      if state.hero.keys.get(k, 0) != prev_keys.get(k, 0)}

        key_str = ""
        if key_change:
            for k, d in key_change.items():
                key_str += f" [{k}{'+' if d > 0 else ''}{d}]"

        intercept_str = " [INTERCEPTING]" if state.floor._event_intercepting else ""

        print(
            f"[{i:3d}] {tok!r:14s} "
            f"{prev_floor}({prev_x},{prev_y})→{state.current_floor}({state.hero.x},{state.hero.y})"
            f"{block}{key_str}{intercept_str}"
            + ("  ← MOVED" if moved else "")
        )

    print()
    print(f"最终: {state.current_floor}({state.hero.x},{state.hero.y})")
    print(f"  keys={dict(state.hero.keys)}  ATK={state.hero.atk}  HP={state.hero.hp}")


if __name__ == "__main__":
    main()
