"""逐 token 重放玩家整盘 route，instrument 每次事件触发，定位 MT2 小偷处 sim/网站可能的 token 错位。

红线：读源码不猜。已确认 sim 里小偷 (3,7) 的 move 指令无 loc → no-op（小偷不搬到 1,9），
只靠 hide 清 (3,7)。网站上小偷真的 move 到 (1,9) 再 hide。本探针查：
  · 玩家真实 token 在开局小偷段（token 60~90）每步触发了哪些事件、消费几 token；
  · (3,7) 和 (1,9) 两处事件在重放中是否 fire、是否 enable 翻转；
  · β 路线后续重访 MT2 (1,x) 列时，sim 在 (1,9) 是否 fire 任何事件（网站若 fire 而 sim 不 → 错位）。
跑法：python extract/probe_thief_events.py
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

FIRED = []          # (floor, x, y, [instr types]) 每次 _execute_event_list 调用
_orig_eel = S._execute_event_list


def _patched_eel(state, event_list, ex, ey, ctx=None):
    types = [i.get("type") if isinstance(i, dict) else "TEXT" for i in event_list]
    FIRED.append((state.current_floor, ex, ey, types))
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
    for i, t in enumerate(tokens):
        for u in expand(t):
            units.append((i, t, u))

    s = make_initial_state()
    print("=" * 96)
    print("玩家整盘 route：开局小偷段逐单步重放（每步显示 触发前位置 / 单步 / 触发后位置 / 本步fired事件）")
    print("=" * 96)
    for ui, (ti, tok, u) in enumerate(units):
        if ui > 95:
            break
        before = (s.current_floor, s.hero.x, s.hero.y)
        nfired = len(FIRED)
        s = S.step(s, u)
        after = (s.current_floor, s.hero.x, s.hero.y)
        new_events = FIRED[nfired:]
        if ui >= 60 or new_events:
            evs = "  ".join(f"@{f}({x},{y}){types}" for (f, x, y, types) in new_events)
            moved = "" if before != after else "  [原地]"
            print(f"  u#{ui:>3} tok#{ti:>3}={tok:>5} {u}: {before}→{after}{moved}  {evs}")

    # 走完开局后查 MT2 (3,7)/(1,9) 状态
    mt2 = s.floors.get("MT2") or S.load_floor(ROOT / "data" / "games51" / "floors" / "MT2.json")
    print("\n开局后（u#95 处）MT2 关键格状态：")
    for (x, y, label) in [(3, 7, "越狱小偷"), (1, 9, "提示小偷/relocate目标"), (2, 7, "thief开的门")]:
        ev = mt2.events.get(f"{x},{y}")
        enable = ev.get("enable") if isinstance(ev, dict) else ("活动列表" if isinstance(ev, list) else None)
        supp = f"{x},{y}" in mt2._suppressed_events
        print(f"  ({x},{y}) {label}: terrain={mt2.terrain[y][x]} entity={mt2.entities[y][x]} "
              f"event.enable={enable} suppressed={supp}")

    # 继续整盘重放，统计 MT2 上 (1,9)/(3,7) 之后是否还 fire
    nfired = len(FIRED)
    for ui in range(96, len(units)):
        ti, tok, u = units[ui]
        s = S.step(s, u)
    mt2_fires = [(f, x, y, ty) for (f, x, y, ty) in FIRED[nfired:] if f == "MT2"]
    print(f"\n开局之后（整盘剩余 {len(units)-96} 单步）MT2 上 fire 的事件（去重计数）：")
    from collections import Counter
    c = Counter((x, y, tuple(ty)) for (f, x, y, ty) in mt2_fires)
    for (x, y, ty), n in sorted(c.items()):
        print(f"  MT2({x},{y}) {list(ty)} ×{n}")
    if not mt2_fires:
        print("  （无）")


if __name__ == "__main__":
    main()
