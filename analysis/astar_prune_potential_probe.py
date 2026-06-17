"""【§S34 A*化前置·只读探针】坐实"带界 A* 能不能砍下穷尽 553s"——动封板 quotient.py 前的命门。

背景：search_quotient 现为 wave-BFS 穷尽（MT9→seam 553s / distinct_fp~21488）。A*化的真提速【必须靠
剪枝】——纯把 wave-FIFO 换 best-first 优先队列只改展开【顺序】、状态数不变、不提速。最自然的无损剪
= 分支定界：一旦有 seam 到达态、其 max-HP=H*，任何"乐观 HP 上界 ≤ H*"的态【不可能】再产出非支配的
max-HP 出口 → 可剪、不展开。本探针【不改产品码】，用现成 on_admit 钩子收集每个入队态的 HP，量：

  ① H* = 出口前沿 max-HP（界的阈值）
  ② 入队态 HP 分布（相对 H* 的长尾有多长 = 剪枝潜力的直接体现）
  ③ 对一组"最大可达增益界" Δ：满足 HP_now + Δ ≤ H* 的入队态占比（= 增益≤Δ 时【保证可剪】的下界）
     —— 不读血瓶数值结构（避免猜数据）、用 Δ 扫描括住任意增益界下的剪枝率。

判读：若大 Δ（如 ≥1000）下仍有可观占比可剪 → 带界 A* 值得建（能砍 553s）；若 Δ 一抬占比就塌到 ~0
→ 入队态普遍贴近 H*、界剪不动 → A* 提速得换思路（有界队列/全局 beam，非无损界）。

⚠ 多维 Pareto 警示：HP 只是主轴；低 HP 态可能靠钥匙/道具维存活为非支配出口。本探针量的是【HP 单轴
界】的剪枝潜力（smoke 的头条就是 max-HP 出口）；多维无损界更弱，故本数是【乐观上界】。同时报入队态
钥匙/道具持有量，标注多维 caveat。

只读·复用 seam_astar_smoke 的已验证 harness（first_enter_mt9 / SEAM / seg_step）。
用法：python -u analysis/astar_prune_potential_probe.py [--max-states 600000]
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_astar_smoke import first_enter_mt9, SEAM, seg_step  # noqa: E402
from solver.quotient import search_quotient, _free_cells              # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=600_000)
    args = ap.parse_args()

    print("=" * 78)
    print("§S34 A*化前置只读探针：带界 A* 剪枝潜力（MT9→seam·穷尽 on_admit 收 HP）")
    print("=" * 78)

    mt9, idx = first_enter_mt9()
    if mt9 is None:
        print("🛑 存档里没找到 MT9")
        sys.exit(1)
    h0 = mt9.hero
    print(f"起点 = 真实存档第一次进 MT9：token[{idx}]  "
          f"{mt9.current_floor}({h0.x},{h0.y}) HP={h0.hp} ATK={h0.atk} DEF={h0.def_}")
    print(f"起点自由块大小={len(_free_cells(mt9))}")

    # on_admit 收每个入队态的 HP + 持有标量（只存标量·不存态·省内存）
    admit = []   # (floor, hp, n_keys, n_items)

    def on_admit(child, _acts):
        hh = child.hero
        nk = sum(v for v in hh.keys.values() if isinstance(v, (int, float)))
        ni = sum(v for v in hh.items.values() if isinstance(v, (int, float)))
        admit.append((child.current_floor, hh.hp, nk, ni))

    print("\n穷尽搜（cross_floor 限{MT9,MT10}·beam_k=None·distinguish_doors=True）... 跑约几分钟", flush=True)
    t0 = time.time()
    res = search_quotient(mt9, SEAM, seg_step, max_states=args.max_states,
                          cross_floor=True, beam_k=None, distinguish_doors=True,
                          on_admit=on_admit)
    secs = time.time() - t0

    print(f"\n  found={res.found}  耗时 {secs:.1f}s  hit_cap={res.hit_cap}")
    print(f"  distinct_fp={res.distinct_fingerprints}  states_expanded={res.states_expanded}  "
          f"states_generated={res.states_generated}  goal_hits={res.goal_hits}")
    print(f"  on_admit 收到入队态={len(admit)}（≈ distinct_fp−1·start 不进 on_admit）")
    print(f"  各层指纹 fp_by_floor={dict(res.fp_by_floor)}")

    if not res.found:
        print("\n  ✗ 没搜通（found=False）→ 无 H* 界，探针不适用")
        sys.exit(0)

    fr = res.goal_frontier
    hstar = max(v.get("hp", 0) for v in fr)
    print(f"\n  ★出口前沿点数={len(fr)}  H*（max-HP 出口）={hstar}")
    print("  前沿（按 HP 降序）：")
    for v in sorted(fr, key=lambda v: -v.get("hp", 0)):
        kk = {k.split(":", 1)[1]: v[k] for k in v if k.startswith("key:") and v[k]}
        print(f"     HP={v.get('hp'):>4} ATK={v.get('atk'):>3} DEF={v.get('def'):>3} 钥={kk}")

    # ── 入队态 HP 分布 ──────────────────────────────────────────────
    hps = sorted(hp for (_f, hp, _k, _i) in admit)
    n = len(hps)
    if n:
        def pct(p):
            return hps[min(n - 1, int(p * n))]
        print(f"\n  入队态 HP 分布（n={n}）：min={hps[0]} p10={pct(.1)} p25={pct(.25)} "
              f"中位={pct(.5)} p75={pct(.75)} p90={pct(.9)} max={hps[-1]}")
        # 按层拆
        from collections import Counter
        byf = Counter(f for (f, _h, _k, _i) in admit)
        print(f"  入队态按层：{dict(byf)}")

    # ── 增益界 Δ 扫描：HP_now + Δ ≤ H* 的占比（= 增益≤Δ 时保证可剪的入队态下界）──
    print(f"\n  ★带界 A* 剪枝潜力（满足 HP_now + Δ ≤ H*={hstar} → 增益≤Δ 时【保证可剪】）：")
    print(f"  {'Δ(最大可达增益界)':>18} | {'可剪入队态':>10} | {'占比':>7}")
    print("  " + "-" * 44)
    for d in (0, 100, 200, 400, 600, 800, 1000, 1500, 2000, 3000):
        cut = sum(1 for hp in hps if hp + d <= hstar)
        print(f"  {d:>18} | {cut:>10} | {cut / n * 100:>6.1f}%")

    # ── 多维 caveat：低 HP 入队态里有多少握着钥匙/道具（可能靠多维存活、HP 单轴界会误判）──
    low = [(hp, k, i) for (_f, hp, k, i) in admit if hp + 1000 <= hstar]
    if low:
        with_res = sum(1 for (_h, k, i) in low if k or i)
        print(f"\n  ⚠多维 caveat：HP_now+1000≤H* 的低血入队态 {len(low)} 个中、"
              f"{with_res} 个仍握钥匙/道具（{with_res/len(low)*100:.1f}%）")
        print("    → 这些在【HP 单轴界】下被算可剪、但多维无损界下可能因钥匙/道具维非支配而【不可剪】。")
        print("    → 故上表占比是 HP 单轴【乐观上界】；多维无损界的真实剪枝率 ≤ 此。")

    print("\n" + "=" * 78)
    print(f"【判读】穷尽 {secs:.1f}s / 入队 {n} 态。大 Δ(≥1000) 下可剪占比若仍可观 → 带界 A* 值得建；"
          f"若 Δ 一抬就塌→换有界队列/全局 beam。")
    print("=" * 78)


if __name__ == "__main__":
    main()
