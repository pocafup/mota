"""【只读诊断·§S23 步1】一区"有价值候选块"判据 + 自动产候选块清单（给玩家拍·非逐块圈）。

把 §S9 钥匙三分（①顺路/②代价/③够不到）从【只对钥匙】扩展到【所有攻防/钥匙物品】，
一次自然滚出"哪些块该当 GA 目标进 pool"。只读：不碰任何产品码、不改 build_min_pool、
不跑 GA、不测无效率。复用已验证原语（detect_key_targets 三分、detect_big_items 大件、
_zone_floor_cells 墙/怪/楼梯源、_combat_damage 守怪损血、build_block_index 块折叠）。

═══ 统一判据（塔无关·扩展自 §S9）═══
对每个【带攻/防/钥增益的物品 cell】，按【固定参照 ref（噩梦后 MT3 入口·atk10/def10·0 钥）】
+ afford 闭包门拓扑，分三档（与钥匙三分同口径、同 floodfill）：
  ① 顺路白捡 = 零损血够到（afford 门通 + 只穿 0 损血守怪）→ navigate_to 顺手吸、无"何时取"
              时机价值、放进基因只造自欺序列（§S11）→ 【排除】。
  ② 代价型   = door-wise 可达但非零损血（要打守怪付血/绕路/深目标）→ "何时取"是真策略
              （等属性高减伤少再取）→ 【进候选池·GA 决策】。大件（剑/盾）天然落此档。
  ③ 够不到   = door-wise 锁死（每条路被一道开不起的门封死·如铁门无铁钥）→ 一区外 → 【排除】。
判据"门色 ∉ afford 闭包 / 零损血够到与否"全数据滚出、换塔重算 → 塔无关、零硬编码。
候选块 = 含 ≥1 个 ② 物品 cell（或大件 cell）的初始块。块内零损血连通、一起进包、无序
        （§S16 块为目标）→ 块间（隔门/怪）才有时机价值 = 正是 GA 该搜的。
"""
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from probe_crossfloor import build_start                              # noqa: E402
from vzone import build_zone, _zone_attr_gems                         # noqa: E402
from big_item_pull import detect_big_items                            # noqa: E402
from key_targets import detect_key_targets, _afford_closure, _FULL_AFFORD, _NB4  # noqa: E402
from block_targets import build_block_index                           # noqa: E402
from solver.beam import build_future_roster, _combat_damage          # noqa: E402
from solver.fitness import build_zone1_roster, _zone_floor_cells      # noqa: E402


def _reach_set(state, fid, afford, *, zero_blood):
    """单层可达 (x,y) 集（楼梯多源 BFS）。zero_blood=True：只穿 0 损血守怪（=navigate_to 顺路语义·判①）；
    False：守怪一律可穿、只看门墙拓扑（=door-wise·判②/③）。与 key_targets._reachable_* 同口径，只是
    返回整个 cell 集（非过滤到钥匙格）→ 任意物品 cell 都能查档。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, mid_at, _key_cells, src_cells = info

    def passable(x, y):
        if is_wall(x, y):
            return False
        if zero_blood and (x, y) in mid_at:
            return _combat_damage(state, mid_at[(x, y)]) == 0   # None(打不动)/>0 都不算顺路
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
    return seen


def _triage_gems(state, zone_fids, afford):
    """对每个攻防宝石 cell 滚三档（同钥匙口径）。返回 {cell: '①'|'②'|'③'}。"""
    gems = _zone_attr_gems(zone_glob)
    out = {}
    for fid in zone_fids:
        zset = _reach_set(state, fid, afford, zero_blood=True)
        dset = _reach_set(state, fid, afford, zero_blood=False)
        for (gfid, x, y) in gems:
            if gfid != fid:
                continue
            if (x, y) in zset:
                out[(gfid, x, y)] = "①顺路"
            elif (x, y) in dset:
                out[(gfid, x, y)] = "②代价"
            else:
                out[(gfid, x, y)] = "③够不到"
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    global zone_glob
    print("组装（build_start + build_zone + 涌现器·无 route 回放）…")
    start, _ = build_start()
    zone_glob = build_zone()
    roster_big = build_future_roster(start)
    _rk, zone_fids, _ak = build_zone1_roster(start)
    print(f"  一区层 zone_fids = {zone_fids}")

    # ── 涌现：大件 / 钥匙三分 / 宝石三分 ──
    big_cells, tau, ranked = detect_big_items(zone_glob, roster_big, start)
    drp_by_cell = {c: drp for (drp, c, _da, _dd) in ranked}
    cands, info_key = detect_key_targets(start, zone_fids)
    afford = info_key["afford"]
    gems = _zone_attr_gems(zone_glob)
    gem_tri = _triage_gems(start, zone_fids, afford)

    # ── 统一判据 → 候选 cell 集 ──
    big_list = sorted(big_cells)
    cand_gems = sorted(c for c, br in gem_tri.items()
                       if br == "②代价" and c not in big_cells and drp_by_cell.get(c, 0) > 0)
    cand_keys = sorted(cands)
    cand_cells = set(big_list) | set(cand_gems) | set(cand_keys)

    print("\n" + "=" * 78)
    print("判据各分支命中（一区·攻防宝石 + 钥匙）")
    print("=" * 78)
    z = sum(1 for b in gem_tri.values() if b == "①顺路")
    c2 = sum(1 for b in gem_tri.values() if b == "②代价")
    c3 = sum(1 for b in gem_tri.values() if b == "③够不到")
    print(f"  攻防宝石总数 {len(gem_tri)}：①顺路 {z} / ②代价 {c2} / ③够不到 {c3}"
          f"（其中大件 {len(big_cells)} 把：{big_list}）")
    print(f"  afford 钥匙色闭包 = {sorted(afford)}")
    print(f"  钥匙：全集 {len(info_key['all_keys'])} = ①顺路 {len(info_key['cheap'])}"
          f" + ②候选 {len(cands)} + ③够不到 {len(info_key['unreachable'])}")
    print(f"  大件缝 tau={tau:.0f}（缝上=大件·数据涌现）")

    # ── 折成初始块 ──
    fids = sorted(set(zone_fids) | {c[0] for c in cand_cells})
    block_index = build_block_index(fids)
    c2b = block_index["cell_to_block"]
    missing = [c for c in cand_cells if c not in c2b]
    if missing:
        print(f"\n  ⚠ 这些候选 cell 不在任何初始块（非自由格?）须人工核对：{sorted(missing)}")

    colors = info_key["colors"]

    def role_of(c):
        if c in big_cells:
            da, dd = gems.get(c, (0, 0))
            return f"大件·{'剑(攻+%d)' % da if da > 0 else '盾(防+%d)' % dd}"
        if c in cands:
            return f"钥·{colors.get(c, '?')}"
        if c in gems:
            da, dd = gems[c]
            return f"宝石·{'攻+%d' % da if da > 0 else '防+%d' % dd}(ΔRP{drp_by_cell.get(c, 0):.0f})"
        return "?"

    blk_to_cells = {}
    for c in sorted(cand_cells):
        if c in c2b:
            blk_to_cells.setdefault(c2b[c], []).append(c)

    # 按层、再按块 id 排序
    blocks_sorted = sorted(blk_to_cells, key=lambda b: (b[0], b[1]))
    print("\n" + "=" * 78)
    print(f"★ 候选块清单（共 {len(blocks_sorted)} 块·含 ≥1 个 ② 或大件 cell）")
    print("=" * 78)
    cur_floor = None
    for b in blocks_sorted:
        fid = b[0]
        if fid != cur_floor:
            cur_floor = fid
            print(f"\n  ── {fid} ──")
        cells = blk_to_cells[b]
        rep = block_index["block_rep"][b]
        size = len(block_index["block_cells"][b])
        roles = "  ".join(f"{c}[{role_of(c)}]" for c in cells)
        # 该块的判据分支（取成员里最强：大件/②）
        if any(c in big_cells for c in cells):
            why = "含大件（剑/盾·减伤数量级·必进）"
        elif any(c in cands for c in cells):
            why = "含②代价钥（afford门内·打守怪付血才到·有何时取价值）"
        else:
            why = "含②代价宝石（door-wise可达但非零损血·有何时取价值）"
        print(f"    块{b}  代表cell={rep}  块大小={size}格")
        print(f"        成员候选物品: {roles}")
        print(f"        判据: {why}")

    print("\n" + "=" * 78)
    print("排除项（透明·供玩家核对判据没漏没多）")
    print("=" * 78)
    cheap_gems = sorted(c for c, br in gem_tri.items() if br == "①顺路" and c not in big_cells)
    cheap_big = sorted(c for c, br in gem_tri.items() if br == "①顺路" and c in big_cells)
    print(f"  ①顺路宝石（白捡·非候选）{len(cheap_gems)}：{cheap_gems}")
    if cheap_big:
        print(f"  ⚠ 逐层三分判①顺路、但靠【大件分支】仍进候选的大件 {len(cheap_big)}：{cheap_big}")
        print(f"     （per-floor 三分=本层楼梯出发·afford门全开·只算本层损血→漏算跨层到达代价；"
              f"盾的真实代价在跨层旅途·大件分支是必须的安全网）")
    print(f"  ①顺路钥匙（白捡·非候选）{len(info_key['cheap'])}：{sorted(info_key['cheap'])}")
    locked_gems = sorted(c for c, br in gem_tri.items() if br == "③够不到")
    print(f"  ③够不到宝石（锁死·一区外）{len(locked_gems)}：{locked_gems}")
    print(f"  ③够不到钥匙（锁死·一区外）{len(info_key['unreachable'])}：{sorted(info_key['unreachable'])}")
    print(f"  ΔRP≤0 宝石（无减伤·不奖励）"
          f"{sorted(c for c in gems if drp_by_cell.get(c, 0) <= 0)}")


if __name__ == "__main__":
    main()
