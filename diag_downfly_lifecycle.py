"""追踪 downFly(道具) 全生命周期 + tok4921 ITEM:52 的行为。
(a) 全程：downFly 计数每次变化的 token（拾取/使用）。
(b) tok4905..4925 逐 token：floor/pos/downFly计数 before->after，标出 ITEM/FLOOR 切层。
目的：sim 里英雄到底有没有 downFly？tok4921 用 downFly 是真用还是 0 张空放(masking bug)？"""
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


def dfcount(s):
    it = s.hero.items
    # downFly 可能存成不同 key，尽量都查
    for k in ('downFly', 'down_fly', 'I52', '52'):
        if k in it:
            return it[k], k
    return 0, None


print("(a) downFly 计数变化时刻：")
prev = 0
for idx, tok in enumerate(tokens):
    state = step(state, tok)
    c, k = dfcount(state)
    if c != prev:
        print(f"   tok[{idx}] {tok:10} downFly {prev}->{c} (key={k}) @ {state.current_floor}{(state.hero.x, state.hero.y)}")
        prev = c
print(f"   最终 downFly={prev}")

# 重放并在 4905..4925 详打
print("\n(b) tok4905..4925 逐 token：")
hero = HeroState(x=hero_init['loc']['x'], y=hero_init['loc']['y'], hp=hero_init['hp'],
                 atk=hero_init['atk'], def_=hero_init['def'], mdef=hero_init.get('mdef', 0),
                 gold=hero_init.get('gold', 0), keys={}, items=dict(hero_init.get('items', {})),
                 flags=dict(hero_init.get('flags', {})))
state = GameState(hero=hero, floors={'MT1': mt1}, current_floor='MT1', floor_ids=floor_ids,
                  visited_floors={'MT1'}, pending_floor_change=None, _floors_dir=FLOORS,
                  _key_bindings=key_bindings)
for idx, tok in enumerate(tokens):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    pc, _ = dfcount(state)
    state = step(state, tok)
    if 4905 <= idx <= 4925:
        cf = state.current_floor
        cp = (state.hero.x, state.hero.y)
        cc, _ = dfcount(state)
        chg = ' <<切层' if cf != pf else ''
        dfc = f'  downFly {pc}->{cc}' if pc != cc else f'  downFly={cc}'
        print(f"   tok[{idx}] {tok:10} {pf}{pp}->{cf}{cp}{dfc}{chg}")
