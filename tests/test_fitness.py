"""【solver/fitness · GA 终局适应度 单元验证】

钉死 fitness 的契约与口径（见 solver/fitness 模块头 / ga_design 钉死点 3）：
  · 死亡态 ≪ 任何活态，且【更深的死】> 更浅的死（给 GA 爬坡梯度）。
  · 通关 → 恒加 win_bonus。
  · 主干 = equiv_hp_over_roster（Δ 形、kill 中性）。
  · 血瓶项 = w_potion · 一区地上剩余血瓶名义回血（线性可加）。
  · 钥匙家底 = w_key·手里余钥匙(已兑现满权重) + Σ_地上够得到钥匙 max(0, w_key−守怪损血)。
    可达=预算门控（终态手里有该色钥匙的门才可过）→ 防 κ=1 裸计数；扣守怪血成本→「13 血净赚」经济学。
  · 标尺对照：cap480k 718(耗尽) vs 689(高潜力)，标定权重(w_potion=1.5,w_key=39)下 689 反超 718，
    且反超来自【血瓶 + 钥匙两个真潜力项】（689 地上多 250 血瓶 + 多 3 把 MT4 便宜黄门钥匙）。

电池组 engine-true：make_initial_state + step 回放两条真 route（与 tests/test_ga_navigate 同源）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import json
import pytest

from sim.simulator import step
from decode_route import parse_rle_route, decompress
from export_mt10_boss_route import make_initial_state
from solver.fitness import (
    DEATH_FLOOR, build_zone1_roster, calibrate_big, fitness, fitness_breakdown,
    zone_remaining_potions, zone_ground_key_costs, zone_key_potential,
    hero_key_count,
)

W_POTION, W_KEY = 1.5, 39      # 标定值（analysis/calibrate_fitness.py 双权重稳健区间中值）
WIN_BONUS = 100000

R718 = ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"
R689 = ROOT / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route"


def _replay(route_file):
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    for a in actions:
        s = step(s, a)
        if s.dead:
            break
    return s


@pytest.fixture(scope="module")
def cal():
    """固定参照（roster/big/zone_fids）+ 两条标尺 route 终态，回放各一次。"""
    s718 = _replay(R718)
    s689 = _replay(R689)
    roster, zone_fids, _all = build_zone1_roster(s718)
    start = make_initial_state()
    big = calibrate_big([s718, s689, start], roster)
    return {"s718": s718, "s689": s689, "roster": roster,
            "zone_fids": zone_fids, "big": big}


class _DeadStub:
    """死亡态最小桩：fitness 死亡分支只读 dead/current_floor/floor_ids（roster/big/zone_fids 不进算）。"""
    dead = True
    won = False

    def __init__(self, current_floor, floor_ids):
        self.current_floor = current_floor
        self.floor_ids = floor_ids


def _fit(s, cal, **kw):
    kw.setdefault("w_potion", W_POTION)
    kw.setdefault("w_key", W_KEY)
    return fitness(s, cal["roster"], cal["big"], cal["zone_fids"], **kw)


# ── 契约 1：死亡态恒 ≪ 活态，且更深的死 > 更浅的死 ──────────────────────────────
def test_dead_far_below_any_live(cal):
    floor_ids = cal["s718"].floor_ids
    dead = _DeadStub(floor_ids[0], floor_ids)
    f_dead = fitness(dead, cal["roster"], cal["big"], cal["zone_fids"],
                     w_potion=W_POTION, w_key=W_KEY)
    assert f_dead <= DEATH_FLOOR + len(floor_ids)
    assert f_dead < _fit(cal["s718"], cal)
    assert f_dead < _fit(cal["s689"], cal)


def test_dead_depth_gradient(cal):
    floor_ids = cal["s718"].floor_ids
    shallow = _DeadStub(floor_ids[1], floor_ids)
    deep = _DeadStub(floor_ids[5], floor_ids)
    f_shallow = fitness(shallow, cal["roster"], cal["big"], cal["zone_fids"])
    f_deep = fitness(deep, cal["roster"], cal["big"], cal["zone_fids"])
    assert f_deep > f_shallow                      # 死得更深 → fitness 更高（爬坡梯度）
    assert f_deep < DEATH_FLOOR + len(floor_ids)   # 但仍远低于任何活态


# ── 契约 2：通关恒加 win_bonus ────────────────────────────────────────────────
def test_win_bonus_added(cal):
    s = cal["s718"]
    assert not s.won
    base = _fit(s, cal)
    s.won = True
    try:
        won = _fit(s, cal)
    finally:
        s.won = False
    assert won - base == pytest.approx(WIN_BONUS)


# ── 契约 3：标定权重下 689 反超 718（指南针指向对）─────────────────────────────
def test_calibrated_689_beats_718(cal):
    f718 = _fit(cal["s718"], cal)
    f689 = _fit(cal["s689"], cal)
    assert f689 > f718


def test_689_reversal_from_both_potentials(cal):
    """反超必须来自【血瓶 + 钥匙两个真潜力项】，缺一不可：
    主干 689 输（Δ<0）；血瓶项 689 赢；钥匙地上项 689 赢。"""
    bd718 = fitness_breakdown(cal["s718"], cal["roster"], cal["big"], cal["zone_fids"],
                              w_potion=W_POTION, w_key=W_KEY)
    bd689 = fitness_breakdown(cal["s689"], cal["roster"], cal["big"], cal["zone_fids"],
                              w_potion=W_POTION, w_key=W_KEY)
    assert bd689["main_equiv_hp"] < bd718["main_equiv_hp"]   # 主干 689 输（更瘦）
    assert bd689["potion_term"] > bd718["potion_term"]       # 血瓶潜力 689 赢
    assert bd689["key_ground"] > bd718["key_ground"]         # 地上钥匙潜力 689 赢
    # 两潜力之和必须翻过主干赤字
    main_deficit = bd718["main_equiv_hp"] - bd689["main_equiv_hp"]
    pot_gain = bd689["potion_term"] - bd718["potion_term"]
    key_gain = bd689["key_ground"] - bd718["key_ground"]
    assert pot_gain + key_gain > main_deficit


# ── 口径 4：血瓶项线性可加（fitness 对 w_potion 的斜率 == 地上血瓶 raw）──────────
def test_potion_term_linear(cal):
    s = cal["s718"]
    raw = zone_remaining_potions(s, cal["zone_fids"])
    assert raw > 0
    f1 = _fit(s, cal, w_potion=1.0)
    f2 = _fit(s, cal, w_potion=2.0)
    assert f2 - f1 == pytest.approx(raw)            # 斜率正好 = 地上血瓶名义回血


# ── 口径 5：钥匙家底 = 手里满权重 + 地上 Σmax(0,w_key−守怪损血)（恒等分解）──────
def test_key_potential_decomposition(cal):
    s = cal["s689"]
    wk = W_KEY
    realized = wk * hero_key_count(s)
    ground = sum(max(0.0, wk - c) for c in zone_ground_key_costs(s, cal["zone_fids"]).values())
    assert zone_key_potential(s, cal["zone_fids"], wk) == pytest.approx(realized + ground)


def test_cheap_key_counts_expensive_drops(cal):
    """便宜守怪钥匙(cost≈13)净赚、贵守怪钥匙(cost≥w_key)归 0（防 κ=1 裸计数）。"""
    costs = zone_ground_key_costs(cal["s689"], cal["zone_fids"])
    assert costs                                     # 689 地上确有够得到的钥匙
    cheap = [c for c in costs.values() if c <= 20]
    expensive = [c for c in costs.values() if c >= W_KEY]
    assert cheap and expensive                       # 两档都存在
    assert all(max(0.0, W_KEY - c) > 0 for c in cheap)        # 便宜 → 正贡献
    assert all(max(0.0, W_KEY - c) == 0 for c in expensive)   # 贵 → 0 贡献


# ── 口径 6：钥匙可达=预算门控（手里没该色钥匙 → 门后钥匙够不到 → κ=1 安全）──────
def test_key_budget_gating(cal):
    """718 手里有黄钥 → 能走过黄门拿到 MT7 便宜钥匙；清空手里钥匙 → 黄门当墙 → 严格更少够得到钥匙。
    证明【可达绑定终态手里预算】=既成事实(type-A)，不奖励「不拿钥匙」。"""
    s = cal["s718"]
    with_keys = zone_ground_key_costs(s, cal["zone_fids"])
    saved = dict(s.hero.keys)
    s.hero.keys = {}                                 # 手里无任何钥匙 → 所有钥匙门当墙
    try:
        no_keys = zone_ground_key_costs(s, cal["zone_fids"])
    finally:
        s.hero.keys = saved
    assert len(no_keys) < len(with_keys)             # 没钥匙 → 够得到的钥匙严格变少
    # 具体：MT7 黄门后的钥匙在「有钥匙」时够得到、「无钥匙」时够不到
    mt7_keys = {k for k in with_keys if k[0] == "MT7"}
    assert mt7_keys and not (mt7_keys & set(no_keys))


# ── 口径 7：fitness total == breakdown 各项之和（标量与对账一致）────────────────
def test_breakdown_sums_to_fitness(cal):
    for tag in ("s718", "s689"):
        s = cal[tag]
        bd = fitness_breakdown(s, cal["roster"], cal["big"], cal["zone_fids"],
                               w_potion=W_POTION, w_key=W_KEY)
        f = _fit(s, cal)
        assert bd["total"] == pytest.approx(f)
        assert bd["main_equiv_hp"] + bd["potion_term"] + bd["key_term"] + bd["win"] \
            == pytest.approx(f)
