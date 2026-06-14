"""【GA decoder · decode 最小闭环 单元验证】（这一棒的成败判据）。

只测 decode 把【基因目标序列 → 串 navigate_to → 合法完整路线 + 终态】这条数据链转得对，绝不进任何
进化（无种群/选择/交叉/变异/主循环）。基因目标【数据涌现】（detect_big_items 的大件/小宝石引用，不
手写裸坐标）：
  A=[剑,盾]              早拿盾、留潜力
  B=[剑,小宝石*k,盾]     晚拿盾、扫小宝石
  C=[盾,剑]              顺序反

钉死的契约（ga_design 钉死点 2.1/2.2/2.3 + CLAUDE.md 验证铁律）：
  · 合法性（铁律）：decode 出的动作串丢回真引擎从入口重放 → 逐字段复现 final_state（撞墙/无钥/打不过
    要么不生成、要么 no-op，产物必是引擎可重放的合法路线）。
  · 闭环门：同一把 718/689 标定尺子下 fitness(A) ≥ fitness(B)——复现 fitness 对「留潜力 > 耗资源」的
    689>718 方向（在目标序列层面）。不成立则诊断解码/基因表示，别硬凑。
  · 钉死点 2.3：够不到的目标 navigate_to 返 reached=False → decode 跳过该目标、零副作用（基因是
    "愿望清单"，做不到就略过 → 任何基因永远可解码成合法路线、不整条作废）。
  · 边界：空基因 → 空动作 + 原样返回入口态本体。

电池组 engine-true：start=build_start()（穿开局噩梦后首个自由态）；尺子=回放 718/689 两条真 route
（与 tests/test_fitness 同源标定）。step 纯函数 → start/终态多测复用、不被改写。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import json

import pytest

from sim.simulator import step
from probe_crossfloor import build_start
from solver.beam import build_future_roster
from vzone import build_zone
from big_item_pull import detect_big_items
from ga_decode import decode
from decode_route import parse_rle_route, decompress
from export_mt10_boss_route import make_initial_state
from solver.fitness import build_zone1_roster, calibrate_big, fitness

W_POTION, W_KEY = 1.5, 39      # 标定值（与 718/689 同尺子，handoff §S7 / test_fitness）
K_SMALL = 3                    # gene_B 扫几个小宝石

R718 = ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"
R689 = ROOT / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route"


def _replay_route(route_file):
    """回放一条 .h5route 真路线 → 终态（标定尺子用，与 test_fitness 同源）。"""
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    for a in actions:
        s = step(s, a)
        if s.dead:
            break
    return s


def _replay_tokens(start_state, tokens):
    """从入口态逐 token 真 step 重放 decode 产物（合法性铁律的独立裁判）。"""
    s = start_state
    for t in tokens:
        s = step(s, t)
        if s.dead:
            break
    return s


def _terminal_fields(s):
    """终态指纹：decode 终态 vs 独立重放终态须逐字段相等（合法 + 确定可重放）。"""
    h = s.hero
    return (s.current_floor, s.dead, s.won, h.x, h.y, h.hp, h.atk, h.def_, h.mdef,
            h.gold, dict(h.keys), dict(h.items))


@pytest.fixture(scope="module")
def zone():
    return build_zone()


@pytest.fixture(scope="module")
def start():
    s, _ = build_start()
    return s


@pytest.fixture(scope="module")
def targets(zone, start):
    """剑/盾/小宝石目标【数据涌现】：detect_big_items 找 ΔRP 最大乘性缝；不硬编码坐标。"""
    roster = build_future_roster(start)
    big_cells, _tau, ranked = detect_big_items(zone, roster, start)
    sword = next((c for (drp, c, da, dd) in ranked if c in big_cells and da > 0), None)
    shield = next((c for (drp, c, da, dd) in ranked if c in big_cells and dd > 0), None)
    small = [c for (drp, c, da, dd) in ranked if c not in big_cells and drp > 0]
    assert sword is not None and shield is not None and small, "目标涌现失败（剑/盾/小宝石缺）"
    return {"sword": sword, "shield": shield, "small": small}


@pytest.fixture(scope="module")
def genes(targets):
    sword, shield, small = targets["sword"], targets["shield"], targets["small"]
    return {
        "A": [sword, shield],
        "B": [sword] + small[:K_SMALL] + [shield],
        "C": [shield, sword],
    }


@pytest.fixture(scope="module")
def decoded(start, zone, genes):
    """A/B/C 各解码一次（共享 navigate_to 缓存省算），全测复用。返回 {label: (tokens, final)}。"""
    cache = {}
    return {label: decode(gene, start, zone, step, cache=cache)
            for label, gene in genes.items()}


@pytest.fixture(scope="module")
def ruler():
    """718/689 标定尺子（roster/big/zone_fids），与 test_fitness 同一把尺。"""
    s718 = _replay_route(R718)
    s689 = _replay_route(R689)
    roster, zone_fids, _all = build_zone1_roster(s718)
    big = calibrate_big([s718, s689, make_initial_state()], roster)
    return {"s718": s718, "s689": s689, "roster": roster,
            "zone_fids": zone_fids, "big": big}


def _fit(state, ruler):
    return fitness(state, ruler["roster"], ruler["big"], ruler["zone_fids"],
                   w_potion=W_POTION, w_key=W_KEY)


# ── 契约 1（CLAUDE.md 铁律）：decode 动作串丢回真引擎重放 → 逐字段复现终态 ──────────
@pytest.mark.parametrize("label", ["A", "B", "C"])
def test_decode_replays_in_real_engine(decoded, start, label):
    """decode 串出的路线必是【引擎可重放的合法路线】：从入口逐 token 真 step，终态逐字段复现。"""
    tokens, final = decoded[label]
    replayed = _replay_tokens(start, tokens)
    assert not replayed.dead, f"{label}：重放途中死亡（路线非法）"
    assert _terminal_fields(replayed) == _terminal_fields(final), \
        f"{label}：独立重放终态与 decode 终态字段不一致（路线不可重放/非确定）"


# ── 契约 2（闭环门）：标定尺下 fitness(A) ≥ fitness(B)，复现 689>718「留潜力>耗资源」方向 ──
def test_closure_A_ge_B(decoded, ruler):
    """本棒成败判据：早拿盾留潜力(A) 不输 晚拿盾扫宝石(B)。不成立 → 诊断解码/基因表示，别硬凑。"""
    fa = _fit(decoded["A"][1], ruler)
    fb = _fit(decoded["B"][1], ruler)
    assert fa >= fb, f"闭环门破：fitness(A)={fa:.1f} < fitness(B)={fb:.1f}"


def test_ruler_anchor_689_beats_718(ruler):
    """同尺 sanity：689(高潜力) > 718(耗尽)，确认 A/B 与锚点同标定（同一把 fitness 尺子）。"""
    assert _fit(ruler["s689"], ruler) > _fit(ruler["s718"], ruler)


# ── 契约 3：基因确实把英雄合法推进了（非空动作、未死、家底兑现）─────────────────────
@pytest.mark.parametrize("label", ["A", "B", "C"])
def test_decode_nonempty_alive_equipped(decoded, label):
    tokens, final = decoded[label]
    assert tokens, f"{label}：解码出空动作串（基因目标全没够到？）"
    assert not final.dead, f"{label}：终态死亡"
    assert final.hero.atk > 10 and final.hero.def_ > 10, \
        f"{label}：终态 atk={final.hero.atk}/def={final.hero.def_} 未超开局 10/10（剑盾家底未兑现）"


# ── 钉死点 2.3：够不到的目标被干净跳过、零副作用（基因=愿望清单，不整条作废）──────────
def test_unreachable_goal_skipped(start, zone, targets):
    """区外目标 navigate_to 必返 reached=False → decode 跳过它、state 不变 → [区外,剑] 与 [剑] 逐字段同。
    用低 max_pops 让区外目标快速失败（与 test_ga_navigate 原子失败口径一致）。"""
    sword = targets["sword"]
    off_zone = ("MT0", 1, 1)              # 区外格：hop 场为空 → 必不可达
    cache = {}
    t_plain, f_plain = decode([sword], start, zone, step, cache=cache, max_pops=60)
    t_off, f_off = decode([off_zone, sword], start, zone, step, cache=cache, max_pops=60)
    assert t_off == t_plain, "区外目标未被干净跳过（动作串受污染）"
    assert _terminal_fields(f_off) == _terminal_fields(f_plain), "区外目标改变了终态（非零副作用）"
    # 且确实够到了剑（区外目标只是被略过、不影响后续目标推进）
    replayed = _replay_tokens(start, t_off)
    assert (replayed.current_floor, replayed.hero.x, replayed.hero.y) == sword, \
        "跳过区外目标后未够到剑"


# ── 边界：空基因 → 空动作 + 原样返回入口态本体（零副作用）────────────────────────────
def test_empty_chromosome_returns_start(start, zone):
    tokens, final = decode([], start, zone, step)
    assert tokens == [], "空基因应解码出空动作串"
    assert final is start, "空基因应原样返回入口态【同一对象】（零副作用）"
