"""逐格追踪 MT5 第一次造访（decoded[210..260]）——含所有 wall hit，找铁剑拾取分叉点。"""
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

# ── 重放到 token[209] ────────────────────────────────────────────────────────
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

for tok in tokens[:210]:
    state = step(state, tok)

print(f"token[209] 结束: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_} keys={dict(state.hero.keys)}")
print()

# ── 打印 MT5 地图行8-12 ──────────────────────────────────────────────────────
if 'MT5' not in state.floors:
    # 预加载 MT5 以便打印地图
    mt5_floor = load_floor(FLOORS / 'MT5.json')
    print("MT5 行8-12（entities层）:")
    for row in range(8, 13):
        print(f"  row{row}: {mt5_floor.entities[row]}")
    print()

# ── 逐格追踪 token[210..260] ────────────────────────────────────────────────
print(f"{'idx':>4}  {'tok':<12}  {'floor':<5}  {'from':<10}  {'to':<10}  "
      f"{'hp':>5}  {'atk':>3}  {'def':>4}  {'keys'}  note")
print('-'*105)

for idx in range(210, 280):
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
        # 查查是哪个 tile 挡住了
        dx = {'L': -1, 'R': 1, 'U': 0, 'D': 0}.get(tok, 0)
        dy = {'U': -1, 'D': 1, 'L': 0, 'R': 0}.get(tok, 0)
        nx, ny = pos_before[0] + dx, pos_before[1] + dy
        if fl_before in state.floors:
            fl = state.floors[fl_before]
            t_t = fl.terrain[ny][nx] if 0 <= ny < len(fl.terrain) and 0 <= nx < len(fl.terrain[0]) else '?'
            e_t = fl.entities[ny][nx] if 0 <= ny < len(fl.entities) and 0 <= nx < len(fl.entities[0]) else '?'
            note = f"  BLOCKED → ({nx},{ny}) terrain={t_t} entity={e_t}"
        else:
            note = f"  BLOCKED → ({nx},{ny})"
    if atk_after != atk_before:
        note += f"  ★ATK {atk_before}→{atk_after}"
    if fl_before != fl_after:
        note += f"  →切层 {fl_before}→{fl_after}"
    elif hp_before != hp_after:
        note += f"  ±HP {hp_before-hp_after:+}"

    yk = state.hero.keys.get('yellowKey', 0)
    bk = state.hero.keys.get('blueKey', 0)
    print(f"{idx:>4}  {tok:<12}  {fl_after:<5}  "
          f"({pos_before[0]},{pos_before[1]})  ({pos_after[0]},{pos_after[1]})  "
          f"{hp_after:>5}  {atk_after:>3}  {state.hero.def_:>4}  Y={yk}B={bk}{note}")

    # 如果离开 MT5，停止追踪
    if fl_after != 'MT5' and fl_before == 'MT5' and idx > 215:
        print(f"\n  【已离开MT5，停止追踪，idx={idx}】")
        break

print(f"\n最终: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"atk={state.hero.atk} def={state.hero.def_}")
