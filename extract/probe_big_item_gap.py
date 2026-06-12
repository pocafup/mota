"""只读探针（结合两套·第一步）：量化一区每件【攻防物】的「Δ减伤」，看【大件(剑盾)/小宝石】
之间有没有清晰的缝 → 把 pull_大件 的门控阈值 τ 放在缝上（数据涌现、塔无关，不硬编码"剑盾"）。

玩家 2026-06-11 拍板【结合】：排序键 = region 区势能基分(兑现侧) + β_big·pull_大件(只对高减伤
大件的引导)。"大件"必须由减伤量自然划出。本探针对每件攻防物算两种 Δ减伤、按 ΔRP 降序排，找缝：
  · ΔRP（区势能口径，与结合用的兑现侧同源）= Σ_{当前区到boss·非当前层·存活怪}[toll(当前) −
    toll(当前+该物增益)]，复用 beam._future_potential（λ=1 取原始和，引擎真损血、不手写公式）。
  · Δboss_toll（vzone.pull 现用口径）= boss_toll(当前) − boss_toll(当前+增益)，单 boss 怪。
  · dist = 起点(MT3 噩梦后入口)→该物格的最短累计损血（vzone._toll_dist_from），看引导折扣 1/(1+dist)。

纯只读：不接搜索、不改打分、不落盘产物。只打印分布 + 自动找最大乘性缝 → 建议 τ。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import _copy_state
from solver.beam import build_future_roster, FutureCfg, _future_potential, _region_bounds
from probe_crossfloor import build_start
from vzone import build_zone, boss_toll, _toll_dist_from, _attr_item_delta


def region_pot(state, roster):
    """区势能原始和（λ=1）：Σ_{当前区到boss·非当前层·存活怪} toll(当前属性, 怪)。越大=越多残损待消。"""
    return _future_potential(state, FutureCfg(roster, 1.0))


def bumped(start, da, dd):
    s = _copy_state(start)
    s.hero.atk += da
    s.hero.def_ += dd
    return s


def scan_attr_gems(zone):
    """一区所有【攻防物】：[(fid,x,y,iid,name,Δatk,Δdef)]，位置/增益从各层初始地图真算。"""
    out = []
    for fid, r in zone["floors"].items():
        fl = r["floor"]
        for y, row in enumerate(fl.entities):
            for x, e in enumerate(row):
                if not e:
                    continue
                iid = fl._tile_to_item.get(e)
                if not iid:
                    continue
                da, dd = _attr_item_delta(fl._items_db, iid, fl.ratio)
                if da or dd:
                    name = ""
                    d = fl._items_db.get(iid)
                    if isinstance(d, dict):
                        name = d.get("name", "") or ""
                    out.append((fid, x, y, iid, name, da, dd))
    return out


def main():
    start, nopen = build_start()
    roster = build_future_roster(start)
    zone = build_zone()
    h = start.hero

    print("=" * 104)
    print("只读探针：一区各【攻防物】Δ减伤分布 → 找【大件/小宝石】缝、定 pull_大件 门控 τ")
    print("=" * 104)
    print(f"起点(噩梦后首个自由态)：{start.current_floor}({h.x},{h.y}) "
          f"HP={h.hp} ATK={h.atk} DEF={h.def_} MDEF={h.mdef}")
    cur_idx = roster["idx_of"].get(start.current_floor)
    lo, hi = _region_bounds(roster, cur_idx)
    fids = roster["floor_ids"]
    print(f"当前区跨度（{start.current_floor}→boss）：[{fids[lo]} .. {fids[hi]}]  "
          f"区势能原始和(起点 atk={h.atk}/def={h.def_})Σ_区={region_pot(start, roster):,.0f}")
    print("-" * 104)

    gems = scan_attr_gems(zone)
    base_rp = region_pot(start, roster)
    boss_cur = boss_toll(zone, h.atk, h.def_, h.mdef)
    src = (start.current_floor, h.x, h.y)
    dist_map = _toll_dist_from(zone, src, h.atk, h.def_, h.mdef)

    rows = []
    for (fid, x, y, iid, name, da, dd) in gems:
        d_rp = base_rp - region_pot(bumped(start, da, dd), roster)
        d_boss = boss_cur - boss_toll(zone, h.atk + da, h.def_ + dd, h.mdef)
        dist = dist_map.get((fid, x, y))
        dist_s = "∞(够不到)" if dist is None else f"{dist:,}"
        pull_rp = (d_rp / (1.0 + dist)) if dist is not None else 0.0
        rows.append((d_rp, d_boss, dist, pull_rp, fid, x, y, iid, name, da, dd))

    rows.sort(key=lambda r: -r[0])   # 按 ΔRP 降序

    print(f"共 {len(rows)} 件攻防物（按 ΔRP=区势能减伤 降序；ΔRP 大=对整区所有怪减伤多=大件）：")
    print(f"{'#':>2} {'物@格':>14} {'物品id':>10} {'名':>8} {'Δatk':>4} {'Δdef':>4} "
          f"{'ΔRP(区减伤)':>12} {'Δboss_toll':>10} {'起点距':>9} {'pull=ΔRP/(1+d)':>14}")
    for i, (d_rp, d_boss, dist, pull_rp, fid, x, y, iid, name, da, dd) in enumerate(rows):
        dist_s = "∞" if dist is None else f"{dist:,}"
        print(f"{i:>2} {fid+f'({x},{y})':>14} {iid:>10} {name[:8]:>8} {da:>4} {dd:>4} "
              f"{d_rp:>12,.0f} {d_boss:>10,.0f} {dist_s:>9} {pull_rp:>14,.1f}")

    # ── 自动找【最大乘性缝】：相邻 ΔRP 比值最大处 = 大件/小宝石的自然分界 ──
    print("-" * 104)
    vals = [r[0] for r in rows if r[0] > 0]
    if len(vals) >= 2:
        best_gap = 0.0
        best_i = None
        for i in range(len(vals) - 1):
            hi_v, lo_v = vals[i], vals[i + 1]
            if lo_v <= 0:
                continue
            ratio = hi_v / lo_v
            if ratio > best_gap:
                best_gap = ratio
                best_i = i
        if best_i is not None:
            tau_hi = vals[best_i]          # 缝上方最小的大件 ΔRP
            tau_lo = vals[best_i + 1]      # 缝下方最大的小宝石 ΔRP
            tau = (tau_hi * tau_lo) ** 0.5  # 几何中点（缝正中）
            n_big = best_i + 1
            print(f"最大乘性缝：第 {best_i} 与第 {best_i+1} 件之间，ΔRP {tau_hi:,.0f} ↓ {tau_lo:,.0f} "
                  f"（{best_gap:.1f}× 落差）")
            print(f"→ 缝上 {n_big} 件 = 大件（ΔRP ≥ {tau_hi:,.0f}）；缝下 {len(vals)-n_big} 件 = 小宝石")
            print(f"→ 建议门控 τ = {tau:,.0f}（缝几何中点；pull_大件 只算 ΔRP ≥ τ 的物）")
            print(f"   大件清单：")
            for r in rows[:n_big]:
                d_rp, d_boss, dist, pull_rp, fid, x, y, iid, name, da, dd = r
                dist_s = "∞" if dist is None else f"{dist:,}"
                print(f"     {fid}({x},{y}) {iid} {name} +atk{da}/+def{dd}  "
                      f"ΔRP={d_rp:,.0f} 起点距={dist_s}")
    else:
        print("攻防物不足，无法找缝。")
    print("=" * 104)


if __name__ == "__main__":
    main()
