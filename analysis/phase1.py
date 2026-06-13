"""阶段一分段框架（驱动层，塔无关逻辑在 solver/）。

裁定①：借 route 层序骨架。把 route 每个 token 按重放轨迹分两类：
  · free  ——「停在本层的普通移动」(U/D/L/R 且不改 current_floor)：成 move-run，段内走法由
            块图搜索 search_quotient 自由搜索（不抄 route），run 目标格 = route 该 run 末的落格。
  · forced——「非移动 token (CHOICE/ITEM/KEY/FLOOR/help…) 或 会改层/触发传送的移动」(楼梯步 /
            伏击传送)：照 route 骨架【逐字施加】到前沿每点。这统一收编了开场 firstArrive 选择、
            中段对话、楼梯换层、伏击传送——它们都不是「自由走法」，属骨架。

裁定②：段间传整条 Pareto 前沿 + 「地图残留态」（活怪 / 地上资源坐标 / coin 等全局乘区开关）随
前沿点完整 state 携带；控宽先不预设、用数据说话（report 膨胀曲线），仅宽度爆时按保底软截断
（HP+各维加权）、被截点落盘不静默丢。

闭环：frontier 是【携带完整残留态的全态列表】。逐 block 推进——forced block 对每点 step 逐字施加；
run block 对每点 search_quotient→solver.verify.replay 干净重放成【独立全态】(引擎裁判+防别名)→
solver.frontier.merge_frontier 按全局残留指纹合并。塔特有信息（route/层/格）只在本文件读。
"""
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
from sim.simulator import _copy_state, step
from solver.beam import (beam_protection_overflow, beam_select,
                         equiv_hp_over_roster, score_points)
from solver.frontier import FrontierPoint, merge_frontier, value_vector
from solver.quotient import count_floor_blocks, search_quotient
from solver.verify import replay

OUT_DIR = Path(__file__).parent / "extract"
MOVES = {"U", "D", "L", "R"}

# 软截断保底权重（仅宽度爆时启用；被截点落盘不丢）。非搜索偏好——只为防 OOM 的应急保活：
# HP 主导 + 永久属性/硬通货次之 + 金/击杀末位。见 docs/solver-design.md 裁定②。
_TRUNC_W = {"hp": 1.0, "atk": 60.0, "def": 60.0, "mdef": 30.0, "gold": 1.0, "kill": 5.0}


# ─── route 轨迹 → 处理计划 ──────────────────────────────────────────────────────

def trace_route(tokens):
    """重放 route，逐 token 记 (floor_before,pos_before,floor_after,pos_after,is_move,changed)。"""
    state = build_initial_state()
    tr = []
    for tok in tokens:
        fb, pb = state.current_floor, (state.hero.x, state.hero.y)
        state = step(state, tok)
        fa, pa = state.current_floor, (state.hero.x, state.hero.y)
        tr.append({"fb": fb, "pb": pb, "fa": fa, "pa": pa,
                   "is_move": tok in MOVES, "changed": fa != fb})
    return tr


def build_plan(tokens, trace, max_floor_segments=None):
    """切成有序 block：('run', floor, goal_cell, i0, i1, seg) | ('forced', tok, i, seg, changed)。
    seg = 已发生的换层次数（floor-segment 序号，MT1=0）。max_floor_segments 后停。"""
    def is_free(i):
        return trace[i]["is_move"] and not trace[i]["changed"]

    blocks, i, n, seg = [], 0, len(tokens), 0
    while i < n:
        if is_free(i):
            j = i
            while j < n and is_free(j):
                j += 1
            blocks.append(("run", trace[i]["fb"], trace[j - 1]["pa"], i, j - 1, seg))
            i = j
        else:
            changed = trace[i]["changed"]
            blocks.append(("forced", tokens[i], i, seg, changed))
            i += 1
            if changed:
                seg += 1
                if max_floor_segments is not None and seg >= max_floor_segments:
                    break
    return blocks


# ─── 闭环执行 ──────────────────────────────────────────────────────────────────

def _trunc_score(vec):
    s = sum(_TRUNC_W.get(k, 0.0) * v for k, v in vec.items())
    s += 100.0 * sum(v for k, v in vec.items() if k.startswith("key:"))
    s += 10.0 * sum(v for k, v in vec.items() if k.startswith("item:"))
    return s


def _search_copy(state):
    """单段搜索入口副本：全量深拷（独立）后置单层拷贝优化 flag（搜索内提速；本 run 不离层、
    搜索内部态全丢弃只用 actions 重放，置位安全）。"""
    s = _copy_state(state)
    s._single_floor_copy = True
    return s


def _apply_cap(blockrec, points, width_cap, tag):
    if width_cap is None or len(points) <= width_cap:
        return points, 0
    scored = sorted(points, key=lambda p: _trunc_score(value_vector(p.state)), reverse=True)
    kept, cut = scored[:width_cap], scored[width_cap:]
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"phase1_truncated_{tag}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for p in cut:
            fh.write(json.dumps({"value": value_vector(p.state),
                                 "actions": "".join(p.actions)}, ensure_ascii=False) + "\n")
    print(f"      [软截断] {len(cut)} 点落盘 {path.name}（不静默丢）")
    return kept, len(cut)


def _apply_beam(points, beam_k, tag):
    """beam 控宽（玩家 2026-06-07 方案）：按 V 标量(HP+攻防/装备等效血量)排序、保护维(钥匙/消耗
    道具)Pareto 骨架硬保护，截到 beam_k。被截点落盘(含 V 分 + 价值向量)可审计——绝不静默丢。
    返回 (kept, n_cut)。V/beam 口径在 solver/beam.py，塔无关、引擎 compute_combat 算。"""
    if beam_k is None or len(points) <= beam_k:
        return points, 0
    overflow, skel = beam_protection_overflow(points, beam_k)
    roster, big, scores = score_points(points)        # 单遍：选点/落盘/cut 复用同一批 V 缓存
    score_fn = lambda st: scores[id(st)] if id(st) in scores \
        else equiv_hp_over_roster(st, roster, big)
    kept, cut = beam_select(points, beam_k, score_fn=score_fn)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"phase1_beam_cut_{tag}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for p in cut:
            fh.write(json.dumps({"value": value_vector(p.state), "V": score_fn(p.state),
                                 "actions": "".join(p.actions)}, ensure_ascii=False) + "\n")
    warn = f"  ⚠保护骨架{skel}≥K让位（保护未全保，已落盘）" if overflow else ""
    print(f"      [beam K={beam_k}] 保留={len(kept)} 截断={len(cut)} 落盘 {path.name}{warn}")
    return kept, len(cut)


def _truncate(points, width_cap, beam_k, tag):
    """统一控宽入口：beam_k 设定则走 beam（玩家方案），否则回退旧软截断（应急保活）。"""
    if beam_k is not None:
        return _apply_beam(points, beam_k, tag)
    return _apply_cap(None, points, width_cap, tag)


def _run_block(frontier, floor, goal, init, width_cap, beam_k, tag):
    """run block：对前沿每点用【块图】搜索到 goal、独立重放成全态、合并。返回 (frontier', stats)。
    段内搜索 = solver.quotient.search_quotient（缩点商图，替代朴素 BFS）；输出动作序列仍由
    solver.verify.replay 独立裁判逐字段核对。hit_cap 必上报（裁定②：被截不静默）。"""
    raw, gen, exp = [], 0, 0
    unreachable = mismatch = capped = 0
    q_states = q_ops = blocks_peak = floor_blocks = free_cells = 0
    intercept = set()    # 撞 choices 事件(商人/祭坛/老人)的格 → 块图记录不强解(放开决策依据)
    for fp in frontier:
        st = fp.state
        if (st.hero.x, st.hero.y) == goal:           # 已在目标格：平凡前沿点（净位移为零的 run）
            raw.append(fp)
            continue
        if not floor_blocks:                          # 首个非平凡点：记录入口缩点规模（代表值）
            floor_blocks, free_cells = count_floor_blocks(st)
        res = search_quotient(_search_copy(st), (floor, goal[0], goal[1]), step)
        gen += res.states_generated
        exp += res.states_expanded
        q_states += res.distinct_fingerprints
        q_ops += getattr(res, "n_ops_total", 0)
        blocks_peak = max(blocks_peak, getattr(res, "n_blocks_peak", 0))
        intercept.update(tuple(c) for c in getattr(res, "intercept_locs", ()))
        if res.hit_cap:
            capped += 1
        if not res.found:
            unreachable += 1
            continue
        for vec, acts in zip(res.goal_frontier, res.goal_frontier_actions):
            carried = replay(st, acts, step, _copy_state)
            if (carried.hero.hp != vec["hp"] or carried.hero.atk != vec["atk"]
                    or carried.hero.def_ != vec["def"]
                    or carried.hero.kill_count != vec["kill"]):
                mismatch += 1
            raw.append(FrontierPoint(state=carried, actions=fp.actions + tuple(acts)))
    merged, mstats = merge_frontier(raw)
    merged, truncated = _truncate(merged, width_cap, beam_k, tag)
    best_hp = max((value_vector(p.state)["hp"] for p in merged), default=0)
    mstats.update(gen=gen, exp=exp, unreachable=unreachable, mismatch=mismatch,
                  truncated=truncated, raw=len(raw), capped=capped, q_states=q_states,
                  q_ops=q_ops, blocks_peak=blocks_peak, floor_blocks=floor_blocks,
                  free_cells=free_cells, intercept=sorted(intercept), best_hp=best_hp)
    return merged, mstats


def _forced_block(frontier, tok, width_cap, beam_k, tag):
    """forced block：对前沿每点逐字施加 tok（楼梯/伏击/对话/道具），合并。"""
    raw = [FrontierPoint(state=step(fp.state, tok), actions=fp.actions + (tok,))
           for fp in frontier]
    merged, mstats = merge_frontier(raw)
    merged, truncated = _truncate(merged, width_cap, beam_k, tag)
    best_hp = max((value_vector(p.state)["hp"] for p in merged), default=0)
    mstats.update(gen=0, exp=0, unreachable=0, mismatch=0, truncated=truncated, raw=len(raw),
                  capped=0, q_states=0, q_ops=0, blocks_peak=0, floor_blocks=0, free_cells=0,
                  intercept=[], best_hp=best_hp)
    return merged, mstats


def run_phase1(num_segments=5, width_cap=None, beam_k=None, ref_sample=3):
    tokens = load_tokens()
    trace = trace_route(tokens)
    plan = build_plan(tokens, trace, max_floor_segments=num_segments)
    init = build_initial_state()
    frontier = [FrontierPoint(state=init, actions=())]

    ctl = (f"beam K={beam_k}" if beam_k is not None
           else (f"软截断 cap={width_cap}" if width_cap is not None else "无控宽(exact)"))
    print("=" * 84)
    print(f"阶段一闭环：从 {init.current_floor} 起跑前 {num_segments} 个楼层段"
          f"（借 route 层序骨架；{len(plan)} 个 block；控宽={ctl}）")
    print("=" * 84)

    seg_floor = {}     # seg -> 该段所在层（首个 block 的 floor）
    blocklog = []
    t_all = time.perf_counter()
    for b in plan:
        kind = b[0]
        seg = b[-2] if kind == "forced" else b[5]
        tag = f"seg{seg}_{kind}_{len(blocklog)}"
        t0 = time.perf_counter()
        if kind == "run":
            _, floor, goal, i0, i1, _ = b
            seg_floor.setdefault(seg, floor)
            frontier, ms = _run_block(frontier, floor, goal, init, width_cap, beam_k, tag)
            desc = f"run {floor} →{goal} tok[{i0}..{i1}]"
        else:
            _, tok, i, _, changed = b
            seg_floor.setdefault(seg, frontier[0].state.current_floor if frontier else "?")
            frontier, ms = _forced_block(frontier, tok, width_cap, beam_k, tag)
            desc = f"forced {tok}@{i}" + ("  ⟶换层" if changed else "")
        dt = (time.perf_counter() - t0) * 1000
        rec = {"seg": seg, "kind": kind, "desc": desc, "ms": dt, **ms}
        blocklog.append(rec)
        cap_tag = f"  ⚠hit_cap×{ms['capped']}" if ms['capped'] else ""
        if ms.get("intercept"):
            cap_tag += f"  ⟦拦截事件格×{len(ms['intercept'])}:{ms['intercept']}⟧"
        print(f"  [seg{seg}] {desc:<34} 原始={ms['raw']:>5} → 宽度={ms['width']:>5} "
              f"指纹={ms['fingerprints']:>5} 截断={ms['truncated']:>4} "
              f"不可达={ms['unreachable']:>3} 不一致={ms['mismatch']:>3} "
              f"gen={ms['gen']:>9,} {dt:>7.0f}ms{cap_tag}")
        if not frontier:
            print("\n[终止] 前沿空——无可继续的携带态。")
            break

    # —— 末态引擎裁判：抽样从全局起点重放，核对携带态 ——
    print("\n" + "-" * 84)
    sample = sorted(frontier, key=lambda p: value_vector(p.state)["hp"], reverse=True)[:ref_sample]
    ref_ok = 0
    for p in sample:
        rep = replay(init, p.actions, step, _copy_state)
        ok = (rep.current_floor == p.state.current_floor
              and (rep.hero.x, rep.hero.y) == (p.state.hero.x, p.state.hero.y)
              and rep.hero.hp == p.state.hero.hp and rep.hero.atk == p.state.hero.atk
              and rep.hero.def_ == p.state.hero.def_ and rep.hero.gold == p.state.hero.gold
              and rep.hero.kill_count == p.state.hero.kill_count)
        ref_ok += ok
    print(f"末态前沿全局重放裁判: {ref_ok}/{len(sample)} 一致"
          + ("（引擎裁判通过）" if ref_ok == len(sample) else "  ⚠ 不一致需排查"))

    _print_curve(blocklog, seg_floor, time.perf_counter() - t_all)
    return blocklog, frontier


def _print_curve(blocklog, seg_floor, total_s):
    # 按 floor-segment 聚合：宽度取该段【最后一个 block】（= 段末携带、传入下一层的前沿）；
    # 块数/段内状态/gen/hit_cap 取该段所有 block 的聚合（块数取该段 run block 代表值）。
    segs = {}
    for r in blocklog:
        segs[r["seg"]] = r  # 末值覆盖 → 段最后一个 block
    agg = {}
    for r in blocklog:
        a = agg.setdefault(r["seg"], {"gen": 0, "ms": 0.0, "q_states": 0,
                                      "capped": 0, "blocks": 0, "free": 0, "peak": 0})
        a["gen"] += r["gen"]
        a["ms"] += r["ms"]
        a["q_states"] += r.get("q_states", 0)
        a["capped"] += r.get("capped", 0)
        a["blocks"] = max(a["blocks"], r.get("floor_blocks", 0))
        a["free"] = max(a["free"], r.get("free_cells", 0))
        a["peak"] = max(a["peak"], r.get("blocks_peak", 0))
    print("\n" + "=" * 104)
    print("膨胀曲线（裁定②控宽依据；块图版。宽度取段末携带前沿；块数=整层自由格→连通块）")
    print("=" * 104)
    print(f"{'段':>2} {'层':>5} {'自由格→块':>11} {'峰块':>5} {'段内状态':>8} "
          f"{'段末宽度':>8} {'段末最优HP':>10} {'累计gen':>10} {'hit_cap':>7} {'段耗时ms':>9}")
    print("-" * 104)
    for seg in sorted(segs):
        r, a = segs[seg], agg[seg]
        blk = f"{a['free']}→{a['blocks']}" if a["blocks"] else "—"
        cap = f"⚠{a['capped']}" if a["capped"] else "0"
        print(f"{seg:>2} {seg_floor.get(seg, '?'):>5} {blk:>11} {a['peak']:>5} "
              f"{a['q_states']:>8} {r['width']:>8} {r.get('best_hp', 0):>10} "
              f"{a['gen']:>10,} {cap:>7} {a['ms']:>9.0f}")
    tot_mm = sum(r["mismatch"] for r in blocklog)
    tot_tr = sum(r["truncated"] for r in blocklog)
    tot_cap = sum(r.get("capped", 0) for r in blocklog)
    print("-" * 104)
    print(f"  总耗时 {total_s:.1f}s  累计裁判不一致={tot_mm}"
          + ("（搜索优化无 bug）" if tot_mm == 0 else "  ⚠ 排查搜索优化")
          + f"  累计软截断={tot_tr}  累计 hit_cap={tot_cap}"
          + ("" if tot_cap == 0 else "  ⚠ 有段撞 cap，前沿可能不全"))
    icpt = {}
    for r in blocklog:
        for loc in r.get("intercept", ()):
            icpt.setdefault(r["seg"], []).append(tuple(loc))
    if icpt:
        print("  ⟦拦截(choices)事件格⟧ 块图遇商人/祭坛/老人 → 记录不强解（放开决策依据）：")
        for seg in sorted(icpt):
            print(f"    seg{seg}（{seg_floor.get(seg, '?')}）: {sorted(set(icpt[seg]))}")


def _analyze(max_runs=14):
    tokens = load_tokens()
    trace = trace_route(tokens)
    plan = build_plan(tokens, trace, max_floor_segments=max_runs)
    print(f"route 展开后 token 总数 = {len(tokens)}；前 {max_runs} 段 plan = {len(plan)} 个 block:")
    print("-" * 84)
    for b in plan:
        if b[0] == "run":
            _, floor, goal, i0, i1, seg = b
            print(f"  [seg{seg}] run    {floor:>5} →{goal} tok[{i0}..{i1}] ({i1 - i0 + 1} 步自由搜索)")
        else:
            _, tok, i, seg, changed = b
            print(f"  [seg{seg}] forced {tok}@{i}" + ("  ⟶换层" if changed else "  (本层)"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="run", choices=["run", "analyze"])
    ap.add_argument("-n", "--segments", type=int, default=5)
    ap.add_argument("-c", "--cap", type=int, default=None)
    ap.add_argument("--beam", type=int, default=None,
                    help="beam 控宽 K（状态相关 V 排序+保护维硬保护）；设则走 beam，不设走旧软截断 -c")
    args = ap.parse_args()
    if args.mode == "analyze":
        _analyze(args.segments)
    else:
        run_phase1(num_segments=args.segments, width_cap=args.cap, beam_k=args.beam)
