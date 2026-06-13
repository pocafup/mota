"""追踪 token[300..400] 所有事件，找 HP 从 482 崩溃到 -110 的根源。"""
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

for tok in tokens[:300]:
    state = step(state, tok)

print(f"token[299] end: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_}")
print()
print(f"{'idx':>4}  {'tok':<12}  {'fl':<6}  {'pos':<12}  {'hp':>6}  {'atk':>3}  note")
print('-'*80)

for idx in range(300, 402):
    tok = tokens[idx]
    fl_before = state.current_floor
    pos_before = (state.hero.x, state.hero.y)
    hp_before = state.hero.hp
    atk_before = state.hero.atk

    state = step(state, tok)

    fl_after = state.current_floor
    pos_after = (state.hero.x, state.hero.y)
    hp_after = state.hero.hp
    atk_after = state.hero.atk

    note = ""
    moved = pos_before != pos_after or fl_before != fl_after

    if not moved:
        dx = {'L': -1, 'R': 1, 'U': 0, 'D': 0}.get(tok, 0)
        dy = {'U': -1, 'D': 1, 'L': 0, 'R': 0}.get(tok, 0)
        nx, ny = pos_before[0] + dx, pos_before[1] + dy
        if fl_before in state.floors and 0 <= ny < 13 and 0 <= nx < 13:
            t = state.floors[fl_before].terrain[ny][nx]
            e = state.floors[fl_before].entities[ny][nx]
            note = f"BLOCKED({nx},{ny}) T={t} E={e}"
    elif fl_before != fl_after:
        note = f"FL {fl_before}→{fl_after}"
    elif hp_before != hp_after:
        note = f"HP {hp_before}→{hp_after} ({hp_after-hp_before:+d})"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"

    if note:
        print(f"{idx:>4}  {tok:<12}  {fl_after:<6}  ({pos_after[0]:>2},{pos_after[1]:>2})  "
              f"{hp_after:>6}  {atk_after:>3}  {note}")
