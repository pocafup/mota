"""【§S55 生存性 probe·非手推】ATK26(4颗gem) vs ATK27(5颗) 能不能清"红钥门守卫∪boss-leg"。

目的：§S55 字典序 beam 卡 ATK26、found=False。要分清是
  (A) 属性【够】但 beam 不肯推门 = 囤血/评分病 → 修护门进度；还是
  (B) 属性【不够】ATK26 清不完 door+boss-leg = 真缺第5颗 gem → 修护第5颗gem的approach。
判据：door+boss-leg 总损血(loss_one·compute_combat 实算) 对照 beam 够得到的 HP。

全部 compute_combat 实算·零手写公式。损血用 §S53 自检过的 loss_one(a,d,cell)。
注意：loss_one 只算【单怪战斗】损血·不含地形/夹击positional/沿途血瓶回血 →
  此和是【按怪战斗损血】口径(地形+positional 会更高·血瓶会抵扣)·当数量级判据·非精确终值。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.smart_phi_s53_beam import (
    build_phi_s53, cat_cells, BOSS_ID, GUARD_ID, BOSS_LEG_FLOORS,
    TOK_SHIELD, REAL_LEG_FLOORS, REDKEY_CELL,
)
from analysis.dir2_redkey_pathloss_beam import replay_to_token, fmt
from vzone import build_zone

# beam(§S55 _s53_lexico_k800.txt)各层【到达过】最优 HP 包络(独立 max·上界参考)
BEAM_HP = {"MT8": 543, "MT9": 579, "MT10": 519}


def main():
    print("=" * 84)
    print("§S55 生存性 probe：ATK26 vs ATK27 清 door+boss-leg(compute_combat 实算)")
    print("=" * 84)
    zone = build_zone()
    start = replay_to_token(TOK_SHIELD)
    print(f"起点 tok{TOK_SHIELD}: {fmt(start)}")
    phi_loss, diag = build_phi_s53(start, REAL_LEG_FLOORS, REDKEY_CELL, zone, 12000, BOSS_LEG_FLOORS)

    mon_cells = diag["mon_cells"]
    loss_one = diag["loss_one"]
    boss_leg = diag["boss_leg"]                       # MT9+MT10 全怪
    guard_cells = cat_cells(mon_cells, GUARD_ID)      # 红钥门守卫
    boss_cells = cat_cells(mon_cells, BOSS_ID)
    must_leg1 = diag["must_leg1"]                     # 段起点→红钥(approach)

    door_leg = guard_cells | boss_leg                 # 破门(守卫)起·到 boss 的整条尾路
    print(f"\n门后尾路 = 守卫({len(guard_cells)}) ∪ boss-leg({len(boss_leg)}·{BOSS_LEG_FLOORS}全怪) "
          f"= {len(door_leg)} 怪  (boss∈? {bool(boss_cells & door_leg)})")
    print(f"approach(段起点→红钥·leg1) = {len(must_leg1)} 怪")

    def leg_cost(cells, a, d):
        return sum(loss_one(a, d, c) for c in cells)

    # ── 主表：door+boss-leg 总损血 @ 各(atk,def)──
    print("\n" + "─" * 84)
    print("【door+boss-leg 总损血】(守卫∪boss-leg·loss_one 实算·按怪战斗口径)")
    print("─" * 84)
    print(f"{'(atk,def)':>10} | {'守卫':>6} {'boss-leg':>9} {'boss单':>7} | {'门后合计':>8} | 对照 beam HP")
    pts = [(26, 26), (27, 26), (26, 27), (27, 27), (26, 24), (27, 24)]
    for a, d in pts:
        g = leg_cost(guard_cells, a, d)
        bl = leg_cost(boss_leg, a, d)
        bj = leg_cost(boss_cells, a, d)
        tot = leg_cost(door_leg, a, d)
        flag = ""
        if d in (26, 27):
            ref = BEAM_HP["MT8"]
            flag = f"MT8={ref} → 余 {ref - tot:+d}" + ("  ⚠不够" if tot > ref else "  ✓够")
        print(f"{f'({a},{d})':>10} | {g:>6} {bl:>9} {bj:>7} | {tot:>8} | {flag}")

    # ── 第5颗 gem(ATK26→27)在整条门后尾路省多少血 ──
    print("\n" + "─" * 84)
    print("【第5颗 gem 价值】ATK26→27 在 door+boss-leg 整条尾路的省血(同 def 对比)")
    print("─" * 84)
    for d in (24, 26, 27):
        c26 = leg_cost(door_leg, 26, d)
        c27 = leg_cost(door_leg, 27, d)
        print(f"  DEF{d}: ATK26={c26}  ATK27={c27}  → 第5颗gem 省 {c26 - c27} 血")

    # ── 全路(approach + 门后)对照·总损血 ──
    print("\n" + "─" * 84)
    print("【全路总损血】approach(leg1) + door+boss-leg")
    print("─" * 84)
    for a, d in [(26, 26), (27, 27)]:
        ap = leg_cost(must_leg1, a, d)
        dl = leg_cost(door_leg, a, d)
        print(f"  ({a},{d}): approach={ap}  门后={dl}  全路={ap + dl}")

    # ── 交叉校验：boss-leg(27,27) vs 已知 V_boss(§S28·−634·含seam8守卫)──
    bl2727 = leg_cost(boss_leg, 27, 27)
    print(f"\n[交叉校验] 我的 boss-leg(27,27) 按怪和 = {bl2727}  "
          f"vs §S28 V_boss(27,27)=634(retrograde精确·seam含8守卫·口径不同仅作量级参照)")
    print("=" * 84)


if __name__ == "__main__":
    main()
