"""【只读诊断·不入产品链】去盾(深主线)导航·顺路吸『非目标』精确清单 —— 为基因池剔除出最终确认表。

只读：只调封板件 navigate_to 跑一次【去盾】实测，绝不改任何文件、不碰基因池、不跑 GA。
判据(玩家定·选项1·以核心深主线盾为准)：剑的顺路性是【条件性】的，条件=基因含盾(689 轴心)；
  在 GA 真正关心的所有含盾好解里，剑 100% 被吸。分母不取『所有主目标平均』(那会被浅目标稀释成假象 14%)，
  只取『GA 真正会走的最深主线=去盾』。
★区分钉死：去盾导航中，盾是【目标本身】(不算顺路吸、绝不自剔)；其余被 _taken 的候选才是『非目标顺路吸』→剔出。
  未被吸的候选=需显式去取=留池。产出『剔除清单(非目标顺路吸) + 盾明确留 + 其余留池』供玩家终审。
"""
import sys
import time
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
from big_item_pull import detect_big_items                # noqa: E402


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

    shield = next(c for (_d, c, _a, dd) in ranked if c in big_cells and dd > 0)
    sword = next(c for (_d, c, da, _dd) in ranked if c in big_cells and da > 0)
    meta = {c: (drp, da, dd) for (drp, c, da, dd) in ranked}

    def label(c):
        is_big = c in big_cells
        da, dd = meta[c][1], meta[c][2]
        return "剑" if is_big and da > 0 else "盾" if is_big and dd > 0 else "宝石"

    print(f"电池组就绪 {time.time() - t0:.1f}s")
    print(f"深主线导航目标(分母) = 盾 {shield}   剑 {sword}")
    print(f"ranked 候选全集 = {len(ranked)} 件（剑+盾 2 大件 + {len(ranked) - 2} 宝石）\n")

    # ── 跑【一次】去盾导航，记录终态吸了哪些候选 ──
    t = time.time()
    final, moves, reached = navigate_to(start, shield, zone, step, cache=None)
    if not reached:
        print(f"❌ 去盾够不到（原子失败），无法判定。{time.time() - t:.1f}s")
        return
    fh = final.hero
    print(f"去盾 reached：steps={len(moves)}  终态 ATK={fh.atk} DEF={fh.def_} HP={fh.hp}  "
          f"{time.time() - t:.1f}s\n")

    # ── 逐候选分类：目标本身(盾) / 非目标顺路吸(剔出) / 未被吸(留池) ──
    drop, keep_onway, keep_target = [], [], []
    print(f"{'cell':>16} {'类别':<4} {'da':>3} {'dd':>3}  去盾时状态     → 处置")
    print("-" * 60)
    for (drp, c, da, dd) in ranked:
        kind = label(c)
        if c == shield:
            cls, bucket = "目标本身·留池", keep_target
            state_s = "导航目标本身"
        elif _taken(final, c):
            cls, bucket = "非目标顺路吸·剔出", drop
            state_s = "被顺路 _absorb"
        else:
            cls, bucket = "未被吸·留池", keep_onway
            state_s = "未吸(需显式取)"
        bucket.append(c)
        flag = "  ◀★剑" if kind == "剑" else "  ◀★盾" if kind == "盾" else ""
        print(f"{str(c):>16} {kind:<4} {da:>3} {dd:>3}  {state_s:<12} → {cls}{flag}")
    print("-" * 60)

    # ── 最终确认表 ──
    print("\n" + "=" * 60)
    print("【最终剔除清单】去盾深主线导航中『非目标顺路吸』→ 基因池剔出：")
    for c in drop:
        print(f"    剔出  {str(c):>16}  [{label(c)}]  非目标顺路吸")
    print(f"\n【明确留池】")
    print(f"    留(目标本身)  {str(shield):>16}  [盾]  去盾导航的目标本身，绝不自剔")
    print(f"    留(需显式取)  其余 {len(keep_onway)} 件宝石（去盾时未被顺路吸）：")
    for c in keep_onway:
        print(f"        {str(c):>16}  [{label(c)}]")
    print("=" * 60)
    print(f"\n汇总：剔出 {len(drop)} | 留池(目标本身) {len(keep_target)} | 留池(需显式取) {len(keep_onway)}"
          f"  = ranked 全集 {len(ranked)}")
    print(f"总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
