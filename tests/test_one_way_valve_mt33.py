"""防回头墙 / 单向阀 (MT33 flower (8,10)) 单元测试 —— 钉死「踏穿后变 noPass、回头被拒」。

机制事实来源（玩家从 live 引擎抓 core.getBlock(8,10).event.outEvent，详见
data/games51/floors/MT33.json 的 _outEvents_comment / _arrive_event_fidelity）：
  flower(168) 在 (8,10) 是单向阀：从左 (7,10) 向右穿过 (8,10)→(9,10) 后，离开 (8,10)
  触发 outEvent = [hide remove destruct + closeDoor yellowWall]（两条均无 loc → 默认作用
  于事件格 (8,10)），把 (8,10) 永久封成 yellowWall(tile1, noPass, canBreak)，不能再从右折回。

建模口径：只建 outEvent(离开封)。arrive-event 的 moveHero 被逐 token 重放吸收(no-op)、
其 false 分支封格与 outEvent 同效且 (8,9)/(8,11) 皆墙无幻影分支，故离开封即可达性等价。

本测试是 C 段「假赢」的回归闸：solver 曾重穿 (8,10) 拿格外增益再折返(真实引擎走不通)。
封进 sim 后，该回头动作必须被引擎判为撞墙原地——此测试钉死它。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

FLOWER_TILE = 168     # flower 地形（可走，noPass:false——见 noPass 矛盾已解）
YELLOW_WALL = 1       # closeDoor yellowWall → tiles.json["1"]，noPass 墙


def _mkstate_mt33_at_7_10():
    """hero 站在 (7,10)（slimeMan 已被击杀清空，模拟 route 到此格前的状态），临穿 (8,10)。"""
    f = load_floor(FLOORS / 'MT33.json')
    f.entities[10][7] = 0   # (7,10) slimeMan(216) 已清——route 到此前必已击杀，使出发格为净空地
    hero = HeroState(x=7, y=10, hp=10000, atk=999, def_=999, mdef=0,
                     gold=0, keys={}, items={}, flags={})
    return GameState(hero=hero, floors={'MT33': f}, current_floor='MT33',
                     floor_ids=FLOOR_IDS, visited_floors={'MT33'},
                     pending_floor_change=None, _floors_dir=FLOORS)


def test_flower_walkable_before_pass():
    """noPass 矛盾已解：未穿越前 (8,10) flower 是可走地形（不是 noPass）。"""
    st = _mkstate_mt33_at_7_10()
    assert st.floor.terrain[10][8] == FLOWER_TILE, '初始 (8,10) 应为 flower 地形'
    st = step(st, 'R')   # (7,10) -> (8,10)
    assert (st.hero.x, st.hero.y) == (8, 10), 'flower 可走：应踏上 (8,10)'
    assert st.floor.terrain[10][8] == FLOWER_TILE, '尚未离开，flower 未封'


def test_valve_seals_on_pass_through():
    """左→右穿过 (8,10)→(9,10)：离开 (8,10) 触发 outEvent，封成 yellowWall(noPass)。"""
    st = _mkstate_mt33_at_7_10()
    st = step(st, 'R')                       # (7,10) -> (8,10)
    assert (st.hero.x, st.hero.y) == (8, 10)
    assert st.floor.terrain[10][8] == FLOWER_TILE, '在 (8,10) 上时尚未封'

    st = step(st, 'R')                       # (8,10) -> (9,10)，离开 (8,10) 触发封格
    assert (st.hero.x, st.hero.y) == (9, 10), '应前进到 (9,10)'
    assert st.floor.terrain[10][8] == YELLOW_WALL, '离开后 (8,10) 应封成 yellowWall(tile1,noPass)'
    assert '8,10' in st.floor._suppressed_events, 'hide remove 应把 (8,10) 记入 _suppressed_events'


def test_valve_blocks_return():
    """封格后从右 (9,10) 回头穿 (8,10)：被墙挡，hero 原地不动（C 段假赢的回归闸）。"""
    st = _mkstate_mt33_at_7_10()
    st = step(st, 'R')                       # -> (8,10)
    st = step(st, 'R')                       # -> (9,10)，(8,10) 已封
    assert st.floor.terrain[10][8] == YELLOW_WALL

    st = step(st, 'L')                       # 试图 (9,10) -> (8,10)
    assert (st.hero.x, st.hero.y) == (9, 10), '回头穿已封的 (8,10) 应被拒，原地不动'


def test_valve_fires_only_once():
    """幂等：_suppressed_events 守门——封过一次后不再重复触发（防御性，封后该格已为墙不可再立其上）。"""
    st = _mkstate_mt33_at_7_10()
    st = step(st, 'R')
    st = step(st, 'R')                       # 封格
    wall_after_first = st.floor.terrain[10][8]
    # 多走几步绕路再回到 (9,10)，确认 (8,10) 维持墙、未被二次事件改写
    for mv in ('R', 'L'):                    # (9,10)->(10,10)? (10,10)=39 sword NPC，撞之不移；再 L 回 (9,10)
        st = step(st, mv)
    assert st.floor.terrain[10][8] == wall_after_first == YELLOW_WALL, '(8,10) 应稳定维持 yellowWall'
