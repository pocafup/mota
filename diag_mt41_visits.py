"""分段每次 MT41 访问：起止 token、max_x、是否到过顶部(y<=3)、是否到过右半(x>=7)。
另：列出全程 8 个 UNKNOWN token 及其上下文（怀疑被 sim 当 no-op 漏处理→desync）。"""
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

visits = []   # (start, end, maxx, miny, reached_top, reached_right)
cur = None
unknowns = []
for idx, tok in enumerate(tokens):
    if tok.startswith('UNKNOWN'):
        unknowns.append((idx, tok))
    prev_f = state.current_floor
    state = step(state, tok)
    f = state.current_floor
    if f == 'MT41':
        if cur is None:
            cur = {'start': idx, 'maxx': state.hero.x, 'miny': state.hero.y}
        cur['maxx'] = max(cur['maxx'], state.hero.x)
        cur['miny'] = min(cur['miny'], state.hero.y)
        cur['end'] = idx
    else:
        if cur is not None:
            visits.append(cur)
            cur = None
if cur is not None:
    visits.append(cur)

print(f"MT41 访问段数={len(visits)}：")
for v in visits:
    print(f"  tok[{v['start']}..{v['end']}] maxx={v['maxx']} miny={v['miny']} "
          f"到顶(y<=3)={v['miny'] <= 3} 到右半(x>=7)={v['maxx'] >= 7}")

print(f"\n全程 UNKNOWN token（{len(unknowns)} 个）:")
for idx, tok in unknowns:
    ctx = [tokens[j] for j in range(max(0, idx - 2), min(len(tokens), idx + 3))]
    print(f"  tok[{idx}] = {tok}   上下文={ctx}")
