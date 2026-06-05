"""只读探针：坐实 MT2(10,11) 小偷的放置机制（MT29 events[6,2] 跨层 show）。
不改任何产品代码/数据/断言。回答：
  1) MT23 上 whiteWall2 初始数量（决定 MT29 外层 searchBlock 条件真假）
  2) 英雄在 tok3265 之前何时踩 MT29(6,2)，那一刻外层/内层条件求值 → 走哪条分支
  3) tok3255..3276 逐格，MT2(10,11) 的实体/enable 状态（看 sim 里小偷有没有出现）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import (
    GameState, HeroState, load_floor, step,
    _search_block_count, _eval_single, _load_floor_if_needed,
)

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


def mt2_thief_state(state):
    """返回 (entity_tile@(10,11), events['10,11'].enable) ，MT2 未加载则 None。"""
    f = state.floors.get('MT2')
    if f is None:
        return None
    ent = f.entities[11][10]
    ev = f.events.get('10,11')
    en = ev.get('enable') if isinstance(ev, dict) else None
    return (ent, en)


def main():
    toks = load_tokens()
    state = build_initial_state()

    # (A) MT23 whiteWall2 初始数量
    _load_floor_if_needed(state, 'MT23')
    n_ww = _search_block_count(state, 'whiteWall2', 'MT23')
    print(f'(A) MT23 上 whiteWall2 初始数量 = {n_ww}')
    print(f'    → 外层条件 searchBlock>0 = {n_ww > 0}  '
          f'(>0 走 true 分支再看 flag:额外功能开关；==0 走 false 分支直接 show)')

    OUTER = "(core.searchBlock('whiteWall2', 'MT23').length > 0)"
    INNER = "flag:额外功能开关"

    prev_floor = state.current_floor
    on_mt29_steps = []
    branch_report = []

    for idx in range(0, 3277):
        if idx >= len(toks):
            break
        tok = toks[idx]
        # 踩 MT29(6,2)：英雄在 MT29 且即将/正在撞 (6,2) thief。
        # 进入 MT29 时先 dump 一次条件。
        before_floor = state.current_floor
        state = step(state, tok)
        f, x, y = state.current_floor, state.hero.x, state.hero.y

        if f == 'MT29':
            on_mt29_steps.append((idx, x, y, tok))
        if before_floor != 'MT29' and f == 'MT29':
            outer = _eval_single(OUTER, state)
            inner = _eval_single(INNER, state)
            branch_report.append(
                (idx, 'ENTER MT29', outer, inner,
                 _search_block_count(state, 'whiteWall2', 'MT23'),
                 state.hero.flags.get('额外功能开关')))

        # 逐格窗口 3255..3276
        if 3255 <= idx <= 3276:
            ts = mt2_thief_state(state)
            print(f'  tok[{idx}:{tok}] {f}({x},{y})  MT2(10,11)实体/enable={ts}')

    print('\n(B) 英雄在 MT29 的轨迹（全部 token≤3276）:')
    if not on_mt29_steps:
        print('    ⚠ 英雄在 tok≤3276 内从未处于 MT29！')
    else:
        for idx, x, y, tok in on_mt29_steps:
            print(f'    tok[{idx}:{tok}] MT29({x},{y})')

    print('\n(C) 每次进入 MT29 时的分支条件求值:')
    for idx, tag, outer, inner, cnt, flagv in branch_report:
        # 真实分支：outer==0 → false分支 show；outer>0 & inner → true→true show；
        #           outer>0 & !inner → true→false 不show
        if not outer:
            branch = 'false 分支 → 执行 show MT2(10,11)'
        elif inner:
            branch = 'true→true → 执行 show MT2(10,11)'
        else:
            branch = 'true→false → 只对话，不 show'
        print(f'    tok[{idx}] {tag}: searchBlock>0={outer}(cnt={cnt}) '
              f'flag:额外功能开关={inner}({flagv!r}) ⇒ sim 走【{branch}】')

    # 终局 MT2(10,11) 状态
    ts = mt2_thief_state(state)
    print(f'\n(D) tok3276 结束时 MT2(10,11) 实体/enable = {ts} '
          f'(123=thief实体在位; enable True=显示/阻挡, False=隐藏/直接通过)')


if __name__ == '__main__':
    main()
