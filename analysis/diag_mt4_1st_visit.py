"""1차 MT4 방문(token[128]→[150]) 추적 — 영웅이 (7,10) redGem을 지나가는지 확인."""
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

# 快进到 token[127]
for tok in tokens[:128]:
    state = step(state, tok)

print(f"token[127] 结束: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_} yk={state.hero.keys.get('yellowKey',0)}")
print()
print(f"{'idx':>4}  {'tok':<10}  {'fl':<5}  {'from':<10}  {'to':<10}  {'hp':>5}  {'atk':>3}  {'yk':>2}  note")
print('-'*95)

for idx in range(128, 160):
    tok = tokens[idx]
    fl_before = state.current_floor
    pos_before = (state.hero.x, state.hero.y)
    hp_before = state.hero.hp
    atk_before = state.hero.atk
    yk_before = state.hero.keys.get('yellowKey', 0)

    state = step(state, tok)

    fl_after = state.current_floor
    pos_after = (state.hero.x, state.hero.y)
    hp_after = state.hero.hp
    atk_after = state.hero.atk
    yk_after = state.hero.keys.get('yellowKey', 0)

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
    if yk_after != yk_before:
        note += f"  ♦YK {yk_before}→{yk_after}"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"

    print(f"{idx:>4}  {tok:<10}  {fl_after:<5}  "
          f"({pos_before[0]},{pos_before[1]})  ({pos_after[0]},{pos_after[1]})  "
          f"{hp_after:>5}  {atk_after:>3}  {yk_after:>2}  {note}")

print()
# MT4 현재 상태
if 'MT4' in state.floors:
    mt4 = state.floors['MT4']
    print("=== MT4 entities 상태 (7,10) 근방 ===")
    for y in range(9, 12):
        for x in range(6, 11):
            e = mt4.entities[y][x]
            t = mt4.terrain[y][x]
            if e or t:
                print(f"  ({x},{y}) terrain={t} entity={e}")
