"""列出 1318-token 重放中所有切层事件，含英雄属性快照。"""
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
tokens = parse_rle_route(decompress(outer['route']))[:1318]

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

print(f"{'idx':>4}  {'tok':<14} {'from':<8}  {'to':<8}  {'pos_after':<12} {'hp':>5} {'atk':>5} {'def':>4}  keys")
print('-'*90)
for idx, tok in enumerate(tokens):
    fl_before = state.current_floor
    state = step(state, tok)
    fl_after = state.current_floor
    if fl_before != fl_after or tok.startswith('FLOOR:'):
        pos = f"({state.hero.x},{state.hero.y})"
        yk = state.hero.keys.get('yellowKey', 0)
        bk = state.hero.keys.get('blueKey', 0)
        rk = state.hero.keys.get('redKey', 0)
        print(f"{idx:>4}  {tok:<14} {fl_before:<8}  {fl_after:<8}  {pos:<12} {state.hero.hp:>5} {state.hero.atk:>5} {state.hero.def_:>4}  Y={yk} B={bk} R={rk}")

print(f"\n最终: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_}")
