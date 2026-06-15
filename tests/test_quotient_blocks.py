"""【块划分契约·单测】partition_floor_blocks ＝ 整层自由格的 4-邻接连通块；count_floor_blocks ＝ 其计数视图。

钉死三条契约（块为目标涌现层的地基·§S18）：
  · 划分性：块两两不交、并集＝全部自由格（_is_free_tile 判真者）、每块非空 → free_all 的真划分；
  · 计数视图一致：count_floor_blocks ＝ (len(块), Σ块大小)（probe_crossfloor/phase1 两调用方旧契约不破）；
  · 确定性：同初始态两次划分得【相同】块集（块身份初始态定死·与遍历顺序无关）。
纯静态初始态（make_static_state·route-free）→ 不慢、不标 slow。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest                                                          # noqa: E402

from block_targets import make_static_state                           # noqa: E402
from solver.quotient import (                                         # noqa: E402
    partition_floor_blocks, count_floor_blocks, _is_free_tile, _zone_blocked)

ZONE1_FIDS = ["MT1", "MT2", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9"]


@pytest.mark.parametrize("fid", ZONE1_FIDS)
def test_blocks_partition_free_tiles(fid):
    """块集是【全部自由格】的真划分：每块非空、两两不交、并集＝free_all。"""
    s = make_static_state(fid)
    zb = _zone_blocked(s)
    floor = s.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    free_all = {(x, y) for y in range(rows) for x in range(cols)
                if _is_free_tile(s, x, y, zb)}
    blocks = partition_floor_blocks(s, zb)
    assert all(len(b) > 0 for b in blocks), f"{fid}: 出现空块"
    union = set()
    for b in blocks:
        assert union.isdisjoint(b), f"{fid}: 块重叠 {set(b) & union}"
        union |= set(b)
    assert union == free_all, f"{fid}: 块并集≠自由格全集（缺{free_all - union} 多{union - free_all}）"


@pytest.mark.parametrize("fid", ZONE1_FIDS)
def test_count_is_view_of_partition(fid):
    """count_floor_blocks ＝ (块数, 自由格合计)＝ partition 的计数视图（旧调用方契约不破）。"""
    s = make_static_state(fid)
    blocks = partition_floor_blocks(s)
    assert count_floor_blocks(s) == (len(blocks), sum(len(b) for b in blocks))


@pytest.mark.parametrize("fid", ZONE1_FIDS)
def test_partition_deterministic(fid):
    """同初始态两次划分得相同块集（块身份与遍历顺序无关·确定性）。"""
    s = make_static_state(fid)
    assert set(partition_floor_blocks(s)) == set(partition_floor_blocks(s))
