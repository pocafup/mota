"""第三批真值对齐：重放到 token2501/2804/2965，对比玩家实测金标准。
口径同 test_checkpoints：tokens[:N+1]（tokens[0]=CHOICE:1 初始化，不计步）。
只读验证，不改任何产品代码/断言。FAIL 时打印「上一检查点→本检查点」窗口的
楼层/HP/ATK/DEF/钥匙变化，定位第一处分叉。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'

# (token_idx, floor, x, y, hp, atk, def_, yk)
CHECKPOINTS = [
    (2501, 'MT32', 6, 10, 143, 102, 64, 5),
    (2804, 'MT33', 7, 11, 854, 112, 68, 3),
    (2965, 'MT33', 8,  3,   6, 154, 70, 2),
]
MAXTOK = max(c[0] for c in CHECKPOINTS)


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(hero=hero, floors={'MT1': floor}, current_floor='MT1',
                     floor_ids=floor_ids, visited_floors={'MT1'},
                     pending_floor_change=None, _floors_dir=FLOORS)


def load_tokens():
    rp = next(Path('.').glob('51_*.h5route'), None) or \
         next((Path(__file__).parent.parent).glob('51_*.h5route'), None)
    raw = rp.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def snap(s):
    return (s.current_floor, s.hero.x, s.hero.y, s.hero.hp, s.hero.atk,
            s.hero.def_, s.hero.keys.get('yellowKey', 0), s.hero.keys.get('blueKey', 0))


def main():
    tokens = load_tokens()
    print(f'route 总 token 数: {len(tokens)}（需 ≥{MAXTOK + 1}）')
    if len(tokens) < MAXTOK + 1:
        print(f'🛑 token 不足，无法回放到 {MAXTOK}'); sys.exit(1)

    state = build_initial_state()
    prev = snap(state)
    snaps, trace = {}, []
    target_idx = {c[0] for c in CHECKPOINTS}

    for idx, tok in enumerate(tokens[:MAXTOK + 1]):
        try:
            state = step(state, tok)
        except Exception as e:
            print(f'\n🛑 token[{idx}] 抛异常 {type(e).__name__}: {e}')
            print(f'   前状态: {prev[0]}({prev[1]},{prev[2]}) HP={prev[3]} '
                  f'ATK={prev[4]} DEF={prev[5]} 黄={prev[6]}  token={tok}')
            sys.exit(1)
        cur = snap(state)
        if cur != prev:
            chg = []
            if cur[0] != prev[0]: chg.append(f'楼层{prev[0]}→{cur[0]}')
            if cur[3] != prev[3]: chg.append(f'HP{prev[3]}→{cur[3]}({cur[3]-prev[3]:+d})')
            if cur[4] != prev[4]: chg.append(f'ATK{prev[4]}→{cur[4]}({cur[4]-prev[4]:+d})')
            if cur[5] != prev[5]: chg.append(f'DEF{prev[5]}→{cur[5]}({cur[5]-prev[5]:+d})')
            if cur[6] != prev[6]: chg.append(f'黄{prev[6]}→{cur[6]}')
            if cur[7] != prev[7]: chg.append(f'蓝{prev[7]}→{cur[7]}')
            if chg:
                trace.append((idx, cur[1], cur[2], cur[0], ', '.join(chg), tok))
        if idx in target_idx:
            snaps[idx] = cur
        prev = cur

    prev_tok = 2400  # 上一已知检查点（token2400 端点）
    all_pass = True
    for ti, ef, ex, ey, ehp, eatk, edef, eyk in CHECKPOINTS:
        f, x, y, hp, atk, df, yk, bk = snaps[ti]
        errs = []
        if f != ef: errs.append(f'floor sim={f} 真值={ef}')
        if (x, y) != (ex, ey): errs.append(f'pos sim=({x},{y}) 真值=({ex},{ey})')
        if hp != ehp: errs.append(f'HP sim={hp} 真值={ehp} 差={hp-ehp:+d}')
        if atk != eatk: errs.append(f'ATK sim={atk} 真值={eatk} 差={atk-eatk:+d}')
        if df != edef: errs.append(f'DEF sim={df} 真值={edef} 差={df-edef:+d}')
        if yk != eyk: errs.append(f'黄 sim={yk} 真值={eyk} 差={yk-eyk:+d}')

        print(f'\n=== token[{ti}] ===')
        print(f'  sim : {f}({x},{y}) HP={hp} ATK={atk} DEF={df} 黄={yk} 蓝={bk}')
        print(f'  真值: {ef}({ex},{ey}) HP={ehp} ATK={eatk} DEF={edef} 黄={eyk}')
        if errs:
            all_pass = False
            print('  🛑 FAIL: ' + '; '.join(errs))
            print(f'  ── token[{prev_tok}→{ti}] 变化轨迹（定位分叉）──')
            win = [t for t in trace if prev_tok < t[0] <= ti]
            for idx, x2, y2, fl, c, tk in win:
                print(f'    tok[{idx}] @({x2},{y2}) {fl}: {c}  | tok={tk}')
            print('  （后续检查点依赖此处，先停在第一处 FAIL 分析）')
            break
        print('  ✅ PASS')
        prev_tok = ti

    print('\n' + ('✅ 三个新检查点全部 PASS。' if all_pass else '🛑 存在 FAIL，见上。'))
    sys.exit(0 if all_pass else 1)


if __name__ == '__main__':
    main()
