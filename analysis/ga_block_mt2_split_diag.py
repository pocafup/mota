"""【一次性诊断·只读】dump③ 在 MT2 step#71 报出 1 起块分裂反例 —— 钉死它的物理成因（绝不猜测·实跑）。

分裂 = 一个旧自由块裂成 ≥2 新块 = 某个【中间自由格由"自由"变"非自由"】把走廊截断。可能成因：
  · 移动怪走上该格（怪 footprint → 非自由）；· 机关门关闭（free→门）；· 领域怪激活（zone_blocked 扩张）；
  · 到达事件被启用/改写。本脚本在分裂步把 free_before/after 逐格 diff，对每个【消失的自由格】打印
  terrain/entities(怪或道具)/门/事件/zone_blocked 归属，定位是哪一类结构事件。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from solver.quotient import partition_floor_blocks, _is_free_tile, _zone_blocked   # noqa: E402
from export_mt10_boss_route import make_initial_state                             # noqa: E402
from decode_route import parse_rle_route, decompress                             # noqa: E402
from sim.simulator import step                                                    # noqa: E402

ROUTE = ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"
TARGET_FID = "MT2"


def _free_all(state):
    floor = state.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    zb = _zone_blocked(state)
    return {(x, y) for y in range(rows) for x in range(cols)
            if _is_free_tile(state, x, y, zb)}, zb


def _describe(state, x, y, zb):
    floor = state.floor
    t = floor.terrain[y][x]
    e = floor.entities[y][x]
    loc = f"{x},{y}"
    enemy = floor._tile_to_enemy.get(e)
    item = floor._tile_to_item.get(e)
    ev = floor.events.get(loc)
    return (f"terrain={t} entities={e}"
            f"{' 怪='+str(enemy) if enemy else ''}{' 道具='+str(item) if item else ''}"
            f"{' 门' if loc in floor.change_floor else ''}"
            f"{' 在zone_blocked' if (x, y) in zb else ''}"
            f"{' 有事件'+('(已抑制)' if loc in floor._suppressed_events else '') if ev is not None else ''}")


def _monster_cells(state):
    floor = state.floor
    return {(x, y): floor._tile_to_enemy.get(e)
            for y, row in enumerate(floor.entities) for x, e in enumerate(row)
            if floor._tile_to_enemy.get(e)}


def main():
    outer = json.loads(decompress(ROUTE.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    prev_floor = s.current_floor
    prev_free, prev_zb = (_free_all(s) if prev_floor == TARGET_FID else (None, None))
    prev_blocks = partition_floor_blocks(s) if prev_floor == TARGET_FID else None
    prev_state = s
    prev_mons = _monster_cells(s) if prev_floor == TARGET_FID else {}

    for i, a in enumerate(actions, 1):
        s = step(s, a)
        if s.dead:
            break
        f = s.current_floor
        if f != TARGET_FID:
            prev_floor = f
            prev_free = prev_blocks = None
            prev_state = s
            continue
        cur_free, cur_zb = _free_all(s)
        cur_blocks = partition_floor_blocks(s)
        if f == prev_floor and prev_blocks is not None:
            split_here = any(
                len([nb for nb in cur_blocks if ob & nb]) >= 2 for ob in prev_blocks)
            if split_here:
                disappeared = sorted(prev_free - cur_free)
                appeared = sorted(cur_free - prev_free)
                ph, ch = prev_state.hero, s.hero
                print("=" * 78)
                print(f"分裂步 step#{i}  动作={a!r}")
                print(f"  勇者：前 ({ph.x},{ph.y}) → 后 ({ch.x},{ch.y})   "
                      f"HP {ph.hp}→{ch.hp} ATK {ph.atk}→{ch.atk}")
                print(f"  自由格变化：消失 {len(disappeared)} 个 / 新增 {len(appeared)} 个")
                print(f"\n  ▼ 消失的自由格（free→非自由·把走廊截断者）：")
                for (x, y) in disappeared:
                    print(f"      ({x},{y})  后态: {_describe(s, x, y, cur_zb)}")
                    print(f"               前态: {_describe(prev_state, x, y, prev_zb)}")
                print(f"\n  ▲ 新增的自由格（非自由→free）：")
                for (x, y) in appeared:
                    print(f"      ({x},{y})  前态: {_describe(prev_state, x, y, prev_zb)}")
                # 怪移动 diff
                cur_mons = _monster_cells(s)
                moved_to = {c: m for c, m in cur_mons.items() if prev_mons.get(c) != m}
                moved_from = {c: m for c, m in prev_mons.items() if cur_mons.get(c) != m}
                print(f"\n  ◆ 怪格变化：新占 {moved_to}   腾空 {moved_from}")
                print(f"\n  旧块锚={[min(b) for b in prev_blocks if len([nb for nb in cur_blocks if b & nb])>=2]}"
                      f"  → 新块锚={sorted(min(nb) for nb in cur_blocks)}")
                print("=" * 78)
                break
        prev_floor = f
        prev_free, prev_zb = cur_free, cur_zb
        prev_blocks = cur_blocks
        prev_state = s
        prev_mons = _monster_cells(s)


if __name__ == "__main__":
    main()
