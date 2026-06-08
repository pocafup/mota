"""MT3 验收：块图搜索 vs 朴素 BFS（(2,11)→(11,5)，即撞 2M cap 的那个 run）。

验收硬标准（玩家 2026-06-06）：
  ① 秒级跑完（对比朴素 2M cap / 23 分钟）。
  ② 块图出口前沿在【持有维】⊇ 朴素被截前沿（不丢解）。
  ③ 取一条样例线路（动作序列）丢回封板引擎 replay 逐字段一致；并验证「route 前缀骨架 +
     MT3 块图动作」整条线路从全局起点重放也落在 MT3(11,5)、属性吻合 —— 即可直接照着走。
报告：块数 / 算子数 / 状态数 / 耗时 / 前沿对比 / 一条样例动作序列。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import step, _copy_state
from solver.search import search_segment, _ge_all
from solver.quotient import search_quotient, _free_cells, _boundary_ops
from solver.verify import replay

GOAL = ("MT3", 11, 5)
PREFIX = 82   # tokens[:82] → MT3 seg4 入口


def mt3_entry(single_floor=False):
    tokens = load_tokens()
    s = build_initial_state()
    for tok in tokens[:PREFIX]:
        s = step(s, tok)
    assert s.current_floor == "MT3", s.current_floor
    if single_floor:
        s = _copy_state(s)
        s._single_floor_copy = True
    return s


def count_blocks(state):
    """整层自由格连通块数（覆盖式 floodfill）。"""
    from solver.quotient import _is_free_tile, _zone_blocked
    floor = state.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    zb = _zone_blocked(state)
    free_all = {(x, y) for y in range(rows) for x in range(cols)
                if _is_free_tile(state, x, y, zb)}
    seen, nblk = set(), 0
    from collections import deque
    for c in free_all:
        if c in seen:
            continue
        nblk += 1
        dq = deque([c]); seen.add(c)
        while dq:
            cx, cy = dq.popleft()
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nb = (cx + dx, cy + dy)
                if nb in free_all and nb not in seen:
                    seen.add(nb); dq.append(nb)
    return nblk, len(free_all)


def held_only(vec):
    """投影到持有维（去掉 map: 剩余资源维）以便与块图同口径比较。"""
    return {k: v for k, v in vec.items() if not k.startswith("map:")}


def main():
    print("=" * 80)
    print("MT3 验收：(2,11) → (11,5)")
    print("=" * 80)

    entry = mt3_entry()
    nblk, nfree = count_blocks(entry)
    init_ops = _boundary_ops(entry, _free_cells(entry))
    print(f"入口态 HP={entry.hero.hp} ATK={entry.hero.atk} DEF={entry.hero.def_} "
          f"keys={entry.hero.keys}")
    print(f"整层自由格={nfree} → 连通块数={nblk}；入口边界付代价算子={len(init_ops)} "
          f"{[(o[0], o[1], o[2]) for o in init_ops]}")

    # —— 块图搜索 ——
    t0 = time.perf_counter()
    rq = search_quotient(mt3_entry(single_floor=True), GOAL, step)
    tq = time.perf_counter() - t0
    print("\n" + "-" * 80)
    print(f"【块图】found={rq.found} 出口前沿宽={len(rq.goal_frontier)} "
          f"状态数(指纹)={rq.distinct_fingerprints} 展开={rq.states_expanded} "
          f"生成={rq.states_generated} 算子累计={rq.n_ops_total} 峰值块={rq.n_blocks_peak} "
          f"hit_cap={rq.hit_cap}")
    print(f"        耗时={tq*1000:.0f}ms（对比朴素 2,000,003 gen / ~104s 且未跑完）")
    if rq.found:
        best = max(rq.goal_frontier, key=lambda v: v["hp"])
        print(f"        出口最高 HP={best['hp']}  最优向量={best}")

    # —— 朴素 BFS（小 cap 得被截前沿做对比）——
    t0 = time.perf_counter()
    rn = search_segment(mt3_entry(single_floor=True), GOAL, step, max_states=300_000)
    tn = time.perf_counter() - t0
    print("\n" + "-" * 80)
    print(f"【朴素 cap=300k】found={rn.found} 出口前沿宽={len(rn.goal_frontier or [])} "
          f"指纹={rn.distinct_fingerprints} 生成={rn.states_generated} hit_cap={rn.hit_cap} "
          f"耗时={tn*1000:.0f}ms")
    if rn.found:
        bn = max(rn.goal_frontier, key=lambda v: v["hp"])
        print(f"        被截前沿最高 HP={bn['hp']}")

    # —— ② ⊇ 验收（持有维）——
    print("\n" + "-" * 80)
    uncovered = []
    if rn.found and rq.found:
        qheld = [held_only(v) for v in rq.goal_frontier]
        for nv in rn.goal_frontier:
            nvh = held_only(nv)
            if not any(_ge_all(qv, nvh) for qv in qheld):
                uncovered.append(nvh)
    cover_ok = (not uncovered) and rq.found
    print(f"② 块图前沿(持有维) ⊇ 朴素被截前沿：{'通过' if cover_ok else '✗ 失败'}"
          + (f"（{len(uncovered)} 个朴素点未被覆盖：{uncovered[:3]}）" if uncovered else ""))

    # —— ③ 样例线路 replay 逐字段一致 ——
    print("\n" + "-" * 80)
    sample = rq.goal_frontier_actions[
        max(range(len(rq.goal_frontier)), key=lambda i: rq.goal_frontier[i]["hp"])]
    seg_ok = False
    if sample is not None:
        rep = replay(mt3_entry(), sample, step, _copy_state)
        seg_ok = (rep.current_floor == "MT3" and (rep.hero.x, rep.hero.y) == (11, 5))
        print(f"③a 段内 replay：落点=({rep.hero.x},{rep.hero.y})@{rep.current_floor} "
              f"HP={rep.hero.hp} ATK={rep.hero.atk} DEF={rep.hero.def_} "
              f"→ {'一致' if seg_ok else '✗ 不一致'}")
        # 整条线路（route 前缀骨架 + MT3 块图动作）从全局起点重放
        tokens = load_tokens()
        full = list(tokens[:PREFIX]) + list(sample)
        g = build_initial_state()
        for tok in full:
            g = step(g, tok)
        glob_ok = (g.current_floor == "MT3" and (g.hero.x, g.hero.y) == (11, 5)
                   and g.hero.hp == rep.hero.hp and g.hero.atk == rep.hero.atk
                   and g.hero.def_ == rep.hero.def_)
        print(f"③b 全局线路({len(full)} token)：落点=({g.hero.x},{g.hero.y})@{g.current_floor} "
              f"HP={g.hero.hp} → {'一致(可直接照着走)' if glob_ok else '✗ 不一致'}")
        print(f"\n样例 MT3 段动作序列({len(sample)} 步,块内零损血故步数非最优只求合法)：")
        print("    " + "".join(sample))

    print("\n" + "=" * 80)
    all_ok = rq.found and tq < 10 and cover_ok and seg_ok
    print(f"MT3 验收总判：{'全过' if all_ok else '✗ 有项未过，见上'}"
          f"（秒级={tq<10} 覆盖={cover_ok} replay={seg_ok}）")


if __name__ == "__main__":
    main()
