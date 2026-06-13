"""逐格追踪 token[0..210]，重点看 token[82..185] 在 MT3 的完整轨迹及 ATK 变化。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(decompress(raw))
tokens = parse_rle_route(decompress(outer['route']))[:220]

hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
floor = load_floor(FLOORS / 'MT1.json')
hero = HeroState(
    x=hero_init['loc']['x'], y=hero_init['loc']['y'],
    hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
    mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
    keys={}, items=dict(hero_init.get('items', {})), flags=dict(hero_init.get('flags', {})),
)
state = GameState(hero=hero, floors={'MT1': floor}, current_floor='MT1',
    floor_ids=FLOOR_IDS, visited_floors={'MT1'}, pending_floor_change=None, _floors_dir=FLOORS)

print(f"{'idx':>4}  {'tok':<10}  {'floor':<5}  {'before':>9}  {'after':>9}  {'hp':>5}  {'atk':>4}  {'def':>4}  {'keys'}")
print('-'*90)

prev_atk = state.hero.atk
for idx, tok in enumerate(tokens):
    fl_before = state.current_floor
    pos_before = (state.hero.x, state.hero.y)
    hp_before = state.hero.hp
    atk_before = state.hero.atk

    state = step(state, tok)

    fl_after = state.current_floor
    pos_after = (state.hero.x, state.hero.y)
    atk_after = state.hero.atk
    hp_after = state.hero.hp

    moved = pos_before != pos_after or fl_before != fl_after
    atk_changed = atk_after != atk_before
    hp_changed = hp_before != hp_after
    fl_changed = fl_before != fl_after

    # 打印条件：atk变化、hp变化、切层、或在 MT3/MT4 的移动步骤(82..210)
    print_this = (
        atk_changed or fl_changed or
        (idx >= 82 and idx <= 210 and (hp_changed or moved))
    )

    if print_this:
        marker = ""
        if atk_changed:
            marker = f"  ★ ATK {atk_before}→{atk_after}"
        elif fl_changed:
            marker = f"  → 切层 {fl_before}→{fl_after}"
        elif hp_changed:
            marker = f"  ±HP {hp_before-hp_after:+}"

        yk = state.hero.keys.get('yellowKey', 0)
        bk = state.hero.keys.get('blueKey', 0)
        print(f"{idx:>4}  {tok:<10}  {fl_after:<5}  "
              f"({pos_before[0]},{pos_before[1]})  ({pos_after[0]},{pos_after[1]})  "
              f"{hp_after:>5}  {atk_after:>4}  {state.hero.def_:>4}  Y={yk} B={bk}{marker}")
