"""
MT10 Visit 5 重放测试（全路径重放版本）。

原 7 个隔离测试已升级为全路径重放：从 hero_init.json 初始状态出发，
重放完整 51_*.h5route 路径，验证 MT10 埋伏机关的正确行为。

mechanics_51.md §G 核心时刻：
  - Visit 5 从 tok[1168] 开始，英雄以 RK=0 进入 MT10
  - tok[1190]：英雄踩 (6,5)，events["6,5"] 同步关门 → (6,3) tile=85
  - tok[1195]：英雄消灭 (6,4) 处敌人，站在 (6,4)，(6,3) 仍为 85（阻挡）
  - tok[1204]：8 只埋伏敌人全灭，autoEvent 开门 → (6,3) tile=0
  - tok[1213]：击败队长 (6,1)，afterBattle 清除红门 (6,9) → tile=0
  - tok[1250]：英雄进入 MT11（HP=701，gold=305，RK=0）
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lzstring import LZString
from extract.decode_route import parse_rle_route
from sim.simulator import GameState, HeroState, step, load_floor
from sim.combat import Monster, PlayerState, compute_combat

DATA      = Path(__file__).parent.parent / "data" / "games51"
FLOORS    = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

# mechanics_51.md §G.3：events["6,5"] 触发后 8 只埋伏敌人的坐标 (x, y)
AMBUSH_POS = [(5, 4), (6, 4), (7, 4), (5, 5), (7, 5), (5, 6), (6, 6), (7, 6)]


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def load_tokens() -> list:
    """加载完整路径 tokens（与 test_checkpoints.py 相同的数据源）。"""
    route_path = next(Path(".").glob("51_*.h5route"), None)
    if route_path is None:
        route_path = next((Path(__file__).parent.parent).glob("51_*.h5route"), None)
    if route_path is None:
        pytest.skip("存档文件 51_*.h5route 未找到")
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def make_initial_state() -> GameState:
    """从 hero_init.json 构建真实初始状态（与 test_checkpoints.py 相同）。"""
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
        hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0), gold=hero_init.get("gold", 0),
        keys={}, items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero, floors={"MT1": floor}, current_floor="MT1",
        floor_ids=FLOOR_IDS, visited_floors={"MT1"},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def run_until(tokens, state, predicate, max_tokens=None):
    """
    逐 token 喂给 step()，当 predicate(state) 首次为 True 时返回 (state, idx)。
    若遍历完仍未触发，返回 (final_state, -1)。
    """
    token_seq = tokens[:max_tokens] if max_tokens is not None else tokens
    for idx, tok in enumerate(token_seq):
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
    """MT10 初始状态 (6,3) 应为 tile 17（可通行视觉地形）。"""
    mt10 = load_floor(FLOORS / "MT10.json")
    assert mt10.map[3][6] == 17, f"期望 tile 17，实际 {mt10.map[3][6]}"


# ── 埋伏触发：(6,3) 变为 specialDoor ─────────────────────────────────────────

def test_ambush_places_specialdoor_at_63():
    """
    英雄踩 MT10(6,5)，events["6,5"] 同步执行：
    closeDoor specialDoor at (6,3) → map[3][6] 变为 85。

    predicate 同时要求 map[3][6]==85，以跳过 Visit 5 之前的访问
    （早期访问 (6,5) 时事件未触发，map[3][6]==17）。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: (
            s.current_floor == "MT10"
            and s.hero.x == 6 and s.hero.y == 5
            and s.floors["MT10"].map[3][6] == 85
        ),
        max_tokens=1400,
    )
    assert idx != -1, "英雄未在 MT10(6,5) 触发埋伏（(6,3) 应变为 specialDoor）"
    assert state.floors["MT10"].map[3][6] == 85, (
        f"events['6,5'] 后 (6,3) 应为 specialDoor (85)，"
        f"实际 {state.floors['MT10'].map[3][6]}"
    )


def test_63_impassable_while_ambush_active():
    """
    specialDoor 存在期间，从 MT10(6,4) 向上（U）不得进入 (6,3)。

    predicate 要求 map[3][6]==85 以确保处于 Visit 5 埋伏封锁阶段。
    tok[1195]：英雄消灭 (6,4) 处敌人后站在 (6,4)，(6,3) 仍封闭。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: (
            s.current_floor == "MT10"
            and s.hero.x == 6 and s.hero.y == 4
            and s.floors["MT10"].map[3][6] == 85
        ),
        max_tokens=1400,
    )
    assert idx != -1, "英雄未在 specialDoor 存在时抵达 MT10(6,4)"
    blocked = step(state, "U")
    assert blocked.hero.y == 4, (
        "specialDoor 封锁期间，英雄从 (6,4) 向上应被阻挡，y 应保持 4"
    )


# ── autoEvent：全灭后 (6,3) 自动开门 ─────────────────────────────────────────

def test_autoEvent_opens_63_after_all_8_killed():
    """
    8 只埋伏敌人全灭，autoEvent 满足条件 → openDoor at (6,3)。
    断言：英雄能踏上 MT10(6,3) 且 map[3][6] == 0。

    predicate 要求 map[3][6]==0 以区别初始状态（tile=17）和开门后（tile=0）。
    tok[1210] 附近：英雄从 (6,4) 向上经过 (6,3) 前往队长位置 (6,1)。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: (
            s.current_floor == "MT10"
            and s.hero.x == 6 and s.hero.y == 3
            and s.floors["MT10"].map[3][6] == 0
        ),
        max_tokens=1400,
    )
    assert idx != -1, "英雄未在 autoEvent 开门后经过 MT10(6,3)"
    assert state.floors["MT10"].map[3][6] == 0, (
        f"autoEvent 开门后 (6,3) 应为 tile 0，"
        f"实际 {state.floors['MT10'].map[3][6]}"
    )


def test_all_ambush_positions_cleared_before_63_opens():
    """
    当英雄踏过 MT10(6,3)（autoEvent 开门后），AMBUSH_POS 8 个坐标的
    实体层（entities）均已清空（== 0）。

    注：AMBUSH_POS 坐标的 terrain 不全是 0（有 tile17/tile330 装饰），
    需检查 entities 层而非 map 属性。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: (
            s.current_floor == "MT10"
            and s.hero.x == 6 and s.hero.y == 3
            and s.floors["MT10"].map[3][6] == 0
        ),
        max_tokens=1400,
    )
    assert idx != -1
    mt10 = state.floors["MT10"]
    for cx, cy in AMBUSH_POS:
        assert mt10.entities[cy][cx] == 0, (
            f"英雄过 (6,3) 时，埋伏位置 ({cx},{cy}) 实体层应已清空，"
            f"实际 entities[{cy}][{cx}] = {mt10.entities[cy][cx]}"
        )


# ── 全程重放 ──────────────────────────────────────────────────────────────────

def test_full_replay_no_exception():
    """tok[0..1300] 全部送入 step()，不得抛出异常（覆盖全部 13 个检查点范围）。"""
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens[:1301]:
        state = step(state, tok)


def test_full_replay_reaches_exit():
    """全路径中，英雄踏上 MT10(6,11) 楼梯并切换到 MT11（tok[1250]）。"""
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: "MT11" in s.visited_floors,
        max_tokens=1400,
    )
    assert idx != -1, "tok[0..1399] 内英雄从未进入 MT11"


def test_visit5_hp_at_mt11_entry():
    """
    Visit 5 战斗消耗 HP 后，拾取 3 个回血道具恢复，进入 MT11 时 HP == 701。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: "MT11" in s.visited_floors,
        max_tokens=1400,
    )
    assert idx != -1, "英雄未进入 MT11"
    assert state.hero.hp == 701, (
        f"期望进入 MT11 时 HP=701，实际 {state.hero.hp}"
    )


def test_visit5_gold_at_mt11_entry():
    """
    Visit 5 强制消灭 8 只埋伏敌人 + 骷髅队长后，进入 MT11 时 gold == 305。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: "MT11" in s.visited_floors,
        max_tokens=1400,
    )
    assert idx != -1, "英雄未进入 MT11"
    assert state.hero.gold == 305, (
        f"期望进入 MT11 时 gold=305，实际 {state.hero.gold}"
    )


def test_red_door_cleared_by_event_not_key():
    """
    afterBattle['6,1'] 执行 setBlock 清除 MT10(6,9) 红门 → map[9][6] == 0。
    英雄以 RK=0 进入 Visit 5 并成功退出到 MT11，证明红门由事件而非钥匙开启。
    """
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: "MT11" in s.visited_floors,
        max_tokens=1400,
    )
    assert idx != -1, "英雄未进入 MT11"
    assert state.floors["MT10"].map[9][6] == 0, (
        f"afterBattle['6,1'] 后 (6,9) 应为 0（红门已清除），"
        f"实际 map[9][6]={state.floors['MT10'].map[9][6]}"
    )
    assert state.hero.keys.get("redKey", 0) == 0, (
        f"英雄以 RK=0 通过 MT10，进入 MT11 时应仍为 0，"
        f"实际 RK={state.hero.keys.get('redKey', 0)}"
    )
