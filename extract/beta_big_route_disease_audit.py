"""【结合验证·只读·不改产品码】β_big 扫描({4,10,25,60}) best-MT10 路线，用【同一套病判据】
   对照【纯 region λ=0.2 基线(bb=0,无大件 pull)】——核心验【剑盾误判治没治】+ 小宝石/血没被搞坏 + β_big 甜区。

打分键 = region 区势能基分(λ=0.2，beam.py/quotient.py 默认) + β_big·pull_big(大件引导，extract/big_item_pull)。
源 = crossbeam_floorbest_K200_bb{bb}_lam0.2_stairs.jsonl（probe --score region --beta-big bb --lam 0.2 --beam 200
     --diversity stairs 的各层最优 Pareto 落盘）。bb=0 基线 = crossbeam_floorbest_K200_lam0.2_stairs.jsonl（无 pull）。
复用 export_beta_route_disease_audit.analyze(cut_fn=) 的四病判据(就近病/MT5剑后拿血/广义早拿血/开门不进)，apples-to-apples。

【核心·剑盾误判】玩家口径：MT3 裸打小蝙蝠+骷髅(384+112≈500 血) vs 先去 MT5 拿铁剑(大件 pull 拉去)再回打(伤害大降)。
量化 = 拿到 MT5 铁剑(+10atk)那步 iron_step + 拿剑【之前】的 MT3 累计损血(mt3_pre_dmg)。
  · mt3_pre_dmg ≈ 500 → 仍先裸打 MT3（病在）；≈ 0 → 先上 MT5 拿剑（病治了）。bb=0 vs bb>0 落差 = 大件 pull 的边际疗效。

甜区 = 最小的 bb，使【剑盾误判治了(mt3_pre_dmg 低) + 就近病/早拿血没变差 + 终末 HP 没崩】。最优 bb 路线导出 .h5route。

跑法：python -u extract/beta_big_route_disease_audit.py
产物：extract/beta_big_route_disease_audit.md + beta_big{bb}_lam0.2_mt10_route.h5route（甜区）
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
from export_k0stairs_mt10_route import fk, build_milestones
from export_bscan_routes import load_rows, pick_best_mt10
from export_beta_route_disease_audit import analyze, _count_mt1_dives, FAR
from export_mt10_boss_route import load_tokens
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META

HERE = Path(__file__).parent
OUT = HERE / "beta_big_route_disease_audit.md"
LAM = 0.2                       # 结合：区势能基分固定 λ=0.2
BB_LIST = [4, 10, 25, 60]       # 扫描的 β_big
K = 200


def bb_floorbest(bb):
    """bb>0 → β_big floorbest；bb==0 → 纯 region λ0.2 floorbest（无大件 pull，基线）。"""
    if bb == 0:
        return HERE / f"crossbeam_floorbest_K{K}_lam{LAM}_stairs.jsonl"
    return HERE / f"crossbeam_floorbest_K{K}_bb{bb}_lam{LAM}_stairs.jsonl"


def dcounts(o):
    """从 analyze 结果取四病计数 + 终态 + 规模标量。未到 MT10/缺文件 → None。"""
    if o.get("missing") or o.get("no_mt10"):
        return None
    d, t = o["dis"], o["term"]
    return dict(junk=len(d["junk_kill"]), sword=len(d["hp_after_sword"]),
                heal=len(d["early_heal"]), door=len(d["door_noenter"]),
                wasted=d["wasted_hp"], fight=d["fight_hp"],
                hp=t["hp"], atk=t["atk"], df=t["df"], steps=o["n_steps"],
                n_mt9=o["n_mt9"], mt1=_count_mt1_dives(o), fid_ok=o["fid_ok"])


def total_disease(c):
    return c["junk"] + c["sword"] + c["heal"] + c["door"]


def pick_sweet(rows, sword):
    """甜区 = 在【治了剑盾误判(剑前MT3损血≤130)且早拿剑(iron_step≤130)】的 pull 档里，终末 HP 最高、
    就近病最少者。⚠ 所有 bb>0 都比基线(bb=0,无pull)病多 → 甜区只是【最不亏的 pull 档】，非『优于不加 pull』。"""
    early = [(bb, rows[bb], sword[bb]) for bb in BB_LIST
             if rows.get(bb) and sword.get(bb) and sword[bb]["iron_step"] is not None
             and sword[bb]["mt3_pre_dmg"] <= 130 and sword[bb]["iron_step"] <= 130]
    if not early:                                  # 放宽：只要治了剑盾误判(不论早晚)
        early = [(bb, rows[bb], sword[bb]) for bb in BB_LIST
                 if rows.get(bb) and sword.get(bb) and sword[bb]["iron_step"] is not None
                 and sword[bb]["mt3_pre_dmg"] <= 130]
    if not early:
        return None
    return max(early, key=lambda t: (t[1]["hp"], -t[1]["junk"], -total_disease(t[1])))


# ── 核心：剑盾误判量化 = 拿 MT5 铁剑那步 + 拿剑前 MT3 累计损血 ───────────────────
def best_route_actions(zone, start, src):
    """取 best-MT10 动作串（同 analyze/pick_best_mt10 口径）；无 MT10 则回退到达最深层的最高 HP 行。"""
    rows = load_rows(src)
    if not rows:
        return None, None, False
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if mt10:
        best, _s, _vz, _D = pick_best_mt10(zone, start, mt10)
        return list(best["actions"]), best, True
    deepest = max(rows, key=lambda r: (fk(r["floor"]) if str(r["floor"]).startswith("MT") else -1, r["hp"]))
    return list(deepest["actions"]), deepest, False


def sword_timing(zone, start, actions, gems):
    """逐步重放，定位 MT5 铁剑(+10atk)拿取步 + 量化拿剑【之前】的 MT3 累计损血（剑盾误判核心信号）。"""
    s = _copy_state(start)
    hp, flo = [s.hero.hp], [s.current_floor]
    for a in actions:
        s = step(s, a)
        hp.append(s.hero.hp)
        flo.append(s.current_floor)
    milestones, _v, _t, _term = build_milestones(start, actions, zone, gems)
    iron_step = None
    for m in milestones:
        c = (m["floor"], m["x"], m["y"])
        if c in gems and gems[c][0] >= 10 and m["floor"] == "MT5":
            iron_step = m["i"]
            break
    if iron_step is None:                       # 全程没拿剑
        mt3_total = sum(max(0, hp[j - 1] - hp[j]) for j in range(1, len(hp)) if flo[j - 1] == "MT3")
        return dict(iron_step=None, pre_dmg=None, mt3_pre_dmg=None, hp_at_sword=None,
                    mt3_total_dmg=mt3_total, final_hp=hp[-1])
    pre_dmg = sum(max(0, hp[j - 1] - hp[j]) for j in range(1, iron_step + 1))
    mt3_pre_dmg = sum(max(0, hp[j - 1] - hp[j]) for j in range(1, iron_step + 1) if flo[j - 1] == "MT3")
    return dict(iron_step=iron_step, pre_dmg=pre_dmg, mt3_pre_dmg=mt3_pre_dmg,
                hp_at_sword=hp[iron_step], mt3_total_dmg=None, final_hp=hp[-1])


def sword_verdict(tm):
    """剑盾误判裁定（以拿剑前 MT3 损血为主信号；~500=病在 384+112，~0=先拿剑治了）。"""
    if tm["iron_step"] is None:
        return f"✗全程未拿MT5铁剑（MT3总损血{tm['mt3_total_dmg']}）"
    d = tm["mt3_pre_dmg"]
    if d <= 130:
        flag = "✅先拿剑后再打"
    elif d <= 350:
        flag = "△剑前打了部分MT3"
    else:
        flag = "⚠剑前裸打MT3(病在)"
    return f"{flag} 剑@步{tm['iron_step']}(剑前MT3损血{d}/剑前总损血{tm['pre_dmg']}/拿剑时HP{tm['hp_at_sword']})"


# ── 甜区 bb 的 best-MT10 → .h5route（镜像 gen_region_h5route）─────────────────────
def gen_bb_h5route(bb, zone, start):
    src = bb_floorbest(bb)
    rows = load_rows(src)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        return dict(bb=bb, no_mt10=True, src=src.name)
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

    out_path = Path(__file__).resolve().parent.parent / f"beta_big{bb}_lam{LAM:g}_mt10_route.h5route"
    write_h5route(out_path, spliced, DEFAULT_META)
    held = {k: v for k, v in h.keys.items() if v}
    return dict(bb=bb, path=out_path, prefix_len=len(prefix), region_steps=len(region_actions),
                total=len(spliced), floor=fin.current_floor, x=h.x, y=h.y,
                hp=h.hp, atk=h.atk, def_=h.def_, keys=held,
                red=h.keys.get("redKey", 0), margin_seen=h.hp - D, src=src.name)


def label(bb):
    return "region λ0.2 基线(bb=0,无pull)" if bb == 0 else f"β_big={bb}"


def write_report(rows, sword, h5info):
    L = []
    L.append("# β_big 扫描验证：结合(region λ0.2 + β_big·pull_大件) —— 剑盾误判治没治 + 小宝石/血没搞坏 + 甜区（只读·封板重放）\n")
    L.append("> 打分键=region 区势能基分(λ=0.2，beam.py/quotient.py 默认) + β_big·pull_big(大件引导，只进排序键不进 value_vector/D)。")
    L.append("> bb=0 = 纯 region λ0.2(无大件 pull)基线；bb>0 = 加大件 pull。同一套病判据(export_beta_route_disease_audit.analyze)。")
    L.append("> 路线=各源 `floor==MT10` 按真实 V=HP−D 取顶那条(pick_best_mt10)，干净起点(开局噩梦后 MT3 入口)引擎封板重放。\n")

    # ── 1. 剑盾误判（核心） ──
    L.append("## 1. 【核心】剑盾误判治没治：拿 MT5 铁剑前的 MT3 裸打损血\n")
    L.append("> 玩家病征：MT3 裸打小蝙蝠+骷髅 384+112≈500 血，不先去 MT5 拿铁剑(+10atk)。")
    L.append("> 量化=拿铁剑那步 `iron_step` + 拿剑【之前】的 MT3 累计损血 `mt3_pre_dmg`。**≈500=病在；≈0=先拿剑治了。**\n")
    L.append("| 打分键 | 到MT10 HP/ATK/DEF | 拿铁剑@步 | 剑前MT3损血 | 剑前总损血 | 拿剑时HP | 裁定 |")
    L.append("|--------|------------------|----------|------------|-----------|---------|------|")
    for bb in [0] + BB_LIST:
        tm = sword.get(bb)
        if tm is None:
            L.append(f"| {label(bb)} | (源缺/未到MT10) | | | | | |")
            continue
        c = rows.get(bb)
        hpd = f"{c['hp']}/{c['atk']}/{c['df']}" if c else "(未到MT10)"
        if tm["iron_step"] is None:
            L.append(f"| {label(bb)} | {hpd} | 未拿 | — | — | — | {sword_verdict(tm)} |")
        else:
            L.append(f"| {label(bb)} | {hpd} | {tm['iron_step']} | **{tm['mt3_pre_dmg']}** | "
                     f"{tm['pre_dmg']} | {tm['hp_at_sword']} | {sword_verdict(tm)} |")
    L.append("")
    base_tm = sword.get(0)
    if base_tm and base_tm["iron_step"] is not None:
        L.append(f"> 基线(bb=0 纯 region)剑前 MT3 损血 = **{base_tm['mt3_pre_dmg']}**。"
                 "大件 pull 的边际疗效 = 各 bb 把这个数压低多少（压到 ~0 = pull 把『先拿剑』拉成了主路）。\n")

    # ── 2. 四病对照（小宝石/血没搞坏？） ──
    L.append("## 2. 四病对照：加大件 pull 后，小宝石/血决策有没有被搞坏\n")
    L.append("| 打分键 | 到MT10 HP/ATK/DEF | 步数 | 进MT9次 | MT1深潜 | 就近病 | MT5剑后拿血 | 广义早拿血 | 开门不进 | 病合计 | 封板 |")
    L.append("|--------|------------------|-----|--------|--------|-------|-----------|-----------|---------|-------|------|")
    for bb in [0] + BB_LIST:
        c = rows.get(bb)
        if c is None:
            L.append(f"| {label(bb)} | (源缺/未到MT10) | | | | | | | | | |")
            continue
        L.append(f"| {label(bb)} | {c['hp']}/{c['atk']}/{c['df']} | {c['steps']} | {c['n_mt9']} | "
                 f"{c['mt1']} | **{c['junk']}** | **{c['sword']}** | **{c['heal']}** | {c['door']} | "
                 f"{total_disease(c)} | {'✅' if c['fid_ok'] else '❌'} |")
    L.append("")
    base_c = rows.get(0)
    if base_c:
        L.append(f"> 基线(bb=0)四病：就近{base_c['junk']}/剑后{base_c['sword']}/早拿血{base_c['heal']}/开门{base_c['door']}"
                 f"（合计{total_disease(base_c)}）。加 pull 后这些【不应变高】(变高=大件 pull 副作用搞坏了小宝石/血决策)。\n")

    # ── 3. 甜区（诚实：剑盾误判每档都治，但没有 β 优于不加 pull）──
    L.append("## 3. β_big 甜区：哪个 pull 档最不亏（⚠ 没有 β 在病合计上优于不加 pull）\n")
    base_dis = total_disease(base_c) if base_c else None
    base_tm = sword.get(0)
    base_pre = base_tm["mt3_pre_dmg"] if base_tm and base_tm.get("iron_step") is not None else None
    L.append(f"> **诚实结论①·剑盾误判全治**：bb>0 每档剑前 MT3 损血都从基线 {base_pre} 压到 ~74"
             "（pull 把『先去 MT5 拿铁剑』拉成主路），名义病征消除。")
    L.append(f"> **诚实结论②·但加 pull 一律抬高病合计**：基线(bb=0)病合计 {base_dis}，bb>0 全部更高"
             "（主要是就近病 0→3~6）。**没有任一 β 在病合计上做到不差于纯 region 基线。**")
    parts = [f"bb{bb}:HP{rows[bb]['hp']}/就近{rows[bb]['junk']}/病合计{total_disease(rows[bb])}"
             for bb in BB_LIST if rows.get(bb)]
    if parts:
        L.append("> **诚实结论③·代价非单调**（" + "；".join(parts) + "）："
                 "低档 pull 反把 HP 打崩、就近病更多，高档回血——并非『β 越小越好』。\n")
    sweet = pick_sweet(rows, sword)
    if sweet:
        sb, sc, stm = sweet
        L.append(f"**最不亏的 pull 档 = β_big={sb}**：治了剑盾误判（剑前 MT3 损血 {stm['mt3_pre_dmg']}、"
                 f"早拿剑@步{stm['iron_step']}），在治好的档里终末 HP 最高（{sc['hp']}HP/{sc['atk']}ATK/{sc['df']}DEF）、"
                 f"就近病最少（{sc['junk']}），但病合计 {total_disease(sc)} 仍 "
                 f"{'>' if base_dis is not None and total_disease(sc) > base_dis else '≤'} 基线 {base_dis}。")
        L.append("> ⚠ 这**不是**『推荐加 pull』，而是在『要加 pull』前提下挑副作用最小的档。"
                 "是否值得用『升高的就近病』换『治好的剑盾误判』，由你定夺（铁律：策略取舍归玩家，求解器不预设）。\n")
    else:
        L.append("**甜区：** 无 bb 治好剑盾误判（剑前 MT3 损血均偏高），待复核。\n")

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
    print("β_big 扫描验证：结合(region λ0.2 + β_big·pull_大件) —— 剑盾误判 + 小宝石/血 + 甜区")
    print(f"MT1-5 属性远货 {len(mt15_cells)} 件　bb 列表 {BB_LIST}（含 bb=0 纯 region 基线）")
    print("=" * 96)

    rows, sword = {}, {}
    for bb in [0] + BB_LIST:
        src = bb_floorbest(bb)
        if not src.exists():
            print(f"{label(bb):<28} 源缺 {src.name}")
            continue
        o = analyze(bb, zone, start, gems, mt15_cells, cut_fn=src)
        c = dcounts(o)
        rows[bb] = c
        actions, _best, reached = best_route_actions(zone, start, src)
        tm = sword_timing(zone, start, actions, gems) if actions else None
        sword[bb] = tm
        if c is None:
            sv = sword_verdict(tm) if tm else "—"
            print(f"{label(bb):<28} 未到MT10（剑盾: {sv}）  源 {src.name}")
        else:
            print(f"{label(bb):<28} HP/ATK/DEF={c['hp']}/{c['atk']}/{c['df']} 步{c['steps']} "
                  f"进MT9×{c['n_mt9']} 就近病{c['junk']} 剑后拿血{c['sword']} 早拿血{c['heal']} 开门{c['door']}")
            print(f"{'':<28} └剑盾: {sword_verdict(tm)}")

    # 甜区 + 导出（pick_sweet：治剑盾误判的档里挑终末 HP 最高/就近病最少；⚠ 仍劣于不加 pull）
    sweet = pick_sweet(rows, sword)
    h5info = None
    if sweet:
        sweet_bb = sweet[0]
        base_dis = total_disease(rows[0]) if rows.get(0) else None
        print("-" * 96)
        print(f"最不亏 pull 档 β_big={sweet_bb}（治剑盾误判、副作用最小；⚠ 病合计仍>基线{base_dis}，无 β 优于不加 pull）→ 导出 .h5route")
        h5info = gen_bb_h5route(sweet_bb, zone, start)
        if h5info.get("no_mt10"):
            print(f"  ⚠ bb={sweet_bb} 源无 MT10，跳过导出")
        else:
            print(f"  写出 {h5info['path'].name}  终态 {h5info['floor']}({h5info['x']},{h5info['y']}) "
                  f"HP={h5info['hp']} 红钥匙={h5info['red']}")

    write_report(rows, sword, h5info)
    print("-" * 96)
    print(f"报告已写：{OUT}")


if __name__ == "__main__":
    main()
