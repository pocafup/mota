"""扫描 tok[0..1372] 找所有 MT16 到访时刻，及 (5,3) 是否有战斗。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA  = Path('data/games51')
FLOORS = DATA / 'floors'

def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'],
        def_=hero_init.get('def_', hero_init.get('def', 10)),
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
    )

tokens = load_tokens = None

def load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'), None)
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))

toks = load_tokens()
state = build_initial_state()

END = 1380
prev_floor = 'MT1'

for idx, tok in enumerate(toks[:END]):
    prev_hp = state.hero.hp
    prev_floor = state.current_floor
    prev_x, prev_y = state.hero.x, state.hero.y

    state = step(state, tok)

    cur_floor = state.current_floor

    # 打印所有涉及 MT16 的楼层切换
    if prev_floor != cur_floor and ('MT16' in (prev_floor, cur_floor)):
        print(f"tok[{idx:4d}] {tok:>12s}  {prev_floor}→{cur_floor}  pos=({state.hero.x},{state.hero.y})  HP={state.hero.hp}")

    # 在 MT16 内：打印所有 HP 变化
    if cur_floor == 'MT16' and state.hero.hp != prev_hp:
        print(f"  tok[{idx:4d}] HP {prev_hp}→{state.hero.hp} ({state.hero.hp-prev_hp:+d})  pos=({state.hero.x},{state.hero.y})")

    # 在 MT16 内：打印任何移动到 (5,3)
    if cur_floor == 'MT16' and state.hero.x == 5 and state.hero.y == 3:
        marker = " *** (5,3) zombie pos ***" if state.hero.hp != prev_hp else " (5,3) reached, no fight"
        print(f"  tok[{idx:4d}] at (5,3){marker}  HP={state.hero.hp}")

# 检查 MT16 (5,3) 状态
mt16 = state.floors.get('MT16')
if mt16:
    ent = None
    try:
        ent = mt16.entities.get((5,3), 'EMPTY')
    except:
        pass
    print(f"\nMT16 (5,3) entity after tok[{END-1}]: {ent}")
    print(f"MT16 visited_floors: {'MT16' in state.visited_floors}")
