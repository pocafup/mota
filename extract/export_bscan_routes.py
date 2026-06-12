"""【只导出·核实，不重跑搜索】各 β 路线逐里程碑 + 红钥匙核实 + 真实余量重估。

回答玩家三问（2026-06-10）：
  1. 各 β 到 MT10 的「最好那条」(按真实 V=HP−D 选，不用裸 boss_toll) 逐里程碑：换层/装备宝石/
     拿钥匙/开门/打怪 + 当刻坐标/HP/ATK/DEF/各色钥匙。
  2. 红钥匙核实：这条拿到红钥匙没? 第几步? 打了 MT8 两个 def22 卫兵没?
     （没红钥匙 → 进不了 boss 房[红门 6,9 必经] → 那个 +余量 是假的。）
  3. 重估真实余量：把 D 漏的 (a)封房埋伏怪 (b)红门 都算进去后还剩多少。

铁律遵循：
  · 不改 sim/solver；动作串=cut 文件原样 RULD、引擎封板重放对账；怪/宝石/钥匙归因到 data 真读格。
  · 绝不手推路径/属性/损血——满房损血、可达性全由引擎 compute_combat / 真地图 BFS 算。

源码核实（来源已在对话核对，数值见 data/games51）：
  · boss 房入口红门：MT10.json map[9][6]=83(redDoor)，在入口(6,10)→队长(6,4)的中央竖井上；
    侧袋被 330(unbreakableWall)+85(specialDoor 事件门) 封死 → 红门是进 boss 房的唯一通道。本脚本
    用真地图 BFS 复核（有/无红钥匙各跑一次）。
  · 埋伏满房 = 6×骷髅人(209) + 2×骷髅士兵(210) + 队长(211)；来源 MT10.json events['6,5'] 的
    generateMove 生成列表 + autoEvent['6,3'] 的 8 格门控(清全 8 格才开出口)。
  · D 两条固有局限(vzone.py:188-193 / 290-295)：最短路只对【路径上】障碍记损血→封房埋伏怪几乎不计；
    且把上锁门当【免费过路】→红门零代价穿、根本不查英雄有没有红钥匙。
  · MT8 红钥匙(23 @10,2) 在 specialDoor(85 @10,4) 后；该门由【杀光两个 yellowGuard(221 def22
    @9,5/11,5)】触发 afterBattle(flag:8) openDoor 打开。怪数值：队长 hp100/atk65/def15、
    骷髅人 hp50/atk42/def6、骷髅士兵 hp55/atk52/def12、卫兵 hp50/atk48/def22（均无 special）。

跑法：python -u extract/export_bscan_routes.py
产物：extract/bscan_routes_redkey_audit.md
"""
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, WALL_TILES
from solver.verify import replay
from vzone import build_zone, boss_toll, _toll, v_zone, _zone_attr_gems
from probe_crossfloor import build_start
from export_k0stairs_mt10_route import build_milestones, nz_keys, fk

HERE = Path(__file__).parent
OUT = HERE / "bscan_routes_redkey_audit.md"
BETAS = [0, 0.5, 1, 2, 4, 8]

# 门 tile（tiles.json）：可开色门 vs 硬门
DOOR_OPENABLE = {81, 82, 84}          # 黄/蓝/绿：假设英雄能开（核红门必经性时放行，给最宽可达）
RED_DOOR = 83                          # 红门：仅持红钥匙可过
HARD_DOOR = {85, 86}                   # 85=机关门(事件门)、86=铁门：一区无钥/事件控 → 当墙
NB4 = [(0, -1), (0, 1), (-1, 0), (1, 0)]

# 埋伏满房构成（来源 MT10.json events['6,5'] 生成列表）
AMBUSH = [("skeleton", 6), ("skeletonSoldier", 2)]   # 6 骷髅人 + 2 骷髅士兵
GUARD_CELLS_MT8 = {("MT8", 9, 5), ("MT8", 11, 5)}    # 两个 def22 卫兵格


def cut_path(beta):
    tag = f"_b{beta:g}" if beta else ""
    return HERE / f"crossbeam_cut_K50_vzone{tag}_lam0.0_stairs.jsonl"


def load_rows(fn):
    rows = []
    with open(fn, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def red_key_of(value):
    return int(value.get("key:redKey", 0)) if isinstance(value, dict) else 0


def keys_by_color(value):
    if not isinstance(value, dict):
        return {}
    return {k[4:]: int(v) for k, v in value.items() if k.startswith("key:") and v}


def find_mon(mon_cache, mid):
    for m in mon_cache.values():
        if m is not None and m.id == mid:
            return m
    return None


def reach_captain(floor, src, captain_cell, has_red):
    """真地图 BFS：从 src 能否走到队长格(=进 boss 房)。读 floor.terrain（引擎数据），不手推。
    可过 = 非硬墙(WALL_TILES∪_no_pass) 且非硬门(85/86)；红门按 has_red 放行；黄蓝绿门放行(假设有钥)；
    怪/道具/楼梯/地形格均可过。captain_cell 自身(怪格)可过=到达。"""
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    nopass = getattr(floor, "_no_pass_tiles", set())
    seen = {src}
    dq = deque([src])
    while dq:
        x, y = dq.popleft()
        if (x, y) == captain_cell:
            return True
        for dx, dy in NB4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < cols and 0 <= ny < rows) or (nx, ny) in seen:
                continue
            t = floor.terrain[ny][nx]
            if (nx, ny) == captain_cell:          # 队长格(airwall/怪叠加)直接算到达，免被 17 误挡
                return True
            if t in WALL_TILES or t in nopass:
                continue
            if t in HARD_DOOR:
                continue
            if t == RED_DOOR and not has_red:
                continue
            seen.add((nx, ny))
            dq.append((nx, ny))
    return False


def killbox_toll(skel, sol, cap, atk, def_, mdef):
    """满房真损血 = 6×骷髅人 + 2×骷髅士兵 + 队长（引擎 _toll，按给定属性现算）。"""
    t = 0
    if skel is not None:
        t += 6 * _toll(skel, atk, def_, mdef)
    if sol is not None:
        t += 2 * _toll(sol, atk, def_, mdef)
    if cap is not None:
        t += _toll(cap, atk, def_, mdef)
    return t


def pick_best_mt10(zone, start, mt10_rows, topn=60):
    """选 best-MT10：先按 HP−boss_toll(上界, D≥boss_toll) 取前 topn，再封板重放算真实 HP−D 取最大。
    返回 (best_row, final_state, vz, D)。"""
    ranked = sorted(
        mt10_rows,
        key=lambda r: r["hp"] - boss_toll(zone, r["atk"], r["def"], r.get("value", {}).get("mdef", 0)),
        reverse=True,
    )[:topn]
    best = None
    for r in ranked:
        s = replay(start, list(r["actions"]), step, _copy_state)
        vz, D, _info = v_zone(zone, s)
        if best is None or vz > best[2]:
            best = (r, s, vz, D)
    return best


def analyze_beta(beta, zone, start, gems, skel, sol, cap):
    fn = cut_path(beta)
    if not fn.exists():
        return dict(beta=beta, missing=True)
    rows = load_rows(fn)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    n_mt10 = len(mt10)
    n_redkey = sum(1 for r in mt10 if red_key_of(r.get("value", {})) >= 1)
    out = dict(beta=beta, n_rows=len(rows), n_mt10=n_mt10, n_redkey=n_redkey)
    if not mt10:
        return out
    best_row, s_final, vz, D = pick_best_mt10(zone, start, mt10)
    h = s_final.hero
    out["term"] = dict(floor=s_final.current_floor, x=h.x, y=h.y, hp=h.hp,
                       atk=h.atk, def_=h.def_, mdef=h.mdef, keys=nz_keys(h))
    out["vz"] = vz
    out["D"] = D
    out["red_at_term"] = h.keys.get("redKey", 0)
    # 里程碑（封板重放归因）
    milestones, visited, taken_gems, term_snap = build_milestones(
        start, list(best_row["actions"]), zone, gems)
    out["milestones"] = milestones
    # 红钥匙第几步拿到（首个 redKey 增量里程碑）
    red_step = None
    for m in milestones:
        if "redKey" in m["label"] and "拿钥匙" in m["label"]:
            red_step = m["i"]
            break
    out["red_step"] = red_step
    # MT8 两个 def22 卫兵杀了几个（里程碑标了「初级卫兵」+ 在 MT8）
    out["mt8_guards_killed"] = sum(
        1 for m in milestones if m["floor"] == "MT8" and "初级卫兵" in m["label"])
    # 入 MT10 的落点（首个 floor==MT10 里程碑）
    ent = next((m for m in milestones if m["floor"] == "MT10"), None)
    out["mt10_entry"] = (ent["x"], ent["y"]) if ent else None
    # 真实余量重估
    cap_toll = boss_toll(zone, h.atk, h.def_, h.mdef)
    full = killbox_toll(skel, sol, cap, h.atk, h.def_, h.mdef)
    out["cap_toll"] = cap_toll
    out["killbox_full"] = full
    out["margin_heuristic"] = h.hp - D                 # 搜索看到的（D：红门免费+埋伏几乎不计）
    out["margin_full"] = h.hp - full                   # 满房全清(8怪+队长)，不含红钥匙门是否能开
    out["cap_killable"] = cap is not None and h.atk > cap.def_
    out["fidelity_ok"] = (s_final.current_floor == best_row["floor"]
                          and h.hp == best_row["hp"] and h.atk == best_row["atk"]
                          and h.def_ == best_row["def"])
    return out


def write_report(results, reach_rows, captain_cell, skel, sol, cap):
    L = []
    L.append("# β 扫各路线导出 + 红钥匙核实 + 真实余量重估（只读·引擎封板重放）\n")
    L.append("> 不重跑搜索；动作串=各 β 的 cut 文件里 `floor==MT10` 按真实 V=HP−D 取顶的那条，"
             "从干净起点(开局噩梦后 MT3 入口)引擎封板重放对账。怪/宝石/钥匙归因到 data 真读格。\n")

    # ── §0 源码核实：红门必经性 + D 两条局限 ──
    L.append("## 0. 源码核实：boss 房进入机制（红门必经 + D 漏了什么）\n")
    L.append(f"- **真地图 BFS（MT10 静态地图，引擎 terrain 数据）**：从两个候选入口落点能否走到队长格 "
             f"{captain_cell}（=进 boss 房）——黄/蓝/绿门放行、机关门(85)/铁门(86)当墙、红门(6,9=tile83)按是否持红钥匙：")
    for cell, no_red, with_red in reach_rows:
        L.append(f"  - 落点 {cell}：**不持红钥匙**可达={'是' if no_red else '**否**'}　|　"
                 f"持红钥匙可达={'是' if with_red else '否'}")
    all_blocked = all(not no_red for _c, no_red, _w in reach_rows)
    all_open_w = all(w for _c, _n, w in reach_rows)
    if all_blocked and all_open_w:
        L.append("  - → **结论：无论从哪个落点，无红钥匙都到不了队长格；持红钥匙才能到。"
                 "红门(6,9)是进 boss 房的唯一通道，红钥匙必需。**侧袋被 330 硬墙 + 85 机关门封死，绕不过去。")
    L.append(f"- **埋伏满房**（来源 MT10.json events['6,5'] 生成列表 + autoEvent 8 格门控）："
             f"6×骷髅人(id209 hp{skel.hp}/atk{skel.atk}/def{skel.def_}) + "
             f"2×骷髅士兵(id210 hp{sol.hp}/atk{sol.atk}/def{sol.def_}) + "
             f"队长(id211 hp{cap.hp}/atk{cap.atk}/def{cap.def_})，共 9 战。")
    L.append("- **D 两条固有局限**（vzone.py 注释明记，非 bug，是 admissible 上界的乐观）：")
    L.append("  - (a) 最短路只对【路径上】障碍记损血。到达态(埋伏触发前)从入口直上竖井到队长，"
             "路上**一只埋伏怪都不踩**(它们在侧格/上排)→ D 的 boss 段≈只算队长 1 战，**8 只埋伏怪全漏**。")
    L.append("  - (b) D 把上锁门当【免费过路】→ **红门零代价穿、根本不查有没有红钥匙**。")
    L.append("  - ⇒ 搜索看到的 `HP−D` 同时吃了这两个乐观红利，是**上界幻觉**，不是能不能过 boss 的真账。\n")

    # ── §1 对照表 ──
    L.append("## 1. 对照表：各 β best-MT10 路线（红钥匙 + 真实余量重估）\n")
    L.append("| β | 到MT10态 HP/ATK/DEF | 持红钥匙 | 拿钥第# | 杀MT8卫兵 | 队长可杀 | HP−D(搜索看到) | 满房真损血 | 重估余量(HP−满房) | MT10态有红钥比例 |")
    L.append("|---|--------------------|---------|--------|----------|---------|---------------|-----------|------------------|----------------|")
    for o in results:
        b = o["beta"]
        if o.get("missing"):
            L.append(f"| {b:g} | (cut 文件缺) | | | | | | | | |")
            continue
        if not o.get("n_mt10"):
            L.append(f"| {b:g} | (未到 MT10) | | | | | | | | 0/0 |")
            continue
        t = o["term"]
        triple = f"{t['hp']}/{t['atk']}/{t['def_']}"
        has_red = "✅有" if o["red_at_term"] else "❌无"
        red_step = o["red_step"] if o["red_step"] is not None else "—"
        guards = f"{o['mt8_guards_killed']}/2"
        killable = "是" if o["cap_killable"] else "否"
        ratio = f"{o['n_redkey']}/{o['n_mt10']}"
        L.append(f"| {b:g} | {triple} | {has_red} | {red_step} | {guards} | {killable} | "
                 f"{o['margin_heuristic']} | {o['killbox_full']} | "
                 f"**{o['margin_full']}** | {ratio} |")
    L.append("")
    L.append("> - **持红钥匙**：到达 MT10 的那一刻手里有没有红钥匙。❌无 → 即便“到了 MT10”也进不了 boss 房，"
             "右侧 `HP−D` 余量是假的。")
    L.append("> - **满房真损血**：6 骷髅人+2 骷髅士兵+队长，按到达态属性引擎现算（不含走位/夹击，"
             "是下界口径的满房直损）。**重估余量 = HP − 满房真损血**。")
    L.append("> - **MT10态有红钥比例**：该 β 所有到达 MT10 的 cut 态里，持≥1 红钥匙的占比"
             "（看“到 MT10”是否普遍不需要红钥匙）。\n")

    # ── §2 每 β 逐里程碑 ──
    L.append("## 2. 各 β best-MT10 逐里程碑（换层/装备宝石/拿钥匙/开门/打怪 + 坐标/属性/持钥）\n")
    for o in results:
        b = o["beta"]
        if o.get("missing") or not o.get("n_mt10"):
            L.append(f"### β={b:g}：{'cut 文件缺' if o.get('missing') else '未到 MT10'}\n")
            continue
        t = o["term"]
        L.append(f"### β={b:g}　到达 MT10 落点={o['mt10_entry']}　终态 "
                 f"{t['floor']}({t['x']},{t['y']}) HP={t['hp']} ATK={t['atk']} DEF={t['def_']} "
                 f"持钥={t['keys']}　封板对账={'✅一致' if o['fidelity_ok'] else '❌偏离'}")
        rk = (f"第 {o['red_step']} 步拿到" if o["red_step"] is not None
              else "**全程未拿红钥匙**")
        L.append(f"- 红钥匙：{rk}　|　MT8 def22 卫兵杀了 {o['mt8_guards_killed']}/2　|　"
                 f"队长可杀(atk>{cap.def_})={'是' if o['cap_killable'] else '否'}")
        L.append(f"- 余量：搜索看到 HP−D={o['margin_heuristic']}（D 含红门免费+埋伏漏算）　vs　"
                 f"满房重估 HP−{o['killbox_full']}=**{o['margin_full']}**")
        L.append("")
        L.append("| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |")
        L.append("|----|------|------|----|----|-----|---------|")
        for m in o["milestones"]:
            L.append(f"| {m['i']} | {m['label']} | ({m['x']},{m['y']})@{m['floor']} | "
                     f"{m['hp']} | {m['atk']} | {m['def_']} | {m['keys']} |")
        L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    start = build_start()[0]
    zone = build_zone()
    gems = _zone_attr_gems(zone)
    skel = find_mon(zone["mon_cache"], "skeleton")
    sol = find_mon(zone["mon_cache"], "skeletonSoldier")
    cap = zone["boss_mon"]

    # 红门必经性：真地图 BFS。两个候选入口落点都跑（MT10.json downFloor=[1,10] / upFloor=[6,10]，
    # 实测各 β 路线落点在两者间，全覆盖消除歧义）；队长静态格 (6,4)。
    fl10 = zone["floors"]["MT10"]["floor"]
    captain_cell = (6, 4)
    landings = [(1, 10), (6, 10)]
    reach_rows = [(c, reach_captain(fl10, c, captain_cell, has_red=False),
                   reach_captain(fl10, c, captain_cell, has_red=True)) for c in landings]

    print("=" * 90)
    print("β 扫路线导出 + 红钥匙核实 + 真实余量重估")
    print("=" * 90)
    for c, nr, wr in reach_rows:
        print(f"红门必经 BFS（落点{c}→队长{captain_cell}）：无红钥可达={nr} / 有红钥可达={wr}")
    print(f"满房：6×骷髅人(def{skel.def_}) + 2×骷髅士兵(def{sol.def_}) + 队长(def{cap.def_})")
    print("-" * 90)

    results = []
    for b in BETAS:
        o = analyze_beta(b, zone, start, gems, skel, sol, cap)
        results.append(o)
        if o.get("missing"):
            print(f"β={b:<4g} cut 文件缺，跳过")
            continue
        if not o.get("n_mt10"):
            print(f"β={b:<4g} 未到 MT10（{o['n_rows']} cut 行）")
            continue
        t = o["term"]
        print(f"β={b:<4g} best-MT10 HP/ATK/DEF={t['hp']}/{t['atk']}/{t['def_']}  "
              f"红钥匙={'有' if o['red_at_term'] else '无'}(全MT10态 {o['n_redkey']}/{o['n_mt10']} 持红钥)  "
              f"杀MT8卫兵={o['mt8_guards_killed']}/2  "
              f"HP−D={o['margin_heuristic']} → 满房重估={o['margin_full']}  "
              f"对账={'✅' if o['fidelity_ok'] else '❌'}")

    write_report(results, reach_rows, captain_cell, skel, sol, cap)
    print("-" * 90)
    print(f"报告已写：{OUT}")


if __name__ == "__main__":
    main()
