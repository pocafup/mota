"""追踪 tok4723..4921 英雄在 MT41 的完整轨迹，标出 stuck（U/D/L/R 未移动=撞墙）
与切层。目的：定位 sim 与真值路线的首个分叉点（真人路线极少连撞墙）。"""
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

state = build_initial_state()
import os
LO = int(os.environ.get('LO', 4713))
HI = int(os.environ.get('HI', 4919))
# 只打印：非撞墙的移动/切层/到达crossing区(x>=5,y in 5..7) — 压缩噪声
prev_print_stuck = False
stuck_run = 0
for idx, tok in enumerate(tokens[:HI + 1]):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    state = step(state, tok)
    if LO <= idx <= HI:
        h = state.hero
        np = (h.x, h.y)
        is_stuck = tok in ("U", "D", "L", "R") and np == pp and pf == state.current_floor
        if is_stuck:
            stuck_run += 1
            continue
        if stuck_run:
            print(f"        ... STUCK x{stuck_run} (撞墙原地)")
            stuck_run = 0
        chg = "  <<切层" if state.current_floor != pf else ""
        cross = "  [crossing区]" if np[0] >= 5 and 5 <= np[1] <= 7 else ""
        print(f"tok[{idx}] {tok:10} {pf}{pp}->{state.current_floor}{np}{chg}{cross}")
if stuck_run:
    print(f"        ... STUCK x{stuck_run} (撞墙原地)")
