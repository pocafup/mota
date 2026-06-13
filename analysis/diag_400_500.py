"""追踪 token[400..499] 的详细执行过程，找出 checkpoint[500] 失败的根因。"""
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

# 构建初始状态（与 test_checkpoints 相同）
hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
floor = load_floor(FLOORS / 'MT1.json')
hero = HeroState(
    x=hero_init['loc']['x'],
    y=hero_init['loc']['y'],
    hp=hero_init['hp'],
    atk=hero_init['atk'],
    def_=hero_init['def'],
    mdef=hero_init.get('mdef', 0),
    gold=hero_init.get('gold', 0),
    keys={},
    items=dict(hero_init.get('items', {})),
    flags=dict(hero_init.get('flags', {})),
)
state = GameState(
    hero=hero,
    floors={'MT1': floor},
    current_floor='MT1',
    floor_ids=FLOOR_IDS,
    visited_floors={'MT1'},
    pending_floor_change=None,
    _floors_dir=FLOORS,
)

# 快进到 token 400
for i in range(400):
    state = step(state, tokens[i])

print(f"=== State at tok[400] ===")
print(f"  floor={state.current_floor}, pos=({state.hero.x},{state.hero.y})")
print(f"  HP={state.hero.hp}, ATK={state.hero.atk}, DEF={state.hero.def_}")
print(f"  keys={dict(state.hero.keys)}")
print()

# 追踪 tok[400..499]
for i in range(400, 500):
    tok = tokens[i]
    old_hp = state.hero.hp
    old_pos = (state.hero.x, state.hero.y)
    old_floor = state.current_floor
    old_keys = dict(state.hero.keys)
    old_atk = state.hero.atk
    old_def = state.hero.def_

    state = step(state, tok)

    new_hp = state.hero.hp
    new_pos = (state.hero.x, state.hero.y)
    new_floor = state.current_floor
    new_keys = dict(state.hero.keys)

    events = []
    if new_floor != old_floor:
        events.append(f"FLOOR {old_floor}→{new_floor}")
    if new_pos != old_pos:
        events.append(f"move {old_pos}→{new_pos}")
    else:
        events.append(f"BLOCKED @{old_pos}")
    if new_hp != old_hp:
        events.append(f"HP {old_hp}→{new_hp} ({new_hp-old_hp:+d})")
    key_diff = {k: new_keys.get(k,0) - old_keys.get(k,0) for k in set(list(old_keys)+list(new_keys))}
    for k, d in key_diff.items():
        if d != 0:
            events.append(f"{k} {old_keys.get(k,0)}→{new_keys.get(k,0)}")
    if state.hero.atk != old_atk:
        events.append(f"ATK {old_atk}→{state.hero.atk}")
    if state.hero.def_ != old_def:
        events.append(f"DEF {old_def}→{state.hero.def_}")

    print(f"  [{i:3d}] {tok:12s} | {', '.join(events)}")

print()
print(f"=== State at tok[500] ===")
print(f"  floor={state.current_floor}, pos=({state.hero.x},{state.hero.y})")
print(f"  HP={state.hero.hp}, ATK={state.hero.atk}, DEF={state.hero.def_}")
print(f"  keys={dict(state.hero.keys)}")
