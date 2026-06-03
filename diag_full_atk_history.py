"""追踪全程 token[0..310] 内所有楼层切换、ATK 变化和 HP 变化。"""
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

print(f"初始: floor={state.current_floor} hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_}")
print()
print(f"{'idx':>4}  {'tok':<12}  {'fl':<6}  {'pos':<12}  {'hp':>5}  {'atk':>3}  note")
print('-'*75)

for idx, tok in enumerate(tokens[:310]):
    fl_before = state.current_floor
    hp_before = state.hero.hp
    atk_before = state.hero.atk
    def_before = state.hero.def_

    state = step(state, tok)

    fl_after = state.current_floor
    hp_after = state.hero.hp
    atk_after = state.hero.atk
    def_after = state.hero.def_

    note = ""
    if fl_before != fl_after:
        note = f"FL {fl_before}→{fl_after}"
    elif hp_before != hp_after:
        note = f"HP {hp_before}→{hp_after} ({hp_after-hp_before:+d})"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"
    if def_after != def_before:
        note += f"  ★DEF {def_before}→{def_after}"

    if note:
        print(f"{idx:>4}  {tok:<12}  {fl_after:<6}  ({state.hero.x:>2},{state.hero.y:>2})  "
              f"{hp_after:>5}  {atk_after:>3}  {note}")
