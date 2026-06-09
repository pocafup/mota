"""一区(MT1-MT10)跨层收缩图【建图前拓扑探查】——只读，dump 三样建 V_zone 收缩图必需的输入：
  ① 楼梯连接(change_floor)：每层上/下行楼梯格连到哪层哪格 → 跨层【免费边】怎么连。
  ② 节点构成(special-mon / battle-hook / zone / special-door 各几格)：决定第一版"当零代价过路"
     的松紧——这些格穿过可能有损血(领域/夹击/硬怪)，第一版若全当零代价是 admissible 松下界，
     需看数量是否少到可接受。
  ③ macro-edge / 块数：跨层图节点边规模(性能预算用)。
不改 quotient/beam，复用 seg_identify_zone1 的识别器产出。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state
from seg_identify_zone1 import analyze_floor, trace_macro_edges, ZONE1


def main():
    base = build_initial_state()
    tot_blocks = tot_edges = 0
    spc_total = 0
    print("=" * 90)
    print("一区跨层收缩图 — 建图前拓扑探查")
    print("=" * 90)
    for fid in ZONE1:
        r = analyze_floor(base, fid)
        fl = r["floor"]
        edges = trace_macro_edges(r)
        tot_blocks += r["nblocks"]
        tot_edges += len(edges)

        kind = r["kind"]
        spc = [c for c, (k, info) in kind.items() if k == "node" and info == "special-mon"]
        hook = [c for c, (k, info) in kind.items() if k == "node" and info == "battle-hook"]
        zone = [c for c, (k, info) in kind.items() if k == "node" and info == "zone"]
        sdr = [c for c, (k, info) in kind.items() if k == "node" and info == "special-door"]
        spc_total += len(spc)

        print(f"\n── {fid} ──  块={r['nblocks']}  macro-edge={len(edges)}  "
              f"自由格={r['nfree']}")
        print(f"   change_floor(楼梯连接):")
        for loc, tgt in fl.change_floor.items():
            print(f"      格 {loc:>6s}  →  {tgt}")
        if spc:
            print(f"   special-mon({len(spc)}格): {spc}")
        if hook:
            print(f"   battle-hook({len(hook)}格): {hook}")
        if zone:
            print(f"   zone领域伤({len(zone)}格): {zone}")
        if sdr:
            print(f"   special-door({len(sdr)}格): {sdr}")

    print("\n" + "=" * 90)
    print(f"【规模】一区合计 块={tot_blocks}  macro-edge(series后)={tot_edges}  "
          f"special-mon 节点={spc_total}")
    print(f"  → 跨层图节点 ~{tot_blocks}(块) + 各类node格；边 ~{tot_edges}(损血edge) + 楼梯免费边")
    print(f"  → 第一版若把 {spc_total} 个 special-mon 全当零代价过路：admissible 松下界，"
          f"看这数大不大决定要不要算它们损血")
    print("=" * 90)


if __name__ == "__main__":
    main()
