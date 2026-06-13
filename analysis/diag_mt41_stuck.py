"""tok4724..4912（最后一个真值检查点 tok4723 之后、飞出前）逐 token：
打印 pos before->after、撞墙时的目标格 tile + 黄钥/蓝钥数。
目的：tok4723 sim 已证忠实(hero@(3,6))，desync 在此后。看英雄左列 thrash 是
(a) 缺钥匙开不了门 / (b) 真墙(reality 也撞) / (c) sim 漏了某事件改图。
并标出：英雄是否再回到 (6,6) 试图二次跨 (7,6)。"""
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

DIRS = {'U': (0, -1), 'D': (0, 1), 'L': (-1, 0), 'R': (1, 0)}
stuck_run = 0
stuck_first = None
for idx, tok in enumerate(tokens):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    state = step(state, tok)
    if not (4724 <= idx <= 4912):
        continue
    cf = state.current_floor
    cp = (state.hero.x, state.hero.y)
    f = state.floors.get('MT41')
    yk = state.hero.keys.get('yellowKey', 0)
    bk = state.hero.keys.get('blueKey', 0)
    stuck = tok in DIRS and cp == pp and cf == pf
    if stuck:
        dx, dy = DIRS[tok]
        tx, ty = pp[0] + dx, pp[1] + dy
        tile = f.terrain[ty][tx] if (f and 0 <= ty < len(f.terrain) and 0 <= tx < len(f.terrain[0])) else '越界'
        ent = f.entities[ty][tx] if (f and 0 <= ty < len(f.terrain) and 0 <= tx < len(f.terrain[0])) else '-'
        if stuck_run == 0:
            stuck_first = (idx, tok, pp, (tx, ty), tile, ent, yk, bk)
        stuck_run += 1
        continue
    if stuck_run:
        i0, t0, p0, tgt, tile, ent, yk0, bk0 = stuck_first
        print(f"  ...STUCK x{stuck_run}：从 {p0} 按 {t0} 撞 {tgt} tile={tile} ent={ent}  yk={yk0} bk={bk0}")
        stuck_run = 0
    mark = ''
    if cp == (6, 6):
        mark = '  <<★回到(6,6)！可二次跨(7,6)'
    elif cp[0] >= 6:
        mark = '  <<到脊柱x>=6'
    chg = f'  <<切层{cf}' if cf != pf else ''
    print(f"tok[{idx}] {tok:9} {pp}->{cp}  yk={yk} bk={bk}{mark}{chg}")
if stuck_run:
    i0, t0, p0, tgt, tile, ent, yk0, bk0 = stuck_first
    print(f"  ...STUCK x{stuck_run}：从 {p0} 按 {t0} 撞 {tgt} tile={tile} ent={ent}  yk={yk0} bk={bk0}")
