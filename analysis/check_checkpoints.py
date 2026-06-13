"""重放存档到每个检查点，与真值比对。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

CHECKPOINTS = [
    (100,  'MT3',  800, 10, 10),
    (200,  'MT4',  666, 20, 10),
    (300,  'MT5',  604, 21, 10),
    (400,  'MT7',  304, 21, 10),
    (500,  'MT9',  290, 21, 10),
    (600,  'MT3',  305, 23, 22),
    (700,  'MT8',  218, 25, 23),
    (800,  'MT10', 229, 26, 25),
    (900,  'MT7',  254, 26, 27),
    (1000, 'MT10', 304, 27, 27),
    (1100, 'MT1',  546, 27, 27),
    (1200, 'MT10', 510, 27, 27),
    (1300, 'MT14', 785, 42, 30),
]

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(decompress(raw))
tokens = parse_rle_route(decompress(outer['route']))[:1301]

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

cp_iter = iter(CHECKPOINTS)
next_cp = next(cp_iter)

print(f"{'tok':>5}  {'fl_真':>5}  {'fl_模':>5}  {'hp_真':>6}  {'hp_模':>6}  {'hp_差':>6}  "
      f"{'atk_真':>6}  {'atk_模':>6}  {'def_真':>6}  {'def_模':>6}  状态")
print('-' * 100)

first_fail = None
for idx, tok in enumerate(tokens):
    state = step(state, tok)
    if next_cp and idx + 1 == next_cp[0]:
        cp_tok, cp_fl, cp_hp, cp_atk, cp_def = next_cp
        sim_fl  = state.current_floor
        sim_hp  = state.hero.hp
        sim_atk = state.hero.atk
        sim_def = state.hero.def_

        fl_ok  = sim_fl == cp_fl
        hp_ok  = sim_hp == cp_hp
        atk_ok = sim_atk == cp_atk
        def_ok = sim_def == cp_def
        ok = fl_ok and hp_ok and atk_ok and def_ok
        label = 'OK' if ok else 'FAIL'
        if not ok and first_fail is None:
            first_fail = cp_tok

        print(f"{cp_tok:>5}  {cp_fl:>5}  {sim_fl:>5}  {cp_hp:>6}  {sim_hp:>6}  "
              f"{sim_hp-cp_hp:>+6}  {cp_atk:>6}  {sim_atk:>6}  {cp_def:>6}  {sim_def:>6}  "
              f"{'✓' if fl_ok else 'FL!'} {'✓' if hp_ok else 'HP!'} "
              f"{'✓' if atk_ok else 'ATK!'} {'✓' if def_ok else 'DEF!'}  {label}")

        try:
            next_cp = next(cp_iter)
        except StopIteration:
            next_cp = None

print()
if first_fail:
    print(f"第一个 FAIL 检查点：token[{first_fail}]")
else:
    print("全部检查点通过！")
