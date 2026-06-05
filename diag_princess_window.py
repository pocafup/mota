"""只读诊断：公主传送链窗口 tok6248(MT25)→6349(MT50) 逐 token 全状态。
6349 真值 HP=32487，sim=25977，差 -6510；楼层/坐标 MT50(6,7) 吻合(传送链走通)。
本脚本回放整条 route，dump [6248,6349] 每 token 的 楼层(x,y)/HP/ATK/DEF/金/钥匙/击杀 + Δ，
重点标出 HP 变化，定位 6510 HP 缺口位置。不改任何产品代码/真值/断言。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import (
    build_initial_state, load_tokens, full_snap, diff_deltas)
from sim.simulator import step

LO, HI = 6248, 6349


def main():
    tokens = load_tokens()
    state = build_initial_state()
    prev = full_snap(state)
    hp_total_delta = 0
    for idx, tok in enumerate(tokens[:HI + 1]):
        state = step(state, tok)
        cur = full_snap(state)
        deltas = diff_deltas(prev, cur)
        if LO <= idx <= HI:
            if cur['hp'] != prev['hp']:
                hp_total_delta += cur['hp'] - prev['hp']
            mark = ''
            if deltas:
                mark = '  Δ ' + ', '.join(deltas)
            print(f"tok[{idx}] {tok:<10} {cur['floor']}({cur['x']},{cur['y']}) "
                  f"HP={cur['hp']} ATK={cur['atk']} DEF={cur['df']} g={cur['gold']} "
                  f"{cur['yk']}/{cur['bk']}/{cur['rk']} k={cur['kills']}{mark}")
        prev = cur
    print(f"\n窗口内 HP 净变化合计 = {hp_total_delta:+d}")
    print(f"6349 真值 HP=32487 / sim HP={prev['hp']} / 差={prev['hp']-32487:+d}")


if __name__ == '__main__':
    main()
