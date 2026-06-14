"""【只读诊断·不入产品链】GA 目标池『顺路 vs 需决策』三分诊断器 —— 为 handoff §S11『剔出顺路必吸目标』出分类表。

只读：只调用封板件 detect_big_items / detect_key_targets / _zone_floor_cells 的现成口径，
绝不改任何文件、不碰基因池(build_min_pool)、不跑 GA 进化。产出分类表供玩家游戏知识终审。

核心：把 detect_key_targets 对【钥匙】做的三分口径，原样套到【剑/盾大件 + 所有宝石】上：
  · 零损血可达          → 顺路（navigate_to 顺手白捡，GA 控制不了顺序）→ 剔出基因池
  · 门拓扑可达但非零损血 → 需决策（要绕路/打守怪付血才到，有"何时取"时机价值）→ 留基因池
  · 门拓扑不可达        → 够不到（每条路被开不起的门锁死）→ 本就不入池
零损血/门拓扑两个可达块的 BFS 与 key_targets._reachable_zerodmg / _reachable_doorwise 【逐行同口径】
(passable: 非墙 + afford 门通 + _combat_damage==0 守怪可穿)，只是把『过滤 key_cells』换成『判定任意目标格』。
自校验：先用本脚本的 block 对钥匙全集重算三分，断言与 detect_key_targets 输出完全一致 → 证明口径未跑偏。
"""
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from solver.fitness import _zone_floor_cells, build_zone1_roster   # noqa: E402
from solver.beam import _combat_damage, build_future_roster        # noqa: E402
from probe_crossfloor import build_start                           # noqa: E402
from vzone import build_zone                                       # noqa: E402
from key_targets import detect_key_targets                         # noqa: E402
from big_item_pull import detect_big_items                         # noqa: E402

_NB4 = ((0, -1), (0, 1), (-1, 0), (1, 0))


def _zerodmg_seen(state, fid, afford):
    """零损血可达格集(raw seen)。口径==key_targets._reachable_zerodmg 的 passable+BFS，只是不过滤 key_cells。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, mid_at, _key_cells, src_cells = info

    def passable(x, y):
        if is_wall(x, y):
            return False
        if (x, y) in mid_at:
            return _combat_damage(state, mid_at[(x, y)]) == 0
        return True

    seen, dq = set(), deque()
    for s in src_cells:
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
    return seen


def _doorwise_seen(state, fid, afford):
    """门拓扑可达格集(raw seen)。口径==key_targets._reachable_doorwise（守怪一律可穿，只看门/墙拓扑）。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, _mid, _key_cells, src_cells = info
    seen, dq = set(), deque()
    for s in src_cells:
        if not is_wall(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not is_wall(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return seen


def _classify(cell, state, afford, zd_cache, dw_cache):
    fid, x, y = cell
    if fid not in zd_cache:
        zd_cache[fid] = _zerodmg_seen(state, fid, afford)
        dw_cache[fid] = _doorwise_seen(state, fid, afford)
    if (x, y) in zd_cache[fid]:
        return "顺路(剔出)"
    if (x, y) in dw_cache[fid]:
        return "需决策(留池)"
    return "够不到(不入池)"


def main():
    start, _ = build_start()
    zone = build_zone()
    _rk, zone_fids, _ak = build_zone1_roster(start)
    roster_big = build_future_roster(start)
    big_cells, tau, ranked = detect_big_items(zone, roster_big, start)
    cands, info = detect_key_targets(start, zone_fids)
    afford = info["afford"]

    zd_cache, dw_cache = {}, {}

    # ── 自校验：本脚本 block 口径对钥匙全集重算三分，须与 detect_key_targets 完全一致 ──
    mism = []
    for cell in sorted(info["all_keys"]):
        mine = _classify(cell, start, afford, zd_cache, dw_cache)
        if cell in info["cheap"]:
            ref = "顺路(剔出)"
        elif cell in cands:
            ref = "需决策(留池)"
        else:
            ref = "够不到(不入池)"
        if mine != ref:
            mism.append((cell, mine, ref))
    print("=" * 80)
    print("自校验：本脚本 block 口径 vs detect_key_targets 钥匙三分 → "
          + ("✅ 全一致(口径未跑偏)" if not mism else f"❌ {len(mism)} 处不一致: {mism}"))
    print(f"  afford 闭包(一区真能开的门色) = {sorted(afford)}")
    print(f"  钥匙三分: 顺路{len(info['cheap'])} 需决策(候选){len(cands)} 够不到{len(info['unreachable'])} "
          f"= 全集{len(info['all_keys'])}")
    print("=" * 80)

    # ── 大件 + 宝石 三分（本方案要分类的对象）──
    print(f"\n大件 big_cells(ΔRP 缝上方) = {sorted(big_cells)}   缝阈 tau={tau:.1f}")
    print(f"ranked 全集(_zone_attr_gems 所有攻防物) = {len(ranked)} 件"
          f"（大件 {len(big_cells)} + 其余宝石 {len(ranked) - len(big_cells)}）\n")
    header = f"{'cell':>16} {'类别':<4} {'da':>3} {'dd':>3} {'ΔRP':>10}  零损血 门拓扑  → 分类"
    print(header)
    print("-" * 72)
    counts = {"顺路(剔出)": 0, "需决策(留池)": 0, "够不到(不入池)": 0}
    kind_cls = {}   # (kind) -> list of (cell, cls)
    for (drp, cell, da, dd) in ranked:
        is_big = cell in big_cells
        kind = ("剑" if is_big and da > 0 else "盾" if is_big and dd > 0
                else "大件" if is_big else "宝石")
        cls = _classify(cell, start, afford, zd_cache, dw_cache)
        counts[cls] += 1
        kind_cls.setdefault(kind, []).append((cell, cls))
        fid, x, y = cell
        zd = "是" if (x, y) in zd_cache[fid] else " ·"
        dw = "是" if (x, y) in dw_cache[fid] else " ·"
        flag = "   ◀★剑" if kind == "剑" else "   ◀★盾" if kind == "盾" else ""
        print(f"{str(cell):>16} {kind:<4} {da:>3} {dd:>3} {drp:>10.1f}   {zd:^4} {dw:^4}  → {cls}{flag}")
    print("-" * 72)
    print(f"汇总：顺路(剔出) {counts['顺路(剔出)']} | 需决策(留池) {counts['需决策(留池)']} | "
          f"够不到(不入池) {counts['够不到(不入池)']}")

    # ── 重点确认行 ──
    print("\n重点确认：")
    for kind in ("剑", "盾"):
        for cell, cls in kind_cls.get(kind, []):
            print(f"  {kind} {cell} → {cls}")
    gem_keep = [c for c, cl in kind_cls.get("宝石", []) if cl == "需决策(留池)"]
    gem_drop = [c for c, cl in kind_cls.get("宝石", []) if cl == "顺路(剔出)"]
    gem_unreach = [c for c, cl in kind_cls.get("宝石", []) if cl == "够不到(不入池)"]
    print(f"  宝石 需决策(留池) {len(gem_keep)}: {sorted(gem_keep)}")
    print(f"  宝石 顺路(剔出)  {len(gem_drop)}: {sorted(gem_drop)}")
    print(f"  宝石 够不到      {len(gem_unreach)}: {sorted(gem_unreach)}")

    # ── 当前写死 MIN_GEMS 三个落哪类（方案要替换它）──
    from ga_loop import MIN_GEMS
    print(f"\n当前 ga_loop.MIN_GEMS(写死3宝石) 各落哪类：")
    for g in MIN_GEMS:
        print(f"  {g} → {_classify(g, start, afford, zd_cache, dw_cache)}")


if __name__ == "__main__":
    main()
