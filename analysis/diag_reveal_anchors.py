"""验 reveal 链锚点与下游：tok4857现身/4858在(10,2)/4916拾downFly/4921下飞MT0/coin1768金/回MT1。
逐 token 重放，打印关键 token 的 floor+坐标+HP+金+downFly库存+visited(MT42)。不分析。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'
floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
kb_raw = json.loads((DATA / 'replay_keybindings.json').read_text(encoding='utf-8'))
key_bindings = {int(k): v for k, v in kb_raw.get('bindings', {}).items()}
mt1 = load_floor(FLOORS / 'MT1.json')
hero = HeroState(x=hero_init['loc']['x'], y=hero_init['loc']['y'], hp=hero_init['hp'],
                 atk=hero_init['atk'], def_=hero_init['def'], mdef=hero_init.get('mdef', 0),
                 gold=hero_init.get('gold', 0), keys={}, items=dict(hero_init.get('items', {})),
                 flags=dict(hero_init.get('flags', {})))
state = GameState(hero=hero, floors={'MT1': mt1}, current_floor='MT1', floor_ids=floor_ids,
                  visited_floors={'MT1'}, pending_floor_change=None, _floors_dir=FLOORS,
                  _key_bindings=key_bindings)
route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw))
tokens = parse_rle_route(LZString().decompressFromBase64(outer['route']))

WATCH = {4855, 4856, 4857, 4858, 4859, 4914, 4915, 4916, 4917,
         4919, 4920, 4921, 4922, 4923, 4924, 4925, 5155, 5156}


def dfly(s):
    return s.hero.items.get('downFly', 0)


prev_gold = None
for idx, tok in enumerate(tokens):
    pg = state.hero.gold
    state = step(state, tok)
    if idx in WATCH:
        mt42 = 'MT42' in state.visited_floors
        gd = state.hero.gold - pg
        gds = f' 金+{gd}' if gd else ''
        print(f"tok{idx:5} {tok:8} | {state.current_floor:4}({state.hero.x:2},{state.hero.y:2}) "
              f"HP={state.hero.hp:6} 金={state.hero.gold:6} downFly={dfly(state)} "
              f"visitedMT42={mt42}{gds}")
