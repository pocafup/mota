"""神圣盾(shield5) = flag:魔法免疫 → 区域伤(领域/夹击/阻击/激光/伏击)全免 单元测试。

机制事实来源（引擎源码，详见 docs/mechanics_51.md §C / items.json）：
  - shield5 itemEffect: `hero.def += 100; setFlag('nowShield','shield5'); setFlag('魔法免疫', true)`。
    (mdef:100 仅 equip 模式，itemEffect 不加；本塔按 itemEffect 拾取，故只 +def100。)
  - updateCheckBlock: 领域15/夹击16/阻击18/激光24/伏击27 的伤害，flag:魔法免疫 一律置 0。
  - 神圣盾在 MT44(6,6)，杀两个 redGuard 开 specialDoor(6,8) 入中心拾取。本 route token4527 拾取。
  - 血网(lavaNet) 是【另一套】免疫(护符 amulet)，本塔无 lavaNet 地形、无 amulet → 该机制空置。
    lava(tile5) 是 noPass 障碍(MT13/MT26)，不扣血，由 snow 清除（见 test_force_battle_mt32 snow 测试）。

“持盾前后过同一巫师格的损血对比”是本测试核心：同一 redWizard 领域格，
不持盾损 value、持盾(魔法免疫)损 0。value 从 monsters DB 读取（数据驱动，不硬编码塔值）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import (
    GameState, HeroState, load_floor,
    _apply_zone_damage, _apply_item_effect, _live_zone_monsters,
    _in_zone_range, _SP_ZONE,
)

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

# (楼层, 英雄格, 巫师id, 巫师格)：扫描得「英雄格仅落在该 1 个巫师领域内」(单源，期望损血=该巫师 value)
ZONE_CASES = [
    ('MT41', (2, 1), 'redWizard',   (2, 2)),
    ('MT42', (9, 3), 'brownWizard', (9, 4)),
]


def _mkstate(fid, x, y, hp, flags=None):
    f = load_floor(FLOORS / f'{fid}.json')
    hero = HeroState(x=x, y=y, hp=hp, atk=1, def_=1, mdef=0,
                     gold=0, keys={}, items={}, flags=dict(flags or {}))
    return GameState(hero=hero, floors={fid: f}, current_floor=fid,
                     floor_ids=FLOOR_IDS, visited_floors={fid},
                     pending_floor_change=None, _floors_dir=FLOORS)


def _wizard_value(state, mid):
    """从该层 monsters DB 读巫师领域 value（数据驱动，不硬编码塔值）。"""
    return state.floor._monsters_db[mid]['value']


def _assert_single_source(state, x, y, mid, mxy):
    """守卫：确认 (x,y) 恰好只在 mid 一个领域怪范围内（否则测试前提失效）。"""
    srcs = [(m[0], m[1], m[2]) for m in _live_zone_monsters(state)
            if _SP_ZONE in m[3] and _in_zone_range(x, y, m[0], m[1], m[5], m[6])]
    assert srcs == [(mxy[0], mxy[1], mid)], f'前提失效：{(x, y)} 领域来源={srcs}'


@pytest.mark.parametrize('fid,hxy,mid,mxy', ZONE_CASES)
def test_zone_damage_applies_without_shield(fid, hxy, mid, mxy):
    """不持盾(无 魔法免疫)：踩巫师领域格损血 = 该巫师 value。"""
    x, y = hxy
    st = _mkstate(fid, x, y, hp=10000)
    _assert_single_source(st, x, y, mid, mxy)
    val = _wizard_value(st, mid)
    _apply_zone_damage(st, x, y)
    assert st.hero.hp == 10000 - val, f'{mid} 领域应损 {val}'
    assert st.dead is False


@pytest.mark.parametrize('fid,hxy,mid,mxy', ZONE_CASES)
def test_zone_damage_immune_with_shield_flag(fid, hxy, mid, mxy):
    """持盾(flag:魔法免疫=true)：同一巫师领域格损血 = 0。"""
    x, y = hxy
    st = _mkstate(fid, x, y, hp=10000, flags={'魔法免疫': True})
    _assert_single_source(st, x, y, mid, mxy)
    _apply_zone_damage(st, x, y)
    assert st.hero.hp == 10000, '魔法免疫应全免领域伤'


def test_same_cell_before_after_shield():
    """同一 redWizard 领域格：拾盾【前】损 value、拾盾【后】(魔法免疫)损 0 —— 持盾前后损血对比。"""
    fid, (x, y), mid, mxy = ZONE_CASES[0]

    before = _mkstate(fid, x, y, hp=10000)
    val = _wizard_value(before, mid)
    _apply_zone_damage(before, x, y)
    dmg_before = 10000 - before.hero.hp
    assert dmg_before == val and val > 0

    after = _mkstate(fid, x, y, hp=10000)
    shield_pickup = json.loads((DATA / 'items.json').read_text(encoding='utf-8'))['shield5']['pickup']
    _apply_item_effect(after.hero, shield_pickup, ratio=after.floor.ratio)
    _apply_zone_damage(after, x, y)
    dmg_after = 10000 - after.hero.hp
    assert dmg_after == 0, '拾神圣盾后同格应零伤'


def test_shield5_pickup_sets_def_and_flags():
    """拾 shield5 = DEF+100 + flag:魔法免疫=true + flag:nowShield=shield5（引擎 itemEffect 字面量）。"""
    st = _mkstate('MT44', 6, 5, hp=10000)
    st.hero.def_ = 204                              # 拾盾前本 route DEF（checkpoint 4504）
    shield_pickup = json.loads((DATA / 'items.json').read_text(encoding='utf-8'))['shield5']['pickup']
    _apply_item_effect(st.hero, shield_pickup, ratio=st.floor.ratio)
    assert st.hero.def_ == 304                      # +100，对齐 checkpoint 4528 DEF=304
    assert st.hero.flags.get('魔法免疫') is True
    assert st.hero.flags.get('nowShield') == 'shield5'
