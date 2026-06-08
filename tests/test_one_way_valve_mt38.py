"""防回头墙 / 单向阀 (MT38 flower (2,5)) 单元测试 —— 钉死「踏穿后变 noPass、回头被拒」。

机制事实来源：与 MT33(8,10) 同一开关、同机制（玩家 2026-06-05 提供 live
core.getBlock(8,10).event.outEvent 时，脚本 switch core.status.floorId 同时含 MT33 / MT38
两 case；原始脚本存档于 data/games51/floors/MT33.json 的 _arrive_event_fidelity，MT38
部分另见 MT38.json 的 _outEvents_comment / _arrive_event_fidelity）。

  flower(168) 在 (2,5) 是单向阀：从上 (2,4) 向下穿过 (2,5)→(2,6) 后，离开 (2,5) 触发
  outEvent = [hide remove destruct + closeDoor yellowWall]（两条均无 loc → 默认作用于
  事件格 (2,5)），把 (2,5) 永久封成 yellowWall(tile1, noPass, canBreak)，不能再从下折回。
  与 MT33(8,10) 镜像同构（横向 right → 纵向 down）。几何：(2,4)/(2,6) 地板、(1,5)/(3,5) 皆墙。

建模口径：只建 outEvent(离开封)。arrive-event 的 moveHero[down:1] 被逐 token 重放吸收
(no-op)、其 false 分支封格与 outEvent 同效——封时机『进入 vs 离开』不改可达性（arrive 封格
亦不阻止英雄移走，净效果均为『穿一次后封、回不来』），且 (1,5)/(3,5) 皆墙无幻影分支，
故离开封即可达性等价。本测试是单向阀回归闸（防 solver 重穿薅增益再折返的假赢）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

FLOWER_TILE = 168     # flower 地形（可走，noPass:false）
YELLOW_WALL = 1       # closeDoor yellowWall → tiles.json["1"]，noPass 墙


def _mkstate_mt38_at_2_4():
    """hero 站在 (2,4)（净空地），临穿 (2,5) 单向阀。允许方向 = down（上→下）。"""
    f = load_floor(FLOORS / 'MT38.json')
    hero = HeroState(x=2, y=4, hp=10000, atk=999, def_=999, mdef=0,
                     gold=0, keys={}, items={}, flags={})
    return GameState(hero=hero, floors={'MT38': f}, current_floor='MT38',
                     floor_ids=FLOOR_IDS, visited_floors={'MT38'},
                     pending_floor_change=None, _floors_dir=FLOORS)


def test_flower_walkable_before_pass():
    """未穿越前 (2,5) flower 是可走地形（不是 noPass）。"""
    st = _mkstate_mt38_at_2_4()
    assert st.floor.terrain[5][2] == FLOWER_TILE, '初始 (2,5) 应为 flower 地形'
    st = step(st, 'D')   # (2,4) -> (2,5)
    assert (st.hero.x, st.hero.y) == (2, 5), 'flower 可走：应踏上 (2,5)'
    assert st.floor.terrain[5][2] == FLOWER_TILE, '尚未离开，flower 未封'


def test_valve_seals_on_pass_through():
    """上→下穿过 (2,5)→(2,6)：离开 (2,5) 触发 outEvent，封成 yellowWall(noPass)。"""
    st = _mkstate_mt38_at_2_4()
    st = step(st, 'D')                       # (2,4) -> (2,5)
    assert (st.hero.x, st.hero.y) == (2, 5)
    assert st.floor.terrain[5][2] == FLOWER_TILE, '在 (2,5) 上时尚未封'

    st = step(st, 'D')                       # (2,5) -> (2,6)，离开 (2,5) 触发封格
    assert (st.hero.x, st.hero.y) == (2, 6), '应前进到 (2,6)'
    assert st.floor.terrain[5][2] == YELLOW_WALL, '离开后 (2,5) 应封成 yellowWall(tile1,noPass)'
    assert '2,5' in st.floor._suppressed_events, 'hide remove 应把 (2,5) 记入 _suppressed_events'


def test_valve_blocks_return():
    """封格后从下 (2,6) 回头穿 (2,5)：被墙挡，hero 原地不动（防回头）。"""
    st = _mkstate_mt38_at_2_4()
    st = step(st, 'D')                       # -> (2,5)
    st = step(st, 'D')                       # -> (2,6)，(2,5) 已封
    assert st.floor.terrain[5][2] == YELLOW_WALL

    st = step(st, 'U')                       # 试图 (2,6) -> (2,5)
    assert (st.hero.x, st.hero.y) == (2, 6), '回头穿已封的 (2,5) 应被拒，原地不动'


def test_valve_fires_only_once():
    """幂等：封过一次后 (2,5) 稳定维持墙——绕 (1,6)↔(2,6) 来回不重新触发。"""
    st = _mkstate_mt38_at_2_4()
    st = step(st, 'D')
    st = step(st, 'D')                       # 封格
    wall_after_first = st.floor.terrain[5][2]
    for mv in ('L', 'R'):                    # (2,6)->(1,6)空地->(2,6)，均不踩 (2,5)
        st = step(st, mv)
    assert st.floor.terrain[5][2] == wall_after_first == YELLOW_WALL, '(2,5) 应稳定维持 yellowWall'
