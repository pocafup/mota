"""核对 sim 的 MT41 实体层：大段访问起点(tok4713)与终点(tok4919)各怪格 ent 值，
以及全程每只怪何时从 entities 消失(被杀/被穿)。对照 map 应有的怪。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'

floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
kb_raw = json.loads((DATA / 'replay_keybindings.json').read_text(encoding='utf-8'))
key_bindings = {int(k): v for k, v in kb_raw.get('bindings', {}).items()}
mt1 = load_floor(FLOORS / 'MT1.json')
hero = HeroState(x=hero_init['loc']['x'], y=hero_init['loc']['y'], hp=hero_init['hp'],
                 atk=hero_init['atk'], def_=hero_init['def'], mdef=hero_init.get('mdef', 0),
                 gold=hero_init.get('gold', 0), keys={}, items=dict(hero_init.get('items', {})),
                 flags=dict(hero_init.get('flags', {})))
state = GameState(hero=hero, floors={'MT1': mt1}, current_floor='MT1', floor_ids=floor_ids,
                  visited_floors={'MT1'}, pending_floor_change=None, _floors_dir=FLOORS,
                  _key_bindings=key_bindings)
route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw))
tokens = parse_rle_route(LZString().decompressFromBase64(outer['route']))

# map 上的怪格（来自 MT41.json _map_entities）
MONSTERS = {
    (2, 2): 'redWizard220', (5, 4): 'whiteKing246', (7, 4): 'whiteKing246',
    (3, 5): 'brownWizard219', (9, 5): 'brownWizard219',
    (1, 6): 'redBat207', (11, 6): 'redBat207', (2, 7): 'redBat207', (10, 7): 'redBat207',
    (4, 7): 'slimelord204', (8, 7): 'slimelord204',
}


def dump(label):
    f = state.floors.get('MT41')
    if f is None:
        print(f"{label}: MT41 未加载")
        return
    print(f"{label}:")
    for (x, y), name in MONSTERS.items():
        e = f.entities[y][x]
        t = f.terrain[y][x]
        alive = e != 0
        print(f"   ({x},{y}) {name:14} ent={e:4} ter={t:4} {'存活' if alive else '★已空(被杀/穿)'}")


# 逐 token，记录每只怪消失的 token + 是否经历过战斗
prev_ent = None
first_load_done = False
death_log = []
for idx, tok in enumerate(tokens):
    state = step(state, tok)
    f = state.floors.get('MT41')
    if f is None:
        continue
    if not first_load_done:
        first_load_done = True
        snap0 = {(x, y): f.entities[y][x] for (x, y) in MONSTERS}
        print(f"[MT41 首次加载 @tok{idx}]")
        for (x, y), name in MONSTERS.items():
            print(f"   ({x},{y}) {name:14} ent={f.entities[y][x]}")
        prev_ent = dict(snap0)
        print()
        continue
    cur = {(x, y): f.entities[y][x] for (x, y) in MONSTERS}
    for k in MONSTERS:
        if prev_ent[k] != 0 and cur[k] == 0:
            death_log.append((idx, tok, k, MONSTERS[k]))
    prev_ent = cur
    if idx == 4713:
        dump(f"[tok4713 大段访问起点]")
    if idx == 4919:
        dump(f"[tok4919 大段访问终点]")

print("\n每只 MT41 怪从 entities 消失的时刻：")
if not death_log:
    print("   （无：全程没有任何 MT41 怪被清除）")
for idx, tok, loc, name in death_log:
    print(f"   tok[{idx}] {tok}: ({loc[0]},{loc[1]}) {name} → ent 清零")
