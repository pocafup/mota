"""【诊断·§S52】beam score_fn 灵敏度判决：窄 beam 下 score_fn 到底改不改终局?

动机：route_aware_phi_probe 三个差异巨大的 score_fn(equiv_hp/现Φ全怪集/更聪明Φ)在 k=8
给出【完全相同】的 max-HP=84。可能①score_fn 真没改变截断(机制旁路)，②碰巧排序一致。
本诊断用【极端】score_fn 隔离机制：纯 +hp(偏好高血) vs 纯 −hp(偏好低血) vs 常数 vs 默认。
若 +hp 与 −hp 给出【相同】goal 前沿 → score_fn 被 beam 保护骨架(item/key Pareto)旁路、
窄 beam 下 score_fn 无力(架构发现)；若不同 → score_fn 有效、Φ 只是不够好。

零产品码改动·纯探针。无 retrograde 前向枚举(快)。
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_astar_smoke import first_enter_mt9, SEAM, seg_step  # noqa: E402
from solver.quotient import search_quotient                           # noqa: E402

DISTINGUISH_DOORS = True


def run(start, beam_k, score_fn, tag):
    t0 = time.time()
    res = search_quotient(start, SEAM, seg_step, max_states=600_000,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=DISTINGUISH_DOORS,
                          beam_score_fn=score_fn, beam_diversity="stairs")
    secs = time.time() - t0
    if not res.found:
        print(f"  k={beam_k:<3} {tag:<26} {secs:5.1f}s  ✗没搜通  cut={res.beam_cut_total}")
        return None
    fr = res.goal_frontier
    mh = max(v.get("hp", 0) for v in fr)
    ma = max(v.get("atk", 0) for v in fr)
    md = max(v.get("def", 0) for v in fr)
    # 前沿 HP 多重集签名(排序后)：完全旁路则三组逐点一致
    hps = tuple(sorted(v.get("hp", 0) for v in fr))
    sig = hash(hps) & 0xffffff
    print(f"  k={beam_k:<3} {tag:<26} {secs:5.1f}s  found  cut={res.beam_cut_total:<5} "
          f"fp={res.distinct_fingerprints:<5} 前沿{len(fr):<3} maxHP={mh:<4} maxATK={ma} maxDEF={md} "
          f"前沿HP签名={sig:06x}")
    return (mh, ma, md, hps)


def main():
    start, idx = first_enter_mt9()
    h0 = start.hero
    print("=" * 96)
    print(f"§S52 beam score_fn 灵敏度判决 · 起点 MT9({h0.x},{h0.y}) "
          f"HP={h0.hp} ATK={h0.atk} DEF={h0.def_} → seam{SEAM}")
    print("=" * 96)

    score_fns = [
        (None,                                   "默认(equiv_hp 区势能)"),
        (lambda s: float(s.hero.hp),             "纯+hp(偏好高血)"),
        (lambda s: -float(s.hero.hp),            "纯−hp(偏好低血·反向)"),
        (lambda s: 0.0,                          "常数0(纯保护骨架+生成序)"),
        (lambda s: float(s.hero.atk * 1000),     "纯+atk×1000(偏好高攻)"),
    ]

    for bk in (8, 24, 64):
        print(f"\n── beam_k={bk} ──")
        results = {}
        for fn, tag in score_fns:
            results[tag] = run(start, bk, fn, tag)
        # 判读：+hp 与 −hp 的前沿 HP 多重集是否一致
        a = results.get("纯+hp(偏好高血)")
        b = results.get("纯−hp(偏好低血·反向)")
        if a and b:
            same = (a[3] == b[3])
            print(f"  >>> +hp vs −hp 前沿HP多重集{'【完全一致】→ score_fn 被旁路' if same else '【不同】→ score_fn 有效'}")

    print("\n" + "=" * 96)
    print("判读：若各 beam_k 下 +hp/−hp/常数/+atk 的 maxHP 与前沿签名全相同 → 窄 beam score_fn 被")
    print("      保护骨架(item/key Pareto 非支配·丢 hp/atk/def 维)旁路，Φ 当 score_fn 在此架构无力。")
    print("      若 +atk 组 maxATK 明显更高 或 −hp 组 maxHP 更低 → score_fn 有效、可继续调 Φ。")
    print("=" * 96)


if __name__ == "__main__":
    main()
