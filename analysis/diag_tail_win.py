"""只读诊断：route 尾部 tok6349(MT50入口)→末 token，看终局 boss 战 + win 是否触发。
dump 每 token 全状态 + Δ；并打印 MT50 boss(6,5) 事件/afterBattle 是否含 type:win。
不改任何产品代码/真值/断言。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import (
    build_initial_state, load_tokens, full_snap, diff_deltas)
from sim.simulator import step

LO = 6349


def main():
    tokens = load_tokens()
    print(f"route 总 token 数: {len(tokens)}（索引 0..{len(tokens)-1}）")
    # MT50 boss 事件源码
    mt50 = json.load(open('data/games51/floors/MT50.json', encoding='utf-8'))
    ev = mt50.get('events', {})
    print("\nMT50 events keys:", list(ev.keys()))
    for key in ('6,5', '6,6', '6,7'):
        if key in ev:
            print(f"\nMT50 events[{key}]:")
            print(json.dumps(ev[key], ensure_ascii=False, indent=1)[:2500])
    # boss monster def
    mons = mt50.get('monsters', mt50.get('_monsters', {}))
    print("\nMT50 monsters:", json.dumps(mons, ensure_ascii=False)[:800])

    print("\n" + "=" * 70)
    state = build_initial_state()
    prev = full_snap(state)
    for idx, tok in enumerate(tokens):
        state = step(state, tok)
        cur = full_snap(state)
        if idx >= LO:
            deltas = diff_deltas(prev, cur)
            mark = ('  Δ ' + ', '.join(deltas)) if deltas else ''
            print(f"tok[{idx}] {tok:<10} {cur['floor']}({cur['x']},{cur['y']}) "
                  f"HP={cur['hp']} ATK={cur['atk']} DEF={cur['df']} g={cur['gold']} "
                  f"{cur['yk']}/{cur['bk']}/{cur['rk']} k={cur['kills']}{mark}")
        prev = cur
    print(f"\n末态: HP={prev['hp']} (win 真值 14382)  楼层={prev['floor']}({prev['x']},{prev['y']})")
    # 是否有 win 标志
    won = getattr(state, 'won', getattr(state, 'win', getattr(state, 'game_over', '无该属性')))
    print(f"state.won/win/game_over = {won}")


if __name__ == '__main__':
    main()
