"""13个检查点永久断言：重放存档至每个 token 里程碑，校验 floor/HP/ATK/DEF 与真值。

真值来源：玩家在真实游戏引擎中实测，是金标准。对不上必须 FAIL。
禁止为让测试变绿而修改真值。
"""
import json
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'

GROUND_TRUTH = [
    # (token_idx, floor, hp, atk, def_, yk, bk)
    # yk/bk: 玩家网站实测金标准。None = 尚未提供真值，不断言。
    (100,  'MT3',   800, 10, 10,  3, None),
    (200,  'MT4',   666, 20, 10,  0,    1),
    (300,  'MT5',   604, 21, 10,  5, None),
    (400,  'MT7',   304, 21, 10,  4, None),
    (500,  'MT9',   290, 21, 10,  2, None),
    (600,  'MT3',   305, 23, 22,  1, None),
    (700,  'MT8',   218, 25, 23,  1, None),
    (800,  'MT10',  229, 26, 25, None, None),
    (900,  'MT7',   254, 26, 27, None, None),
    (1000, 'MT10',  304, 27, 27, None, None),
    (1100, 'MT1',   546, 27, 27, None, None),
    (1200, 'MT10',  510, 27, 27, None, None),
    (1300, 'MT14',  785, 42, 30, None, None),
]

MAX_TOKEN = max(t for t, *_ in GROUND_TRUTH)


def _build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def _load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'), None)
    if route_path is None:
        route_path = next((Path(__file__).parent.parent).glob('51_*.h5route'), None)
    if route_path is None:
        pytest.skip('存档文件 51_*.h5route 未找到')
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


@pytest.mark.parametrize('token_idx,exp_floor,exp_hp,exp_atk,exp_def,exp_yk,exp_bk', GROUND_TRUTH)
def test_checkpoint(token_idx, exp_floor, exp_hp, exp_atk, exp_def, exp_yk, exp_bk):
    """重放到 token_idx，断言 floor/HP/ATK/DEF/yk/bk 与真值一致。"""
    tokens = _load_tokens()
    state = _build_initial_state()

    for idx, tok in enumerate(tokens[:token_idx]):
        state = step(state, tok)

    sim_floor = state.current_floor
    sim_hp    = state.hero.hp
    sim_atk   = state.hero.atk
    sim_def   = state.hero.def_
    sim_yk    = state.hero.keys.get('yellowKey', 0)
    sim_bk    = state.hero.keys.get('blueKey', 0)

    errors = []
    if sim_floor != exp_floor:
        errors.append(f'floor: sim={sim_floor} 真值={exp_floor}')
    if sim_hp != exp_hp:
        errors.append(f'HP: sim={sim_hp} 真值={exp_hp} 差={sim_hp - exp_hp:+d}')
    if sim_atk != exp_atk:
        errors.append(f'ATK: sim={sim_atk} 真值={exp_atk} 差={sim_atk - exp_atk:+d}')
    if sim_def != exp_def:
        errors.append(f'DEF: sim={sim_def} 真值={exp_def} 差={sim_def - exp_def:+d}')
    if exp_yk is not None and sim_yk != exp_yk:
        errors.append(f'yellowKey: sim={sim_yk} 真值={exp_yk} 差={sim_yk - exp_yk:+d}')
    if exp_bk is not None and sim_bk != exp_bk:
        errors.append(f'blueKey: sim={sim_bk} 真值={exp_bk} 差={sim_bk - exp_bk:+d}')

    assert not errors, (
        f'token[{token_idx}] 检查点失败:\n  ' + '\n  '.join(errors)
    )
