"""MT32/MT40 剧情 boss 强制战斗(force)单元测试 + 配套机制(setEnemy/setBlock字符串/searchBlock)。

锁定全塔铁律【例外】(见 docs/mechanics_51.md §M)：
  - battle 指令 = 强制战斗，绕过 canBattle 拦截：damage>=hp 也照打，英雄可被打死。
  - 普通战斗(走格触怪)的 damage>=hp 拦截【保持不变】——这条若被"修绿"即违背玩家实测，
    test_normal_battle_interception_unchanged 永久看守。
  - 骑士队长的先攻不是常驻，而是 setEnemy special=1 临时赋予、打完 setEnemy special=0 还原。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import (
    GameState, HeroState, load_floor,
    _execute_instruction, _eval_condition, _search_block_count,
    _forced_battle, _build_monster, _fight_monster,
)
from sim.combat import PlayerState, compute_combat

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

SET_CHARGE = {'type': 'setEnemy', 'id': 'yellowKnight', 'name': 'special', 'value': '1'}
CLR_CHARGE = {'type': 'setEnemy', 'id': 'yellowKnight', 'name': 'special', 'value': '0'}


def _mkstate(fid, hp, atk, df):
    f = load_floor(FLOORS / f'{fid}.json')
    hero = HeroState(x=6, y=6, hp=hp, atk=atk, def_=df, mdef=0,
                     gold=0, keys={}, items={}, flags={})
    return GameState(hero=hero, floors={fid: f}, current_floor=fid,
                     floor_ids=FLOOR_IDS, visited_floors={fid},
                     pending_floor_change=None, _floors_dir=FLOORS)


def test_setenemy_grants_charge_attack():
    """setEnemy special=1 临时赋予先攻；损血随之 +per_damage；special=0 还原。"""
    st = _mkstate('MT32', 10000, 200, 100)
    assert _build_monster(st, 'yellowKnight').special == []      # 基础无特技
    d0 = compute_combat(PlayerState(10000, 200, 100, 0),
                        _build_monster(st, 'yellowKnight')).damage
    assert d0 == 0                                               # 200atk 一刀秒(def50)，无先攻零损
    _execute_instruction(st, SET_CHARGE, 0, 0)
    assert st._enemy_overrides['yellowKnight']['special'] == [1]
    d1 = compute_combat(PlayerState(10000, 200, 100, 0),
                        _build_monster(st, 'yellowKnight')).damage
    assert d1 == 50                                             # 先攻多挨一刀 per=150-100=50
    _execute_instruction(st, CLR_CHARGE, 0, 0)
    assert st._enemy_overrides['yellowKnight']['special'] == []


def test_canbattle_condition():
    """core.canBattle('id') = 能击杀且不致死(damage != null && damage < hp)。"""
    st = _mkstate('MT32', 10000, 200, 100)
    _execute_instruction(st, SET_CHARGE, 0, 0)
    assert _eval_condition("core.canBattle('yellowKnight')", st) is True
    st_low = _mkstate('MT32', 30, 200, 100)
    _execute_instruction(st_low, SET_CHARGE, 0, 0)
    assert _eval_condition("core.canBattle('yellowKnight')", st_low) is False


def test_forced_battle_applies_damage_and_gold():
    st = _mkstate('MT32', 10000, 200, 100)
    _execute_instruction(st, SET_CHARGE, 0, 0)
    _forced_battle(st, 'yellowKnight')
    assert st.hero.hp == 9950        # 10000 - 50
    assert st.hero.gold == 100       # yellowKnight gold


def test_forced_battle_bypasses_canbattle_can_kill():
    """force 例外：damage>=hp 也强制开打，英雄可被打死(hp<=0)。"""
    st = _mkstate('MT32', 30, 200, 100)
    _execute_instruction(st, SET_CHARGE, 0, 0)
    _forced_battle(st, 'yellowKnight')
    assert st.hero.hp == -20         # 30 - 50，不拦截


def test_normal_battle_interception_unchanged():
    """【铁律不变】普通走格战斗：damage>=hp 必须拦截，英雄原地不动、状态全不变。"""
    st = _mkstate('MT32', 100, 200, 100)
    f = st.floor
    f.entities[3][3] = 227           # redKnight：对 100hp 英雄 damage=130 >= hp
    f.terrain[3][3] = 0
    snap = (st.hero.hp, st.hero.gold, st.hero.x, st.hero.y, f.entities[3][3])
    _fight_monster(st, 3, 3)
    assert (st.hero.hp, st.hero.gold, st.hero.x, st.hero.y, f.entities[3][3]) == snap


def test_setblock_string_ids():
    """setBlock number 接受字符串 id：门/墙/地形不再被误置 0。"""
    st = _mkstate('MT32', 10000, 200, 100)
    f = st.floor
    _execute_instruction(st, {'type': 'setBlock', 'number': 'specialDoor', 'loc': [[0, 0]]}, 0, 0)
    _execute_instruction(st, {'type': 'setBlock', 'number': 'yellowWall', 'loc': [[1, 0]]}, 0, 0)
    _execute_instruction(st, {'type': 'setBlock', 'number': 'yellowKnight', 'loc': [[2, 0]]}, 0, 0)
    assert f.terrain[0][0] == 85       # specialDoor
    assert f.terrain[0][1] == 1        # yellowWall（标准墙）
    assert f.entities[0][2] == 226     # yellowKnight（实体层）


def test_searchblock_counts_target_floor():
    """searchBlock('whiteWall2','MT23').length：MT23 默认仍有 whiteWall2 → 小偷暗道默认不开。"""
    st = _mkstate('MT32', 10000, 200, 100)
    assert _search_block_count(st, 'whiteWall2', 'MT23') > 0
    assert _eval_condition("(core.searchBlock('whiteWall2', 'MT23').length > 0)", st) is True


# ─── MT40 骑士队长 boss：13 场强制 battle（§M.1，force=true 全程先攻）──────────────
from sim.simulator import step


def test_mt40_boss_thirteen_waves():
    """踩 (6,7) 触发 events['6,7']：12 小怪 + 队长本人 = 13 场 battle 依次力斩。
    断言 kill_count+13、gold+700(35×3+45×3+55×3+65×3+100)、flag:402、setBlock 奖励与楼梯。
    全程大属性英雄不死，仅验证演出指令链的状态转移忠实展开。"""
    st = _mkstate('MT40', 100000, 10000, 10000)
    st.hero.x, st.hero.y = 6, 6                  # 楼梯下方，向下踩入 (6,7) 触发
    st = step(st, 'D')
    f = st.floor
    assert (st.hero.x, st.hero.y) == (6, 7)
    assert st.hero.kill_count == 13
    assert st.hero.gold == 700                   # 5 类怪金币合计
    assert st.hero.flags.get('402') is True      # flag:402=true → events[6,1] 放行下楼
    assert f.terrain[1][6] == 87                 # setBlock 87 @ [6,1] 上楼梯(terrain 层)
    assert '6,7' in f._suppressed_events          # hide remove → 事件不再触发
    # 12 小怪原位被覆写为掉落道具(entities 层)
    for x in (2, 3, 4):
        assert f.entities[2][x] == 21            # swordsman→yellowKey
    for x in (8, 9, 10):
        assert f.entities[2][x] == 27            # redKnight→redGem
    for x in (3, 4, 5):
        assert f.entities[4][x] == 32            # ghostSkeleton→bluePotion
    for x in (7, 8, 9):
        assert f.entities[4][x] == 28            # soldier→blueGem


def test_mt40_boss_can_kill_underpowered_hero():
    """force 例外贯穿全队：能破防但血薄(damage>=hp)时英雄会在 battle 中被打死(hp<=0)，
    绝不被普通拦截分支救下原地不动。atk 须>怪防才会真正开打(否则 hero_per==0，§M.1 该格不可达)。"""
    st = _mkstate('MT40', 10, 100, 0)            # 破得了防(100>30)但血薄无防，必死于首批鬼战士
    st.hero.x, st.hero.y = 6, 6
    st = step(st, 'D')
    assert st.hero.hp <= 0                        # 强制开打致死，验证未走普通拦截分支


# ─── snow 冰魔法：清英雄四方向相邻 lava → 永久空地（§K.4，数据驱动 lava tile）──────────
def test_snow_clears_adjacent_lava():
    """ITEM:54(snow) 把英雄四方相邻的 lava(tile 经 _id_to_tile_full['lava'] 解析)永久变 0；
    非相邻 lava 不动。用 MT13 真实 lava 场，受控放置英雄于一被 lava 环绕格。"""
    f = load_floor(FLOORS / 'MT13.json')
    lava = f._id_to_tile_full['lava']
    assert lava == 5
    hx, hy = 6, 2                                # 四邻：上(6,1)=lava 左(5,2)=lava 右(7,2)=lava 下(6,3)=墙
    f.terrain[hy][hx] = 0                        # 英雄脚下设为空地（如已被前一步 snow 清出）
    hero = HeroState(x=hx, y=hy, hp=1000, atk=10, def_=10, mdef=0,
                     gold=0, keys={}, items={'snow': 1}, flags={})
    st = GameState(hero=hero, floors={'MT13': f}, current_floor='MT13',
                   floor_ids=FLOOR_IDS, visited_floors={'MT13'},
                   pending_floor_change=None, _floors_dir=FLOORS)
    # 记录受控场景的相邻 lava 与一个远处 lava
    adj_lava = [(hx + dx, hy + dy) for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                if f.terrain[hy + dy][hx + dx] == lava]
    assert len(adj_lava) == 3                    # 上/左/右三面 lava，下面是墙
    far = (1, 1)
    assert f.terrain[far[1]][far[0]] == lava
    st = step(st, 'ITEM:54')
    fr = st.floor
    for lx, ly in adj_lava:
        assert fr.terrain[ly][lx] == 0           # 相邻 lava 清成空地
    assert fr.terrain[far[1]][far[0]] == lava    # 远处 lava 不受影响
