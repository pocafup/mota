"""追踪 MT4 两次造访：第一次开了哪几个黄门；第二次逐格走偏在哪。"""
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
tokens = parse_rle_route(decompress(outer['route']))[:320]

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

# 先快进到第一次进 MT4 之前
FIRST_MT4_START = None
for idx in range(len(tokens)):
    tok = tokens[idx]
    fl_before = state.current_floor
    state = step(state, tok)
    if fl_before != 'MT4' and state.current_floor == 'MT4':
        FIRST_MT4_START = idx
        print(f"=== 第一次进 MT4：token[{idx}] ===")
        print(f"  落地位置：({state.hero.x},{state.hero.y})")
        break

if FIRST_MT4_START is None:
    print("未找到第一次 MT4！")
    sys.exit(1)

# 继续追踪第一次 MT4，记录黄门开关事件
print(f"\n{'idx':>4}  {'tok':<8}  {'from':<10}  {'to':<10}  {'hp':>5}  {'Y':>2}  note")
print('-'*70)

DOOR_CELLS = {(1,8): '黄门(1,8)', (4,8): '黄门(4,8)', (8,8): '黄门(8,8)', (11,8): '黄门(11,8)'}

for idx in range(FIRST_MT4_START + 1, len(tokens)):
    tok = tokens[idx]
    fl_before = state.current_floor
    pos_before = (state.hero.x, state.hero.y)
    hp_before = state.hero.hp

    state = step(state, tok)

    fl_after = state.current_floor
    pos_after = (state.hero.x, state.hero.y)
    hp_after = state.hero.hp

    note = ""
    moved = pos_before != pos_after or fl_before != fl_after

    if not moved:
        dx = {'L': -1, 'R': 1, 'U': 0, 'D': 0}.get(tok, 0)
        dy = {'U': -1, 'D': 1, 'L': 0, 'R': 0}.get(tok, 0)
        nx, ny = pos_before[0] + dx, pos_before[1] + dy
        if fl_before in state.floors:
            fl = state.floors[fl_before]
            t = fl.terrain[ny][nx] if 0 <= ny < 13 and 0 <= nx < 13 else '?'
            e = fl.entities[ny][nx] if 0 <= ny < 13 and 0 <= nx < 13 else '?'
            note = f"BLOCKED({nx},{ny}) T={t} E={e}"
    elif fl_before != fl_after:
        note = f"→{fl_before}→{fl_after}"
        # 检查黄门状态
        if 'MT4' in state.floors:
            mt4 = state.floors['MT4']
            doors = {(x,y): mt4.terrain[y][x] for (x,y) in [(1,8),(4,8),(8,8),(11,8)]}
            note += f"  MT4门状态={doors}"
    elif hp_before != hp_after:
        note = f"±HP {hp_after - hp_before:+d}"

    # 高亮黄门操作
    if pos_after in DOOR_CELLS and fl_after == 'MT4':
        note += f"  ★在门格{DOOR_CELLS[pos_after]}"
    if pos_before in DOOR_CELLS and fl_before == 'MT4' and moved:
        note += f"  ★过门{DOOR_CELLS[pos_before]}"

    yk = state.hero.keys.get('yellowKey', 0)
    if fl_before == 'MT4' or fl_after == 'MT4' or note:
        print(f"{idx:>4}  {tok:<8}  ({pos_before[0]},{pos_before[1]})  ({pos_after[0]},{pos_after[1]})  "
              f"{hp_after:>5}  {yk:>2}  {note}")

    if fl_before == 'MT4' and fl_after != 'MT4':
        # 离开 MT4 了，打印第一次离开时的门状态
        if 'MT4' in state.floors:
            mt4 = state.floors['MT4']
            print(f"\n=== 第一次离开 MT4（token[{idx}]）时 MT4 门状态 ===")
            for (x,y), label in DOOR_CELLS.items():
                t = mt4.terrain[y][x]
                e = mt4.entities[y][x]
                status = '已开(0)' if t == 0 else f'未开({t})'
                print(f"  {label}: terrain={t} entity={e} → {status}")
        break

print()

# 快进到第二次 MT4
SECOND_MT4_START = None
for idx2 in range(idx + 1, len(tokens)):
    tok = tokens[idx2]
    fl_before = state.current_floor
    state = step(state, tok)
    if fl_before != 'MT4' and state.current_floor == 'MT4':
        SECOND_MT4_START = idx2
        print(f"=== 第二次进 MT4：token[{idx2}] ===")
        print(f"  落地位置：({state.hero.x},{state.hero.y})")
        if 'MT4' in state.floors:
            mt4 = state.floors['MT4']
            print(f"  此时 MT4 门状态：")
            for (x,y), label in DOOR_CELLS.items():
                t = mt4.terrain[y][x]
                status = '已开(0)' if t == 0 else f'未开({t})'
                print(f"    {label}: {status}")
        break

if SECOND_MT4_START is None:
    print("未找到第二次 MT4！")
    sys.exit(1)

print(f"\n{'idx':>4}  {'tok':<8}  {'from':<10}  {'to':<10}  {'hp':>5}  {'atk':>3}  {'Y':>2}  note")
print('-'*80)

for idx3 in range(SECOND_MT4_START + 1, len(tokens)):
    tok = tokens[idx3]
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
        if fl_before in state.floors and 0 <= ny < 13 and 0 <= nx < 13:
            fl = state.floors[fl_before]
            t = fl.terrain[ny][nx]
            e = fl.entities[ny][nx]
            note = f"BLOCKED({nx},{ny}) T={t} E={e}"
        else:
            note = f"BLOCKED({nx},{ny})"
    elif fl_before != fl_after:
        note = f"→{fl_before}→{fl_after}"
    elif hp_before != hp_after:
        note = f"±HP {hp_after - hp_before:+d}"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"
    if pos_after in DOOR_CELLS and fl_after == 'MT4':
        note += f"  ★在门格{DOOR_CELLS[pos_after]}"

    yk = state.hero.keys.get('yellowKey', 0)
    print(f"{idx3:>4}  {tok:<8}  ({pos_before[0]},{pos_before[1]})  ({pos_after[0]},{pos_after[1]})  "
          f"{hp_after:>5}  {atk_after:>3}  {yk:>2}  {note}")

    if fl_before == 'MT4' and fl_after != 'MT4':
        break
    if idx3 >= 300:
        break
