"""【一次性诊断·只读·不碰产品码】块为目标重构 —— 玩家"初始态块定义 + 单向吸纳"模型实证。

上个 session 把"块没有跨属性稳定身份"判成死结；玩家用游戏机制解开：块身份用【初始态】定死，
运行时动态只跟勇者强相关、且【不会让两个勇者都不在的块自己合并】，真正改结构的特殊事件全塔不超过 10 个。
本 session【只坐实+评估、不实现、不改产品码】，按 CLAUDE.md 铁律实跑钉死、不靠记忆。

复刻 quotient 引擎口径（_is_free_tile / _zone_blocked / _DELTAS / _killable），不改任何产品码。

═══ 坐实两条机制断言 ═══
断言1 单向吸纳：块合并只由勇者边界算子（杀怪/开门/触发）驱动、永远"勇者块吸纳相邻块"，绝不"两个
              勇者都不在的块自己合并"。
  实测A 属性隔离：同一态、只把勇者 atk/def/mdef/hp 拉满（不杀怪/不开门/不动 entities）→ 块划分必须
                逐格不变。证：块划分是 entities/门/事件 的纯函数、与勇者属性无关 → 合并必由算子驱动、
                非属性自动并块。附带：同态低/高属性下【可杀怪数】对照，证"边"才是属性动态的栖身处。
  实测B 单向性：重放标尺 route，逐步重算整层块划分，任何"≥2 个旧块并进 1 个新块"事件都断言勇者上一步
              在其中一块内。报告全部并块事件 + 勇者是否参与；勇者都不在者 = 反例（疑似特殊事件）。
断言2 初始块可计算：从初始态（make_initial_state 首踏各层 = 该层未被操作的初始 entities）floodfill 算
              全区静态块集、每块稳定 id。Dump 块数 + 五钥各属哪个初始块。
              连通分量(CC) vs 双连通分量(BCC) 术语对齐：逐块数割点（割点=0 → 该块本身双连通 → CC==BCC）。
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

from solver.quotient import _is_free_tile, _zone_blocked, _killable, _DELTAS   # noqa: E402
from ga_loop import build_harness                                              # noqa: E402
from export_mt10_boss_route import make_initial_state                          # noqa: E402
from decode_route import parse_rle_route, decompress                          # noqa: E402
from sim.simulator import step                                                 # noqa: E402


# ─── 块划分（覆盖式 floodfill·与 count_floor_blocks 同口径）───────────────────────
def _partition(state):
    floor = state.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    zb = _zone_blocked(state)
    free_all = {(x, y) for y in range(rows) for x in range(cols)
                if _is_free_tile(state, x, y, zb)}
    seen, blocks = set(), []
    for c in free_all:
        if c in seen:
            continue
        comp, dq = set(), deque([c])
        seen.add(c)
        while dq:
            cx, cy = dq.popleft()
            comp.add((cx, cy))
            for dx, dy in _DELTAS:
                nb = (cx + dx, cy + dy)
                if nb in free_all and nb not in seen:
                    seen.add(nb)
                    dq.append(nb)
        blocks.append(frozenset(comp))
    return free_all, blocks


def _stable_blocks(blocks):
    """稳定 id：块按 min(cell) 排序 → 列表序即 id。返回 (sorted_blocks, cell->id)。"""
    sb = sorted(blocks, key=lambda b: min(b))
    c2i = {c: i for i, b in enumerate(sb) for c in b}
    return sb, c2i


def _connected(cells):
    if not cells:
        return True
    start = next(iter(cells))
    seen, dq = {start}, deque([start])
    while dq:
        cx, cy = dq.popleft()
        for dx, dy in _DELTAS:
            nb = (cx + dx, cy + dy)
            if nb in cells and nb not in seen:
                seen.add(nb)
                dq.append(nb)
    return len(seen) == len(cells)


def _articulation_count(block):
    """块内割点数（删一格后是否断开·块≤51 格暴力即可，绝对正确）。0 ⇒ 该块本身双连通(BCC==CC)。"""
    nodes = set(block)
    if len(nodes) <= 2:
        return 0
    return sum(1 for c in nodes if not _connected(nodes - {c}))


def _killable_count(state):
    floor = state.floor
    return sum(1 for y, row in enumerate(floor.entities) for x, e in enumerate(row)
               if floor._tile_to_enemy.get(e) and _killable(state, x, y))


# ─── 重放工具 ────────────────────────────────────────────────────────────────
def _load_actions(route_file):
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    return parse_rle_route(decompress(outer["route"]))


def _first_entry_snapshots(route_file, target_fids):
    """重放，首次踏入各 target 层即深拷贝快照（= 该层未被操作的初始 entities）。"""
    import copy
    actions = _load_actions(route_file)
    s = make_initial_state()
    snaps = {}
    if s.current_floor in target_fids:
        snaps[s.current_floor] = copy.deepcopy(s)
    for a in actions:
        s = step(s, a)
        if s.dead:
            break
        f = s.current_floor
        if f in target_fids and f not in snaps:
            snaps[f] = copy.deepcopy(s)
    return snaps


# ─── 实测A：属性隔离 → 块划分与勇者属性无关 ──────────────────────────────────────
def test_A(snaps):
    print("\n" + "=" * 80)
    print("实测A 属性隔离：同态只拉满勇者 atk/def/mdef/hp（不动 entities）→ 块划分必须逐格不变")
    print("  (若不变 ⇒ 块划分是 entities/门/事件 纯函数、与属性无关 ⇒ 合并必由算子驱动·非属性自动并块)")
    print("=" * 80)
    all_pass = True
    for fid in sorted(snaps):
        s = snaps[fid]
        free1, blk1 = _partition(s)
        kc_lo = _killable_count(s)
        saved = (s.hero.atk, s.hero.def_, s.hero.mdef, s.hero.hp)
        s.hero.atk = s.hero.def_ = s.hero.mdef = 99999
        s.hero.hp = 9_999_999
        free2, blk2 = _partition(s)
        kc_hi = _killable_count(s)
        s.hero.atk, s.hero.def_, s.hero.mdef, s.hero.hp = saved
        same = (free1 == free2) and (set(blk1) == set(blk2))
        all_pass &= same
        tag = "✅块划分逐格不变" if same else "❌块划分变了(属性影响了划分!)"
        print(f"  [{fid}] 块数={len(blk1)} 自由格={len(free1)}  {tag}"
              f"   可杀怪数 低属性={kc_lo} → 满属性={kc_hi}"
              f"  {'(边随属性增·块不变=动态只在边)' if kc_hi > kc_lo else ''}")
    print(f"\n  ★实测A 结论：{'全层块划分与属性无关 ✅（断言1 机制根据成立）' if all_pass else '有反例 ❌'}")
    return all_pass


# ─── 实测B：单向吸纳 → 并块事件勇者必在其中一块 ──────────────────────────────────
def test_B(route_file):
    print("\n" + "=" * 80)
    print("实测B 单向吸纳：重放 route 逐步重算整层块划分，每次'≥2 旧块并进 1 新块'断言勇者上一步在其一")
    print("  (勇者都不在 = 反例 = 两个勇者都不在的块自己合并 = 玩家说的特殊事件)")
    print("=" * 80)
    actions = _load_actions(route_file)
    s = make_initial_state()
    prev_floor = s.current_floor
    prev_hero = (s.hero.x, s.hero.y)
    _, prev_blk = _partition(s)
    merge_total = 0
    merge_hero_in = 0
    counterex = []
    step_idx = 0
    for a in actions:
        s = step(s, a)
        step_idx += 1
        if s.dead:
            break
        cur_floor = s.current_floor
        _, cur_blk = _partition(s)
        if cur_floor == prev_floor:
            for nb in cur_blk:
                overlapped = [ob for ob in prev_blk if ob & nb]
                if len(overlapped) >= 2:                 # ≥2 旧块并进同一新块 = 一次并块
                    merge_total += 1
                    hero_in = any(prev_hero in ob for ob in overlapped)
                    if hero_in:
                        merge_hero_in += 1
                    else:
                        counterex.append((step_idx, cur_floor, prev_hero,
                                          [min(ob) for ob in overlapped]))
        prev_floor, prev_hero, prev_blk = cur_floor, (s.hero.x, s.hero.y), cur_blk
    print(f"  并块事件总数={merge_total}  勇者参与(在其中一块)={merge_hero_in}  反例(都不在)={len(counterex)}")
    if counterex:
        print("  ⚠ 反例（疑似特殊事件·两个勇者都不在的块自合并）：")
        for si, fid, hpos, mins in counterex[:20]:
            print(f"    step#{si} [{fid}] 勇者@{hpos} 并入的旧块锚点={mins}")
    else:
        print("  ★实测B 结论：route 全程零反例 → 单向吸纳模型在标尺路线上成立 ✅")
    return len(counterex)


# ─── 实测C：初始块可计算 + 五钥归属 + CC/BCC 术语对齐 ────────────────────────────
def test_C(snaps, meta):
    keys, gems = set(meta["keys"]), set(meta["gems"])

    def lab(c):
        if c == meta.get("sword"):
            return f"剑{c}"
        if c == meta.get("shield"):
            return f"盾{c}"
        if c in keys:
            return f"钥{c}"
        if c in gems:
            return f"宝石{c}"
        return f"目标{c}"

    print("\n" + "=" * 80)
    print("实测C 初始块可计算：各层初始态块集 + 稳定 id + 割点(CC vs BCC 对齐)")
    print("=" * 80)
    total_blocks = total_art_blocks = 0
    for fid in sorted(snaps):
        free, blocks = _partition(snaps[fid])
        sb, _c2i = _stable_blocks(blocks)
        arts = [_articulation_count(b) for b in sb]
        n_art_blocks = sum(1 for a in arts if a > 0)
        total_blocks += len(sb)
        total_art_blocks += n_art_blocks
        print(f"  [{fid}] 初始块数={len(sb):2d} 自由格={len(free):3d}  "
              f"含割点的块数={n_art_blocks}（割点>0 ⇒ BCC 会把该块再切细；=0 ⇒ CC==BCC）")
    print(f"\n  全区合计：初始块={total_blocks}  含割点的块={total_art_blocks}  "
          f"→ {'CC==BCC（双连通分量不会过切·术语等价）' if total_art_blocks == 0 else 'CC≠BCC（有几何瓶颈格·BCC 会过切·建议用 CC）'}")

    # MT4 详查：五钥 + 宝石各属哪个初始块
    if "MT4" in snaps:
        print("\n  —— MT4 详查（五钥所在层）——")
        free, blocks = _partition(snaps["MT4"])
        sb, c2i = _stable_blocks(blocks)
        h = snaps["MT4"].hero
        print(f"  首踏 MT4：勇者@({h.x},{h.y}) atk={h.atk} def={h.def_}  初始块数={len(sb)}")
        mt4_goals = sorted(c for c in meta_pool_cells if c[0] == "MT4")
        rows = []
        for c in mt4_goals:
            _fid, x, y = c
            bid = c2i.get((x, y))
            sz = len(sb[bid]) if bid is not None else None
            art = _articulation_count(sb[bid]) if bid is not None else None
            rows.append((lab(c), (x, y), bid, sz, art))
        for name, xy, bid, sz, art in rows:
            where = (f"初始块#{bid}(大小{sz}·割点{art})" if bid is not None
                     else "非自由格(被守怪/门/墙挡·不在任何块)")
            print(f"    {name:>14} @{xy} → {where}")
        bids = sorted({bid for _, _, bid, _, _ in rows if bid is not None})
        print(f"  ★MT4 目标落在 {len(bids)} 个初始块 {bids} "
              f"→ {'同块(块内一起拿)' if len(bids) == 1 else '分散(每块一个 GA 目标·跨块付代价才连通)'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-persistent", action="store_true")
    args = ap.parse_args()

    print("组装 GA 电池组（取 zone_fids / meta / pool）…")
    H = build_harness(persistent=not args.no_persistent)
    zone_fids = set(H["zone_fids"])
    meta = H["meta"]
    global meta_pool_cells
    meta_pool_cells = list(H["pool"])
    print(f"  一区层 zone_fids = {sorted(zone_fids)}")

    root = Path(__file__).resolve().parent.parent
    route_file = root / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"

    print("\n首次踏入各一区层快照（初始 entities）…")
    snaps = _first_entry_snapshots(route_file, zone_fids)
    print(f"  捕获层 = {sorted(snaps)}")

    test_A(snaps)
    test_C(snaps, meta)
    test_B(route_file)


if __name__ == "__main__":
    main()
