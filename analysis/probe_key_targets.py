"""【诊断·一次性】钥匙目标涌现口径实测（detect_key_targets 口径1：参照态/可达门控）。

问题：navigate_to 顺路 _absorb 吸不到的【代价型钥匙=要打守门怪/绕路】(玩家点名 MT4 三钥)，
要进 GA 候选目标池让基因显式控制"何时取"。范围已定 β=复用 fitness.zone_ground_key_costs
守怪可达口径只纳代价型。但该口径带 afford 门控(没钥匙的门当墙)+守怪打不动断边——
起点态属性最低、手里 0 钥匙 → 黄门后的 MT4 三钥可能被判"够不到"而漏掉。

本探针用【固定起点态 build_start()】(detect_big_items 同源参照)跑三版可达，看 MT4 三钥在不在：
  V1 起点原样 afford(_afford_colors(start)，手里 0 钥匙)            —— fitness 现状口径，预期漏 MT4
  V2 起点属性 + 全色 afford(乐观开门，门不阻断)                     —— 隔离"门挡" vs "怪挡"
  V3 高属性 + 全色 afford(门开、守怪都打得动、不断边)               —— 纯结构"被守怪挡着"的代价型理想候选集
每版分 cost==0(顺路·空地零损血直达，排除) / cost>0(代价型·要打守怪，入候选)。
塔无关：钥匙=_tile_to_item∩_KEY_ITEMS、门=DOOR_KEY_MAP、不写死 MT4（MT4 仅 dump 过滤显示用）。
"""
import sys
import json
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import copy

from probe_crossfloor import build_start
from vzone import build_zone, _NB4
from solver.fitness import (
    build_zone1_roster, _ground_key_costs, _afford_colors, _zone_floor_cells,
)
from sim.simulator import _KEY_ITEMS, DOOR_KEY_MAP
from solver.beam import _combat_damage

FULL = set(_KEY_ITEMS)   # 全色 afford：假设各色钥匙都能开门（门不阻断）


def all_key_cells(state, zone_fids, afford):
    """一区地上钥匙全集（全色 afford 下、门不锁）：[(fid,x,y)]。不经 Dijkstra，纯枚举钥匙格。"""
    out = []
    for fid in zone_fids:
        info = _zone_floor_cells(state, fid, afford)
        if info is None:
            continue
        _h, _w, _isw, _mid, key_cells, _src = info
        out.extend((fid, x, y) for (x, y) in key_cells)
    return out


def costs(state, zone_fids, afford):
    out = {}
    for fid in zone_fids:
        out.update(_ground_key_costs(state, fid, afford))
    return out


def dump(label, cmap):
    cheap = sorted(k for k, c in cmap.items() if c == 0)
    costly = sorted((k, round(c, 1)) for k, c in cmap.items() if c > 0)
    mt4 = [(k, round(c, 1)) for k, c in cmap.items() if k[0] == "MT4"]
    print(f"\n===== {label} =====  够得到 {len(cmap)} 把")
    print(f"  顺路 cost==0 ({len(cheap)}): {cheap}")
    print(f"  代价型 cost>0 ({len(costly)}): {costly}")
    print(f"  ★MT4 三钥: {mt4 if mt4 else '【不在结果里——被门/守怪封死】'}")


def reachable_keys(state, fid, afford, monster_wall):
    """单层（楼梯口多源 BFS·门按 afford 开）够得到的钥匙格集合。monster_wall：守怪格当墙(绕开)/当通。
    ★纯结构、不算损血、不依赖英雄属性 → 固定参照（只看地图布局）。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, mid_at, key_cells, src_cells = info

    def blocked(x, y):
        return is_wall(x, y) or (monster_wall and (x, y) in mid_at)

    seen, dq = set(), deque()
    for s in src_cells:
        if not blocked(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not blocked(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return {(fid, x, y) for (x, y) in key_cells if (x, y) in seen}


def structural_costly(state, zone_fids, afford):
    """代价型钥匙（纯结构）= 门乐观开下，绕开守怪到不了、但允许穿守怪能到 = 取它必经守怪。
    返回 (顺路集, 代价型集)。不依赖英雄属性（打不打得过留运行时）→ 固定参照、只产候选。"""
    cheap, full = set(), set()
    for fid in zone_fids:
        cheap |= reachable_keys(state, fid, afford, monster_wall=True)
        full |= reachable_keys(state, fid, afford, monster_wall=False)
    return cheap, (full - cheap)


def reachable_keys_zerodmg(state, fid, afford):
    """单层零损血够得到的钥匙格（楼梯多源 BFS·门按 afford 开·只穿【0 损血守怪】）。
    这正是 navigate_to 真实"顺路"语义：_absorb 不杀怪，navigate_to 只零损血开 afford 门(开门 0 血)、
    顺手杀 0 损血怪(op_dmg=0)。守怪损血=0(打了不掉血)→可穿=顺路；>0 或打不动(_combat_damage None)→边界。
    损血按【固定参照态 state 的属性】算(本探针=起点 atk/def) → 不随搜索漂移。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, mid_at, key_cells, src_cells = info

    def passable(x, y):
        if is_wall(x, y):
            return False
        if (x, y) in mid_at:
            return _combat_damage(state, mid_at[(x, y)]) == 0   # None/>0 都不算顺路
        return True

    seen, dq = set(), deque()
    for s in src_cells:
        if passable(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and passable(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return {(fid, x, y) for (x, y) in key_cells if (x, y) in seen}


def costly_zerodmg(state, zone_fids, afford, all_keys):
    """代价型钥匙 = 一区地上钥匙全集 − 零损血够得到的钥匙。
    顺路=零损血够到(navigate_to 顺手白捡)；代价型=要穿【>0 损血或打不动】守怪/锁死门才够到→需 GA 显式去取。
    返回 (顺路集, 代价型集)。固定参照态判损血、只产候选(打不打得过的最终取舍留 GA 搜)。"""
    cheap = set()
    for fid in zone_fids:
        cheap |= reachable_keys_zerodmg(state, fid, afford)
    return cheap, (set(all_keys) - cheap)


# ─── 三分口径探查：① 顺路 ② 一区内代价型候选 ③ 一区内够不到（铁门/红门无钥锁死） ──────────────

def _floor_tile_at(state, fid, x, y):
    """取 (fid,x,y) 的 tile id（已载层读 entities，未载层读 JSON map）。塔无关。"""
    fl = state.floors.get(fid)
    if fl is not None:
        return fl.entities[y][x]
    floors_dir = getattr(state, "_floors_dir", None)
    if floors_dir is None:
        return None
    path = Path(floors_dir) / f"{fid}.json"
    if not path.exists():
        return None
    grid = json.loads(path.read_text(encoding="utf-8")).get("map", [])
    return grid[y][x] if grid and 0 <= y < len(grid) and 0 <= x < len(grid[0]) else None


def key_color_at(state, fid, x, y):
    """该钥匙格的钥匙色（item id ∈ _KEY_ITEMS），用于 key-chain 自给 afford 闭包。"""
    t = _floor_tile_at(state, fid, x, y)
    return state.floor._tile_to_item.get(t) if t else None


def reachable_doorwise(state, fid, afford):
    """单层【门拓扑可达】钥匙格：afford 门开 / 没钥匙的门(铁红)=墙 / 守怪一律可穿(只看门墙拓扑，
    不管打不打得过)。判③用：door-wise 够不到 = 每条路都被一道开不起的门锁死。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, mid_at, key_cells, src_cells = info
    seen, dq = set(), deque()
    for s in src_cells:
        if not is_wall(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not is_wall(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return {(fid, x, y) for (x, y) in key_cells if (x, y) in seen}


def afford_closure(state, zone_fids):
    """零钥起步、钥匙-门自给到不动点：door-wise 够到的钥匙色并入 afford，迭代。返回最终可得色集。
    最宽口径（穿怪也算够到）→ 若某色(如铁钥)在一区根本拿不到，它必不在 afford → 该色门=永久墙→门后=③。"""
    afford = set(_afford_colors(state))
    while True:
        reached = set()
        for fid in zone_fids:
            reached |= reachable_doorwise(state, fid, afford)
        colors = {key_color_at(state, *c) for c in reached}
        colors.discard(None)
        if colors <= afford:
            return afford
        afford |= colors


def triage(state, zone_fids, all_keys):
    """三分：用 key-chain 自给 afford（真实可开的门），
      ① 顺路   = 零损血够到（afford 门 + 0 损血怪）
      ③ 够不到 = door-wise 不可达（每条路都过开不起的门，如铁门无铁钥）→ 一区外、不进池
      ② 候选   = door-wise 可达但非零损血（afford 门内、要付守怪血）→ GA 决策何时取
    返回 (afford, 顺路, 候选, 够不到)。"""
    afford = afford_closure(state, zone_fids)
    zero, doorR = set(), set()
    for fid in zone_fids:
        zero |= reachable_keys_zerodmg(state, fid, afford)
        doorR |= reachable_doorwise(state, fid, afford)
    allset = set(all_keys)
    return afford, zero, (doorR - zero), (allset - doorR)


def main():
    start, _ = build_start()
    zone = build_zone()
    roster, zone_fids, _all = build_zone1_roster(start)
    print(f"zone_fids = {zone_fids}")
    print(f"起点 ATK={start.hero.atk} DEF={start.hero.def_} keys={dict(start.hero.keys)}")

    allk = all_key_cells(start, zone_fids, FULL)
    print(f"\n一区地上钥匙全集（全色 afford·门不锁，{len(allk)} 把）: "
          f"{dict(Counter(f for f, _, _ in allk))}")
    print(f"  其中 MT4: {[(x, y) for f, x, y in allk if f == 'MT4']}")

    # V1 起点原样 afford（手里 0 钥匙 → afford 空 → 钥匙门全当墙）
    dump("V1 起点原样 afford=" + str(_afford_colors(start)), costs(start, zone_fids, _afford_colors(start)))

    # V2 起点属性 + 全色 afford（乐观开门，隔离门挡 vs 怪挡）
    dump("V2 起点属性 + 全色 afford（乐观开门）", costs(start, zone_fids, FULL))

    # V3 高属性 + 全色 afford（守怪都打得动、不断边 → 纯结构被守怪挡着的代价型）
    sup = copy.deepcopy(start)
    object.__setattr__(sup.hero, "atk", 9999)
    object.__setattr__(sup.hero, "def_", 9999)
    dump("V3 高属性 ATK/DEF=9999 + 全色 afford（守怪全可杀）", costs(sup, zone_fids, FULL))

    # 口径(i) 纯结构差集（守怪一律当墙）：参照——过宽，连 0 损血怪后的钥匙也算代价型
    cheap_i, costly_i = structural_costly(start, zone_fids, FULL)
    print("\n" + "=" * 70)
    print("口径(i) 纯结构（守怪一律当墙·绕不到=代价型）——【过宽，仅作参照】")
    print(f"  顺路 {len(cheap_i)} 把 {dict(Counter(f for f, _, _ in cheap_i))}")
    print(f"  代价型 {len(costly_i)} 把 {dict(Counter(f for f, _, _ in costly_i))}")

    # ★口径(ii) 建议：零损血够到=顺路，需穿>0损血/打不动守怪才够到=代价型（固定参照态 start 判损血）
    allset = set(allk)
    cheap, costly = costly_zerodmg(start, zone_fids, FULL, allset)
    mt4_cost = sorted(k for k in costly if k[0] == "MT4")
    mt4_cheap = sorted(k for k in cheap if k[0] == "MT4")
    print("\n" + "=" * 70)
    print("★★★ 口径(ii) 建议：零损血够到=顺路 / 需穿>0损血·打不动守怪=代价型（固定参照 start 判损血）★★★")
    print(f"  顺路钥匙（零损血白捡，{len(cheap)} 把）: {dict(Counter(f for f, _, _ in cheap))}")
    print(f"  代价型钥匙（需付守怪血，{len(costly)} 把）: {dict(Counter(f for f, _, _ in costly))}")
    print(f"  代价型明细: {sorted(costly)}")
    print(f"  ★MT4 代价型 {len(mt4_cost)}/6: {mt4_cost}")
    print(f"  ★MT4 顺路   {len(mt4_cheap)}/6: {mt4_cheap}")
    print(f"  自检·顺路∩代价型(应为空): {sorted(cheap & costly)}")
    print(f"  自检·顺路∪代价型 == 全集{len(allset)}: {len(cheap | costly) == len(allset)}")

    # ★★★ 三分口径探查：玩家点出 MT2 三钥(铁门+中级卫兵守、要三区才拿)该是【第三类·一区内够不到】 ★★★
    afford, c1, c2, c3 = triage(start, zone_fids, allk)
    print("\n" + "=" * 70)
    print("★★★ 三分口径：① 顺路 / ② 一区内代价型候选 / ③ 一区内够不到（用真实 key-chain afford）★★★")
    print(f"  key-chain 自给 afford 闭包（一区真能开的门色）= {sorted(afford)}")
    print(f"    → 不在此集的门色(铁/红钥)在一区拿不到 → 那种门永久=墙 → 门后钥匙=③")
    print(f"\n  ① 顺路（零损血白捡·非候选，{len(c1)} 把）: {dict(Counter(f for f, _, _ in c1))}")
    print(f"     明细: {sorted(c1)}")
    print(f"  ② 一区内代价型候选（afford 门内·付守怪血·GA 决策何时取，{len(c2)} 把）: "
          f"{dict(Counter(f for f, _, _ in c2))}")
    print(f"     明细: {sorted(c2)}")
    print(f"  ③ 一区内够不到（door-wise 锁死·不进池，{len(c3)} 把）: {dict(Counter(f for f, _, _ in c3))}")
    print(f"     明细: {sorted(c3)}")

    print("\n  ── 关键对照 ──")
    for tag, cells in [("MT2 三钥", [k for k in allk if k[0] == 'MT2']),
                       ("MT4 六钥", [k for k in allk if k[0] == 'MT4'])]:
        for k in sorted(cells):
            cls = "①顺路" if k in c1 else ("②候选" if k in c2 else ("③够不到" if k in c3 else "?"))
            col = key_color_at(start, *k)
            print(f"    {tag} {k}  色={col}  → {cls}")
    print(f"\n  自检·三分无交叠且并==全集{len(allk)}: "
          f"{len(c1 | c2 | c3) == len(allk) and not (c1 & c2) and not (c1 & c3) and not (c2 & c3)}")
    print(f"  对照玩家说法：顺路应=12 → 实测 ①={len(c1)}；MT2 三钥应=③；MT4 六钥应=②")


if __name__ == "__main__":
    main()
