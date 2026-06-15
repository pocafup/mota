"""【块涌现层契约·单测】build_block_index：detect cell → 所属初始块 id（§S18 块为目标地基·纯静态构造）。

钉死四条契约：
  · 块 id ＝ (fid, min(块内 (x,y)))：含 fid（跨层 min 会撞）、min 是初始态几何锚 → 全局稳定；
  · 代表 cell ＝ (fid, mx, my) 从 id 结构直接取，且【必在块内】（navigate_to 目标格落在该块）；
  · cell_to_block 自洽：block_cells 每个 cell 都折回它自己的块 id（无错折、无漏）；
  · 块集 == partition_floor_blocks 逐层结果（块层只组织 id·不改划分），且两次构造确定一致。
纯静态初始态（make_static_state·route-free）→ 不慢、不标 slow。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest                                                          # noqa: E402

from block_targets import build_block_index, make_static_state        # noqa: E402
from solver.quotient import partition_floor_blocks                    # noqa: E402

ZONE1_FIDS = ["MT1", "MT2", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9"]


@pytest.fixture(scope="module")
def index():
    return build_block_index(ZONE1_FIDS)


def test_block_id_is_fid_min_cell(index):
    """块 id ＝ (fid, min(块内 (x,y)))：第二元是块内字典序最小格。"""
    for bid, cells in index["block_cells"].items():
        fid = bid[0]
        xy = {(x, y) for (_f, x, y) in cells}
        assert bid == (fid, min(xy)), f"块 id 非 (fid,min)：{bid} vs min={min(xy)}"


def test_rep_cell_derivable_and_inside_block(index):
    """代表 cell ＝ (fid, mx, my)（从 id 结构取）且必在块内（navigate_to 目标落在块上）。"""
    for bid, rep in index["block_rep"].items():
        fid, (mx, my) = bid
        assert rep == (fid, mx, my), f"代表 cell 非从 id 取：{rep} vs {(fid, mx, my)}"
        assert rep in index["block_cells"][bid], f"代表 cell {rep} 不在块 {bid} 内"


def test_cell_to_block_consistent(index):
    """cell_to_block 自洽：block_cells 每个 cell 折回所属块 id；键集恰＝所有块 cell 的并。"""
    c2b = index["cell_to_block"]
    for bid, cells in index["block_cells"].items():
        for c in cells:
            assert c2b[c] == bid, f"{c} 折到 {c2b.get(c)}，应为 {bid}"
    all_cells = set().union(*index["block_cells"].values())
    assert set(c2b) == all_cells


def test_blocks_match_partition(index):
    """build_block_index 的块集 == partition_floor_blocks 逐层结果（块层只组织 id·不改划分）。"""
    for fid in ZONE1_FIDS:
        s = make_static_state(fid)
        raw = {frozenset((fid, x, y) for (x, y) in b) for b in partition_floor_blocks(s)}
        got = {index["block_cells"][bid] for bid in index["blocks_by_floor"][fid]}
        assert got == raw, f"{fid}: 块集与 partition 不一致"


def test_deterministic():
    """两次构造得相同索引（块身份初始态定死）。"""
    a = build_block_index(ZONE1_FIDS)
    b = build_block_index(ZONE1_FIDS)
    assert a["cell_to_block"] == b["cell_to_block"]
    assert a["block_rep"] == b["block_rep"]
    assert a["block_cells"] == b["block_cells"]
    assert a["blocks_by_floor"] == b["blocks_by_floor"]
