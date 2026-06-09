"""一区 macro-edge 收缩【收益评估】——量化"收缩到底压掉多少 decision/状态"，供玩家判断
"收缩本身值不值得做整套工程，还是真正红利在 Q3 的 V_zone"。

只统计+论证，不收缩、不动 quotient/beam/识别器。口径分三层(玩家最关心"是不是就 34% 量级")：
  ① 块图节点(位置 decision 点)：FREE 块 → 消度2过道块后的超节点。
  ② pay 算子(逐怪/逐门 decision)：现 quotient 每个 pay-cell 是一个 kill/door 算子(散落搜索树)；
     收缩后整条 gauntlet 并成一条 macro-edge 一跳(f 预处理算好)→ 中间低HP态不再进 beam。
  ③ 综合决策单元 = 节点 + 边一跳，收缩前后对比。
并给 macro-edge 穿越格分布(证明收益是否集中在少数长边) + 簇端点分布(哪些 pay 能/不能 series 收缩)。
"""
import sys
from collections import Counter
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
    L = []

    def w(s=""):
        L.append(s)

    tot_nodes = tot_deg2 = tot_clusters = tot_pay = 0
    ep_dist = Counter()                 # 簇端点数 → 簇数
    series_edges = series_pay = series_clusters_used = 0
    cross_dist = Counter()              # 每条 series macro-edge 穿过的 pay 格数 → 边数

    for fid in ZONE1:
        res = analyze_floor(base, fid)
        tot_nodes += res["nblocks"]
        tot_deg2 += res["deg_dist"].get(2, 0)
        tot_clusters += res["nclusters"]
        for (cl, eps, pk) in res["cluster_info"]:
            ep_dist[len(eps)] += 1
            tot_pay += sum(pk.values())
        for (va, vb, chain, nk, nd) in trace_macro_edges(res):
            series_edges += 1
            series_pay += nk + nd
            series_clusters_used += len(chain)
            cross_dist[nk + nd] += 1

    nodes_after = tot_nodes - tot_deg2
    merged_away = series_clusters_used - series_edges     # 被串掉的簇接缝(=度2过道)
    edges_after = tot_clusters - merged_away              # 收缩后总边数(series一跳 + 非series簇各一跳)
    mid_removed = tot_pay - edges_after                   # 不再独立进 beam 的 pay 中间态
    units_before = tot_nodes + tot_pay                    # 综合决策单元(位置 + 逐pay算子)
    units_after = nodes_after + edges_after

    def pct(a, b):
        return f"-{round(100 * (a - b) / a)}%" if a else "—"

    w("=" * 96)
    w("一区(MT1-MT10) macro-edge 收缩【收益评估】—— 收缩到底压掉多少 decision/状态？")
    w("=" * 96)
    w("【口径①】块图节点(位置 decision 点)")
    w(f"   FREE 块 {tot_nodes}  →  消度2过道块 {tot_deg2}  →  收缩后超节点 {nodes_after}    "
      f"({pct(tot_nodes, nodes_after)})")
    w("")
    w("【口径②】pay 算子(现 quotient 逐怪/逐门各一个 kill/door 算子，散落搜索树→展开即暴露中间态)")
    w(f"   pay-cell 算子 {tot_pay}(怪+门)  →  收缩后边一跳 {edges_after}    ({pct(tot_pay, edges_after)})")
    w(f"   ⇒ 被吃进 macro-edge 内、不再独立进 beam 的【gauntlet 中间态】= {mid_removed} 个 "
      f"({pct(tot_pay, edges_after)} 的 pay 决策从搜索树消失)")
    w("")
    w("【口径③】综合决策单元(节点 + 边一跳)")
    w(f"   收缩前 {tot_nodes}节点+{tot_pay}pay算子 = {units_before}  →  "
      f"收缩后 {nodes_after}节点+{edges_after}边 = {units_after}    ({pct(units_before, units_after)})")
    w("")
    w("-" * 96)
    w("【pay 簇端点分布】决定哪些 pay 能 series 收缩：")
    w(f"   1端点(spur死胡同怪/门,含 boss 幽灵格): {ep_dist.get(1,0)} 簇  ← 各自一跳，搜索本就少展开")
    w(f"   2端点(过道型,可 series 串接): {ep_dist.get(2,0)} 簇  ← 收缩主力")
    w(f"   ≥3端点(枢纽,连多块): {sum(v for k,v in ep_dist.items() if k>=3)} 簇  ← 不能并，留作多叉边")
    w("")
    w("【macro-edge 穿越格分布】(只统计 2端点 series 链；证明收益是否集中在少数长边)")
    longn = sum(v for k, v in cross_dist.items() if k >= 2)
    for k in sorted(cross_dist):
        bar = "█" * cross_dist[k]
        tag = "  ←穿1格:无收缩收益(单算子边)" if k == 1 else ""
        w(f"   穿 {k} 格: {cross_dist[k]:>2} 条 {bar}{tag}")
    w(f"   ⇒ 真有收缩收益(穿≥2格)的边 = {longn} 条 / 共 {series_edges} 条 series 边 "
      f"({round(100*longn/series_edges) if series_edges else 0}%)；这 {longn} 条吃掉 "
      f"{series_pay - cross_dist.get(1,0)} 个 pay(占全部 pay 的 "
      f"{round(100*(series_pay-cross_dist.get(1,0))/tot_pay)}%)")
    w("")
    w("-" * 96)
    w("【判断给玩家】")
    w(f"   · 纯图拓扑压缩(节点)= {pct(tot_nodes, nodes_after)}，温和、线性，单看这个不足以撑整套工程。")
    w(f"   · 但 pay 算子维压缩 {pct(tot_pay, edges_after)}：{mid_removed} 个 gauntlet 中间低HP态不再进 beam——")
    w(f"     这是比 34% 更实质的收益(beam 不再被'穿到一半HP见底'的中间态污染、挤掉好状态)，且集中在")
    w(f"     {longn} 条长边(最长穿 {max(cross_dist) if cross_dist else 0} 格)。属性/钥匙维不变，故仍非数量级。")
    w(f"   · 数量级红利在 Q3 的 V_zone(块→boss 最短路启发)：它给 beam admissible 下界、按区剪枝。")
    w(f"     收缩是 V_zone 的【基建】——在 {edges_after} 条边的紧凑图上算最短路，比在 {tot_pay} 个散 pay")
    w(f"     算子的图上更快更干净。结论：收缩值得做，但定位是'前置/基建+消谷底'，终极加速器是 V_zone，两者协同。")
    w("=" * 96)

    report = "\n".join(L)
    out = Path(__file__).parent / "seg_contract_benefit.txt"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[落盘] {out}")


if __name__ == "__main__":
    main()
