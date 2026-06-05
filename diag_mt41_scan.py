"""全程扫描：找出英雄在 MT41 关键格的所有时刻 + flag:41 / downFly 的每次变化。
关键格：(2,2)=redWizard隐藏怪源(杀它 flag41=1)、(9,2)=reveal触发位、(10,2)=隐藏怪。
也打印：每当英雄在 MT41 且尝试朝 (10,2) 走、flag41 变化、downFly 数量变化、ent[2][10]变化。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    kb_raw = json.loads((DATA / 'replay_keybindings.json').read_text(encoding='utf-8'))
    key_bindings = {int(k): v for k, v in kb_raw.get('bindings', {}).items()}
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
        _key_bindings=key_bindings,
    )


route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw))
tokens = parse_rle_route(LZString().decompressFromBase64(outer['route']))

KEY = {(2, 2), (9, 2), (10, 2), (10, 1), (10, 3), (11, 2)}
state = build_initial_state()
prev_flag41 = 0
prev_downfly = 0
prev_e102 = 0
for idx, tok in enumerate(tokens):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    state = step(state, tok)
    h = state.hero
    f = state.floors.get('MT41')
    flag41 = h.flags.get('41', 0)
    downfly = h.items.get('downFly', 0)
    e102 = f.entities[2][10] if f else 0
    reasons = []
    if state.current_floor == 'MT41' and (h.x, h.y) in KEY:
        reasons.append(f"@{(h.x, h.y)}")
    if pf == 'MT41' and pp in KEY:
        reasons.append(f"from{pp}")
    if flag41 != prev_flag41:
        reasons.append(f"flag41 {prev_flag41}->{flag41}")
    if downfly != prev_downfly:
        reasons.append(f"downFly {prev_downfly}->{downfly}")
    if e102 != prev_e102:
        reasons.append(f"ent[2][10] {prev_e102}->{e102}")
    if reasons:
        print(f"tok[{idx}] {tok:10} {pf}{pp}->{state.current_floor}({h.x},{h.y}) "
              f"flag41={flag41} | {' '.join(reasons)}")
    prev_flag41, prev_downfly, prev_e102 = flag41, downfly, e102
