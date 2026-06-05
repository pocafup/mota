"""只读修复模拟：不改产品代码，仅在脚本内于"踩 MT29(6,2) 后"手动把
MT2 events['10,11'].enable 置 True（模拟 show 跨层修复后的效果），
重放到 token3371，看错位修正后 HP 是否回到真值 606。
对照真值: token3371 = MT32(1,4) HP=606 ATK=158 DEF=70 黄=3。
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


def run(patch: bool):
    toks = load_tokens()
    state = build_initial_state()
    patched = False
    hp_window = []
    for idx in range(0, 3372):
        if idx >= len(toks):
            break
        tok = toks[idx]
        state = step(state, tok)
        # 踩 MT29(6,2) 之后注入修复：把 MT2(10,11) 小偷显形（模拟 show 跨层）
        if patch and not patched and state.current_floor == 'MT29' \
                and (state.hero.x, state.hero.y) == (6, 2):
            mt2 = state.floors.get('MT2')
            if mt2 is not None:
                ev = mt2.events.get('10,11')
                if isinstance(ev, dict):
                    ev['enable'] = True
                    patched = True
        if 3260 <= idx <= 3371:
            hp_window.append((idx, tok, state.current_floor,
                              state.hero.x, state.hero.y, state.hero.hp,
                              state.hero.keys.get('yellowKey', 0)))
    return hp_window, patched


def main():
    print('=== run1: 原样（show 跨层 bug 在，错位）===')
    w0, _ = run(patch=False)
    print('=== run2: 注入修复（踩 MT29(6,2) 后强制 MT2(10,11) 显形）===')
    w1, patched = run(patch=True)
    print(f'    注入是否生效: {patched}')

    def find(w, i):
        for r in w:
            if r[0] == i:
                return r
        return None

    print('\n逐格对照（tok | run1 原样 | run2 修复后）:')
    print(f'{"tok":>5} | {"run1 floor(x,y) HP 黄":28} | run2 floor(x,y) HP 黄')
    for i in range(3263, 3277):
        r0, r1 = find(w0, i), find(w1, i)
        s0 = f'{r0[2]}({r0[3]},{r0[4]}) HP={r0[5]} y{r0[6]}' if r0 else '-'
        s1 = f'{r1[2]}({r1[3]},{r1[4]}) HP={r1[5]} y{r1[6]}' if r1 else '-'
        mark = '' if s0 == s1 else '  ←差异'
        print(f'{i:>5} | {s0:28} | {s1}{mark}')

    print('\n关键 HP 事件点（run2 修复后）:')
    prev = None
    for r in w1:
        i, tok, fl, x, y, hp, yk = r
        if prev is not None and hp != prev:
            print(f'  tok[{i}:{tok}] {fl}({x},{y}) HP {prev}→{hp} ({hp-prev:+d}) 黄={yk}')
        prev = hp

    r0e, r1e = find(w0, 3371), find(w1, 3371)
    print('\n=== token3371 终局对照（真值 MT32(1,4) HP=606 黄=3）===')
    if r0e:
        print(f'  run1 原样 : {r0e[2]}({r0e[3]},{r0e[4]}) HP={r0e[5]} 黄={r0e[6]}  '
              f'(差真值 HP {r0e[5]-606:+d})')
    if r1e:
        print(f'  run2 修复 : {r1e[2]}({r1e[3]},{r1e[4]}) HP={r1e[5]} 黄={r1e[6]}  '
              f'(差真值 HP {r1e[5]-606:+d})')


if __name__ == '__main__':
    main()
