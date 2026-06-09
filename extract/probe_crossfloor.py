"""跨层楼梯缩点【真实膨胀】探针（solver/quotient.py 跨层第一步落地验证）。

口径（data/games51/floor_graph.md §8 第一步）：解除单层限制，楼梯(changeFloor)格作 stair 算子、
真实 step() 触发换层（免资源代价），门禁未满足的楼梯格自然不生成边；事件传送(MT3 重置/MT40/MT24)
与飞行边均不接。本探针从 MT1 起跑 cross_floor=True 搜索，不控宽(无 beam)，只测：状态膨胀、到达哪些层、
各层指纹分布、耗时，供玩家拍板第二步控宽/飞行。

塔无关性：solver/ 不变；本驱动在 extract/ 读塔特有的 MT 层 id（与 probe_topology.py 同性质）。
多层安全：搜索入口 _single_floor_copy=False（全量深拷，跨层兄弟分支不共享引用）——这是跨层正确性前提。
不进搜索循环的引擎裁判不在此做（只测膨胀）；正确性由 93 单测 + verify_mt3 + phase1 段 replay 已守。
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import step, _copy_state
from solver.quotient import (
    search_quotient, count_floor_blocks, _free_cells, _boundary_ops,
)
from solver.verify import replay


def _fidx(fid):
    m = re.match(r"MT(\d+)$", fid or "")
    return int(m.group(1)) if m else 1_000_000


OPENING_PREFIX = 82   # tokens[:82] = 强制开局噩梦序列结束、落 MT3 seg4 入口（与 verify_mt3 同口径）


def build_start():
    """跨层膨胀的【真实起点】= 强制开局噩梦结束后的首个自由可玩态。

    开局噩梦(MT3→MT2，flag:03 一次性)会 setValue hp=400/atk=10/def=10、清武器盾、是不可路由的
    剧情过场(floor_graph.md §5)。它【之前】英雄是 hp1000/atk100/def100 的过场态，搜索一旦踩噩梦触发格
    就被合法地裁掉(非 stair 离层)→ 困在开局。真正的自由博弈从噩梦【之后】的 MT3 入口开始(hp400/atk10/
    def10)，与 verify_mt3 的 PREFIX=82、phase1 seg4 起点同口径。施加 tokens[:82] 只是穿过【强制】开局
    (无博弈自由度)抵达首个可玩态——不是模仿 route 走法(此后搜索自由跨层、不抄 route)。
    跨层须多层安全深拷 → _single_floor_copy=False。"""
    state = build_initial_state()
    tokens = load_tokens()
    for tok in tokens[:OPENING_PREFIX]:
        state = step(state, tok)
    assert state.current_floor == "MT3", state.current_floor
    state._single_floor_copy = False
    return state, OPENING_PREFIX


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=20000,
                    help="max_states 生成上限（首测宜小，确认能跑通+看膨胀速率后再 ramp）")
    ap.add_argument("--goal-floor", default="MT0",
                    help="目标层；默认 MT0（楼梯不可达→搜索穷尽全楼梯连通分量/撞 cap，测原始扇出膨胀）")
    ap.add_argument("--goal", default="1,1", help="目标格 x,y（goal 楼梯不可达时无关紧要）")
    args = ap.parse_args()
    gx, gy = (int(v) for v in args.goal.split(","))
    goal_cell = (args.goal_floor, gx, gy)

    start, nopen = build_start()
    h = start.hero
    print("=" * 92)
    print("跨层楼梯缩点 真实膨胀探针（cross_floor=True，无控宽，_single_floor_copy=False）")
    print("=" * 92)
    print(f"起点(穿过 {nopen} token 强制开局噩梦后的首个自由态): {start.current_floor}({h.x},{h.y}) "
          f"HP={h.hp} ATK={h.atk} DEF={h.def_} keys={dict(h.keys)} items={dict(h.items)}")

    nblk, nfree = count_floor_blocks(start)
    free0 = _free_cells(start)
    ops0 = _boundary_ops(start, free0, cross_floor=True)
    kinds = {}
    for op in ops0:
        kinds[op[0]] = kinds.get(op[0], 0) + 1
    stair_ops = [(op[1], op[2]) for op in ops0 if op[0] == "stair"]
    print(f"起点 {start.current_floor}: 整层自由格={nfree} → 连通块={nblk}；英雄块自由格={len(free0)}")
    print(f"起点边界算子分类={kinds}；楼梯算子格={stair_ops}  "
          + ("✅ 跨层楼梯边已生成" if stair_ops else "⚠ 起点块边界无楼梯（块未触及楼梯，正常——climb 后才现）"))
    print(f"目标格={goal_cell}（{'楼梯不可达→测穷尽膨胀' if args.goal_floor in ('MT0',) else '可达目标'}）  "
          f"max_states={args.cap:,}")
    print("-" * 92)

    t0 = time.perf_counter()
    res = search_quotient(start, goal_cell, step, max_states=args.cap, cross_floor=True)
    dt = time.perf_counter() - t0

    print(f"found={res.found}  goal_hits={getattr(res, 'goal_hits', 0)}  "
          f"hit_cap={res.hit_cap}  耗时={dt:.1f}s")
    print(f"指纹(distinct)={res.distinct_fingerprints:,}  前沿峰={res.frontier_peak:,}  "
          f"峰块={getattr(res, 'n_blocks_peak', 0)}  "
          f"展开={res.states_expanded:,}  生成={res.states_generated:,}  "
          f"算子累计={getattr(res, 'n_ops_total', 0):,}")
    floors_seen = getattr(res, "floors_seen", [])
    print(f"到达层数={len(floors_seen)}  到达层={sorted(floors_seen, key=_fidx)}")
    icpt = getattr(res, "intercept_locs", [])
    if icpt:
        print(f"拦截(choices)事件格={icpt}（商人/祭坛/老人，块图记录不强解）")
    print("-" * 92)
    print("各层指纹分布（跨层膨胀按层拆解；fp[0]=current_floor）：")
    fpf = getattr(res, "fp_by_floor", {})
    for fid in sorted(fpf, key=_fidx):
        bar = "█" * min(60, max(1, fpf[fid] * 60 // max(fpf.values())))
        print(f"  {fid:>6}: {fpf[fid]:>7,}  {bar}")
    if res.found:
        print("-" * 92)
        print(f"目标出口前沿宽={len(res.goal_frontier)}  最优HP={res.final_hp}")
        # 跨层正确性抽查：最优动作序列丢回封板引擎独立重放，逐字段核对（证明楼梯边产出可照走的合法线路）
        rep = replay(start, res.actions, step, _copy_state)
        ok = (rep.current_floor == goal_cell[0] and (rep.hero.x, rep.hero.y) == (gx, gy)
              and rep.hero.hp == res.final_hp)
        print(f"裁判重放({len(res.actions)} 步): 落点={rep.current_floor}({rep.hero.x},{rep.hero.y}) "
              f"HP={rep.hero.hp} → " + ("✅ 一致(跨层线路可直接照走)" if ok else "⚠ 不一致需排查"))


if __name__ == "__main__":
    main()
