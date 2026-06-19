"""【§S46 小段验证(b)·retrograde V 当 beam_score_fn】验证"路线感知的价值"这根轴对不对。

背景（§S46 主线）：真问题 = beam 评分【路线盲】（hp−Φ：只看当前血+静态惩罚、不知未来该绕路拿什么）。
正解 = 把"路线盲评分"换成"路线感知的价值"V(state)＝从该状态出发最优剩余路线能拿到的最终 HP。
本探针在一小段（MT9 盾→seam=MT10(1,10)·§S33 搜通过的段）上把 V 精确算出来（穷尽枚举 + 后向价值
迭代 retrograde），再当 beam_score_fn 跑窄 beam，验四问：
  ① beam 还屯血吗（路线感知的 V 该让"绕路拿属性现在血少"的态 V 更高、不被截 → 不再屯血）
  ② 留住绕路拿属性的态了吗（"先损血去拿盾/宝石"的中间态 V 该更高、beam 该留它）
  ③ ATK/DEF 上去了吗（出口属性 vs 路线盲基线）
  ④ 后向传播对不对、状态可控不（金标准自检：V[start] 必须 == 穷尽 H*；节点/边数/耗时）

★retrograde = 后向回填（从已知段尾 seam 出口价值往回传 max），不是 forward 猜。
★这是验证轴的【正确性】：若用精确 V 当 score_fn beam 仍屯血 → 轴错；若不屯血+留绕路态 → 轴对、(b)
  可行 → 往 (d) 精确 / 更大段推。本探针不便宜算 V（穷尽付一次），(b)/(d) 的便宜近似是后续。

★只读探针·零产品码改动·不碰封板件（search_quotient/_*/value_vector 一字不动）·beam 逐字节零回归。

数学（为什么后向 max 标签传播 = 这个 V）：V[node]＝从 node 出发到 seam 的最优最终 HP。到 seam 那刻
之前的损血已体现在沿途态的 hp 上（value_vector 含 hp）→ 从 node 走到某 seam 出口的最终 HP 恰 = 该出口
节点的 hp。故 V[node]＝node 在前向 DAG 里能到达的所有 seam 出口 hp 的 max。后向 = 反图上 max 标签传播
（worklist 值迭代·有环也收敛·V 单调有上界 H*）。自检：V[start]＝start 能到全部出口 = 全局最优 = H*。

用法：python -u analysis/seam_retrograde_v_probe.py [--max-states N] [--enable-fly] [--beam-k 8,24]
"""
import argparse
import json
import os
import sys
import time
from collections import deque, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_astar_smoke import first_enter_mt9, SEAM, seg_step          # noqa: E402
from solver.quotient import (search_quotient, _absorb, _boundary_ops,          # noqa: E402
                             _expand_op, _free_cells, _qfp, _bfs_moves, value_vector)
from solver.search import _ge_all                                              # noqa: E402

FLY_ATTRS = json.loads(
    (ROOT / "data" / "games51" / "fly_attrs.json").read_text(encoding="utf-8"))["floors"]

DISTINGUISH_DOORS = True   # 对齐 §S35 探针口径（修红门支配 bug）


def vkey(vec):
    """value_vector dict → hashable（节点身份的价值维部分）。"""
    return tuple(sorted(vec.items()))


def forward_enumerate(start_state, goal_cell, step_fn, max_states, enable_fly):
    """复刻 search_quotient 的 wave-BFS 穷尽枚举（cross_floor 限{MT9,MT10}），额外记录转移图。
    节点 = (fp, vkey(value_vector))，与封板穷尽的 Pareto 去重【同口径】：
      - cvec 被严格支配 → 剪掉（与穷尽一致·不记边·不入图）
      - cvec 等于已有向量 → 指向已存在节点·记边·不重复展开
      - cvec 非支配 → admit 新节点·记边·入下一 wave
    边总是记录（即使 child 去重不重展），保证后向 max 传播图完整。"""
    cross_floor = True
    fly_attrs = FLY_ATTRS if enable_fly else None
    goal_floor, gx, gy = goal_cell

    start, _sm = _absorb(start_state, step_fn)
    start_fp = _qfp(start, _free_cells(start), DISTINGUISH_DOORS)
    start_node = (start_fp, vkey(value_vector(start)))
    node_id = {start_node: 0}
    succ = [[]]                       # succ[i] = child node ids
    goal_hp = {}                      # node_id -> 该节点走到 seam 的最大 hp
    visited = {start_fp: [value_vector(start)]}

    def add_node(fp, vec):
        nd = (fp, vkey(vec))
        i = node_id.get(nd)
        if i is None:
            i = len(node_id)
            node_id[nd] = i
            succ.append([])
        return i

    wave = [(start, 0)]
    gen = 0
    hit_cap = False
    while wave and not hit_cap:
        nxt = []
        for state, pid in wave:
            free = _free_cells(state)
            # 目标可达 → 块内零损血走到 seam，记该节点的出口 hp
            if state.current_floor == goal_floor and (gx, gy) in free:
                walk = _bfs_moves(state, free, (gx, gy))
                if walk is not None:
                    gs = state
                    ok = True
                    for m in walk:
                        gs = step_fn(gs, m)
                        if gs.dead:
                            ok = False
                            break
                    if ok and (gs.hero.x, gs.hero.y) == (gx, gy):
                        ghp = value_vector(gs)["hp"]
                        if goal_hp.get(pid, -1) < ghp:
                            goal_hp[pid] = ghp
            # 付代价算子展开
            ops = _boundary_ops(state, free, cross_floor, enable_fly, fly_attrs)
            for op in ops:
                res = _expand_op(state, free, op, step_fn)
                gen += 1
                if res is None:
                    continue
                child, _om = res
                if child.floor._event_intercepting:
                    continue   # allow_purchase=False 口径（段内无商店·§S35）
                rchild = child
                if rchild.current_floor != state.current_floor:
                    if not (op[0] == "fly" or op[0] == "stair"):
                        continue
                rchild, _abs = _absorb(rchild, step_fn)
                if rchild.dead:
                    continue
                fp = _qfp(rchild, _free_cells(rchild), DISTINGUISH_DOORS)
                cvec = value_vector(rchild)
                cur = visited.get(fp)
                dom_strict = False
                equal = False
                if cur is not None:
                    for v in cur:
                        if _ge_all(v, cvec):
                            if _ge_all(cvec, v):
                                equal = True
                            else:
                                dom_strict = True
                            break
                if dom_strict:
                    continue
                cid = add_node(fp, cvec)
                succ[pid].append(cid)
                if equal:
                    continue
                if cur is None:
                    visited[fp] = [cvec]
                else:
                    visited[fp] = [v for v in cur if not _ge_all(cvec, v)] + [cvec]
                nxt.append((rchild, cid))
                if gen >= max_states:
                    hit_cap = True
                    break
            if hit_cap:
                break
        wave = nxt

    n_edges = sum(len(s) for s in succ)
    fp_by_floor = Counter(fp[0] for (fp, _vk) in node_id)
    return dict(node_id=node_id, succ=succ, goal_hp=goal_hp, visited=visited,
                n=len(node_id), n_edges=n_edges, gen=gen, hit_cap=hit_cap,
                fp_by_floor=fp_by_floor, distinct_fp=len(visited))


def retrograde(succ, goal_hp, n):
    """后向 max 标签传播：V[node] = 从 node 可达的所有 seam 出口 hp 的 max。worklist 值迭代。"""
    NEG = float("-inf")
    V = [NEG] * n
    preds = [[] for _ in range(n)]
    for p in range(n):
        for c in succ[p]:
            preds[c].append(p)
    dq = deque()
    inq = [False] * n
    for nid, hp in goal_hp.items():
        if hp > V[nid]:
            V[nid] = hp
        if not inq[nid]:
            dq.append(nid)
            inq[nid] = True
    pops = 0
    while dq:
        x = dq.popleft()
        inq[x] = False
        pops += 1
        vx = V[x]
        for p in preds[x]:
            if vx > V[p]:
                V[p] = vx
                if not inq[p]:
                    dq.append(p)
                    inq[p] = True
    return V, pops


def fmt_vec(v):
    kk = {k.split(":", 1)[1]: v[k] for k in v if k.startswith("key:") and v[k]}
    return f"HP={v.get('hp'):>4} ATK={v.get('atk'):>3} DEF={v.get('def'):>3} 钥={kk}"


def run_beam(mt9, beam_k, score_fn, enable_fly, max_states, tag):
    """跑一次窄 beam·返回出口前沿统计。score_fn=None → 默认 equiv_hp 路线盲基线。"""
    fly_attrs = FLY_ATTRS if enable_fly else None
    t0 = time.time()
    res = search_quotient(mt9, SEAM, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=DISTINGUISH_DOORS,
                          enable_fly=enable_fly, fly_attrs=fly_attrs,
                          beam_score_fn=score_fn, beam_diversity="stairs")
    secs = time.time() - t0
    print(f"\n  ── beam_k={beam_k} · {tag} · {secs:.1f}s · found={res.found} "
          f"distinct_fp={res.distinct_fingerprints} cut={res.beam_cut_total}")
    if not res.found:
        print("     ✗ 没搜通")
        return None
    fr = res.goal_frontier
    best_hp = max(fr, key=lambda v: v.get("hp", 0))
    best_atk = max(fr, key=lambda v: (v.get("atk", 0), v.get("def", 0)))
    print(f"     出口前沿 {len(fr)} 点 | max-HP 出口: {fmt_vec(best_hp)} | "
          f"max-ATK 出口: {fmt_vec(best_atk)}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=600_000)
    ap.add_argument("--enable-fly", action="store_true")
    ap.add_argument("--beam-k", type=str, default="8,24",
                    help="逗号分隔的窄 beam_k 列表（对照截断行为）")
    ap.add_argument("--skip-beam", action="store_true", help="只跑前向+后向+自检")
    ap.add_argument("--skip-selfcheck", action="store_true",
                    help="跳过金标准自检的封板穷尽重跑（已验过传播正确时省时）")
    args = ap.parse_args()

    print("=" * 80)
    print(f"§S46 小段验证(b)：MT9 盾→seam retrograde V 当 beam_score_fn  "
          f"(fly={'开' if args.enable_fly else '关'})")
    print("=" * 80)

    mt9, idx = first_enter_mt9()
    if mt9 is None:
        print("🛑 没找到 MT9 起点")
        sys.exit(1)
    h0 = mt9.hero
    print(f"起点 = 真实存档首进 MT9 token[{idx}]: {mt9.current_floor}({h0.x},{h0.y}) "
          f"HP={h0.hp} ATK={h0.atk} DEF={h0.def_}")

    # ── 阶段1+2：前向枚举 + 后向 retrograde V ───────────────────────────────
    print("\n[阶段1] 前向穷尽枚举 + 记录转移图（复刻封板 BFS·额外记边）...", flush=True)
    t0 = time.time()
    g = forward_enumerate(mt9, SEAM, seg_step, args.max_states, args.enable_fly)
    t_fwd = time.time() - t0
    print(f"  耗时 {t_fwd:.1f}s | 节点={g['n']} 边={g['n_edges']} | distinct_fp={g['distinct_fp']} "
          f"| 生成={g['gen']} | hit_cap={g['hit_cap']}")
    print(f"  各层指纹 fp_by_floor={dict(g['fp_by_floor'])}")
    print(f"  goal-capable 节点数={len(g['goal_hp'])}")

    print("\n[阶段2] 后向 retrograde V（max 标签传播）...", flush=True)
    t0 = time.time()
    V, pops = retrograde(g["succ"], g["goal_hp"], g["n"])
    t_back = time.time() - t0
    v_start = V[0]
    hstar_exit = max(g["goal_hp"].values()) if g["goal_hp"] else None
    print(f"  耗时 {t_back:.2f}s | 松弛 pops={pops}")
    print(f"  ★V[start]={v_start}  |  出口 max-hp(=H*)={hstar_exit}")

    # ── 金标准自检：V[start] 必须 == 穷尽 H* ──────────────────────────────
    if args.skip_selfcheck:
        print("\n[金标准自检] --skip-selfcheck → 跳过封板穷尽重跑（前次 fly=关 已验 V[start]==H*=324）")
        res_full = None
    else:
        print("\n[金标准自检] 对照封板 search_quotient 穷尽（beam_k=None）的 H* ...", flush=True)
        t0 = time.time()
        fly_attrs = FLY_ATTRS if args.enable_fly else None
        res_full = search_quotient(mt9, SEAM, seg_step, max_states=args.max_states,
                                   cross_floor=True, beam_k=None,
                                   distinguish_doors=DISTINGUISH_DOORS,
                                   enable_fly=args.enable_fly, fly_attrs=fly_attrs)
        t_full = time.time() - t0
    if res_full is not None and res_full.found:
        hstar_full = max(v.get("hp", 0) for v in res_full.goal_frontier)
        print(f"  封板穷尽 {t_full:.1f}s | found=True | distinct_fp={res_full.distinct_fingerprints} "
              f"| H*={hstar_full} | 前沿={len(res_full.goal_frontier)} 点")
        ok_v = (v_start == hstar_full)
        ok_fp = (g["distinct_fp"] == res_full.distinct_fingerprints)
        print(f"  ★自检 V[start]({v_start}) == 封板H*({hstar_full}) ? {'✅通过' if ok_v else '❌不等→传播/复刻有bug'}")
        print(f"  ★自检 复刻distinct_fp({g['distinct_fp']}) == 封板({res_full.distinct_fingerprints}) ? "
              f"{'✅一致' if ok_fp else '⚠不一致(复刻偏离穷尽)'}")
        print("\n  封板穷尽出口前沿（按 HP 降序·= 这段的 ground truth 取舍）：")
        for v in sorted(res_full.goal_frontier, key=lambda v: -v.get("hp", 0)):
            print(f"     {fmt_vec(v)}")
    elif res_full is not None:
        print("  ⚠ 封板穷尽 found=False（撞 cap?）→ 自检不可用")

    if args.skip_beam:
        return

    # ── 阶段3：V 当 beam_score_fn 跑窄 beam 对照 ─────────────────────────────
    print("\n" + "=" * 80)
    print("[阶段3] 窄 beam 对照：路线盲 vs retrograde V 当 beam_score_fn")
    print("=" * 80)

    v_table = {nd: V[i] for nd, i in g["node_id"].items()}
    miss = [0]

    def v_score(state):
        nd = (_qfp(state, _free_cells(state), DISTINGUISH_DOORS),
              vkey(value_vector(state)))
        r = v_table.get(nd)
        if r is None:
            miss[0] += 1
            return float(state.hero.hp)   # fallback
        return float(r)

    def hp_score(state):
        return float(state.hero.hp)

    for bk in [int(x) for x in args.beam_k.split(",") if x.strip()]:
        print(f"\n{'#'*70}\n# beam_k = {bk}\n{'#'*70}")
        miss[0] = 0
        run_beam(mt9, bk, None, args.enable_fly, args.max_states, "默认(equiv_hp 路线盲)")
        run_beam(mt9, bk, hp_score, args.enable_fly, args.max_states, "纯 hp(最朴素屯血)")
        miss[0] = 0
        run_beam(mt9, bk, v_score, args.enable_fly, args.max_states, "★retrograde V(路线感知)")
        print(f"     [v_table miss={miss[0]}（应≈0；beam态是穷尽子集·查不到=复刻不一致）]")

    print("\n" + "=" * 80)
    print("【四问判读】① 看 retrograde V 组 max-HP 出口的 ATK/DEF 是否高于路线盲组（拿了盾/宝石=不屯血）")
    print("           ② retrograde V 组出口属性高 = beam 留住并走了绕路拿属性的态")
    print("           ③ 出口 ATK 对照三组")
    print("           ④ 上方自检 V[start]==H* + 节点/边数/耗时")
    print("=" * 80)


if __name__ == "__main__":
    main()
