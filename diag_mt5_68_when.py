"""逐 token 追踪 MT5.entities[8][6] 何时从 201 变为 0。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(decompress(raw))
tokens = parse_rle_route(decompress(outer['route']))

hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
floor = load_floor(FLOORS / 'MT1.json')
hero = HeroState(
    x=hero_init['loc']['x'], y=hero_init['loc']['y'],
    hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
    mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
    keys={}, items=dict(hero_init.get('items', {})), flags=dict(hero_init.get('flags', {})),
)
state = GameState(hero=hero, floors={'MT1': floor}, current_floor='MT1',
    floor_ids=FLOOR_IDS, visited_floors={'MT1'}, pending_floor_change=None, _floors_dir=FLOORS)

prev_val = None
for idx, tok in enumerate(tokens[:220]):
    state = step(state, tok)
    mt5 = state.floors.get('MT5')
    if mt5 is None:
        continue
    cur_val = mt5.entities[8][6]
    if prev_val is None:
        prev_val = cur_val
        print(f"MT5 first loaded at token[{idx}]: entities[8][6]={cur_val}  floor={state.current_floor} pos=({state.hero.x},{state.hero.y})")
    elif cur_val != prev_val:
        print(f"token[{idx}] tok={tok!r}: entities[8][6] changed {prev_val}→{cur_val}  floor={state.current_floor} pos=({state.hero.x},{state.hero.y})")
        prev_val = cur_val
