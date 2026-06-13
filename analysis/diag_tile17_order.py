"""只读探针②：厘清英雄踩 tile-17 占位格是在大怪【击败前】还是【击败后】。
 - 击败后踩 = 合法(afterBattle 已清占位格)，无掩盖。
 - 击败前踩 = sim 穿了实测应被挡的禁区 → 真分叉，PASS 是掩盖。
按 token 顺序，记录英雄每次进入 MT15/MT35 的 17 格时，对应大怪实体是否还在地图上(存活)。
另：确认 MT35 魔龙整局是否被击败(玩家走暗道绕过则永不击败)。
不改任何产品代码/数据/断言。
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
BIG = {'MT15': (6, 6, 258), 'MT35': (6, 7, 257)}
C17 = {
    'MT15': {(5, 4), (5, 5), (5, 6), (6, 4), (7, 4), (7, 5), (7, 6)},
    'MT35': {(5, 7), (7, 7)},
}


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


def monster_alive(state, fid):
    bx, by, num = BIG[fid]
    f = state.floors.get(fid)
    if f is None:
        return None
    return f.entities[by][bx] == num


def main():
    toks = load_tokens()
    state = build_initial_state()
    events = {'MT15': [], 'MT35': []}
    ever_killed = {'MT15': False, 'MT35': False}
    prev_alive = {'MT15': None, 'MT35': None}

    for idx, tok in enumerate(toks):
        state = step(state, tok)
        f = state.current_floor
        for fid in ('MT15', 'MT35'):
            al = monster_alive(state, fid)
            if prev_alive[fid] is True and al is False:
                ever_killed[fid] = True
                events[fid].append((idx, tok, '☠ 大怪被击败', None))
            prev_alive[fid] = al
        if f in C17:
            pos = (state.hero.x, state.hero.y)
            if pos in C17[f]:
                al = monster_alive(state, f)
                events[f].append((idx, tok, f'英雄踩占位格{pos}',
                                  '怪存活' if al else '怪已死'))

    for fid in ('MT15', 'MT35'):
        bx, by, num = BIG[fid]
        print(f'=== {fid} 大怪{num}@({bx},{by}) 事件时间线 ===')
        if not events[fid]:
            print('  (英雄从未踩占位格)')
        for idx, tok, what, st in events[fid]:
            print(f'  tok[{idx}:{tok}] {what} {("→ "+st) if st else ""}')
        print(f'  整局是否击败该大怪: {ever_killed[fid]}')
        # 判定
        pre = [e for e in events[fid] if e[3] == '怪存活']
        if pre:
            print(f'  ⚠ 有 {len(pre)} 次"击败前"踩占位格 → sim穿禁区(实测应被挡)，'
                  f'这是真分叉/掩盖')
        else:
            tramples = [e for e in events[fid] if e[3] == '怪已死']
            if tramples:
                print('  ✓ 踩占位格都在击败后(afterBattle已清)，合法，无掩盖')
            else:
                print('  ✓ 从未踩占位格')
        print()


if __name__ == '__main__':
    main()
