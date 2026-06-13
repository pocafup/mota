"""算 route 完整楼层调度：每个 floor-segment 走哪层、各层最后一次出现在第几段。
据此判定"某段之后不再回切的层"——其地图残留指纹对未来全冗余，可证无损折叠。
用法：python diag_floor_schedule.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import load_tokens
from phase1 import trace_route, build_plan


def main():
    tokens = load_tokens()
    trace = trace_route(tokens)
    plan = build_plan(tokens, trace, max_floor_segments=None)

    # 每个 run block 的 (seg, floor)
    seg_floor = {}
    for b in plan:
        if b[0] == "run":
            _, floor, _goal, _i0, _i1, seg = b
            seg_floor[seg] = floor

    segs = sorted(seg_floor)
    print(f"route 共 {len(segs)} 个 floor-segment（token 总数 {len(tokens)}）")
    print("\n段→层 序列：")
    for s in segs:
        print(f"  seg{s:>2}  {seg_floor[s]}")

    # 各层最后一次出现的 seg
    last_seg = {}
    for s in segs:
        last_seg[seg_floor[s]] = s
    print("\n各层最后一次出现的 seg（此段之后该层死，残留可折叠）：")
    for floor in sorted(last_seg, key=lambda f: last_seg[f]):
        print(f"  {floor:<8} 最后见于 seg{last_seg[floor]}")

    # 逐段：到达该段时，已经"死"的层（last_seg < 当前 seg）
    print("\n逐段累计已死层（其残留指纹在该段及以后可无损折叠）：")
    for s in segs:
        dead = sorted(f for f, ls in last_seg.items() if ls < s)
        print(f"  seg{s:>2} 进入时已死层 = {dead}")
        if s >= 12:
            print("  …（仅列前 12 段，足够覆盖当前推进深度）")
            break


if __name__ == "__main__":
    main()
