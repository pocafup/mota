"""【解码后规整·必做层护栏单测·块版】§S12 自欺序列真解的两条命门 + 复刻一致性（§S18 目标＝初始块 id）。

钉死「只折叠真自欺、不误伤有效排序」（基因元素＝块 id；进包判据＝块折进的全部 pool 物品 cell·block_markers）：
  · 含盾 [盾块,剑块,5钥块,3宝块] ≡ [剑块,盾块,…] → 规整出【相同】normalized（去盾顺路吸剑致剑排序失效＝§S11
    自欺、该折叠），且终态全同 → fitness 相等（佐证规整不改值）；
  · ★无盾 [剑块,5钥块] ≠ [5钥块,剑块] → 规整出【不同】normalized（剑早拿在无盾解有真实价值 Δ+16826、有效序
    不该被误折叠）——这条是生死线：误折叠＝毁掉 +16826 信号＝规整做错。剑块(MT5)/钥块(MT4)异层必不同块、
    天然不折叠；Δ 精确 +16826 兼当【块边界漂移】哨兵（剑/钥块若误并入宝石块 → Δ 变 → 本测红）。
  · 一致性：_decode_with_order 终态【逐字段】等于封板 decode（规整没改 decode 行为＝fitness 不变前提）。

真 navigate_to（含盾深盾冷算·分钟级）→ 标 slow；module fixture 共享一次 build_harness + 四基因解码。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest

from ga_loop import build_harness, _decode_with_order   # noqa: E402
from ga_decode import decode                             # noqa: E402
from solver.fitness import fitness                       # noqa: E402


def _hero_tuple(s):
    """终态可比指纹（逐字段）：当前层 + 英雄位置/血/攻/防/各色钥匙。"""
    h = s.hero
    return (s.current_floor, h.x, h.y, h.hp, h.atk, h.def_, tuple(sorted(dict(h.keys).items())))


@pytest.fixture(scope="module")
def cooked():
    """一次 build_harness + 四基因（无盾 X1/Y1·含盾 X2/Y2）双解码：封板 decode 终态 + 规整终态/normalized
    + fitness。decode 与 _decode_with_order 共享 decode_cache → 同基因第二次解码命中、不重复冷算深盾。"""
    h = build_harness()
    start, zone, step = h["start"], h["zone"], h["step"]
    cache = h["decode_cache"]
    bm = h["block_markers"]                       # 块模式进包判据（块为目标·必传 _decode_with_order）
    m = h["meta"]
    sword, shield, keys, gems = m["sword"], m["shield"], m["keys"], m["gems"]   # 现为块 id（非 cell）
    genes = {
        "X1": [sword] + keys,                    # 无盾·剑早（剑块在 5 钥块之前）
        "Y1": keys + [sword],                    # 无盾·剑晚（5 钥块之后才拿剑块）
        "X2": [sword, shield] + keys + gems,     # 含盾·剑块在盾块前
        "Y2": [shield, sword] + keys + gems,     # 含盾·盾块在剑块前（盾腿顺路吸剑＝§S11 自欺）
    }
    out = {}
    for name, g in genes.items():
        _t1, final_dec = decode(g, start, zone, step, cache=cache)
        _t2, final_ord, norm = _decode_with_order(g, start, zone, step, cache, block_markers=bm)
        f = fitness(final_dec, h["roster_fit"], h["big"], h["zone_fids"],
                    w_potion=1.5, w_key=39.0)
        out[name] = dict(gene=g, final_dec=final_dec, final_ord=final_ord, norm=norm, fit=f)

    # ── 诊断摘要（pytest -s 可见）：四基因 normalized + fitness + 终态，供人核对折叠边界 ──
    print("\n" + "=" * 80)
    for nm in ("X1", "Y1", "X2", "Y2"):
        d = out[nm]
        hh = d["final_dec"].hero
        print(f"  {nm} gene={d['gene']}")
        print(f"     normalized = {d['norm']}")
        print(f"     fitness={d['fit']:.1f}   终态 ATK={hh.atk} DEF={hh.def_} HP={hh.hp}")
    print(f"  无盾 X1 vs Y1：norm 相同? {out['X1']['norm'] == out['Y1']['norm']}   "
          f"Δfit(剑早−剑晚)={out['X1']['fit'] - out['Y1']['fit']:+.1f}")
    print(f"  含盾 X2 vs Y2：norm 相同? {out['X2']['norm'] == out['Y2']['norm']}   "
          f"Δfit={out['X2']['fit'] - out['Y2']['fit']:+.1f}")
    print("=" * 80)
    return out


@pytest.mark.slow
def test_normalized_decode_matches_sealed_decode(cooked):
    """规整复刻的终态【逐字段】等于封板 decode（四基因全过）——规整没改 decode 行为＝fitness 不变的前提。"""
    for name, d in cooked.items():
        assert _hero_tuple(d["final_dec"]) == _hero_tuple(d["final_ord"]), \
            f"{name}: _decode_with_order 终态与封板 decode 不一致（规整改了 decode 行为！）"


@pytest.mark.slow
def test_shielded_self_deception_folds(cooked):
    """含盾命门：[盾,剑,..] 与 [剑,盾,..] 规整出【相同】normalized（§S11 自欺被折叠）；
    且两者终态全同 → fitness 相等（佐证折叠不改值＝去盾顺路吸剑后 X2/Y2 本就同终态）。"""
    x2, y2 = cooked["X2"], cooked["Y2"]
    assert x2["norm"] == y2["norm"], \
        f"含盾自欺未折叠：X2={x2['norm']}  Y2={y2['norm']}"
    assert abs(x2["fit"] - y2["fit"]) < 1e-9, \
        f"含盾两序 fitness 应相等（终态全同），实得 X2={x2['fit']} Y2={y2['fit']}"


@pytest.mark.slow
def test_shieldless_effective_order_not_folded(cooked):
    """★生死线·无盾命门：[剑,5钥] 与 [5钥,剑] 规整出【不同】normalized（剑早拿有效序存活、不被误折叠）；
    且 fitness 真有别、剑早严格更优（Δ+16826，§S12 铁证）——误折叠＝毁掉这条信号＝规整做错。"""
    x1, y1 = cooked["X1"], cooked["Y1"]
    assert x1["norm"] != y1["norm"], \
        f"★无盾有效序被误折叠（+16826 信号被毁）：X1={x1['norm']}  Y1={y1['norm']}"
    delta = x1["fit"] - y1["fit"]
    assert delta > 0, \
        f"剑早(X1)应严格优于剑晚(Y1)，实得 X1={x1['fit']} Y1={y1['fit']} Δ={delta:+.1f}"
    assert abs(delta - 16826.0) < 1e-6, \
        f"★生死线 Δ 漂移（块边界哨兵）：剑早−剑晚应＝+16826.0（§S12 铁证·块版同值），实得 {delta:+.1f}"
