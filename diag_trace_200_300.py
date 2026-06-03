"""
逐 token 轨迹追踪：tok[190..305]
目的：定位 ATK+1(redGem) 和 yellowKey 漏拾的具体 token/格子
打印格式：tok[N] floor (x,y) HP/ATK/DEF yk/bk [事件说明]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, FloorState, load_floor, step, _copy_state

DATA = Path("data/games51")
FLOORS = DATA / "floors"

START = 190
END   = 306


def build_initial_state():
    floor_ids = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
        hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0), gold=hero_init.get("gold", 0),
        keys={}, items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero, floors={"MT1": floor}, current_floor="MT1",
        floor_ids=floor_ids, visited_floors={"MT1"},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def load_tokens():
    route_path = next(Path(".").glob("51_*.h5route"), None)
    if route_path is None:
        print("错误：找不到 51_*.h5route")
        sys.exit(1)
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def main():
    tokens = load_tokens()
    state = build_initial_state()

    # 快进到 START 前
    for i in range(START):
        prev = _copy_state(state)
        state = step(state, tokens[i])

    print(f"{'tok':>6}  {'token':<12}  {'floor':<5}  {'pos':>7}  {'HP':>5}  {'ATK':>4}  {'DEF':>4}  {'yk':>3}  {'bk':>3}  {'备注'}")
    print("-" * 90)

    for i in range(START, min(END, len(tokens))):
        tok = tokens[i]
        prev = _copy_state(state)
        state = step(state, tok)

        h = state.hero
        ph = prev.hero

        yk = h.keys.get("yellowKey", 0)
        bk = h.keys.get("blueKey", 0)
        pyk = prev.hero.keys.get("yellowKey", 0)
        pbk = prev.hero.keys.get("blueKey", 0)

        notes = []

        # 检测 BLOCKED（楼层未变、坐标未变、非事件处理 token）
        floor_same = (prev.current_floor == state.current_floor)
        pos_same = (ph.x == h.x and ph.y == h.y)

        if tok in ("U", "D", "L", "R"):
            if floor_same and pos_same:
                notes.append("BLOCKED")
            elif prev.current_floor != state.current_floor:
                notes.append(f"→{state.current_floor}")

        # ATK 变化
        if h.atk != ph.atk:
            notes.append(f"ATK {ph.atk:+d}→{h.atk} (Δ{h.atk - ph.atk:+d})")
        # DEF 变化
        if h.def_ != ph.def_:
            notes.append(f"DEF {ph.def_:+d}→{h.def_} (Δ{h.def_ - ph.def_:+d})")
        # HP 变化
        if h.hp != ph.hp:
            notes.append(f"HP Δ{h.hp - ph.hp:+d}")
        # 钥匙变化
        if yk != pyk:
            notes.append(f"yellowKey {pyk}→{yk}")
        if bk != pbk:
            notes.append(f"blueKey {pbk}→{bk}")

        note_str = "  ".join(notes) if notes else ""

        # 显示当前格的地图实体（如果当前层已加载）
        cur_floor = state.floors.get(state.current_floor)
        entity_info = ""
        if cur_floor:
            ex = h.x; ey = h.y
            if 0 <= ey < len(cur_floor.entities) and 0 <= ex < len(cur_floor.entities[ey]):
                ent = cur_floor.entities[ey][ex]
                ter = cur_floor.terrain[ey][ex]
                # 尝试还原实体名
                name = cur_floor._tile_to_entity.get(ent, "") if ent else ""
                if name:
                    entity_info = f"[{name}@({ex},{ey})]"

        print(f"tok[{i:>3}]  {tok:<12}  {state.current_floor:<5}  ({h.x:2},{h.y:2})  {h.hp:>5}  {h.atk:>4}  {h.def_:>4}  {yk:>3}  {bk:>3}  {note_str} {entity_info}")


if __name__ == "__main__":
    main()
