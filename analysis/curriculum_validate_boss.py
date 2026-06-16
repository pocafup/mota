"""【课程学习·定生死验证】打 boss 这一段(最后一段)能不能用 search_quotient 穷尽搜出来？

§S27 课程学习框架的"生死判据"：若连最简单的 boss 段都搜不动，整个框架要重想。
本脚本从真实存档(剩余HP14382)里取"刚进 MT10 打 boss 那一刻"的状态(tok1168)，对它跑
solver.quotient.search_quotient(穷尽 Pareto，beam_k=None)，dump 真实复杂度：
  · 验证A 核心 boss 战：goal=队长格 MT10(6,1)，cross_floor=False(单层)。
      —— 必须开红门→踩(6,5)触发埋伏→清8小怪→杀队长，测纯 boss 战搜索成本。
  · 验证B 整段(到下一区)：goal=MT11(6,10)，cross_floor=True，楼层限 {MT10,MT11}。
      —— 测全段成本 + 揭示"直接下楼跳 boss vs 打 boss 拿战利品"的出口 Pareto 权衡，
         并用 solver.fitness 给每个出口打分(段奖励=出口 fitness 而非裸 HP 的设计佐证)。

只读：复用 build_initial_state/load_tokens/step/search_quotient/fitness，绝不改产品码。
"""
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from analysis.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step
from solver.quotient import search_quotient, _free_cells, _boundary_ops, _expand_op
from solver.fitness import build_zone1_roster, calibrate_big, fitness, fitness_breakdown

BOSS_ENTRY_TOK = 1168          # 真实存档第5次进 MT10 = 打 boss visit（dump 已坐实）
REAL_EXIT = "HP701 ATK30 DEF30（真实存档 tok1250 出 MT10→MT11）"


def snap(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 金={h.gold} kills={h.kill_count} dead={s.dead} won={s.won}")


def boss_entry_state():
    """重放真实存档到刚进 MT10(打boss那一刻)，返回该状态。"""
    s = build_initial_state()
    tokens = load_tokens()
    for tok in tokens[:BOSS_ENTRY_TOK + 1]:
        s = step(s, tok)
    return s


def print_result(tag, res, secs):
    print(f"\n────── {tag} 结果 ──────")
    print(f" found={res.found}  final_hp(最大HP出口)={res.final_hp}")
    print(f" 耗时 = {secs:.2f}s")
    print(f" states_expanded(展开节点) = {res.states_expanded}")
    print(f" states_admitted(入队去重后) = {res.states_admitted}")
    print(f" states_generated(生成子态) = {res.states_generated}")
    print(f" distinct_fingerprints(去重指纹) = {res.distinct_fingerprints}")
    print(f" n_waves(BFS层数) = {res.n_waves}  frontier_peak(波峰宽) = {res.frontier_peak}")
    print(f" n_blocks_peak(最大自由块) = {res.n_blocks_peak}  n_ops_total(算子总数) = {res.n_ops_total}")
    print(f" goal_hits(到达目标次数) = {res.goal_hits}  hit_cap(撞上限) = {res.hit_cap}")
    print(f" floors_seen(搜到的楼层) = {res.floors_seen}")
    print(f" fp_by_floor(各层指纹数) = {dict(res.fp_by_floor)}")
    print(f" 出口 Pareto 前沿点数 = {len(res.goal_frontier)}")


def replay_actions(start, actions):
    """从 start 用真实 step 独立重放一串动作，返回终态(独立校验)。"""
    s = start
    for a in actions:
        s = step(s, a)
    return s


def main():
    start = boss_entry_state()
    print("========== 打 boss 段起点(真实存档 tok1168) ==========")
    print(f" {snap(start)}")
    print(f" _single_floor_copy = {getattr(start, '_single_floor_copy', '??')}（跨层搜须 False）")

    # ══════════ 验证 A：核心 boss 战（单层，goal=队长格 (6,1)）══════════
    print("\n\n========== 验证A：核心 boss 战  goal=MT10(6,1)队长格  cross_floor=False 穷尽 ==========")
    admitted_log = []

    def log_admit(child, acts):
        admitted_log.append((len(acts), snap(child)))

    t0 = time.time()
    resA = search_quotient(start, ("MT10", 6, 1), step,
                           max_states=2_000_000, cross_floor=False, beam_k=None,
                           on_admit=log_admit, distinguish_doors=True)
    print_result("验证A", resA, time.time() - t0)
    print(" ── 全部入队状态(诊断)──")
    for n, sn in admitted_log:
        print(f"   步{n:3} | {sn}")
    if resA.found:
        ex = replay_actions(start, resA.actions)
        print(f" 最优(最大HP)杀队长出口独立重放 = {snap(ex)}")
        print(f" 动作串长度 = {len(resA.actions)}")

    # ══════════ 验证 B：整段到下一区（跨层，goal=MT11(6,10)，限 {MT10,MT11}）══════════
    ALLOWED = {"MT10", "MT11"}

    def seg_step(state, action):
        ns = step(state, action)
        if ns.current_floor not in ALLOWED:   # 段外楼层(回 MT9 等)→裁掉，把搜索框在本段
            ns.dead = True
        return ns

    print("\n\n========== 验证B：整段到下一区  goal=MT11(6,10)  cross_floor=True 限{MT10,MT11} 穷尽 ==========")
    t0 = time.time()
    resB = search_quotient(start, ("MT11", 6, 10), seg_step,
                           max_states=2_000_000, cross_floor=True, beam_k=None,
                           distinguish_doors=True)
    print_result("验证B", resB, time.time() - t0)

    # ══════════ 验证 C：从"红门已开"态起搜（隔离红门支配 bug，测埋伏→队长→出口）══════════
    print("\n\n========== 验证C：红门已开态起搜  goal=MT11(6,10)  cross_floor=True 限{MT10,MT11} 穷尽 ==========")
    free0 = _free_cells(start)
    door_op = [o for o in _boundary_ops(start, free0, cross_floor=True) if o[1:3] == (6, 9)]
    if not door_op:
        print(" ⚠ 起点找不到红门算子，跳过C")
    else:
        door_open, _dm = _expand_op(start, free0, door_op[0], step)
        print(f" 红门已开起点 = {snap(door_open)}  _single_floor_copy={getattr(door_open,'_single_floor_copy','??')}")
        t0 = time.time()
        resC = search_quotient(door_open, ("MT11", 6, 10), seg_step,
                               max_states=2_000_000, cross_floor=True, beam_k=None,
                               distinguish_doors=True)
        print_result("验证C", resC, time.time() - t0)
        if resC.found:
            rosterC, zone_fidsC, _ = build_zone1_roster(start)
            exitsC = [replay_actions(door_open, a) for a in resC.goal_frontier_actions]
            bigC = calibrate_big([door_open] + exitsC, rosterC)
            rowsC = sorted(
                ((fitness(ex, rosterC, bigC, zone_fidsC), ex, a) for ex, a in zip(exitsC, resC.goal_frontier_actions)),
                key=lambda r: r[0], reverse=True)
            print(f" 验证C 出口前沿 {len(rowsC)} 个，fitness 降序前8：")
            for fit, ex, a in rowsC[:8]:
                h = ex.hero
                print(f"   fit={fit:10.1f} | HP={h.hp:4} ATK={h.atk} DEF={h.def_} 金={h.gold} kills={h.kill_count} 步={len(a)}")
            bf = rowsC[0]
            print(f" 验证C 最优fitness出口: {snap(bf[1])}")
            ex = replay_actions(door_open, bf[2])
            print(f" 独立重放校验 → {snap(ex)} "
                  f"{'✓到MT11(6,10)' if (ex.current_floor=='MT11' and (ex.hero.x,ex.hero.y)==(6,10)) else '✗未到目标'}")
            print(f" 真实存档出口: {REAL_EXIT}")

    if not resB.found:
        print("\n ⚠ 验证B 未找到到 MT11 的路径（红门支配 bug，见上方诊断）。")
        return

    # ── 出口 Pareto 前沿逐点 fitness：揭示"跳boss vs 打boss"────────────────────
    roster, zone_fids, _ = build_zone1_roster(start)
    # big 标定：用起点 + 各前沿出口态作参照集（口径稳健、排序不敏感）
    exits = [replay_actions(start, acts) for acts in resB.goal_frontier_actions]
    big = calibrate_big([start] + exits, roster)
    print(f"\n────── 验证B 出口前沿 fitness（roster={len(roster)}怪, big={big}）──────")
    rows = []
    for vec, acts, ex in zip(resB.goal_frontier, resB.goal_frontier_actions, exits):
        fb = fitness_breakdown(ex, roster, big, zone_fids)
        rows.append((fb["total"], ex, acts, fb))
    rows.sort(key=lambda r: r[0], reverse=True)
    print(f" 前沿共 {len(rows)} 个出口，按 fitness 降序：")
    for total, ex, acts, fb in rows:
        h = ex.hero
        print(f"  fit={total:10.1f} | HP={h.hp:4} ATK={h.atk} DEF={h.def_} 金={h.gold} "
              f"kills={h.kill_count} | 主干={fb['main_equiv_hp']:.0f} 血瓶项={fb['potion_term']:.0f} "
              f"钥项={fb['key_term']:.0f} | 步数={len(acts)}")

    best_fit = rows[0]
    best_hp = max(rows, key=lambda r: r[1].hero.hp)
    print(f"\n 最优fitness出口: fit={best_fit[0]:.1f}  {snap(best_fit[1])}")
    print(f" 最大HP出口:      HP={best_hp[1].hero.hp}  {snap(best_hp[1])}")
    print(f" 真实存档出口:    {REAL_EXIT}")
    if best_fit[1].hero.atk == start.hero.atk and best_fit[1].hero.kill_count <= start.hero.kill_count + 1:
        print(" ★ 最优fitness出口 ATK 未涨/几乎没杀 → 搜索选择【跳过 boss 直接下楼】（段奖励须含携带价值！）")
    else:
        print(" ★ 最优fitness出口 打了 boss（ATK/kills 上涨）→ fitness 正确引导吃战利品")

    # 独立重放最优fitness路径校验
    ex = replay_actions(start, best_fit[2])
    print(f"\n 最优fitness路径独立重放校验 → {snap(ex)}  "
          f"{'✓到达MT11(6,10)' if (ex.current_floor=='MT11' and (ex.hero.x,ex.hero.y)==(6,10)) else '✗未到目标'}")


if __name__ == "__main__":
    main()
