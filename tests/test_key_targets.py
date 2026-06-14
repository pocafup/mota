"""【GA 钥匙目标涌现器 · detect_key_targets 单元验证】（§S9 三分口径钉死 + 验证门）。

钉死两件事：
  ① 三分口径（§S9 定死、probe_key_targets 实测 12/44/3）：detect_key_targets 用真实 key-chain afford
     闭包 + 门拓扑，从一区钥匙全集 59 自然产出 ①顺路12 / ②候选44(含 MT4 六钥) / ③够不到3(MT2 三钥)。
     结构断言（MT4⊆候选、MT2⊆够不到、顺路∩候选=∅、完备划分）+ 数量锚点（防算法改动后输出漂移）。
  ② 验证门：手搓 689 式 chromosome=[盾, MT4 钥匙, 门后目标]，decode 串成引擎可重放的合法路线、物理
     先盾后钥匙（打 MT4 守怪时盾 DEF 已就位）、≥3 钥匙取到、用钥匙开后门。对比现状（detect_big_items
     目标池无钥匙 → 这条路线表达不出）。证 pickup_key 进池后 GA 才表达得出「先拿深盾、回头取浅钥」。

电池组 engine-true：start=build_start()（穿开局噩梦后首个自由态·atk10/def10·手里 0 钥匙）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest

from sim.simulator import step
from probe_crossfloor import build_start
from vzone import build_zone
from key_targets import detect_key_targets
from big_item_pull import detect_big_items
from ga_decode import decode
from solver.beam import build_future_roster
from solver.fitness import build_zone1_roster


@pytest.fixture(scope="module")
def start():
    s, _ = build_start()
    return s


@pytest.fixture(scope="module")
def zone():
    return build_zone()


@pytest.fixture(scope="module")
def zone_fids(start):
    _, zf, _all = build_zone1_roster(start)
    return zf


@pytest.fixture(scope="module")
def kt(start, zone_fids):
    """detect_key_targets 产物 (candidates, info)，全测复用。"""
    return detect_key_targets(start, zone_fids)


def _keys_total(s):
    return sum(v for v in s.hero.keys.values() if isinstance(v, (int, float)))


def _replay_tokens(start_state, tokens):
    s = start_state
    for t in tokens:
        s = step(s, t)
        if s.dead:
            break
    return s


def _terminal_fields(s):
    h = s.hero
    return (s.current_floor, s.dead, s.won, h.x, h.y, h.hp, h.atk, h.def_, h.mdef,
            h.gold, dict(h.keys), dict(h.items))


# ═══ ① 三分口径钉死 ════════════════════════════════════════════════════════════════

def test_afford_closure_colors(kt):
    """零钥起步 key-chain 自给闭包 = 一区真能开的门色 {黄,蓝,红}（铁钥一区拿不到 → 不在内）。"""
    _, info = kt
    assert info["afford"] == {"yellowKey", "blueKey", "redKey"}


def test_triage_counts(kt):
    """数量锚点（防算法漂移）：全集 59 = ①顺路12 + ②候选44 + ③够不到3。"""
    cands, info = kt
    assert len(info["all_keys"]) == 59
    assert len(cands) == 44
    assert len(info["cheap"]) == 12
    assert len(info["unreachable"]) == 3


def test_partition_complete_and_disjoint(kt):
    """三分是【一次滚出的划分】（非加规则）：无交叠且并 == 全集。"""
    cands, info = kt
    cheap, unreach, allk = info["cheap"], info["unreachable"], info["all_keys"]
    assert cheap | cands | unreach == allk
    assert not (cheap & cands)
    assert not (cands & unreach)
    assert not (cheap & unreach)


def test_mt4_six_keys_are_candidates(kt):
    """MT4 六钥（afford 门内·必须打守怪付血才到）全是 ②候选 → 进 GA 池、决策何时取。"""
    cands, info = kt
    mt4 = {c for c in info["all_keys"] if c[0] == "MT4"}
    assert len(mt4) == 6
    assert mt4 <= cands


def test_mt2_three_keys_unreachable_not_candidates(kt):
    """MT2 三钥（黄钥但被铁门锁死·铁钥一区拿不到）全是 ③够不到 → 不进池（自然落③，非特判）。"""
    cands, info = kt
    mt2 = {c for c in info["all_keys"] if c[0] == "MT2"}
    assert len(mt2) == 3
    assert mt2 <= info["unreachable"]
    assert not (mt2 & cands)


def test_cheap_keys_not_candidates(kt):
    """①顺路（零损血白捡·navigate_to 顺手吸）绝不进 ②候选池。"""
    cands, info = kt
    assert info["cheap"]
    assert not (info["cheap"] & cands)


def test_candidates_subset_of_all_keys(kt):
    """候选必是真实钥匙格子集（_tile_to_item∩_KEY_ITEMS 枚举出的全集）。"""
    cands, info = kt
    assert cands <= info["all_keys"]
    for c in cands:
        assert info["colors"].get(c) is not None


# ═══ ② 验证门：689 式 chromosome（盾 → 回头取 MT4 钥匙 → 门后目标）═════════════════════

@pytest.fixture(scope="module")
def gate(start, zone, zone_fids, kt):
    """手搓验证门 chromosome 解码一次，全验证门测试复用。
    盾/门后目标(剑) 从 detect_big_items 涌现；MT4 钥匙从 detect_key_targets 候选涌现——均不写死坐标。"""
    cands, _info = kt
    roster = build_future_roster(start)
    big_cells, _tau, ranked = detect_big_items(zone, roster, start)
    shield = next((c for (drp, c, da, dd) in ranked if c in big_cells and dd > 0), None)
    sword = next((c for (drp, c, da, dd) in ranked if c in big_cells and da > 0), None)
    mt4_keys = sorted(c for c in cands if c[0] == "MT4")
    assert shield and sword and len(mt4_keys) == 6
    chromosome = [shield] + mt4_keys + [sword]
    tokens, final = decode(chromosome, start, zone, step)
    return {"chromosome": chromosome, "tokens": tokens, "final": final,
            "shield": shield, "sword": sword, "mt4_keys": mt4_keys}


def test_gate_replays_in_real_engine(gate, start):
    """合法性铁律：chromosome 解码动作串丢回真引擎逐 token 重放 → 不死、终态逐字段复现。"""
    replayed = _replay_tokens(start, gate["tokens"])
    assert not replayed.dead, "验证门路线重放途中死亡（非法）"
    assert _terminal_fields(replayed) == _terminal_fields(gate["final"]), \
        "验证门独立重放终态与 decode 终态不一致（路线不可重放/非确定）"


def test_gate_picks_up_at_least_three_keys(gate, start):
    """≥3 把 MT4 代价型钥匙真取到（手里钥匙净增 ≥3）——现状目标池无钥匙根本表达不出『回头取钥匙』。"""
    got = _keys_total(gate["final"]) - _keys_total(start)
    assert got >= 3, f"只取到 {got} 把钥匙（验证门要求 ≥3）"


def test_gate_shield_before_keys(gate, start):
    """物理先盾后钥匙：重放时踏上盾 cell 的 step 早于踏上任一 MT4 钥匙 cell 的 step
    （盾 DEF 先就位 → 打 MT4 守怪损血少，正是 689 式『先深盾后浅钥』的时机价值）。"""
    s = start
    shield_step = None
    first_key_step = None
    mt4_set = set(gate["mt4_keys"])
    for i, tok in enumerate(gate["tokens"]):
        s = step(s, tok)
        cur = (s.current_floor, s.hero.x, s.hero.y)
        if cur == gate["shield"] and shield_step is None:
            shield_step = i
        if cur in mt4_set and first_key_step is None:
            first_key_step = i
        if s.dead:
            break
    assert shield_step is not None, "重放未踏上盾 cell"
    assert first_key_step is not None, "重放未踏上任一 MT4 钥匙 cell"
    assert shield_step < first_key_step, \
        f"盾 step({shield_step}) 不早于首钥匙 step({first_key_step})——物理顺序非先盾后钥匙"


def test_gate_opens_door_with_key(gate, start):
    """用钥匙开后门：重放过程中出现『手里钥匙数减少』时刻（开门花掉一把钥匙）。"""
    s = start
    prev = _keys_total(s)
    spent = False
    for tok in gate["tokens"]:
        s = step(s, tok)
        cur = _keys_total(s)
        if cur < prev:
            spent = True
            break
        prev = cur
        if s.dead:
            break
    assert spent, "全程未花钥匙开门（验证门要求『用钥匙开后门』）"
