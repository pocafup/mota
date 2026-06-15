"""【一次性诊断·只读·不碰产品码】连通块粒度摸底 —— 玩家"连通块当目标"方案评估前的实证。

玩家想法：把"同一连通区域里的一批物品"当一个【目标块】(块内一起拿、禁区只发生块间)，
减少 navigate_to 顺路吸后续目标造成的黄腿。关键先查清(决定复用现成还是造新)：
  ★ MT4 五钥到底在不在【同一个零损血自由块】(_free_cells 那种)？

═══ 读运行码、不靠推断(CLAUDE.md 铁律) ═══
本脚本【只读】，不改 navigate_to / quotient / decode / 任何产品码。复刻 quotient.count_floor_blocks
的覆盖式 floodfill(同 _is_free_tile 口径)，对 MT4 做【整层零损血块划分】，报告 5 把钥匙 + 宝石各落
在哪个块。守怪/没钥匙的门=非自由格=块边界 → 若钥匙被守怪劈开 = 落在不同块。

为看【静态 vs 动态】对比：重放标尺 route，快照英雄【首次】踏入 MT4(守怪多还活着·最静态) 与【末次】
在 MT4(route 在 MT4 上清完后·最动态) 两个态，各做一次块划分 → 看"清怪前分几块、清怪后并几块"。
"""
import argparse
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from solver.quotient import _is_free_tile, _zone_blocked, _DELTAS   # noqa: E402
from ga_loop import build_harness                                   # noqa: E402


def _floor_block_partition(state):
    """覆盖式 floodfill 当前层所有零损血自由格 → (cell->block_id, blocks:list[set])。复刻 count_floor_blocks。"""
    floor = state.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    zb = _zone_blocked(state)
    free_all = {(x, y) for y in range(rows) for x in range(cols)
                if _is_free_tile(state, x, y, zb)}
    seen, blocks = {}, []
    for c in free_all:
        if c in seen:
            continue
        bid = len(blocks)
        comp, dq = {c}, deque([c])
        seen[c] = bid
        while dq:
            cx, cy = dq.popleft()
            for dx, dy in _DELTAS:
                nb = (cx + dx, cy + dy)
                if nb in free_all and nb not in seen:
                    seen[nb] = bid
                    comp.add(nb)
                    dq.append(nb)
        blocks.append(comp)
    return seen, blocks


def _snapshot_floor_states(route_file, target_fid):
    """重放 route，返回 (first_state, last_state) = 英雄【首次】/【末次】current_floor==target_fid 的态。"""
    from export_mt10_boss_route import make_initial_state
    from decode_route import parse_rle_route, decompress
    from sim.simulator import step
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    first = last = None
    if s.current_floor == target_fid:
        first = s
    for a in actions:
        s = step(s, a)
        if s.dead:
            break
        if s.current_floor == target_fid:
            if first is None:
                first = s
            last = s
    return first, last


def _report(tag, state, goal_cells, lab):
    if state is None:
        print(f"\n[{tag}] 无此态(route 未踏入)")
        return
    h = state.hero
    print(f"\n[{tag}] 英雄 @({h.x},{h.y})  atk={h.atk} def={h.def_} 钥={dict((k, v) for k, v in h.keys.items() if v)}")
    seen, blocks = _floor_block_partition(state)
    print(f"  整层零损血块数={len(blocks)}  自由格数={sum(len(b) for b in blocks)}")
    rows = []
    for c in goal_cells:
        fid, x, y = c
        bid = seen.get((x, y))
        rows.append((lab(c), (x, y), bid))
    for name, xy, bid in rows:
        where = f"块#{bid}(大小{len(blocks[bid])})" if bid is not None else "非自由格(被守怪/墙/门挡·不在任何块)"
        print(f"    {name:>16} @{xy} → {where}")
    bids = [bid for _, _, bid in rows if bid is not None]
    if bids:
        uniq = sorted(set(bids))
        if len(uniq) == 1:
            print(f"  ★这些目标全在同一块 #{uniq[0]} → 块内一起拿成立(可复用 _absorb)")
        else:
            print(f"  ★这些目标分散在 {len(uniq)} 个块 {uniq} → 静态零损血块【没把它们归一】(守怪/门劈开)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-persistent", action="store_true")
    args = ap.parse_args()

    print("组装 GA 电池组(build_start + 目标池涌现)…")
    H = build_harness(persistent=not args.no_persistent)
    meta = H["meta"]
    keys, gems = set(meta["keys"]), set(meta["gems"])

    def lab(c):
        if c == meta["sword"]:
            return f"剑{c}"
        if c == meta["shield"]:
            return f"盾{c}"
        if c in keys:
            return f"钥{c}"
        if c in gems:
            return f"宝石{c}"
        return f"?{c}"

    # MT4 全部目标(5 钥 + 宝石(7,10))
    mt4_goals = sorted([c for c in H["pool"] if c[0] == "MT4"])
    # MT1 双宝石(顺路·相邻·对照)
    mt1_goals = sorted([c for c in H["pool"] if c[0] == "MT1"])
    print(f"  MT4 目标 = {[lab(c) for c in mt4_goals]}")
    print(f"  MT1 目标 = {[lab(c) for c in mt1_goals]}")

    root = Path(__file__).resolve().parent.parent
    R718 = root / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"

    print("\n" + "=" * 78)
    print("MT4 零损血块划分(标尺 route 首次踏入 vs 末次在 MT4) —— 看五钥静态分几块")
    print("=" * 78)
    first4, last4 = _snapshot_floor_states(R718, "MT4")
    _report("MT4·首次踏入(守怪最全·最静态)", first4, mt4_goals, lab)
    _report("MT4·末次(route 清完后·最动态)", last4, mt4_goals, lab)

    print("\n" + "=" * 78)
    print("MT1 零损血块划分(对照·双宝石相邻是否同块)")
    print("=" * 78)
    first1, last1 = _snapshot_floor_states(R718, "MT1")
    _report("MT1·首次踏入", first1, mt1_goals, lab)


if __name__ == "__main__":
    main()
