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


# ─── +16826 生死线·块边界漂移哨兵（§S20/S21·规整退役后从护栏单测迁来·改挂 fitness）──
# 无盾 [剑块,5钥块] vs [5钥块,剑块]：剑块 MT5 / 钥块 MT4 异层必不同块 → 天然不可折叠（结构性·非靠规整）。
# Δfitness(剑早−剑晚)=+16826.0 是无盾解「剑该早拿」的核心信号（§S12 铁证），同时兼【块边界漂移哨兵】：
# 剑/钥块若误并入宝石块 → 终态变 → fitness 变 → Δ 漂 → 本测红。规整去重退役后 Δ 直接由封板 decode+fitness
# 算（不经 normalized_order）→ 哨兵与规整解耦、独立守住。真 navigate_to 深算 → 标 slow。
@pytest.fixture(scope="module")
def sword_order_fits():
    """无盾剑早 X1=[剑块]+5钥块 / 剑晚 Y1=5钥块+[剑块] 各 decode→fitness（共享 decode_cache·只冷算一次）。"""
    from ga_loop import build_harness          # 重 import 局部化 → 不拖慢本文件快测 collection
    from ga_decode import decode
    from solver.fitness import fitness
    h = build_harness()
    start, zone, step = h["start"], h["zone"], h["step"]
    cache = h["decode_cache"]
    m = h["meta"]
    sword, keys = m["sword"], m["keys"]        # 块 id（meta 角色→块 id）
    out = {}
    for name, g in (("X1", [sword] + keys), ("Y1", keys + [sword])):
        _t, final = decode(g, start, zone, step, cache=cache)
        out[name] = fitness(final, h["roster_fit"], h["big"], h["zone_fids"], w_potion=1.5, w_key=39.0)
    return out


@pytest.mark.slow
def test_sword_early_16826_sentinel(sword_order_fits):
    """★生死线：无盾剑早(X1)严格优于剑晚(Y1)、Δ＝+16826.0（§S20/S21 块版铁证·兼块边界漂移哨兵）。"""
    delta = sword_order_fits["X1"] - sword_order_fits["Y1"]
    assert delta > 0, f"剑早(X1)应严格优于剑晚(Y1)，实得 Δ={delta:+.1f}"
    assert abs(delta - 16826.0) < 1e-6, \
        f"★块边界漂移哨兵：剑早−剑晚应＝+16826.0，实得 {delta:+.1f}（剑/钥块或误并入别块）"
