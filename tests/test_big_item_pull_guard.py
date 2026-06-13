"""守卫单测（命门·结合）：钉死【region 区势能基分 + β_big·pull_大件】的三层分离与 κ=1 免疫。

玩家 2026-06-11 拍板【结合】（不是二选一）：region 兑现侧管小宝石/血、pull_大件 引导侧治剑盾误判。
本测与 test_region_potential_guard（钉区势能 base）/ test_pull_guard（钉 vzone pull）对偶，钉新增的
【可加 extra 钩子 + pull_大件】：

  命门①  extra=None 字节零回归 —— score_points/equiv_hp_over_roster/search_quotient 加 extra 形参后，
          不传(=None)必须与原版逐字节一致（off 路径不引入任何项）。
  命门②  extra 纯加性 + 只读 + 不进剪枝界 —— 传 extra=g 时打分恰好 +g(state)；pull_big/detect_big_items
          绝不改 value_vector / hero；value_vector 仍是纯资源 _value_map 本体（引导项没渗进无损剪枝维）。
  命门③  大件【数据涌现】+ κ=1 结构免疫 —— 大件由 ΔRP 最大乘性缝自动划出（不硬编码"剑盾"/物品 id）；
          拿到大件→pull 对它归 0（离场），同时区势能 base 兑现 λ·ΔRP>0（拿到才兑现，非预付）→ 守着严格
          劣于拿起，结构上不复发 κ=1（小宝石不在大件集、只走兑现侧，更不会被引导悬而不拿）。

电池组=真引擎重放 route token 到多检查点取态（遵铁律：绝不手造态/手算属性）；roster/zone/大件集一次构建复用。
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
                         score_points, equiv_hp_over_roster, region_reference)
from vzone import build_zone, BOSS_FLAG, _zone_attr_gems
from big_item_pull import detect_big_items, pull_big, build_pickup_bonus, pickup_bonus

LAM = 0.2                                   # 甜区 λ（路径B 验证结论），结合基分用它
_SCALAR_KEYS = {"hp", "atk", "def", "mdef", "gold", "kill"}
_ALLOWED_PREFIXES = ("key:", "item:")


def _is_resource_key(k):
    return k in _SCALAR_KEYS or any(k.startswith(p) for p in _ALLOWED_PREFIXES)


def _P(s):
    """score_points/region_reference 的最小点对象（只需 .state）。"""
    return type("P", (), {"state": s})()


@pytest.fixture(scope="module")
def roster():
    start, _ = build_start()
    return build_future_roster(start)


@pytest.fixture(scope="module")
def zone():
    return build_zone()


@pytest.fixture(scope="module")
def big(zone, roster):
    """大件集（数据涌现，一次检测复用）：detect_big_items 找 ΔRP 最大乘性缝。"""
    start, _ = build_start()
    big_cells, tau, ranked = detect_big_items(zone, roster, start)
    return {"cells": big_cells, "tau": tau, "ranked": ranked}


@pytest.fixture(scope="module")
def battery():
    """真引擎重放 route 到多 token 检查点的态电池组（全 engine-true，绝不手造态/手改属性）。"""
    start, nopen = build_start()
    toks = load_tokens()
    ckpts = [82, 120, 160, 220, 300, 400, 520, 680]
    snaps = [_copy_state(start)]
    s = start
    for i in range(nopen, max(ckpts)):
        if i >= len(toks):
            break
        s = step(s, toks[i])
        if (i + 1) in ckpts:
            snaps.append(_copy_state(s))
    assert len(snaps) >= 6, f"电池组态过少({len(snaps)})，重放检查点失败"
    return snaps


# ───────────────── 命门①：extra=None 字节零回归 ─────────────────

def test_score_points_extra_none_byte_identical(roster, battery):
    """score_points(extra=None) 必须与不传 extra 逐态【完全相等】（roster/big/scores 全等）。"""
    pts = [_P(s) for s in battery]
    R0, b0, sc0 = score_points(pts, future=FutureCfg(roster, LAM))
    R1, b1, sc1 = score_points(pts, future=FutureCfg(roster, LAM), extra=None)
    assert b0 == b1 and sc0 == sc1, "score_points extra=None 非零回归"


def test_equiv_hp_extra_none_byte_identical(roster, battery):
    """equiv_hp_over_roster(extra=None) 必须与不传 extra 逐态相等。"""
    for s in battery:
        R, bg = region_reference([_P(s)])
        a = equiv_hp_over_roster(s, R, bg, future=FutureCfg(roster, LAM))
        b = equiv_hp_over_roster(s, R, bg, future=FutureCfg(roster, LAM), extra=None)
        assert a == b, f"equiv_hp extra=None 非零回归(floor={s.current_floor})"


@pytest.mark.slow
def test_search_extra_none_byte_identical(roster):
    """最强命门：region λ 打分路上，beam_score_extra=None 与不传必须跑出逐字段同结果（结合 off=零回归）。
    小 cap+小 beam、目标楼梯不可达→穷尽探索撞 cap、覆盖大量截断决策。"""
    cap, beam = 4000, 16
    goal = ("MT0", 1, 1)

    def run(extra):
        start, _ = build_start()
        return search_quotient(start, goal, step, max_states=cap, cross_floor=True,
                               beam_k=beam, beam_future=FutureCfg(roster, LAM),
                               beam_score_extra=extra)

    off = run(None)
    explicit = run(None)        # 显式传 None 也走 extra is None 分支
    for f in ("found", "states_expanded", "states_generated", "states_admitted",
              "frontier_peak", "distinct_fingerprints", "goal_hits", "hit_cap"):
        assert getattr(off, f) == getattr(explicit, f), \
            f"beam_score_extra=None 偏离不传：{f}"


# ───────────────── 命门②：extra 纯加性 + 只读 + 不进 value_vector ─────────────────

def test_extra_is_strictly_additive_in_score_points(roster, battery):
    """传 extra=g 时每点打分恰好 = 基分 + g(state)（引导项只叠加、不渗进基分）。"""
    pts = [_P(s) for s in battery]
    fut = FutureCfg(roster, LAM)
    _, _, base = score_points(pts, future=fut)
    for g in (lambda st: 100.0, lambda st: float(st.hero.atk) * 7.0):
        _, _, withg = score_points(pts, future=fut, extra=g)
        for p in pts:
            sid = id(p.state)
            assert withg[sid] == pytest.approx(base[sid] + g(p.state)), \
                f"extra 非严格加性(floor={p.state.current_floor})"


def test_extra_is_strictly_additive_in_equiv_hp(roster, battery):
    """equiv_hp_over_roster(extra=g) == 基分 + g(state)。"""
    g = lambda st: 42.0
    for s in battery:
        R, bg = region_reference([_P(s)])
        base = equiv_hp_over_roster(s, R, bg, future=FutureCfg(roster, LAM))
        withg = equiv_hp_over_roster(s, R, bg, future=FutureCfg(roster, LAM), extra=g)
        assert withg == pytest.approx(base + 42.0), f"equiv_hp extra 非加性(floor={s.current_floor})"


def test_pull_big_and_detect_do_not_mutate(zone, roster, big, battery):
    """调 pull_big / detect_big_items 绝不改 value_vector 或任何 hero 字段（引导项纯只读，含临时 bump 后还原）。"""
    hero_scalars = ("hp", "atk", "def_", "mdef", "gold", "x", "y", "kill_count")
    for s in battery:
        before_vv = dict(value_vector(s))
        before_scalars = {a: getattr(s.hero, a) for a in hero_scalars}
        before_keys = dict(s.hero.keys)
        before_items = dict(s.hero.items)

        pull_big(zone, roster, s, big["cells"])
        detect_big_items(zone, roster, s)

        assert dict(value_vector(s)) == before_vv, f"pull_big 改了 value_vector(floor={s.current_floor})"
        assert {a: getattr(s.hero, a) for a in hero_scalars} == before_scalars, \
            f"pull_big 改了 hero 标量(floor={s.current_floor})——临时 bump 未还原？"
        assert dict(s.hero.keys) == before_keys, "pull_big 改了 hero.keys"
        assert dict(s.hero.items) == before_items, "pull_big 改了 hero.items"


def test_value_vector_is_pure_pruning_key(battery):
    """value_vector 仍是 _value_map 本体、只含纯资源键（结构证明 extra/pull_大件 没渗进无损剪枝维）。"""
    assert value_vector is _value_map
    for s in battery:
        leaked = [k for k in value_vector(s) if not _is_resource_key(k)]
        assert not leaked, f"剪枝维泄漏非资源键 {leaked}(floor={s.current_floor})"


# ───────────────── 命门③：大件涌现 + pull 契约 + κ=1 结构免疫 ─────────────────

def test_big_items_emerge_with_clear_cleft(big):
    """大件【从数据涌现】：检出非空；缝上大件 ΔRP 全 ≥ τ ≥ 缝下小宝石 ΔRP；落差 ≥ min_gap（清晰分界）。
    不断言具体是"铁剑/铁盾"（塔无关，只验涌现结构）。"""
    cells, tau, ranked = big["cells"], big["tau"], big["ranked"]
    assert cells, "未涌现任何大件（缝检测失败）"
    drp = {c: v for v, c, _, _ in ranked}
    big_vals = [drp[c] for c in cells]
    small_vals = [v for v, c, _, _ in ranked if c not in cells and v > 0]
    assert min(big_vals) >= tau, "大件 ΔRP 落到 τ 之下"
    if small_vals:
        assert max(small_vals) <= tau, "小宝石 ΔRP 越过 τ"
        assert min(big_vals) / max(small_vals) >= 2.0, "大件/小宝石落差 < 2×（缝不清晰）"


def test_pull_big_nonneg_and_gated(zone, roster, big, battery):
    """pull_大件 契约：恒 ≥ 0；空大件集 / 区外 / 已胜 boss → 严格 0（可达性 + 拾取兑现门控）。"""
    for s in battery:
        pl = pull_big(zone, roster, s, big["cells"])
        assert pl >= 0.0, f"pull_big 出负值 {pl}(floor={s.current_floor})"
        assert pull_big(zone, roster, s, set()) == 0.0, "空大件集 pull_big 非 0"
        out_zone = s.current_floor not in zone["floors"]
        won = bool(s.hero.flags.get(BOSS_FLAG))
        if out_zone or won:
            assert pl == 0.0, f"区外/已胜 boss 仍 pull_big={pl}(floor={s.current_floor})"


def test_acquire_realizes_value_and_pull_vanishes(zone, roster, big, battery):
    """κ=1 结构免疫的命门：对每个【可达·还在地上】的大件，模拟拿起（引擎已知增益 bump + 实体离场）后——
       (a) pull 对它【归 0】（离场，引导梯度消失）；
       (b) 区势能 base 兑现 λ·ΔRP > 0（拿到才兑现，非预付）。
    → 守着 = 放弃 base 兑现跃升、只留 pull 引导分；拿起 = 锁定 base 兑现 + pull 归 0 → 拿起严格优于守着。
    报告 β_crit=兑现/守着引导（β_big < β_crit 时拿起恒胜），供扫 β_big 取在它下方。
    遵铁律：bump 用引擎 _attr_item_delta 算的真增益、离场=真置 0；不手算属性、不喂走法。"""
    gems = _zone_attr_gems(zone)
    fut1 = FutureCfg(roster, 1.0)
    exercised = 0
    crit_min = float("inf")
    for s in battery:
        for cell in big["cells"]:
            gfid, x, y = cell
            fl = s.floors.get(gfid)
            if fl is None or fl.entities[y][x] == 0:
                continue                       # 该态下大件未加载/已拿走 → 无法模拟离场，跳过
            pull_before = pull_big(zone, roster, s, {cell})
            if pull_before <= 0.0:
                continue                       # 够不到 → 非 κ=1 风险（门控已为 0），跳过
            da, dd = gems[cell]
            g = _copy_state(s)                 # 深拷（build_start 起点 _single_floor_copy=False）→ 改 entities 安全
            g.hero.atk += da
            g.hero.def_ += dd
            g.floors[gfid].entities[y][x] = 0  # 引擎拾取：增益入账 + 实体离场
            # (a) 拿起后该大件 pull 归 0（离场）
            assert pull_big(zone, roster, g, {cell}) == 0.0, \
                f"拿起大件后 pull 未归 0（离场失败）：{cell} floor={s.current_floor}"
            # (b) 区势能 base 兑现 λ·ΔRP > 0
            realized = LAM * (_future_potential(s, fut1) - _future_potential(g, fut1))
            assert realized > 0.0, \
                f"拿起大件区势能未兑现（base 没跃升）：{cell} realized={realized} floor={s.current_floor}"
            beta_crit = realized / pull_before
            crit_min = min(crit_min, beta_crit)
            exercised += 1
    assert exercised >= 1, "命门③未覆盖任何可达大件态（电池组/检测口径漂移？）"
    print(f"\n[命门③] 覆盖 {exercised} 个可达大件态；min β_crit={crit_min:.2f}"
          f"（β_big < {crit_min:.2f} 时拿起恒严格优于守着→不复发 κ=1）")


# ───────────────── 命门④：满额兑现拿取奖励 G（build_pickup_bonus / pickup_bonus）─────────────────
# 玩家 2026-06-11 拍板【满额兑现】治就近病：拿走时补 G=β·ΔRP₀(满额) ≥ 在场守着引导 β·ΔRP/(1+dist)(折扣)，
# 结构性保证拿走≥守着、不靠调参。小宝石只给拿取奖励(无在场 pull)→无平台、无就近病风险。
# 本组钉死：①β=0→G≡0 字节零回归；②G 纯只读不进 value_vector；③拿到才兑现(κ=1 免疫)；④满额≥守着(结构性)。

def test_pickup_bonus_zero_beta_is_empty(big, battery):
    """命门④-①（字节零回归）：β_big=β_small=0 → 拿取奖励表为空 → pickup_bonus 恒 0（G 关时绝不引入任何项）。"""
    cells, ranked = big["cells"], big["ranked"]
    assert build_pickup_bonus(ranked, cells, 0.0, 0.0) == {}, "β_big=β_small=0 拿取奖励表非空（破坏字节零回归）"
    for s in battery:
        assert pickup_bonus(s, {}) == 0.0, f"空表 pickup_bonus 非 0(floor={s.current_floor})"
        assert pickup_bonus(s, build_pickup_bonus(ranked, cells, 0.0, 0.0)) == 0.0, "β=0 拿取奖励非 0"


def test_build_pickup_bonus_uses_ref_drp_constants(big):
    """命门④（数据涌现·满额常数）：表值恰为 β·ΔRP₀(detect_big_items 参照态固定常数)；大件用 β_big、小宝石用 β_small；
    ΔRP₀≤0 不入表。证 G 用涌现常数、不硬编码，且大/小是【两个独立旋钮】。"""
    cells, ranked = big["cells"], big["ranked"]
    drp0 = {c: v for v, c, _, _ in ranked}
    bb, bs = 25.0, 3.0
    table = build_pickup_bonus(ranked, cells, bb, bs)
    for v, cell, da, dd in ranked:
        if v <= 0:
            assert cell not in table, f"ΔRP₀≤0 的格不该入表：{cell}"
            continue
        beta = bb if cell in cells else bs
        assert table[cell] == pytest.approx(beta * drp0[cell]), f"拿取奖励 ≠ β·ΔRP₀：{cell}"
    # 独立旋钮：只开 β_big → 表里只有大件；只开 β_small → 表里没有大件
    only_big = build_pickup_bonus(ranked, cells, bb, 0.0)
    assert set(only_big) <= cells, "β_small=0 时小宝石不该入表"
    only_small = build_pickup_bonus(ranked, cells, 0.0, bs)
    assert not (set(only_small) & cells), "β_big=0 时大件不该入表"


def test_pickup_bonus_only_counts_taken(big, battery):
    """命门④-③（拿到才兑现）：pickup_bonus 恰为 Σ_{表内·已拿走(entities==0)} 表值（未加载/在场格一律不计）。"""
    cells, ranked = big["cells"], big["ranked"]
    table = build_pickup_bonus(ranked, cells, 25.0, 3.0)
    for s in battery:
        expect = 0.0
        for cell, bonus in table.items():
            gfid, x, y = cell
            fl = s.floors.get(gfid)
            if fl is not None and fl.entities[y][x] == 0:
                expect += bonus
        assert pickup_bonus(s, table) == pytest.approx(expect), \
            f"pickup_bonus ≠ Σ已拿走(floor={s.current_floor})"


def test_pickup_bonus_realized_only_on_take(zone, big, battery):
    """命门④-③（κ=1 免疫·拿起才翻开）：对每个【在场】表内格，模拟拿起（实体离场）后 pickup_bonus 恰好 +表值；
    在场时该格贡献 0（没拿不给）→ 天然不犯 κ=1（不会悬而不拿被奖励）。遵铁律：离场=真置 entities 0、不手算。"""
    cells, ranked = big["cells"], big["ranked"]
    table = build_pickup_bonus(ranked, cells, 25.0, 3.0)
    exercised = 0
    for s in battery:
        for cell in table:
            gfid, x, y = cell
            fl = s.floors.get(gfid)
            if fl is None or fl.entities[y][x] == 0:
                continue                            # 未加载/已拿走 → 无法模拟离场，跳过
            before = pickup_bonus(s, table)
            g = _copy_state(s)
            g.floors[gfid].entities[y][x] = 0       # 引擎拾取：实体离场
            after = pickup_bonus(g, table)
            assert after == pytest.approx(before + table[cell]), \
                f"拿起才兑现失败：{cell} 应 +{table[cell]:.0f}(floor={s.current_floor})"
            exercised += 1
    assert exercised >= 1, "命门④-③未覆盖任何可拿取格（电池组/检测口径漂移？）"


def test_pickup_bonus_does_not_mutate(zone, big, battery):
    """命门④-②（纯只读·不进剪枝维）：调 build_pickup_bonus / pickup_bonus 绝不改 value_vector 或 hero 任何字段。"""
    table = build_pickup_bonus(big["ranked"], big["cells"], 25.0, 3.0)
    hero_scalars = ("hp", "atk", "def_", "mdef", "gold", "x", "y", "kill_count")
    for s in battery:
        before_vv = dict(value_vector(s))
        before_scalars = {a: getattr(s.hero, a) for a in hero_scalars}
        pickup_bonus(s, table)
        assert dict(value_vector(s)) == before_vv, f"pickup_bonus 改了 value_vector(floor={s.current_floor})"
        assert {a: getattr(s.hero, a) for a in hero_scalars} == before_scalars, \
            f"pickup_bonus 改了 hero 标量(floor={s.current_floor})"


def test_full_realization_dominates_guarding_pull(zone, roster, big, battery):
    """命门④-④（满额兑现【结构性】压过守着，直对玩家口径 满额β·ΔRP₀ ≥ 守着β·ΔRP/(1+dist)）：
    对每个【在场·够得到】大件，拿取奖励 table[cell]=β·ΔRP₀ ≥ 守着引导 β·pull_big({cell})=β·ΔRP(当前)/(1+dist)。
    ΔRP₀(参照态最弱)是当前 ΔRP 的上界 → 不等式【结构成立·非阈值】→ 拿走(满额)恒压守着(折扣)，再叠区势能兑现 λ·ΔRP>0
    → 拿走严格优于守着、对【任意 β】成立(无 β 上限)→ 治就近病。比值 β 无关(两侧同乘 β)，用 β=1 直比。报告 min(满额/守着)。"""
    beta = 1.0
    table = build_pickup_bonus(big["ranked"], big["cells"], beta, 0.0)
    exercised = 0
    min_ratio = float("inf")
    for s in battery:
        for cell in big["cells"]:
            gfid, x, y = cell
            fl = s.floors.get(gfid)
            if fl is None or fl.entities[y][x] == 0:
                continue
            guard = beta * pull_big(zone, roster, s, {cell})   # β·ΔRP(当前)/(1+dist)（守着折扣引导）
            if guard <= 0.0:
                continue                                       # 够不到 → 门控 0、无就近病风险
            take = table[cell]                                 # β·ΔRP₀（满额拿取）
            assert take >= guard - 1e-6, \
                f"满额兑现未压过守着：{cell} 满额={take:.0f} < 守着={guard:.0f}(floor={s.current_floor})"
            min_ratio = min(min_ratio, take / guard)
            exercised += 1
    assert exercised >= 1, "命门④-④未覆盖任何在场够得到的大件态（电池组/检测口径漂移？）"
    print(f"\n[满额兑现] 覆盖 {exercised} 态；min(满额 β·ΔRP₀ / 守着 β·ΔRP/(1+dist))={min_ratio:.2f}"
          f"（≥1 → 拿走结构性压过守着、任意 β 无上限、治就近病）")


# ───────────────── 命门⑤：共享 α 衰减旋钮（α=1 字节零回归 + 满额对任意 α 仍是上界）─────────────────
# 玩家 2026-06-12：pull_大件/door_pull 距离衰减 /(1+dist) → /(1+dist)^α（共享旋钮，治剑盾长途被(1+dist)压扁/MT8门后谷）。
# 钉死：①α=1 字节回滚零回归（_decay 显式 α==1.0 分支，不依赖浮点 pow(x,1.0)==x）；②满额 G=β·ΔRP₀ 对【任意 α∈(0,1]】
# 仍 ≥ 守着引导 β·ΔRP/(1+dist)^α（结构性·不破红线）——α 只调引导陡峭度，绝不让守着反超拿走。

def test_pull_big_alpha1_byte_identical_to_default(zone, roster, big, battery):
    """共享 α 字节零回归：pull_big(alpha=1.0) 必逐态【字节】== 不传 alpha（默认）。
    _decay 用显式 α==1.0 分支走原 (1+dist) 路径 → 不依赖跨平台不保证的 pow(x,1.0)==x。"""
    for s in battery:
        d = pull_big(zone, roster, s, big["cells"])
        a1 = pull_big(zone, roster, s, big["cells"], 1.0)
        assert a1 == d, f"pull_big(α=1) 非字节零回归：default={d!r} α1={a1!r}(floor={s.current_floor})"


def test_full_realization_dominates_guard_any_alpha(zone, roster, big, battery):
    """满额兑现【对任意 α】仍压过守着（共享 α 红线·结构性）：对每个【在场·够得到】大件、每个
    α∈{1,0.7,0.5,0.3}，满额 take=β·ΔRP₀ ≥ 守着 guard=β·pull_big(α)=β·ΔRP/(1+dist)^α。
    机理：(1+dist)^α≥1（dist≥0,α≥0）且 ΔRP₀≥ΔRP(当前) ⇒ take/guard=(ΔRP₀/ΔRP)·(1+dist)^α≥1，与 α 无关地成立。
    α<1 衰减更弱→守着引导更高→对不等式更严苛，仍须成立。报告每个 α 的 min(满额/守着)。"""
    beta = 1.0
    table = build_pickup_bonus(big["ranked"], big["cells"], beta, 0.0)
    worst = {}
    exercised = 0
    for alpha in (1.0, 0.7, 0.5, 0.3):
        min_ratio = float("inf")
        for s in battery:
            for cell in big["cells"]:
                gfid, x, y = cell
                fl = s.floors.get(gfid)
                if fl is None or fl.entities[y][x] == 0:
                    continue
                guard = beta * pull_big(zone, roster, s, {cell}, alpha)
                if guard <= 0.0:
                    continue
                take = table[cell]
                assert take >= guard - 1e-6, \
                    f"α={alpha}：满额 {take:.0f} < 守着 {guard:.0f}（{cell} floor={s.current_floor}）"
                min_ratio = min(min_ratio, take / guard)
                exercised += 1
        worst[alpha] = min_ratio
    assert exercised >= 1, "未覆盖任何在场够得到的大件态（电池组/检测口径漂移？）"
    print("\n[共享α·满额≥守着] min(满额/守着) by α：  " +
          "  ".join(f"α={a}:{worst[a]:.2f}" for a in (1.0, 0.7, 0.5, 0.3)))
