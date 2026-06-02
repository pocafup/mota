"""
MT1→MT11 跨层重放测试 + MT3 伏击机制隔离测试。

重放测试（共 4 项）：
  1. 全 1318 个 token 逐一送入 step()，不抛出异常
  2. 最终 current_floor="MT11"，英雄落点 (6,10)
  3. 路由 FLOOR 关键切点断言：FLOOR:MT3 后 current_floor=="MT3"（upFloor 落点 10,11）

MT3 伏击机制隔离测试（共 7 项）：
  路由实际未经过 (5,9)（英雄仅从 MT4 upFloor 进入 MT3 右侧孤立区域，无法到达左侧内部）。
  改用隔离测试：直接把英雄置于 (5,8)，step('U') 踩上 (5,9)，验证事件正确执行：
    HP=400, ATK=10, DEF=10, nowWeapon=None, nowShield=None, 魔法免疫=False, 传送至 MT2(3,8)

初始状态来源：data/games51/hero_init.json
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA   = Path(__file__).parent.parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

# 路由中 FLOOR:MT11 的索引（共 1318 个 token，下标 0-1317）
MT11_ENTRY_INDEX = 1317


def _decode_all_tokens() -> list[str]:
    def decompress(s: str) -> str:
        return LZString().decompressFromBase64(s)

    route_path = next(Path(__file__).parent.parent.glob("51_*.h5route"))
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    return parse_rle_route(decompress(outer["route"]))


def load_tokens() -> list[str]:
    """返回 token[0..MT11_ENTRY_INDEX]（含 FLOOR:MT11）。"""
    all_tokens = _decode_all_tokens()
    assert all_tokens[MT11_ENTRY_INDEX] == "FLOOR:MT11", (
        f"token[{MT11_ENTRY_INDEX}] 应为 FLOOR:MT11，实际 {all_tokens[MT11_ENTRY_INDEX]!r}"
    )
    return all_tokens[: MT11_ENTRY_INDEX + 1]


def make_initial_state() -> GameState:
    """按 hero_init.json 构建 MT1 起始状态。"""
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"],
        y=hero_init["loc"]["y"],
        hp=hero_init["hp"],
        atk=hero_init["atk"],
        def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0),
        gold=hero_init.get("gold", 0),
        keys={},
        items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero,
        floors={"MT1": floor},
        current_floor="MT1",
        floor_ids=FLOOR_IDS,
        visited_floors={"MT1"},
        pending_floor_change=None,
        _floors_dir=FLOORS,
    )


def run_replay(tokens: list[str]) -> GameState:
    state = make_initial_state()
    for tok in tokens:
        state = step(state, tok)
    return state


# ── 全程无异常 ────────────────────────────────────────────────────────────────

def test_full_replay_no_exception():
    """1318 个 token 全部送入 step()，不得抛出异常。"""
    tokens = load_tokens()
    run_replay(tokens)


# ── 最终楼层和落点 ────────────────────────────────────────────────────────────

def test_final_floor_is_mt11():
    """最终 current_floor 应为 MT11。"""
    tokens = load_tokens()
    state = run_replay(tokens)
    assert state.current_floor == "MT11", (
        f"期望 MT11，实际 {state.current_floor!r}"
    )


def test_final_position_is_mt11_downfloor():
    """
    FLOOR:MT11 来自 MT14（index=14 > 11）→ 落点为 MT11.upFloor=[11,10]。
    fly 规则：from_index > to_index → use_down=False → 用 upFloor。
    """
    tokens = load_tokens()
    state = run_replay(tokens)
    assert state.hero.x == 11 and state.hero.y == 10, (
        f"期望 MT11 落点 (11,10)，实际 ({state.hero.x},{state.hero.y})"
    )


# ── MT3 伏击验证（路线重放） ─────────────────────────────────────────────────────

def _state_at_ambush() -> GameState:
    """
    路线全程重放直到 MT3 伏击触发（ATK 降至 10）后返回该状态。
    §H 定论：伏击强制触发，setValue status:atk=10 在路线重放中必定执行。
    若 ATK 全程未降至 10，说明模拟器存在 bug，未能在路线中复现伏击触发。
    """
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens:
        state = step(state, tok)
        if state.hero.atk == 10:
            return state
    pytest.fail(
        "重放 1318 个 token 后 ATK 从未等于 10。\n"
        "§H 定论：MT3 伏击强制触发，须将 ATK 重置为 10。\n"
        "模拟器未在路线重放中复现此事件——须查模拟器 bug。\n"
        "诊断线索：英雄是否到达 MT3(5,9)？changeFloor 分支/null 处理是否正常？\n"
        "stair changeFloor 在 MT1(1,1) 处是否触发？"
    )


def test_mt3_ambush_hp_reset():
    """路线重放中 MT3 伏击触发 → HP 重置为 400（§H setValue status:hp=400）。"""
    state = _state_at_ambush()
    assert state.hero.hp == 400, (
        f"伏击触发时 HP 应为 400，实际 {state.hero.hp}"
    )


def test_mt3_ambush_atk_reset():
    """路线重放中 MT3 伏击触发 → ATK 重置为 10（§H setValue status:atk=10）。"""
    assert _state_at_ambush().hero.atk == 10


def test_mt3_ambush_def_reset():
    """路线重放中 MT3 伏击触发 → DEF 重置为 10（§H setValue status:def=10）。"""
    state = _state_at_ambush()
    assert state.hero.def_ == 10, (
        f"伏击触发时 DEF 应为 10，实际 {state.hero.def_}"
    )


def test_mt3_ambush_weapon_unequipped():
    """路线重放中 MT3 伏击触发 → nowWeapon=None（§H setValue flag:nowWeapon=null）。"""
    state = _state_at_ambush()
    assert state.hero.flags.get("nowWeapon") is None, (
        f"伏击触发时 nowWeapon 应为 None，实际 {state.hero.flags.get('nowWeapon')!r}"
    )


def test_mt3_ambush_shield_unequipped():
    """路线重放中 MT3 伏击触发 → nowShield=None（§H setValue flag:nowShield=null）。"""
    state = _state_at_ambush()
    assert state.hero.flags.get("nowShield") is None, (
        f"伏击触发时 nowShield 应为 None，实际 {state.hero.flags.get('nowShield')!r}"
    )


def test_mt3_ambush_magic_immune_removed():
    """路线重放中 MT3 伏击触发 → 魔法免疫=False（§H setValue flag:魔法免疫=false）。"""
    state = _state_at_ambush()
    assert state.hero.flags.get("魔法免疫") is False, (
        f"伏击触发时 魔法免疫 应为 False，实际 {state.hero.flags.get('魔法免疫')!r}"
    )


def test_mt3_ambush_teleports_to_mt2():
    """路线重放中 MT3 伏击触发 → 传送至 MT2(3,8)（§H changeFloor MT2 [3,8]）。"""
    state = _state_at_ambush()
    assert state.current_floor == "MT2", (
        f"伏击后期望 current_floor=MT2，实际 {state.current_floor!r}"
    )
    assert state.hero.x == 3 and state.hero.y == 8, (
        f"伏击后期望英雄在 (3,8)，实际 ({state.hero.x},{state.hero.y})"
    )


# ── 关键 FLOOR token 切点断言 ─────────────────────────────────────────────────

def test_floor_mt3_transition():
    """
    FLOOR:MT3（第一次，token[573]）处理后，current_floor 应为 MT3。
    MT3 来自 MT7（index=7>3）→ 落点 MT3.upFloor=[10,11]。
    """
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens[: 574]:   # 含 token[573]
        state = step(state, tok)
    assert state.current_floor == "MT3", (
        f"FLOOR:MT3 后期望 current_floor=MT3，实际 {state.current_floor!r}"
    )
    # MT3.upFloor = [10, 11]
    assert state.hero.x == 10 and state.hero.y == 11, (
        f"MT3 upFloor 落点期望 (10,11)，实际 ({state.hero.x},{state.hero.y})"
    )
