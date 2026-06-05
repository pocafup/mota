"""只读诊断：重放全程 route，切分「单层连续停留段」，统计每段决策密度。
用于提名 MVP 候选层。不改产品代码、不进搜索循环——纯分析。

单层停留段 = current_floor 连续不变的极大 token 区间。
对每段报告：层 / token 区间 / 长度 / 入口·出口属性 / kill 变化 / HP 净变化 /
段内 fly·item·choice token 计数（衡量是否含切层/道具/对话决策）。
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent / 'data/games51'
FLOORS = DATA / 'floors'


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    kb_raw = json.loads((DATA / 'replay_keybindings.json').read_text(encoding='utf-8'))
    key_bindings = {int(k): v for k, v in kb_raw.get('bindings', {}).items()}
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
        _key_bindings=key_bindings,
    )


def load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'), None)
    if route_path is None:
        route_path = next((Path(__file__).parent).glob('51_*.h5route'), None)
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def snap(state):
    h = state.hero
    return dict(
        floor=state.current_floor, x=h.x, y=h.y, hp=h.hp, atk=h.atk,
        def_=h.def_, gold=h.gold, kc=h.kill_count,
        yk=h.keys.get('yellowKey', 0), bk=h.keys.get('blueKey', 0),
        rk=h.keys.get('redKey', 0),
        shield='魔法免疫' if h.flags.get('魔法免疫') else '',
        coin='coin' if h.items.get('coin', 0) > 0 else '',
        won=state.won, dead=state.dead,
    )


def main():
    tokens = load_tokens()
    state = build_initial_state()
    # 逐 token 记录每步【之后】的快照（idx 对应 tokens[idx] 执行后）
    snaps = [snap(state)]  # idx -1 = 初始；下面 align：snaps[i] = 执行完 tokens[i]
    toks_kind = []  # 每个 token 的种类标记
    for i, tok in enumerate(tokens):
        state = step(state, tok)
        snaps.append(snap(state))
        k = 'move' if tok in ('U', 'D', 'L', 'R') else \
            'fly' if tok.startswith('FLOOR:') else \
            'item' if tok.startswith('ITEM:') else \
            'key' if tok.startswith('KEY:') else \
            'choice' if tok.startswith('CHOICE:') else \
            'movexy' if tok.startswith('MOVE:') else 'other'
        toks_kind.append(k)
    print(f'总 token={len(tokens)}  终态 won={snaps[-1]["won"]} HP={snaps[-1]["hp"]}')

    # 切分单层连续停留段：以 snaps[i].floor (执行完 token i 后所在层) 为准
    # 段 = [start_idx, end_idx]，其间 floor 恒定
    segs = []
    seg_start = 0
    for i in range(1, len(snaps)):
        if snaps[i]['floor'] != snaps[i - 1]['floor']:
            segs.append((seg_start, i - 1))
            seg_start = i
    segs.append((seg_start, len(snaps) - 1))

    # 报告：聚焦盾前(出口 shield 为空)、长度>=8、有打怪或拾取或属性变化的段
    print('\n=== 单层连续停留段（筛：长度>=8 且 (kill变化>=1 或 属性/钥匙有变)）===')
    print(f'{"层":>5} {"tok区间":>14} {"len":>4} | 入口HP/ATK/DEF/金/kill | 出口HP/ATK/DEF/金/kill | Δkill ΔHP ΔATK ΔDEF Δ金 | 钥匙出 盾 币 | fly item key choice')
    cand = []
    for (a, b) in segs:
        s_in = snaps[a]
        s_out = snaps[b]
        length = b - a
        if length < 8:
            continue
        dkc = s_out['kc'] - s_in['kc']
        dhp = s_out['hp'] - s_in['hp']
        datk = s_out['atk'] - s_in['atk']
        ddef = s_out['def_'] - s_in['def_']
        dgold = s_out['gold'] - s_in['gold']
        dkeys = (s_out['yk'] + s_out['bk'] + s_out['rk']) - (s_in['yk'] + s_in['bk'] + s_in['rk'])
        if dkc == 0 and datk == 0 and ddef == 0 and dkeys == 0 and dhp == 0:
            continue
        # 段内 token 种类计数（tokens[a..b-1] 即产生这些 snap 的动作）
        kinds = toks_kind[a:b]
        nfly = kinds.count('fly')
        nitem = kinds.count('item')
        nkey = kinds.count('key')
        nchoice = kinds.count('choice')
        floor = s_out['floor']
        keysout = f"{s_out['yk']}/{s_out['bk']}/{s_out['rk']}"
        print(f'{floor:>5} {f"[{a}-{b}]":>14} {length:>4} | '
              f'{s_in["hp"]:>5}/{s_in["atk"]:>3}/{s_in["def_"]:>3}/{s_in["gold"]:>5}/{s_in["kc"]:>2} | '
              f'{s_out["hp"]:>5}/{s_out["atk"]:>3}/{s_out["def_"]:>3}/{s_out["gold"]:>5}/{s_out["kc"]:>2} | '
              f'{dkc:>+3} {dhp:>+5} {datk:>+3} {ddef:>+3} {dgold:>+5} | '
              f'{keysout:>6} {s_out["shield"]:>4} {s_out["coin"]:>4} | '
              f'{nfly:>3} {nitem:>4} {nkey:>3} {nchoice:>6}')
        cand.append((floor, a, b, length, dkc, dhp, datk, ddef, dgold))

    # 额外：标注哪些层是单次/多次停留段（碎片化程度）
    from collections import Counter
    floor_seg_count = Counter(snaps[b]['floor'] for (a, b) in segs if (b - a) >= 8)
    print('\n=== 各层「>=8长停留段」出现次数（次数=1 → 该层基本单次访问，最干净）===')
    for fl, c in sorted(floor_seg_count.items(), key=lambda kv: (kv[1], kv[0])):
        print(f'  {fl}: {c}')


if __name__ == '__main__':
    main()
