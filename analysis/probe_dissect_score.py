"""【只读·决策点解剖·第二步：打分明细】在四个决策点的 block 态，用【真实打分函数】给每个
   候选边界算子算明细：region 区势能基分 / β_big·pull_大件 / HP代价 / 最终 V，并做 β×λ 敏感性网格。
   纯诊断、不改产品码、不调参（β/λ 扫描只是【对现有打分函数重新取值】，不动产品默认）。

口径（与 search_quotient 一致）：
  · 决策态 s0 = 重放 region 段前 anchor−1 步后再 _absorb（落到该 op 触发前的同一自由块）。
  · 候选 = _boundary_ops(s0)（杀怪/开门/楼梯/自开/触发），逐个 _expand_op+_absorb 成子态。
  · 打分 = solver/beam.py 真函数：Σcost(region_reference 建 R/BIG)、区势能(_future_potential λ=1 原始和)、
    pull(big_item_pull.pull_big 原始、不含 β)。V(β,λ)=HP − Σcost − λ·区势能 + β·pull。

⚠ 两条诚实保真说明（必须随报告写出，不静默）：
  (1) 真实 beam 的 R/BIG 来自【整个 wave】(所有父态的子态并集)，本探针只用【单父 s0 的子态】局部批。
      但兄弟间 Σcost 差异由属性(atk/def)驱动、对杀怪中性 → 局部 R 下的【相对排序】稳健；区势能/pull
      是【与批无关的绝对值】→ 精确。故 V 的【兄弟相对高低】可信，绝对数值仅供量级参考。
  (2) 真实选择 = 整 wave 按 V 取 top-K(=200) beam + 末态 best-MT10 的 Pareto 路径回溯，【不是】局部 argmax。
      故"病 op 在 route 上"≠"病 op 是局部 V 第一"；本探针给出局部排名，区分这两种成因。

跑法：python -u extract/probe_dissect_score.py
"""
import sys
from pathlib import Path
from collections import namedtuple

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, DOOR_KEY_MAP
from solver.quotient import _free_cells, _boundary_ops, _expand_op, _absorb
from solver.beam import (build_future_roster, FutureCfg, _future_potential,
                         region_reference, _combat_damage)
from vzone import build_zone
from big_item_pull import detect_big_items, pull_big, build_pickup_bonus, pickup_bonus
from probe_crossfloor import build_start, OPENING_PREFIX
from export_bscan_routes import load_rows, pick_best_mt10

HERE = Path(__file__).parent
SRC = HERE / "crossbeam_floorbest_K200_bb25_PUREPULL_lam0.2_stairs.jsonl"   # 纯 pull(pre-G)病态路线→取四点决策态

BETA_BIG = 25.0
BETA_SMALL = 3.0                  # 满额兑现：小宝石拿取奖励系数（与产品扫描同口径）
LAM = 0.2
SWEEP_BETA = [0, 4, 25, 60]
SWEEP_LAM = [0.0, 0.1, 0.2]

# 满额兑现拿取奖励【单位表】(β=1，raw ΔRP₀)：score_children 用 pickup_bonus 算每个子态【已拿走】的 g_big/g_small。
# 在 main() 里按 ranked/big_cells 建好（β=1 → 表值=ΔRP₀；V 里再乘 β/β_small）。
_TABLE_BIG_UNIT = {}
_TABLE_SMALL_UNIT = {}

# 四决策点：(tok, anchor_region步, 病target_cell, 标签)
# anchor = 病 op 触发的 region 步号（1基）；replay region_actions[:anchor−1] → 英雄停在该块边界、邻接病格。
POINTS = [
    (550, 468, (2, 6), "tok550 打骷髅士兵"),
    (710, 628, (4, 1), "tok710 开门不进"),
    (737, 655, (10, 2), "tok737 打史莱姆·不走无损到盾"),
    (1011, 929, (11, 2), "tok1011 打红史莱姆·不深入拿钥匙"),
]

_Pt = namedtuple("_Pt", ["state"])


def load_region_actions():
    start = build_start()[0]
    zone = build_zone()
    rows = load_rows(SRC)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    best_row, _s, _vz, _D = pick_best_mt10(zone, start, mt10)
    return start, list(best_row["actions"])


def replay(start, actions):
    s = _copy_state(start)
    for a in actions:
        s = step(s, a)
    return s


def op_desc(state, op):
    """算子简述：kind + 目标格上是什么。"""
    kind, ox, oy, fx, fy, mv = op
    fl = state.floor
    if kind == "kill":
        mid = fl._tile_to_enemy.get(fl.entities[oy][ox])
        return f"kill 怪:{mid}@({ox},{oy})"
    if kind == "door":
        t = fl.terrain[oy][ox]
        return f"door 门:{DOOR_KEY_MAP.get(t)}@({ox},{oy})"
    if kind == "stair":
        dest = fl.change_floor.get(f"{ox},{oy}")
        return f"stair 楼梯@({ox},{oy})→{dest}"
    if kind == "autoopen":
        return f"autoopen 自开@({ox},{oy})"
    if kind == "trigger":
        return f"trigger 事件@({ox},{oy})"
    return f"{kind}@({ox},{oy})"


def op_short(op):
    kind, ox, oy, fx, fy, mv = op
    return f"{kind}({ox},{oy})"


def sigma_cost(state, roster_R, big):
    """Σ_{m∈R} cost(state,m)：可杀(损血<HP)→损血；打不动/会被打死→BIG。与 equiv_hp_over_roster 同口径。"""
    hp = state.hero.hp
    total = 0
    for mid in roster_R.values():
        d = _combat_damage(state, mid)
        total += d if (d is not None and d < hp) else big
    return total


def expand_children(s0, cross_floor=True):
    """枚举 s0 边界算子，逐个展开+吸收成子态。返回 [(op, child)]（剔除死亡/无效）。"""
    free = _free_cells(s0)
    ops = _boundary_ops(s0, free, cross_floor=cross_floor)
    out = []
    for op in ops:
        res = _expand_op(s0, free, op, step)
        if res is None:
            continue
        child, _moves = res
        child, _ = _absorb(child, step)
        if child.dead:
            continue
        out.append((op, child))
    return out


def score_children(s0, children, roster_future, zone, big_cells):
    """给每个子态算【与批无关的绝对量】+ 局部批 Σcost。返回 list[dict]。"""
    pts = [_Pt(state=c) for (_op, c) in children]
    roster_R, big = region_reference(pts)
    rows = []
    for (op, child) in children:
        hp = child.hero.hp
        sk = sigma_cost(child, roster_R, big)
        rp = float(_future_potential(child, FutureCfg(roster_future, 1.0)))  # λ=1 原始和
        pl = pull_big(zone, roster_future, child, big_cells)                 # 原始 pull，不含 β
        gb = pickup_bonus(child, _TABLE_BIG_UNIT)        # 满额兑现 raw G_big = Σ_{大件已拿走} ΔRP₀（不含 β）
        gs = pickup_bonus(child, _TABLE_SMALL_UNIT)      # raw G_small = Σ_{小宝石已拿走} ΔRP₀（不含 β_small）
        rows.append(dict(op=op, child=child, hp=hp, dcost=s0.hero.hp - hp,
                         sk=sk, rp=rp, pull=pl, g_big=gb, g_small=gs,
                         post=f"{child.current_floor}({child.hero.x},{child.hero.y})"))
    return rows, roster_R, big


def V(row, beta, lam):
    """旧式·纯 pull（pre-G）：HP − Σcost − λ·区势能 + β·pull_大件。四点解剖原口径，作【满额兑现前】对照。"""
    return row["hp"] - row["sk"] - lam * row["rp"] + beta * row["pull"]


def V_full(row, beta, lam, beta_small=BETA_SMALL):
    """满额兑现：旧 V + 拿取奖励 G = β·(pull + g_big) + β_small·g_small（大件在场折扣引导 + 拿走满额兑现）。
    拿到大件/小宝石(entities==0)→ +β·ΔRP₀，结构性压过守着折扣引导 → 治就近病/hover 平台。"""
    return V(row, beta, lam) + beta * row["g_big"] + beta_small * row["g_small"]


def dissect(start, region_actions, zone, roster_future, big_cells, tok, anchor, tgt, label):
    print("\n" + "#" * 108)
    print(f"# {label}  (tok={tok} → region 步 {anchor})")
    print("#" * 108)

    s0 = replay(start, region_actions[:anchor - 1])
    s0, _ = _absorb(s0, step)
    h = s0.hero
    free = _free_cells(s0)
    print(f"决策态 s0：{s0.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"持钥={{ {', '.join(f'{k}:{v}' for k, v in h.keys.items() if v)} }}  自由块{len(free)}格")

    children = expand_children(s0, cross_floor=True)
    if not children:
        print("  ⚠ s0 无可展开算子（死节点？）")
        return
    rows, roster_R, big = score_children(s0, children, roster_future, zone, big_cells)

    # 病 op = 目标格==tgt
    sick = None
    for r in rows:
        _k, ox, oy, _fx, _fy, _mv = r["op"]
        if (ox, oy) == tgt:
            sick = r
            break
    print(f"  R(局部批锚怪集)={len(roster_R)}只  BIG={big}  候选算子 {len(rows)} 个"
          + (f"  ★病 op={op_short(sick['op'])}" if sick else "  ⚠未在候选里找到病格"))

    # 候选明细表（按 V(β=25,λ=0.2) 降序）
    rows.sort(key=lambda r: -V(r, BETA_BIG, LAM))
    print("\n  候选明细（按 V(β=25,λ=.2) 降序）：")
    print(f"  {'':>2} {'算子':>22} {'落点':>12} {'子HP':>6} {'HP代价':>7} {'Σcost':>9} "
          f"{'区势能raw':>10} {'λ·区(.2)':>9} {'pull_raw':>9} {'β·pull(25)':>10} {'V(25,.2)':>11}")
    for rk, r in enumerate(rows, 1):
        mark = "★" if r is sick else " "
        print(f"  {mark:>2} {op_desc(s0, r['op']):>22} {r['post']:>12} {r['hp']:>6} "
              f"{r['dcost']:>+7} {r['sk']:>9.0f} {r['rp']:>10,.0f} {LAM * r['rp']:>9,.0f} "
              f"{r['pull']:>9.3f} {BETA_BIG * r['pull']:>10.2f} {V(r, BETA_BIG, LAM):>11,.1f}")

    if sick is not None:
        rank = rows.index(sick) + 1
        best = rows[0]
        print(f"\n  → 病 op 在 (β=25,λ=.2) 局部 V 排名 = {rank}/{len(rows)}"
              + ("（=局部第一：打分函数确实最偏好它）" if rank == 1
                 else f"（非第一；局部最优是 {op_short(best['op'])} V={V(best, BETA_BIG, LAM):,.1f} > "
                      f"病 op V={V(sick, BETA_BIG, LAM):,.1f}→病 op 上路靠 beam 保留+全局 Pareto，非局部 argmax）"))

    # β×λ 敏感性网格：每格 = 局部 argmax 算子（★=病 op 胜出）
    print("\n  β×λ 敏感性网格（格=该 (β,λ) 下局部 V 最高的算子；★=病 op 胜出）：")
    head = "  " + f"{'β|λ':>8}" + "".join(f"{lam:>22.1f}" for lam in SWEEP_LAM)
    print(head)
    sick_wins = 0
    total_cells = 0
    for beta in SWEEP_BETA:
        cells = []
        for lam in SWEEP_LAM:
            win = max(rows, key=lambda r: V(r, beta, lam))
            total_cells += 1
            tag = ""
            if sick is not None and win is sick:
                tag = "★"
                sick_wins += 1
            cells.append(f"{tag}{op_short(win['op'])}")
        print("  " + f"{beta:>8.0f}" + "".join(f"{c:>22}" for c in cells))
    if sick is not None:
        print(f"  → 病 op 在 {sick_wins}/{total_cells} 个 (β,λ) 组合里是局部 argmax")

    # 病 op vs 最佳非病兄弟：跨网格的 V 差（>0=病 op 领先；<0=该组合下别的算子更优=病在此组合被治）
    if sick is not None and len(rows) > 1:
        print("\n  病 op V − 最佳非病兄弟 V（>0=病 op 局部领先；<0=此组合别的算子更优=该组合治好）：")
        print("  " + f"{'β|λ':>8}" + "".join(f"{lam:>14.1f}" for lam in SWEEP_LAM))
        others = [r for r in rows if r is not sick]
        for beta in SWEEP_BETA:
            diffs = []
            for lam in SWEEP_LAM:
                vs = V(sick, beta, lam)
                vo = max(V(r, beta, lam) for r in others)
                diffs.append(vs - vo)
            print("  " + f"{beta:>8.0f}" + "".join(f"{d:>+14,.1f}" for d in diffs))

    # ── 满额兑现 G 重排：V_full = V(纯pull) + β·g_big + β_small·g_small（拿大件/小宝石才兑现）→ 守>拿治没治 ──
    print(f"\n  ── 满额兑现拿取奖励 G 重排：V_full = V + β·g_big + β_small·g_small（β={BETA_BIG:g} β_small={BETA_SMALL:g}）──")
    s0_gbig = pickup_bonus(s0, _TABLE_BIG_UNIT)
    take_rows = [r for r in rows if r["g_big"] > s0_gbig + 1e-9]   # 子态【新拿走大件】(g_big 比 s0 高)
    rows_full = sorted(rows, key=lambda r: -V_full(r, BETA_BIG, LAM))
    show = list(rows_full[:5])
    for r in take_rows + ([sick] if sick else []):
        if r is not None and r not in show:
            show.append(r)
    print(f"    {'':>3} {'算子':>22} {'落点':>12} {'pull_raw':>9} {'g_big':>11} {'g_small':>9} "
          f"{'V(纯pull)':>12} {'V_full(满额)':>13}")
    for r in rows_full:
        if r not in show:
            continue
        tag = "★病" if r is sick else ("◆拿件" if r in take_rows else "")
        print(f"    {tag:>3} {op_desc(s0, r['op']):>22} {r['post']:>12} {r['pull']:>9.1f} "
              f"{r['g_big']:>11,.0f} {r['g_small']:>9,.0f} {V(r, BETA_BIG, LAM):>12,.0f} "
              f"{V_full(r, BETA_BIG, LAM):>13,.0f}")
    win_full = rows_full[0]
    win_pull = max(rows, key=lambda r: V(r, BETA_BIG, LAM))
    if take_rows:
        best_take = max(take_rows, key=lambda r: V_full(r, BETA_BIG, LAM))
        cured = (win_full in take_rows)
        print(f"    → 满额前局部最优={op_short(win_pull['op'])}(纯pull) ；满额后={op_short(win_full['op'])} ；"
              f"拿件 {op_short(best_take['op'])} V_full={V_full(best_take, BETA_BIG, LAM):,.0f} "
              + ("✅夺冠 → 守>拿【治好】" if cured else "✗仍未夺冠，待查"))
    else:
        cured = (op_short(win_full['op']) != op_short(win_pull['op']))
        print(f"    → 本点无【拿大件】算子（大件在别层/已拿光）→ G 对各候选近似恒定、几乎不改本地排序"
              f"（满额前后局部最优 {op_short(win_pull['op'])}→{op_short(win_full['op'])}）。"
              "此点疗效看【全程路线审计·就近病合计】，非本地决策。")

    # 病 op 的子态再展开一层（level-2）：拿了病 op 之后能开出什么续接算子（看"继续深入"长什么样、值不值）
    if sick is not None:
        print(f"\n  ── level-2：病 op({op_short(sick['op'])}) 子态续接算子（拿了之后能做什么）──")
        sc = sick["child"]
        sc2, _ = _absorb(sc, step)
        g2 = sc2.hero
        ch2 = expand_children(sc2, cross_floor=True)
        if not ch2:
            print("    （续接无算子：拿了即到块尽头/无更多边界）")
        else:
            rows2, R2, big2 = score_children(sc2, ch2, roster_future, zone, big_cells)
            rows2.sort(key=lambda r: -V(r, BETA_BIG, LAM))
            print(f"    子态 {sc2.current_floor}({g2.x},{g2.y}) HP={g2.hp} 续接 {len(rows2)} 算子（按 V(25,.2) 降序，取前 8）：")
            for r in rows2[:8]:
                print(f"      {op_desc(sc2, r['op']):>22} {r['post']:>12} 子HP={r['hp']:>4} "
                      f"HP代价={r['dcost']:>+5} pull_raw={r['pull']:>8.3f} V(25,.2)={V(r, BETA_BIG, LAM):>11,.1f}")


def main():
    start, region_actions = load_region_actions()
    zone = build_zone()
    roster_future = build_future_roster(start)
    big_cells, tau, ranked = detect_big_items(zone, roster_future, start)
    global _TABLE_BIG_UNIT, _TABLE_SMALL_UNIT
    _TABLE_BIG_UNIT = build_pickup_bonus(ranked, big_cells, 1.0, 0.0)     # 大件 raw ΔRP₀（β=1）
    _TABLE_SMALL_UNIT = build_pickup_bonus(ranked, big_cells, 0.0, 1.0)   # 小宝石 raw ΔRP₀（β_small=1）

    print("=" * 108)
    print(f"四决策点解剖·打分明细  路线=beta_big25_lam0.2 best-MT10（region 段 {len(region_actions)} 步）")
    print(f"产品默认：β_big={BETA_BIG:g}  λ={LAM:g}  |  扫描 β∈{SWEEP_BETA} × λ∈{SWEEP_LAM}")
    print(f"大件涌现（ΔRP 最大乘性缝，数据自动找、不硬编码）：τ={tau:,.0f}  大件 {len(big_cells)} 件：")
    for drp, cell, da, dd in ranked:
        mark = "★大件" if cell in big_cells else "  小宝石"
        print(f"    {mark} {cell[0]}({cell[1]},{cell[2]}) +atk{da}/+def{dd}  ΔRP={drp:,.0f}")
    print("=" * 108)

    for tok, anchor, tgt, label in POINTS:
        dissect(start, region_actions, zone, roster_future, big_cells, tok, anchor, tgt, label)


if __name__ == "__main__":
    main()
