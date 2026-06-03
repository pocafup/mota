"""追踪 token[295..320] 的 ATK 变化，找真值 ATK=21 对应的位置。"""
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
tokens = parse_rle_route(decompress(outer['route']))[:340]

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

for tok in tokens[:295]:
    state = step(state, tok)

print(f"token[294] 结束: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_}")
print()
print(f"{'idx':>4}  {'tok':<12}  {'fl':<6}  {'pos':<10}  {'hp':>5}  {'atk':>3}  {'def':>4}  note")
print('-'*75)

for idx in range(295, 330):
    tok = tokens[idx]
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
        note = f"→{fl_before}→{fl_after}"
    elif hp_before != hp_after:
        note = f"±HP {hp_after - hp_before:+d}"

    if atk_after != atk_before:
        note += f"  ★★ATK {atk_before}→{atk_after}"
    if def_after != def_before:
        note += f"  ★DEF {def_before}→{def_after}"

    print(f"{idx:>4}  {tok:<12}  {fl_after:<6}  "
          f"({pos_after[0]},{pos_after[1]})  "
          f"{hp_after:>5}  {atk_after:>3}  {def_after:>4}  {note}")
