"""【只读诊断·不入产品链】剑早拿 vs 晚拿·fitness 对照 —— 验证①（玩家 2026-06-14 推翻"剔剑"后）

只读：只调封板件 navigate_to / decode / fitness 跑对照，绝不改任何文件、不碰基因池、不跑 GA 进化。
动机：玩家铁证(GA 真产出过"先 MT4 钥匙、没早拿剑"的次优路线)推翻"剑顺路必吸=自欺空排"前提——
  那条次优路线存在 ⟺ 剑排序有真实影响 ⟺ 剑不该剔。真问题=GA 没搜出"先拿剑更优"(搜索力问题)。
本脚本查 fitness 这指南针对不对：构造剑早/晚对照基因，看 fitness 是否给"先拿剑"更高分
  (剑减伤大→后续打怪损血少→终态 HP/属性更好)。
  · 组1(无盾·剑+5钥)：剑前置=去 MT4 钥(不吸剑)→剑真晚拿，隔离"剑早vs晚"。期望 fit(剑早)>fit(剑晚)。
  · 组2(含盾)：剑放盾前 vs 盾前置→盾腿顺路吸剑(§S11 自欺)，两者 decode 终态≈同→fit≈同。
    演示"含盾解里剑排序失效"=为什么需要§S11规整(剔除会连无盾解的有效排序一起杀掉)。
逐目标 trace(复刻 decode 的 navigate_to 串)记录【剑/盾何时被吸+当步属性】→ 看清剑实际第几腿进包。
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

from ga_loop import build_harness          # noqa: E402
from ga_navigate import navigate_to        # noqa: E402
from solver.fitness import fitness         # noqa: E402


def _taken(state, cell):
    fid, x, y = cell
    fl = state.floors.get(fid)
    return fl is not None and fl.entities[y][x] == 0


def _trace(gene, start, zone, step, sword, shield, cache):
    """复刻 decode 的逐目标 navigate_to 串，逐腿记录剑/盾是否已被吸 + 当步属性。"""
    cur = start
    rows = []
    for i, goal in enumerate(gene):
        final, moves, reached = navigate_to(cur, goal, zone, step, cache=cache)
        if reached:
            cur = final
        rows.append((i, goal, reached, len(moves) if reached else None,
                     _taken(cur, sword), _taken(cur, shield),
                     cur.hero.atk, cur.hero.def_, cur.hero.hp))
        if cur.dead or cur.won:
            break
    return rows, cur


def main():
    t0 = time.time()
    h = build_harness()
    start, zone, step = h["start"], h["zone"], h["step"]
    cache = h["decode_cache"]
    roster_fit, big, zone_fids = h["roster_fit"], h["big"], h["zone_fids"]
    sword, shield = h["meta"]["sword"], h["meta"]["shield"]
    keys, gems = h["meta"]["keys"], h["meta"]["gems"]
    print(f"电池组就绪 {time.time() - t0:.1f}s   剑={sword} 盾={shield}")
    print(f"5 钥={keys}\n3 宝={gems}\n")

    groups = [
        ("组1·无盾（隔离剑早 vs 晚·前置去钥不吸剑）", [
            ("X1 剑早 [剑,5钥]", [sword] + keys),
            ("Y1 剑晚 [5钥,剑]", keys + [sword]),
        ]),
        ("组2·含盾（演示 §S11 自欺：盾腿顺路吸剑）", [
            ("X2 剑在盾前 [剑,盾,5钥,3宝]", [sword, shield] + keys + gems),
            ("Y2 盾在剑前 [盾,剑,5钥,3宝]", [shield, sword] + keys + gems),
        ]),
    ]

    fits = {}
    for gname, genes in groups:
        print("═" * 72)
        print(f"  {gname}")
        print("═" * 72)
        for label, gene in genes:
            t = time.time()
            rows, final = _trace(gene, start, zone, step, sword, shield, cache)
            fit = fitness(final, roster_fit, big, zone_fids, w_potion=1.5, w_key=39.0)
            assert abs(fit - h["eval_fn"](gene)) < 1e-9, "trace 终态与封板 decode 不一致！"
            fits[label] = fit
            sword_leg = next((i for (i, *_r) in rows if _r[3]), None)  # 第一个 sw=True 的腿 index
            print(f"\n{label}   （剑第 {sword_leg} 腿进包）")
            for (i, goal, reached, steps, sw, sh, atk, df, hp) in rows:
                rs = f"steps={steps:>4}" if reached else "够不到  "
                mark = ""
                if sw and (i == sword_leg):
                    mark = "  ◀剑进包"
                print(f"    腿{i} →{str(goal):>15} {('reached ' if reached else '✗skip   ')}{rs}  "
                      f"剑{'✔' if sw else '·'} 盾{'✔' if sh else '·'}  "
                      f"ATK={atk:>2} DEF={df:>2} HP={hp:>5}{mark}")
            print(f"    ⇒ fitness = {fit:.1f}   终态 ATK={final.hero.atk} DEF={final.hero.def_} "
                  f"HP={final.hero.hp}  ({time.time() - t:.1f}s)")
        print()

    # ── 组内对比结论 ──
    print("═" * 72)
    print("  对比结论")
    print("═" * 72)
    d1 = fits["X1 剑早 [剑,5钥]"] - fits["Y1 剑晚 [5钥,剑]"]
    print(f"组1 无盾：fit(剑早 X1)={fits['X1 剑早 [剑,5钥]']:.1f}  "
          f"vs  fit(剑晚 Y1)={fits['Y1 剑晚 [5钥,剑]']:.1f}   Δ={d1:+.1f}")
    print(f"   → {'✅ 剑早更高·fitness 指南针对(剑减伤价值算进去了)' if d1 > 0 else '⚠ 剑早未更高·疑 fitness 没算剑减伤价值，需查 fitness' if d1 < 0 else '＝ 完全相等·剑顺序在此子问题无 fitness 差异'}")
    d2 = fits["X2 剑在盾前 [剑,盾,5钥,3宝]"] - fits["Y2 盾在剑前 [盾,剑,5钥,3宝]"]
    print(f"组2 含盾：fit(剑在盾前 X2)={fits['X2 剑在盾前 [剑,盾,5钥,3宝]']:.1f}  "
          f"vs  fit(盾在剑前 Y2)={fits['Y2 盾在剑前 [盾,剑,5钥,3宝]']:.1f}   Δ={d2:+.1f}")
    print(f"   → {'✅ ≈相等=§S11 自欺确认(盾腿吸剑致剑排序在含盾解里失效)' if abs(d2) < 1e-6 else '两者有别(剑排序在含盾解仍有残余影响)'}")

    print(f"\n总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
