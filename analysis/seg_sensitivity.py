"""前 9 段 beam 敏感性实验（实验编排层，塔无关逻辑在 solver/，塔特有只在 phase1）。

玩家 2026-06-07 方案验收：在【前 9 段 exact 前沿是现成真值】的区间，对 K∈{50,100,200,500}
跑 beam，对照 exact + route 基准，看：
  (a) K 足够大时 beam 能否复现 exact（beam 正确性标尺；未截断的段 beam≡exact 是构造性事实）；
  (b) 收敛 K = 「再加宽结果不再变好」的最小 K（无损 K）；
  (c) 若不收敛 → 打分函数 V 抓错特征，回头修 V。
验收四条：beam≥route 基准、能复现 exact、裁判一致(mismatch=0)、截点落盘（落盘在 phase1 内）。

用法：
  python seg_sensitivity.py run exact -n 9          # 跑 exact，落盘 seg_exit_exact.json
  python seg_sensitivity.py run 50    -n 9          # 跑 beam K=50，落盘 seg_exit_K50.json
  python seg_sensitivity.py report    -n 9          # 汇总 route+exact+各 K → 敏感性曲线

本文件只编排实验、读 route 骨架做基准；不碰 sim/solver，exact 当真值标尺。"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import step
from solver.frontier import value_vector
from phase1 import trace_route, build_plan, run_phase1

OUT_DIR = Path(__file__).parent / "extract"


def route_benchmark(num_segments):
    """重放 route 骨架，取每个 floor-segment 出口的英雄态(value_vector：HP/属性/钥匙/道具) = 下界
    基准（beam 不得差于它）。与 phase1 同一套 build_plan 切段，逐 block 施加 route 原 token。"""
    tokens = load_tokens()
    trace = trace_route(tokens)
    plan = build_plan(tokens, trace, max_floor_segments=num_segments)
    state = build_initial_state()
    exits = {}
    for b in plan:
        if b[0] == "run":
            _, _floor, _goal, i0, i1, seg = b
            for k in range(i0, i1 + 1):
                state = step(state, tokens[k])
        else:
            _, tok, _i, seg, _changed = b
            state = step(state, tok)
        exits[seg] = value_vector(state)          # 末值覆盖 → 该段出口
    return exits


def _seg_exits(blocklog):
    """blocklog → 每段出口聚合：best_hp/宽度取该段最后一个 block；truncated/mismatch/ms 求和。
    与 phase1._print_curve 同口径（段末 block 末值覆盖）。"""
    last, agg = {}, {}
    for r in blocklog:
        seg = r["seg"]
        last[seg] = r                              # 末值覆盖 → 段最后 block
        a = agg.setdefault(seg, {"truncated": 0, "mismatch": 0, "ms": 0.0})
        a["truncated"] += r.get("truncated", 0)
        a["mismatch"] += r.get("mismatch", 0)
        a["ms"] += r.get("ms", 0.0)
    out = {}
    for seg, r in last.items():
        a = agg[seg]
        out[seg] = {"best_hp": r.get("best_hp", 0), "width": r.get("width", 0),
                    "truncated": a["truncated"], "mismatch": a["mismatch"], "ms": a["ms"]}
    return out


def _label(beam_k):
    return "exact" if beam_k is None else f"K{beam_k}"


def _dump_path(beam_k):
    return OUT_DIR / f"seg_exit_{_label(beam_k)}.json"


def cmd_run(num_segments, beam_k):
    """跑一个控宽配置（exact=None 或 beam K），把每段出口结果落盘 JSON。"""
    t0 = time.perf_counter()
    blocklog, frontier = run_phase1(num_segments=num_segments, beam_k=beam_k)
    total_s = time.perf_counter() - t0
    segs = _seg_exits(blocklog)
    total_mm = sum(s["mismatch"] for s in segs.values())
    final_best = max((value_vector(p.state)["hp"] for p in frontier), default=0)
    rec = {"label": _label(beam_k), "beam_k": beam_k, "num_segments": num_segments,
           "total_s": total_s, "total_mismatch": total_mm, "final_best_hp": final_best,
           "segs": {str(k): v for k, v in segs.items()}}
    OUT_DIR.mkdir(exist_ok=True)
    path = _dump_path(beam_k)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    print(f"\n[落盘] {path.name}  总耗时={total_s:.1f}s  裁判不一致={total_mm}  末态最优HP={final_best}")
    return rec


def cmd_report(num_segments, ks):
    """汇总 route 基准 + exact + 各 K 的每段出口 best_hp → 敏感性曲线 + 收敛 K + 验收核对。"""
    route = route_benchmark(num_segments)
    configs = []                                    # [(label, beam_k, rec or None)]
    for bk in [None] + list(ks):
        p = _dump_path(bk)
        rec = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        configs.append((_label(bk), bk, rec))

    present = [(lbl, bk, rec) for lbl, bk, rec in configs if rec is not None]
    if not present:
        print("无任何配置结果落盘，先跑 `run exact` / `run <K>`。")
        return

    segn = sorted(route)
    print("\n" + "=" * 100)
    print(f"前 {num_segments} 段 beam 敏感性曲线：每段【出口最优 HP】(route=下界基准, exact=真值标尺)")
    print("=" * 100)
    hdr = f"{'段':>2} {'route':>7} " + " ".join(f"{lbl:>8}" for lbl, _, _ in present)
    print(hdr)
    print("-" * 100)
    exact_rec = next((rec for lbl, _, rec in present if lbl == "exact"), None)
    for seg in segn:
        rhp = route.get(seg, {}).get("hp", 0)
        cells = []
        for lbl, _, rec in present:
            s = rec["segs"].get(str(seg))
            if s is None:
                cells.append(f"{'—':>8}")
                continue
            hp, tr = s["best_hp"], s["truncated"]
            mark = "*" if tr else " "              # * = 该段发生截断（可能有损）
            cells.append(f"{hp:>7}{mark}")
        print(f"{seg:>2} {rhp:>7} " + " ".join(cells))
    print("-" * 100)
    print("  (HP 后 * = 该段 beam 发生截断 → 可能有损；无 * = 未截断，beam≡exact 构造性成立)")

    # —— 验收核对 ——
    print("\n【验收核对】")
    for lbl, bk, rec in present:
        if lbl == "exact":
            print(f"  exact：总耗时={rec['total_s']:.1f}s  裁判不一致={rec['total_mismatch']}"
                  f"  末态最优HP={rec['final_best_hp']}")
            continue
        ge_route = all(rec["segs"].get(str(s), {}).get("best_hp", 0)
                       >= route.get(s, {}).get("hp", 0) for s in segn)
        repro = None
        if exact_rec is not None:
            repro = all(rec["segs"].get(str(s), {}).get("best_hp", -1)
                        == exact_rec["segs"].get(str(s), {}).get("best_hp", -2) for s in segn)
        repro_s = ("复现exact" if repro else "≠exact") if repro is not None else "无exact对照"
        print(f"  {lbl}：总耗时={rec['total_s']:6.1f}s  裁判不一致={rec['total_mismatch']}"
              f"  末态最优HP={rec['final_best_hp']}  ≥route={'是' if ge_route else '否⚠'}  {repro_s}")

    # —— 收敛 K：相邻 K 每段 best_hp 全相等 → 已收敛 ——
    kconfigs = [(lbl, bk, rec) for lbl, bk, rec in present if bk is not None]
    kconfigs.sort(key=lambda t: t[1])
    print("\n【收敛 K】(再加宽 best_hp 不再变化的最小 K = 无损 K)")
    conv = None
    for i in range(len(kconfigs) - 1):
        lo, hi = kconfigs[i], kconfigs[i + 1]
        same = all(lo[2]["segs"].get(str(s), {}).get("best_hp", 0)
                   == hi[2]["segs"].get(str(s), {}).get("best_hp", 1) for s in segn)
        flag = "＝（收敛）" if same else "≠（仍在变好/变化）"
        print(f"  {lo[0]} → {hi[0]}：每段 best_hp {flag}")
        if same and conv is None:
            conv = lo[0]
    if conv:
        print(f"  收敛 K = {conv}（再加宽无增益）")
    else:
        print("  未见相邻 K 收敛 → 或需更大 K，或 V 抓错特征（回头修 V）。")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report"])
    ap.add_argument("k", nargs="?", default=None,
                    help="run 模式：'exact' 或整数 K；report 模式忽略")
    ap.add_argument("-n", "--segments", type=int, default=9)
    ap.add_argument("--ks", default="50,100,200,500", help="report 汇总的 K 列表")
    args = ap.parse_args()
    if args.cmd == "run":
        bk = None if (args.k is None or args.k == "exact") else int(args.k)
        cmd_run(args.segments, bk)
    else:
        ks = [int(x) for x in args.ks.split(",") if x.strip()]
        cmd_report(args.segments, ks)
