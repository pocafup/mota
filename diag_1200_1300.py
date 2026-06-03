"""逐 token 列出 tok[1200]→tok[1300] 的状态变化，定位英雄在哪一步卡住/走偏。
口径：tok[N] = 处理完 tokens[0..N]（与 test_checkpoints.py 一致）。
使用当前 sim/simulator.py（含本次 3 处改动）重放。
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent / 'data/games51'
FLOORS = DATA / 'floors'


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
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
    )


def load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'), None)
    if route_path is None:
        route_path = next(Path(__file__).parent.glob('51_*.h5route'), None)
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def snap(s):
    h = s.hero
    return (s.current_floor, h.x, h.y, h.hp, h.atk, h.def_,
            h.keys.get('yellowKey', 0), h.keys.get('blueKey', 0), h.gold)


LO, HI = 1269, 1300
tokens = load_tokens()
state = build_initial_state()
for idx in range(LO + 1):           # 处理 tokens[0..LO] → tok[LO] 状态
    state = step(state, tokens[idx])

prev = snap(state)
print(f"=== tok[{LO}] 起点: floor={prev[0]} pos=({prev[1]},{prev[2]}) "
      f"HP={prev[3]} ATK={prev[4]} DEF={prev[5]} yk={prev[6]} bk={prev[7]} gold={prev[8]}")
print(f"{'idx':>4} {'token':<9} {'floor':<5} {'pos':<8} {'HP':>5} {'ATK':>3} "
      f"{'DEF':>3} {'yk':>2} {'bk':>2} {'gold':>4}  note")

stuck = 0
for idx in range(LO + 1, HI + 1):
    tok = tokens[idx]
    state = step(state, tok)
    cur = snap(state)
    notes = []
    if cur[0] != prev[0]:
        notes.append(f"<<FLOOR {prev[0]}->{cur[0]}>>")
    moved = (cur[1], cur[2]) != (prev[1], prev[2])
    if not moved and tok in ('U', 'D', 'L', 'R'):
        stuck += 1
        notes.append(f"撞/不移x{stuck}")
    elif moved:
        stuck = 0
    if cur[3] != prev[3]:
        notes.append(f"HP{cur[3]-prev[3]:+d}")
    if cur[6] != prev[6]:
        notes.append(f"yk{cur[6]-prev[6]:+d}")
    if cur[7] != prev[7]:
        notes.append(f"bk{cur[7]-prev[7]:+d}")
    if cur[8] != prev[8]:
        notes.append(f"gold{cur[8]-prev[8]:+d}")
    pos = f"({cur[1]},{cur[2]})"
    print(f"{idx:>4} {repr(tok):<9} {cur[0]:<5} {pos:<8} {cur[3]:>5} {cur[4]:>3} "
          f"{cur[5]:>3} {cur[6]:>2} {cur[7]:>2} {cur[8]:>4}  {' '.join(notes)}")
    prev = cur
