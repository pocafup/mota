"""守卫单测（命门·钥匙价值）：钉死【门锚定·全臂梯度 door_pull】的六条 κ=1 结构红线。

玩家 2026-06-12 拍板【选项1·门锚定全臂梯度】落地钥匙价值（病根 idea3 §B：开门花钥匙、门后价值不进排序键）。
door_pull 只进 beam_score_extra 排序键、绝不进 D/value_vector；信用锚在【开门动作 + pocket 未吸价值】、
绝不锚在【持有钥匙】（=被否的选项2 的 κ=1 直病）。本测与 test_big_item_pull_guard（钉 pull_大件 / G）对偶：

  命门①  γ=0 字节零回归 —— door_pull(γ=0) 与 空表 必恒 ==0.0（off 路径不引入任何项，与 β_big/β_small 路同口径）。
  命门②  纯只读 + 不进 value_vector —— build_door_reward / door_pull 绝不改 value_vector / hero / 地图实体；
          value_vector 仍是 _value_map 本体、只含纯资源键（引导项没渗进无损剪枝维）。
  命门③  R(门)【数据涌现·塔无关·无双计】—— 门/钥匙/boss 由 _zone_key_geometry(DOOR_KEY_MAP)/BOSS 门禁读出、
          不硬编码；R = Σ门后小宝石 ΔRP₀ + 血瓶 HP (+win)，排怪 toll(已在 D)、排大件(pull_大件已引导)；
          同一格/宝石绝不落进两扇门 pocket（无二重计上）。
  命门④  吸收→引导消失 + 开门≠掉分（κ=1 免疫核心）—— 把门后 pocket 价值吸光 → door_pull 对该门归 0
          （不会永远守着没开/已空的门拿分）；仅【开门】(不吸收) → door_pull 不归 0（无"开门即掉分"崖、平滑接管）。
  命门⑤  持有钥匙【本身】零加分 —— 钥匙只经 penalty 归 0 帮【够得到有价值的门】；手里多攥一把（已有该色后再加）
          door_pull【一字不变】→ 没有"每持一把钥匙 +c"项（=与被否选项2 的本质区别、不囤钥匙）。
  命门⑥  门 gating 通关→win 量级 R（塔无关 BOSS 检测）—— include_win 时【pocket 含 boss 格】的门(且仅这些)
          领 win=_region_pot(整区待克势能)；win 由 boss 格几何归属判定(非硬编码红门)；已胜 boss → door_pull 归 0。

电池组=真引擎重放 route token 到多检查点取态（遵铁律：绝不手造态/手算属性）；ref 起点/roster/zone 一次构建复用。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest

from probe_crossfloor import build_start
from seg_experiment import load_tokens
from sim.simulator import step, _copy_state, DOOR_KEY_MAP, _load_floor_if_needed
from solver.search import _value_map
from solver.quotient import value_vector
from solver.beam import build_future_roster, FutureCfg
from vzone import (build_zone, BOSS_FLAG, BOSS_FLOOR, BOSS_CELL,
                   _zone_attr_gems, _zone_key_geometry)
from big_item_pull import detect_big_items, _region_pot
from door_value import build_door_reward, door_pull, _zone_blood

_SCALAR_KEYS = {"hp", "atk", "def", "mdef", "gold", "kill"}
_ALLOWED_PREFIXES = ("key:", "item:")
_BOSS_NODE = (BOSS_FLOOR, *BOSS_CELL)


def _is_resource_key(k):
    return k in _SCALAR_KEYS or any(k.startswith(p) for p in _ALLOWED_PREFIXES)


@pytest.fixture(scope="module")
def ref_state():
    start, _ = build_start()
    return start


@pytest.fixture(scope="module")
def roster(ref_state):
    return build_future_roster(ref_state)


@pytest.fixture(scope="module")
def zone():
    return build_zone()


@pytest.fixture(scope="module")
def big(zone, roster, ref_state):
    big_cells, tau, ranked = detect_big_items(zone, roster, ref_state)
    return {"cells": big_cells, "tau": tau, "ranked": ranked}


@pytest.fixture(scope="module")
def reward(zone, roster, big, ref_state):
    """阶段1·短臂门后奖励表（include_win=False，纯宝石/血 pocket）。"""
    return build_door_reward(zone, roster, ref_state, big["cells"], big["ranked"], include_win=False)


@pytest.fixture(scope="module")
def reward_win(zone, roster, big, ref_state):
    """阶段2·长臂门后奖励表（include_win=True，含红钥过 boss 的 win 巨值）。"""
    return build_door_reward(zone, roster, ref_state, big["cells"], big["ranked"], include_win=True)


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


# ───────────────── 命门①：γ=0 字节零回归 ─────────────────

def test_gamma_zero_is_byte_zero(zone, reward, battery):
    """door_pull(γ=0) 必恒 ==0.0（不是 approx，是字节 0）→ 与 β_big/β_small 路一致的零回归基线。"""
    for s in battery:
        assert door_pull(zone, s, reward, 0.0) == 0.0, \
            f"γ=0 door_pull 非 0(floor={s.current_floor})"


def test_empty_reward_is_zero(zone, battery):
    """空门后奖励表 → door_pull 恒 0（γ 任意）：没有门后价值就没有引导。"""
    for s in battery:
        assert door_pull(zone, s, {}, 0.1) == 0.0, f"空表 door_pull 非 0(floor={s.current_floor})"
        assert door_pull(zone, s, {}, 99.0) == 0.0, "空表大 γ 仍非 0"


# ───────────────── 命门②：纯只读 + 不进 value_vector ─────────────────

def test_build_and_pull_do_not_mutate(zone, roster, big, ref_state, reward, battery):
    """build_door_reward / door_pull 绝不改 value_vector / hero(标量·钥匙·道具) / 地图实体/地形/flags（纯只读）。"""
    hero_scalars = ("hp", "atk", "def_", "mdef", "gold", "x", "y", "kill_count")
    for s in battery:
        before_vv = dict(value_vector(s))
        before_scalars = {a: getattr(s.hero, a) for a in hero_scalars}
        before_keys = dict(s.hero.keys)
        before_items = dict(s.hero.items)
        before_flags = dict(s.hero.flags)
        # 实体/地形快照（任意层的展平拷贝，证 door_pull/build 不改地图）
        before_ent = {fid: [row[:] for row in fl.entities] for fid, fl in s.floors.items()}
        before_ter = {fid: [row[:] for row in fl.terrain] for fid, fl in s.floors.items()}

        build_door_reward(zone, roster, ref_state, big["cells"], big["ranked"], include_win=True)
        door_pull(zone, s, reward, 0.1)

        assert dict(value_vector(s)) == before_vv, f"改了 value_vector(floor={s.current_floor})"
        assert {a: getattr(s.hero, a) for a in hero_scalars} == before_scalars, "改了 hero 标量"
        assert dict(s.hero.keys) == before_keys, "改了 hero.keys"
        assert dict(s.hero.items) == before_items, "改了 hero.items"
        assert dict(s.hero.flags) == before_flags, "改了 hero.flags"
        for fid, fl in s.floors.items():
            assert [row[:] for row in fl.entities] == before_ent[fid], f"改了 {fid} entities"
            assert [row[:] for row in fl.terrain] == before_ter[fid], f"改了 {fid} terrain"


def test_value_vector_is_pure_pruning_key(battery):
    """value_vector 仍是 _value_map 本体、只含纯资源键（结构证明 door_pull 没渗进无损剪枝维）。"""
    assert value_vector is _value_map
    for s in battery:
        leaked = [k for k in value_vector(s) if not _is_resource_key(k)]
        assert not leaked, f"剪枝维泄漏非资源键 {leaked}(floor={s.current_floor})"


# ───────────────── 命门③：R(门) 数据涌现·塔无关·无双计·排怪排大件 ─────────────────

def test_reward_tower_agnostic_and_consistent(zone, big, reward_win):
    """R(门) 塔无关 + 自洽：每扇门 ∈ _zone_key_geometry(DOOR_KEY_MAP) 读出的门集、color 与之一致(非硬编码红门)；
    R 恰 = Σ宝石 ΔRP₀ + Σ血瓶 HP + win（无任何怪 toll 项）；宝石 ΔRP₀ 取自同一份 ranked(单一事实源)。"""
    geom = _zone_key_geometry(zone)
    drp0 = {c: v for v, c, _, _ in big["ranked"]}
    for dcell, info in reward_win.items():
        assert dcell in geom["door_color"], f"门 {dcell} 不在 geom 门集(凭空造门？)"
        assert info["color"] == geom["door_color"][dcell], f"门 {dcell} color 与 geom 不符(硬编码？)"
        assert info["color"] in set(DOOR_KEY_MAP.values()), f"门色 {info['color']} 非合法钥匙色"
        for cell, v in info["gems"]:
            assert v == pytest.approx(drp0[cell]), f"门后宝石 ΔRP₀ 非取自 ranked：{cell}"
        recomputed = sum(v for _, v in info["gems"]) + sum(v for _, v in info["blood"]) + info["win"]
        assert info["R"] == pytest.approx(recomputed), f"R 含额外项(怪 toll 漏进?)：门 {dcell}"


def test_reward_excludes_big_cells(big, reward_win):
    """排大件：任何门后 gems 列表都不含 big_cells（大件由 pull_大件 引导，door_pull 排除防双引导）。"""
    for dcell, info in reward_win.items():
        bigin = [c for c, _ in info["gems"] if c in big["cells"]]
        assert not bigin, f"门 {dcell} 的 pocket 混入大件 {bigin}（应排除）"


def test_no_double_count_across_doors(reward_win):
    """无二重计上（强不变式）：同一 pocket 格 / 宝石 / 血瓶绝不同时落进两扇门——证紧邻∩gated 干净切分。"""
    cell_owner = {}
    gem_owner = {}
    blood_owner = {}
    for dcell, info in reward_win.items():
        for c in info["pocket"]:
            assert c not in cell_owner, f"pocket 格 {c} 被两扇门共有：{cell_owner.get(c)} & {dcell}"
            cell_owner[c] = dcell
        for c, _ in info["gems"]:
            assert c not in gem_owner, f"宝石 {c} 双计：{gem_owner.get(c)} & {dcell}"
            gem_owner[c] = dcell
        for c, _ in info["blood"]:
            assert c not in blood_owner, f"血瓶 {c} 双计：{blood_owner.get(c)} & {dcell}"
            blood_owner[c] = dcell


# ───────────────── 命门④：吸收→引导消失 + 开门≠掉分（κ=1 免疫核心）─────────────────

def test_absorbing_pocket_kills_pull(zone, reward, battery):
    """κ=1 免疫(a)：把某门后 pocket 价值【全吸光】(宝石/血实体离场)后 → door_pull 对该门归 0。
    → 不会永远守着【已空】的门拿引导分（拿到才兑现的对偶；锚在 pocket 未吸、吸完即消失）。
    遵铁律：离场=真置 entities 0、不手算。"""
    exercised = 0
    for s in battery:
        if s.current_floor not in zone["floors"] or s.hero.flags.get(BOSS_FLAG):
            continue
        for dcell, info in reward.items():
            one = {dcell: info}
            if door_pull(zone, s, one, 0.1) <= 0.0:
                continue                                # 够不到/已空 → 非 κ=1 风险，跳过
            g = _copy_state(s)
            for cell, _ in info["gems"] + info["blood"]:
                gfid, x, y = cell
                _load_floor_if_needed(g, gfid)          # 惰性加载：未访层先加载初始态，才能真置实体 0
                if gfid in g.floors:
                    g.floors[gfid].entities[y][x] = 0   # 引擎拾取：实体离场
            assert door_pull(zone, g, one, 0.1) == 0.0, \
                f"吸光 pocket 后 door_pull 未归 0：门 {dcell}(floor={s.current_floor})"
            exercised += 1
    assert exercised >= 1, "命门④(a)未覆盖任何够得到的门（电池组/口径漂移？）"


def test_opening_door_does_not_collapse_pull(zone, reward, battery):
    """κ=1 免疫(b)：仅【开门】(门 tile→0、不吸 pocket) → door_pull 不归 0（pocket 仍未吸）。
    → 无"开门即掉分"崖（病机正相反：开门不抬分却花钥匙），开门后引导平滑接管直到吸收。"""
    exercised = 0
    for s in battery:
        if s.current_floor not in zone["floors"] or s.hero.flags.get(BOSS_FLAG):
            continue
        for dcell, info in reward.items():
            one = {dcell: info}
            before = door_pull(zone, s, one, 0.1)
            if before <= 0.0:
                continue
            dfid, dx, dy = dcell
            g = _copy_state(s)
            if dfid not in g.floors:
                continue
            g.floors[dfid].terrain[dy][dx] = 0          # 引擎开门：门 tile→floor(不吸 pocket)
            after = door_pull(zone, g, one, 0.1)
            assert after > 0.0, f"仅开门 door_pull 崩到 0（开门即掉分崖）：门 {dcell}(floor={s.current_floor})"
            exercised += 1
    assert exercised >= 1, "命门④(b)未覆盖任何够得到的门（电池组/口径漂移？）"


# ───────────────── 命门⑤：持有钥匙本身零加分（锚门不锚钥匙）─────────────────

def test_holding_more_keys_adds_no_bonus(zone, reward, battery):
    """κ=1 直病免疫：钥匙只经 penalty 归 0 帮【够得到有价值的门】；【已持有该色后再多攥】door_pull 一字不变。
    构造：充裕态(各色钥匙=1，penalty 已全归 0) vs 巨量态(各色=1000) → door_pull 必【完全相等】
    → 没有"每持一把 +c"项（与被否的选项2『奖励持有钥匙』本质不同，不诱导囤钥匙）。"""
    colors = sorted(set(DOOR_KEY_MAP.values()))
    exercised = 0
    for s in battery:
        if s.current_floor not in zone["floors"] or s.hero.flags.get(BOSS_FLAG):
            continue
        g1 = _copy_state(s)
        g2 = _copy_state(s)
        for c in colors:
            g1.hero.keys[c] = 1
            g2.hero.keys[c] = 1000
        v1 = door_pull(zone, g1, reward, 0.1)
        v2 = door_pull(zone, g2, reward, 0.1)
        assert v1 == pytest.approx(v2), \
            f"多攥钥匙改变 door_pull(={v1}→{v2})＝犯选项2 囤钥匙 κ=1(floor={s.current_floor})"
        if v1 > 0.0:
            exercised += 1
    assert exercised >= 1, "命门⑤未覆盖任何 door_pull>0 的态（电池组/口径漂移？）"


def test_key_only_helps_via_penalty_monotone(zone, reward, battery):
    """钥匙是【工具性】非【奖励性】：手里有全套钥匙(penalty 可归 0) 的 door_pull ≥ 一把没有(penalty 全顶格) 的——
    钥匙只会经『减 penalty=帮够到门后价值』单调抬分，绝不反向；证它的价值【经能开的门兑现】、不是凭空持有。"""
    colors = sorted(set(DOOR_KEY_MAP.values()))
    exercised = 0
    for s in battery:
        if s.current_floor not in zone["floors"] or s.hero.flags.get(BOSS_FLAG):
            continue
        g_full = _copy_state(s)
        g_none = _copy_state(s)
        for c in colors:
            g_full.hero.keys[c] = 1000
            g_none.hero.keys[c] = 0
        v_full = door_pull(zone, g_full, reward, 0.1)
        v_none = door_pull(zone, g_none, reward, 0.1)
        assert v_full >= v_none - 1e-9, \
            f"有钥匙反而 door_pull 更低(={v_full}<{v_none})＝penalty 方向反了(floor={s.current_floor})"
        if v_full > v_none:
            exercised += 1
    assert exercised >= 1, "命门⑤(单调)未覆盖任何钥匙影响 door_pull 的态（口径漂移？）"


# ───────────────── 命门⑥：门 gating 通关 → win 量级 R（塔无关 BOSS 检测）─────────────────

def test_win_gated_by_boss_cell_geometry(zone, roster, ref_state, reward, reward_win):
    """include_win 时：win>0 的门【当且仅当】其 pocket 含 boss 格(BOSS_FLOOR,BOSS_CELL)——
    boss 由【格几何归属】判定(塔无关)、非硬编码"红门"；win 值恰 = _region_pot(整区待克势能)；
    且至少 1 扇(红钥过 boss 门)。include_win=False 时所有门 win==0（开关干净）。"""
    win_val = _region_pot(ref_state, roster)
    win_doors = []
    for dcell, info in reward_win.items():
        has_boss = _BOSS_NODE in info["pocket"]
        assert (info["win"] > 0.0) == has_boss, \
            f"门 {dcell} win({info['win']}) 与 boss∈pocket({has_boss}) 不一致（boss 检测漂移/硬编码？）"
        if info["win"] > 0.0:
            assert info["win"] == pytest.approx(win_val), f"门 {dcell} win≠_region_pot"
            assert info["R"] >= info["win"] - 1e-6, "win 应是该门 R 的主导项"
            win_doors.append(dcell)
    assert win_doors, "include_win=True 未出现任何 boss-gating 门（红钥过 boss 长臂检测失败）"
    for dcell, info in reward.items():
        assert info["win"] == 0.0, f"include_win=False 门 {dcell} 仍带 win（开关漏）"


def test_pull_zero_after_boss_cleared(zone, reward_win, battery):
    """已胜 boss(BOSS_FLAG 置位) → door_pull 归 0：通关后不再朝任何门引导（不犯"赢了还守门"κ=1）。"""
    exercised = 0
    for s in battery:
        if s.current_floor not in zone["floors"]:
            continue
        g = _copy_state(s)
        g.hero.flags[BOSS_FLAG] = True
        assert door_pull(zone, g, reward_win, 0.1) == 0.0, \
            f"已胜 boss 仍 door_pull≠0(floor={s.current_floor})"
        exercised += 1
    assert exercised >= 1, "命门⑥(胜后归零)未覆盖任何态"
