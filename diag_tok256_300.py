"""最小诊断：打印 tok[256..300] 轨迹。预热每50步一行心跳，若挂死即可定位。"""
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
print(f"路线总 token 数: {len(tokens)}", flush=True)

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

print("=== 预热 tok[0..255]（每50步一行）===", flush=True)
for i in range(256):
    if i % 50 == 0:
        print(f"  tok[{i:3d}] floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
              f"HP={state.hero.hp} ATK={state.hero.atk} DEF={state.hero.def_}", flush=True)
    state = step(state, tokens[i])

print(f"\n预热完成 → floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"HP={state.hero.hp} ATK={state.hero.atk} DEF={state.hero.def_}", flush=True)
print(f"  keys={dict(state.hero.keys)}\n", flush=True)

print("=== tok[256..300] 详细轨迹 ===", flush=True)
for i in range(256, 301):
    tok = tokens[i]
    old_pos   = (state.hero.x, state.hero.y)
    old_hp    = state.hero.hp
    old_atk   = state.hero.atk
    old_def   = state.hero.def_
    old_floor = state.current_floor
    old_keys  = dict(state.hero.keys)

    state = step(state, tok)

    new_pos   = (state.hero.x, state.hero.y)
    new_floor = state.current_floor

    events = []
    if new_floor != old_floor:
        events.append(f"FLOOR→{new_floor}")
    if new_pos != old_pos:
        if state.hero.hp < old_hp:
            events.append(f"FIGHT(HP{state.hero.hp-old_hp:+d})")
        elif state.hero.hp > old_hp:
            events.append(f"PICKUP(HP+{state.hero.hp-old_hp})")
        else:
            events.append("MOVE")
    else:
        events.append("BLOCKED")

    if state.hero.atk != old_atk:
        events.append(f"ATK{state.hero.atk-old_atk:+d}")
    if state.hero.def_ != old_def:
        events.append(f"DEF{state.hero.def_-old_def:+d}")
    key_diff = {k: state.hero.keys.get(k,0)-old_keys.get(k,0)
                for k in set(list(old_keys)+list(dict(state.hero.keys)))}
    for k, d in key_diff.items():
        if d != 0:
            events.append(f"{k}{d:+d}")

    print(f"  [{i:3d}] {tok:14s} {new_floor:4s} ({new_pos[0]:2d},{new_pos[1]:2d}) "
          f"HP={state.hero.hp:4d} ATK={state.hero.atk:2d} DEF={state.hero.def_:2d} | "
          + ", ".join(events), flush=True)
