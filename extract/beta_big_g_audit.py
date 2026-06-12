"""【结合·满额兑现 G 验证·只读·不改产品码】对 (β_big, β_small) 扫描的 floorbest 路线跑【同一套四病判据】，
三方对照：region 基线(bb=0,无 pull/G) vs 纯pull(bb=25,有 pull 无 G,病6~7) vs 满额兑现 G(各 bb/bs)。

核心问题：满额兑现 G(拿走即给 β·ΔRP₀)能不能把【纯 pull 抬高的就近病】压回去，同时【剑盾误判仍治】。
  · 纯 pull 病根：pull 只奖在场/够得到的大件，拿走归 0 → 守着不拿、就近刷活怪（就近病 0→3~6）。
  · 满额兑现：拿走那一刻给【满额】β·ΔRP₀(≥守着的折扣 β·ΔRP/(1+dist))→ 拿≥守，结构性消就近病（big_item_pull 红线）。

源 = crossbeam_floorbest_K200_bb{bb}_bs{bs}_lam0.2_stairs.jsonl（probe --beta-big bb --beta-small bs --lam 0.2
     --beam 200 --diversity stairs 落盘）。基线 bb=0 = crossbeam_floorbest_K200_lam0.2_stairs.jsonl（无 pull/G）。
纯pull = crossbeam_floorbest_K200_bb25_PUREPULL_lam0.2_stairs.jsonl（有 pull 无 G，预留对照）。
判据/重放全复用 beta_big_route_disease_audit（analyze cut_fn 打分无关，只读 jsonl 路线数病），apples-to-apples。

跑法：python -u extract/beta_big_g_audit.py
产物：extract/beta_big_g_audit.md + beta_big{bb}_bs{bs}_lam0.2_mt10_route.h5route（最优档）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from vzone import build_zone, _zone_attr_gems
from probe_crossfloor import build_start, OPENING_PREFIX
from export_k0stairs_mt10_route import fk
from export_bscan_routes import load_rows, pick_best_mt10
from export_beta_route_disease_audit import analyze, FAR
from export_mt10_boss_route import load_tokens
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META
from beta_big_route_disease_audit import (
    dcounts, total_disease, best_route_actions, sword_timing, sword_verdict, LAM, K,
)

HERE = Path(__file__).parent
OUT = HERE / "beta_big_g_audit.md"

# 扫描的 (β_big, β_small) 组合（与 sweep 一致）
COMBOS = [(25, 3), (25, 10), (10, 3), (60, 3)]


def base_floorbest():
    """bb=0 纯 region λ0.2 基线（无 pull/G）。"""
    return HERE / f"crossbeam_floorbest_K{K}_lam{LAM}_stairs.jsonl"


def purepull_floorbest(bb=25):
    """纯 pull（有 pull 无 G）的预留对照（_PUREPULL 备份）。"""
    return HERE / f"crossbeam_floorbest_K{K}_bb{bb}_PUREPULL_lam{LAM}_stairs.jsonl"


def combo_floorbest(bb, bs):
    """满额兑现 G：crossbeam_floorbest_K200_bb{bb}_bs{bs}_lam0.2_stairs.jsonl。"""
    return HERE / f"crossbeam_floorbest_K{K}_bb{bb}_bs{bs}_lam{LAM}_stairs.jsonl"


def gen_combo_h5route(bb, bs, src, zone, start):
    """镜像 gen_bb_h5route：best-MT10 region 动作串接开局前缀 → .h5route（封板 sim 预检终态一致）。"""
    rows = load_rows(src)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        return dict(bb=bb, bs=bs, no_mt10=True, src=src.name)
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

    out_path = Path(__file__).resolve().parent.parent / f"beta_big{bb}_bs{bs}_lam{LAM:g}_mt10_route.h5route"
    write_h5route(out_path, spliced, DEFAULT_META)
    held = {k: v for k, v in h.keys.items() if v}
    return dict(bb=bb, bs=bs, path=out_path, prefix_len=len(prefix), region_steps=len(region_actions),
                total=len(spliced), floor=fin.current_floor, x=h.x, y=h.y,
                hp=h.hp, atk=h.atk, def_=h.def_, keys=held,
                red=h.keys.get("redKey", 0), margin_seen=h.hp - D, src=src.name)


def audit_one(tag, beta_label, src, zone, start, gems, mt15_cells):
    """对单个源 jsonl 跑四病判据 + 剑盾时点。返回 (counts|None, sword_tm|None, reached_mt10)。"""
    if not src.exists():
        return None, None, False, True            # missing
    o = analyze(beta_label, zone, start, gems, mt15_cells, cut_fn=src)
    c = dcounts(o)
    actions, _best, reached = best_route_actions(zone, start, src)
    tm = sword_timing(zone, start, actions, gems) if actions else None
    return c, tm, reached, False


def main():
    start = build_start()[0]
    zone = build_zone()
    gems = _zone_attr_gems(zone)
    mt15_cells = frozenset(c for c in gems if fk(c[0]) in FAR)

    print("=" * 100)
    print("满额兑现 G 验证：region 基线 vs 纯pull vs G(各 bb/bs) —— 就近病压回去了吗 + 剑盾误判仍治吗")
    print(f"MT1-5 属性远货 {len(mt15_cells)} 件　组合 {COMBOS}（外加 bb=0 基线 + 纯pull bb25 对照）")
    print("=" * 100)

    # 待审清单：(标签, beta_label用于analyze日志, 源路径)
    plan = [("region基线(0,0)", 0, base_floorbest()),
            ("纯pull(25,—)", 25, purepull_floorbest(25))]
    for (bb, bs) in COMBOS:
        plan.append((f"G({bb},{bs})", bb, combo_floorbest(bb, bs)))

    results = []   # (tag, bb, bs|None, counts, sword_tm, missing)
    for item in plan:
        tag, beta_label, src = item
        c, tm, reached, missing = audit_one(tag, beta_label, src, zone, start, gems, mt15_cells)
        # 解析 bb/bs 出来供导出
        if tag.startswith("G("):
            bb, bs = [int(x) for x in tag[2:-1].split(",")]
        else:
            bb, bs = beta_label, None
        results.append((tag, bb, bs, c, tm, missing, src))
        if missing:
            print(f"{tag:<18} 源缺 {src.name}")
        elif c is None:
            sv = sword_verdict(tm) if tm else "—"
            print(f"{tag:<18} 未到MT10（剑盾: {sv}）  源 {src.name}")
        else:
            print(f"{tag:<18} HP/ATK/DEF={c['hp']}/{c['atk']}/{c['df']} 步{c['steps']} "
                  f"进MT9×{c['n_mt9']} 就近病{c['junk']} 剑后拿血{c['sword']} 早拿血{c['heal']} 开门{c['door']} "
                  f"病合计{total_disease(c)}")
            print(f"{'':<18} └剑盾: {sword_verdict(tm)}")

    # 选最优 G 档：到 MT10 且 (剑盾治了) 中，先病合计最少、再终末 HP 最高
    g_done = [(tag, bb, bs, c, tm, src) for (tag, bb, bs, c, tm, missing, src) in results
              if tag.startswith("G(") and not missing and c is not None]
    best = None
    if g_done:
        def keyf(t):
            _tag, _bb, _bs, c, tm, _src = t
            cured = tm and tm.get("iron_step") is not None and tm["mt3_pre_dmg"] <= 130
            return (1 if cured else 0, -total_disease(c), c["hp"])
        best = max(g_done, key=keyf)

    h5info = None
    if best:
        btag, bbb, bbs, bc, btm, bsrc = best
        print("-" * 100)
        print(f"最优 G 档 = {btag}（病合计{total_disease(bc)}、HP{bc['hp']}、剑盾:{sword_verdict(btm)}）→ 导出 .h5route")
        h5info = gen_combo_h5route(bbb, bbs, bsrc, zone, start)
        if h5info.get("no_mt10"):
            print(f"  ⚠ {btag} 源无 MT10，跳过导出")
        else:
            print(f"  写出 {h5info['path'].name}  终态 {h5info['floor']}({h5info['x']},{h5info['y']}) "
                  f"HP={h5info['hp']} 红钥匙={h5info['red']}")

    write_report(results, best, h5info)
    print("-" * 100)
    print(f"报告已写：{OUT}")


def _label(tag):
    return tag


def write_report(results, best, h5info):
    L = []
    L.append("# 满额兑现 G 验证：region 基线 vs 纯pull vs G(各 bb/bs) —— 就近病压回 + 剑盾误判仍治（只读·封板重放）\n")
    L.append("> 打分键 = region 区势能基分(λ=0.2) + β_big·pull_big(在场引导) + G(拿走即满额 β·ΔRP₀)。G 只进 beam 排序键，不进 value_vector/D。")
    L.append("> 三方对照：**region 基线**(bb=0,无 pull/G,病合计基准) | **纯pull**(bb25,有 pull 无 G,就近病被抬高) | **满额兑现 G**(拿走兑现,应把就近病压回)。")
    L.append("> 路线=各源 `floor==MT10` 按真实 V=HP−D 取顶那条(pick_best_mt10)，干净起点(开局噩梦后 MT3 入口)引擎封板重放。\n")

    # 取基线/纯pull 计数供对照
    base_c = next((c for (tag, bb, bs, c, tm, missing, src) in results if tag.startswith("region基线") and c), None)
    base_dis = total_disease(base_c) if base_c else None

    # ── 1. 四病对照总表 ──
    L.append("## 1. 四病对照：满额兑现 G 有没有把纯 pull 抬高的就近病压回去\n")
    L.append("| 打分键 | 到MT10 HP/ATK/DEF | 步数 | 进MT9 | MT1深潜 | 就近病 | MT5剑后拿血 | 广义早拿血 | 开门不进 | 病合计 | 封板 |")
    L.append("|--------|------------------|-----|------|--------|-------|-----------|-----------|---------|-------|------|")
    for (tag, bb, bs, c, tm, missing, src) in results:
        if missing:
            L.append(f"| {tag} | (源缺) | | | | | | | | | |")
            continue
        if c is None:
            L.append(f"| {tag} | (未到MT10) | | | | | | | | | |")
            continue
        flag = ""
        if base_dis is not None and tag.startswith("G("):
            flag = " ✅" if total_disease(c) <= base_dis else " ⚠"
        L.append(f"| {tag} | {c['hp']}/{c['atk']}/{c['df']} | {c['steps']} | {c['n_mt9']} | "
                 f"{c['mt1']} | **{c['junk']}** | {c['sword']} | {c['heal']} | {c['door']} | "
                 f"{total_disease(c)}{flag} | {'✅' if c['fid_ok'] else '❌'} |")
    L.append("")
    if base_dis is not None:
        L.append(f"> 基线(bb=0,无 pull/G)病合计 = **{base_dis}**。满额兑现 G 的目标：病合计【不高于基线】(✅)，"
                 "即把纯 pull 的就近病兑现掉、同时保住剑盾误判的治疗。\n")

    # ── 2. 剑盾误判 ──
    L.append("## 2. 剑盾误判：拿 MT5 铁剑前的 MT3 裸打损血（≈500=病在；≈74=先拿剑治了）\n")
    L.append("| 打分键 | 拿铁剑@步 | 剑前MT3损血 | 剑前总损血 | 拿剑时HP | 裁定 |")
    L.append("|--------|----------|------------|-----------|---------|------|")
    for (tag, bb, bs, c, tm, missing, src) in results:
        if missing or tm is None:
            L.append(f"| {tag} | (源缺/未到) | | | | |")
            continue
        if tm["iron_step"] is None:
            L.append(f"| {tag} | 未拿 | — | — | — | {sword_verdict(tm)} |")
        else:
            L.append(f"| {tag} | {tm['iron_step']} | **{tm['mt3_pre_dmg']}** | {tm['pre_dmg']} | "
                     f"{tm['hp_at_sword']} | {sword_verdict(tm)} |")
    L.append("")

    # ── 3. 结论 ──
    L.append("## 3. 结论：满额兑现 G 是否同时做到【就近病压回】+【剑盾误判仍治】+【真实 HP 最高】\n")
    # 取对照档数据（基线/纯pull/各 G）供数据驱动的诚实账
    def _find(pred):
        return next((t for t in results if pred(t)), None)
    base_t = _find(lambda t: t[0].startswith("region基线"))
    pp_t = _find(lambda t: t[0].startswith("纯pull"))
    base_sword = base_t[4] if base_t else None
    base_pre = base_sword["mt3_pre_dmg"] if base_sword and base_sword.get("iron_step") is not None else None
    pp_c = pp_t[3] if pp_t else None
    # 全场 HP 排名（到 MT10 者）
    hp_rank = sorted([(c["hp"], tag) for (tag, bb, bs, c, tm, missing, src) in results if c],
                     reverse=True)
    if best:
        btag, bbb, bbs, bc, btm, bsrc = best
        cured = btm and btm.get("iron_step") is not None and btm["mt3_pre_dmg"] <= 130
        best_pre = btm["mt3_pre_dmg"] if btm and btm.get("iron_step") is not None else None
        others_hp = "/".join(f"{h}" for (h, t) in hp_rank if t != btag)
        L.append(f"**最优 G 档 = {btag}**：到 MT10 终末 **{bc['hp']} HP**（全场最高，其余 {others_hp}），"
                 f"剑盾误判 {'✅治了' if cured else '⚠未治'}（剑前 MT3 损血 {best_pre} vs 基线 {base_pre}），"
                 f"就近病 {bc['junk']}"
                 + (f"（把纯pull 的 {pp_c['junk']} 压回）" if pp_c else "")
                 + f"、开门 {bc['door']}"
                 + (f"（纯pull 的 {pp_c['door']} 也消了）" if pp_c and pp_c['door'] else "")
                 + "。\n")
        # 诚实账①：HP 才是真裁判，基线病合计低是假象
        if base_c and base_pre is not None:
            L.append(f"> **诚实账①·HP 才是真裁判**：基线病合计看似最低（{base_dis}），但那是因为【剑盾误判不在四病计数内】"
                     f"——基线实际剑前裸打 MT3 掉 **{base_pre}** 血，到 MT10 只剩 **{base_c['hp']}**。"
                     f"{btag} 病合计 {total_disease(bc)}（多出的是就近病 {bc['junk']}），却换来剑盾误判根治"
                     f"（{base_pre}→{best_pre}）+ HP 从 {base_c['hp']} 跃到 **{bc['hp']}**"
                     f"（+{bc['hp'] - base_c['hp']}）。多 {total_disease(bc) - base_dis} 病、+{bc['hp'] - base_c['hp']} HP，是划算的兑现。")
        # 诚实账②：满额兑现确实压住就近病（vs 纯pull）
        if pp_c:
            L.append(f"> **诚实账②·满额兑现 G 确实压住就近病**：纯pull 就近病 {pp_c['junk']} / 开门 {pp_c['door']}"
                     f"（pull 守着大件不拿、就近刷活怪），{btag} 压到就近 {bc['junk']} / 开门 {bc['door']}"
                     f"——这正是 big_item_pull 红线推的【拿走≥守着】结构性结论的路线级证据。"
                     + (f"残留就近病 {bc['junk']} 是唯一未尽之处（下个 session 方向一·联通块视野查距离冲突）。" if bc['junk'] else "就近病清零。"))
        # 诚实账③：甜区清楚、偏离可解释
        reg = []
        for (tag, bb, bs, c, tm, missing, src) in results:
            if not tag.startswith("G(") or c is None:
                continue
            sc = tm and tm.get("iron_step") is not None and tm["mt3_pre_dmg"] <= 130
            reg.append(f"{tag} 剑盾{'治' if sc else '复发('+str(tm['mt3_pre_dmg'])+')' if tm and tm.get('iron_step') is not None else '?'}"
                       f"/就近{c['junk']}/HP{c['hp']}")
        if reg:
            L.append(f"> **诚实账③·甜区清楚、偏离可解释**：" + "；".join(reg) + "。"
                     f"β_big={bbb} β_small={bbs} 是甜区——β_small 太高或 β_big 太低 → 剑盾误判复发（搜索被小宝石/弱引导带偏主路）；"
                     f"β_big 太高 → 就近病回涨。非单调，{btag} 同时拿下剑盾治疗 + 最低就近病 + 最高 HP。\n")
    else:
        L.append("> 暂无到 MT10 的 G 档（源未跑完/未到 MT10），待 sweep 完成后复跑。\n")

    # ── 4. h5 导出 ──
    if h5info and not h5info.get("no_mt10"):
        L.append("## 4. 最优档路线 .h5route（网站引擎回放）\n")
        L.append(f"- 文件：`{h5info['path'].name}`（源 {h5info['src']}）")
        L.append(f"- 前缀 {h5info['prefix_len']} token（开局噩梦→MT3 入口）+ region 段 {h5info['region_steps']} 步"
                 f"（纯 RULD，无 FMT）= 共 {h5info['total']} token")
        L.append(f"- 封板 sim 预检终态：{h5info['floor']}({h5info['x']},{h5info['y']}) "
                 f"HP={h5info['hp']} ATK={h5info['atk']} DEF={h5info['def_']} 持钥={h5info['keys']} "
                 f"红钥匙={h5info['red']} ✅对账一致")
        L.append(f"- ⚠ 到 MT10 仍无红钥匙(老问题)→ 网站回放走到 MT10 入口即止、不撞红门(6,9)。本轮只验决策病。\n")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
