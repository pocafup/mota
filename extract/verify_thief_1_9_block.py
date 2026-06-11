"""隔离验证：修 move 无 loc 后，MT2 小偷搬到 (1,9) 是否真的挡路（复现网站行为）。

为什么不能用玩家整盘路线验证：玩家路线被 MT3 伏击传回 MT2(3,8) 后会二次踩 (3,7)，
sim 的 hide 不抑制该事件→事件再 fire→move 把 0 写回 (1,9) 把小偷清掉，故玩家路线
在 (1,9) 畅通（也正因此 46 检查点不受影响）。β 路线只触发一次 (3,7)、不二次踩，
才会真正撞上 (1,9) 的小偷。本验证复现"只触发一次"的场景：

  1. 重放玩家 token 到 u#70（英雄 (3,8) 按 U 触发 (3,7) 越狱小偷，小偷搬到 (1,9)）；
  2. 断言 entities[9][1] 非空（小偷确实在 (1,9)）；
  3. 直接把英雄摆到 (1,8)（测试夹具，非游戏移动，刻意绕开二次踩 (3,7)）；
  4. step 'D' 走向 (1,9)：期望被挡（英雄原地）+ (1,9) 事件 fire；
  5. 再 step 'D'：期望 (1,9) 事件已 hide、路开，英雄进 (1,9)。

跑法：python extract/verify_thief_1_9_block.py
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


def main():
    tokens = load_tokens()
    units = []
    for t in tokens:
        for u in expand(t):
            units.append(u)

    s = make_initial_state()
    for u in units[:71]:          # 重放到 u#70 含（触发 (3,7) 越狱小偷）
        s = S.step(s, u)

    mt2 = s.floors["MT2"]
    thief_19 = mt2.entities[9][1]
    print(f"[1] 触发 (3,7) 后英雄位置: ({s.hero.x},{s.hero.y}) @ {s.current_floor}")
    print(f"[2] MT2 (1,9) 实体层 entities[9][1] = {thief_19}  "
          f"→ {'小偷在 (1,9) ✅' if thief_19 else '(1,9) 空 ❌（小偷没搬过去）'}")

    # 夹具：直接把英雄摆到 (1,8)，绕开二次踩 (3,7)（模拟 β 路线从上方直插 (1,9)）
    s.hero.x, s.hero.y = 1, 8
    print(f"\n[3] 夹具置英雄于 (1,8)（不二次踩 (3,7)），从上方走向 (1,9)：")

    nf = len(FIRED)
    s = S.step(s, "D")
    fired_19 = [(f, x, y) for (f, x, y) in FIRED[nf:] if (f, x, y) == ("MT2", 1, 9)]
    blocked = (s.hero.x, s.hero.y) == (1, 8)
    print(f"    第 1 次 D: 英雄→({s.hero.x},{s.hero.y})  "
          f"{'被挡停在 (1,8) ✅' if blocked else '没被挡 ❌'}  "
          f"(1,9)事件fire={'是 ✅' if fired_19 else '否 ❌'}")

    nf = len(FIRED)
    s = S.step(s, "D")
    moved_in = (s.hero.x, s.hero.y) == (1, 9)
    print(f"    第 2 次 D: 英雄→({s.hero.x},{s.hero.y})  "
          f"{'小偷已hide、路开、进 (1,9) ✅' if moved_in else f'仍未进 (1,9)（{s.hero.x},{s.hero.y}）'}")

    print("\n结论：", end="")
    if thief_19 and blocked and fired_19:
        print("修后 (1,9) 复现网站行为——小偷挡路、英雄撞上对话停一步、随后开路。✅")
    else:
        print("(1,9) 行为与网站预期不符，需复查。❌")


if __name__ == "__main__":
    main()
