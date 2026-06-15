"""块为目标涌现层（§S18 步①/②·岔路 A 定 (a) 纯静态构造）——把"单物品 cell"目标抬成"初始块"目标。

设计（docs/handoff §S18/§S19 定稿，本文件只落地、不再重议）：
  · 初始态来源 = (a) 纯静态 JSON 构造 make_static_state(fid)：load_floor 后【不进任何 step】套最小
    GameState。摆脱 route 文件依赖；初始态天然未操作（_suppressed_events 恒空、一区零大怪 footprint/
    领域怪 → _zone_blocked 恒空）→ 与已验证的 (b) 重放首踏快照【逐格等价】(analysis/ga_block_static_view_diag 坐实)。
  · 块划分 = solver.quotient.partition_floor_blocks（复用已验证 CC floodfill·非另造），用 CC 不用 BCC
    （BCC 在割点处过切；一区实测 CC==BCC 见 ga_block_initial_model_diag 实测 C）。
  · 全局稳定块 id = (fid, min(块内 cell))：含 fid（跨层 min(cell) 会撞）；min 是初始态定死的几何锚、
    与勇者属性/拾取顺序无关（单向吸纳只合并不分裂 → 同一物理块在任何中途态都含此锚 → id 稳定）。
  · 代表 cell = (fid, mx, my)（从 id 结构直接取）：navigate_to 的目标格。进块即 _absorb 吸光整块零损血
    道具（ga_navigate.py:209），故"导航到代表 cell"= 吸下整块——代表 cell 是道具格或空地都成立。

塔无关边界：本文件属 extract/（塔特有驱动层），可知 data/games51 路径与 load_floor，与 ga_loop /
export_mt10_boss_route 同列；solver/ 与 sim/ 仍零塔硬编码（块划分逻辑全在 quotient，本层只喂初始态 +
组织 id）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # solver / sim

from sim.simulator import GameState, HeroState, load_floor   # noqa: E402
from solver.quotient import partition_floor_blocks            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))


def make_static_state(fid):
    """(a) 纯静态：load_floor(fid) → 套最小合法 GameState（current_floor=fid，无任何 step/route）。
    hero 仅为构造合法 GameState 的占位——partition_floor_blocks / _is_free_tile / _zone_blocked 均不读
    hero（块划分是 entities/门/事件的纯函数，与勇者属性无关，见 ga_block_initial_model_diag 实测 A）。"""
    floor = load_floor(FLOORS / f"{fid}.json")
    hero = HeroState(x=0, y=0, hp=1000, atk=10, def_=10, mdef=0, gold=0,
                     keys={}, items={}, flags={})
    return GameState(
        hero=hero, floors={fid: floor}, current_floor=fid,
        floor_ids=FLOOR_IDS, visited_floors={fid},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def _block_id(fid, block):
    """全局稳定块 id = (fid, min(块内 (x,y)))。min 取字典序最小格（初始态几何锚）。"""
    return (fid, min(block))


def build_block_index(fids):
    """对每个 fid 用 (a) 静态构造 + partition_floor_blocks 算初始块集，组装全区块索引。返回 dict：
      · cell_to_block : {(fid,x,y): block_id}      —— detect 吐的 cell 折到所属初始块（build_min_pool 用）
      · block_rep     : {block_id: (fid,mx,my)}     —— 代表 cell（navigate_to 目标）
      · block_cells   : {block_id: frozenset((fid,x,y),...)}  —— 整块全 cell（dump 块大小/成员用）
      · blocks_by_floor: {fid: [block_id 按 min 升序, ...]}    —— 逐层块清单（dump 用）
    塔无关：块划分全走 quotient，本函数只喂静态初始态 + 组织 id（extract/ 驱动层）。"""
    cell_to_block = {}
    block_rep = {}
    block_cells = {}
    blocks_by_floor = {}
    for fid in fids:
        state = make_static_state(fid)
        blocks = partition_floor_blocks(state)
        ids = []
        for blk in sorted(blocks, key=lambda b: min(b)):
            bid = _block_id(fid, blk)
            full = frozenset((fid, x, y) for (x, y) in blk)
            block_rep[bid] = (fid, bid[1][0], bid[1][1])
            block_cells[bid] = full
            for cell in full:
                cell_to_block[cell] = bid
            ids.append(bid)
        blocks_by_floor[fid] = ids
    return {
        "cell_to_block": cell_to_block,
        "block_rep": block_rep,
        "block_cells": block_cells,
        "blocks_by_floor": blocks_by_floor,
    }
