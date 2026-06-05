"""冰魔法 snow 全链单元测试（MT13 真实地图）。

机制事实来源（详见 docs/mechanics_51.md §K / items.json）：
  - snow cls=constants → 永久持有、【重复使用不消耗】(无 _afterUseItem 递减)。
  - useItemEffect: 清【英雄四正方向】相邻 lava(tile5) → terrain 置 0（空地，永久可通行）。
    lava tile 经 _id_to_tile_full['lava'] 数据驱动解析，不硬编码。
  - 来源 MT35(6,7) magicDragon afterBattle → setBlock snow(6,6) 获取。
  - 全塔 lava 仅 MT13(80格)/MT26(19格) 两处；lava 是 noPass 障碍，不扣血(扣血是 lavaNet，本塔无)。

全链：走到 lava 边 → snow 清相邻 lava → 走进原 lava 格 → 再 snow 清下一圈（含重复使用）。
MT13 唯一自然切入点 = (6,10) 可站，正上 (6,9) 为 lava，往里 (6,8)(5,9)(7,9) 连片 lava。

⚠ 本测试预期行为待玩家在真实引擎核对一次（snow 实际清除范围/是否可重复/清后是否可踩）。
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))


def _mkstate_snow(fid, x, y):
    f = load_floor(FLOORS / f'{fid}.json')
    f._first_arrive_done = True                       # 隔离 snow 机制，跳过首次到达事件
    hero = HeroState(x=x, y=y, hp=99999, atk=1, def_=1, mdef=0,
                     gold=0, keys={}, items={'snow': 1}, flags={})
    return GameState(hero=hero, floors={fid: f}, current_floor=fid,
                     floor_ids=FLOOR_IDS, visited_floors={fid},
                     pending_floor_change=None, _floors_dir=FLOORS)


def test_snow_def_is_constants_reusable():
    """snow 数据声明：cls=constants（→ 永久不消耗的事实依据）。"""
    snow = json.loads((DATA / 'items.json').read_text(encoding='utf-8'))['snow']
    assert snow['cls'] == 'constants'


def test_snow_clears_adjacent_lava_and_is_walkable():
    """走到 lava 边(6,10) → snow 清正上 lava(6,9) → 该格变空地且可踩入。"""
    st = _mkstate_snow('MT13', 6, 10)
    lava = st.floor._id_to_tile_full['lava']
    assert st.floor.terrain[9][6] == lava             # (6,9) 初始为 lava

    st = step(st, 'ITEM:54')                           # 用 snow（step 纯函数→须重取 terrain）
    assert st.floor.terrain[9][6] == 0                # (6,9) lava→空地(可通行)
    assert st.hero.items.get('snow') == 1             # 非消耗：snow 仍在

    st = step(st, 'U')                                 # (6,10)→(6,9) 走进原 lava 格
    assert (st.hero.x, st.hero.y) == (6, 9)           # 清后可通行(可达性实时重算)


def test_snow_reuse_clears_next_ring():
    """重复使用：进到 (6,9) 后再 snow，清下一圈 (6,8)/(5,9)/(7,9)，snow 仍不消耗。"""
    st = _mkstate_snow('MT13', 6, 10)
    lava = st.floor._id_to_tile_full['lava']

    st = step(st, 'ITEM:54')                           # 清 (6,9)
    st = step(st, 'U')                                 # 进 (6,9)
    assert (st.hero.x, st.hero.y) == (6, 9)
    ter = st.floor.terrain
    assert ter[8][6] == lava and ter[9][5] == lava and ter[9][7] == lava

    st = step(st, 'ITEM:54')                           # 第二次 snow（重复使用）
    ter = st.floor.terrain
    assert ter[8][6] == 0 and ter[9][5] == 0 and ter[9][7] == 0   # 下一圈三格清除
    assert st.hero.items.get('snow') == 1             # 重复使用仍不消耗

    st = step(st, 'U')                                 # 继续往里 (6,9)→(6,8)
    assert (st.hero.x, st.hero.y) == (6, 8)


def test_snow_only_clears_four_directions():
    """只清四【正】方向：对角 lava 不清。在 (6,10) 用 snow 只动 (6,9)，对角 (5,9)/(7,9) 仍 lava。"""
    st = _mkstate_snow('MT13', 6, 10)
    lava = st.floor._id_to_tile_full['lava']
    assert st.floor.terrain[9][5] == lava and st.floor.terrain[9][7] == lava   # (5,9)(7,9) 对角

    st = step(st, 'ITEM:54')
    ter = st.floor.terrain
    assert ter[9][6] == 0                              # 正上清除
    assert ter[9][5] == lava and ter[9][7] == lava    # 对角不清（仅四正方向）


def test_snow_no_lava_is_noop():
    """英雄四周无 lava 时 snow 无副作用（不报错、不改地图）。"""
    st = _mkstate_snow('MT13', 6, 11)                 # 第11行可站、四周无 lava
    before = [row[:] for row in st.floor.terrain]
    st = step(st, 'ITEM:54')
    assert st.floor.terrain == before
    assert st.hero.items.get('snow') == 1


def test_snow_not_held_is_noop():
    """持有守卫：背包无 snow 时用 snow = no-op（不清 lava）。solver 正确性必须。"""
    st = _mkstate_snow('MT13', 6, 10)
    st.hero.items.pop('snow', None)                   # 不持有 snow
    lava = st.floor._id_to_tile_full['lava']
    assert st.floor.terrain[9][6] == lava

    st = step(st, 'ITEM:54')                           # 未持有 → 不生效
    assert st.floor.terrain[9][6] == lava             # (6,9) 仍是 lava，未被清除
