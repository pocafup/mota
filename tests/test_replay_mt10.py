"""
MT10 Visit 4 重放测试。

验证 mechanics_51.md §G 定义的三个核心行为：
  1. events["6,5"] 触发后 (6,3) 变为 specialDoor (tile 85) → 不可通行
  2. 8 只埋伏敌人全灭后 autoEvent 开门 → (6,3) 变为地板 (tile 0)
  3. 148 token 全程重放无异常，英雄到达出口 (6,11)

初始状态说明：
  - 英雄落点 (1,10)（downFloor=[1,10]，来自低楼层 MT1）
  - ATK=100 / DEF=100 → MT10 所有怪物伤害为 0（见 test_combat_zero_damage）
  - 黄钥匙 ×10 / 红钥匙 ×3 — 足以开启路线中的所有门
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import GameState, HeroState, FloorState, step, load_floor
from sim.combat import Monster, PlayerState, compute_combat

DATA   = Path(__file__).parent.parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

# mechanics_51.md §G.3：events["6,5"] 结束后 8 只敌人的最终坐标
AMBUSH_POS = [(5, 4), (6, 4), (7, 4), (5, 5), (7, 5), (5, 6), (6, 6), (7, 6)]


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def make_initial_state() -> GameState:
    """
    构建 MT10 Visit 4 的起始 GameState。
    ATK/DEF=100 保证 MT10 所有怪物零伤害，钥匙数量充足。
    """
    floor = load_floor(FLOORS / "MT10.json")
    hero = HeroState(
        x=1, y=10,
        hp=1000, atk=100, def_=100, mdef=0,
        gold=0,
        keys={"yellowKey": 10, "blueKey": 3, "redKey": 3},
        items={},
        flags={"魔法免疫": True},
    )
    return GameState(
        hero=hero,
        floors={"MT10": floor},
        current_floor="MT10",
        floor_ids=FLOOR_IDS,
        visited_floors={"MT10"},
        pending_floor_change=None,
        _floors_dir=FLOORS,
    )


def load_tokens() -> list:
    trace = json.loads(
        (DATA / "mt10_route_trace.json").read_text(encoding="utf-8")
    )
    return [t["token"] for t in trace["tokens"]]


def run_until(tokens, state, predicate):
    """
    逐 token 喂给 step()，当 predicate(state) 首次为 True 时返回 (state, idx)。
    若遍历完仍未触发，返回 (final_state, -1)。
    """
    for idx, tok in enumerate(tokens):
        state = step(state, tok)
        if predicate(state):
            return state, idx
    return state, -1


# ── 战斗伤害完整性 ───────────────────────────────────────────────────────────

def test_combat_zero_damage_all_mt10_enemies():
    """ATK=100 / DEF=100 时，MT10 出现的所有怪物伤害均为 0。"""
    hero_ps = PlayerState(hp=1000, atk=100, def_=100, mdef=0)
    db = json.loads((DATA / "monsters.json").read_text(encoding="utf-8"))

    for mid in ("skeleton", "skeletonSoldier", "skeletonCaptain", "bluePriest"):
        m = db[mid]
        sp = m.get("special", [])
        if isinstance(sp, int):
            sp = [sp] if sp else []
        monster = Monster(
            id=mid, name=m["name"],
            hp=m["hp"], atk=m["atk"], def_=m["def"],
            special=sp, n=m.get("n", 0), value=m.get("value", 0.0),
            add=m.get("add", False), atkValue=m.get("atkValue", 0.1),
            defValue=m.get("defValue", 0.9), damage=m.get("damage", 0),
        )
        result = compute_combat(hero_ps, monster)
        assert result.damage == 0, f"{mid}：期望 0 伤害，实际 {result.damage}"


# ── (6,3) 初始状态 ────────────────────────────────────────────────────────────

def test_63_initial_tile_is_17():
    """未触发任何事件时，(6,3) 应为 tile 17（可通行视觉地形）。"""
    state = make_initial_state()
    assert state.floor.map[3][6] == 17, (
        f"期望 tile 17，实际 {state.floor.map[3][6]}"
    )


# ── 埋伏触发：(6,3) 变为 specialDoor ─────────────────────────────────────────

def test_ambush_places_specialdoor_at_63():
    """
    英雄踩 (6,5)，events["6,5"] 同步执行：
    closeDoor specialDoor at (6,3) → map[3][6] 变为 85。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: s.hero.x == 6 and s.hero.y == 5,
    )
    assert idx != -1, "英雄未抵达 (6,5)"
    assert state.floor.map[3][6] == 85, (
        f"events['6,5'] 后 (6,3) 应为 specialDoor (85)，实际 {state.floor.map[3][6]}"
    )


def test_63_impassable_while_ambush_active():
    """
    specialDoor 存在期间，从 (6,4) 向上（U）不得进入 (6,3)。
    """
    tokens = load_tokens()
    # 推进至英雄到达 (6,4) 且 (6,3)==85
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: (
            s.hero.x == 6 and s.hero.y == 4
            and s.floor.map[3][6] == 85
        ),
    )
    assert idx != -1, "英雄未在 specialDoor 存在时抵达 (6,4)"

    blocked = step(state, "U")
    assert blocked.hero.y == 4, (
        "specialDoor 封锁期间，英雄从 (6,4) 向上应被阻挡，y 应保持 4"
    )


# ── autoEvent：全灭后 (6,3) 自动开门 ─────────────────────────────────────────

def test_autoEvent_opens_63_after_all_8_killed():
    """
    8 只埋伏敌人全灭，autoEvent 满足条件 → openDoor at (6,3)。
    断言：英雄站上 (6,3) 时，map[3][6] == 0。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: s.hero.x == 6 and s.hero.y == 3,
    )
    assert idx != -1, "英雄未经过 (6,3)"
    assert state.floor.map[3][6] == 0, (
        f"autoEvent 开门后 (6,3) 应为 0，实际 {state.floor.map[3][6]}"
    )


def test_all_ambush_positions_cleared_before_63_opens():
    """
    当英雄经过 (6,3) 时，AMBUSH_POS 中 8 个坐标均已清空（敌人已死）。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: s.hero.x == 6 and s.hero.y == 3,
    )
    assert idx != -1
    for cx, cy in AMBUSH_POS:
        assert state.floor.map[cy][cx] == 0, (
            f"英雄过 (6,3) 时，埋伏位置 ({cx},{cy}) 应已清空"
        )


# ── 全程重放 ──────────────────────────────────────────────────────────────────

def test_full_replay_no_exception():
    """148 个 token 全部送入 step()，不得抛出异常。"""
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens:
        state = step(state, tok)  # 任何异常均会使测试失败


def test_full_replay_reaches_exit():
    """
    全程重放中，英雄踏上 MT10(6,11) 楼梯并切换到 MT11。
    MT10 trace 中部分 token 属于 MT11 上的首步（旧模拟器靠 _exited 冻结），
    新模拟器无冻结机制，用 visited_floors 验证 MT11 曾经被访问过。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: "MT11" in s.visited_floors,
    )
    assert idx != -1, "148 个 token 内英雄从未进入 MT11"


def test_full_replay_hp_no_decrease():
    """
    MT10 无血网地形，所有怪物对 ATK=100/DEF=100 英雄的伤害均为 0。
    HP 只会因拾取回血道具增加，不会减少。
    """
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens:
        state = step(state, tok)
    assert state.hero.hp >= 1000, (
        f"HP 不应低于初始值 1000，实际 {state.hero.hp}"
    )


def test_full_replay_gold_from_mandatory_kills():
    """
    Visit 4 必须消灭的敌人（8 只埋伏 + 队长）产生的最少金币：
      骷髅 ×6 @ 6 = 36，骷髅士兵 ×2 @ 8 = 16，队长 ×1 @ 30 = 30 → 合计 ≥ 82。
    """
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens:
        state = step(state, tok)
    assert state.hero.gold >= 82, (
        f"期望金币 ≥ 82，实际 {state.hero.gold}"
    )


def test_full_replay_red_key_spent():
    """路线经过红门 (6,9)，消耗 1 把红钥匙，3 → 2。"""
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens:
        state = step(state, tok)
    assert state.hero.keys.get("redKey", 0) == 2, (
        f"期望剩余 2 把红钥匙，实际 {state.hero.keys.get('redKey', 0)}"
    )
