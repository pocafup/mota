"""【只读诊断·方向3(分层摘要)评估】分解 MT7 组合爆炸的维度。

回答：MT7 的 37 万节点是 ——
  (A) 指纹多（层内进度爆炸：杀哪些怪/开哪些门的不同子集 → 不同自由块/flags），还是
  (B) 价值向量多（携带资源组合爆炸：同一层内位置/进度，但带着各种 hp/atk/def/钥匙/道具组合）？
并看哪些价值维（hp/atk/def/mdef/gold/key:*/item:*）撑起 MT7 的多样性。

为什么关键：方向3 摘要要把 MT7 压成"几个高价值点"。
  若主因=(B) 价值向量 → 摘要须压价值维 Pareto 前沿，但**阈值非线性**(CLAUDE.md 铁律)下分桶有丢解风险；
  若主因=(A) 指纹 → 摘要须压"层内进度子集"，不同进度后续不同 → 无损更难。
本脚本只读·复用 forward_enumerate + redkey 配置·不碰产品码。
用法：python -u analysis/_mt7_explosion_diag.py [--max-states N] [--floor MT7]
"""
import argparse
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_retrograde_v_probe import forward_enumerate                         # noqa: E402
from analysis.dir2_redkey_pathloss_beam import (replay_to_token, make_seg_step,        # noqa: E402
                                                TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=300_000)
    ap.add_argument("--floor", type=str, default="MT7", help="重点分解哪层")
    args = ap.parse_args()

    print("=" * 80)
    print(f"MT7 爆炸维度诊断 (redkey 段·max_states={args.max_states}·重点层={args.floor})")
    print("=" * 80, flush=True)
    start = replay_to_token(TOK_SHIELD)
    seg_step = make_seg_step(REAL_LEG_FLOORS)
    h = start.hero
    print(f"起点 {start.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"goal={REDKEY_CELL}", flush=True)

    t0 = time.time()
    g = forward_enumerate(start, REDKEY_CELL, seg_step, args.max_states, False)
    print(f"前向 {time.time() - t0:.1f}s | 节点={g['n']} distinct_fp={g['distinct_fp']} "
          f"生成={g['gen']} hit_cap={g['hit_cap']}", flush=True)

    visited = g["visited"]   # {fp: [vec, ...]}（fp 已是 _qfp 元组·vec 是 value_vector dict）
    fp_by_floor = Counter(fp[0] for fp in visited)
    node_by_floor = Counter()
    for fp, vecs in visited.items():
        node_by_floor[fp[0]] += len(vecs)

    print("\n【每层：指纹数 / 节点数(fp×vec) / 平均 Pareto 厚度】")
    for fl in sorted(node_by_floor, key=lambda x: -node_by_floor[x]):
        nfp = fp_by_floor[fl]
        nn = node_by_floor[fl]
        print(f"  {fl:>5}: fp={nfp:>7} 节点={nn:>8} 厚度={nn / max(nfp, 1):.1f}")

    # ── 重点层爆炸维度分解 ──
    F = args.floor
    f_fps = [fp for fp in visited if fp[0] == F]
    f_vecs = [v for fp in f_fps for v in visited[fp]]
    print(f"\n【{F} 分解】指纹={len(f_fps)} 节点(价值向量)={len(f_vecs)}")
    if f_fps:
        thick = sorted(len(visited[fp]) for fp in f_fps)
        avg = len(f_vecs) / len(f_fps)
        print(f"  Pareto 厚度: min={thick[0]} 中位={thick[len(thick) // 2]} "
              f"max={thick[-1]} 平均={avg:.1f}")
        # 厚度直方
        hist = Counter()
        for t in thick:
            b = "1" if t == 1 else "2-5" if t <= 5 else "6-20" if t <= 20 else "21-100" if t <= 100 else "100+"
            hist[b] += 1
        print(f"  厚度分布: {dict(hist)}")

        # 各价值维 distinct 取值数（撑多样性的维 = 价值向量爆炸的来源）
        dims = defaultdict(set)
        for v in f_vecs:
            for k, val in v.items():
                dims[k].add(val)
        print(f"  各价值维 distinct 取值数（{F} 价值向量在哪些维上分裂）：")
        for k in sorted(dims, key=lambda x: -len(dims[x])):
            vals = sorted(dims[k])
            rng = f"[{vals[0]}..{vals[-1]}]" if len(vals) > 1 else f"={vals[0]}"
            print(f"    {k:>12}: {len(dims[k]):>5} 种 {rng}")

        print("\n【判读】")
        if avg > 5:
            print(f"  → {F} 爆炸主因 = (B)价值向量(资源组合)：平均每指纹挂 {avg:.1f} 个非支配向量")
            print("     摘要须压价值维 Pareto 前沿；阈值非线性下分桶有丢解风险（看上面哪维分裂最多）")
        else:
            print(f"  → {F} 爆炸主因 = (A)指纹(层内进度)：指纹 {len(f_fps)} 多·每指纹仅 {avg:.1f} 向量")
            print("     摘要须压层内进度子集（杀怪/开门组合）；不同进度后续不同 → 无损更难")


if __name__ == "__main__":
    main()
