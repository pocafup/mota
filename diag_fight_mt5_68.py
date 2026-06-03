"""直接调试 token[217]: hero 走到 MT5(6,8) 时 greenSlime 战斗是否发生。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step
from sim.combat import Monster, PlayerState, compute_combat

DATA = Path('data/games51')
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(decompress(raw))
tokens = parse_rle_route(decompress(outer['route']))

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

# 快进到 token[216] (hero 在 MT5 (6,9))
for tok in tokens[:216]:
    state = step(state, tok)

print(f"After token[215]: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) hp={state.hero.hp}")

# 检查 MT5 entities[8][6]
mt5 = state.floors.get('MT5')
if mt5:
    e = mt5.entities[8][6]
    t = mt5.terrain[8][6]
    in_enemy = e in mt5._tile_to_enemy
    in_item = e in mt5._tile_to_item
    print(f"MT5 entities[8][6]={e}  terrain[8][6]={t}  in_enemy={in_enemy}  in_item={in_item}")

    # 如果是敌人，模拟战斗
    if in_enemy:
        mid = mt5._tile_to_enemy[e]
        m = mt5._monsters_db[mid]
        monster = Monster(
            id=mid, name=m['name'],
            hp=m['hp'], atk=m['atk'], def_=m['def'],
            special=m.get('special', []), n=m.get('n', 0), value=m.get('value', 0.0),
            add=m.get('add', False), atkValue=m.get('atkValue', 0.1),
            defValue=m.get('defValue', 0.9), damage=m.get('damage', 0),
        )
        hp = PlayerState(hp=state.hero.hp, atk=state.hero.atk, def_=state.hero.def_, mdef=state.hero.mdef)
        result = compute_combat(hp, monster)
        print(f"combat: {mid} → damage={result.damage}  (hero atk={state.hero.atk} def={state.hero.def_})")
        print(f"  monster: hp={m['hp']} atk={m['atk']} def={m['def']} special={m.get('special', [])}")
else:
    print("MT5 not in state.floors!")

print()
# 执行 token[216] (U from (6,9) to (6,8))
tok = tokens[216]
print(f"Executing token[216]={tok!r}")
state = step(state, tok)
print(f"After token[216]: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) hp={state.hero.hp}")

# 再次检查 entities[8][6]
mt5 = state.floors.get('MT5')
if mt5:
    print(f"MT5 entities[8][6] after={mt5.entities[8][6]}")
