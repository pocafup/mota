"""【§S29 定生死探针】玩家手排强基因 → decode → navigate 到 seam → V_boss(只读·不碰封板件)。

背景：§S29 小验证(pop8/gen3)0/18 到 seam、全 V_boss=0；标定排除了「max_pops=8000 假阴性」，
但暴露混淆——被测的全是低楼层弱态(GA 没找出会爬的解)、分不开『搜索力 vs 架构』。玩家手排了一条
强基因当探针定生死(执行序，见 HAND_GENE)：剑→盾→一路宝石→红钥→navigate 到 boss 区 seam。

本脚本两段(都用真实封板件、不重写语义)：
  · PART A【忠实 GA 管线】：真实 _decode_with_order(带 block_markers/cells + final_goal=红钥块·@8000)
    跑这条基因 = GA 真会对它做的事；再 navigate_to(term, SEAM, @8000) → query V_boss。
    报：进包序(normalized)、哪些块没进包、终态层/属性/钥匙、红钥到手否、seam 到达否、V_boss。
  · PART B【架构天花板】：手动逐块 navigate(★无 forbidden·最宽松物理可达)、每腿升档 max_pops
    8000→30000→100000 破预算假阴性，定三点：① 爬到 MT9 拿到盾否 ② 红钥到手否 ③ 送到 seam 否+V_boss。
    A vs B 隔离：A 没到而 B 到 = 搜索力/forbidden/budget 问题(非架构)；B 也到不了 = 真架构墙。

归类(玩家定义·脚本只出客观数·★甲/乙玩家拍)：
  情况1 = 连爬到 MT9 拿盾都做不到 → navigate 执行问题 → 支持乙。
  情况2 = 拿到盾但送不到 seam → 末腿/路径瓶颈 → 支持乙。
  情况3 = 拿盾+到 seam+V_boss>0 → 架构能到 seam、GA 没到纯搜索力 → 甲理论可行(navigate 天花板仍在)。

坐标不猜：玩家给的 (fid,x,y) 一律用 cell_to_block 折到真实块；命中不了/不在 pool_13/红钥不匹配
  全部标出报玩家，绝不臆造(撞 CLAUDE.md「坐标对不上绝不猜」)。

用法：python -u analysis/probe_handgene_seam.py
      可调：--ladder 8000,30000,100000  --max-states 400000
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
sys.path.insert(0, str(ROOT / "analysis"))

from ga_loop import build_harness, _decode_with_order, _invalid_score, _taken  # noqa: E402
from ga_decode import goal_to_cell                                             # noqa: E402
from ga_navigate import navigate_to, _nav_key                                  # noqa: E402
from solver.fitness import fitness                                             # noqa: E402
from solver.quotient import search_quotient                                    # noqa: E402
from block_targets import build_block_index                                    # noqa: E402
from curriculum_smoke_vboss import (SEAM, BOSS_GOAL, W_POTION, W_KEY,          # noqa: E402
                                    make_seg_step, build_pool_13)

# ── 玩家手排基因(执行序)·(label, fid, x, y)·坐标按 (x,y)(与 SEAM=('MT10',1,11) 同口径) ──
HAND_GENE = [
    ("MT5剑",     "MT5", 11, 11),
    ("MT4宝石",   "MT4",  7, 10),
    ("MT9盾",     "MT9",  9,  7),
    ("MT9宝石",   "MT9",  6,  5),
    ("MT9宝石",   "MT9",  1,  5),
    ("MT7宝石",   "MT7",  3,  1),
    ("MT3宝石",   "MT3",  2,  1),
    ("MT1宝石x2", "MT1",  8,  4),
    ("MT6宝石",   "MT6",  4,  9),
    ("MT8宝石x2", "MT8",  5, 11),
    ("MT3宝石",   "MT3",  2,  9),
    ("MT10宝石",  "MT10", 2,  6),
    ("MT5宝石",   "MT5",  1,  9),
    ("MT10宝石",  "MT10",10,  6),
]
RED_KEY = ("MT8红钥匙", "MT8", 10, 2)


def _parse_args():
    p = argparse.ArgumentParser(description="§S29 定生死探针：手排强基因→seam→V_boss")
    p.add_argument("--ladder", type=str, default="8000,30000,100000",
                   help="PART B 每腿 max_pops 升档(逗号分隔·从小到大·破预算假阴性)")
    p.add_argument("--decode-maxpops", type=int, default=8000, help="PART A decode 每腿护栏(GA 口径)")
    p.add_argument("--max-states", dest="max_states", type=int, default=400_000,
                   help="V_boss 段 search_quotient 状态上限")
    return p.parse_args()


def _fmt_state(st):
    h = st.hero
    keys = {k: v for k, v in h.keys.items() if v}
    return f"{st.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} 钥={keys}"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = _parse_args()
    ladder = [int(x) for x in args.ladder.split(",") if x.strip()]

    print(f"=== §S29 定生死探针·手排强基因 → seam → V_boss  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    print(f"组装电池组(build_harness · persistent=True)…", flush=True)
    t0 = time.time()
    H = build_harness(persistent=True)
    start, zone, step = H["start"], H["zone"], H["step"]
    roster_fit, big, zone_fids = H["roster_fit"], H["big"], H["zone_fids"]
    decode_cache = H["decode_cache"]
    red_block, red_markers = H["red_block"], H["red_markers"]
    pool, block_markers, block_cells, sword_block, shield_block = build_pool_13(H)
    pool_set = set(pool)
    seg_step = make_seg_step(step)
    print(f"  就绪 {time.time()-t0:.1f}s  pool=13  剑块={sword_block} 盾块={shield_block} 红钥块={red_block}",
          flush=True)
    print(f"  SEAM={SEAM}  BOSS_GOAL={BOSS_GOAL}  起点={_fmt_state(start)}", flush=True)

    # ── V_boss(memo·键=_nav_key(seam))──
    vboss_memo = {}
    wiring_broken = []  # 收集『配线前提破』(只报不瞎改)

    def query_vboss(seam_state):
        k = _nav_key(seam_state)
        if k in vboss_memo:
            return vboss_memo[k]
        if seam_state._single_floor_copy is not False:
            msg = ("★配线前提破：seam 态 _single_floor_copy 非 False(跨层搜会共享引用污染)→ "
                   "V_boss 不可信。报玩家·不瞎改。")
            print("    " + msg, flush=True)
            wiring_broken.append(msg)
            return (0, False)
        res = search_quotient(seam_state, BOSS_GOAL, seg_step, max_states=args.max_states,
                              cross_floor=True, beam_k=None, distinguish_doors=True)
        v = (res.final_hp if res.found else 0, res.found)
        vboss_memo[k] = v
        return v

    # ── 坐标→块映射(不猜·全报) ──
    print("\n" + "=" * 78)
    print("【映射】玩家坐标 → 真实块 id(cell_to_block·命中不了/不在pool_13/红钥不匹配 全标出)")
    print("=" * 78)
    gene_fids = {fid for (_l, fid, _x, _y) in HAND_GENE} | {RED_KEY[1]}
    fids = sorted(set(zone_fids) | gene_fids)
    bidx = build_block_index(fids)
    c2b = bidx["cell_to_block"]

    chromosome = []
    issues = []
    for (label, fid, x, y) in HAND_GENE:
        cell = (fid, x, y)
        bid = c2b.get(cell)
        if bid is None:
            print(f"  ⚠ {label:11} {cell} → 【未命中任何块】(非道具格/墙/空地)")
            issues.append(f"{label}{cell} 未命中")
            continue
        in_pool = bid in pool_set
        dup = bid in chromosome
        tag = "✓在pool_13" if in_pool else "✗不在pool_13"
        dtag = " 【重复·同块已在序】" if dup else ""
        print(f"  {label:11} {cell} → 块{bid}  {tag}{dtag}")
        if in_pool and not dup:
            chromosome.append(bid)
        elif not in_pool:
            issues.append(f"{label}{cell}→{bid} 不在pool_13")
        elif dup:
            issues.append(f"{label}{cell}→{bid} 与前序重复")

    # 红钥
    rk_cell = (RED_KEY[1], RED_KEY[2], RED_KEY[3])
    rk_bid = c2b.get(rk_cell)
    rk_match = (rk_bid == red_block)
    print(f"  {RED_KEY[0]:11} {rk_cell} → 块{rk_bid}  "
          f"{'✓=电池组红钥块' if rk_match else f'⚠≠电池组红钥块{red_block}'}")
    if not rk_match:
        issues.append(f"红钥{rk_cell}→{rk_bid} ≠ 电池组红钥块{red_block}")

    print(f"\n  映射结果：chromosome={len(chromosome)} 个 pool 块(玩家序)；红钥末腿={red_block}")
    print(f"  pool 块未被玩家覆盖的：{sorted(pool_set - set(chromosome))}")
    if issues:
        print(f"  ⚠ 映射存疑 {len(issues)} 项(报玩家·已按规则处理·下面照样跑)：")
        for s in issues:
            print(f"      - {s}")
    else:
        print("  映射全部干净命中。")
    print(f"  PART A 用 final_goal={red_block}(电池组权威红钥块·非玩家坐标·守 §S26 末腿语义)", flush=True)

    # ════════════════════════════ PART A：忠实 GA 管线 ════════════════════════════
    print("\n" + "=" * 78)
    print("【PART A】忠实 GA 管线：_decode_with_order(@%d·带禁区+红钥末腿) → navigate seam → V_boss"
          % args.decode_maxpops)
    print("  (= GA 真会对这条基因做的事·有 §S15 禁区约束)")
    print("=" * 78)
    ta = time.time()
    _tok, term, normalized, verdict = _decode_with_order(
        chromosome, start, zone, step, decode_cache, max_pops=args.decode_maxpops,
        block_markers=block_markers, block_cells=block_cells,
        final_goal=red_block, final_markers=red_markers, final_max_pops=args.decode_maxpops)
    print(f"  decode 耗时 {time.time()-ta:.0f}s", flush=True)
    if verdict["invalid"]:
        print(f"  ★verdict=【INVALID】(§S15 排序不可实现·整条作废) navigated={verdict['navigated']} "
              f"depth={verdict['depth']}  _invalid_score={_invalid_score(verdict):.0f}")
    else:
        base = fitness(term, roster_fit, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
        print(f"  verdict: invalid=False navigated={verdict['navigated']} depth={verdict['depth']} "
              f"reached_final(红钥到手)={verdict['reached_final']}")
        print(f"  base(fitness 终评)={base:.1f}")
    picked = list(normalized)
    not_picked = [b for b in chromosome if b not in set(picked)]
    print(f"  进包序(normalized·真实先后)：{picked}")
    print(f"  基因里【没进包】的块：{not_picked if not_picked else '(全进包)'}")
    print(f"  盾块进包？{shield_block in set(picked)}   红钥块进包(reached_final)？{verdict['reached_final']}")
    print(f"  终态：{_fmt_state(term)}", flush=True)

    print("\n  ── PART A seam 腿：navigate_to(term, SEAM, @%d) ──" % args.decode_maxpops)
    ts = time.time()
    seamA, _m, reachedA = navigate_to(term, SEAM, zone, step, max_pops=args.decode_maxpops, cache=decode_cache)
    print(f"    {time.time()-ts:.0f}s  reached_seam={reachedA}", flush=True)
    vbossA, foundA = 0, False
    if reachedA:
        print(f"    seam 态：{_fmt_state(seamA)}")
        vbossA, foundA = query_vboss(seamA)
        print(f"    ★V_boss={vbossA}(found={foundA})", flush=True)
    else:
        print(f"    seam 未到达 → V_boss=0(PART A)")

    # ════════════════════════════ PART B：架构天花板 ════════════════════════════
    print("\n" + "=" * 78)
    print(f"【PART B】架构天花板：手动逐块 navigate(★无 forbidden) 升档 max_pops={ladder} 破预算假阴性")
    print("  (问『生成预算足够、无禁区约束下，这条基因物理上能不能爬到 MT9 拿盾/拿红钥/到 seam』)")
    print("=" * 78)

    def reach_escalating(st, goal_cell, tag):
        """逐档 max_pops 试到 goal_cell·break on reach。返回 (final_state, reached, hit_mp, secs)。"""
        for mp in ladder:
            tt = time.time()
            fst, _mv, rc = navigate_to(st, goal_cell, zone, step, max_pops=mp, cache=decode_cache)
            secs = time.time() - tt
            if rc:
                return fst, True, mp, secs
            print(f"      [{tag}] max_pops={mp:>7} reached=False {secs:5.0f}s(烧满)", flush=True)
        return st, False, None, 0.0

    def is_taken(bid, st, markers):
        return all(_taken(st, c) for c in markers)

    state = start
    # legs = 玩家序里在 pool 的块(去重保序) + 红钥块末腿
    seen_b = set()
    ordered = []
    for (label, fid, x, y) in HAND_GENE:
        bid = c2b.get((fid, x, y))
        if bid in pool_set and bid not in seen_b:
            ordered.append((label, bid))
            seen_b.add(bid)
    ordered.append((RED_KEY[0], red_block))

    shield_taken_at = None
    red_taken_at = None
    print(f"  起点：{_fmt_state(state)}\n")
    for i, (label, bid) in enumerate(ordered):
        goal_cell = goal_to_cell(bid)
        nst, rc, hit_mp, secs = reach_escalating(state, goal_cell, f"{i:02d}{label}")
        if rc:
            state = nst
        # 进包检查(用真实 marker：pool 块→block_markers·红钥→red_markers)
        mk = red_markers if bid == red_block else block_markers.get(bid, (bid,))
        got = is_taken(bid, state, mk)
        if bid == shield_block and got and shield_taken_at is None:
            shield_taken_at = hit_mp
        if bid == red_block and got and red_taken_at is None:
            red_taken_at = hit_mp
        flag = f"✓@{hit_mp}" if rc else "✗(升满全档未到)"
        print(f"  [{i:02d}] {label:11} 块{bid} nav={flag} {secs:4.0f}s  进包={got}  态={_fmt_state(state)}",
              flush=True)

    print(f"\n  ── PART B seam 腿：navigate_to(state, SEAM) 升档 {ladder} ──")
    seamB, reachedB, seam_mp, seam_secs = reach_escalating(state, SEAM, "SEAM")
    print(f"    seam reached={reachedB}" + (f" @max_pops={seam_mp} {seam_secs:.0f}s" if reachedB else ""),
          flush=True)
    vbossB, foundB = 0, False
    if reachedB:
        print(f"    seam 态：{_fmt_state(seamB)}")
        vbossB, foundB = query_vboss(seamB)
        print(f"    ★V_boss={vbossB}(found={foundB})", flush=True)

    # ════════════════════════════ 归类 + 报玩家 ════════════════════════════
    shield_ok = shield_taken_at is not None
    red_ok = red_taken_at is not None
    print("\n" + "=" * 78)
    print("【归类·按玩家定义的情况1/2/3】★脚本只出客观数·甲/乙玩家拍")
    print("=" * 78)
    print(f"  PART B 关键三点：")
    print(f"    ① 爬到 MT9 拿到盾？  {shield_ok}" + (f"(@max_pops={shield_taken_at})" if shield_ok else ""))
    print(f"    ② 红钥到手？        {red_ok}" + (f"(@max_pops={red_taken_at})" if red_ok else ""))
    print(f"    ③ 送到 seam？       {reachedB}" + (f"(@max_pops={seam_mp})" if reachedB else "")
          + f"   V_boss={vbossB}")
    print()
    if not shield_ok:
        case = "情况1：连爬到 MT9 拿盾都做不到 → navigate 执行问题 → 支持【乙】"
    elif shield_ok and not reachedB:
        case = "情况2：拿到盾但 navigate 送不到 seam → 架构能拿块但送 seam 过不去 → 支持【乙】(末腿/路径瓶颈)"
    elif shield_ok and reachedB and vbossB > 0:
        case = ("情况3：拿盾 + 送到 seam + V_boss>0 → 架构能到 seam、GA 没到纯搜索力(pop8/gen3 小) → "
                "甲理论可行(但 navigate 不绕路/不省钥的天花板仍在)")
    else:  # shield_ok and reachedB and vbossB==0
        case = ("情况3'(边界)：拿盾 + 送到 seam 但 V_boss=0 → 架构能把态送到 seam(reach 这关过了)、"
                "但该 seam 态过不了 boss(多半红钥到手否=" + str(red_ok) + "/血不够)→ reach 角度近情况3、"
                "过 boss 角度仍缺 → 甲/乙都不能据此单独拍，看红钥与血")
    print(f"  ▶ {case}")

    print("\n  ── PART A vs PART B 对照(隔离 搜索力/forbidden/budget vs 真架构墙) ──")
    print(f"    PART A(GA 真管线@{args.decode_maxpops}·带禁区)：reached_seam={reachedA} V_boss={vbossA}")
    print(f"    PART B(无禁区·升档{ladder})：       reached_seam={reachedB} V_boss={vbossB}")
    if (not reachedA) and reachedB:
        print("    → A 到不了而 B 到 = 禁区/budget/搜索力问题(非架构墙)。")
    elif reachedA and reachedB:
        print("    → A、B 都到 = 架构能把这条基因送到 seam。")
    elif (not reachedA) and (not reachedB):
        print("    → A、B 都到不了(连无禁区+升满档也到不了)= 强信号『真到不了』(架构/路径)。")

    print("\n" + "=" * 78)
    print("★【玩家的 navigate_to 天花板判断·探针证不证都正视】：")
    print("  navigate_to 贪心、血够就永不绕路、蓝钥不省——路径决策锁在 navigate 内部、GA 控制不了")
    print("  (从 MT7 骷髅一路撞过来的)。即便落情况3(能到 seam)，这个 navigate 天花板依然在。")
    print("  玩家倾向『把所有块+绕路决策丢进去、让 MCTS 搜路径而非 navigate 外包』= 乙的完整形态")
    print("  (不只块层、连路径决策一起搜)。")
    print("=" * 78)
    if wiring_broken:
        print(f"\n⚠⚠ 配线前提破 {len(wiring_broken)} 次(_single_floor_copy 非 False)→ 上面 V_boss 不可信！")
        print("   按红线『配线有 bug 报别瞎改』——报玩家定，不在此改封板件。")
    print("\n★甲/乙最终由玩家拍——上面是客观数 + 情况归类，请你定。")


if __name__ == "__main__":
    main()
