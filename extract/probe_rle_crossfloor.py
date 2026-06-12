"""验证假设：β 路线删了 FMT 后，RLE 编码把【同向移动跨楼层切换】合并成多步 token（如 D2），
网站引擎处理"跨换层的多步移动"可能出错 → 卡在换层、后面全错。

玩家原始路线每个换层处都有 FMT 标记，天然把 RLE 连跑断开（换层前后是两个独立 token，
不会合并成多步）。删 FMT 后这个保护没了。本探针：
  1) 把 β spliced（单步串）逐步重放，记录每单步【执行后所在楼层】。
  2) 模拟 RLE 合并：把连续同向单步分组。
  3) 找出【组内发生楼层切换】的多步组 = 跨换层多步 token = 嫌疑。
  4) 对照玩家原始路线：是否任何多步 token 跨换层（应为 0，FMT 断开）。
跑法：python extract/probe_rle_crossfloor.py
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
from extract.export_mt10_boss_route import make_initial_state, load_tokens

MOVES = {"U", "D", "L", "R"}


def load_spliced():
    f = next(ROOT.glob("beta05_mt10_route.h5route"))
    outer = json.loads(LZString().decompressFromBase64(f.read_text(encoding="utf-8").strip()))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def expand(tok):
    if tok and tok[0] in MOVES and (len(tok) == 1 or tok[1:].isdigit()):
        return [tok[0]] * (int(tok[1:]) if len(tok) > 1 else 1)
    return [tok]


def analyze(name, tokens, break_on_nonmove=True):
    """重放单步串，标记每步前/后楼层；按 RLE 规则分组同向连跑；找跨换层的多步组。"""
    units = [u for t in tokens for u in expand(t)]
    s = make_initial_state()
    steps = []        # (idx, unit, floor_before, floor_after)
    for u in units:
        fb = s.current_floor
        s = S.step(s, u)
        steps.append((u, fb, s.current_floor))

    # RLE 分组：连续相同【移动】token 合并；非移动 token 自成一组（天然断开连跑）
    groups = []       # (token_char, count, floors_touched_set, transition_inside)
    i = 0
    n = len(steps)
    while i < n:
        u, fb, fa = steps[i]
        if u in MOVES:
            j = i
            floors = set()
            transitions = []
            while j < n and steps[j][0] == u:
                _, b, a = steps[j]
                floors.add(b); floors.add(a)
                if b != a:
                    transitions.append((b, a))
                j += 1
            groups.append((u, j - i, floors, transitions))
            i = j
        else:
            groups.append((u, 1, {fb, fa}, [(fb, fa)] if fb != fa else []))
            i += 1

    cross = [(ch, cnt, tr) for (ch, cnt, fl, tr) in groups if ch in MOVES and cnt > 1 and tr]
    print(f"\n【{name}】单步 {len(units)}，RLE 组 {len(groups)}，"
          f"跨换层的多步组（嫌疑）= {len(cross)}")
    for ch, cnt, tr in cross[:20]:
        print(f"    多步 {ch}{cnt} 内发生换层: {tr}")
    return len(cross)


def main():
    print("=" * 90)
    print("RLE 跨换层多步 token 诊断（验证删 FMT 是否导致换层处合并出多步、网站误处理）")
    print("=" * 90)

    spliced = load_spliced()
    n_beta = analyze("β=0.5 路线 (无 FMT)", spliced)

    player = load_tokens()
    n_player = analyze("玩家原始整盘路线 (有 FMT)", player)

    print("\n" + "=" * 90)
    print(f"结论：β 路线跨换层多步组 = {n_beta}；玩家原始 = {n_player}")
    if n_beta > 0 and n_player == 0:
        print("✅ 假设成立：玩家路线 FMT 把换层处连跑断开(0 跨换层多步)，β 删 FMT 后产生跨换层多步 token，")
        print("   网站引擎对'跨换层的多步移动'误处理 → 卡换层、后续全错。修法：换层处插断点(不重定位的FMT/或拆单步)。")
    elif n_beta == 0:
        print("✘ 假设不成立：β 路线无跨换层多步组，另查。")
    else:
        print("？ 玩家路线也有跨换层多步组，需重看 FMT 作用。")


if __name__ == "__main__":
    main()
