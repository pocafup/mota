"""追踪 MT41 (10,2) 隐藏怪触发链：tok4885..4921 逐 token 打印
floor/pos/terrain[2][10]/entities[2][10]/entities[5][6]/flag:41/visited MT42/关键道具。
目的：实证英雄如何走到 (9,2)、用哪个 token 触发隐藏怪现身、哪个 token 打它、
afterBattle 是否放下 downFly@(6,5)。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    kb_raw = json.loads((DATA / 'replay_keybindings.json').read_text(encoding='utf-8'))
    key_bindings = {int(k): v for k, v in kb_raw.get('bindings', {}).items()}
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
        _key_bindings=key_bindings,
    )


route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw))
tokens = parse_rle_route(LZString().decompressFromBase64(outer['route']))

state = build_initial_state()
LO, HI = 4885, 4921
for idx, tok in enumerate(tokens[:HI + 1]):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    state = step(state, tok)
    if LO <= idx <= HI:
        h = state.hero
        f = state.floors.get('MT41')
        t102 = f.terrain[2][10] if f else '-'
        e102 = f.entities[2][10] if f else '-'
        e65 = f.entities[5][6] if f else '-'
        flag41 = h.flags.get('41', 0)
        vis42 = 'MT42' in state.visited_floors
        keyitems = {k: h.items.get(k, 0) for k in ('downFly', 'centerFly', 'fly')}
        print(f"tok[{idx}] {tok:10} {pf}{pp}->{state.current_floor}({h.x},{h.y}) "
              f"ter[2][10]={t102} ent[2][10]={e102} ent[5][6]={e65} "
              f"flag41={flag41} vis42={vis42} {keyitems}")
