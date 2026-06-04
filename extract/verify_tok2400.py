"""token2400 端点验证：英雄从 token2323 的 MT20 楼梯连爬到 MT28。
真值（玩家实测金标准）：token2400 → MT28(2,11) HP=1261 ATK=78 DEF=64 黄钥匙=5。

口径同 test_checkpoints：tokens[:N+1]（tokens[0]=CHOICE:1 初始化，不计步）。
若 FAIL，打印 2300→2400 窗口的楼层切换 + 属性/钥匙变化，定位第一处分叉。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'

EXP = {'floor': 'MT28', 'x': 2, 'y': 11, 'hp': 1261, 'atk': 78, 'def_': 64, 'yk': 5}
TOK = 2400


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
    print(f'route 总 token 数: {len(tokens)}（需 ≥{TOK+1}）')
    if len(tokens) < TOK + 1:
        print(f'🛑 token 不足，无法回放到 {TOK}'); sys.exit(1)

    state = build_initial_state()
    prev = snap(state)
    trace = []
    for idx, tok in enumerate(tokens[:TOK + 1]):
        try:
            state = step(state, tok)
        except Exception as e:
            print(f'\n🛑 在 token[{idx}] 抛异常: {type(e).__name__}: {e}')
            print(f'   异常前状态: floor={prev[0]} pos=({prev[1]},{prev[2]}) '
                  f'HP={prev[3]} ATK={prev[4]} DEF={prev[5]} 黄={prev[6]}')
            print(f'   token 内容: {tok}')
            sys.exit(1)
        cur = snap(state)
        if 2300 <= idx <= TOK and (cur[0] != prev[0] or cur[3] != prev[3] or
                                   cur[6] != prev[6] or cur[7] != prev[7]):
            chg = []
            if cur[0] != prev[0]: chg.append(f'楼层 {prev[0]}→{cur[0]}')
            if cur[3] != prev[3]: chg.append(f'HP {prev[3]}→{cur[3]}({cur[3]-prev[3]:+d})')
            if cur[6] != prev[6]: chg.append(f'黄钥匙 {prev[6]}→{cur[6]}')
            if cur[7] != prev[7]: chg.append(f'蓝钥匙 {prev[7]}→{cur[7]}')
            trace.append(f'  tok[{idx}] @({cur[1]},{cur[2]}) {cur[0]}: ' + ', '.join(chg) + f'  | tok={tok}')
        prev = cur

    f, x, y, hp, atk, df, yk, bk = snap(state)
    print(f'\n2300→{TOK} 窗口关键变化（楼层/HP/钥匙）:')
    print('\n'.join(trace) if trace else '  （无）')

    print(f'\n=== token[{TOK}] 端点 ===')
    print(f'  sim : {f}({x},{y}) HP={hp} ATK={atk} DEF={df} 黄={yk} 蓝={bk}')
    print(f'  真值: {EXP["floor"]}({EXP["x"]},{EXP["y"]}) HP={EXP["hp"]} '
          f'ATK={EXP["atk"]} DEF={EXP["def_"]} 黄={EXP["yk"]}')

    errs = []
    if f != EXP['floor']:   errs.append(f'floor: sim={f} 真值={EXP["floor"]}')
    if (x, y) != (EXP['x'], EXP['y']): errs.append(f'pos: sim=({x},{y}) 真值=({EXP["x"]},{EXP["y"]})')
    if hp != EXP['hp']:     errs.append(f'HP: sim={hp} 真值={EXP["hp"]} 差={hp-EXP["hp"]:+d}')
    if atk != EXP['atk']:   errs.append(f'ATK: sim={atk} 真值={EXP["atk"]} 差={atk-EXP["atk"]:+d}')
    if df != EXP['def_']:   errs.append(f'DEF: sim={df} 真值={EXP["def_"]} 差={df-EXP["def_"]:+d}')
    if yk != EXP['yk']:     errs.append(f'黄钥匙: sim={yk} 真值={EXP["yk"]} 差={yk-EXP["yk"]:+d}')

    if errs:
        print('\n🛑 FAIL:'); [print('   '+e) for e in errs]
        sys.exit(1)
    print('\n✅ PASS：token2400 端点完全吻合（MT28(2,11) 1261/78/64 5黄）。')


if __name__ == '__main__':
    main()
