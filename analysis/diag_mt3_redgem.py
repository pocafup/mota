"""MT3 방문(token[82]→[128]) 추적 — (2,9) redGem이 픽업되는지 확인."""
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

# 快进到 token[82]（MT2(1,9)小偷 hide 抑制修法后，进 MT3 前缀 82→83）
for tok in tokens[:83]:
    state = step(state, tok)

print(f"token[82] 结束: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_}")

# MT3 상태 확인
if 'MT3' in state.floors:
    mt3 = state.floors['MT3']
    print(f"MT3(2,9) entity={mt3.entities[9][2]} terrain={mt3.terrain[9][2]}")
print()
print(f"{'idx':>4}  {'tok':<10}  {'fl':<5}  {'from':<10}  {'to':<10}  {'hp':>5}  {'atk':>3}  note")
print('-'*90)

for idx in range(82, 130):
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
        fl = fl_before
        if fl in state.floors and 0 <= ny < 13 and 0 <= nx < 13:
            t = state.floors[fl].terrain[ny][nx]
            e = state.floors[fl].entities[ny][nx]
            note = f"BLOCKED({nx},{ny}) T={t} E={e}"
    elif fl_before != fl_after:
        note = f"→{fl_before}→{fl_after}"
    elif hp_before != hp_after:
        note = f"±HP {hp_after - hp_before:+d}"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"
    if pos_after == (2, 9) and fl_after == 'MT3':
        note += "  *** VISIT (2,9) ***"
    if tok.startswith('CHOICE'):
        note += f"  [{tok}]"

    print(f"{idx:>4}  {tok:<10}  {fl_after:<5}  "
          f"({pos_before[0]},{pos_before[1]})  ({pos_after[0]},{pos_after[1]})  "
          f"{hp_after:>5}  {atk_after:>3}  {note}")

print()
if 'MT3' in state.floors:
    mt3 = state.floors['MT3']
    print(f"MT3(2,9) entity after: {mt3.entities[9][2]}")
    print(f"영웅 pos: ({state.hero.x},{state.hero.y}), floor={state.current_floor}")
