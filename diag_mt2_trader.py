"""只读诊断：MT2 specialTrader(11,7) 3% 祝福。
回放到 tok6204..6225，打印每 token 的英雄位置/ATK/DEF + 是否撞 (11,7)/CHOICE，
并单独验算 _eval_value_expr('Math.round(status:atk*0.03)') 当前返回值（证明 BUG=返回0）。
不改任何产品代码/真值/断言。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step, _eval_value_expr

LO, HI = 6204, 6225


def main():
    tokens = load_tokens()
    state = build_initial_state()
    for idx, tok in enumerate(tokens[:HI + 1]):
        prev = (state.hero.atk, state.hero.def_)
        state = step(state, tok)
        if idx < LO:
            continue
        h = state.hero
        mark = ""
        if (h.atk, h.def_) != prev:
            mark = f"  <<< ATK/DEF 变化 {prev} → ({h.atk},{h.def_})"
        if state.current_floor == "MT2" and h.x == 11 and h.y == 8:
            mark += "  [在(11,8)，(11,7)=specialTrader 正上方]"
        print(f"tok[{idx}] {tok:<10} {state.current_floor}({h.x},{h.y}) "
              f"ATK={h.atk} DEF={h.def_}{mark}")
        if state.current_floor == "MT2":
            # 当前代码下，对当前 atk/def 求值祝福表达式
            ra = _eval_value_expr("Math.round(status:atk*0.03)", state)
            rd = _eval_value_expr("Math.round(status:def*0.03)", state)
            print(f"        _eval_value_expr('Math.round(status:atk*0.03)')={ra}  "
                  f"('...def...')={rd}   (期望 ATK→15 DEF→11)")


if __name__ == "__main__":
    main()
