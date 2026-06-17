"""【方向3·段链端到端验证】用现成 search_quotient 把一区切段、逐段穷尽搜、接缝串联，
验证能否端到端"攒攻防→拿红钥→打过 boss"。首要目标=能否端到端打过 boss（慢没关系）。

只读：复用 extract_zone1_milestones 的加载（明确指名新存档 51_20260616144514，不靠 glob）、
sim.step、solver.quotient.search_quotient、solver.search 的 Pareto 口径。绝不改产品码。

接缝机制（validate_boss 已验证可行）：search_quotient 返回 goal_frontier_actions（每个出口
  Pareto 点的可照走动作串）→ 用真实 step 重放(replay_actions)重建出口完整态 → 作下段起点。
段间 Pareto 去重：用 solver.search._value_map(越多越好资源向量) + _ge_all(多维支配)，控前沿规模。
"打过 boss"判据：到达队长格 MT10(6,1)（非 MT11(6,10)，避免搜索选"跳过 boss 直接下楼"）。

用法：python -u analysis/seg_chain_verify.py [--seg boss|redkey|chain] [--max-states 600000]
"""
import argparse
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

from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step
from solver.quotient import search_quotient
from solver.search import _value_map, _ge_all

CAPTAIN = ("MT10", 6, 1)      # 队长格 = "打过 boss"真判据（=新存档终点）
REDKEY_CELL = ("MT8", 10, 2)  # 红钥格（tok945 一区唯一红钥）


def replay_to_token(tok_idx):
    """重放真实新存档到 token[tok_idx]（含），返回该里程碑真实态。"""
    s = build_initial_state()
    tokens, _ = load_tokens()
    for t in tokens[:tok_idx + 1]:
        s = step(s, t)
    return s


def make_seg_step(allowed):
    """把搜索框在 allowed 楼层集：踏出本段的子态置 dead 裁掉。"""
    aset = set(allowed)

    def seg_step(state, action):
        ns = step(state, action)
        if ns.current_floor not in aset:
            ns.dead = True
        return ns
    return seg_step


def replay_actions(start, actions):
    """从 start 用真实 step 独立重放动作串，返回终态（接缝重建出口态 + 校验）。"""
    s = start
    for a in actions:
        s = step(s, a)
    return s


def pareto_dedup(items):
    """items: [(state, acts)] → 按 _value_map 多维支配去重，保非支配前沿。
    相等向量保留靠前一个（动作短的优先靠前传入）。O(n^2)，n=前沿规模(几十~几百)。"""
    scored = [(_value_map(s), s, a) for s, a in items]
    keep = []
    for i, (vi, si, ai) in enumerate(scored):
        dominated = False
        for j, (vj, sj, aj) in enumerate(scored):
            if i == j:
                continue
            ge_ji = _ge_all(vj, vi)
            if ge_ji and not _ge_all(vi, vj):     # vj 严格支配 vi
                dominated = True
                break
            if ge_ji and _ge_all(vi, vj) and j < i:  # 等价，保留靠前
                dominated = True
                break
        if not dominated:
            keep.append((si, ai))
    return keep


def fmt(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    items = {k: v for k, v in h.items.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 道具={items} kills={h.kill_count} dead={s.dead} won={s.won}")


def run_segment(entry_states, goal_cell, allowed, max_states, label, cross_floor=True):
    """对一组入口态逐个跑 search_quotient → 收出口前沿（重放重建+校验）→ 段间 Pareto 去重。
    返回 (exits, any_found)。exits=[(出口态, 累积动作串)]。"""
    seg_step = make_seg_step(allowed)
    gf, gx, gy = goal_cell
    print("\n" + "=" * 80)
    print(f"段【{label}】 goal={goal_cell} 楼层={sorted(allowed)} "
          f"cross_floor={cross_floor} 入口态数={len(entry_states)}")
    print("=" * 80)
    all_exits = []
    any_found = False
    for ei, (st, acts0) in enumerate(entry_states):
        print(f"\n  ── 入口[{ei}] {fmt(st)}")
        assert st._single_floor_copy is False, "起点 _single_floor_copy 须 False（跨层安全深拷）"
        t0 = time.time()
        res = search_quotient(st, goal_cell, seg_step, max_states=max_states,
                              cross_floor=cross_floor, beam_k=None, distinguish_doors=True)
        secs = time.time() - t0
        print(f"     found={res.found} 耗时={secs:.1f}s hit_cap={res.hit_cap} "
              f"distinct_fp={res.distinct_fingerprints} expanded={res.states_expanded} "
              f"generated={res.states_generated} 前沿={len(res.goal_frontier)} "
              f"goal_hits={res.goal_hits}")
        print(f"     fp_by_floor={dict(res.fp_by_floor)}")
        if not res.found:
            print(f"     ✗ 此入口搜不到 goal（属性/钥匙不够 or 段裁切 or 撞 cap）")
            continue
        any_found = True
        # 接缝：每个出口前沿点 → 重放重建完整态 + 校验到达 goal
        n_ok = 0
        for out_acts in res.goal_frontier_actions:
            ex = replay_actions(st, list(out_acts))
            if ex.current_floor == gf and (ex.hero.x, ex.hero.y) == (gx, gy) and not ex.dead:
                all_exits.append((ex, tuple(acts0) + tuple(out_acts)))
                n_ok += 1
            else:
                print(f"     ⚠ 出口重放未达 goal/dead：{fmt(ex)}")
        print(f"     出口重放校验通过 {n_ok}/{len(res.goal_frontier_actions)}")
    exits = pareto_dedup(all_exits) if all_exits else []
    print(f"\n  段【{label}】汇总：any_found={any_found} "
          f"出口前沿(段间Pareto去重后)={len(exits)}（去重前 {len(all_exits)}）")
    if exits:
        hp_max = max(exits, key=lambda t: t[0].hero.hp)
        print(f"  max-HP 出口：{fmt(hp_max[0])}  动作串长={len(hp_max[1])}")
    return exits, any_found


def seg_boss(max_states):
    """段A 基线：红钥在手、第5次进 MT10(tok1019) → 队长格(6,1)。单层 MT10。
    预期搜通（=validate_boss 验证A 的新存档版）。量打 boss 段规模/耗时。"""
    start = replay_to_token(1019)   # 第5次进 MT10(3,9) HP560 ATK26 DEF26 红1
    return run_segment([(start, ())], CAPTAIN, {"MT10"}, max_states,
                       "打boss基线(红钥在手→队长格)", cross_floor=False)


def seg_redkey(max_states):
    """段B 判据：铁盾刚到手态(tok454, MT9(9,7) ATK22 DEF20 钥黄2蓝1) → 红钥格 MT8(10,2)。
    递增 ALLOWED 测"拿红钥需要几层 + 状态规模"——交错回访段爆不爆的直接判据。
    ⚠ 起点在 MT9（铁盾就在 MT9(9,7)），故 ALLOWED 单 {MT8} 必平凡 found=False（起点不在 MT8）。"""
    start = replay_to_token(454)    # 铁盾刚到手 MT9(9,7) HP166 ATK22 DEF20 钥黄2蓝1（里程碑表已坐实）
    print("\n### 段B 判据：从铁盾态搜红钥，递增楼层看几层能通 + 规模 ###")
    for allowed in ({"MT8", "MT9"}, {"MT7", "MT8", "MT9"}):  # 起点在 MT9，单 {MT8} 已知平凡失败故跳过
        exits, found = run_segment([(start, ())], REDKEY_CELL, allowed, max_states,
                                   f"红钥获取@{sorted(allowed)}", cross_floor=True)
        if found:
            print(f"  ★ {sorted(allowed)} 即可搜到红钥 → 停止递增")
            return exits, found
    print("  ⚠ 到 3 层仍未搜到红钥（或撞 cap）——交错回访段超出现成穷尽能力")
    return [], False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", choices=["boss", "redkey", "chain"], default="boss")
    ap.add_argument("--max-states", type=int, default=600_000)
    args = ap.parse_args()

    print("=" * 80)
    print(f"方向3 段链验证  seg={args.seg}  max_states={args.max_states}")
    print("=" * 80)
    tokens, _ = load_tokens()
    print(f"新存档 token 数={len(tokens)}（应=1044）")

    if args.seg == "boss":
        seg_boss(args.max_states)
    elif args.seg == "redkey":
        seg_redkey(args.max_states)
    elif args.seg == "chain":
        print("（chain 端到端串联待单段判据确认后再开）")


if __name__ == "__main__":
    main()
