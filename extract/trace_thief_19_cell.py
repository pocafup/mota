"""逐单步追踪玩家真实 route 在 MT2 小偷段，打印英雄位置 + (1,9) 小偷格 entities[9][1]。

目的：核对"撞 (1,9) 小偷停一步"行为到底在不在玩家 token 里。
红线：数 token、不猜。(3,7) 的"撞上停一步"上轮探针已见(u#70 原地)；本 trace 专看 (1,9)：
玩家 route 经过 (1,9) 那步，英雄是"停一步(原地)"还是"直接进格"？同时看小偷在不在 (1,9)
(entities[9][1] 非 0 = 在)，以判定 (1,9) 是否被前面某步清掉。

跑法：python extract/trace_thief_19_cell.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sim.simulator as S
from extract.export_mt10_boss_route import make_initial_state, load_tokens

FIRED = []
_orig_eel = S._execute_event_list


def _patched_eel(state, event_list, ex, ey, ctx=None):
    FIRED.append((state.current_floor, ex, ey))
    return _orig_eel(state, event_list, ex, ey, ctx)


S._execute_event_list = _patched_eel


def expand(tok):
    D = {"U", "D", "L", "R"}
    if tok and tok[0] in D and (len(tok) == 1 or tok[1:].isdigit()):
        return [tok[0]] * (int(tok[1:]) if len(tok) > 1 else 1)
    return [tok]


def thief19(s):
    mt2 = s.floors.get("MT2")
    return mt2.entities[9][1] if mt2 else None


def main():
    tokens = load_tokens()
    units = [u for t in tokens for u in expand(t)]

    s = make_initial_state()
    print("u#   单步  英雄(前→后)            (1,9)小偷格  本步fire事件")
    print("-" * 78)
    for ui in range(min(len(units), 84)):
        u = units[ui]
        before = (s.current_floor, s.hero.x, s.hero.y)
        nf = len(FIRED)
        s = S.step(s, u)
        after = (s.current_floor, s.hero.x, s.hero.y)
        t19 = thief19(s)
        ev = "  ".join(f"@{f}({x},{y})" for (f, x, y) in FIRED[nf:])
        if ui >= 60:
            stay = " 原地" if before == after else "     "
            mark = "  <<<在(1,9)" if t19 else ""
            print(f"{ui:>3}  {u:>4}  {str(before):>20}→{str(after):<14}{stay}  "
                  f"e[9][1]={t19}{mark}  {ev}")


if __name__ == "__main__":
    main()
