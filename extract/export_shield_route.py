"""导出 K=200/λ=0.05/floor 自主搜索里【拿到 MT9 铁盾】的路线 → 决策交代（玩家下个会话用）。

用途：(1) 照着动作序列在真实游戏走、终审；(2) 判定它是不是「晚拿盾多打怪」的亏路线
       （玩家怀疑：先打了很多怪攒了很多属性才去拿盾，那些已死的怪没享受盾的减伤=亏，
        只因 route 首过基准属性故意留得低才显得「支配」）。

做法（全部引擎算，绝不在对话推演）：
  · 重跑跨层 beam（K=200, λ=0.05, floor 分坑, goal=MT0 纯探索＝未喂盾坐标），on_admit 累计各层
    Pareto 最优属性（含完整 actions）；
  · 取拿盾候选路线（全局/MT9/MT10 的 maxDEF·maxATK），逐 token 引擎重放：
      - 完整动作序列（可照走）；
      - 逐属性增益事件（每块攻防宝石/铁剑/铁盾：第几步·此前累计杀怪·当刻 HP/ATK/DEF）；
      - 【MT9 铁盾那一刻】定位 + 盾对【剩余未杀区怪】的边际减伤 vs 若开局即拿的满额减伤(标定 20,264)
        → 量化「晚拿盾」损失；
      - 逐层首过属性曲线 vs route 首过基准。
  · 引擎独立重放裁判（replay + diff 零差异）。
落盘 extract/shield_route_decision.txt + .json。

红线照旧：goal=MT0 未喂盾坐标＝真自主；每候选封板 replay 核对；route 仅下界对照、不喂走法。
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from collections import defaultdict

from sim.simulator import step, _copy_state
from solver.quotient import search_quotient, value_vector
from solver.beam import (build_future_roster, FutureCfg, _future_potential,
                         _region_bounds, _alive_mids_on)
from solver.verify import replay, diff_states
from probe_crossfloor import build_start, _fidx
from probe_crossfloor_beam import FloorBest, route_profile

OUT = Path(__file__).parent
BEAM_K = 200
LAM = 0.05
DIVERSITY = "floor"
CAP = 120000
SHIELD_FLOOR = "MT9"   # 「哪层的 DEF 跳变=铁盾」来自 probe_topology 数据探出(shield1@MT9)，非硬编码打法


def _snap(s):
    h = s.hero
    return {"floor": s.current_floor, "x": h.x, "y": h.y, "hp": h.hp, "atk": h.atk,
            "def": h.def_, "mdef": h.mdef, "gold": h.gold, "kill": h.kill_count,
            "keys": {k: v for k, v in h.keys.items() if v},
            "items": {k: v for k, v in h.items.items() if v}}


def trace_route(actions, roster):
    """逐 token 引擎重放一条动作序列，返回详尽轨迹（全部引擎算）。"""
    s, _ = build_start()
    start_snap = _snap(s)
    floor_runs = []
    attr_events = []          # 每次 ATK/DEF/MDEF 增益事件
    cur = start_snap
    run = {"floor": cur["floor"], "enter": (cur["x"], cur["y"]),
           "hp_in": cur["hp"], "atk_in": cur["atk"], "def_in": cur["def"], "kills": 0}
    grab = None               # MT9 首次 DEF 跳变(铁盾)
    for idx, tok in enumerate(actions):
        before = _snap(s)
        s = step(s, tok)
        after = _snap(s)
        if before["floor"] != after["floor"]:
            run["exit"] = (before["x"], before["y"])
            run["hp_out"], run["atk_out"], run["def_out"] = before["hp"], before["atk"], before["def"]
            floor_runs.append(run)
            run = {"floor": after["floor"], "enter": (after["x"], after["y"]),
                   "hp_in": after["hp"], "atk_in": after["atk"], "def_in": after["def"], "kills": 0}
        if after["kill"] > before["kill"]:
            run["kills"] += after["kill"] - before["kill"]
        for key, label in (("atk", "ATK"), ("def", "DEF"), ("mdef", "MDEF")):
            if after[key] > before[key]:
                ev = {"step": idx, "floor": after["floor"], "attr": label,
                      "delta": after[key] - before[key], "kills_so_far": after["kill"],
                      "hp": after["hp"], "atk": after["atk"], "def": after["def"]}
                attr_events.append(ev)
                if label == "DEF" and after["floor"] == SHIELD_FLOOR and grab is None:
                    grab = {"ev": ev, "state": _copy_state(s), "def_before": before["def"]}
    run["exit"] = (s.hero.x, s.hero.y)
    run["hp_out"], run["atk_out"], run["def_out"] = s.hero.hp, s.hero.atk, s.hero.def_
    floor_runs.append(run)

    first_visit = {}          # fid -> 该层首次访问的 run（进/出属性）
    for r in floor_runs:
        first_visit.setdefault(r["floor"], r)
    return {"start": start_snap, "end": _snap(s), "end_state": s,
            "floor_runs": floor_runs, "attr_events": attr_events,
            "first_visit": first_visit, "grab": grab, "n_tokens": len(actions)}


def shield_analysis(grab, roster, start_state, base_far):
    """拿盾那一刻：盾对【剩余未杀区怪】的边际减伤 vs 若开局即拿的满额减伤 → 量化晚拿盾损失。"""
    if grab is None:
        return None
    gs = grab["state"]
    delta = grab["ev"]["delta"]
    cfg1 = FutureCfg(roster, 1.0)
    toll_after = int(_future_potential(gs, cfg1))            # 拿盾后(def 已+delta)，剩余区怪 toll
    s_no = _copy_state(gs)
    s_no.hero.def_ -= delta
    toll_no = int(_future_potential(s_no, cfg1))             # 同一存活集，假设没这块盾
    reduce_remaining = toll_no - toll_after                  # 盾对【剩余】区怪的减伤＝晚拿盾的实得

    # 若同样 +delta 在【起点】就拿到（全区怪都还活着）的满额减伤
    s_full = _copy_state(start_state)
    s_full.hero.def_ += delta
    full_drop = base_far - int(_future_potential(s_full, cfg1))

    cur_i = roster["idx_of"].get(gs.current_floor)
    lo, hi = _region_bounds(roster, cur_i)
    alive_excl_cur = sum(len(_alive_mids_on(gs, roster, i))
                         for i in range(lo, hi + 1) if i != cur_i)
    # 本区(MT0..boss)起点全员怪数=分母；用起点所在层的区界，与标定 base_far 同区
    lo0, hi0 = _region_bounds(roster, roster["idx_of"][start_state.current_floor])
    total_region = sum(len(_alive_mids_on(start_state, roster, i))
                       for i in range(lo0, hi0 + 1))
    return {"delta": delta, "step": grab["ev"]["step"], "kills_so_far": grab["ev"]["kills_so_far"],
            "hp": grab["ev"]["hp"], "atk": grab["ev"]["atk"], "def": grab["ev"]["def"],
            "def_before": grab["def_before"],
            "toll_after": toll_after, "toll_no": toll_no, "reduce_remaining": reduce_remaining,
            "full_drop_if_at_start": full_drop,
            "alive_region_excl_cur": alive_excl_cur, "total_region_monsters": total_region,
            "region": (roster["floor_ids"][lo], roster["floor_ids"][hi]),
            "cur_floor": gs.current_floor}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=CAP, help="冒烟测试用小 cap；正式跑用默认 120000")
    ap.add_argument("--beam", type=int, default=BEAM_K)
    args = ap.parse_args()
    cap, beam_k = args.cap, args.beam

    start, nopen = build_start()
    h = start.hero
    roster = build_future_roster(start)
    beam_future = FutureCfg(roster, LAM)

    def far(datk=0, ddef=0):
        s2 = _copy_state(start)
        s2.hero.atk += datk
        s2.hero.def_ += ddef
        return int(_future_potential(s2, FutureCfg(roster, 1.0)))

    base_far = far()
    shield_full_10 = base_far - far(ddef=10)

    print("=" * 96)
    print(f"导出【拿到 MT9 铁盾】路线决策交代（K={BEAM_K} λ={LAM} 分坑={DIVERSITY} goal=MT0 纯探索）")
    print("=" * 96)
    print(f"起点(噩梦后首个自由态): {start.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_}")
    print(f"区势能标定：Σ_区 toll(裸态)={base_far:,}；+10DEF 铁盾若开局即拿满额减伤={shield_full_10:,}")
    print("-" * 96)

    # ── on_admit 累计各层 Pareto 最优属性（含 actions），与 probe 同口径 ──
    per_floor = defaultdict(FloorBest)

    def on_admit(stt, actions):
        hh = stt.hero
        per_floor[stt.current_floor].offer((hh.hp, hh.atk, hh.def_, hh.mdef),
                                           actions, value_vector(stt))

    cut_path = OUT / f"export_shield_cut_K{beam_k}.jsonl"
    fh = cut_path.open("w", encoding="utf-8")

    def sink(records):
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    t0 = time.perf_counter()
    res = search_quotient(start, ("MT0", 1, 1), step, max_states=cap, cross_floor=True,
                          beam_k=beam_k, beam_cut_sink=sink, on_admit=on_admit,
                          beam_future=beam_future, beam_diversity=DIVERSITY)
    dt = time.perf_counter() - t0
    fh.close()
    floors_seen = sorted(getattr(res, "floors_seen", []), key=_fidx)
    print(f"耗时={dt:.1f}s  hit_cap={res.hit_cap}  到达层={floors_seen}")

    # ── 收集拿盾候选：全局 maxDEF + MT9/MT10 各自 maxDEF·maxATK（去重 actions）──
    def gmax(idx):
        best = None
        for fid, fb in per_floor.items():
            b = fb.max_by(idx)
            if b and (best is None or b[0][idx] > best[1][0][idx]):
                best = (fid, b)
        return best

    cand_specs = []
    g = gmax(2)
    if g:
        cand_specs.append(("全局maxDEF", g[0], g[1]))
    g = gmax(1)
    if g:
        cand_specs.append(("全局maxATK", g[0], g[1]))
    for fid in (SHIELD_FLOOR, "MT10"):
        fb = per_floor.get(fid)
        if not fb:
            continue
        for idx, nm in ((2, "maxDEF"), (1, "maxATK"), (0, "maxHP")):
            b = fb.max_by(idx)
            if b:
                cand_specs.append((f"{fid}-{nm}", fid, b))

    seen_actions = set()
    candidates = []
    for label, fid, (vec4, actions, valvec) in cand_specs:
        key = tuple(actions)
        if key in seen_actions:
            continue
        seen_actions.add(key)
        tr = trace_route(list(actions), roster)
        sa = shield_analysis(tr["grab"], roster, start, base_far)
        rep = replay(start, list(actions), step, _copy_state)
        diffs = diff_states(tr["end_state"], rep)
        candidates.append({"label": label, "rec_floor": fid, "vec4": vec4, "actions": list(actions),
                           "trace": tr, "shield": sa, "replay_ok": not diffs, "diffs": diffs})

    # ── 选 primary：有拿盾(grab)且 DEF 最高者；都没拿盾则取全局 maxDEF ──
    grabbers = [c for c in candidates if c["shield"] is not None]
    if grabbers:
        primary = max(grabbers, key=lambda c: c["vec4"][2])
    else:
        primary = max(candidates, key=lambda c: c["vec4"][2])

    prof, rfinal = route_profile()

    # ── 文本报告 ──
    out = []
    def w(line=""):
        out.append(line)

    w("=" * 96)
    w(f"【拿到 MT9 铁盾】路线决策交代 — 玩家真实游戏终审 + 判定是否「晚拿盾多打怪」亏路线")
    w(f"搜索配置：K={beam_k} λ={LAM} 分坑={DIVERSITY} goal=MT0(纯探索·未喂盾坐标)  "
      f"耗时={dt:.1f}s hit_cap={res.hit_cap} 到达层={floors_seen}")
    w("=" * 96)

    # 候选总览
    w("一、拿盾候选总览（同一次搜索的不同 Pareto 最优态；★=该路线在 MT9 检测到铁盾拿取）")
    w(f"{'候选':>14} {'记录层':>6} {'末HP':>6} {'末ATK':>6} {'末DEF':>6} {'步数':>6} "
      f"{'拿盾?':>6} {'重放':>5}")
    for c in candidates:
        v = c["vec4"]
        grabbed = "★拿到" if c["shield"] else "—"
        w(f"{c['label']:>14} {c['rec_floor']:>6} {v[0]:>6} {v[1]:>6} {v[2]:>6} "
          f"{c['trace']['n_tokens']:>6} {grabbed:>6} {'✅' if c['replay_ok'] else '❌':>5}")
    w("")

    # primary 详解
    pl = primary["label"]
    pt = primary["trace"]
    w("=" * 96)
    w(f"二、PRIMARY 路线＝{pl}（记录层 {primary['rec_floor']}，{pt['n_tokens']} 步，"
      f"末态 HP={primary['vec4'][0]} ATK={primary['vec4'][1]} DEF={primary['vec4'][2]}）")
    w(f"   引擎独立重放裁判：{'✅ 零差异（可照走）' if primary['replay_ok'] else '❌ '+str(primary['diffs'])}")
    w("=" * 96)

    sa = primary["shield"]
    w("【关键】MT9 铁盾拿取时机 + 晚拿盾损失量化（玩家最关心）")
    if sa is None:
        w("  ⚠⚠ 本路线【未检测到 MT9 铁盾拿取】——其 DEF 全部来自宝石，而非 MT9 铁盾！")
        w("       （若所有候选都如此，则『自主拿到铁盾』这一结论需要推翻，请看候选总览的『拿盾?』列）")
    else:
        w(f"  · 拿盾发生在第 {sa['step']} 步（floor={sa['cur_floor']}），DEF {sa['def_before']}→{sa['def']}（+{sa['delta']}）")
        w(f"  · 拿盾【那一刻】属性：HP={sa['hp']} ATK={sa['atk']} DEF={sa['def']}")
        w(f"  · 拿盾【之前已累计杀怪】= {sa['kills_so_far']} 只（这些怪【没】享受到这块盾的减伤）")
        w(f"  · 拿盾时本区还剩 {sa['alive_region_excl_cur']} 只活怪(excl 当前层)能享受减伤；全区共 {sa['total_region_monsters']} 只")
        w(f"  · 盾对【剩余未杀区怪】的边际减伤 = {sa['reduce_remaining']:,}")
        w(f"  · 若同样这块盾【开局即拿】对全区的满额减伤 = {sa['full_drop_if_at_start']:,}")
        if sa["full_drop_if_at_start"] > 0:
            ratio = sa["reduce_remaining"] / sa["full_drop_if_at_start"]
            w(f"  · 实得/满额 = {ratio:.0%}  →  晚拿盾【损失】≈ {sa['full_drop_if_at_start']-sa['reduce_remaining']:,} "
              f"({1-ratio:.0%} 的盾价值因『先打怪后拿盾』被浪费)")
        w(f"  注：剩余减伤在 {sa['cur_floor']} 处算(排除当前层)，满额在起点 MT3 处算(排除 MT3)，"
          f"两者排除层不同→比值为近似；但『拿盾前已杀 {sa['kills_so_far']} 只』是引擎精确计数、不受影响。")
    w("")

    # 逐属性增益事件
    w("-" * 96)
    w("三、逐属性增益事件（每块攻/防/魔防：第几步·此前累计杀怪·当刻 HP/ATK/DEF）——看「攒属性 vs 拿盾」先后")
    w(f"{'步':>6} {'层':>5} {'增益':>5} {'幅度':>5} {'此前杀怪':>8} {'当刻HP':>7} {'当刻ATK':>7} {'当刻DEF':>7}")
    for ev in pt["attr_events"]:
        star = "  ←MT9铁盾" if (ev["attr"] == "DEF" and ev["floor"] == SHIELD_FLOOR) else ""
        w(f"{ev['step']:>6} {ev['floor']:>5} {ev['attr']:>5} {'+'+str(ev['delta']):>5} "
          f"{ev['kills_so_far']:>8} {ev['hp']:>7} {ev['atk']:>7} {ev['def']:>7}{star}")
    w("")

    # 逐层首过属性曲线 vs route 首过
    w("-" * 96)
    w("四、逐层【首过】属性曲线 vs route 首过基准（搜索进/出 同期对照；route=首次离开该层）")
    w(f"{'层':>5} {'搜索首入(hp/atk/def)':>20} {'搜索首出(hp/atk/def)':>20} {'route首过出(hp/atk/def)':>22}")
    seen = set()
    for r in pt["floor_runs"]:
        fid = r["floor"]
        if fid in seen:
            continue
        seen.add(fid)
        ein = f"{r['hp_in']}/{r['atk_in']}/{r['def_in']}"
        eout = f"{r.get('hp_out','?')}/{r.get('atk_out','?')}/{r.get('def_out','?')}"
        rp = prof.get(fid)
        rexit = (f"{rp['first_exit'][0]}/{rp['first_exit'][1]}/{rp['first_exit'][2]}"
                 if rp else "—(route未访)")
        w(f"{fid:>5} {ein:>20} {eout:>20} {rexit:>22}")
    w(f"  route 通关末态(下界): {rfinal['_floor']} won={rfinal['_won']} "
      f"HP={rfinal['hp']} ATK={rfinal['atk']} DEF={rfinal['def']} kill={rfinal['kill']}")
    w("")

    # 完整动作序列
    w("-" * 96)
    w(f"五、PRIMARY 完整动作序列（可照走，{pt['n_tokens']} 步）")
    w(" ".join(primary["actions"]))
    w("=" * 96)

    report = "\n".join(out)
    print("\n" + report)

    # ── 落盘 ──
    def cand_json(c):
        return {"label": c["label"], "rec_floor": c["rec_floor"],
                "end": c["trace"]["end"], "n_tokens": c["trace"]["n_tokens"],
                "replay_ok": c["replay_ok"], "shield": c["shield"],
                "actions": c["actions"]}

    payload = {
        "config": {"beam_k": beam_k, "lam": LAM, "diversity": DIVERSITY, "cap": cap,
                   "goal": "MT0", "elapsed_s": round(dt, 1), "hit_cap": res.hit_cap,
                   "floors_seen": floors_seen},
        "calibration": {"base_region_toll": base_far, "shield_plus10_full_drop": shield_full_10},
        "route_final": {"floor": rfinal["_floor"], "won": rfinal["_won"], "hp": rfinal["hp"],
                        "atk": rfinal["atk"], "def": rfinal["def"], "kill": rfinal["kill"]},
        "route_first_pass": {fid: prof[fid]["first_exit"] for fid in prof},
        "primary_label": pl,
        "primary": {"shield": sa, "attr_events": pt["attr_events"],
                    "floor_runs": pt["floor_runs"], "actions": primary["actions"]},
        "candidates": [cand_json(c) for c in candidates],
    }
    (OUT / "shield_route_decision.txt").write_text(report, encoding="utf-8")
    (OUT / "shield_route_decision.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[落盘] extract/shield_route_decision.txt + .json")


if __name__ == "__main__":
    main()
