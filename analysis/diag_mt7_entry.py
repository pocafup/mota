"""精确追踪 tok[378..410] 的内容和英雄状态，理解 MT7 导航。"""
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

print("Tokens 378-410:")
for i in range(378, 411):
    print(f"  [{i}] {tokens[i]!r}")

print()
print("Running simulation to tok[380]...")

hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
floor = load_floor(FLOORS / 'MT1.json')
hero = HeroState(
    x=hero_init['loc']['x'], y=hero_init['loc']['y'],
    hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
    mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
    keys={}, items=dict(hero_init.get('items', {})),
    flags=dict(hero_init.get('flags', {})),
)
state = GameState(
    hero=hero, floors={'MT1': floor}, current_floor='MT1',
    floor_ids=FLOOR_IDS, visited_floors={'MT1'},
    pending_floor_change=None, _floors_dir=FLOORS,
)

for i in range(380):
    state = step(state, tokens[i])

print(f"State at tok[380] entry: floor={state.current_floor}, pos=({state.hero.x},{state.hero.y}), HP={state.hero.hp}, keys={dict(state.hero.keys)}")
print()

# Detailed trace 380..410
for i in range(380, 410):
    tok = tokens[i]
    old_hp = state.hero.hp
    old_pos = (state.hero.x, state.hero.y)
    old_floor = state.current_floor
    old_keys = dict(state.hero.keys)

    state = step(state, tok)

    new_pos = (state.hero.x, state.hero.y)
    new_floor = state.current_floor
    new_keys = dict(state.hero.keys)

    events = []
    if new_floor != old_floor:
        events.append(f"FLOOR {old_floor}→{new_floor}")

    if new_pos != old_pos:
        events.append(f"move {old_pos}→{new_pos}")
    else:
        # Determine why blocked
        if new_floor in state.floors:
            fl = state.floors[new_floor]
            dx, dy = 0, 0
            if tok == 'U': dy = -1
            elif tok == 'D': dy = 1
            elif tok == 'L': dx = -1
            elif tok == 'R': dx = 1
            nx, ny = old_pos[0] + dx, old_pos[1] + dy
            if 0 <= ny < fl.height and 0 <= nx < fl.width:
                tile = fl.map[ny][nx]
                ent = fl.entities.get((nx, ny), 0)
                events.append(f"BLOCKED→({nx},{ny}) tile={tile} ent={ent}")
            else:
                events.append(f"BLOCKED→({nx},{ny}) OUT_OF_BOUNDS")
        else:
            events.append(f"BLOCKED @{old_pos}")

    if state.hero.hp != old_hp:
        events.append(f"HP {old_hp}→{state.hero.hp} ({state.hero.hp-old_hp:+d})")
    key_diff = {k: new_keys.get(k,0)-old_keys.get(k,0) for k in set(list(old_keys)+list(new_keys))}
    for k, d in key_diff.items():
        if d != 0:
            events.append(f"{k} {old_keys.get(k,0)}→{new_keys.get(k,0)}")

    print(f"  [{i}] {tok:3s} | floor={new_floor:4s} pos={str(new_pos):10s} HP={state.hero.hp:4d} | {', '.join(events)}")
