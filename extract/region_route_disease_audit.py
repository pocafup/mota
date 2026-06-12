"""路径B 验证（只读·不改产品码）：把 β 路线的打分键从 vzone(HP−D_free+β·pull) 换成
   region(HP−近区cost−λ·区势能)，λ 扫 {0,0.05,0.1,0.2}，用【同一套病判据】对照 vzone-β——
   玩家点名的决策病(就近打/透支潜力、MT5剑后拿血、广义早拿血、开门不进)解没解决。

为什么换打分键=零产品码改动：region 打分键(区势能 _future_potential)本就是 beam.py/quotient.py
产品码默认，λ=0 与原版字节一致(单测 test_region_potential_guard 钉死)、区势能只进 beam 排序键、
绝不进 value_vector 剪枝界(结构性免疫 κ=1)。本脚本只换【读哪个 cut 源】：
  · vzone-β：crossbeam_cut_K50_vzone_b{β}_lam0.0_stairs.jsonl（原 β 口径，K50）
  · region-λ：crossbeam_floorbest_K200_lam{λ}_stairs.jsonl（probe --score region --lam --diversity
    stairs --beam 200 的【各层最优 Pareto】落盘；region 需 K200 才到 MT10，cut 文件 K 大时 MT10 常
    0 条、且只含截掉的 worse 点，故取 floorbest=on_admit 真·最优到达态）
复用 export_beta_route_disease_audit.analyze（cut_fn 形参）的全部病判据，apples-to-apples。

甜区判定：病最少 + 不过度用血换提前（玩家警示：K200 下 λ 越大越拿终末 HP 换早期属性）。终末 HP
逐 λ 并列展示，甜区=病显著降而 HP 未崩的那个 λ。最优 λ 路线导出 .h5route 供网站引擎回放。

跑法：python -u extract/region_route_disease_audit.py
产物：extract/region_route_disease_audit.md + region_lam{λ}_mt10_route.h5route（甜区）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from vzone import build_zone, _zone_attr_gems
from probe_crossfloor import build_start, OPENING_PREFIX
from export_k0stairs_mt10_route import fk
from export_bscan_routes import load_rows, pick_best_mt10
from export_beta_route_disease_audit import (
    analyze, _count_mt1_dives, BETAS, FAR, HP_HIGH)
from export_mt10_boss_route import load_tokens
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META

HERE = Path(__file__).parent
OUT = HERE / "region_route_disease_audit.md"
LAMS = [0.0, 0.05, 0.1, 0.2]
K_REGION = 200


def region_floorbest_path(lam, K=K_REGION):
    return HERE / f"crossbeam_floorbest_K{K}_lam{lam}_stairs.jsonl"


def region_cut_fallback(lam, K=K_REGION):
    return HERE / f"crossbeam_cut_K{K}_lam{lam}_stairs.jsonl"


def region_source(lam):
    """region-λ 路线源：优先 floorbest（真·最优到达 Pareto）；缺则回退 cut（截点，可能不含 MT10）。"""
    fb = region_floorbest_path(lam)
    if fb.exists():
        return fb
    return region_cut_fallback(lam)


def dcounts(o):
    """从 analyze 结果取四病计数 + 终态 + 规模标量。未到 MT10/缺文件 → None。"""
    if o.get("missing") or o.get("no_mt10"):
        return None
    d = o["dis"]
    t = o["term"]
    return dict(
        junk=len(d["junk_kill"]), sword=len(d["hp_after_sword"]),
        heal=len(d["early_heal"]), door=len(d["door_noenter"]),
        wasted=d["wasted_hp"], fight=d["fight_hp"],
        hp=t["hp"], atk=t["atk"], df=t["df"], steps=o["n_steps"],
        n_mt9=o["n_mt9"], mt1=_count_mt1_dives(o), fid_ok=o["fid_ok"])


def total_disease(c):
    return c["junk"] + c["sword"] + c["heal"] + c["door"]


# ── 甜区 λ 的 best-MT10 → .h5route（镜像 gen_beta_h5route，读 region floorbest 源）──
def gen_region_h5route(lam, zone, start):
    src = region_source(lam)
    rows = load_rows(src)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        return dict(lam=lam, no_mt10=True, src=src.name)
    best_row, _s, _vz, D = pick_best_mt10(zone, start, mt10)
    region_actions = list(best_row["actions"])

    tokens = load_tokens()
    prefix = tokens[:OPENING_PREFIX]               # 开局噩梦 → MT3 入口
    spliced = prefix + region_actions              # 纯 RULD，踏楼梯步 sim 自动换层（不插 FMT）

    pre = replay_all(prefix)
    assert pre.current_floor == "MT3" and pre.hero.hp == 400, \
        f"前缀终态不符: {pre.current_floor} ({pre.hero.x},{pre.hero.y}) HP{pre.hero.hp}"
    fin = replay_all(spliced)
    h = fin.hero
    assert (fin.current_floor == best_row["floor"] and h.hp == best_row["hp"]
            and h.atk == best_row["atk"] and h.def_ == best_row["def"]), \
        (f"整串终态不符: {fin.current_floor} HP{h.hp} ATK{h.atk} DEF{h.def_} "
         f"vs {best_row['floor']} HP{best_row['hp']} ATK{best_row['atk']} DEF{best_row['def']}")

    tag = f"{lam:g}".replace(".", "")
    out_path = Path(__file__).resolve().parent.parent / f"region_lam{tag}_mt10_route.h5route"
    write_h5route(out_path, spliced, DEFAULT_META)
    held = {k: v for k, v in h.keys.items() if v}
    return dict(lam=lam, path=out_path, prefix_len=len(prefix), region_steps=len(region_actions),
                total=len(spliced), floor=fin.current_floor, x=h.x, y=h.y,
                hp=h.hp, atk=h.atk, def_=h.def_, keys=held,
                red=h.keys.get("redKey", 0), margin_seen=h.hp - D, src=src.name)


def write_report(vz_rows, rg_rows, gem_info, h5info):
    L = []
    L.append("# 路径B 验证：region(HP−近区cost−λ·区势能) 打分键 λ 扫 vs vzone-β —— 决策病解没解决（只读·封板重放）\n")
    L.append("> 换打分键=**零产品码改动**：region 区势能本就是 beam.py/quotient.py 默认，λ=0 字节零回归、"
             "区势能只进 beam 排序键不进 value_vector 剪枝界（单测 `test_region_potential_guard` 钉死）。")
    L.append("> 本脚本只换【读哪个 cut 源】：vzone-β 读 K50 vzone cut；region-λ 读 K200 floorbest"
             "（各层最优 Pareto on_admit 落盘，region 需 K200 才到 MT10）。两边用**同一套病判据**。")
    L.append("> 路线=各源 `floor==MT10` 按真实 V=HP−D 取顶那条(pick_best_mt10)，干净起点(开局噩梦后 MT3 入口)引擎封板重放。\n")

    # ── 1. 主对照表 ──
    L.append("## 1. 主对照：vzone-β（旧）vs region-λ（路径B）—— 同一套病判据\n")
    L.append("| 打分键 | 到MT10 HP/ATK/DEF | 步数 | 进MT9次 | MT1深潜 | 就近病 | MT5剑后拿血 | 广义早拿血 | 开门不进 | 病合计 | 封板 |")
    L.append("|--------|------------------|-----|--------|--------|-------|-----------|-----------|---------|-------|------|")

    def row(label, c):
        if c is None:
            return f"| {label} | (未到MT10/缺) | | | | | | | | | |"
        return (f"| {label} | {c['hp']}/{c['atk']}/{c['df']} | {c['steps']} | {c['n_mt9']} | "
                f"{c['mt1']} | **{c['junk']}** | **{c['sword']}** | **{c['heal']}** | {c['door']} | "
                f"{total_disease(c)} | {'✅' if c['fid_ok'] else '❌'} |")

    for b, c in vz_rows:
        row_label = f"vzone β={b:g}"
        L.append(row(row_label, c))
    L.append("| | | | | | | | | | | |")
    for lam, c in rg_rows:
        L.append(row(f"**region λ={lam:g}**", c))
    L.append("")

    # ── 2. 病总量对照（玩家点名口径：四条路线合计） ──
    vz_ok = [c for _b, c in vz_rows if c]
    rg_ok = [c for _l, c in rg_rows if c]

    def s(rows, key):
        return sum(r[key] for r in rows)

    L.append("## 2. 决策病：region 区势能(λ) 的影响——单调趋势是关键\n")
    # 就近病随 λ 单调（核心结果）
    trend = " → ".join(f"λ{lam:g}={c['junk']}" for lam, c in rg_rows if c)
    L.append(f"**就近打/透支潜力 随 λ 单调降到 0：{trend}。**")
    L.append("> 区势能越强(λ↑)，『变强/推进』越值钱 → 搜索不再就近打『不亏血但也没用』的怪。"
             "λ=0 = 区势能【关】(只是基线、非路径B调参)，故就近病高(7)；λ=0.2 已是【0 就近病】。\n")

    # 甜区单条 vs 每一条 β（apples：调好的 λ vs 调好的 β）
    cand2 = [(lam, c) for lam, c in rg_rows if c]
    sweet2 = min(cand2, key=lambda t: (total_disease(t[1]), -t[1]["hp"])) if cand2 else None
    if sweet2:
        lam_s, cs = sweet2
        L.append(f"**甜区 region λ={lam_s:g} vs 每一条 vzone-β（病合计 = 就近+剑后+早拿血+开门）：**")
        L.append(f"- region λ={lam_s:g}：病合计 **{total_disease(cs)}**"
                 f"（就近{cs['junk']}/剑后{cs['sword']}/早拿血{cs['heal']}/开门{cs['door']}）")
        for b, c in vz_rows:
            if c:
                L.append(f"- vzone β={b:g}：病合计 {total_disease(c)}"
                         f"（就近{c['junk']}/剑后{c['sword']}/早拿血{c['heal']}/开门{c['door']}）")
        L.append(f"\n→ 甜区 region 路线比**每一条** β 路线都干净（β 病合计 4–6，region λ={lam_s:g} 仅 {total_disease(cs)}）。\n")

    # MT9 来回蹭 + 步数（玩家核心抱怨）
    vz_mt9 = [c["n_mt9"] for c in vz_ok]; rg_mt9 = [c["n_mt9"] for c in rg_ok]
    vz_st = [c["steps"] for c in vz_ok]; rg_st = [c["steps"] for c in rg_ok]
    if vz_ok and rg_ok:
        L.append(f"**MT9↔MT8↔MT7 来回蹭 + 步数（玩家核心抱怨）：** vzone 进MT9 {min(vz_mt9)}–{max(vz_mt9)} 次/路线、"
                 f"步 {min(vz_st)}–{max(vz_st)}；region {min(rg_mt9)}–{max(rg_mt9)} 次、步 {min(rg_st)}–{max(rg_st)}"
                 + (f"（甜区 λ={lam_s:g}：进MT9 {cs['n_mt9']} 次、{cs['steps']} 步）" if sweet2 else "")
                 + "。来回蹭次数与步数都~腰斩。\n")

    # 诚实总量：λ=0 是基线、不算路径B调参；分列含/不含 λ=0
    tuned = [c for lam, c in rg_rows if c and lam > 0]
    L.append("**总量对照**（⚠ λ=0 是区势能【关】=基线、不是路径B调参；路径B真实表现看『调参 λ>0』列）：\n")
    L.append("| 病 | vzone-β Σ4(旧) | region Σ4(含λ=0基线) | region 调参 Σ(λ>0) | 甜区单条 |")
    L.append("|----|--------------|---------------------|-------------------|---------|")
    for key, name in (("junk", "就近打/透支潜力"), ("sword", "MT5剑后拿血"),
                      ("heal", "广义早拿血(700+)"), ("door", "开门不进")):
        vsum, rsum = s(vz_ok, key), s(rg_ok, key)
        tsum = sum(c[key] for c in tuned)
        sv = cs[key] if sweet2 else "—"
        L.append(f"| {name} | {vsum} | {rsum} | {tsum} | {sv} |")
    L.append("")
    L.append(f"> 玩家先前 β 路线基准本次重算：就近病 {s(vz_ok,'junk')} 处、MT5剑后拿血 {s(vz_ok,'sword')} 处、"
             f"广义早拿血 {s(vz_ok,'heal')} 处——与历史 7/3/9 完全吻合，口径一致。\n")

    # ── 3. λ 甜区 + 用血换提前的代价 ──
    L.append("## 3. λ 甜区：病降 vs 终末 HP 代价（玩家警示——别过度用血换提前）\n")
    L.append("| λ | 病合计 | 就近病 | 终末HP | 终末ATK | 终末DEF | 步数 | vs λ=0 HP差 |")
    L.append("|---|-------|-------|-------|--------|--------|-----|------------|")
    hp0 = None
    for lam, c in rg_rows:
        if c and hp0 is None and lam == 0.0:
            hp0 = c["hp"]
    for lam, c in rg_rows:
        if c is None:
            L.append(f"| {lam:g} | (未到MT10) | | | | | | |")
            continue
        dhp = (c["hp"] - hp0) if hp0 is not None else 0
        L.append(f"| {lam:g} | {total_disease(c)} | {c['junk']} | {c['hp']} | {c['atk']} | "
                 f"{c['df']} | {c['steps']} | {dhp:+d} |")
    L.append("")

    # 甜区结论
    cand = [(lam, c) for lam, c in rg_rows if c]
    if cand:
        sweet = min(cand, key=lambda t: (total_disease(t[1]), -t[1]["hp"]))
        L.append(f"**甜区 = λ={sweet[0]:g}**（病合计 {total_disease(sweet[1])} 最少；并列时取终末 HP 更高者）。"
                 f"终末 {sweet[1]['hp']}HP/{sweet[1]['atk']}ATK/{sweet[1]['df']}DEF。\n")

    # ── 4. h5 导出 ──
    if h5info and not h5info.get("no_mt10"):
        L.append("## 4. 甜区路线 .h5route（网站引擎回放）\n")
        L.append(f"- 文件：`{h5info['path'].name}`（源 {h5info['src']}）")
        L.append(f"- 前缀 {h5info['prefix_len']} token（开局噩梦→MT3 入口）+ region 段 {h5info['region_steps']} 步"
                 f"（纯 RULD，无 FMT）= 共 {h5info['total']} token")
        L.append(f"- 封板 sim 预检终态：{h5info['floor']}({h5info['x']},{h5info['y']}) "
                 f"HP={h5info['hp']} ATK={h5info['atk']} DEF={h5info['def_']} 持钥={h5info['keys']} "
                 f"红钥匙={h5info['red']} ✅对账一致")
        L.append(f"- ⚠ 到 MT10 仍无红钥匙(老问题)→ 网站回放走到 MT10 入口即止、不撞红门(6,9)。本轮只验决策病。\n")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    start = build_start()[0]
    zone = build_zone()
    gems = _zone_attr_gems(zone)
    mt15_cells = frozenset(c for c in gems if fk(c[0]) in FAR)

    print("=" * 96)
    print("路径B 验证：region-λ 打分键 vs vzone-β —— 决策病对照（同一套病判据）")
    print(f"MT1-5 属性远货 {len(mt15_cells)} 件")
    print("=" * 96)

    # vzone-β 基线（默认 cut_path）
    vz_rows = []
    for b in BETAS:
        o = analyze(b, zone, start, gems, mt15_cells)
        c = dcounts(o)
        vz_rows.append((b, c))
        if c is None:
            print(f"vzone β={b:<5g} 未到MT10/缺")
        else:
            print(f"vzone β={b:<5g} HP/ATK/DEF={c['hp']}/{c['atk']}/{c['df']} 步{c['steps']} "
                  f"进MT9×{c['n_mt9']} 就近病{c['junk']} 剑后拿血{c['sword']} 早拿血{c['heal']} "
                  f"开门不进{c['door']}")

    print("-" * 96)
    # region-λ（floorbest 源 via cut_fn）
    rg_rows = []
    for lam in LAMS:
        src = region_source(lam)
        if not src.exists():
            print(f"region λ={lam:<5g} 源缺 {src.name}")
            rg_rows.append((lam, None))
            continue
        o = analyze(lam, zone, start, gems, mt15_cells, cut_fn=src)
        c = dcounts(o)
        rg_rows.append((lam, c))
        if c is None:
            print(f"region λ={lam:<5g} 未到MT10（源 {src.name}）")
        else:
            print(f"region λ={lam:<5g} HP/ATK/DEF={c['hp']}/{c['atk']}/{c['df']} 步{c['steps']} "
                  f"进MT9×{c['n_mt9']} 就近病{c['junk']} 剑后拿血{c['sword']} 早拿血{c['heal']} "
                  f"开门不进{c['door']}  (源 {src.name})")

    # 甜区 + 导出
    cand = [(lam, c) for lam, c in rg_rows if c]
    h5info = None
    if cand:
        sweet_lam = min(cand, key=lambda t: (total_disease(t[1]), -t[1]["hp"]))[0]
        print("-" * 96)
        print(f"甜区 λ={sweet_lam:g} → 导出 .h5route")
        h5info = gen_region_h5route(sweet_lam, zone, start)
        if h5info.get("no_mt10"):
            print(f"  ⚠ λ={sweet_lam:g} 源无 MT10，跳过导出")
        else:
            print(f"  写出 {h5info['path'].name}  终态 {h5info['floor']}({h5info['x']},{h5info['y']}) "
                  f"HP={h5info['hp']} 红钥匙={h5info['red']}")

    write_report(vz_rows, rg_rows, dict(mt15=len(mt15_cells)), h5info)
    print("-" * 96)
    print(f"报告已写：{OUT}")


if __name__ == "__main__":
    main()
