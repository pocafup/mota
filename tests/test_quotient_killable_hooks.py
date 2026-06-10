"""缩点商图 _killable『独立节点 ⊥ 可杀』解耦回归测试（硬前置 1）。

钉死本次修复：旧版 _killable 把挂 afterBattle/beforeBattle/到达事件的怪一律判【不可杀】，
把「是否独立节点」与「是否可杀」混为一谈 → MT10 骷髅队长(6,1)（挂 afterBattle+到达事件）既
不生成 kill 算子、又因 e∈_tile_to_enemy 不进 trigger 分支 = 无算子死节点、beam 过不了 boss。

解耦后（怪是 noPass、英雄活着踩不上怪格 → 怪格事件皆『怪死后』语义）：
  · 战斗钩子/到达事件怪【可杀】，杀掉经引擎 step 在 _fight_monster 内自然触发 afterBattle；
  · 但仍是【独立节点】（_is_free_tile=False、永不并入自由块），残留指纹保住。

覆盖玩家点名的回归项：
  1. MT10 队长(6,1)：真实重放到临杀前态 → _killable=True、生成 kill 算子、_expand_op 经真 step 杀之
     → afterBattle 触发（清红门(6,9)、置 flag:10f战胜骷髅队长）；
  2. MT2(6,2)/(8,2) blueGuard、MT8(9,5)/(11,5) yellowGuard（4 个 afterBattle 钩子怪）：可杀但
     _is_free_tile=False（独立节点身份保住、不并入自由块）。

MT33 单向阀不经 _killable（flower 地形+outEvents 通道）→ 其单测 test_one_way_valve_mt33.py 与本修复
零关联（放开战斗钩子不碰单向阀），故那 4 条仍 PASS = 反证隔离。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lzstring import LZString
from extract.decode_route import parse_rle_route
from sim.simulator import GameState, HeroState, step, load_floor
from solver.quotient import (_killable, _is_free_tile, _zone_blocked, _free_cells,
                             _boundary_ops, _expand_op)

DATA = Path(__file__).parent.parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

CAPTAIN = (6, 1)
# 玩家点名的 4 个挂 afterBattle 战斗钩子怪（audit_mon_events 全塔扫描所得）
HOOK_MONSTERS = [("MT2", 6, 2), ("MT2", 8, 2), ("MT8", 9, 5), ("MT8", 11, 5)]


def _mid_at(floor, x, y):
    return floor._tile_to_enemy.get(floor.entities[y][x])


def make_initial_state():
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


def load_tokens():
    route_path = next((Path(__file__).parent.parent).glob("51_*.h5route"), None)
    if route_path is None:
        pytest.skip("存档 51_*.h5route 未找到")
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def replay_to(predicate, fail_msg):
    """真实重放（最多 1400 token），返回首个满足 predicate(state) 的态；不命中则 fail。"""
    tokens = load_tokens()
    state = make_initial_state()
    for tok in tokens[:1400]:
        state = step(state, tok)
        if predicate(state):
            return state
    pytest.fail(fail_msg)


def _at_mt10(x, y, captain_alive=True):
    """谓词工厂：MT10、英雄在 (x,y)、(6,3) 已开门(8 怪清完)、队长按需存活。"""
    def pred(s):
        return (s.current_floor == "MT10" and s.hero.x == x and s.hero.y == y
                and s.floors["MT10"].map[3][6] == 0
                and (_mid_at(s.floor, *CAPTAIN) is not None) == captain_alive)
    return pred


def replay_to_captain_pre_kill():
    """真实重放到【MT10、英雄站 (6,2)、队长(6,1)仍活】的临杀前态：8 埋伏怪已清、(6,3) 已开门、
    决斗喊话(6,2)已触发(英雄正站其上)、队长尚未挨打。此态唯一（仅 Visit 5），无歧义。"""
    return replay_to(_at_mt10(6, 2, captain_alive=True),
                     "未重放到 MT10 队长临杀前态（英雄(6,2)、队长(6,1)存活）")


def _mkstate(floor_id, atk=9999, hp=99999):
    """单层裸态：高 atk/hp 保证基础怪可杀。_killable/_is_free_tile 不读英雄坐标，故落点任意。"""
    floor = load_floor(FLOORS / f"{floor_id}.json")
    hero = HeroState(x=0, y=0, hp=hp, atk=atk, def_=999, mdef=999,
                     gold=0, keys={}, items={}, flags={})
    return GameState(hero=hero, floors={floor_id: floor}, current_floor=floor_id,
                     floor_ids=FLOOR_IDS, visited_floors={floor_id},
                     pending_floor_change=None, _floors_dir=FLOORS)


# ── 前置 1 核心：队长可杀 + kill 算子 + afterBattle 触发 ──────────────────────────

def test_captain_now_killable():
    """队长(6,1)挂 afterBattle+到达事件，解耦后 _killable=True（旧版=False=死节点，boss 过不去）。"""
    state = replay_to_captain_pre_kill()
    assert _mid_at(state.floor, *CAPTAIN) is not None, "前提：队长应在 (6,1) 存活"
    assert _killable(state, *CAPTAIN) is True, (
        "队长挂 afterBattle，解耦后应可杀（真到场 atk=100 对队长 0 伤害<hp）；"
        "旧版把战斗钩子并入不可杀 → 无 kill 算子的死节点"
    )


def test_captain_gated_by_duel_trigger_then_killed_two_step():
    """忠实建模 MT10 过 boss 的两步缩点（解耦后天然成立）：队长(6,1)被『决斗喊话』到达事件 (6,2)
    门控——8 怪清完、(6,3) 开门后，队长【不】直接生成 kill 算子（(6,2) 是独立 trigger 节点、挡在
    队长与自由块之间）；先触发 (6,2)（事件 hide remove 自删、英雄踏入）→ 队长才暴露在自由块边界
    → kill 算子出现 → _expand_op 经真 step 杀之 → afterBattle 开 boss 三门 (4,4)/(6,7)/(8,4)、
    清红门 (6,9)、置 flag:10f战胜骷髅队长。
    （旧版 bug：队长既不可杀又因 e∈_tile_to_enemy 不进 trigger 分支 = 无算子死节点，连这第二步都到不了。）"""
    # 种子：英雄 (6,3)，8 怪清完、(6,3) 开门、决斗喊话 (6,2) 未触发、队长(6,1)活
    state = replay_to(_at_mt10(6, 3, captain_alive=True),
                      "未重放到 MT10『8 怪清完、英雄(6,3)、队长活』态")

    free = _free_cells(state)
    ops = _boundary_ops(state, free, cross_floor=True)
    # 队长被 (6,2) 决斗喊话门控：此刻无队长直接 kill 算子，但有 (6,2) trigger 算子
    assert not [o for o in ops if o[0] == "kill" and (o[1], o[2]) == CAPTAIN], (
        "队长应被 (6,2) 决斗喊话门控、此刻不应直接出 kill 算子（(6,2) 是中间独立 trigger 节点）"
    )
    trig62 = [o for o in ops if o[0] == "trigger" and (o[1], o[2]) == (6, 2)]
    assert trig62, f"应有 (6,2) 决斗喊话 trigger 算子，实得 {sorted((o[0], o[1], o[2]) for o in ops)}"

    # 第一步：触发 (6,2)（hide remove 自删 → 英雄踏入 (6,2)）
    res = _expand_op(state, free, trig62[0], step)
    assert res is not None, "触发 (6,2) 应成功推进"
    s2, _ = res
    assert (s2.hero.x, s2.hero.y) == (6, 2), "触发 (6,2) 后英雄应踏入 (6,2)"
    assert "6,2" in s2.floors["MT10"]._suppressed_events, "(6,2) 决斗喊话应自删入 _suppressed_events"

    # 第二步：队长暴露 → kill 算子出现 → 杀之触发 afterBattle
    free2 = _free_cells(s2)
    ops2 = _boundary_ops(s2, free2, cross_floor=True)
    cap_kill = [o for o in ops2 if o[0] == "kill" and (o[1], o[2]) == CAPTAIN]
    assert cap_kill, "触发决斗喊话后队长应暴露在自由块边界、生成 kill 算子"

    res2 = _expand_op(s2, free2, cap_kill[0], step)
    assert res2 is not None, "杀队长应成功推进"
    s3, _ = res2
    assert _mid_at(s3.floor, *CAPTAIN) is None, "杀后 (6,1) 不应再是怪"
    mt10 = s3.floors["MT10"]
    assert mt10.map[4][4] == 0 and mt10.map[7][6] == 0 and mt10.map[4][8] == 0, (
        "afterBattle 应开 boss 三门 (4,4)/(6,7)/(8,4)（map[y][x]）"
    )
    assert mt10.map[9][6] == 0, "afterBattle 应清红门 (6,9)"
    assert s3.hero.flags.get("10f战胜骷髅队长") is True, (
        "afterBattle 应置 flag:10f战胜骷髅队长=True（证 kill 经真 step 触发后续）"
    )


def test_captain_stays_independent_node_pre_kill():
    """解耦只放可杀、不动节点身份：临杀前队长格 (6,1) 仍 _is_free_tile=False、不在英雄自由块内。"""
    state = replay_to_captain_pre_kill()
    zb = _zone_blocked(state)
    assert _is_free_tile(state, *CAPTAIN, zb) is False, "活队长格必须非自由（独立节点）"
    assert CAPTAIN not in _free_cells(state), "队长格不得并入英雄自由块"


# ── 钩子怪：可杀 ⊥ 独立节点（玩家点名的 4 只）────────────────────────────────────

@pytest.mark.parametrize("fid,x,y", HOOK_MONSTERS)
def test_hook_monster_killable_but_stays_independent_node(fid, x, y):
    """MT2/MT8 4 个挂 afterBattle 钩子怪：解耦后【可杀】，但 _is_free_tile=False（独立节点身份保住、
    不并入自由块）——证『可杀』与『独立节点』正交。"""
    st = _mkstate(fid)
    assert _mid_at(st.floor, x, y) is not None, f"{fid}({x},{y}) 应有怪"
    assert f"{x},{y}" in st.floor.after_battle, f"{fid}({x},{y}) 应挂 afterBattle（钩子怪）"
    assert _killable(st, x, y) is True, (
        f"{fid}({x},{y}) 高 atk 下应可杀（解耦后钩子怪可杀，旧版误判不可杀）"
    )
    zb = _zone_blocked(st)
    assert _is_free_tile(st, x, y, zb) is False, (
        f"{fid}({x},{y}) 是怪格 → 必须仍非自由（独立节点身份），不得并入自由块"
    )
