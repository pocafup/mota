"""逐格追踪 MT5 第二次造访（tokens[280..546]）——看英雄是否到达剑格区域。"""
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
tokens = parse_rle_route(decompress(outer['route']))[:600]

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

for tok in tokens[:280]:
    state = step(state, tok)

print(f"token[279]: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} keys={dict(state.hero.keys)}")

# 打印 MT5 sword 区域当前状态
if 'MT5' in state.floors:
    mt5 = state.floors['MT5']
    e = mt5.entities
    print(f"  MT5(11,11) entity: {e[11][11]} (35=剑未取, 0=已取)")
    print(f"  MT5(8,9) entity: {e[9][8]} (81=黄门未开, 0=已开)")
print()

print(f"{'idx':>4}  {'tok':<12}  {'fl':<4}  {'from':<10}  {'to':<10}  "
      f"{'hp':>6}  {'atk':>3}  Y  note")
print('-'*100)

for idx in range(280, 548):
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

    moved = pos_before != pos_after or fl_before != fl_after

    note = ""
    if not moved:
        dx = {'L': -1, 'R': 1, 'U': 0, 'D': 0}.get(tok, 0)
        dy = {'U': -1, 'D': 1, 'L': 0, 'R': 0}.get(tok, 0)
        nx, ny = pos_before[0] + dx, pos_before[1] + dy
        if fl_before in state.floors and 0 <= ny < 13 and 0 <= nx < 13:
            fl = state.floors[fl_before]
            t_t = fl.terrain[ny][nx]
            e_t = fl.entities[ny][nx]
            note = f"BLOCKED({nx},{ny}) T={t_t} E={e_t}"
        else:
            note = f"BLOCKED({nx},{ny})"
    elif fl_before != fl_after:
        note = f"→{fl_before}→{fl_after}"
    elif hp_before != hp_after:
        note = f"±HP {hp_before - hp_after:+}"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"

    # 高亮关键格
    x, y = pos_after
    if fl_after == 'MT5' and y >= 6:
        # 关键区域：打印所有 MT5 y≥6 的步骤
        pass
    else:
        # 其他层只打印 HP 变化 / ATK 变化 / 切层
        if not note:
            continue

    yk = state.hero.keys.get('yellowKey', 0)
    print(f"{idx:>4}  {tok:<12}  {fl_after:<4}  "
          f"({pos_before[0]},{pos_before[1]})  ({pos_after[0]},{pos_after[1]})  "
          f"{hp_after:>6}  {atk_after:>3}  {yk:>2}  {note}")
