"""【只读诊断·不入产品链】动态实测·剑/盾/宝石『顺路 vs 需决策』分类器（玩家选项1·2026-06-14）。

只读：只调封板件 navigate_to / detect_big_items / detect_key_targets 跑实测，绝不改任何文件、
不碰基因池(build_min_pool)、不跑 GA 进化。产出带『普遍性比例 + 依据』的分类表供玩家游戏知识终审。

判据（玩家定）：候选目标(剑/盾/14宝石)是否『顺路必吸』，看它在【主目标集 M 的真 navigate_to 导航路径上
被顺路吸的普遍性】——不是『去某一个目标碰巧被吸』就算顺路，要看它在【多个主目标导航中被吸的普遍性】。
  · 主目标集 M = 盾(big_cells 里 dd>0) + 代价钥匙代表(detect_key_targets 候选②·每层取坐标最小 1 把)。
    M 全从 detect_* 涌现取，不写死坐标；钥匙候选每层 1 代表 = 玩家说的『若干代表』、跨层覆盖、控时间。
  · 被吸普遍性 ratio(c) = (去 M 里【非 c】主目标时 c 被顺路吸的腿数) / (M 里【非 c】reached 的腿数)。
    ratio 高 → 顺路必吸(剔出)；ratio≈0 → 只有显式去它才拿到=需决策(留池)。阈值建议 0.5，但 dump 原始
    比例 + 每条腿明细 → 玩家终审(尤其 14 宝石哪些真顺路)。
高效：每个主目标 m 只跑【一次】navigate_to、记下该腿吸了哪些候选 → 再统计每候选被吸于多少 m（|M| 次 nav，
  非 |候选|×|M|）。navigate_to/detect_* 一字不动；被剔目标 navigate_to 仍顺路吸(不当 GA 排序目标≠不拿)。
"""
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start                  # noqa: E402
from vzone import build_zone                              # noqa: E402
from ga_navigate import navigate_to                       # noqa: E402
from sim.simulator import step                            # noqa: E402
from solver.fitness import build_zone1_roster            # noqa: E402
from solver.beam import build_future_roster               # noqa: E402
from key_targets import detect_key_targets                # noqa: E402
from big_item_pull import detect_big_items                # noqa: E402

THRESHOLD = 0.5   # 建议阈值（dump 原始比例，玩家终审）


def _taken(state, cell):
    fid, x, y = cell
    fl = state.floors.get(fid)
    return fl is not None and fl.entities[y][x] == 0


def main():
    t0 = time.time()
    start, _ = build_start()
    zone = build_zone()
    _rk, zone_fids, _ak = build_zone1_roster(start)
    roster_big = build_future_roster(start)
    big_cells, tau, ranked = detect_big_items(zone, roster_big, start)
    cands, info = detect_key_targets(start, zone_fids)

    shield = next(c for (_d, c, _a, dd) in ranked if c in big_cells and dd > 0)
    sword = next(c for (_d, c, da, _dd) in ranked if c in big_cells and da > 0)

    # 主目标集 M = 盾 + 候选钥匙每层坐标最小 1 把（涌现取、不写死）
    by_floor = defaultdict(list)
    for c in cands:
        by_floor[c[0]].append(c)
    key_reps = [sorted(v)[0] for _k, v in sorted(by_floor.items())]
    M = [shield] + key_reps

    candidate_cells = [cell for (_d, cell, _a, _dd) in ranked]   # 剑/盾 + 14 宝石
    meta = {c: (drp, da, dd) for (drp, c, da, dd) in ranked}

    print(f"电池组就绪 {time.time() - t0:.1f}s")
    print(f"剑={sword}  盾={shield}")
    print(f"主目标集 M({len(M)}) = 盾 + 候选钥匙每层代表:")
    print(f"  盾 {shield}")
    print(f"  钥匙代表 {key_reps}\n")

    # ── 每个主目标只跑一次 navigate_to，记录该腿吸了哪些候选 ──
    m_taken = {}     # m -> frozenset(被吸候选)
    m_meta = {}      # m -> (steps, atk, def_)
    print("跑 navigate_to（每主目标一次）…")
    for m in M:
        t = time.time()
        final, moves, reached = navigate_to(start, m, zone, step, cache=None)
        if reached:
            ts = frozenset(c for c in candidate_cells if _taken(final, c))
            m_taken[m] = ts
            m_meta[m] = (len(moves), final.hero.atk, final.hero.def_)
            print(f"  {str(m):>16} reached steps={len(moves):>4} 吸候选{len(ts):>2}件  "
                  f"ATK={final.hero.atk} DEF={final.hero.def_}  {time.time() - t:.1f}s")
        else:
            print(f"  {str(m):>16} 够不到·跳过                          {time.time() - t:.1f}s")
    print()

    # ── 分类每个候选：被吸普遍性 ratio（排除自指 m==c）──
    def label(c):
        is_big = c in big_cells
        da, dd = meta[c][1], meta[c][2]
        return "剑" if is_big and da > 0 else "盾" if is_big and dd > 0 else "宝石"

    rows = []
    for (drp, c, da, dd) in ranked:
        others = [m for m in m_taken if m != c]
        votes = [m for m in others if c in m_taken[m]]
        ratio = len(votes) / len(others) if others else 0.0
        cls = "顺路(剔出)" if ratio >= THRESHOLD else "需决策(留池)"
        rows.append((c, label(c), da, dd, ratio, votes, others, cls))

    header = f"{'cell':>16} {'类别':<4} {'da':>2} {'dd':>2}  被吸普遍性     → 分类"
    print(header)
    print("-" * 64)
    counts = defaultdict(int)
    for (c, kind, da, dd, ratio, votes, others, cls) in rows:
        counts[cls] += 1
        flag = "  ◀★剑" if kind == "剑" else "  ◀★盾" if kind == "盾" else ""
        print(f"{str(c):>16} {kind:<4} {da:>2} {dd:>2}  {len(votes):>2}/{len(others):<2} ={ratio:>4.0%}  "
              f"→ {cls}{flag}")
    print("-" * 64)
    print(f"汇总：顺路(剔出) {counts['顺路(剔出)']} | 需决策(留池) {counts['需决策(留池)']}"
          f"   (阈值 {THRESHOLD:.0%})")

    # ── 重点确认 + 依据明细 ──
    print("\n重点确认（依据=在哪些主目标导航中被吸/不被吸）：")
    for (c, kind, da, dd, ratio, votes, others, cls) in rows:
        if kind in ("剑", "盾"):
            print(f"  {kind} {c} → {cls}  ({ratio:.0%})")
            print(f"      被吸于: {votes}")
            print(f"      未被吸: {[m for m in others if m not in votes]}")
    print("\n  14 宝石明细：")
    for (c, kind, da, dd, ratio, votes, others, cls) in rows:
        if kind == "宝石":
            prop = "ATK+%d" % da if da > 0 else "DEF+%d" % dd
            print(f"    {str(c):>16} [{prop}] {ratio:>4.0%}  {cls:<12} 被吸于{len(votes)}/{len(others)}: {votes}")

    print(f"\n总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
