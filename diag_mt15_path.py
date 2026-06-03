"""
精确诊断 tok[1293..1374]：MT14 → MT11 → MT15 → MT16
逐 token 打印：坐标、HP、开门、捡道具、战斗、楼层切换。
重点：
  A. tok[1293-1321]: MT14 路径——是否经过 (5,10) redPotion？
  B. tok[1321-1366]: MT15——是否正确走小偷(9,1)开墙(8,1)绕过 steelRock？
  C. tok[1366-1374]: MT16——是否打了 zombie (5,3)？
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
        hp=hero_init['hp'], atk=hero_init['atk'],
        def_=hero_init.get('def_', hero_init.get('def', 10)),
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

START = 1293
END   = 1374

tokens = load_tokens()
state  = build_initial_state()

for idx, tok in enumerate(tokens[:START]):
    state = step(state, tok)

prev = dict(
    hp=state.hero.hp, yk=state.hero.keys.get('yellowKey',0),
    bk=state.hero.keys.get('blueKey',0), rk=state.hero.keys.get('redKey',0),
    gold=state.hero.gold, floor=state.current_floor,
    x=state.hero.x, y=state.hero.y,
)
print(f"=== 基态 tok[{START-1}]: floor={prev['floor']} pos=({prev['x']},{prev['y']}) HP={prev['hp']} yk={prev['yk']} rk={prev['rk']}")
print()

# 打印时始终显示坐标变化和 token，只在有 HP/key/gold/floor 变化时打附加信息
for idx in range(START, END + 1):
    tok = tokens[idx]
    state = step(state, tok)

    cur = dict(
        hp=state.hero.hp, yk=state.hero.keys.get('yellowKey',0),
        bk=state.hero.keys.get('blueKey',0), rk=state.hero.keys.get('redKey',0),
        gold=state.hero.gold, floor=state.current_floor,
        x=state.hero.x, y=state.hero.y,
    )

    changes = []
    if cur['hp']   != prev['hp']:    changes.append(f"HP {prev['hp']}→{cur['hp']} ({cur['hp']-prev['hp']:+d})")
    if cur['yk']   != prev['yk']:    changes.append(f"yk {prev['yk']}→{cur['yk']}")
    if cur['bk']   != prev['bk']:    changes.append(f"bk {prev['bk']}→{cur['bk']}")
    if cur['rk']   != prev['rk']:    changes.append(f"rk {prev['rk']}→{cur['rk']}")
    if cur['gold'] != prev['gold']:  changes.append(f"gold {prev['gold']}→{cur['gold']} ({cur['gold']-prev['gold']:+d})")
    if cur['floor']!= prev['floor']: changes.append(f"FLOOR {prev['floor']}→{cur['floor']}")
    pos_changed = (cur['x'] != prev['x'] or cur['y'] != prev['y'])

    # 始终打印：楼层切换、stat变化、非方向token；方向token若未移动（撞墙）也打印
    show = bool(changes) or tok not in ('U','D','L','R') or not pos_changed
    if show or True:  # 全打印，方便追踪
        pos = f"({cur['x']},{cur['y']})"
        moved = "" if pos_changed else " [BLOCKED]"
        info = ("  " + "  ".join(changes)) if changes else ""
        print(f"tok[{idx:4d}] {tok:>12s}  {cur['floor']:6s} {pos:8s}{moved}{info}")

    prev = dict(cur)

print()
print(f"=== tok[{END}] 终态: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) HP={state.hero.hp} ATK={state.hero.atk} DEF={state.hero.def_} yk={state.hero.keys.get('yellowKey',0)}")

# 单独确认：MT15 (8,1) 是否被清除（小偷事件的效果）
mt15_floor = state.floors.get('MT15')
if mt15_floor:
    tile_81 = mt15_floor.terrain.get((8, 1), 0)
    print(f"MT15 (8,1) tile = {tile_81}  (0=通行, 330=不可破坏墙)")
