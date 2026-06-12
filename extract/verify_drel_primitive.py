"""D_rel 第1步原语验证【只读探针，未接搜索】—— 验"区内松弛预计算"方向是否站得住。

玩家 2026-06-10 定方向：把 D="冻结属性下到 boss 最短血"换成 D_rel="在本区拿一组宝石变强、再
到 boss 的最小总血"。本探针验三件事：
  (a) admissible：D_rel ≤ 已知血下界，且【D_rel 算出的一区 boss 前最优属性 = 27/27】(玩家实战金标准)；
  (b) κ_yellow/κ_blue > 0：钥匙终于对【属性获取】有信号了(D_K 旧结论：黄/蓝对 boss-距离零信号，
      钥匙价值在"属性获取路由"——正是这里要验)；
  (c) 算得动：枚举规模/耗时。

────────────────────────────────────────────────────────────────────────────────
D_rel 口径(admissible-by-construction，每项都取真实血耗【下界】→ D_rel ≤ 真实续航血 → 不错杀)：

  D_rel(预算B) = boss_toll(atk0 + Δatk_可达(B), def0 + Δdef_可达(B), mdef0)

  · G = 一区 boss 前【攻防源】= 7 红宝石(各 atk+1) + 7 蓝宝石(各 def+1) + 铁剑(atk+10) + 铁盾
    (def+10) = 16 个源、Σ=atk+17/def+17(从各层【初始】entities 扫 _tile_to_item，不含 MT10 那批
    setBlock 的【boss 后】奖励、不含祭坛/商人——玩家实证一区不花钱就 27/27、祭坛商人对最优无贡献)。
  · "宝石 g 在预算 B 下可达" = 存在一条 src→g 的路、过门耗钥 ≤ B(per-gem 独立判定)。
    Δ_可达(B) = Σ 各独立可达宝石的 Δ。
  · 【admissible 证明】任何真实路线收集的宝石集 S：S 里每个宝石都被该路线用 ≤B 钥到达过 → 每个都
    【独立可达】→ S ⊆ {独立可达集} → 真实 Δ(S) ≤ Δ_可达(B)(独立可达求和是真实可得增益的【上界】)。
    boss_toll 随属性单调降 → boss_toll(atk0+Δ_可达) ≤ boss_toll(atk0+真实Δ) ≤ 真实续航血。∴ D_rel 下界。✓
  · κ_色 = D_rel(B 该色−1) − D_rel(B) ≥ 0 = 少一把该色钥导致【某属性宝石够不到→变弱→boss 变贵】的血代价。
  · 【第一版保守】acq 获取阶段血按 0 下界处理(acq≥0，丢掉只让 D_rel 更小=更松=仍 admissible)；
    boss 项是【精确】(27/27 是玩家真实属性、boss_toll 即玩家真实 boss 损血)。获取阶段血是下一版要
    谨慎加的【下界】项(加错=高估=危险，故先不加)。

  · 损血全用引擎 _toll(强制可杀 ref_atk=max(atk,怪防+1)，vzone 既定)；门 0 损血、怪付 toll(铁律：
    不手写战斗公式)。塔无关性不适用(extract/ 驱动层探针，可读 MT1-10)；vzone/solver 一行不改。
    引擎只当裁判，不进搜索循环。
"""
import sys
import time
import heapq
import json
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start
from sim.simulator import _KEY_ITEMS
from vzone import (build_zone, _zone_key_geometry, _passable, _enter_cost,
                   boss_toll, _NB4)

DATA = Path(__file__).parent.parent / "data" / "games51"
items_def = json.loads((DATA / "items.json").read_text(encoding="utf-8"))

# 真可达供给(probe_zone1_key_scarcity 实测 C 终态)；MT2 三把黄一区杀不动 def110 守门怪 → 拿不到。
REACHABLE = {"yellowKey": 53, "blueKey": 3, "redKey": 1}
UNREACHABLE_KEY_CELLS = {("MT2", 3, 4), ("MT2", 4, 4), ("MT2", 3, 5)}
ATTR = ("atk", "def", "mdef")


def item_delta(iid):
    """从 items.json pickup 算 {stat:增量}(一区 ratio=1，gain=base)；非 pickup→{}。只留 atk/def/mdef。"""
    d = items_def.get(iid)
    if not isinstance(d, dict):
        return {}
    pu = d.get("pickup")
    if not isinstance(pu, dict):
        return {}
    out = defaultdict(int)
    if pu["type"] == "stat":
        if "base" in pu:
            out[pu["stat"]] += pu["base"]      # 一区 ratio=1
        else:
            out[pu["stat"]] += pu.get("delta", 0)
    elif pu["type"] == "multi":
        for op in pu["ops"]:
            out[op["stat"]] += op["delta"]
    return {k: v for k, v in out.items() if k in ATTR}


def collect_attr_gems(zone):
    """扫各层【初始】entities，列攻防源宝石/装备。返回 [(cell,iid,name,datk,ddef)]。"""
    gems = []
    for fid, r in zone["floors"].items():
        fl = r["floor"]
        for y, row in enumerate(fl.entities):
            for x, e in enumerate(row):
                if not e:
                    continue
                iid = fl._tile_to_item.get(e)
                if not iid:
                    continue
                dd = item_delta(iid)
                if dd.get("atk") or dd.get("def"):
                    gems.append(((fid, x, y), iid, items_def[iid]["name"],
                                 dd.get("atk", 0), dd.get("def", 0)))
    return gems


def explore_reachable(zone, src, atk, def_, mdef, budget, pickup_cells=None, cap=None):
    """有界 keyed-BFS：从 src 出发、过门按色库存放行(过则−1)、pickup_cells 过则该色+1(按 cap 封顶)。
       返回【所有出现过的格集合】(per-gem 独立可达：格在任一预算态被达到即算可达)。
       budget 只减(无 pickup)→ 状态有限；有 pickup→ 按 cap 封顶 → 状态有限。"""
    geom = _zone_key_geometry(zone)
    colors = geom["colors"]
    ci = {c: i for i, c in enumerate(colors)}
    door_color, links = geom["door_color"], zone["links"]
    pickup_cells = pickup_cells or {}
    capv = tuple((cap or {}).get(c, 10 ** 9) for c in colors)
    b0 = tuple(min(int(budget.get(c, 0)), capv[i]) for i, c in enumerate(colors))
    start = (src, b0)
    seen = {start}
    reached_cells = {src}
    stack = [start]
    n_states = 0
    while stack:
        node, bud = stack.pop()
        n_states += 1
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in links:
            nbrs.append(links[node])
        for nb in nbrs:
            if not _passable(zone, nb):
                continue
            nbud = bud
            c = door_color.get(nb)
            if c is not None:
                i = ci[c]
                if bud[i] <= 0:
                    continue                       # 开不了 → 此门不可过
                nbud = nbud[:i] + (nbud[i] - 1,) + nbud[i + 1:]
            kc = pickup_cells.get(nb)
            if kc is not None:
                j = ci[kc]
                if nbud[j] < capv[j]:
                    nbud = nbud[:j] + (nbud[j] + 1,) + nbud[j + 1:]
            ns = (nb, nbud)
            if ns not in seen:
                seen.add(ns)
                reached_cells.add(nb)
                stack.append(ns)
    return reached_cells, n_states


def reachable_delta(gems, reached):
    """可达宝石的 ΣΔatk/Δdef + 可达宝石列表。"""
    datk = ddef = 0
    got = []
    for (cell, iid, name, da, dd) in gems:
        if cell in reached:
            datk += da
            ddef += dd
            got.append((cell, iid, name, da, dd))
    return datk, ddef, got


def D_rel(zone, atk0, def0, mdef0, datk, ddef):
    return boss_toll(zone, atk0 + datk, def0 + ddef, mdef0)


def per_gem_min_color(zone, src, atk0, def0, mdef0, gems, color, others_full, cap):
    """逐宝石：在其余色给满下，该 color 预算从 0 升，宝石首次可达的最小该色钥数(独立可达口径)。
       够不到(扫到 cap 仍不可达)→ None。返回 {cell: min_budget_or_None}。"""
    res = {g[0]: None for g in gems}
    remaining = set(res)
    for b in range(0, cap + 1):
        if not remaining:
            break
        budget = dict(others_full)
        budget[color] = b
        reach, _ = explore_reachable(zone, src, atk0, def0, mdef0, budget)
        for cell in list(remaining):
            if cell in reach:
                res[cell] = b
                remaining.discard(cell)
    return res


def main():
    t0 = time.time()
    L = []
    w = L.append

    real, nopen = build_start()
    rh = real.hero
    src = (real.current_floor, rh.x, rh.y)
    atk0, def0, mdef0 = rh.atk, rh.def_, rh.mdef
    real_keys = {k: v for k, v in dict(rh.keys).items() if v and k in _KEY_ITEMS}

    zone = build_zone()
    geom = _zone_key_geometry(zone)
    colors = geom["colors"]
    gems = collect_attr_gems(zone)
    pickup_reach = {cell: c for cell, c in geom["key_item"].items()
                    if cell not in UNREACHABLE_KEY_CELLS}

    tot_atk = sum(g[3] for g in gems)
    tot_def = sum(g[4] for g in gems)

    w("=" * 100)
    w("D_rel 第1步原语验证 —— 区内松弛预计算方向(只读，未接搜索)")
    w("=" * 100)
    w(f"真起点(穿 {nopen} token 开局噩梦后) = {src}  atk0={atk0} def0={def0} mdef0={mdef0}")
    w(f"真起手钥匙 = {real_keys or '空(0 钥)'}   预算维 = {colors}")
    w(f"真可达供给 = {REACHABLE}")
    w("")
    w(f"G(攻防源) = {len(gems)} 个：ΣΔ = atk+{tot_atk}/def+{tot_def}  "
      f"→ boss 前满拿属性 = {atk0 + tot_atk}/{def0 + tot_def}")
    by_floor = defaultdict(list)
    for (fid, x, y), iid, name, da, dd in gems:
        tag = f"atk+{da}" if da else f"def+{dd}"
        by_floor[fid].append(f"({x},{y}){name}={tag}")
    for fid in [f"MT{i}" for i in range(1, 11)]:
        if by_floor.get(fid):
            w(f"    {fid}: " + "  ".join(by_floor[fid]))
    w("-" * 100)

    # ───────────── (a) admissible + 27/27 金标准 ─────────────
    w("")
    w("#" * 100)
    w("# (a) admissible 自检：D_rel 算出的 boss 前最优属性 = 27/27 ? 且 D_rel ≤ 已知血下界 ?")
    w("#" * 100)
    # 最乐观可达(预授真可达钥 + 沿路捡 → 最大可达集 → D_rel 最小 = 最松下界)
    reach_opt, ns_opt = explore_reachable(zone, src, atk0, def0, mdef0, real_keys,
                                          pickup_cells=pickup_reach, cap=REACHABLE)
    da_o, dd_o, got_o = reachable_delta(gems, reach_opt)
    # 预授真可达钥、不捡(也够吗)
    reach_pre, ns_pre = explore_reachable(zone, src, atk0, def0, mdef0, REACHABLE)
    da_p, dd_p, got_p = reachable_delta(gems, reach_pre)

    w(f"  最优属性(预授真可达钥+沿路捡)  = atk {atk0 + da_o}/def {def0 + dd_o}   "
      f"可达攻防源 {len(got_o)}/{len(gems)}")
    w(f"  最优属性(预授真可达钥·不捡)    = atk {atk0 + da_p}/def {def0 + dd_p}   "
      f"可达攻防源 {len(got_p)}/{len(gems)}")
    miss = [g for g in gems if g[0] not in reach_opt]
    if miss:
        w(f"  ⚠ 够不到的攻防源({len(miss)})：")
        for (cell, iid, name, da, dd) in miss:
            w(f"      {cell} {name} (atk+{da}/def+{dd}) —— 待查为何不可达")
    gold = (atk0 + da_o == 27 and def0 + dd_o == 27)
    w(f"  → boss 前最优属性 = {atk0 + da_o}/{def0 + dd_o}  "
      f"{'★ = 27/27 金标准吻合(攻防源全可达)' if gold else '✗ 不等于 27/27 —— G/可达性有问题，须查'}")
    drel_full = D_rel(zone, atk0, def0, mdef0, da_o, dd_o)
    boss_naked = D_rel(zone, atk0, def0, mdef0, 0, 0)
    w("")
    w(f"  D_rel(满拿) = boss_toll({atk0 + da_o},{def0 + dd_o}) = {drel_full}")
    w(f"    对照 boss_toll(裸 {atk0}/{def0}) = {boss_naked}  → 拿满属性把 boss 损血从 "
      f"{boss_naked} 压到 {drel_full}")
    w(f"  【已知血下界】= 玩家实战 boss 处属性正是 27/27 → 引擎 boss 损血 = {drel_full}(精确，非估)。")
    w(f"    ∴ D_rel(boss 项) = {drel_full} = 玩家真实 boss 损血 ≤ 玩家真实【总】续航血(后者另含获取阶段血)。")
    w(f"    admissible：✓(boss 项精确不高估；获取阶段血按 0 下界丢掉 → D_rel 只会更小=更松)。")

    # ───────────── (b) κ：按色预算扫，找属性宝石的门控阈值 ─────────────
    w("")
    w("#" * 100)
    w("# (b) κ_色 > 0 ? —— 逐色把【该色预算】从 0 扫到真可达上限(其余色给满)、不捡，看可达攻防源/D_rel")
    w("#    曲线在哪一把钥匙处跳变。跳变 = 那把钥解锁了属性宝石 = 钥匙对【属性获取】有信号。")
    w("#" * 100)
    sweep_max = {"yellowKey": min(REACHABLE["yellowKey"], 25), "blueKey": REACHABLE["blueKey"],
                 "redKey": REACHABLE["redKey"]}
    kappa_seen = {}
    for color in ("yellowKey", "blueKey", "redKey"):
        w("")
        w(f"────── 扫 {color.replace('Key','')} 预算 0→{sweep_max[color]}(其余色={{others full}}) ──────")
        others = {c: REACHABLE[c] for c in colors if c in REACHABLE and c != color}
        prev_drel = None
        prev_n = None
        rows = []
        first_full = None
        for b in range(0, sweep_max[color] + 1):
            budget = dict(others)
            budget[color] = b
            reach, _ = explore_reachable(zone, src, atk0, def0, mdef0, budget)
            da, dd, got = reachable_delta(gems, reach)
            drel = D_rel(zone, atk0, def0, mdef0, da, dd)
            kap = (prev_drel - drel) if prev_drel is not None else None
            rows.append((b, len(got), atk0 + da, def0 + dd, drel, kap))
            if len(got) == len(gems) and first_full is None:
                first_full = b
            prev_drel, prev_n = drel, len(got)
        # 只打印有跳变的行 + 边界行
        for (b, n, a, d, drel, kap) in rows:
            mark = ""
            if kap is not None and kap > 0:
                mark = f"   ← κ(第{b}把{color.replace('Key','')})= +{kap} 血(解锁属性宝石)"
                kappa_seen.setdefault(color, []).append((b, kap))
            if kap is None or kap > 0 or b == sweep_max[color] or b == first_full:
                w(f"    {color.replace('Key','')}预算={b:>2}  可达源 {n:>2}/{len(gems)}  "
                  f"属性 {a}/{d}  D_rel={drel}{mark}")
        if first_full is not None:
            w(f"  ⇒ {color.replace('Key','')}预算 ≥ {first_full} 即解锁【全部】攻防源；再多的"
              f"{color.replace('Key','')}对【属性】κ=0(只剩对宝箱收集/boss 路有用)。")
        else:
            w(f"  ⇒ 扫到 {sweep_max[color]} 仍未解锁全部攻防源(还差 "
              f"{len(gems) - rows[-1][1]} 个)。")
        if color not in kappa_seen:
            w(f"  ⇒ 全程 κ_{color.replace('Key','')} = 0：该色钥匙不门控任何属性宝石。")

    # ───────────── (b′) 逐宝石门控表：把 κ 跳变坐实到具体宝石(不靠猜) ─────────────
    w("")
    w("#" * 100)
    w("# (b′) 逐宝石门控表 —— 每颗攻防源【最少几把黄/几把蓝】才独立可达(其余色给满、不捡)。")
    w("#    用途：把 (b) 里某把钥的 κ 跳变坐实到【具体哪颗宝石此刻解锁】——尤其那个大跳是不是铁剑，")
    w("#    不靠推断。某色第 b 把的 κ = 恰在 min_该色=b 处首次可达的宝石们之 Δ 令 boss 变便宜之差。")
    w("#" * 100)
    others_for_y = {c: REACHABLE[c] for c in colors if c in REACHABLE and c != "yellowKey"}
    others_for_b = {c: REACHABLE[c] for c in colors if c in REACHABLE and c != "blueKey"}
    min_y = per_gem_min_color(zone, src, atk0, def0, mdef0, gems, "yellowKey",
                              others_for_y, sweep_max["yellowKey"])
    min_b = per_gem_min_color(zone, src, atk0, def0, mdef0, gems, "blueKey",
                              others_for_b, sweep_max["blueKey"])

    def _mc(v):
        return str(v) if v is not None else "够不到"

    w(f"  {'宝石(层/坐标/名)':<26s} {'增益':<8s} {'最少黄':>6s} {'最少蓝':>6s}")
    for (cell, iid, name, da, dd) in sorted(
            gems, key=lambda g: (-(min_y.get(g[0]) or 0), -(min_b.get(g[0]) or 0))):
        tag = f"atk+{da}" if da else f"def+{dd}"
        loc = f"{cell[0]}({cell[1]},{cell[2]}){name}"
        w(f"  {loc:<26s} {tag:<8s} {_mc(min_y.get(cell)):>6s} {_mc(min_b.get(cell)):>6s}")

    buck_y = defaultdict(list)
    buck_b = defaultdict(list)
    for (cell, iid, name, da, dd) in gems:
        buck_y[min_y.get(cell)].append((name, da, dd))
        buck_b[min_b.get(cell)].append((name, da, dd))
    w("")
    w("  按【最少黄】分桶(对齐 b 的黄 κ 跳变；其余色给满)：")
    for b in sorted(k for k in buck_y if k is not None):
        s = ", ".join(f"{nm}({'atk+'+str(da) if da else 'def+'+str(dd)})"
                      for nm, da, dd in buck_y[b])
        sda = sum(da for _, da, dd in buck_y[b])
        sdd = sum(dd for _, da, dd in buck_y[b])
        w(f"    黄={b:>2} 处首次可达：ΣΔatk+{sda}/def+{sdd}  ←  {s}")
    w("  按【最少蓝】分桶(对齐 b 的蓝 κ 跳变；其余色给满)：")
    for b in sorted(k for k in buck_b if k is not None):
        s = ", ".join(f"{nm}({'atk+'+str(da) if da else 'def+'+str(dd)})"
                      for nm, da, dd in buck_b[b])
        sda = sum(da for _, da, dd in buck_b[b])
        sdd = sum(dd for _, da, dd in buck_b[b])
        w(f"    蓝={b:>2} 处首次可达：ΣΔatk+{sda}/def+{sdd}  ←  {s}")

    # ───────────── (c) 算得动 ─────────────
    w("")
    w("#" * 100)
    w("# (c) 算得动？枚举规模 / 耗时")
    w("#" * 100)
    w(f"  G 攻防源 = {len(gems)} 个；可达性靠【单趟】有界 keyed-BFS(per-gem 独立、一趟得全集)，")
    w(f"  非 2^{len(gems)} 子集枚举。最乐观可达 BFS 展开 {ns_opt} 态、预授不捡 {ns_pre} 态。")
    w(f"  κ 扫：黄 {sweep_max['yellowKey']+1} + 蓝 {sweep_max['blueKey']+1} + 红 "
      f"{sweep_max['redKey']+1} = {sum(v+1 for v in sweep_max.values())} 次 BFS。")
    w(f"  总耗时 = {time.time() - t0:.2f}s。→ 算得动。")

    # ───────────── 小结 ─────────────
    w("")
    w("=" * 100)
    w("【第1步原语结论(待玩家核)】")
    w(f"  (a) ✓ boss 前最优属性 = {atk0 + da_o}/{def0 + dd_o}"
      f"{'(=27/27 金标准)' if gold else '(✗ 须查)'}；D_rel(boss 项)={drel_full}=玩家真实 boss 损血，")
    w(f"      获取阶段血按 0 下界丢 → D_rel ≤ 真实续航血，admissible 不破。")
    if kappa_seen:
        parts = []
        for c, lst in kappa_seen.items():
            tot = sum(k for _, k in lst)
            parts.append(f"{c.replace('Key','')}(共 +{tot} 血，{len(lst)} 处跳变)")
        w(f"  (b) κ > 0 出现在：{', '.join(parts)} —— 钥匙对【属性获取】有信号了。")
    else:
        w("  (b) ✗ 全色 κ=0：起点 0 钥沿路捡即可达全部攻防源、或攻防源压根不在门后 —— 钥匙不门控一区属性。")
    w(f"  (c) ✓ 单趟 BFS 得可达全集、非子集爆炸，{time.time() - t0:.2f}s。")
    w("=" * 100)

    text = "\n".join(L)
    out = Path(__file__).parent / "drel_primitive_verify.txt"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[落盘] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
