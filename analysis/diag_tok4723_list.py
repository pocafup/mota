"""tok4723..4760 逐 token 纯清单：idx | 动作 | 坐标before->after | HP | 黄钥 | 蓝钥 | 撞墙标注。
不分析、不下结论。tok4729 门交互单独标。"""
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

DIRS = {'U', 'D', 'L', 'R'}
print("idx   | 动作      | floor 坐标 before -> after        | HP   | 黄钥 | 蓝钥 | 标注")
print("-" * 92)
for idx, tok in enumerate(tokens):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    pyk = state.hero.keys.get('yellowKey', 0)
    pbk = state.hero.keys.get('blueKey', 0)
    state = step(state, tok)
    if not (4723 <= idx <= 4760):
        continue
    cf = state.current_floor
    cp = (state.hero.x, state.hero.y)
    yk = state.hero.keys.get('yellowKey', 0)
    bk = state.hero.keys.get('blueKey', 0)
    note = ''
    if tok in DIRS and cp == pp and cf == pf:
        note = '撞墙(原地)'
    if yk != pyk:
        note = (note + ' ' if note else '') + f'黄钥{pyk}->{yk}'
    if bk != pbk:
        note = (note + ' ' if note else '') + f'蓝钥{pbk}->{bk}'
    if cf != pf:
        note = (note + ' ' if note else '') + f'切层{pf}->{cf}'
    star = ' <== 门异常?' if idx == 4729 else ''
    print(f"{idx:5} | {tok:9} | {pf:5}{str(pp):8} -> {cf:5}{str(cp):8} | {state.hero.hp:5}| {yk:3}  | {bk:3}  | {note}{star}")
