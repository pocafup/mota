"""打印前 300 token 中所有切层事件和 ATK/DEF 变化。"""
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
tokens = parse_rle_route(decompress(outer['route']))[:310]

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

print(f"初始: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_}")
print()
print(f"{'idx':>4}  {'tok':<12}  {'fl':<6}  {'pos':<10}  {'hp':>5}  {'atk':>3}  {'def_':>4}  note")
print('-'*80)

for idx, tok in enumerate(tokens[:310]):
    fl_before = state.current_floor
    pos_before = (state.hero.x, state.hero.y)
    hp_before = state.hero.hp
    atk_before = state.hero.atk
    def_before = state.hero.def_

    state = step(state, tok)

    fl_after = state.current_floor
    pos_after = (state.hero.x, state.hero.y)
    hp_after = state.hero.hp
    atk_after = state.hero.atk
    def_after = state.hero.def_

    note = ""
    if fl_before != fl_after:
        note = f"→{fl_before}→{fl_after}"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"
    if def_after != def_before:
        note += f"  ★DEF {def_before}→{def_after}"
    if tok.startswith('CHOICE'):
        note += f"  [{tok}]"

    if note:
        print(f"{idx:>4}  {tok:<12}  {fl_after:<6}  "
              f"({pos_after[0]},{pos_after[1]})  "
              f"{hp_after:>5}  {atk_after:>3}  {def_after:>4}  {note}")
