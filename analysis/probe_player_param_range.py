"""【想法3·只读·第二阶段：逐决策参数反推 + 可复现/结构盲区分类】

承接第一阶段 probe_player_decisions.py（沿玩家通关路线检测一区每个边界算子跨越、映射到商图算子）。
本阶段：对每个【商图可表达】的玩家决策，用【真实打分函数】反推——在什么 (β_big, β_small, λ) 下，
算法（局部贪心）会做出和玩家【相同】的选择，并据此分类：

  【参数内可复现】 = ∃ (β_big,β_small,λ) 让玩家那个算子成为局部 V_full 第一（argmax）。
                   → 只是调参问题，现有架构能复现。
  【任何参数复现不了】 = 网格内【没有】任何 (β,λ) 让玩家算子当上局部 argmax。
                   → 打分几何结构上偏好别的；是结构盲区候选（要换架构，不是调参）。
  （外加第一阶段已定的【飞行楼传 fly / 事件传送】= 商图根本无此边 = 硬结构外。）

口径与诚实保真（与 probe_dissect_score.py 完全一致、必须随报告写出）：
  · 打分键 V_full = HP − Σcost − λ·区势能 + β_big·pull_big + β_big·g_big + β_small·g_small
    （只进 beam 排序键，绝不进 value_vector/D，红线）。Σcost 用【本决策子态批】的局部 R（诚实账①：
    兄弟相对排序稳健、绝对值仅量级参考）。
  · 真实选择 = 整 wave 取 top-K=200 beam + 末态 best-MT10 的 Pareto 回溯，【不是】局部 argmax（诚实账②）。
    故"never-argmax"≠"绝对复现不了"——它可能仍被 beam 保留 / 被 value_vector Pareto 保号。
    本探针对 never-argmax 决策【额外】标注：玩家子态在全价值向量(hp,atk,def,mdef,gold,kill,key:*,item:*)
    上是否被某兄弟严格支配（被支配=连 Pareto 都保不住=最强结构盲区信号；非支配=帧前沿仍可活、
    局部数据不足以判结构、honest 中间档）。

为什么不算"学走法"：玩家路线只当【标尺】反推参数、找盲区（CLAUDE.md 红线：存档仅作校验+下界，
不入搜索、不改产品码）。本阶段纯分析。

跑法：python -u extract/probe_player_param_range.py
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import probe_player_decisions as ppd
import probe_dissect_score as pds
from probe_crossfloor import build_start
from vzone import build_zone
from solver.beam import build_future_roster, value_vector, _strictly_dominates
from big_item_pull import detect_big_items, build_pickup_bonus

# 参数反推网格（β_big × β_small × λ）。覆盖产品甜区(25,3,0.2)、基线(0,*,*)、两端偏离。
SWEEP_BB = [0, 4, 10, 25, 60]
SWEEP_BS = [0, 3, 10]
SWEEP_LAM = [0.0, 0.1, 0.2]
N_CELLS = len(SWEEP_BB) * len(SWEEP_BS) * len(SWEEP_LAM)
SWEET = (25.0, 3.0, 0.2)      # 产品甜区，用来报告"算法在甜区改选了什么"
PROTECT_AXES = ("atk", "def", "mdef")   # 有意义的保护轴（hp/gold/kill 噪声大、单列）


def setup():
    start = build_start()[0]
    zone = build_zone()
    roster_future = build_future_roster(start)
    big_cells, tau, ranked = detect_big_items(zone, roster_future, start)
    # 满额兑现拿取奖励单位表（β=1 → 表值=ΔRP₀）——注入 pds 模块全局，供其 score_children/V_full 用。
    pds._TABLE_BIG_UNIT = build_pickup_bonus(ranked, big_cells, 1.0, 0.0)
    pds._TABLE_SMALL_UNIT = build_pickup_bonus(ranked, big_cells, 0.0, 1.0)
    return start, zone, roster_future, big_cells, tau, ranked


def manhattan(s0, ox, oy):
    return abs(s0.hero.x - ox) + abs(s0.hero.y - oy)


def unique_max_axes(player_child, sibling_children):
    """玩家子态在哪些轴上是【兄弟中唯一最高】（=该轴上 Pareto 独占，真实 frontier 保号点）。
    只看保护轴 atk/def/mdef + 任意 key:*（钥匙）。返回轴名 list。"""
    pv = value_vector(player_child)
    others = [value_vector(c) for c in sibling_children]
    axes = []
    cand_axes = list(PROTECT_AXES) + sorted({k for v in [pv] + others for k in v if k.startswith("key:")})
    for ax in cand_axes:
        pvv = pv.get(ax, 0)
        ovs = [o.get(ax, 0) for o in others]
        if pvv > 0 and all(pvv > o for o in ovs):   # 严格唯一最高（无并列）
            axes.append(ax)
    return axes


def analyze_decision(d, roster_future, zone, big_cells):
    """对一个【已匹配】决策做参数反推。返回 record dict 或 None（无法展开）。"""
    s0 = d["s0"]
    mop = d["matched_op"]
    mkey = (mop[0], mop[1], mop[2])

    children = pds.expand_children(s0, cross_floor=True)
    if not children:
        return dict(status="expand-empty", d=d)
    rows, roster_R, big = pds.score_children(s0, children, roster_future, zone, big_cells)
    player_row = next((r for r in rows if (r["op"][0], r["op"][1], r["op"][2]) == mkey), None)
    if player_row is None:
        # 玩家算子在商图里展开成【死/无效】子态（被 expand_children 剔除）——一种"算子能列出但模型认为走不通"
        return dict(status="expand-invalid", d=d, n_cands=len(rows))

    n = len(rows)
    # 45 格参数网格：玩家算子的 V_full 排名
    ranks = {}
    wins = []
    for bb in SWEEP_BB:
        for bs in SWEEP_BS:
            for lam in SWEEP_LAM:
                key = pds.V_full(player_row, bb, lam, beta_small=bs)
                rank = 1 + sum(1 for r in rows if r is not player_row
                               and pds.V_full(r, bb, lam, beta_small=bs) > key)
                ranks[(bb, bs, lam)] = rank
                if rank == 1:
                    wins.append((bb, bs, lam))
    best_rank = min(ranks.values()) if ranks else n

    # 甜区算法改选了谁
    sweet_win = max(rows, key=lambda r: pds.V_full(r, SWEET[0], SWEET[2], beta_small=SWEET[1]))

    # 全价值向量 Pareto：玩家子态被某兄弟严格支配？被支配=连 frontier 都保不住。
    pchild = player_row["child"]
    pv = value_vector(pchild)
    dominators = [r for r in rows if r is not player_row
                  and _strictly_dominates(value_vector(r["child"]), pv)]
    prot_axes = unique_max_axes(pchild, [r["child"] for r in rows if r is not player_row])

    if n <= 1:
        cls = "trivial"
    elif best_rank == 1:
        cls = "param-repro"
    else:
        cls = "never-argmax"

    # 复现参数的紧凑刻画
    win_bb = sorted({w[0] for w in wins})
    win_at_bb0 = any(w[0] == 0 for w in wins)         # 区势能基线(无 pull/G)就选它
    min_bb_win = min(win_bb) if win_bb else None
    win_needs_lam0 = wins and all(w[2] == 0.0 for w in wins)   # 仅 λ=0 才赢（区势能反而害它）

    return dict(
        status="ok", d=d, cls=cls, n_cands=n,
        wins=wins, n_wins=len(wins), best_rank=best_rank,
        win_bb=win_bb, win_at_bb0=win_at_bb0, min_bb_win=min_bb_win,
        win_needs_lam0=win_needs_lam0,
        sweet_win=sweet_win, sweet_is_player=(sweet_win is player_row),
        dominated=len(dominators) > 0, dominators=dominators,
        prot_axes=prot_axes,
        player_row=player_row, rows=rows, s0=s0,
        kind=d["kind"], cell=d["cell"], mop=mop,
        dist=manhattan(s0, mop[1], mop[2]),
    )


def op_brief(s0, op):
    return pds.op_desc(s0, op)


def main():
    start, zone, roster_future, big_cells, tau, ranked = setup()

    print("=" * 110)
    print("想法3·第二阶段：玩家逐决策【参数反推】+ 可复现/结构盲区分类（只读·不改产品码）")
    print(f"参数网格 β_big∈{SWEEP_BB} × β_small∈{SWEEP_BS} × λ∈{SWEEP_LAM} = {N_CELLS} 格/决策")
    print(f"产品甜区=(β_big={SWEET[0]:g}, β_small={SWEET[1]:g}, λ={SWEET[2]:g})")
    print(f"大件涌现（数据自动找）：{[f'{c[0]}({c[1]},{c[2]})+a{da}/+d{dd}' for (drp,c,da,dd) in ranked if c in big_cells]}")
    print("=" * 110)

    tokens = ppd.load_player_tokens()
    decisions, end_state = ppd.detect(tokens, verbose=False)

    # 第一阶段结构外（fly/teleport）—— 硬盲区，直接计数
    fly = [d for d in decisions if d["kind"] == "fly"]
    teleport = [d for d in decisions if d["kind"] == "teleport"]
    matched = [d for d in decisions if d["matched"]]
    method_miss = [d for d in decisions if (not d["matched"]) and d["kind"] not in ("fly", "teleport")]

    print(f"\n第一阶段回顾：一区检测 {len(decisions)} 决策 | 商图可表达(matched)={len(matched)} | "
          f"飞行楼传 fly={len(fly)} | 事件传送={len(teleport)} | 其它未匹配={len(method_miss)}")
    print("-" * 110)
    print(f"对 {len(matched)} 个【可表达】决策逐个参数反推（expand+score 较慢，进度每 20 个一报）…")

    recs = []
    for i, d in enumerate(matched, 1):
        rec = analyze_decision(d, roster_future, zone, big_cells)
        recs.append(rec)
        if i % 20 == 0:
            print(f"    …{i}/{len(matched)}")

    ok = [r for r in recs if r["status"] == "ok"]
    expand_bad = [r for r in recs if r["status"] in ("expand-empty", "expand-invalid")]

    by_cls = defaultdict(list)
    for r in ok:
        by_cls[r["cls"]].append(r)

    print("\n" + "=" * 110)
    print("【总分类】(对 matched 可表达决策)")
    print("=" * 110)
    print(f"  可展开评分 ok                 : {len(ok)}")
    print(f"    ├─ trivial(候选≤1，平凡复现) : {len(by_cls['trivial'])}")
    print(f"    ├─ 参数内可复现 param-repro   : {len(by_cls['param-repro'])}  (∃(β,λ)让玩家算子=局部argmax)")
    print(f"    └─ 参数复现不了 never-argmax  : {len(by_cls['never-argmax'])}  (网格内无一格让它当argmax)")
    print(f"  展开异常(模型认为走不通/无候选): {len(expand_bad)}")
    for r in expand_bad:
        d = r["d"]
        print(f"      {r['status']}  tok[{d['tok_i']}] {d['block_floor']} {d['kind']}@{d['cell']} {d.get('label','')}")
    print(f"  ── 外加硬结构外(商图无此边)：飞行楼传 {len(fly)} + 事件传送 {len(teleport)} ──")

    # ── param-repro 的复现条件画像 ──
    pr = by_cls["param-repro"]
    if pr:
        bb0 = [r for r in pr if r["win_at_bb0"]]
        needhi = [r for r in pr if (r["min_bb_win"] is not None and r["min_bb_win"] >= 25)]
        needlam0 = [r for r in pr if r["win_needs_lam0"]]
        print("\n" + "-" * 110)
        print("【参数内可复现】的复现条件画像：")
        print(f"  · 区势能基线就选它(β_big=0 也能 argmax)          : {len(bb0)}/{len(pr)}  → 纯调参/甚至无需 pull 引导")
        print(f"  · 必须高 β_big(≥25)才选它(需大件引导才追得动)     : {len(needhi)}/{len(pr)}")
        print(f"  · 仅 λ=0 才选它(区势能罚分反而把它压下去)         : {len(needlam0)}/{len(pr)}  → 区势能与玩家此步冲突")

    # ── never-argmax：结构盲区候选，逐个详列 + 共性 ──
    na = by_cls["never-argmax"]
    print("\n" + "=" * 110)
    print(f"【参数复现不了 never-argmax】共 {len(na)} 个 —— 结构盲区候选，逐决策详情：")
    print("=" * 110)
    if na:
        print(f"  {'#':>3} {'tok':>5} {'层':>5} {'类型':>6} {'目标格':>8} {'dist':>4} "
              f"{'最佳排名':>5} {'候选':>4} {'被支配':>5} {'保护轴':>10}  玩家算子 →算法甜区改选")
        for r in sorted(na, key=lambda x: x["d"]["tok_i"]):
            d = r["d"]
            s0 = r["s0"]
            pa = ",".join(r["prot_axes"]) if r["prot_axes"] else "—"
            dom = "是" if r["dominated"] else "否"
            print(f"  {d['idx']:>3} {d['tok_i']:>5} {d['block_floor']:>5} {d['kind']:>6} "
                  f"{str(r['cell']):>8} {r['dist']:>4} {r['best_rank']:>5} {r['n_cands']:>4} "
                  f"{dom:>5} {pa:>10}  {op_brief(s0, r['mop'])} → {op_brief(s0, r['sweet_win']['op'])}")

    # 共性交叉表
    print("\n" + "-" * 110)
    print("【共性分析】never-argmax 决策按维度拆分（找结构盲区的共同特征）：")

    def tab(recs_):
        by_kind = defaultdict(int)
        for r in recs_:
            by_kind[r["kind"]] += 1
        return dict(by_kind)

    na_kind = tab(na)
    repro_kind = tab(pr)
    triv_kind = tab(by_cls["trivial"])
    allkinds = sorted(set(na_kind) | set(repro_kind) | set(triv_kind))
    print(f"  按算子类型(复现不了 / 可复现 / 平凡)：")
    for k in allkinds:
        print(f"    {k:>8}: never-argmax {na_kind.get(k,0):>3}  | param-repro {repro_kind.get(k,0):>3}  | trivial {triv_kind.get(k,0):>3}")

    if na:
        dom_yes = [r for r in na if r["dominated"]]
        dom_no = [r for r in na if not r["dominated"]]
        prot_def = [r for r in na if any(a == "def" for a in r["prot_axes"])]
        prot_atk = [r for r in na if any(a == "atk" for a in r["prot_axes"])]
        prot_key = [r for r in na if any(a.startswith("key:") for a in r["prot_axes"])]
        far = [r for r in na if r["dist"] >= 4]
        stairs = [r for r in na if r["kind"] == "stair"]
        doors = [r for r in na if r["kind"] == "door"]
        print(f"\n  · 被兄弟严格支配(连 Pareto 都保不住=真盲区) : {len(dom_yes)}/{len(na)}")
        print(f"  · 未被支配(value_vector frontier 仍保号)    : {len(dom_no)}/{len(na)}  → 局部数据不足判结构、honest 中间档")
        print(f"  · 玩家此步独占 def 轴(=抢盾类、真该保的)     : {len(prot_def)}")
        print(f"  · 玩家此步独占 atk 轴(=抢剑类)               : {len(prot_atk)}")
        print(f"  · 玩家此步独占某 key 轴(=拿到独有钥匙)        : {len(prot_key)}")
        print(f"  · 目标距 s0 英雄 ≥4 格(远处目标)            : {len(far)}/{len(na)}")
        print(f"  · 玩家此步是上下楼(跨层/远目标)             : {len(stairs)}/{len(na)}")
        print(f"  · 玩家此步是开门(花钥匙)                    : {len(doors)}/{len(na)}")

    # 算法在甜区【改选成什么】的分布（玩家被复现不了时、算法更偏好哪类）
    if na:
        pref = defaultdict(int)
        for r in na:
            pref[r["sweet_win"]["op"][0]] += 1
        print(f"\n  · 算法甜区(25,3,0.2)改选的算子类型分布：{dict(pref)}")
        print("    （玩家做 A、算法偏好 B；B 多为就近 kill/door = 近视/就近病的另一面）")

    # ── 深挖①：3 个其它未匹配(非 fly/teleport)是什么 ──
    if method_miss:
        print("\n" + "-" * 110)
        print(f"【深挖①】其它未匹配 {len(method_miss)} 个（非飞行/非传送，查是否 MT10 boss 埋伏链动态机关）：")
        for d in method_miss:
            print(f"    #{d['idx']} tok[{d['tok_i']}] {d['block_floor']} {d['kind']}@{d['cell']} "
                  f"detail={d['detail']} why={d['why']}")

    # ── 深挖②：never-argmax 按"最佳排名"分层（rank2=擦肩、调参临界；rank≥3=被明显冷落）──
    if na:
        from collections import Counter
        rank_hist = Counter(r["best_rank"] for r in na)
        near = [r for r in na if r["best_rank"] == 2]
        cold = [r for r in na if r["best_rank"] >= 3]
        print("\n" + "-" * 110)
        print("【深挖②】never-argmax 按最佳排名分层（best_rank=网格内玩家算子能达到的最高名次）：")
        print(f"    best_rank 直方图: {dict(sorted(rank_hist.items()))}")
        print(f"    · rank=2 擦肩(差一点就 argmax、beam 必留、近调参临界): {len(near)}/{len(na)}")
        print(f"    · rank≥3 被明显冷落(打分几何真不喜欢、结构信号强)    : {len(cold)}/{len(na)}")
        print(f"      rank≥3 清单: " + ", ".join(
            f"#{r['d']['idx']}({r['kind']}@{r['cell']},r{r['best_rank']}/{r['n_cands']})"
            for r in sorted(cold, key=lambda x: -x["best_rank"])))

    # ── 深挖③：13 个被严格支配的(连 Pareto 都保不住)——谁支配它、赢在哪条轴 ──
    if na:
        dom_recs = [r for r in na if r["dominated"]]
        print("\n" + "-" * 110)
        print(f"【深挖③】被严格支配 {len(dom_recs)} 个（最硬结构盲区：连 value_vector frontier 都保不住）。")
        print("    逐个看【谁支配它/赢在哪条轴】——验证'开门花钥匙=价值向量上纯损'这个假设：")
        for r in sorted(dom_recs, key=lambda x: x["d"]["tok_i"]):
            d = r["d"]
            s0 = r["s0"]
            pv = value_vector(r["player_row"]["child"])
            # 取一个支配者，列出它 > 玩家 的轴
            dom = r["dominators"][0]
            dv = value_vector(dom["child"])
            better = {k: (dv.get(k, 0), pv.get(k, 0)) for k in set(dv) | set(pv)
                      if dv.get(k, 0) != pv.get(k, 0)}
            print(f"    #{d['idx']} tok[{d['tok_i']}] {d['block_floor']} 玩家[{op_brief(s0, r['mop'])}] "
                  f"被[{op_brief(s0, dom['op'])}]支配；轴差(支配者,玩家): "
                  + ", ".join(f"{k}={a}vs{b}" for k, (a, b) in sorted(better.items())))

    print("\n" + "=" * 110)
    print("结论要点（详见报告 .md）：")
    print(f"  1) 硬结构外 = 飞行楼传 {len(fly)}（商图无飞行边）—— 任何 (β,λ) 都复现不了，是想法2/想法3 的头号盲区。")
    print(f"  2) 商图可表达决策里：{len(by_cls['param-repro'])} 可调参复现 + {len(by_cls['never-argmax'])} 参数复现不了。")
    print(f"  3) never-argmax 的共性见上交叉表（远处目标/跨层/钥匙门=结构盲区候选；被支配者=最硬）。")
    return recs, decisions


if __name__ == "__main__":
    main()
