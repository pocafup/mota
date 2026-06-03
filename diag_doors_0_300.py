"""
扫描 tok[0..300] 内所有"钥匙被消耗"事件
目的：
  - 统计哪些 token 消耗了钥匙（→ 开门）
  - 验证：开门时，当前模拟器是否把"开门+移动"合并成了一步
  - 为"开门不移动"修复提供全局影响评估
输出：每次钥匙减少的 token 号、方向、门坐标、英雄坐标变化
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step, _copy_state

DATA = Path("data/games51")
FLOORS = DATA / "floors"


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

    print(f"{'tok':>6}  {'dir':<3}  {'floor':<5}  {'before_pos':>9}  {'after_pos':>9}  {'moved?':<7}  {'key_used':<12}  {'门格tile'}")
    print("-" * 80)

    door_count_before = {100: 0, 200: 0, 300: 0}
    door_events = []

    for i in range(min(301, len(tokens))):
        tok = tokens[i]
        prev = _copy_state(state)
        state = step(state, tok)

        ph = prev.hero
        h = state.hero

        # 检查任意钥匙是否减少（开门）
        key_types = ["yellowKey", "blueKey", "redKey", "greenKey", "steelKey"]
        for kt in key_types:
            pk = prev.hero.keys.get(kt, 0)
            ck = h.keys.get(kt, 0)
            if ck < pk:  # 钥匙减少 → 消耗在开门上
                moved = not (ph.x == h.x and ph.y == h.y and prev.current_floor == state.current_floor)
                # 找门的位置（应在英雄移动方向上）
                dx, dy = {"U": (0,-1), "D": (0,1), "L": (-1,0), "R": (1,0)}.get(tok, (0,0))
                door_x = ph.x + dx
                door_y = ph.y + dy
                print(f"tok[{i:>3}]  {tok:<3}  {prev.current_floor:<5}  ({ph.x:2},{ph.y:2})→  ({h.x:2},{h.y:2})  {'✓移动' if moved else '✗未动':<7}  {kt:<12}  门在({door_x},{door_y})")
                door_events.append(i)

    # 按 checkpoint 统计
    print()
    for cp in [100, 200, 300]:
        cnt = sum(1 for d in door_events if d < cp)
        print(f"  tok[0..{cp}) 内开门次数: {cnt}")


if __name__ == "__main__":
    main()
