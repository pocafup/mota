"""验证终局段真值 token4723/4925/5156（MT0 已落盘后）。
4723(MT41) 不依赖 MT0；4925(MT0)/5156 在 tok4921 downFly→MT0 之后。
验证 floor/HP/ATK/DEF/yk/bk/坐标/金币。5156 金=1768 是幸运金币 coin×2 的 oracle。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'

# (token, floor, hp, atk, def, yk, bk, x, y, gold)  None=不验
GT = [
    (4723, 'MT41', 4600, 212, 309, 14, None, 3, 6, None),
    (4925, 'MT0',  4943, 217, 314, 20, 1,    2, 5, None),  # 玩家2026-06-05裁定(2,5)为真，原(1,5)系误录
    (5156, None,   5193, 217, 314, 17, 1,    9, 6, 1768),
]


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


def load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'))
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


tokens = load_tokens()
state = build_initial_state()
targets = {t[0]: t for t in GT}
maxt = max(targets)

for idx, tok in enumerate(tokens[:maxt + 1]):
    try:
        state = step(state, tok)
    except Exception as e:
        print(f"\n🛑 tok[{idx}] = {tok} 崩溃: {type(e).__name__}: {e}")
        print(f"   （崩溃前 floor={state.current_floor} pos=({state.hero.x},{state.hero.y})）")
        break
    if idx in targets:
        _, ef, eh, ea, ed, eyk, ebk, ex, ey, eg = targets[idx]
        h = state.hero
        sf = state.current_floor
        syk = h.keys.get('yellowKey', 0)
        sbk = h.keys.get('blueKey', 0)
        errs = []
        if ef and sf != ef: errs.append(f"floor sim={sf} 真={ef}")
        if (ex, ey) != (h.x, h.y): errs.append(f"pos sim=({h.x},{h.y}) 真=({ex},{ey})")
        if h.hp != eh: errs.append(f"HP sim={h.hp} 真={eh} 差{h.hp-eh:+d}")
        if h.atk != ea: errs.append(f"ATK sim={h.atk} 真={ea} 差{h.atk-ea:+d}")
        if h.def_ != ed: errs.append(f"DEF sim={h.def_} 真={ed} 差{h.def_-ed:+d}")
        if eyk is not None and syk != eyk: errs.append(f"yk sim={syk} 真={eyk} 差{syk-eyk:+d}")
        if ebk is not None and sbk != ebk: errs.append(f"bk sim={sbk} 真={ebk} 差{sbk-ebk:+d}")
        if eg is not None and h.gold != eg: errs.append(f"金 sim={h.gold} 真={eg} 差{h.gold-eg:+d}")
        tag = "✅ PASS" if not errs else "❌ FAIL"
        print(f"[{tag}] tok[{idx}] sim: floor={sf}({h.x},{h.y}) HP={h.hp} ATK={h.atk} "
              f"DEF={h.def_} yk={syk} bk={sbk} 金={h.gold} coin={h.items.get('coin',0)}")
        if errs:
            print("        " + " | ".join(errs))
