"""fly 魔杖跨层边（方案B保守子集）单测：钉死 enable_fly 开关零回归 + 三道不作弊门 + 落点/零代价。

背景（玩家诊断链）：beam 卡 ATK26→27（破不了红钥门）。§S44 证「钥匙价值」「加大 beam_k」都不是
瓶颈，真问题=【视野】——beam 没拿 MT1 宝石（首访属性不够、绕开了；后期属性够了却"视野下不来"
回不到 MT1）。fly 魔杖（item:fly，cls=constants 永久持有、不消耗）可向回飞（§I.4.1 hasVisitedFloor：
访问过更高层 → 低层算已访问），解此视野病。本文件钉死 fly 边的实现契约：

  · 零回归：enable_fly=False（默认）→ _boundary_ops 不生成任何 fly 算子（守 beam 封板）；
  · gate2 不作弊（只少不多）：canFlyTo=false 的 MT0/MT44/MT50 永不作飞行目标；未访问层永不作目标；
    canFlyFrom=false 的 MT50 永不作飞行起点；
  · gate1 不作弊：当前块够不到任何楼梯（接不上主链）→ 无 fly 边；[to..cur] 主链层须连续全访问过；
  · 落点/代价：_expand_op 经引擎真实 step FLOOR: token 换层，落点合 §I.3.2（向回飞=目标层 up_floor），
    不耗 HP（FLY-CHEAP）、不耗道具（constants），原 state 不被污染（step 纯函数）；
  · search_quotient(enable_fly=True, fly_attrs=None) 报错（缺表则默认 True 兜底会作弊飞入隐藏/结局层）。

塔无关：canFlyTo/canFlyFrom 由驱动层从 data/games51/fly_attrs.json 注入；solver 不写死任何坐标。
纯静态构造态（load_floor + 手置 visited，route-free）→ 不慢、不标 slow。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import GameState, HeroState, load_floor, step
from solver.quotient import _free_cells, _boundary_ops, _expand_op, search_quotient

DATA = Path(__file__).parent.parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
FLY_ATTRS = json.loads((DATA / "fly_attrs.json").read_text(encoding="utf-8"))["floors"]


def _mkstate(cur, visited, atk=9999, hp=99999):
    """裸态：英雄落在 cur 层的 down/up 楼梯格（保证自由块够到楼梯 = has_stair）；高 atk/hp 不影响
    fly 枚举（fly 只读 floor_ids/visited/change_floor/fly_attrs）。fly 道具置 1（constants 永久）。"""
    f = load_floor(FLOORS / f"{cur}.json")
    coords = f.down_floor or f.up_floor or [1, 1]
    hero = HeroState(x=coords[0], y=coords[1], hp=hp, atk=atk, def_=999, mdef=999,
                     gold=0, keys={}, items={"fly": 1}, flags={})
    return GameState(hero=hero, floors={cur: f}, current_floor=cur,
                     floor_ids=FLOOR_IDS, visited_floors=set(visited),
                     pending_floor_change=None, _floors_dir=FLOORS)


def _fly_targets(state, **kw):
    free = _free_cells(state)
    ops = _boundary_ops(state, free, **kw)
    return sorted(o[1] for o in ops if o[0] == "fly")


# ── 零回归：enable_fly=False（默认）= 不生成任何 fly 边（守 beam 封板）────────────────

@pytest.mark.parametrize("cur", ["MT2", "MT6", "MT9", "MT20"])
def test_enable_fly_off_no_fly_ops(cur):
    """enable_fly=False 显式传 → 零 fly 算子（beam 走老路、指纹逐字节不变）。"""
    s = _mkstate(cur, FLOOR_IDS)            # 全访问也不该出 fly（开关关死）
    assert _fly_targets(s, cross_floor=False, enable_fly=False, fly_attrs=FLY_ATTRS) == []
    assert _fly_targets(s, cross_floor=True, enable_fly=False, fly_attrs=FLY_ATTRS) == []


def test_enable_fly_default_no_fly_ops():
    """_boundary_ops 默认调用（不传 enable_fly/fly_attrs，= beam/历史调用签名）→ 零 fly 算子。"""
    s = _mkstate("MT6", FLOOR_IDS)
    free = _free_cells(s)
    assert [o for o in _boundary_ops(s, free) if o[0] == "fly"] == []
    assert [o for o in _boundary_ops(s, free, cross_floor=True) if o[0] == "fly"] == []


# ── gate2：访问过 + canFlyTo≠false 的低层子集（不作弊）────────────────────────────

def test_fly_targets_are_visited_lower_floors():
    """MT6、访问 MT1-6 → 只飞 MT1-5（不含自身 MT6、不含未访问 MT0/MT7+；MT0 兼 canFlyTo=false）。"""
    s = _mkstate("MT6", ["MT1", "MT2", "MT3", "MT4", "MT5", "MT6"])
    targets = _fly_targets(s, cross_floor=False, enable_fly=True, fly_attrs=FLY_ATTRS)
    assert targets == ["MT1", "MT2", "MT3", "MT4", "MT5"]


def test_fly_excludes_unvisited_floors():
    """未访问层永不作飞行目标（§I.4.1 保守取精确访问、不用高索引代理）。"""
    s = _mkstate("MT6", ["MT4", "MT5", "MT6"])   # 只访问 MT4-6
    targets = _fly_targets(s, cross_floor=False, enable_fly=True, fly_attrs=FLY_ATTRS)
    assert targets == ["MT4", "MT5"]             # MT1-3 未访问 → 不可飞
    assert "MT7" not in targets and "MT8" not in targets


def test_fly_gate2_excludes_canflyto_false_floors():
    """canFlyTo=false 的 MT0/MT44/MT50 即使"已访问"也永不作飞行目标（隐藏层/地下室/结局层）；
    普通层（MT43/MT45/MT48）正常可飞。从 MT49 全访问态隔离 gate2（gate1 连续性全满足）。"""
    s = _mkstate("MT49", FLOOR_IDS)              # 全访问 → gate1 对所有层都过 → 隔离 canFlyTo 门
    targets = set(_fly_targets(s, cross_floor=False, enable_fly=True, fly_attrs=FLY_ATTRS))
    for excluded in ("MT0", "MT44", "MT50"):
        assert excluded not in targets, f"{excluded} canFlyTo=false 不该作飞行目标"
    for included in ("MT43", "MT45", "MT48"):
        assert included in targets, f"{included} 普通层应可飞"
    assert len(targets) == 47                    # 51 层 − 自身 MT49 − {MT0,MT44,MT50}


def test_fly_excludes_canflyfrom_false_origin():
    """canFlyFrom=false 的 MT50（结局层）永不作飞行【起点】：身处 MT50 时无任何 fly 边（不能飞出）。"""
    s = _mkstate("MT50", FLOOR_IDS)
    assert _fly_targets(s, cross_floor=False, enable_fly=True, fly_attrs=FLY_ATTRS) == []


# ── gate1：连通性不作弊（接得上主链 + [to..cur] 连续访问）──────────────────────────

def test_fly_contiguity_gate_blocks_gapped_floors():
    """gate1 连续性：[to..cur] 主链层须全访问过。MT6、访问跳过 MT3（{MT1,MT2,MT4,MT5,MT6}）→
    飞 MT1/MT2 须经 MT3（未访问）被挡，只剩 MT4/MT5（[MT4..MT6] 连续访问）。"""
    s = _mkstate("MT6", ["MT1", "MT2", "MT4", "MT5", "MT6"])
    targets = _fly_targets(s, cross_floor=False, enable_fly=True, fly_attrs=FLY_ATTRS)
    assert targets == ["MT4", "MT5"], f"连续性门应只放行 MT4/MT5，实得 {targets}"


def test_fly_requires_stair_reachable_in_block():
    """gate1 接主链：当前自由块够不到任何楼梯格 → 无 fly 边（防"从导航不到的口袋里凭空飞走"）。
    构造：清空当前层 change_floor（块内再无楼梯邻接）→ has_stair=False → 零 fly。"""
    s = _mkstate("MT6", ["MT1", "MT2", "MT3", "MT4", "MT5", "MT6"])
    s.floor.change_floor = {}                    # 抹掉本层全部楼梯格
    assert _fly_targets(s, cross_floor=False, enable_fly=True, fly_attrs=FLY_ATTRS) == []


# ── _expand_op：真实 step 换层、落点合 §I.3.2、零代价、不污染原态 ──────────────────

def test_fly_expand_lands_at_up_floor_no_cost():
    """fly MT6→MT1（向回飞，to_index<from_index → use_down=False → 落 MT1.up_floor）：
    真实换层、HP 不变（FLY-CHEAP）、fly 道具仍=1（constants 不消耗）、原 state 不被污染、MT1 入 visited。"""
    s = _mkstate("MT6", ["MT1", "MT2", "MT3", "MT4", "MT5", "MT6"], hp=12345)
    free = _free_cells(s)
    fly_mt1 = [o for o in _boundary_ops(s, free, enable_fly=True, fly_attrs=FLY_ATTRS)
               if o[0] == "fly" and o[1] == "MT1"]
    assert fly_mt1, "MT6 访问 MT1-6 应有飞回 MT1 的 fly 算子"

    res = _expand_op(s, free, fly_mt1[0], step)
    assert res is not None, "fly 换层应成功推进"
    child, moves = res
    mt1_up = load_floor(FLOORS / "MT1.json").up_floor
    assert child.current_floor == "MT1", "应换层到 MT1"
    assert (child.hero.x, child.hero.y) == tuple(mt1_up), (
        f"向回飞应落 MT1.up_floor={mt1_up}（§I.3.2 use_down=False）"
    )
    assert child.hero.hp == 12345, "fly 不耗 HP（FLY-CHEAP）"
    assert child.hero.items.get("fly") == 1, "fly 是 constants 永久道具、不消耗"
    assert moves == ["FLOOR:MT1"], "动作串应为单个 FLOOR: token"
    assert "MT1" in child.visited_floors, "落点层应入 visited"
    # 原 state 不被污染（step 纯函数）
    assert s.current_floor == "MT6" and (s.hero.x, s.hero.y) == tuple(s.floor.down_floor)
    assert s.hero.hp == 12345


# ── search_quotient：enable_fly=True 须带 fly_attrs（防默认 True 兜底作弊）──────────

def test_search_quotient_enable_fly_requires_fly_attrs():
    """enable_fly=True 而 fly_attrs=None → ValueError（缺表会默认 True 兜底作弊飞入 MT0/MT44/MT50）。"""
    s = _mkstate("MT1", ["MT1"])
    with pytest.raises(ValueError, match="fly_attrs"):
        search_quotient(s, ("MT1", 1, 1), step, enable_fly=True, fly_attrs=None)
