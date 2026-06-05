"""决定性检查：MT41 唯一左右通道 = (7,6) blueDoor(82)。
扫描全程：(a) 英雄每次站到 (6,6) 时的 bk 数与 ter[6][7]；(b) ter[6][7] 每次变化；
(c) 英雄每次站到 (5,6) 或 (7,6) 旁尝试开门。看 sim 是否/何时打开 (7,6)。"""
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

prev76 = None
prev_bk_at_66 = None
for idx, tok in enumerate(tokens):
    pf = state.current_floor
    pp = (state.hero.x, state.hero.y)
    state = step(state, tok)
    f41 = state.floors.get('MT41')
    if f41 is None:
        continue
    d76 = f41.terrain[6][7]
    bk = state.hero.keys.get('blueKey', 0)
    # (b) ter[6][7] 变化
    if prev76 is not None and d76 != prev76:
        print(f"tok[{idx}] {tok}: MT41 ter[6][7](门(7,6)) {prev76}->{d76}  bk={bk}")
    prev76 = d76
    # (a) 站到 (6,6)
    if state.current_floor == 'MT41' and (state.hero.x, state.hero.y) == (6, 6):
        print(f"tok[{idx}] {tok}: 英雄@ (6,6)  bk={bk}  ter[6][7]={d76}(82=关闭)")
    # (c) 在 (6,6) 朝右按 R 撞 (7,6) / 在 (8,6) 朝左撞
    if pf == 'MT41' and pp == (6, 6) and tok == 'R':
        print(f"tok[{idx}] R from (6,6): 尝试过 (7,6)门 → 现在@{(state.hero.x, state.hero.y)} bk={bk} ter[6][7]={d76}")

# 终态
f41 = state.floors.get('MT41')
print(f"\n最终 MT41 ter[6][7] = {f41.terrain[6][7]} (82=blueDoor仍关闭，0=已开)")
print(f"最终英雄 blueKey = {state.hero.keys.get('blueKey', 0)}")
