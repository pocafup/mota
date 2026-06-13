"""第0步【β 复跑】探针（不碰产品码，纯诊断）：用各 β 搜索的【真实 MT9 态】横向四个 β
   （0.25/0.5/0.75/1）复跑 fly-aware pull 对比，回答玩家三问：

   1. 各 β 跑到 MT9 的代表态（首入 MT9=min len(actions) + 停留最深态=max atk+def），报告该态属性 +
      MT1-5【此刻实际留了什么货】（还在地上、value>0 的攻防宝石/装备：物品名、Δatk/Δdef、boss-value、
      四距离）——解决“零碎小宝石 vs 大量属性”那个出入，确认 β 走法下 MT9 时 MT1-5 到底值不值得回。
   2. 四距离口径对比 → 四口径 pull：
        d楼梯静 → pull楼梯静 = value/(1+d楼梯静)             【现状（vzone.pull 口径）】
        d楼梯活 → pull楼梯活 = value/(1+d楼梯活)             【方向A：_enter_cost 读活体】
        d_fly静 → pull_fly静 = value/(1+min(d楼梯静,d_fly静)) 【fly 边初版（层内仍静态）】
        d_fly活 → pull_fly活 = value/(1+min(d楼梯活,d_fly活)) 【fly + 方向A 全修】
      MT1-5 合计 pull vs 就近 MT8/MT7：现状压不压得过、方向A/fly-aware 翻不翻身、翻身幅度。
   3. 横向四 β：翻身在 0.25→1 都成立吗？哪个 β 的 MT9 态 MT1-5 留货最多/最值得回？
      β 越高是否 MT1-5 被拿得越早、回头价值越低（对照“高 β 打无意义怪”现象）。

   态来源：各 β 的 cut 文件 crossbeam_cut_K50_vzone_b{β}_lam0.0_stairs.jsonl（= bscan/玩家“六条 β
   路线”同源），floor==MT9 行里取首入(min len(actions))+最深(max atk+def)，从 build_start() 引擎
   封板 replay 重建全态再诊断（cut 态=搜索探索到、可能被 beam 截的态，与玩家路线同源）。
   口径与 vzone.pull 完全一致（boss_toll Δ 区势能、距离 Dijkstra、拿走离场不计、value<=0 不计），
   复用 probe_pull_flyaware 的 make_cost/toll_dist/single_floor_toll/fly_landing/_fmt。
   不改 vzone.py / quotient.py / sim。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from solver.verify import replay
from probe_crossfloor import build_start, _fidx
from vzone import build_zone, boss_toll, _zone_attr_gems
from probe_pull_flyaware import (make_cost, toll_dist, single_floor_toll,
                                 fly_landing, _fmt, INF)

HERE = Path(__file__).parent
DEFAULT_BETAS = [0.25, 0.5, 0.75, 1.0]


def cut_path(beta):
    tag = f"_b{beta:g}" if beta else ""
    return HERE / f"crossbeam_cut_K50_vzone{tag}_lam0.0_stairs.jsonl"


def load_mt9_rows(beta):
    """读 cut 文件里所有 floor==MT9 的行（流式跳过残行）。文件缺→None。"""
    fn = cut_path(beta)
    if not fn.exists():
        return None
    rows = []
    with fn.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("floor") == "MT9":
                rows.append(r)
    return rows


def gem_item(zone, gfid, x, y):
    """从 zone【初始】层读该格物品 id/中文名（zone floors 保留初始放置，不随搜索拾取改）。"""
    fl = zone["floors"][gfid]["floor"]
    e = fl.entities[y][x]
    iid = fl._tile_to_item.get(e) if e else None
    if not iid:
        return "?", ""
    d = fl._items_db.get(iid)
    name = d.get("name", "") if isinstance(d, dict) else ""
    return iid, name


def diagnose_beta(zone, state, tag, betatag):
    """对单个 MT9 态：四口径 pull 逐格表 + MT1-5 留货明细 + 层汇总 + 翻身判定。
    返回 dict(band15=[4], mt8=[4], mt7=[4], near=[4], hero=(hp,atk,def), mt15_count, mt15_da, mt15_dd,
              boss_cur, boss_mt15_all)。"""
    h = state.hero
    fid = state.current_floor
    print("=" * 116)
    print(f"【β={betatag} · {tag}】MT9 态: floor={fid} ({h.x},{h.y}) HP={h.hp} "
          f"ATK={h.atk} DEF={h.def_} mdef={h.mdef} gold={h.gold}")

    boss_cur = boss_toll(zone, h.atk, h.def_, h.mdef)
    cost_static = make_cost(zone, state, h.atk, h.def_, h.mdef, live=False)
    cost_live = make_cost(zone, state, h.atk, h.def_, h.mdef, live=True)
    stair_static = toll_dist(zone, (fid, h.x, h.y), cost_static)
    stair_live = toll_dist(zone, (fid, h.x, h.y), cost_live)
    gems = _zone_attr_gems(zone)
    floors = state.floors

    remaining = []
    for (gfid, x, y), (da, dd) in gems.items():
        fl = floors.get(gfid)
        if fl is not None and fl.entities[y][x] == 0:
            continue
        remaining.append(((gfid, x, y), (da, dd)))

    by_floor_cnt, tot_by_floor = {}, {}
    for (gfid, _x, _y), _ in remaining:
        by_floor_cnt[gfid] = by_floor_cnt.get(gfid, 0) + 1
    for (gfid, _x, _y), _ in gems.items():
        tot_by_floor[gfid] = tot_by_floor.get(gfid, 0) + 1
    print("各层 attr-gem 剩余/总数：", end="")
    for gfid in sorted(tot_by_floor, key=_fidx):
        print(f" {gfid}:{by_floor_cnt.get(gfid,0)}/{tot_by_floor[gfid]}", end="")
    print()

    # sums[gfid] = [Σ楼梯静, Σ楼梯活(方向A), Σfly静, Σfly活]
    sums = {}
    mt15_rows = []
    for (gfid, x, y), (da, dd) in sorted(remaining,
                                         key=lambda t: (_fidx(t[0][0]), t[0][1], t[0][2])):
        value = boss_cur - boss_toll(zone, h.atk + da, h.def_ + dd, h.mdef)
        if value <= 0:
            continue
        ds_s = stair_static.get((gfid, x, y), INF)
        ds_l = stair_live.get((gfid, x, y), INF)
        land = fly_landing(zone, fid, gfid)
        df_s = single_floor_toll(zone, gfid, land, (x, y), cost_static) if land else INF
        df_l = single_floor_toll(zone, gfid, land, (x, y), cost_live) if land else INF
        p_ss = value / (1.0 + ds_s) if ds_s != INF else 0.0
        p_sl = value / (1.0 + ds_l) if ds_l != INF else 0.0
        m_fs = min(ds_s, df_s)
        m_fl = min(ds_l, df_l)
        p_fs = value / (1.0 + m_fs) if m_fs != INF else 0.0
        p_fl = value / (1.0 + m_fl) if m_fl != INF else 0.0
        s = sums.setdefault(gfid, [0.0, 0.0, 0.0, 0.0])
        s[0] += p_ss; s[1] += p_sl; s[2] += p_fs; s[3] += p_fl
        if 1 <= _fidx(gfid) <= 5:
            iid, name = gem_item(zone, gfid, x, y)
            mt15_rows.append((gfid, x, y, da, dd, value, iid, name,
                              ds_s, ds_l, df_s, df_l))

    # ── MT1-5 留货明细（解决“零碎小宝石 vs 大量属性”）──
    print("-" * 116)
    print("  MT1-5【此刻实际留货】（还在地上、value>0 的攻防宝石/装备；d 四列=楼梯静/楼梯活/fly静/fly活）：")
    sda = sdd = 0
    if not mt15_rows:
        print("    （MT1-5 已无 value>0 的攻防货可拿）")
    else:
        print(f"    {'层':>4} {'格':>8} {'Δa,Δd':>7} {'value':>5} {'物品':>12}  "
              f"{'d楼梯静':>7} {'d楼梯活':>7} {'d_fly静':>7} {'d_fly活':>7}")
        for (gfid, x, y, da, dd, value, iid, name, ds_s, ds_l, df_s, df_l) in mt15_rows:
            sda += da; sdd += dd
            print(f"    {gfid:>4} {f'({x},{y})':>8} {f'{da},{dd}':>7} {value:>5} "
                  f"{(name or iid):>12}  {_fmt(ds_s):>7} {_fmt(ds_l):>7} "
                  f"{_fmt(df_s):>7} {_fmt(df_l):>7}")
    boss_mt15_all = boss_toll(zone, h.atk + sda, h.def_ + sdd, h.mdef)
    print(f"    合计 MT1-5 留 {len(mt15_rows)} 件 value>0 货：ΣΔatk+{sda} ΣΔdef+{sdd}　"
          f"全拿→boss_toll {boss_cur}→{boss_mt15_all}（省 {boss_cur - boss_mt15_all}）")

    # ── 层汇总（四口径）+ 翻身判定 ──
    print("-" * 116)
    print(f"  {'层汇总':>4} {'Σ楼梯静':>11} {'Σ楼梯活(方A)':>13} {'Σfly静':>11} {'Σfly活':>11}")
    for gfid in sorted(sums, key=_fidx):
        a, b, c, d = sums[gfid]
        print(f"  {gfid:>4} {a:>11.3f} {b:>13.3f} {c:>11.3f} {d:>11.3f}")

    def band(lo, hi, idx):
        return sum(sums.get(f"MT{i}", [0, 0, 0, 0])[idx] for i in range(lo, hi + 1))

    mt8 = sums.get("MT8", [0, 0, 0, 0])
    mt7 = sums.get("MT7", [0, 0, 0, 0])
    near = [max(mt7[i], mt8[i]) for i in range(4)]
    band15 = [band(1, 5, i) for i in range(4)]
    names = ["楼梯静(现状)", "楼梯活(方向A)", "fly静(fly边初版)", "fly活(fly+方A)"]
    print("-" * 116)
    print(f"  {'':12}{'楼梯静':>11}{'楼梯活(方A)':>13}{'fly静':>11}{'fly活':>11}")
    print(f"  MT1-5合计   {band15[0]:>11.3f}{band15[1]:>13.3f}{band15[2]:>11.3f}{band15[3]:>11.3f}")
    print(f"  MT8就近     {mt8[0]:>11.3f}{mt8[1]:>13.3f}{mt8[2]:>11.3f}{mt8[3]:>11.3f}")
    print(f"  MT7就近     {mt7[0]:>11.3f}{mt7[1]:>13.3f}{mt7[2]:>11.3f}{mt7[3]:>11.3f}")
    for idx, nm in enumerate(names):
        b15, nr = band15[idx], near[idx]
        win = b15 > nr
        ratio = f"{b15/nr:.2f}×" if nr > 0 else "—"
        print(f"  判定[{nm:>14}]：MT1-5={b15:.3f} {'>' if win else '≤'} "
              f"max(MT7,MT8)={nr:.3f} ({ratio}) "
              f"→ {'翻身(应优先回MT1-5)' if win else '压不过就近层'}")

    return dict(band15=band15, mt8=list(mt8), mt7=list(mt7), near=near,
                hero=(h.hp, h.atk, h.def_), mt15_count=len(mt15_rows),
                mt15_da=sda, mt15_dd=sdd, boss_cur=boss_cur, boss_mt15_all=boss_mt15_all)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--betas", default=",".join(f"{b:g}" for b in DEFAULT_BETAS),
                    help="逗号分隔的 β 列表（默认 0.25,0.5,0.75,1）")
    args = ap.parse_args()
    betas = [float(x) for x in args.betas.split(",") if x.strip()]

    zone = build_zone()
    start = build_start()[0]

    print("#" * 116)
    print("β 复跑 fly-aware pull 横向对比（态=各 β cut 文件 MT9 行：首入=min步 / 最深=max(atk+def)）")
    print("  四口径：楼梯静=现状 | 楼梯活=方向A(读活体) | fly静=fly边初版(层内仍静态) | fly活=fly+方向A全修")
    print("#" * 116)

    summary = []   # (beta, tag, diag-dict)
    for beta in betas:
        rows = load_mt9_rows(beta)
        if rows is None:
            print(f"\n⚠ β={beta:g} cut 文件缺（{cut_path(beta).name}）——可能还在补跑，跳过。")
            continue
        if not rows:
            print(f"\n⚠ β={beta:g} cut 文件无 MT9 行，跳过。")
            continue
        first = min(rows, key=lambda r: len(r["actions"]))
        deepest = max(rows, key=lambda r: (r["atk"] + r["def"], r["hp"]))
        print(f"\n{'#'*40} β={beta:g}：MT9 行 {len(rows)} 个，"
              f"首入(min步 {len(first['actions'])}) hp{first['hp']}/atk{first['atk']}/def{first['def']}，"
              f"最深(atk+def {deepest['atk']+deepest['def']}) hp{deepest['hp']}/atk{deepest['atk']}/def{deepest['def']} {'#'*10}")
        for tag, row in (("首入MT9", first), ("停留最深态", deepest)):
            s = replay(start, list(row["actions"]), step, _copy_state)
            if s.current_floor != "MT9":
                print(f"  ⚠ {tag} 重放落点={s.current_floor}≠MT9（动作串异常），跳过该态。")
                continue
            d = diagnose_beta(zone, s, tag, f"{beta:g}")
            summary.append((beta, tag, d))

    # ── 横向四 β 汇总 ──
    if summary:
        print("\n" + "#" * 116)
        print("横向汇总：四 β × {首入/最深} 的 MT1-5 留货 + 四口径 pull(MT1-5合计 / 就近max(MT7,MT8)) + 翻身")
        print("#" * 116)
        hdr = (f"{'β':>5} {'态':>10} {'属性hp/a/d':>14} {'MT15留':>6} "
               f"{'ΣΔa/Δd':>8} {'boss省':>6} | "
               f"{'楼梯静15/近':>14} {'楼梯活15/近':>14} {'fly静15/近':>14} {'fly活15/近':>14}")
        print(hdr)
        print("-" * 116)
        for beta, tag, d in summary:
            hp, atk, df = d["hero"]
            cells = []
            for i in range(4):
                b15, nr = d["band15"][i], d["near"][i]
                mark = "↑" if b15 > nr else "·"
                cells.append(f"{b15:.2f}/{nr:.2f}{mark}")
            attr_s = f"{hp}/{atk}/{df}"
            delta_s = f"+{d['mt15_da']}/+{d['mt15_dd']}"
            boss_save = d["boss_cur"] - d["boss_mt15_all"]
            print(f"{beta:>5g} {tag:>10} {attr_s:>14} {d['mt15_count']:>6} "
                  f"{delta_s:>8} {boss_save:>6} | "
                  f"{cells[0]:>14} {cells[1]:>14} {cells[2]:>14} {cells[3]:>14}")
        print("-" * 116)
        print("说明：每格 = MT1-5合计pull / max(MT7,MT8)pull；↑=MT1-5 翻身(>就近)，·=压不过。"
              "boss省 = MT1-5 留货全拿后 boss_toll 下降量(真·非线性算)。")


if __name__ == "__main__":
    main()
