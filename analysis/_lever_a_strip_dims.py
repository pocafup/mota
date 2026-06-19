"""【Lever A·只读验证】删 gold+kill 死维后，MT7 / 全段 Pareto 厚度砍到多少。

§S49 拍板：gold 是确凿死维（redkey 段内无商店·forward_enumerate 第117行
`child.floor._event_intercepting: continue`=allow_purchase=False），kill 几乎肯定
死维（已体现在 hp/atk·不 gate 任何门/事件）。删之【无损】（绝不丢最优解）、顺手压厚度。

做法（只读·不碰产品码·不 monkeypatch）：
  跑一次原版 6 维 forward_enumerate 得 visited={fp:[vec,...]}（=每 fp 的 6 维 Pareto 前沿），
  再对每个 fp 的前沿【删指定维后重做 Pareto 去重】，数新厚度。

为何后处理而非删维重跑：对固定可达 vec 集 S，有
  Pareto_strip(Pareto_full(S)) == Pareto_strip(S)   （投影保持支配·见下证）
所以对【同一批枚举出的节点】，后处理给出的删维厚度【精确等于】当初用少维去重的厚度——
干净隔离"删维压厚度"的纯效应，不被 hit_cap 下探索区域差异污染；且 distinct_fp 严格不变
（_qfp 不含价值维），当场坐实 §S49"删维治不了 6262 指纹主因"。

证（投影保支配）：若 y 在全维支配 x（y≥x 每维），则删掉若干维后 y 在剩余维仍≥x。故
全维前沿外被支配的点，删维后仍被同一支配者支配 → 不会"复活"进删维前沿。⇒ 上式成立。

用法：python -u analysis/_lever_a_strip_dims.py [--max-states N]
"""
import argparse
import os
import sys
import time
from collections import Counter

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_retrograde_v_probe import forward_enumerate                          # noqa: E402
from analysis.dir2_redkey_pathloss_beam import (replay_to_token, make_seg_step,         # noqa: E402
                                                TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS)
from solver.search import _ge_all                                                       # noqa: E402

DROPS = {
    "原版6维": frozenset(),
    "删gold": frozenset({"gold"}),
    "删kill": frozenset({"kill"}),
    "删gold+kill": frozenset({"gold", "kill"}),
}


def repareto(vecs, drop):
    """删 drop 维后对 vecs 重做 Pareto 去重，返回新前沿（含等值合并）。"""
    if not drop:
        return list(vecs)
    front = []
    for vec in vecs:
        sv = {k: v for k, v in vec.items() if k not in drop}
        if any(_ge_all(f, sv) for f in front):   # 被已有点支配-或-等于 → 丢
            continue
        front = [f for f in front if not _ge_all(sv, f)]
        front.append(sv)
    return front


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=300_000)
    args = ap.parse_args()

    print("=" * 84)
    print(f"Lever A 死维删除验证 (redkey 段·max_states={args.max_states})")
    print("=" * 84, flush=True)
    start = replay_to_token(TOK_SHIELD)
    seg_step = make_seg_step(REAL_LEG_FLOORS)
    h = start.hero
    print(f"起点 {start.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"goal={REDKEY_CELL}", flush=True)

    t0 = time.time()
    g = forward_enumerate(start, REDKEY_CELL, seg_step, args.max_states, False)
    print(f"前向 {time.time() - t0:.1f}s | 节点={g['n']} distinct_fp={g['distinct_fp']} "
          f"生成={g['gen']} hit_cap={g['hit_cap']}", flush=True)

    visited = g["visited"]   # {fp: [vec, ...]}（fp[0]=楼层·vec=value_vector dict）

    # 每层 / 每档：fp 数（不变）、节点数(=厚度和)、平均厚度
    floors = sorted({fp[0] for fp in visited})
    fp_by_floor = Counter(fp[0] for fp in visited)
    # node_by[floor][drop_name] = 删该维后该层总节点数
    node_by = {fl: {} for fl in floors}
    total_nodes = {name: 0 for name in DROPS}
    for fp, vecs in visited.items():
        fl = fp[0]
        for name, drop in DROPS.items():
            cnt = len(repareto(vecs, drop))
            node_by[fl][name] = node_by[fl].get(name, 0) + cnt
            total_nodes[name] += cnt

    names = list(DROPS)
    # ── 每层厚度对比表 ──
    print("\n【每层 Pareto 厚度（节点/指纹）·各删维档对比】")
    head = f"  {'层':>5} {'指纹':>7} | " + " ".join(f"{n:>11}" for n in names)
    print(head)
    print("  " + "-" * (len(head) - 2))
    for fl in sorted(floors, key=lambda x: -node_by[x]["原版6维"]):
        nfp = max(fp_by_floor[fl], 1)
        cells = []
        for n in names:
            th = node_by[fl][n] / nfp
            cells.append(f"{th:>11.2f}")
        print(f"  {fl:>5} {fp_by_floor[fl]:>7} | " + " ".join(cells))

    # ── 全段汇总 ──
    print("\n【全段汇总】")
    print(f"  distinct_fp = {g['distinct_fp']}（各档恒等·删价值维不改 _qfp 指纹 → 坐实"
          f"§S49：删 gold/kill 治不了指纹主因）")
    base = total_nodes["原版6维"]
    print(f"  {'档':>12} {'总节点(fp×vec)':>16} {'平均厚度':>10} {'相对原版':>10}")
    for n in names:
        tn = total_nodes[n]
        avg = tn / max(g['distinct_fp'], 1)
        pct = 100.0 * (base - tn) / max(base, 1)
        tag = "—" if n == "原版6维" else f"-{pct:.1f}%"
        print(f"  {n:>12} {tn:>16} {avg:>10.2f} {tag:>10}")

    # ── MT7 重点 ──
    if "MT7" in node_by:
        nfp7 = max(fp_by_floor["MT7"], 1)
        print(f"\n【MT7 重点】指纹={fp_by_floor['MT7']}")
        for n in names:
            print(f"  {n:>12}: 厚度 {node_by['MT7'][n] / nfp7:.2f}  "
                  f"(节点 {node_by['MT7'][n]})")
        cut = node_by["MT7"]["原版6维"] - node_by["MT7"]["删gold+kill"]
        print(f"  → MT7 厚度 {node_by['MT7']['原版6维'] / nfp7:.2f} → "
              f"{node_by['MT7']['删gold+kill'] / nfp7:.2f}"
              f"（删 gold+kill 合并 {cut} 个伪非支配点·这些仅靠 gold/kill 高虚占前沿）")


if __name__ == "__main__":
    main()
