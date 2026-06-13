"""决定性：逐 token 打印 MT41 内英雄在 (7,6) 横向通道附近的全部动作（不压缩）。
对每个 token 打印：idx, tok, 楼层/坐标 before->after, 是否 stuck(移动键但原地),
blueKey, ter[6][5]((5,6)门), ter[6][7]((7,6)门)。
只在 MT41 内、且 (before 或 after 的 x>=5) 时打印——聚焦横向通道与右半区。
目的：看 route 是否真的按 R 想穿 (7,6) 而 sim 拦住了(=sim bug)，还是 route 自己往左走。"""
import json
import os
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

LO = int(os.environ.get('LO', 0))
HI = int(os.environ.get('HI', len(tokens)))

for idx, tok in enumerate(tokens):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    state = step(state, tok)
    if not (LO <= idx <= HI):
        continue
    cf = state.current_floor
    cp = (state.hero.x, state.hero.y)
    # 只在与 MT41 横向通道相关时打印
    relevant = (pf == 'MT41' or cf == 'MT41') and (pp[0] >= 5 or cp[0] >= 5)
    if not relevant:
        continue
    f41 = state.floors.get('MT41')
    d56 = f41.terrain[6][5] if f41 else '?'
    d76 = f41.terrain[6][7] if f41 else '?'
    bk = state.hero.keys.get('blueKey', 0)
    stuck = tok in ('U', 'D', 'L', 'R') and cp == pp and cf == pf
    flag = ' <<STUCK撞墙' if stuck else ''
    chg = ' <<切层' if cf != pf else ''
    print(f"tok[{idx}] {tok:9} {pf}{pp}->{cf}{cp}  bk={bk} d(5,6)={d56} d(7,6)={d76}{flag}{chg}")
