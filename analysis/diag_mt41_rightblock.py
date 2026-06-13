"""全程扫描：sim 里英雄在 MT41 是否【曾经】跨到右半区(x>=7)、到过(9,2)、杀过(2,2)红巫/(10,2)隐藏怪。
按 MT41 每次访问分段报告：entry/exit token、该次访问 max_x、是否到过(9,2)、flag41、(2,2)/(10,2)实体状态。
目的：坐实 (10,2) 杀点到底在哪次 MT41 访问（早期已验证段 or 本段 tok4713-4920），还是全程从未发生。"""
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


def flag41(s):
    return s.hero.flags.get('41', s.hero.flags.get(41, 0))


def tile_at(s, x, y):
    f = s.floors.get('MT41')
    if not f:
        return None
    return f.terrain[y][x]


visits = []  # (entry_idx, exit_idx, max_x, reached_9_2, flag41_exit, t22, t102, t76, t56)
in_mt41 = False
seg = None
flag_changes = []
prev_flag = 0
for idx, tok in enumerate(tokens):
    pf = state.current_floor
    state = step(state, tok)
    cf = state.current_floor
    fl = flag41(state)
    if fl != prev_flag:
        flag_changes.append((idx, tok, prev_flag, fl, cf, (state.hero.x, state.hero.y)))
        prev_flag = fl
    if cf == 'MT41':
        if not in_mt41:
            in_mt41 = True
            seg = {'entry': idx, 'max_x': state.hero.x, 'reached92': False}
        seg['max_x'] = max(seg['max_x'], state.hero.x)
        if (state.hero.x, state.hero.y) == (9, 2):
            seg['reached92'] = True
    else:
        if in_mt41:
            seg['exit'] = idx - 1
            seg['flag41'] = flag41(state)
            visits.append(seg)
            in_mt41 = False
if in_mt41:
    seg['exit'] = len(tokens) - 1
    seg['flag41'] = flag41(state)
    visits.append(seg)

print(f"MT41 访问次数={len(visits)}")
for v in visits:
    print(f"  visit tok[{v['entry']}..{v['exit']}]  max_x={v['max_x']}  到过(9,2)={v['reached92']}  flag41_exit={v.get('flag41')}")

print("\nflag41 变化时刻：")
if not flag_changes:
    print("  （全程从未改变，始终=0）")
for idx, tok, p, n, cf, pos in flag_changes:
    print(f"  tok[{idx}] {tok} flag41 {p}->{n} @ {cf}{pos}")

# 末态 MT41 关键格
f = state.floors.get('MT41')
if f:
    print("\n末态 MT41 关键格 terrain：")
    for (x, y, lbl) in [(5, 6, '(5,6)blueDoor'), (6, 6, '(6,6)spine'), (7, 6, '(7,6)blueDoor'),
                        (5, 7, '(5,7)'), (7, 7, '(7,7)'), (6, 5, '(6,5)downFly点'),
                        (10, 2, '(10,2)隐藏'), (7, 1, '(7,1)')]:
        print(f"  {lbl}: terrain={f.terrain[y][x]} entity={f.entities[y][x]}")
