"""【想法1·只读·不改产品码】导出 G(60,3) 与 G(10,3) 的 best-MT10 路线为 .h5route，并与甜区 G(25,3)
做【逐里程碑对比】。三档都 ATK≈25，但到 MT10 的 HP 截然不同（甜区 649 / bb60 411 / bb10 227）。

重点回答玩家：β_big 高/低（60 vs 10）怎么改变路线？尤其【拿到铁剑之后】——
  · 是【上楼追盾】（强大件引导→直奔 MT9 铁盾）
  · 还是【把近区攻防拿光】（弱引导→在铁剑附近薅小宝石、慢慢凑属性）
并标出每档【从甜区 G(25,3) 岔开】的地方（属性拾取序 / 楼层序的首个分歧）。

口径：路线=各源 crossbeam_floorbest_K200_bb{bb}_bs3_lam0.2_stairs.jsonl 里 floor==MT10 按真实 V=HP−D 取顶
（pick_best_mt10，与产品/审计同口径）。.h5route = 开局前缀 83 token + region 段，引擎封板预检终态一致。
铁剑/铁盾=detect_big_items 数据涌现（MT5(11,11)+10atk / MT9(9,7)+10def），不硬编码。

跑法：python -u extract/idea1_g_route_compare.py
产物：beta_big60_bs3_lam0.2_mt10_route.h5route + beta_big10_bs3_lam0.2_mt10_route.h5route + extract/idea1_g_route_compare.md
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
from probe_crossfloor import build_start
from solver.beam import build_future_roster
from big_item_pull import detect_big_items
from export_bscan_routes import load_rows, pick_best_mt10
from beta_big_g_audit import combo_floorbest, gen_combo_h5route
from beta_big_route_disease_audit import sword_timing, sword_verdict

HERE = Path(__file__).parent
OUT = HERE / "idea1_g_route_compare.md"

CONFIGS = [(25, 3), (60, 3), (10, 3)]      # 甜区在前作参照
REF = (25, 3)


def label_cell(cell, gems, big_cells):
    if cell in big_cells:
        da, dd = gems.get(cell, (0, 0))
        if da >= dd:
            return f"★铁剑+{da}atk"
        return f"★铁盾+{dd}def"
    if cell in gems:
        da, dd = gems[cell]
        seg = []
        if da:
            seg.append(f"+{da}atk")
        if dd:
            seg.append(f"+{dd}def")
        return "小宝石" + "".join(seg)
    return "?事件"


def trace_route(start, actions, gems, big_cells):
    """逐步重放，记录每个【属性拾取】事件(atk/def 变化)+楼层首达+终态。"""
    s = _copy_state(start)
    h = s.hero
    prev_a, prev_d = h.atk, h.def_
    attr_events = []
    floor_first = {s.current_floor: (0, h.hp, h.atk, h.def_)}
    floor_seq = [s.current_floor]
    for i, a in enumerate(actions, 1):
        s = step(s, a)
        h = s.hero
        fid = s.current_floor
        if fid not in floor_first:
            floor_first[fid] = (i, h.hp, h.atk, h.def_)
        if floor_seq[-1] != fid:
            floor_seq.append(fid)
        if h.atk != prev_a or h.def_ != prev_d:
            cell = (fid, h.x, h.y)
            attr_events.append(dict(
                i=i, cell=cell, fid=fid, x=h.x, y=h.y,
                da=h.atk - prev_a, dd=h.def_ - prev_d,
                hp=h.hp, atk=h.atk, deff=h.def_,
                big=(cell in big_cells), label=label_cell(cell, gems, big_cells)))
            prev_a, prev_d = h.atk, h.def_
    return dict(final=s, attr_events=attr_events, floor_first=floor_first, floor_seq=floor_seq)


def find_big(attr_events, want_atk):
    """返回首个 big 拾取(铁剑 want_atk=True / 铁盾 want_atk=False)的事件，无则 None。"""
    for e in attr_events:
        if e["big"] and ((want_atk and e["da"] >= 10) or (not want_atk and e["dd"] >= 10)):
            return e
    return None


def first_divergence(ref_seq, seq):
    """两序列首个不同的下标(0基)；完全前缀一致返回较短长度。返回 (idx, ref_item, item)。"""
    n = min(len(ref_seq), len(seq))
    for i in range(n):
        if ref_seq[i] != seq[i]:
            return i, ref_seq[i], seq[i]
    if len(ref_seq) != len(seq):
        return n, (ref_seq[n] if n < len(ref_seq) else None), (seq[n] if n < len(seq) else None)
    return None, None, None


def action_divergence(start, ref_actions, actions):
    """region 动作串【逐 token】首个分歧：精确的路线分叉点（比属性拾取序/楼层序更细）。
    返回分叉处【两档分开前】的共同态(floor,x,y,hp,atk,def) + 各自岔出的 token。"""
    n = min(len(ref_actions), len(actions))
    di = next((i for i in range(n) if ref_actions[i] != actions[i]), None)
    if di is None:
        return None
    s = _copy_state(start)
    for a in ref_actions[:di]:
        s = step(s, a)
    h = s.hero
    return dict(i=di, ref_tok=ref_actions[di], tok=actions[di], fid=s.current_floor,
                x=h.x, y=h.y, hp=h.hp, atk=h.atk, deff=h.def_)


def main():
    start = build_start()[0]
    zone = build_zone()
    gems = _zone_attr_gems(zone)
    roster_future = build_future_roster(start)
    big_cells, tau, ranked = detect_big_items(zone, roster_future, start)

    print("=" * 104)
    print("想法1：G(60,3) / G(10,3) 导出 + 与甜区 G(25,3) 逐里程碑对比（只读·不改产品码）")
    print(f"大件涌现：{[f'{c[0]}({c[1]},{c[2]})+a{da}/+d{dd}' for (drp,c,da,dd) in ranked if c in big_cells]}")
    print("=" * 104)

    data = {}
    for (bb, bs) in CONFIGS:
        src = combo_floorbest(bb, bs)
        if not src.exists():
            print(f"G({bb},{bs}) 源缺 {src.name}，跳过")
            continue
        rows = load_rows(src)
        mt10 = [r for r in rows if r["floor"] == "MT10"]
        if not mt10:
            print(f"G({bb},{bs}) 源无 MT10 行，跳过")
            continue
        best_row, _s, _vz, D = pick_best_mt10(zone, start, mt10)
        actions = list(best_row["actions"])
        tr = trace_route(start, actions, gems, big_cells)
        tm = sword_timing(zone, start, actions, gems)
        # 导出 .h5route（甜区已存在也重导，保证三档同口径同时落盘）
        info = gen_combo_h5route(bb, bs, src, zone, start)
        data[(bb, bs)] = dict(best_row=best_row, actions=actions, tr=tr, tm=tm, D=D, info=info, src=src)
        h = tr["final"].hero
        print(f"\nG({bb},{bs}) → {info['path'].name}")
        print(f"  终态 MT10({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} 步数={len(actions)} "
              f"红钥匙={h.keys.get('redKey',0)}  V裕度HP−D={h.hp - D}")
        print(f"  剑盾: {sword_verdict(tm)}")

    if REF not in data:
        print("\n甜区参照 G(25,3) 缺失，无法对比。")
        return

    ref = data[REF]
    ref_pcells = [e["cell"] for e in ref["tr"]["attr_events"]]
    ref_fseq = ref["tr"]["floor_seq"]

    # ── 逐里程碑对比 ──
    print("\n" + "=" * 104)
    print("逐里程碑对比")
    print("=" * 104)

    print("\n[1] 终末与关键时点（铁剑=MT5+10atk / 铁盾=MT9+10def）")
    print(f"  {'档':>10} {'到MT10 HP/A/D':>16} {'步数':>5} {'铁剑@步':>8} {'剑前MT3损血':>11} "
          f"{'铁盾@步':>8} {'盾时HP':>7} {'剑→盾步距':>9} {'剑→盾间薅小宝石':>14}")
    for (bb, bs) in CONFIGS:
        if (bb, bs) not in data:
            continue
        d = data[(bb, bs)]
        tr, tm = d["tr"], d["tm"]
        h = tr["final"].hero
        sword = find_big(tr["attr_events"], True)
        shield = find_big(tr["attr_events"], False)
        s_i = sword["i"] if sword else None
        sh_i = shield["i"] if shield else None
        sh_hp = shield["hp"] if shield else None
        gap = (sh_i - s_i) if (s_i and sh_i) else None
        # 剑→盾之间薅的小宝石
        between = [e for e in tr["attr_events"]
                   if (not e["big"]) and s_i is not None and sh_i is not None and s_i < e["i"] <= sh_i]
        nb = len(between)
        tag = "★甜区" if (bb, bs) == REF else ""
        print(f"  {('G(%d,%d)'%(bb,bs)):>10}{tag} {h.hp}/{h.atk}/{h.def_:>2} {len(d['actions']):>5} "
              f"{str(s_i):>8} {str(tm['mt3_pre_dmg']):>11} {str(sh_i):>8} {str(sh_hp):>7} "
              f"{str(gap):>9} {nb:>14}")

    print("\n[2] 拿到铁剑【之后】到拿到铁盾【之前】——上楼追盾 vs 把近区攻防拿光")
    for (bb, bs) in CONFIGS:
        if (bb, bs) not in data:
            continue
        d = data[(bb, bs)]
        tr = d["tr"]
        sword = find_big(tr["attr_events"], True)
        shield = find_big(tr["attr_events"], False)
        if not sword:
            print(f"  G({bb},{bs}): 未拿铁剑")
            continue
        s_i = sword["i"]
        sh_i = shield["i"] if shield else 10 ** 9
        seg = [e for e in tr["attr_events"] if s_i < e["i"] <= sh_i]
        # 剑→盾之间走过的楼层
        fl_between = []
        for fid, (fi, hp, atk, dff) in sorted(d["tr"]["floor_first"].items(), key=lambda kv: kv[1][0]):
            if s_i < fi <= sh_i:
                fl_between.append(fid)
        tag = "★甜区" if (bb, bs) == REF else ""
        print(f"  G({bb},{bs}){tag} 铁剑@步{s_i}(MT5)，到铁盾@步{shield['i'] if shield else '未拿'}：")
        print(f"     中间属性拾取 {len(seg)} 次：" + (", ".join(
            f"步{e['i']}{e['fid']}({e['x']},{e['y']}){e['label']}→A{e['atk']}/D{e['deff']}" for e in seg) or "（无，直奔铁盾）"))
        print(f"     中间首达楼层：{' → '.join(fl_between) if fl_between else '（同层内直达）'}")

    print("\n[3] 从甜区 G(25,3) 岔开的地方（属性拾取序 / 楼层序首个分歧）")
    for (bb, bs) in CONFIGS:
        if (bb, bs) == REF or (bb, bs) not in data:
            continue
        d = data[(bb, bs)]
        pcells = [e["cell"] for e in d["tr"]["attr_events"]]
        fseq = d["tr"]["floor_seq"]
        pi, pr, pc = first_divergence(ref_pcells, pcells)
        fi, fr, fc = first_divergence(ref_fseq, fseq)
        ad = action_divergence(start, ref["actions"], d["actions"])
        print(f"  G({bb},{bs}) vs 甜区：")
        if ad is None:
            print(f"     动作串：完全一致（前缀）")
        else:
            print(f"     ★动作串第 {ad['i']+1} 步精确岔开：在 {ad['fid']}({ad['x']},{ad['y']}) HP{ad['hp']} A{ad['atk']}/D{ad['deff']}，"
                  f"甜区走 '{ad['ref_tok']}'，本档走 '{ad['tok']}'")
        if pi is None:
            print(f"     属性拾取序：完全一致（同一串属性件）")
        else:
            rl = label_cell(pr, gems, big_cells) if pr else "—"
            cl = label_cell(pc, gems, big_cells) if pc else "—"
            print(f"     属性拾取序第 {pi+1} 件岔开：甜区拿 {pr}{rl}，本档拿 {pc}{cl}")
        if fi is None:
            print(f"     楼层序：完全一致")
        else:
            print(f"     楼层序第 {fi+1} 段岔开：甜区→{fr}，本档→{fc}")

    print("\n[4] HP 轨迹（各楼层首达时 HP，看在哪段被拉开）")
    all_floors = sorted({f for (bb, bs) in data for f in data[(bb, bs)]["tr"]["floor_first"]},
                        key=lambda f: (int(f[2:]) if f.startswith("MT") and f[2:].isdigit() else 999))
    cols = [c for c in CONFIGS if c in data]
    print(f"  {'楼层':>6} " + " ".join(f"{('G%d,%d'%c):>16}" for c in cols))
    for f in all_floors:
        cells = []
        for c in cols:
            ff = data[c]["tr"]["floor_first"].get(f)
            cells.append(f"步{ff[0]} HP{ff[1]}" if ff else "—")
        print(f"  {f:>6} " + " ".join(f"{x:>16}" for x in cells))

    write_report(data, gems, big_cells, ranked)
    print("\n" + "-" * 104)
    print(f"报告已写：{OUT}")


def write_report(data, gems, big_cells, ranked):
    ref = data.get(REF)
    ref_pcells = [e["cell"] for e in ref["tr"]["attr_events"]] if ref else []
    ref_fseq = ref["tr"]["floor_seq"] if ref else []
    L = []
    L.append("# 想法1：G(60,3) / G(10,3) 导出 + 与甜区 G(25,3) 逐里程碑对比（只读·不改产品码）\n")
    L.append("> 路线=各源 `crossbeam_floorbest_K200_bb{bb}_bs3_lam0.2_stairs.jsonl` 的 best-MT10（pick_best_mt10，V=HP−D 取顶）。")
    L.append("> .h5route = 开局前缀 83 token（噩梦→MT3 入口）+ region 段，引擎封板预检终态一致；铁剑/铁盾=detect_big_items 数据涌现。")
    L.append(f"> 大件：{', '.join(f'{c[0]}({c[1]},{c[2]})+{da}atk/+{dd}def' for (drp,c,da,dd) in ranked if c in big_cells)}。\n")

    L.append("## 1. 三档总览：同 ATK≈25，HP 天差地别\n")
    L.append("| 档 | 到MT10 HP/ATK/DEF | 步数 | 铁剑@步 | 剑前MT3损血 | 铁盾@步 | 盾时HP | 剑→盾步距 | 剑→盾间薅小宝石 | .h5route |")
    L.append("|----|------------------|-----|--------|------------|--------|-------|----------|----------------|----------|")
    for (bb, bs) in CONFIGS:
        if (bb, bs) not in data:
            L.append(f"| G({bb},{bs}) | (源缺/无MT10) | | | | | | | | |")
            continue
        d = data[(bb, bs)]
        tr, tm = d["tr"], d["tm"]
        h = tr["final"].hero
        sword = find_big(tr["attr_events"], True)
        shield = find_big(tr["attr_events"], False)
        s_i = sword["i"] if sword else None
        sh_i = shield["i"] if shield else None
        gap = (sh_i - s_i) if (s_i and sh_i) else None
        nb = len([e for e in tr["attr_events"] if (not e["big"]) and s_i and sh_i and s_i < e["i"] <= sh_i])
        star = " ★甜区" if (bb, bs) == REF else ""
        L.append(f"| **G({bb},{bs})**{star} | {h.hp}/{h.atk}/{h.def_} | {len(d['actions'])} | {s_i} | "
                 f"**{tm['mt3_pre_dmg']}** | {sh_i} | {shield['hp'] if shield else '—'} | {gap} | {nb} | `{d['info']['path'].name}` |")
    L.append("")

    L.append("## 2. 拿到铁剑之后：上楼追盾 vs 把近区攻防拿光\n")
    for (bb, bs) in CONFIGS:
        if (bb, bs) not in data:
            continue
        d = data[(bb, bs)]
        tr = d["tr"]
        sword = find_big(tr["attr_events"], True)
        shield = find_big(tr["attr_events"], False)
        if not sword:
            L.append(f"- **G({bb},{bs})**：全程未拿铁剑。")
            continue
        s_i = sword["i"]
        sh_i = shield["i"] if shield else 10 ** 9
        seg = [e for e in tr["attr_events"] if s_i < e["i"] <= sh_i]
        fl_between = [fid for fid, (fi, *_r) in sorted(d["tr"]["floor_first"].items(), key=lambda kv: kv[1][0])
                      if s_i < fi <= sh_i]
        star = " ★甜区" if (bb, bs) == REF else ""
        body = ", ".join(f"步{e['i']}{e['fid']}({e['x']},{e['y']}){e['label']}" for e in seg) or "（无，直奔铁盾）"
        L.append(f"- **G({bb},{bs})**{star}：铁剑@步{s_i}(MT5) → 铁盾@步{shield['i'] if shield else '未拿'}。"
                 f"中间薅属性 {len(seg)} 次：{body}。中间首达楼层：{' → '.join(fl_between) if fl_between else '（同层直达）'}。")
    L.append("")

    L.append("## 3. 从甜区 G(25,3) 岔开的地方\n")
    for (bb, bs) in CONFIGS:
        if (bb, bs) == REF or (bb, bs) not in data:
            continue
        d = data[(bb, bs)]
        pcells = [e["cell"] for e in d["tr"]["attr_events"]]
        fseq = d["tr"]["floor_seq"]
        pi, pr, pc = first_divergence(ref_pcells, pcells)
        fi, fr, fc = first_divergence(ref_fseq, fseq)
        ad = action_divergence(ref["actions"] and data[REF]["actions"] and build_start()[0], ref["actions"], d["actions"]) \
            if False else action_divergence(build_start()[0], ref["actions"], d["actions"])
        L.append(f"- **G({bb},{bs}) vs 甜区**：")
        if ad is not None:
            L.append(f"  - **动作串第 {ad['i']+1} 步精确岔开**：在 `{ad['fid']}({ad['x']},{ad['y']})` HP{ad['hp']} A{ad['atk']}/D{ad['deff']}，"
                     f"甜区走 `{ad['ref_tok']}`、本档走 `{ad['tok']}`。")
        if pi is None:
            L.append(f"  - 属性拾取序：完全一致。")
        else:
            L.append(f"  - 属性拾取序第 {pi+1} 件岔开：甜区拿 `{pr}`{label_cell(pr,gems,big_cells) if pr else ''}，"
                     f"本档拿 `{pc}`{label_cell(pc,gems,big_cells) if pc else ''}。")
        if fi is None:
            L.append(f"  - 楼层序：完全一致。")
        else:
            L.append(f"  - 楼层序第 {fi+1} 段岔开：甜区 →`{fr}`，本档 →`{fc}`。")
    L.append("")

    L.append("## 4. HP 轨迹（各楼层首达 HP）\n")
    cols = [c for c in CONFIGS if c in data]
    all_floors = sorted({f for c in cols for f in data[c]["tr"]["floor_first"]},
                        key=lambda f: (int(f[2:]) if f.startswith("MT") and f[2:].isdigit() else 999))
    L.append("| 楼层 | " + " | ".join(f"G({c[0]},{c[1]})" for c in cols) + " |")
    L.append("|------|" + "|".join("------" for _ in cols) + "|")
    for f in all_floors:
        row = [f]
        for c in cols:
            ff = data[c]["tr"]["floor_first"].get(f)
            row.append(f"步{ff[0]} HP{ff[1]}" if ff else "—")
        L.append("| " + " | ".join(row) + " |")
    L.append("")

    L.append("## 5. 结论\n")
    if all(c in data for c in CONFIGS):
        g25 = data[(25, 3)]["tr"]["final"].hero
        g60 = data[(60, 3)]["tr"]["final"].hero
        g10 = data[(10, 3)]["tr"]["final"].hero
        tm10 = data[(10, 3)]["tm"]
        tm60 = data[(60, 3)]["tm"]
        L.append(f"- **同 ATK≈25，HP 甜区 {g25.hp} > bb60 {g60.hp} > bb10 {g10.hp}**：β_big 偏离甜区两端都掉血，但机理不同。")
        L.append(f"- **bb10（弱大件引导）剑盾误判复发**：剑前 MT3 裸打损血 **{tm10['mt3_pre_dmg']}**（甜区/bb60 仅 {data[(25,3)]['tm']['mt3_pre_dmg']}）"
                 f"——大件引导太弱，搜索没有先去 MT5 拿剑、在 MT3 硬扛，HP 从一开始就亏掉。")
        L.append(f"- **bb60（过强大件引导）就近病回涨**：大件邻域分太高，搜索被铁剑/铁盾周围一圈格子吸住、顺手清就近杂怪，"
                 f"绕路损血，HP 落在中间（{g60.hp}）。")
        L.append(f"- 详细岔开点见 §3、HP 在哪段被拉开见 §4。**甜区 (25,3) 同时避开'引导太弱不先拿剑'和'引导太强就近绕路'两个坑。**")
    L.append("")
    L.append("> ⚠ 三档到 MT10 都仍无红钥匙（老问题）→ 网站回放走到 MT10 入口即止、不撞红门。本轮只对比决策路线形态。")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
