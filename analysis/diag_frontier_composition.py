"""诊断跨段前沿为何虚胖（玩家 2026-06-07 裁定：先看清成分再定控宽）。

方法：投影塌缩测试。对某深段携带的整条 Pareto 前沿，逐维（及维组）做
「去掉该维后重算 Pareto 非支配集大小」——去掉后宽度大幅塌缩 = 该维在撑宽。
据此区分：真阈值维（atk/def/mdef/hp 跨怪攻/连击/坚固阈值，去掉会丢解）
vs 记账维（gold/单 key/单 item/kill 细维，可能只差 1 单位却互不支配 = 虚胖）。

用法：python diag_frontier_composition.py [N]   # N=floor-segment 深度，默认 6
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import phase1
from solver.frontier import value_vector, residual_fingerprint, _floor_residual


def _strict_dominated(vecs, drop):
    """返回投影到「去掉 drop 维」后的 Pareto 非支配点数（先去重再数非被严格支配点）。
    A 支配 B：A 各维 ≥ B 且 A≠B。去重后，B 保留 ⇔ 无 A≠B 满足 A≥B 全维。"""
    keys0 = set()
    for v in vecs:
        keys0.update(v.keys())
    keys = sorted(k for k in keys0 if k not in drop)
    proj = []
    seen = set()
    for v in vecs:
        tup = tuple(v.get(k, 0) for k in keys)
        if tup not in seen:
            seen.add(tup)
            proj.append(tup)
    # 非支配集：B 被支配 ⇔ ∃A≠B, A≥B 全分量
    kept = 0
    for i, b in enumerate(proj):
        dominated = False
        for j, a in enumerate(proj):
            if i == j:
                continue
            if all(a[d] >= b[d] for d in range(len(keys))) and a != b:
                dominated = True
                break
        if not dominated:
            kept += 1
    return kept, len(proj), keys


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    blocklog, frontier = phase1.run_phase1(num_segments=n)
    vecs = [value_vector(fp.state) for fp in frontier]
    W = len(vecs)
    print("\n" + "=" * 84)
    print(f"前沿成分诊断：seg<{n} 末携带前沿宽度 = {W}")
    print("=" * 84)

    # 1. 各维 distinct / min / max
    allkeys = set()
    for v in vecs:
        allkeys.update(v.keys())
    print("\n[1] 各价值维分布（distinct=不同取值数；distinct 大 = 嫌疑撑宽维）")
    print(f"  {'维':<16}{'distinct':>9}{'min':>7}{'max':>7}")
    for k in sorted(allkeys):
        vals = [v.get(k, 0) for v in vecs]
        print(f"  {k:<16}{len(set(vals)):>9}{min(vals):>7}{max(vals):>7}")

    # 2. 全维 Pareto（基线）应 = W（合并已保证），再逐维去掉看塌缩
    base_kept, base_uniq, base_keys = _strict_dominated(vecs, drop=set())
    print(f"\n[2] 投影塌缩测试（基线全维 Pareto={base_kept}，去重前={W}）")
    print(f"  {'去掉的维':<22}{'去重后':>8}{'Pareto宽':>9}{'塌缩%':>8}")
    singles = sorted(allkeys)
    groups = {
        "gold": {"gold"},
        "kill": {"kill"},
        "所有 key:*": {k for k in allkeys if k.startswith("key:")},
        "所有 item:*": {k for k in allkeys if k.startswith("item:")},
        "gold+key+item+kill(全记账维)": ({"gold", "kill"}
            | {k for k in allkeys if k.startswith("key:") or k.startswith("item:")}),
        "atk": {"atk"}, "def": {"def"}, "mdef": {"mdef"}, "hp": {"hp"},
        "atk+def+mdef(纯属性维)": {"atk", "def", "mdef"},
    }
    for label, drop in groups.items():
        kept, uniq, _ = _strict_dominated(vecs, drop)
        shrink = 100.0 * (base_kept - kept) / base_kept if base_kept else 0.0
        print(f"  {label:<22}{uniq:>8}{kept:>9}{shrink:>7.1f}%")

    # 3. 仅保留属性+HP（丢全部记账维）后的宽度——这是「真阈值」需要的最小前沿估计
    keep_attr = {"hp", "atk", "def", "mdef"}
    drop_all_but_attr = allkeys - keep_attr
    kept, uniq, _ = _strict_dominated(vecs, drop_all_but_attr)
    print(f"\n[3] 只保留 (hp,atk,def,mdef) 4 维 → Pareto 宽 = {kept}"
          f"（去重后 {uniq}）。若 ≪ {base_kept}，则记账维是虚胖主因。")

    # 4. 指纹成分分解：宽度=distinct 残留指纹时，是哪个成分在乘？
    states = [fp.state for fp in frontier]
    fps = [residual_fingerprint(s) for s in states]
    print(f"\n[4] 残留指纹成分分解（前沿 {W} 点 → distinct 指纹 {len(set(fps))}；"
          f"指纹≈宽度则每指纹 1 价值点，宽度由【地图残留态】撑）")
    comp_names = ["current_floor", "h.x", "h.y", "floors(全层残留)", "flags",
                  "visited", "auto_mode", "dead", "won", "enemy_overrides", "pending"]
    cols = list(zip(*fps))
    print(f"  {'指纹成分':<22}{'distinct':>9}  说明")
    for name, col in zip(comp_names, cols):
        d = len(set(col))
        note = "← 撑宽主成分" if d >= max(2, W // 2) else ("常量" if d == 1 else "")
        print(f"  {name:<22}{d:>9}  {note}")

    # 4b. floors 成分再按 floor_id 拆：每层 terrain / entities 各自 distinct
    print("\n  floors 内逐层拆（terrain vs entities 谁在变）：")
    per_floor = {}
    for s in states:
        for f in s.floors.values():
            fr = _floor_residual(f)   # (id, terrain, entities, doneAB, suppressed, is_hide, intercept)
            per_floor.setdefault(fr[0], {"terrain": set(), "entities": set(),
                                          "suppressed": set(), "doneAB": set()})
            per_floor[fr[0]]["terrain"].add(fr[1])
            per_floor[fr[0]]["entities"].add(fr[2])
            per_floor[fr[0]]["doneAB"].add(fr[3])
            per_floor[fr[0]]["suppressed"].add(fr[4])
    print(f"    {'层':<7}{'terrain':>9}{'entities':>10}{'doneAB':>9}{'suppressed':>12}")
    for fid in sorted(per_floor):
        d = per_floor[fid]
        print(f"    {fid:<7}{len(d['terrain']):>9}{len(d['entities']):>10}"
              f"{len(d['doneAB']):>9}{len(d['suppressed']):>12}")


if __name__ == "__main__":
    main()
