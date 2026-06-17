"""【方向2·便宜诊断②补】beam 卡住的 ATK25/DEF25/HP733 态下，剩余 ATK/DEF 宝石是否【real 可达】
（打得过沿途怪）→ 区分「延迟满足/搜索问题·加力可破」vs「战力锁死·加力没用」。

- door-wise(②)：守怪一律可穿 = 乐观上界（已知 ATK27/DEF27、没锁红门后）。
- real-reach(本脚本)：怪格用引擎 _combat_damage 判能不能打过（打不过=断边，单怪不累积损血=乐观）。

若 ATK25/DEF25 态下剩余红蓝宝石仍 real 可达 → beam 没收全是搜索/延迟满足问题（非战力锁）→ 加宽 beam 有戏。
若被打不过的怪锁死 → 要先攒别处属性才能拿、但别处也卡 → 偏死锁。

只读：构造 beam 卡住态（replay tok454 后把属性改到 ATK25/DEF25/HP733）。绝不改产品码。
"""
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step
from solver.fitness import _afford_colors, _zone_floor_cells
from extract.key_targets import _floor_tile_at, _NB4
from solver.beam import _combat_damage

REAL_LEG = ["MT1", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10"]
GEM = {27: ("redGem", "ATK"), 28: ("blueGem", "DEF")}


def _flood(state, fid, afford, respect_combat):
    """floodfill。respect_combat=False→守怪可穿(door-wise)；True→怪格须打得过(real)。
    返回 (seen, gem_cells)；gem_cells = [(x,y,tile)] 在 seen 里的红蓝宝石。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return None, []
    h, w, is_wall, mid_at, _keys, src = info
    hp = state.hero.hp

    def passable(x, y):
        if is_wall(x, y):
            return False
        if (x, y) in mid_at:
            if not respect_combat:
                return True
            d = _combat_damage(state, mid_at[(x, y)])
            return d is not None and d < hp     # 能杀且单怪不死
        return True

    seen, dq = set(), deque()
    for s in src:
        if passable(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and passable(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    gems = []
    for (x, y) in seen:
        t = _floor_tile_at(state, fid, x, y)
        if t in GEM:
            gems.append((x, y, t))
    return seen, gems


def main():
    s = build_initial_state()
    toks, _ = load_tokens()
    for t in toks[:455]:
        s = step(s, t)
    # 构造 beam 卡住态：属性改到 ATK25/DEF25/HP733（诊断 hack·只读模拟）
    s.hero.atk, s.hero.def_, s.hero.hp = 25, 25, 733
    afford = _afford_colors(s)
    print("=" * 84)
    print(f"诊断态（beam 卡住）= ATK{s.hero.atk}/DEF{s.hero.def_}/HP{s.hero.hp}  afford={afford}")
    print("door-wise=守怪可穿(乐观上界) ; real=怪须打得过(引擎 _combat_damage 判)")
    print("=" * 84)

    door_n = {27: 0, 28: 0}
    real_n = {27: 0, 28: 0}
    blocked = []   # door-wise 可达但 real 不可达的宝石（被打不过的怪挡）
    for fid in REAL_LEG:
        _, gems_door = _flood(s, fid, afford, respect_combat=False)
        seen_real, gems_real = _flood(s, fid, afford, respect_combat=True)
        real_set = {(x, y) for (x, y, _t) in gems_real}
        for (x, y, t) in gems_door:
            door_n[t] += 1
        for (x, y, t) in gems_real:
            real_n[t] += 1
        only_door = [(x, y, t) for (x, y, t) in gems_door if (x, y) not in real_set]
        if gems_door:
            dd = [f"{GEM[t][0]}({x},{y})" for (x, y, t) in gems_door]
            rr = [f"{GEM[t][0]}({x},{y})" for (x, y, t) in gems_real]
            print(f"\n[{fid}] door-wise红蓝宝石={dd}")
            print(f"      real可达红蓝宝石={rr}")
            if only_door:
                bd = [f"{GEM[t][0]}({x},{y})" for (x, y, t) in only_door]
                print(f"      ★被打不过的怪挡(door可达但real不可达)={bd}")
                blocked.extend((fid, x, y, t) for (x, y, t) in only_door)

    print("\n" + "=" * 84)
    print("【汇总】ATK25/DEF25/HP733 态下：")
    print(f"  redGem(ATK)：door-wise可达 {door_n[27]} 颗 / real可达 {real_n[27]} 颗")
    print(f"  blueGem(DEF)：door-wise可达 {door_n[28]} 颗 / real可达 {real_n[28]} 颗")
    print(f"  beam 攒到 ATK25(收3红)/DEF25(收5蓝)。破门要再 +1红 或 +1蓝。")
    if real_n[27] >= 4 or real_n[28] >= 6:
        print(f"  ⟹ real 可达红/蓝宝石数 ≥ beam 已收(3红/5蓝)+1 → 剩余宝石【真够得到】（怪打得过）")
        print(f"     → beam 没收全是搜索/延迟满足问题、非战力锁 → 加宽 beam 有戏。")
    else:
        print(f"  ⟹ real 可达红/蓝宝石数不足 → 剩余宝石被打不过的怪挡 → 偏战力死锁。")
    if blocked:
        print(f"\n  被打不过的怪挡的宝石明细：")
        for (fid, x, y, t) in blocked:
            print(f"    {fid}({x},{y}) {GEM[t][0]}")


if __name__ == "__main__":
    main()
