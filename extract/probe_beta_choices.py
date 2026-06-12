"""重放 β=0.5 路线（spliced = prefix82 + β段），记录每次 fire 的事件，找第一个【choices】或小偷TEXT。

假设：β 纯 RULD 路线触发了某 choices 事件（祭坛/老人/商人）却没带 CHOICE token，网站在 choices
处死等下一个选择 token，却来个移动 token → 从此每 token 错位一格，"后面全错"。sim 里 choices 会
设 _event_intercepting 拦截、吞掉随后的非 CHOICE token？还是照走？本探针实测 sim 行为 + 定位首个
choices/thief 触发点（unit idx / floor / xy / 属于 prefix 还是 β段）。
跑法：python extract/probe_beta_choices.py
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

import json
from lzstring import LZString
import sim.simulator as S
from extract.decode_route import parse_rle_route
from extract.export_mt10_boss_route import make_initial_state

OPENING_PREFIX = 83   # 82→83：MT2(1,9)小偷 hide 抑制修法后进 MT3 前缀多一步
FIRED = []
_orig = S._execute_event_list


def _patched(state, event_list, ex, ey, ctx=None):
    types = [i.get("type") if isinstance(i, dict) else "TEXT" for i in event_list]
    FIRED.append([state.current_floor, ex, ey, types, None])   # [floor,x,y,types,unit_idx]
    return _orig(state, event_list, ex, ey, ctx)


S._execute_event_list = _patched


def load_spliced():
    f = next(ROOT.glob("beta05_mt10_route.h5route"))
    outer = json.loads(LZString().decompressFromBase64(f.read_text(encoding="utf-8").strip()))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def expand(tok):
    D = {"U", "D", "L", "R"}
    if tok and tok[0] in D and (len(tok) == 1 or tok[1:].isdigit()):
        return [tok[0]] * (int(tok[1:]) if len(tok) > 1 else 1)
    return [tok]


def main():
    spliced = load_spliced()
    units = []
    for i, t in enumerate(spliced):
        for u in expand(t):
            units.append((i, t, u))

    s = make_initial_state()
    choices_events = []
    thief_events = []
    for ui, (ti, tok, u) in enumerate(units):
        n0 = len(FIRED)
        s = S.step(s, u)
        for rec in FIRED[n0:]:
            rec[4] = (ui, ti, tok)
            f, x, y, types, info = rec
            if "choices" in types:
                choices_events.append(rec)
            if "TEXT" in types and "move" in types:   # 小偷剧情型（TEXT+move）
                thief_events.append(rec)

    print("=" * 96)
    print(f"β=0.5 路线 fire 的【choices】事件（需 CHOICE token；β纯RULD无此token）：共 {len(choices_events)}")
    print("=" * 96)
    for f, x, y, types, info in choices_events:
        ui, ti, tok = info
        seg = "prefix" if ti < OPENING_PREFIX else "β段"
        print(f"  [{seg}] unit#{ui} tok#{ti}={tok!r}  @{f}({x},{y})  {types}")

    print(f"\nβ=0.5 路线 fire 的【小偷剧情(TEXT+move)】事件：共 {len(thief_events)}")
    for f, x, y, types, info in thief_events:
        ui, ti, tok = info
        seg = "prefix" if ti < OPENING_PREFIX else "β段"
        print(f"  [{seg}] unit#{ui} tok#{ti}={tok!r}  @{f}({x},{y})  {types}")

    # 第一个属于 β 段（ti>=82）的 choices/thief —— 这就是网站最早可能错位的点
    first_beta = None
    for rec in choices_events + thief_events:
        if rec[4][1] >= OPENING_PREFIX:
            if first_beta is None or rec[4][0] < first_beta[4][0]:
                first_beta = rec
    print("\n" + "=" * 96)
    if first_beta:
        f, x, y, types, info = first_beta
        ui, ti, tok = info
        print(f"⚠ β段最早的 choices/thief 触发：unit#{ui} tok#{ti}={tok!r} @{f}({x},{y}) {types}")
        print("   → 若网站在此 choices 处死等选择 token，而 β 路线下一个是移动 token，则此后逐 token 错位。")
    else:
        print("β段未 fire 任何 choices/小偷剧情事件 → 错位不在 choices/thief，另查。")


if __name__ == "__main__":
    main()
