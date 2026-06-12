"""第0步坐实探针（不碰产品码，纯诊断）：在【MT9 真实态】量化 MT1-5 攻防宝石的
   ① 楼梯路径 d（现状 pull 用的 _toll_dist_from，静态全活跨层图）
   ② fly 落点→gem 的【层内】d（fly 本身零损血，落点按 §I.3.2 = 高飞低→目标层 up_floor）
   ③ min(楼梯d, fly层内d) = fly-aware 后 pull 会用的距离
   并打印对应 pull 贡献 value/(1+d) 的【楼梯版 vs fly-aware 版】，按层汇总，
   再与 MT8/MT7 的 pull 贡献对比——一锤定音：fly-aware 后 MT1-5 能否在 pull 里翻身
   （即搜索会不会改成优先飞回 MT1-5，而非就近打 MT8/MT7）。

口径与 vzone.pull 完全一致（boss_toll Δ 区势能、_toll_dist_from 距离、_enter_cost 怪 toll、
拿走离场不计、value<=0 不计）——只是把 pull 内部分项拆开打印 + 新增 fly-aware 距离列。
不改 vzone.py / quotient.py / sim。MT9 态来源：重放已验证的 k200_mt10_route.json（算法跑出、
replay_ok=true、MT3 噩梦后起点同 build_start）到【踏入 MT9】的态。
"""
import argparse
import heapq
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step
from probe_crossfloor import build_start, _fidx
from vzone import (build_zone, boss_toll, _toll, _enter_cost, _passable,
                   _zone_attr_gems, _NB4)

ROUTE = Path(__file__).parent / "k200_mt10_route.json"
INF = float("inf")


def replay_snapshots(target_floor):
    """重放 k200 路线，返回所有 current_floor==target 的 (step_idx, state) 快照。"""
    state = build_start()[0]
    actions = json.loads(ROUTE.read_text(encoding="utf-8"))["actions"]
    snaps = []
    for i, a in enumerate(actions):
        state = step(state, a)
        if state.current_floor == target_floor:
            snaps.append((i, state))
    return snaps


def make_cost(zone, state, atk, def_, mdef, live):
    """怪格 enter-cost。live=False → 静态全活（现状 pull 口径，_enter_cost）；
       live=True → 读 state.floors 真实 entities：已清怪(entities==0)→0、活怪→toll（=方向A口径）。
       只换怪 toll 这一个变量；墙/门可达性 _passable 两版都用静态，隔离『静态高估』单因素。"""
    def cost(node):
        m = zone["mon_cache"].get(node)
        if m is None:
            return 0
        if live:
            fid, x, y = node
            fl = state.floors.get(fid)
            if fl is not None and fl.entities[y][x] == 0:
                return 0
        return _toll(m, atk, def_, mdef)
    return cost


def toll_dist(zone, src, cost):
    """跨层 Dijkstra（楼梯免费边 links），返回 {node: 最小累计 cost}。cost=make_cost(...)。"""
    dist = {src: 0}
    pq = [(0, src)]
    while pq:
        d, node = heapq.heappop(pq)
        if d > dist.get(node, INF):
            continue
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in zone["links"]:
            nbrs.append(zone["links"][node])
        for nb in nbrs:
            if not _passable(zone, nb):
                continue
            nd = d + cost(nb)
            if nd < dist.get(nb, INF):
                dist[nb] = nd
                heapq.heappush(pq, (nd, nb))
    return dist


def single_floor_toll(zone, gfid, src_xy, dst_xy, cost):
    """fly 落点→gem 的【单层】最小累计损血（只在 gfid 层内 4 邻走）。cost 决定静态/ live。无路→inf。"""
    src = (gfid, src_xy[0], src_xy[1])
    dst = (gfid, dst_xy[0], dst_xy[1])
    if not _passable(zone, dst):
        return INF
    dist = {src: 0}
    pq = [(0, src)]
    while pq:
        d, node = heapq.heappop(pq)
        if node == dst:
            return d
        if d > dist.get(node, INF):
            continue
        fid, x, y = node
        for dx, dy in _NB4:
            nb = (fid, x + dx, y + dy)
            if nb[0] != gfid or not _passable(zone, nb):
                continue
            nd = d + cost(nb)
            if nd < dist.get(nb, INF):
                dist[nb] = nd
                heapq.heappush(pq, (nd, nb))
    return INF


def fly_landing(zone, from_fid, to_fid):
    """§I.3.2 落点：_fidx(from) <= _fidx(to) → 目标层 down_floor，否则 up_floor。返回 (x,y) 或 None。
       MT9→MT1-5 是高飞低 → up_floor（上楼梯旁）。与 sim _execute_floor_fly 同。"""
    fl = zone["floors"][to_fid]["floor"]
    coords = fl.down_floor if _fidx(from_fid) <= _fidx(to_fid) else fl.up_floor
    if coords:
        return (coords[0], coords[1])
    return None


def _fmt(d):
    return f"{d:.0f}" if d != INF else "inf"


def diagnose(zone, state, tag):
    h = state.hero
    fid = state.current_floor
    print("=" * 108)
    print(f"【{tag}】MT9 真实态: floor={fid} ({h.x},{h.y}) HP={h.hp} ATK={h.atk} "
          f"DEF={h.def_} mdef={h.mdef} gold={h.gold}")

    boss_cur = boss_toll(zone, h.atk, h.def_, h.mdef)
    cost_static = make_cost(zone, state, h.atk, h.def_, h.mdef, live=False)
    cost_live = make_cost(zone, state, h.atk, h.def_, h.mdef, live=True)
    stair_static = toll_dist(zone, (fid, h.x, h.y), cost_static)   # 现状 pull 用的（静态全活）
    stair_live = toll_dist(zone, (fid, h.x, h.y), cost_live)       # 方向A（楼梯距离读活体）
    gems = _zone_attr_gems(zone)
    floors = state.floors

    remaining = []
    for (gfid, x, y), (da, dd) in gems.items():
        fl = floors.get(gfid)
        if fl is not None and fl.entities[y][x] == 0:
            continue
        remaining.append(((gfid, x, y), (da, dd)))

    by_floor_cnt, tot_by_floor = {}, {}
    for (gfid, _x, _y), _ in remaining:
        by_floor_cnt[gfid] = by_floor_cnt.get(gfid, 0) + 1
    for (gfid, _x, _y), _ in gems.items():
        tot_by_floor[gfid] = tot_by_floor.get(gfid, 0) + 1
    print("各层 attr-gem 剩余/总数：", end="")
    for gfid in sorted(tot_by_floor, key=_fidx):
        print(f" {gfid}:{by_floor_cnt.get(gfid,0)}/{tot_by_floor[gfid]}", end="")
    print()
    print("距离四列：d楼梯静=现状pull | d楼梯活=方向A(楼梯读活体) | "
          "d_fly静=fly边初版(层内仍静态) | d_fly活=fly+方向A全修")
    print("-" * 108)
    print(f"{'层':>4} {'格':>8} {'Δa,Δd':>7} {'value':>5} | "
          f"{'d楼梯静':>7} {'d楼梯活':>7} {'d_fly静':>7} {'d_fly活':>7} | "
          f"{'pull现状':>8} {'pull_fly静':>10} {'pull_fly活':>10}")

    # sums[gfid] = [Σpull现状, Σpull_fly静, Σpull_fly活]
    sums = {}
    for (gfid, x, y), (da, dd) in sorted(remaining, key=lambda t: (_fidx(t[0][0]), t[0][1], t[0][2])):
        value = boss_cur - boss_toll(zone, h.atk + da, h.def_ + dd, h.mdef)
        if value <= 0:
            continue
        ds_s = stair_static.get((gfid, x, y), INF)
        ds_l = stair_live.get((gfid, x, y), INF)
        land = fly_landing(zone, fid, gfid)
        df_s = single_floor_toll(zone, gfid, land, (x, y), cost_static) if land else INF
        df_l = single_floor_toll(zone, gfid, land, (x, y), cost_live) if land else INF
        p_cur = value / (1.0 + ds_s) if ds_s != INF else 0.0
        p_fs = value / (1.0 + min(ds_s, df_s)) if min(ds_s, df_s) != INF else 0.0
        p_fl = value / (1.0 + min(ds_l, df_l)) if min(ds_l, df_l) != INF else 0.0
        s = sums.setdefault(gfid, [0.0, 0.0, 0.0])
        s[0] += p_cur; s[1] += p_fs; s[2] += p_fl
        print(f"{gfid:>4} {f'({x},{y})':>8} {f'{da},{dd}':>7} {value:>5} | "
              f"{_fmt(ds_s):>7} {_fmt(ds_l):>7} {_fmt(df_s):>7} {_fmt(df_l):>7} | "
              f"{p_cur:>8.3f} {p_fs:>10.3f} {p_fl:>10.3f}")

    print("-" * 108)
    print(f"{'层汇总':>4} {'Σpull现状':>12} {'Σpull_fly静':>12} {'Σpull_fly活':>12}")
    for gfid in sorted(sums, key=_fidx):
        a, b, c = sums[gfid]
        print(f"{gfid:>4} {a:>12.3f} {b:>12.3f} {c:>12.3f}")

    def band(lo, hi, idx):
        return sum(sums.get(f"MT{i}", [0.0, 0.0, 0.0])[idx] for i in range(lo, hi + 1))
    mt8 = sums.get("MT8", [0.0, 0.0, 0.0])
    mt7 = sums.get("MT7", [0.0, 0.0, 0.0])
    near = [max(mt7[i], mt8[i]) for i in range(3)]
    print("-" * 108)
    print(f"{'':12}{'现状':>12}{'fly静':>12}{'fly活':>12}")
    print(f"MT1-5 合计 {band(1,5,0):>12.3f}{band(1,5,1):>12.3f}{band(1,5,2):>12.3f}")
    print(f"MT8 就近   {mt8[0]:>12.3f}{mt8[1]:>12.3f}{mt8[2]:>12.3f}")
    print(f"MT7 就近   {mt7[0]:>12.3f}{mt7[1]:>12.3f}{mt7[2]:>12.3f}")
    for idx, name in ((0, "现状(只楼梯静)"), (1, "fly静(上fly边+pull-aware)"), (2, "fly活(fly+方向A全修)")):
        win = band(1, 5, idx) > near[idx]
        print(f"判定[{name}]：MT1-5={band(1,5,idx):.3f} "
              f"{'>' if win else '≤'} max(MT7,MT8)={near[idx]:.3f} "
              f"→ {'MT1-5 翻身(应优先飞回)' if win else 'MT1-5 压不过就近层'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", default="MT9", help="诊断楼层（默认 MT9）")
    args = ap.parse_args()

    zone = build_zone()
    snaps = replay_snapshots(args.floor)
    if not snaps:
        print(f"⚠ 重放 k200 路线未经过 {args.floor}（可能 fly 跳层）。换态来源后再诊断。")
        return
    print(f"重放 k200_mt10_route：共 {len(snaps)} 个 {args.floor} 态（step_idx "
          f"{snaps[0][0]}..{snaps[-1][0]}）")
    # 首入 MT9（刚到，决策点之一） + 停留最深态（atk+def 最大，≈『MT9 打完』）
    first = snaps[0][1]
    deepest = max(snaps, key=lambda t: (t[1].hero.atk + t[1].hero.def_, t[1].hero.hp))[1]
    diagnose(zone, first, f"首入 MT9 (step {snaps[0][0]})")
    diagnose(zone, deepest, "MT9 停留最深态(atk+def 最大)")


if __name__ == "__main__":
    main()
