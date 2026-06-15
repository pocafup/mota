"""【一次性诊断·只读·不碰产品码】块为目标 §S18 岔路A —— 坐实 (a) 纯静态 JSON 构造 floor 视图可行性。

问题（§S18 三岔路 A）：块涌现层要"从初始态 CC 算块集"。初始态从哪来两条路：
  (a) 纯静态 JSON 构造：直接 load_floor(*.json) 套最小 state，摆脱 route 依赖。更纯、无 route 债。
  (b) 重放 route 首踏快照：ga_block_initial_model_diag.py 已验证 144 块 / MT4 五钥→4 块，但挂一条 route 文件依赖。

本脚本坐实 (a)：对每个一区层【同时】算 (a) 纯静态构造 与 (b) 重放首踏快照的块划分，
【逐格断言 free_all 与块集完全一致】（不只是块数相同，是 cell-for-cell 同分区），MT4 五钥归属同样对照。
  · 两者一致 ⇒ (a) 与已验证的 (b) 严格等价 ⇒ (a) 可行、用 (a)（摆脱 route 依赖）。
  · 任何不一致 ⇒ (a) 有坑 ⇒ 退 (b)。

口径保证同源：直接 import 诊断脚本里已验证的 _partition / _stable_blocks / _first_entry_snapshots，
            底层 _is_free_tile / _zone_blocked / _DELTAS 全是 solver.quotient 产品函数本体。

(a) 构造依据（Agent 坐实，CLAUDE.md「不猜」）：_is_free_tile 读 11 类字段，10 类直接来自静态 JSON；
唯一运行时字段 floor._suppressed_events 在初始态恒为空集（load_floor 硬初始化 set()）。一区零 footprint
大怪、零领域/夹击/阻击怪 → _zone_blocked / _in_alive_monster_footprint 在一区恒空/恒 False。
故"构造静态 floor 视图 = 调 load_floor 但不进任何 step"，无需新写派生逻辑。

跑法：python analysis/ga_block_static_view_diag.py  [--no-persistent]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extract"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import GameState, HeroState, load_floor                     # noqa: E402
from ga_loop import build_harness                                             # noqa: E402
# 复用已验证的同口径原语（_is_free_tile/_zone_blocked/_DELTAS 经它落到 solver.quotient 本体）
from ga_block_initial_model_diag import (                                     # noqa: E402
    _partition, _stable_blocks, _first_entry_snapshots,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
ROUTE_FILE = ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"


def make_static_state(fid: str) -> GameState:
    """(a) 纯静态：load_floor(fid) → 套最小 GameState，current_floor=fid，无任何 step/route。

    hero 仅为构造合法 GameState 的占位（_partition / _is_free_tile / _zone_blocked 均不读 hero）。
    """
    floor = load_floor(FLOORS / f"{fid}.json")
    hero = HeroState(
        x=0, y=0, hp=1000, atk=10, def_=10, mdef=0, gold=0,
        keys={}, items={}, flags={},
    )
    return GameState(
        hero=hero, floors={fid: floor}, current_floor=fid,
        floor_ids=FLOOR_IDS, visited_floors={fid},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-persistent", action="store_true")
    args = ap.parse_args()

    print("组装 GA 电池组（取 zone_fids / meta / pool）…")
    H = build_harness(persistent=not args.no_persistent)
    zone_fids = set(H["zone_fids"])
    meta = H["meta"]
    pool_cells = list(H["pool"])
    print(f"  一区层 zone_fids = {sorted(zone_fids)}")

    print(f"\n(b) 重放 route 首踏各一区层快照…  {ROUTE_FILE.name}")
    snaps_b = _first_entry_snapshots(ROUTE_FILE, zone_fids)
    print(f"  (b) 捕获层 = {sorted(snaps_b)}")

    print("\n(a) 纯静态 load_floor 构造各一区层（无 route）…")
    states_a = {fid: make_static_state(fid) for fid in sorted(zone_fids)}
    print(f"  (a) 构造层 = {sorted(states_a)}")

    # ── 逐层 cell-for-cell 对照 ───────────────────────────────────────────────
    print("\n" + "=" * 84)
    print("逐层对照：(a) 纯静态构造  vs  (b) 重放首踏快照  —— free_all 与块集是否【逐格一致】")
    print("=" * 84)
    all_fids = sorted(zone_fids)
    total_a = total_b = total_shared_a = 0
    shared_match = True            # 共有层是否逐格一致（真正的可行性判据）
    mismatches = []
    a_only = []                    # (a) 独有层 = (b) route 首踏盲区（非不一致）
    for fid in all_fids:
        free_a, blk_a = _partition(states_a[fid])
        total_a += len(blk_a)
        if fid in snaps_b:
            free_b, blk_b = _partition(snaps_b[fid])
            total_b += len(blk_b)
            total_shared_a += len(blk_a)
            free_same = (free_a == free_b)
            blk_same = (set(blk_a) == set(blk_b))
            same = free_same and blk_same
            shared_match &= same
            if same:
                tag = "✅一致"
            else:
                tag = f"❌不一致(free_all同={free_same} 块集同={blk_same})"
                mismatches.append((fid, free_a, free_b, blk_a, blk_b))
            print(f"  [{fid}] (a)块数={len(blk_a):2d} 自由格={len(free_a):3d}  |  "
                  f"(b)块数={len(blk_b):2d} 自由格={len(free_b):3d}   {tag}")
        else:
            a_only.append((fid, len(blk_a), len(free_a)))
            print(f"  [{fid}] (a)块数={len(blk_a):2d} 自由格={len(free_a):3d}  |  "
                  f"(b)未捕获该层（route 首踏从没进过 → 盲区，非不一致）—— 仅 (a) 有")
    print(f"\n  共有层合计：(a) 块={total_shared_a}   (b) 块={total_b}   "
          f"→ {'✅ 共有层总块数相同' if total_shared_a == total_b else '❌ 共有层总块数不同'}")
    print(f"  (a) 全覆盖合计：{total_a} 块（含 (b) 盲区层 {[f for f, _, _ in a_only]} 共 {total_a - total_shared_a} 块）")

    # ── 不一致细节 ───────────────────────────────────────────────────────────
    if mismatches:
        print("\n  ⚠ 不一致明细（(a) 有坑、须退 (b)）：")
        for fid, fa, fb, ba, bb in mismatches:
            only_a = sorted(fa - fb)
            only_b = sorted(fb - fa)
            print(f"    [{fid}] 仅(a)自由格={only_a[:20]}  仅(b)自由格={only_b[:20]}")

    # ── MT4 五钥归属对照 ─────────────────────────────────────────────────────
    print("\n" + "=" * 84)
    print("MT4 五钥+宝石归属对照：(a) vs (b) 落在几个初始块、块 id 是否一致")
    print("=" * 84)
    mt4_goals = sorted(c for c in pool_cells if c[0] == "MT4")
    print(f"  MT4 目标格（来自 pool）= {mt4_goals}")
    for label, src in (("(a)纯静态", states_a.get("MT4")),
                       ("(b)重放  ", snaps_b.get("MT4"))):
        if src is None:
            print(f"  {label}: 无 MT4 态")
            continue
        _free, blocks = _partition(src)
        _sb, c2i = _stable_blocks(blocks)
        bids = sorted({c2i.get((x, y)) for _fid, x, y in mt4_goals if c2i.get((x, y)) is not None})
        miss = [(x, y) for _fid, x, y in mt4_goals if c2i.get((x, y)) is None]
        print(f"  {label}: 落在 {len(bids)} 个初始块 bids={bids}"
              f"{'  非自由格(不在任何块)=' + str(miss) if miss else ''}")

    # ── 总判决 ───────────────────────────────────────────────────────────────
    # 可行性判据 = 共有层是否逐格一致；(a) 独有层(route 盲区)不算不一致、反是 (a) 覆盖更全的体现。
    print("\n" + "=" * 84)
    if shared_match and not mismatches:
        print("★判决：(a) 纯静态构造 在【所有 (b) 能捕获的层】与 (b) 重放首踏快照【逐格完全一致】(free_all+块集)。")
        print(f"        + (a) 额外覆盖 (b) route 盲区层 {[f for f, _, _ in a_only]}（route 首踏从没进过、(b) 整层缺失）。")
        print("        ⇒ (a) 可行、与已验证 (b) 在重叠面严格等价，且覆盖更全。")
        print("        建议用 (a)：摆脱 route 文件依赖；初始态天然未操作（不靠 (b)『route 首踏前未改层』隐含假设）；无盲区。")
    else:
        print("★判决：(a) 与 (b) 在【共有层】存在逐格不一致 → (a) 有坑、本棒退 (b)。见上方不一致明细。")
    print("=" * 84)


if __name__ == "__main__":
    main()
