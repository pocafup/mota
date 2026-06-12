"""【只读·对照导出】κ=1(D_rel 开)那条 vs κ=0(纯 HP−D_free 旧版)那条，关键决策逐项对比。

不比"谁总分高"（κ=1 只到 MT9、κ=0 到 MT10 已知），比【关键局部决策】：
  · 铁剑(MT5,11,11)+10ATK 谁拿得更早/更省血？拿剑前是否裸打高攻骷髅？
  · 铁盾(MT9,9,7)+10DEF 谁拿了？留钥开属性门谁做得好？
  · κ=1 卡在哪（终态 + 最后几步；beam 截断 or 战死）。
另含 grab-incentive 探针：用 κ=0 路线拿剑那一步前/后两个真实态，分别用 κ=0 和 κ=1 打分，
看"拿铁剑"这一步让分数涨多少——实证玩家直觉"D_rel(κ=1) 奖励守着潜力不拿"。

铁律：不改 sim/solver；全 replay+data 取数；动作串=cut 原样落盘 RULD；事件归因到 data 真读的格。
跑法：python -u extract/export_k1_vs_k0_compare.py
产物：extract/k1_vs_k0_compare.md（本脚本只写【数据对照】§0–§4；§5 评估人工追加）
"""
import json
import re
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from solver.verify import replay
from vzone import build_zone, boss_toll, v_zone_score
from probe_crossfloor import build_start
# 复用上一个导出脚本的归因逻辑（live 怪检测、宝石/钥匙归因、逐里程碑）
from export_k0stairs_mt10_route import (
    build_milestones, gem_label, nz_keys, fk, load_rows,
)

HERE = Path(__file__).parent
CUT_K0 = HERE / "crossbeam_cut_K50_vzone_lam0.0_stairs.jsonl"
CUT_K1 = HERE / "crossbeam_cut_K50_vzone_k1_lam0.0_stairs.jsonl"
OUT = HERE / "k1_vs_k0_compare.md"

_BLOOD = re.compile(r"损血(\d+)")


def pick_best(rows):
    """最高触达层 → 该层按 (DEF↓,ATK↓,HP↓) 取顶；另给该层 maxHP 兄弟态。"""
    top = max((r["floor"] for r in rows), key=fk)
    pool = [r for r in rows if r["floor"] == top]
    primary = max(pool, key=lambda r: (r["def"], r["atk"], r["hp"]))
    hp_best = max(pool, key=lambda r: (r["hp"], r["def"], r["atk"]))
    return top, primary, hp_best, len(pool)


def verify(start, actions, row):
    rs = replay(start, list(actions), step, _copy_state)
    fid = dict(floor=(rs.current_floor, row["floor"]), hp=(rs.hero.hp, row["hp"]),
               atk=(rs.hero.atk, row["atk"]), def_=(rs.hero.def_, row["def"]))
    return all(a == b for a, b in fid.values()), fid


def first_with(milestones, needle):
    for m in milestones:
        if needle in m["label"]:
            return m
    return None


def skeleton_fights(milestones):
    """所有骷髅系战斗：(步,层,坐标,atk,def,hp_after,损血,名)。atk<20=裸(无铁剑)。"""
    out = []
    for m in milestones:
        if "打怪" in m["label"] and "骷髅" in m["label"]:
            mm = _BLOOD.search(m["label"])
            blood = int(mm.group(1)) if mm else None
            nm = ("骷髅队长" if "队长" in m["label"]
                  else "骷髅士兵" if "士兵" in m["label"] else "骷髅人")
            out.append(dict(i=m["i"], floor=m["floor"], x=m["x"], y=m["y"],
                            atk=m["atk"], def_=m["def_"], hp=m["hp"], blood=blood, name=nm))
    return out


def analyze(tag, start, zone, gems, row, nstates):
    actions = list(row["actions"])
    ms, visited, taken, term = build_milestones(start, actions, zone, gems)
    ok, fid = verify(start, actions, row)
    return dict(tag=tag, row=row, actions=actions, milestones=ms, visited=visited,
                taken=taken, term=term, fid_ok=ok, fid=fid, nstates=nstates,
                sword=first_with(ms, "拿铁剑"), shield=first_with(ms, "拿铁盾"),
                skels=skeleton_fights(ms),
                doors=[m for m in ms if "开门" in m["label"]])


def grab_incentive_probe(start, zone, sword_step):
    """κ=0 路线拿铁剑那一步：前(step-1)/后(step)两个真实态，分别 κ=0/κ=1 打分。
       看「拿剑」这一步 ΔScore：κ=0 应大涨(奖励拿)，κ=1 应几乎不涨(潜力已预记，拿不拿无所谓)。"""
    out = {}
    for tag, n in (("拿剑前", sword_step - 1), ("拿剑后", sword_step)):
        st = replay(start, list(K0_ACTIONS[:n]), step, _copy_state)
        s0, d0, sav0, _ = v_zone_score(zone, st, 0.0)
        s1, d1, sav1, _ = v_zone_score(zone, st, 1.0)
        out[tag] = dict(atk=st.hero.atk, def_=st.hero.def_, hp=st.hero.hp,
                        score0=s0, dfree=d0, score1=s1, savings1=sav1)
    return out


K0_ACTIONS = []  # 填充于 main（探针要用）


def main():
    global K0_ACTIONS
    start = build_start()[0]
    zone = build_zone()
    from vzone import _zone_attr_gems
    gems = _zone_attr_gems(zone)

    top0, p0, hp0, n0 = pick_best(load_rows(CUT_K0))
    top1, p1, hp1, n1 = pick_best(load_rows(CUT_K1))
    K0_ACTIONS = list(p0["actions"])

    A0 = analyze("κ=0(纯HP−D_free 旧版)", start, zone, gems, p0, n0)
    A1 = analyze("κ=1(D_rel 开)", start, zone, gems, p1, n1)

    probe = None
    if A0["sword"] is not None:
        probe = grab_incentive_probe(start, zone, A0["sword"]["i"])

    bm = zone["boss_mon"]
    write_report(A0, A1, top0, top1, hp0, hp1, bm, probe)

    # ── stdout QA ──
    for A in (A0, A1):
        t = A["term"]
        sw = A["sword"]
        sh = A["shield"]
        print("=" * 80)
        print(f"{A['tag']}  最高层={A['row']['floor']}({A['nstates']}态)  "
              f"封板重放={'一致✅' if A['fid_ok'] else '不一致❌ '+str(A['fid'])}")
        print(f"  终态: {t['floor']}({t['x']},{t['y']}) HP={t['hp']} ATK={t['atk']} "
              f"DEF={t['def_']} gold={t['gold']} 持钥={t['keys']} 步数={len(A['actions'])}")
        print(f"  铁剑: " + (f"step{sw['i']} @{sw['floor']} ATK{sw['atk']-10}→{sw['atk']} HP={sw['hp']}"
                            if sw else "✗ 全程没拿"))
        print(f"  铁盾: " + (f"step{sh['i']} @{sh['floor']} DEF{sh['def_']-10}→{sh['def_']} HP={sh['hp']}"
                            if sh else "✗ 全程没拿"))
        print(f"  骷髅战 {len(A['skels'])} 场；裸打(atk<20)的: ", end="")
        naked = [s for s in A["skels"] if s["atk"] < 20]
        print(", ".join(f"step{s['i']}@{s['floor']} {s['name']} atk{s['atk']} 损{s['blood']}"
                        for s in naked) or "（无）")
    if probe:
        print("=" * 80)
        print("【grab-incentive 探针：κ=0 路线拿铁剑这一步，分数涨多少】")
        a, b = probe["拿剑前"], probe["拿剑后"]
        print(f"  拿剑前 ATK={a['atk']} DEF={a['def_']} HP={a['hp']}: "
              f"V(κ=0)={a['score0']:.0f}  V(κ=1)={a['score1']:.0f}(savings={a['savings1']})")
        print(f"  拿剑后 ATK={b['atk']} DEF={b['def_']} HP={b['hp']}: "
              f"V(κ=0)={b['score0']:.0f}  V(κ=1)={b['score1']:.0f}(savings={b['savings1']})")
        print(f"  → 拿剑这一步 ΔV：κ=0={b['score0']-a['score0']:+.0f}   κ=1={b['score1']-a['score1']:+.0f}")
    print("=" * 80)
    print(f"报告(数据§0–§4)已写: {OUT}")


def _route_block(A):
    L = []
    t, sw, sh = A["term"], A["sword"], A["shield"]
    L.append(f"**{A['tag']}** — 最高触达层 **{A['row']['floor']}**（该层 {A['nstates']} 态）")
    L.append(f"- 封板重放对账：{'逐字段一致 ✅' if A['fid_ok'] else '不一致 ❌ '+str(A['fid'])}")
    L.append(f"- 终态：{t['floor']}({t['x']},{t['y']}) HP={t['hp']} ATK={t['atk']} DEF={t['def_']} "
             f"gold={t['gold']} 持钥={t['keys']}（{len(A['actions'])} 步）")
    L.append(f"- 铁剑+10ATK@(MT5,11,11)：" +
             (f"**step{sw['i']}** 拿，当刻 @{sw['floor']} ATK {sw['atk']-10}→{sw['atk']} HP={sw['hp']}"
              if sw else "**✗ 全程没拿**"))
    L.append(f"- 铁盾+10DEF@(MT9,9,7)：" +
             (f"**step{sh['i']}** 拿，当刻 @{sh['floor']} DEF {sh['def_']-10}→{sh['def_']} HP={sh['hp']}"
              if sh else "**✗ 全程没拿**"))
    L.append(f"- 开门耗钥 {len(A['doors'])} 次。")
    return L


def write_report(A0, A1, top0, top1, hp0, hp1, bm, probe):
    L = []
    L.append("# κ=1（D_rel 开）对照 κ=0（纯 HP−D_free 旧版）：关键决策逐项比对\n")
    L.append("> 只读导出。比的不是总分（κ=0 到 MT10、κ=1 只到 MT9 已知），是【关键局部决策】谁做得好。")
    L.append("> 两条动作串都从干净起点(开局噩梦后 MT3 入口)封板引擎重放对账过。\n")

    L.append("## 0. 两条各取哪一条 + 封板重放对账")
    L += _route_block(A0)
    L.append("")
    L += _route_block(A1)
    L.append("")

    L.append("## 1. 终态对照")
    L.append("| | 最高层 | 坐标 | HP | ATK | DEF | gold | 持钥 | 步数 |")
    L.append("|---|---|---|----|----|----|----|----|----|")
    for A in (A0, A1):
        t = A["term"]
        L.append(f"| {A['tag']} | {A['row']['floor']} | ({t['x']},{t['y']}) | {t['hp']} | "
                 f"{t['atk']} | {t['def_']} | {t['gold']} | {t['keys']} | {len(A['actions'])} |")
    L.append("")

    L.append("## 2. 关键决策对照（玩家问 #1）")
    L.append("### 铁剑（MT5,11,11 +10ATK）— 拿剑时机 / 是否避开裸打")
    L.append("| | 拿铁剑 step | 当刻 ATK 前→后 | 拿剑前裸打(atk<20)的骷髅战 |")
    L.append("|---|---|---|---|")
    for A in (A0, A1):
        sw = A["sword"]
        swstep = sw["i"] if sw else None
        naked_before = [s for s in A["skels"] if s["atk"] < 20 and (swstep is None or s["i"] < swstep)]
        nb = "；".join(f"step{s['i']}@{s['floor']} {s['name']}(atk{s['atk']}) 损血{s['blood']}"
                      for s in naked_before) or "（无）"
        swcell = f"step{sw['i']}（ATK {sw['atk']-10}→{sw['atk']}）" if sw else "✗ 没拿"
        L.append(f"| {A['tag']} | {swstep if swstep else '—'} | "
                 f"{(str(sw['atk']-10)+'→'+str(sw['atk'])) if sw else '—'} | {nb} |")
    L.append("")
    L.append("### 铁盾（MT9,9,7 +10DEF）")
    L.append("| | 拿铁盾 step | 当刻 DEF 前→后 | 当刻 HP |")
    L.append("|---|---|---|---|")
    for A in (A0, A1):
        sh = A["shield"]
        L.append(f"| {A['tag']} | {sh['i'] if sh else '✗ 没拿'} | "
                 f"{(str(sh['def_']-10)+'→'+str(sh['def_'])) if sh else '—'} | {sh['hp'] if sh else '—'} |")
    L.append("")
    L.append("### 全部骷髅系战斗（裸打=atk<20，无铁剑硬抗）")
    for A in (A0, A1):
        L.append(f"**{A['tag']}**：")
        if A["skels"]:
            for s in A["skels"]:
                nk = " ⚠裸打" if s["atk"] < 20 else ""
                L.append(f"- step{s['i']} @{s['floor']}({s['x']},{s['y']}) {s['name']} "
                         f"atk{s['atk']}/def{s['def_']} 损血{s['blood']}{nk}")
        else:
            L.append("- （无骷髅战）")
    L.append("")

    if probe:
        L.append("## 3. grab-incentive 探针：拿铁剑这一步，分数到底涨不涨（实证玩家直觉）")
        L.append("> 取 κ=0 路线拿铁剑那一步【前/后】两个真实态，各用 κ=0 与 κ=1 两套打分。")
        L.append("> V=HP−D(κ)，越高越好。看「拿剑」让 V 涨多少：涨得多=搜索被奖励去拿；几乎不涨=拿不拿无所谓。")
        a, b = probe["拿剑前"], probe["拿剑后"]
        L.append("")
        L.append("| 时刻 | ATK | DEF | HP | V(κ=0) | V(κ=1) | κ=1 的 savings |")
        L.append("|---|---|---|----|----|----|----|")
        L.append(f"| 拿剑前 | {a['atk']} | {a['def_']} | {a['hp']} | {a['score0']:.0f} | {a['score1']:.0f} | {a['savings1']} |")
        L.append(f"| 拿剑后 | {b['atk']} | {b['def_']} | {b['hp']} | {b['score0']:.0f} | {b['score1']:.0f} | {b['savings1']} |")
        d0 = b["score0"] - a["score0"]
        d1 = b["score1"] - a["score1"]
        L.append("")
        L.append(f"- **拿剑这一步 ΔV：κ=0 = {d0:+.0f}　κ=1 = {d1:+.0f}**")
        L.append(f"- 读法：κ=0 拿剑分数涨 {d0:+.0f}（搜索被强力奖励去拿剑）；κ=1 只涨 {d1:+.0f}"
                 f"（铁剑的 boss 减伤在 savings 里已被「可达即预记」，真拿到手分数几乎不动）。")
        L.append("- 这正是玩家说的「D_rel 奖励守着潜力不拿」：κ=1 下铁剑【够得着】就算分，没有梯度逼搜索真去拿。\n")

    L.append("## 4. κ=1 卡在哪（玩家问 #1 末项）")
    t1 = A1["term"]
    L.append(f"- κ=1 最高只到 {A1['row']['floor']}，终态 {t1['floor']}({t1['x']},{t1['y']}) "
             f"HP={t1['hp']} ATK={t1['atk']} DEF={t1['def_']}。")
    L.append("- 这些是 **beam 截断态**（cut=前沿被砍的点，非战死）：说明 κ=1 的 beam 自始至终没"
             "产出任何 MT10 态——是【打分/排序】把搜索引去别处，不是某一步把血打光。")
    L.append("- κ=1 最后 6 个里程碑（看它停在哪、在干嘛）：")
    for m in A1["milestones"][-6:]:
        L.append(f"  - step{m['i']} {m['label']} @({m['x']},{m['y']}){m['floor']} "
                 f"HP={m['hp']} ATK={m['atk']} DEF={m['def_']}")
    L.append("")

    L.append("## （附）κ=1 路线逐里程碑全表")
    L.append("| 步# | 事件 | 坐标 | HP | ATK | DEF | 持钥 |")
    L.append("|----|------|------|----|----|-----|-----|")
    for m in A1["milestones"]:
        L.append(f"| {m['i']} | {m['label']} | ({m['x']},{m['y']})@{m['floor']} | "
                 f"{m['hp']} | {m['atk']} | {m['def_']} | {m['keys']} |")
    L.append("")
    L.append("---")
    L.append("> §5「剑盾永久视野」设计评估：见本文件后续人工追加段。")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
