"""
追踪 tok[1374..1430]：zombie之后发生了什么，有无道具弥补 HP。
同时检查 tok[0..1372] 内是否有 MT16 道具被提前消费。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA  = Path('data/games51')
FLOORS = DATA / 'floors'

def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hi = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hi['loc']['x'], y=hi['loc']['y'],
        hp=hi['hp'], atk=hi['atk'],
        def_=hi.get('def_', hi.get('def', 10)),
        mdef=hi.get('mdef', 0), gold=hi.get('gold', 0),
        keys={}, items=dict(hi.get('items', {})),
        flags=dict(hi.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
    )

def load_tokens():
    rp = next(Path('.').glob('51_*.h5route'), None)
    raw = rp.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))

toks = load_tokens()
state = build_initial_state()

# 推进到 1373
for idx, tok in enumerate(toks[:1374]):
    state = step(state, tok)

print(f"=== 基态 tok[1373]: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) HP={state.hero.hp}")

prev_hp = state.hero.hp
prev_floor = state.current_floor
prev_x, prev_y = state.hero.x, state.hero.y

for idx in range(1374, 1430):
    tok = toks[idx]
    state = step(state, tok)

    cur_hp, cur_floor = state.hero.hp, state.current_floor
    cur_x, cur_y = state.hero.x, state.hero.y
    changes = []
    if cur_hp != prev_hp:        changes.append(f"HP {prev_hp}→{cur_hp} ({cur_hp-prev_hp:+d})")
    if cur_floor != prev_floor:  changes.append(f"FLOOR {prev_floor}→{cur_floor}")
    pos_changed = (cur_x != prev_x or cur_y != prev_y)

    info = "  ".join(changes)
    blocked = " [BLOCKED]" if not pos_changed else ""
    print(f"tok[{idx:4d}] {tok:>12s}  {cur_floor:6s} ({cur_x},{cur_y}){blocked}  {info}")

    prev_hp, prev_floor, prev_x, prev_y = cur_hp, cur_floor, cur_x, cur_y

print()
# MT16 在 tok[0..1372] 有无道具被消费（检查 MT16 floor state）
state2 = build_initial_state()
for idx, tok in enumerate(toks[:1373]):
    state2 = step(state2, tok)
mt16 = state2.floors.get('MT16')
if mt16:
    print("MT16 floor state at tok[1372] entities:")
    # Print all entities on MT16
    for pos, eid in sorted(mt16.entities.items()):
        print(f"  {pos}: {eid}")
else:
    print("MT16 not yet loaded at tok[1372]")
