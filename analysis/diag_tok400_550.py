"""追踪 tok[400..549] 的完整执行，显示楼层、坐标、HP、tile类型信息。"""
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
    keys={}, items=dict(hero_init.get('items', {})),
    flags=dict(hero_init.get('flags', {})),
)
state = GameState(
    hero=hero, floors={'MT1': floor}, current_floor='MT1',
    floor_ids=FLOOR_IDS, visited_floors={'MT1'},
    pending_floor_change=None, _floors_dir=FLOORS,
)

for i in range(400):
    state = step(state, tokens[i])

print(f"=== tok[400] 开始状态 ===")
print(f"  floor={state.current_floor}, pos=({state.hero.x},{state.hero.y}), HP={state.hero.hp}, ATK={state.hero.atk}")
print(f"  keys={dict(state.hero.keys)}")
print()

def tile_info(fl, x, y):
    """返回指定位置的 terrain tile 和 entity tile。"""
    if fl is None:
        return "?", "?"
    rows = len(fl.terrain)
    cols = len(fl.terrain[0]) if rows else 0
    if not (0 <= y < rows and 0 <= x < cols):
        return -1, -1
    t = fl.terrain[y][x]
    e = fl.entities[y][x]
    return t, e

# 追踪 tok[400..549]
for i in range(400, 550):
    tok = tokens[i]
    old_hp = state.hero.hp
    old_pos = (state.hero.x, state.hero.y)
    old_floor = state.current_floor
    old_keys = dict(state.hero.keys)

    state = step(state, tok)

    new_pos = (state.hero.x, state.hero.y)
    new_floor = state.current_floor
    new_keys = dict(state.hero.keys)

    # 只打印有意义的事件
    events = []
    if new_floor != old_floor:
        events.append(f"FLOOR {old_floor}→{new_floor}")
    if new_pos != old_pos:
        events.append(f"→({new_pos[0]},{new_pos[1]})")
    else:
        # 被 BLOCKED，获取目标位置信息
        dx, dy = {'U': (0,-1), 'D': (0,1), 'L': (-1,0), 'R': (1,0)}.get(tok, (0,0))
        nx, ny = old_pos[0]+dx, old_pos[1]+dy
        if tok in ('U','D','L','R') and new_floor in state.floors:
            t, e = tile_info(state.floors[new_floor], nx, ny)
            events.append(f"BLKD→({nx},{ny}) T={t} E={e}")
        elif tok in ('U','D','L','R'):
            events.append(f"BLKD→({nx},{ny})")
    if state.hero.hp != old_hp:
        events.append(f"HP {old_hp}→{state.hero.hp} ({state.hero.hp-old_hp:+d})")
    key_diff = {k: new_keys.get(k,0)-old_keys.get(k,0) for k in set(list(old_keys)+list(new_keys))}
    for k, d in key_diff.items():
        if d != 0:
            events.append(f"{k}{d:+d}")

    # 只打印有 HP 变化/楼层变化/BLKD 的行
    has_event = (state.hero.hp != old_hp or new_floor != old_floor or
                 new_pos == old_pos or any(d != 0 for d in key_diff.values()))
    if has_event:
        yk = state.hero.keys.get('yellowKey', 0)
        bk = state.hero.keys.get('blueKey', 0)
        print(f"  [{i:3d}] {tok:12s} f={new_floor:4s} pos=({state.hero.x:2d},{state.hero.y:2d}) HP={state.hero.hp:4d} yk={yk} | {', '.join(events)}")
