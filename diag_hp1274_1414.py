"""
诊断 tok[1274..1414] 区间：逐 token 打印 HP/floor/pos/yk 变化。
目标：找到 sim HP=60 vs 真值 HP=545 的 485 差距来源。
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
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def_'] if 'def_' in hero_init else hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
    )

def load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'), None)
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))

START = 1274
END   = 1414

tokens = load_tokens()
state  = build_initial_state()

# 快速推进到 START-1
for idx, tok in enumerate(tokens[:START]):
    state = step(state, tok)

prev_hp  = state.hero.hp
prev_yk  = state.hero.keys.get('yellowKey', 0)
prev_bk  = state.hero.keys.get('blueKey', 0)
prev_rk  = state.hero.keys.get('redKey', 0)
prev_gold= state.hero.gold
prev_floor = state.current_floor
prev_x   = state.hero.x
prev_y   = state.hero.y

print(f"=== tok[{START-1}] base: floor={prev_floor} HP={prev_hp} yk={prev_yk} bk={prev_bk} rk={prev_rk} gold={prev_gold} pos=({prev_x},{prev_y})")
print()

for idx in range(START, END + 1):
    tok = tokens[idx]
    state = step(state, tok)

    cur_hp   = state.hero.hp
    cur_yk   = state.hero.keys.get('yellowKey', 0)
    cur_bk   = state.hero.keys.get('blueKey', 0)
    cur_rk   = state.hero.keys.get('redKey', 0)
    cur_gold = state.hero.gold
    cur_floor= state.current_floor
    cur_x    = state.hero.x
    cur_y    = state.hero.y

    changes = []
    if cur_hp   != prev_hp:    changes.append(f"HP {prev_hp:+d}→{cur_hp} ({cur_hp-prev_hp:+d})")
    if cur_yk   != prev_yk:    changes.append(f"yk {prev_yk}→{cur_yk}")
    if cur_bk   != prev_bk:    changes.append(f"bk {prev_bk}→{cur_bk}")
    if cur_rk   != prev_rk:    changes.append(f"rk {prev_rk}→{cur_rk}")
    if cur_gold != prev_gold:  changes.append(f"gold {prev_gold}→{cur_gold} ({cur_gold-prev_gold:+d})")
    if cur_floor!= prev_floor: changes.append(f"FLOOR {prev_floor}→{cur_floor}")

    if changes or tok not in ('U','D','L','R'):
        loc = f"({cur_x},{cur_y})"
        print(f"tok[{idx}] {tok:>12s}  {cur_floor:6s} {loc:8s}  {'  '.join(changes) if changes else ''}")

    prev_hp   = cur_hp
    prev_yk   = cur_yk
    prev_bk   = cur_bk
    prev_rk   = cur_rk
    prev_gold = cur_gold
    prev_floor= cur_floor
    prev_x    = cur_x
    prev_y    = cur_y

print()
print(f"=== tok[{END}] final: floor={state.current_floor} HP={state.hero.hp} ATK={state.hero.atk} DEF={state.hero.def_} yk={state.hero.keys.get('yellowKey',0)} bk={state.hero.keys.get('blueKey',0)} gold={state.hero.gold}")
