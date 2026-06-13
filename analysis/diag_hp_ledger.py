"""
tok[1300..1400] 逐笔HP变化清单
每行 = tok序号 | 楼层 | 坐标 | HP变化 | 类型 | 名称
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, FloorState, load_floor, step

DATA   = Path('data/games51')
FLOORS = DATA / 'floors'

monsters_db = json.loads((DATA / 'monsters.json').read_text(encoding='utf-8'))
items_db    = json.loads((DATA / 'items.json').read_text(encoding='utf-8'))
tiles_db    = json.loads((DATA / 'tiles.json').read_text(encoding='utf-8'))

# tile_int -> (kind, id_str)  用于事后查怪/道具名
_tile_to_enemy = {int(k): v['_monster'] for k, v in tiles_db['enemys'].items()}
_tile_to_item  = {int(k): v['_item']    for k, v in tiles_db['items'].items()}

def classify_tile(tile_int):
    if tile_int in _tile_to_enemy:
        mid  = _tile_to_enemy[tile_int]
        mobj = monsters_db.get(mid, {})
        return 'monster', mobj.get('name', mid)
    if tile_int in _tile_to_item:
        iid  = _tile_to_item[tile_int]
        iobj = items_db.get(iid, {})
        return 'item', iobj.get('name', iid)
    return '?', f'tile={tile_int}'

def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hi = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    fl = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hi['loc']['x'], y=hi['loc']['y'],
        hp=hi['hp'], atk=hi['atk'],
        def_=hi.get('def_', hi.get('def', 10)),
        mdef=hi.get('mdef', 0), gold=hi.get('gold', 0),
        keys={}, items=dict(hi.get('items', {})),
        flags=dict(hi.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': fl}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
    )

def load_tokens():
    rp = next(Path('.').glob('51_*.h5route'), None)
    raw = rp.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))

def entity_at(fl: FloorState, x: int, y: int):
    h = len(fl.entities)
    w = len(fl.entities[0]) if h else 0
    if 0 <= y < h and 0 <= x < w:
        return fl.entities[y][x]
    return 0

DIR = {'U': (0,-1), 'D': (0,1), 'L': (-1,0), 'R': (1,0)}

toks  = load_tokens()
state = build_initial_state()

START, END = 1300, 1400

for idx, tok in enumerate(toks[:START]):
    state = step(state, tok)

rows = []

for idx in range(START, END + 1):
    tok = toks[idx]
    prev_hp    = state.hero.hp
    prev_floor = state.current_floor
    prev_x, prev_y = state.hero.x, state.hero.y

    # 预取目的地实体（仅方向键有意义）
    dest_entity_tile = 0
    dest_x = dest_y = None
    if tok in DIR and state.current_floor in state.floors:
        dx, dy = DIR[tok]
        dest_x = prev_x + dx
        dest_y = prev_y + dy
        fl = state.floors[state.current_floor]
        dest_entity_tile = entity_at(fl, dest_x, dest_y)

    state = step(state, tok)

    cur_hp    = state.hero.hp
    cur_floor = state.current_floor
    delta     = cur_hp - prev_hp

    if delta != 0:
        kind, name = classify_tile(dest_entity_tile)
        rows.append((idx, prev_floor, state.hero.x, state.hero.y, delta, kind, name, tok))

# ── 输出 ──────────────────────────────────────────────────────────────────────
header = f"{'tok':>4}  {'楼层':6}  {'坐标':8}  {'HP变化':>8}  {'类型':8}  名称"
sep    = '-' * 70
lines  = [header, sep]
for (i, fl, x, y, d, kind, name, tok) in rows:
    sign = f"+{d}" if d > 0 else str(d)
    lines.append(f"{i:4d}  {fl:6s}  ({x:2d},{y:2d})    {sign:>6s}  {kind:8s}  {name}")

output = '\n'.join(lines)
out_path = Path('diag_hp_ledger_1300_1400.txt')
out_path.write_text(output, encoding='utf-8')
print(output)
print(f"\n=> 写入 {out_path}  共 {len(rows)} 笔HP变化")
