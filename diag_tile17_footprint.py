"""只读探针：坐实 tile 17 = bigImage 占位碰撞格。不改任何产品代码/数据/断言。
回答：
 1) 全塔 tile 17 出现在哪些层哪些格，是否都贴着大怪(257魔龙/258章鱼)；有没有"独立的17"(如MT10)
 2) 重放玩家存档，记录英雄在 MT15/MT35 踩过的所有格，与各自的17占位格求交集——
    若英雄从没踩过17(只从正下方打)，则 MT15 PASS 是"绕行掩盖"，不是 sim 正确。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hi = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    fl = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hi['loc']['x'], y=hi['loc']['y'],
        hp=hi['hp'], atk=hi['atk'], def_=hi['def'],
        mdef=hi.get('mdef', 0), gold=hi.get('gold', 0),
        keys={}, items=dict(hi.get('items', {})),
        flags=dict(hi.get('flags', {})),
    )
    return GameState(hero=hero, floors={'MT1': fl}, current_floor='MT1',
                     floor_ids=floor_ids, visited_floors={'MT1'},
                     pending_floor_change=None, _floors_dir=FLOORS)


def load_tokens():
    rp = next(Path('.').glob('51_*.h5route'), None)
    raw = rp.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def tile17_cells(floor_id):
    """返回该层原始 map 中所有 tile==17 的 (x,y)。"""
    f = json.loads((FLOORS / f'{floor_id}.json').read_text(encoding='utf-8'))
    cells = set()
    for y, row in enumerate(f['map']):
        for x, v in enumerate(row):
            if v == 17:
                cells.add((x, y))
    return cells


def big_enemy_cells(floor_id):
    f = json.loads((FLOORS / f'{floor_id}.json').read_text(encoding='utf-8'))
    out = []
    for y, row in enumerate(f['map']):
        for x, v in enumerate(row):
            if v in (257, 258):
                out.append((x, y, v))
    return out


def main():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

    print('=== (1) 全塔 tile 17 分布 + 附近大怪 ===')
    for fid in floor_ids:
        p = FLOORS / f'{fid}.json'
        if not p.exists():
            continue
        c17 = tile17_cells(fid)
        if not c17:
            continue
        big = big_enemy_cells(fid)
        big_s = ', '.join(f'{v}@({x},{y})' for x, y, v in big) or '无'
        # 判断17是否都在某大怪的曼哈顿≤2范围内
        near = all(any(abs(x-bx) <= 1 and abs(y-by) <= 1 for bx, by, _ in big)
                   for (x, y) in c17) if big else False
        print(f'  {fid}: 17×{len(c17)} @ {sorted(c17)}  大怪[{big_s}]  '
              f'{"全贴大怪(九宫格占位)" if near else "★有独立17(非占位)"}')

    print('\n=== (2) 重放玩家存档，记录 MT15/MT35 踩过的格 ===')
    toks = load_tokens()
    state = build_initial_state()
    visited = {'MT15': set(), 'MT35': set()}
    for idx, tok in enumerate(toks):
        state = step(state, tok)
        f = state.current_floor
        if f in visited:
            visited[f].add((state.hero.x, state.hero.y))

    for fid in ('MT15', 'MT35'):
        c17 = tile17_cells(fid)
        big = big_enemy_cells(fid)
        stepped = visited[fid]
        overlap = stepped & c17
        print(f'\n  --- {fid} (大怪 {[(x,y,v) for x,y,v in big]}) ---')
        print(f'    占位17格({len(c17)}): {sorted(c17)}')
        print(f'    英雄踩过的格({len(stepped)}): {sorted(stepped)}')
        if overlap:
            print(f'    ⚠ 英雄踩进了17占位格: {sorted(overlap)} ← sim穿禁区(实测应被挡)')
        else:
            print(f'    ✓ 英雄从未踩17占位格 → PASS靠绕行(从正下方打)，掩盖了"17应noPass"的bug')
        # 列出英雄是否到过怪正下方
        for x, y, v in big:
            below = (x, y + 1)
            print(f'    大怪({x},{y})正下方{below} 英雄{"到过" if below in stepped else "没到过"}')


if __name__ == '__main__':
    main()
