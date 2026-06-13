"""(1) BFS：在 sim 的 MT41 初始地图上，从 (6,1)/(6,11) 出发，门/怪/道具全当可通过，
墙(1)与 noPass(330)当障碍——判 (9,2)/(10,2)/(6,5) 是否结构可达。
(2) 全程扫描：英雄在 MT41 到过的最大 x（看是否进过右半区 x>=7）。"""
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'

floor = load_floor(FLOORS / 'MT41.json')
H = len(floor.terrain)
W = len(floor.terrain[0])
WALLS = {1, 330}  # 墙 + unbreakableWall(noPass)


def passable(x, y):
    if not (0 <= x < W and 0 <= y < H):
        return False
    t = floor.terrain[y][x]
    # 门(81/82)/楼梯/装饰当可通过；实体格（怪/道具）当可通过；仅墙/noPass 阻挡
    if t in WALLS:
        return False
    return True


def bfs(sx, sy):
    seen = {(sx, sy)}
    q = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if (nx, ny) not in seen and passable(nx, ny):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


for start in [(6, 1), (6, 11), (6, 2)]:
    reach = bfs(*start)
    print(f"从 {start} BFS（门/怪/道具皆可过，仅墙/330阻挡）：")
    for tgt in [(9, 2), (10, 2), (6, 5), (8, 2), (9, 5), (9, 6)]:
        ter = floor.terrain[tgt[1]][tgt[0]]
        ent = floor.entities[tgt[1]][tgt[0]]
        print(f"   {tgt} 可达={tgt in reach}  ter={ter} ent={ent}")
    print()

# 全程：英雄在 MT41 到过的最大 x、是否到过 x>=7
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

maxx = -1
first_right_tok = None
mt41_tokens = 0
for idx, tok in enumerate(tokens):
    state = step(state, tok)
    if state.current_floor == 'MT41':
        mt41_tokens += 1
        if state.hero.x > maxx:
            maxx = state.hero.x
        if state.hero.x >= 7 and first_right_tok is None:
            first_right_tok = (idx, state.hero.x, state.hero.y)
print(f"全程在 MT41 的 token 数={mt41_tokens}，英雄到过的最大 x={maxx}")
print(f"首次进入右半区(x>=7)：{first_right_tok}")
