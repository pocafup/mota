"""守卫单测（命门·路径B）：钉死 region 打分键的【区势能项 _future_potential】三层分离，
   防它污染【无损剪枝界 value_vector】、且 λ=0 对原版字节零回归。

与 test_pull_guard.py 对偶：那个钉 vzone 路径的 pull(β)，这个钉 region 路径的区势能(λ)。
玩家 2026-06-11 拍板走路径B（区势能进 base 打分键、结构性免疫 κ=1）的两条命门：
  命门①  区势能只进 beam 排序键、绝不进 value_vector —— 算 _future_potential 逐字节不改剪枝界/态。
  命门②  λ=0 / future=None 返回 int 0 → 与原版字节一致；整条 search_quotient 行为逐字段不变。
  命门③（结构性免疫 κ=1）区势能 = 对【当前区·剩余存活怪】的 Σ 残损惩罚，是当前属性+存活体的纯
          函数：+atk 只会【降低】它（残损更小），绝不为「够得到但没拿」的宝石加分（拿到才兑现）。

电池组用【真引擎重放 route token 到多检查点】取态（遵铁律：绝不手造态/手算属性）；roster 从干净
起点 build_start（确有 _floors_dir）一次构建、复用于所有态，_future_potential 读各态 live floors
算存活残留——与 probe_crossfloor_beam 同口径。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest

from probe_crossfloor import build_start
from seg_experiment import load_tokens
from sim.simulator import step, _copy_state
from solver.search import _value_map
from solver.quotient import value_vector, search_quotient
from solver.beam import (build_future_roster, FutureCfg, _future_potential,
                         equiv_hp_over_roster, region_reference)


@pytest.fixture(scope="module")
def roster():
    """区势能 roster：从干净起点(build_start，确有 _floors_dir)一次构建，复用于所有态。"""
    start, _ = build_start()
    return build_future_roster(start)


@pytest.fixture(scope="module")
def battery():
    """真引擎重放 route 到多 token 检查点的态电池组（全 engine-true，绝不手造态/手改属性）。
    覆盖 MT3→MT9 多层、拿剑前后多属性态——区势能在不同区/不同属性下都要守住命门。"""
    start, nopen = build_start()
    toks = load_tokens()
    ckpts = [82, 120, 160, 220, 300, 400, 520, 680]
    snaps = [_copy_state(start)]            # 检查点 82 = 噩梦后起点本身
    s = start
    for i in range(nopen, max(ckpts)):
        if i >= len(toks):
            break
        s = step(s, toks[i])
        if (i + 1) in ckpts:
            snaps.append(_copy_state(s))
    assert len(snaps) >= 6, f"电池组态过少({len(snaps)})，重放检查点失败"
    return snaps


# ───────────────── 命门②：λ=0 / future=None → int 0，与原版字节一致 ─────────────────

def test_future_potential_off_path_is_int_zero(roster, battery):
    """future=None 与 λ=0 都必须返回【int 0】（不是 0.0）——off 路径不引入 float、与原版字节一致。"""
    for s in battery:
        for fut in (None, FutureCfg(roster, 0.0)):
            v = _future_potential(s, fut)
            assert v == 0 and type(v) is int, \
                f"区势能 off 路径非 int 0：{v!r}(type={type(v).__name__}, floor={s.current_floor})"


def test_equiv_hp_lam0_byte_identical_to_no_future(roster, battery):
    """equiv_hp_over_roster：λ=0 与 future=None 必须逐态【完全相等】（区势能项=0 不改打分键）。"""
    for s in battery:
        R, big = region_reference([type("P", (), {"state": s})()])
        base = equiv_hp_over_roster(s, R, big, future=None)
        lam0 = equiv_hp_over_roster(s, R, big, future=FutureCfg(roster, 0.0))
        assert base == lam0, \
            f"λ=0 非零回归：base={base!r} lam0={lam0!r}(floor={s.current_floor})"


# ───────────────── 命门①：区势能只读、绝不改 value_vector / 态 ─────────────────

def test_future_potential_does_not_mutate_state_or_value_vector(roster, battery):
    """算区势能（含 λ>0）绝不改 value_vector 或任何 hero 字段（引导项纯只读）。"""
    hero_scalars = ("hp", "atk", "def_", "mdef", "gold", "x", "y", "kill_count")
    for s in battery:
        before_vv = dict(value_vector(s))
        before_scalars = {a: getattr(s.hero, a) for a in hero_scalars}
        before_keys = dict(s.hero.keys)
        before_items = dict(s.hero.items)

        _future_potential(s, FutureCfg(roster, 0.2))
        _future_potential(s, FutureCfg(roster, 0.05))

        assert dict(value_vector(s)) == before_vv, \
            f"区势能改了 value_vector(floor={s.current_floor})"
        assert {a: getattr(s.hero, a) for a in hero_scalars} == before_scalars, "区势能改了 hero 标量"
        assert dict(s.hero.keys) == before_keys, "区势能改了 hero.keys"
        assert dict(s.hero.items) == before_items, "区势能改了 hero.items"


def test_value_vector_unaffected_by_lambda(roster, battery):
    """value_vector 不接收 future 参数 → 结构上不可能被区势能/λ 影响（剪枝界与打分键正交）。"""
    assert value_vector is _value_map           # 剪枝键就是 _value_map 本体（pull/区势能都没接进来）
    for s in battery:
        vv = dict(value_vector(s))
        # value_vector 是 state 的纯函数，与任何 λ 无关——这里复算一次确认稳定、无隐藏 future 入口
        assert dict(value_vector(s)) == vv, f"value_vector 不稳定(floor={s.current_floor})"


# ───────────────── 命门③：区势能=残损惩罚，+atk 只降不升（结构性免疫 κ=1） ─────────────────

def test_future_potential_nonneg_and_monotone_in_atk(roster, battery):
    """区势能契约：恒 ≥ 0；且对【当前存活怪】Σ残损 → +atk 必使它【非增】(残损更小)。
    这是路径B 免疫 κ=1 的结构保证：价值在【拿到属性(atk 真涨)】时才兑现为减分，绝不为
    「够得到但没拿」的宝石预付（κ=1 反向病的根）。"""
    fut = FutureCfg(roster, 0.05)
    for s in battery:
        base = _future_potential(s, fut)
        assert base >= 0, f"区势能出负值 {base}(floor={s.current_floor})"
        bumped = _copy_state(s)
        bumped.hero.atk += 5
        up = _future_potential(bumped, fut)
        assert up <= base + 1e-9, \
            f"+atk 反而抬高区势能(应非增)：base={base} up={up}(floor={s.current_floor})"


# ───────────────── 命门②·最强：λ=0 search 与 future=None 逐字段同结果 ─────────────────

@pytest.mark.slow
def test_search_byte_identical_no_future_vs_lam0(roster):
    """最强命门：在 κ=1/区势能真正作恶的 beam 截断层，beam_future=None 与 FutureCfg(roster,0.0)
       跑 search_quotient 必须逐字段同结果（λ=0 字节零回归）。
       小 cap+小 beam、目标格设楼梯不可达 → 强制穷尽探索撞 cap、覆盖大量截断决策。"""
    cap, beam = 4000, 16
    goal = ("MT0", 1, 1)            # 楼梯不可达 → 纯探索撞 cap，最大化截断决策覆盖

    def run(beam_future):
        start, _ = build_start()
        return search_quotient(start, goal, step, max_states=cap, cross_floor=True,
                               beam_k=beam, beam_future=beam_future)

    off = run(None)
    lam0 = run(FutureCfg(roster, 0.0))

    for f in ("found", "states_expanded", "states_generated", "states_admitted",
              "frontier_peak", "distinct_fingerprints", "goal_hits", "hit_cap"):
        assert getattr(off, f) == getattr(lam0, f), \
            f"λ=0 搜索行为偏离 future=None：{f} off={getattr(off, f)} lam0={getattr(lam0, f)}"
