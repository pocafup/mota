"""【fitness 权重标定·w_potion + w_key 双权重稳健区间】用 cap480k 的 718 vs 689 这对真对照，标定
血瓶权重 w_potion 与钥匙权重 w_key，确认 689 反超是靠【血瓶 + 钥匙两个真潜力项】、每项物理意义干净。

任务（玩家 2026-06-13 拍板，钥匙潜力加入后更新）：
  · 标尺 = cap480k 的 718（耗尽）vs 689（高潜力）。主干 689 输 718（更瘦→压制弱），必须靠【血瓶 + 钥匙】
    两个潜力项把 689 抬过 718，才真考验潜力项有效。
  · 两个权重都扫【稳健区间】取中值，不取脆弱临界。
  · 给两条 route 的【完整分项对账】：主干 equiv_hp / 血瓶 w_potion·raw / 钥匙(手里满权重 + 地上够得到
    Σmax(0,w_key−守怪损血)) / 通关·死亡 各贡献多少 → 确认 689 赢在【血瓶多 250 + 地上便宜钥匙多】两真潜力。
  · 钥匙可达=预算门控(终态手里有钥匙的门可过)、扣守怪血成本(防 κ=1)，数据坐实见 probe_key_reachability。

回放与 tests/test_ga_navigate 同源（make_initial_state + step）。roster/big 走 solver.fitness 现成件。
"""
import sys
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step
from decode_route import parse_rle_route, decompress
from export_mt10_boss_route import make_initial_state
from solver.fitness import (
    build_zone1_roster, calibrate_big, fitness, fitness_breakdown,
)


def replay(route_file):
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    for a in actions:
        s = step(s, a)
        if s.dead:
            break
    return s, len(actions)


def main():
    R718 = ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"
    R689 = ROOT / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route"

    s718, n718 = replay(R718)
    s689, n689 = replay(R689)

    roster, zone_fids, _all = build_zone1_roster(s718)
    start = make_initial_state()
    big = calibrate_big([s718, s689, start], roster)

    print(f"一区 roster 怪数={len(roster)}  zone_fids={zone_fids}  big={big}")
    print(f"718(耗尽)   {n718} actions  HP={s718.hero.hp} DEF={s718.hero.def_} "
          f"钥匙={dict(s718.hero.keys)} kill={s718.hero.kill_count}")
    print(f"689(高潜力) {n689} actions  HP={s689.hero.hp} DEF={s689.hero.def_} "
          f"钥匙={dict(s689.hero.keys)} kill={s689.hero.kill_count}")

    # ── Δ 分解：主干 / 血瓶 / 钥匙 三项各贡献多少（与权重无关的 raw 口径）─────────────
    bd718 = fitness_breakdown(s718, roster, big, zone_fids, w_potion=1.0, w_key=1.0)
    bd689 = fitness_breakdown(s689, roster, big, zone_fids, w_potion=1.0, w_key=1.0)
    dmain = bd689["main_equiv_hp"] - bd718["main_equiv_hp"]
    dpot = bd689["potion_raw"] - bd718["potion_raw"]
    print(f"\n{'='*74}\nΔ 分解（689 − 718，raw 口径）\n{'='*74}")
    print(f"  主干 equiv_hp:   718={bd718['main_equiv_hp']:>9.0f}  689={bd689['main_equiv_hp']:>9.0f}"
          f"  Δ={dmain:>+8.0f}  (689 更瘦→压制弱，主干输)")
    print(f"  血瓶 raw:        718={bd718['potion_raw']:>9.0f}  689={bd689['potion_raw']:>9.0f}"
          f"  Δ={dpot:>+8.0f}  (689 地上多留血瓶)")
    print(f"  手里钥匙:        718={bd718['key_in_hand']:>9.0f}  689={bd689['key_in_hand']:>9.0f}"
          f"  Δ={bd689['key_in_hand']-bd718['key_in_hand']:>+8.0f}")
    print("\n  地上够得到钥匙(预算门控·{(fid,x,y):守怪损血}):")
    for tag, bd in [("718", bd718), ("689", bd689)]:
        gk = sorted(bd["ground_keys"].items(), key=lambda kv: kv[1])
        print(f"    {tag}: {[(k, round(c)) for k, c in gk]}")
    # 差异钥匙（689 独有/更便宜）= 反超动力来源
    diff_keys = {k: bd689["ground_keys"][k] for k in bd689["ground_keys"]
                 if k not in bd718["ground_keys"]}
    print(f"  689 独有地上钥匙(718 已吃掉/够不到): {[(k, round(c)) for k, c in sorted(diff_keys.items(), key=lambda kv: kv[1])]}")
    cheap_diff = sorted(c for c in diff_keys.values() if c <= 20)
    print(f"  其中便宜(≤20血)守怪损血: {[round(c) for c in cheap_diff]}  → w_key 须 > 此以「净赚」")

    # ── w_key 稳健区间：lower/upper 由【差异钥匙守怪损血】数据驱动 ───────────────────
    cheap_guard = max(cheap_diff) if cheap_diff else 13.0   # 差异便宜钥匙的最贵守怪损血
    wk_lo = round(2 * cheap_guard)          # 净赚≥守血一倍（稳，非 break-even=cheap_guard 脆弱临界）
    wk_hi = round(4 * cheap_guard)          # 上界：保持钥匙为「小资源」，中等守怪(~32)只弱计、贵守怪(48+)≈0
    wk_sel = round((wk_lo + wk_hi) / 2)
    print(f"\n{'='*74}\nw_key 稳健区间（隔离钥匙效应：固定 w_potion=0，看 Δ=Δmain+Δkey）\n{'='*74}")
    print(f"  差异便宜钥匙守怪损血 cheap_guard={cheap_guard:.0f}  脆弱临界(净0)={cheap_guard:.0f}")
    for wk in range(0, 85, 5):
        f718 = fitness(s718, roster, big, zone_fids, w_potion=0.0, w_key=wk)
        f689 = fitness(s689, roster, big, zone_fids, w_potion=0.0, w_key=wk)
        kg718 = sum(max(0.0, wk - c) for c in bd718["ground_keys"].values())
        kg689 = sum(max(0.0, wk - c) for c in bd689["ground_keys"].values())
        mark = "  ←区间" if wk_lo <= wk <= wk_hi else ""
        print(f"  w_key={wk:>3}  key地上718={kg718:>6.0f} 689={kg689:>6.0f}"
              f"  Δkey地上={kg689-kg718:>+7.0f}  Δtotal(wp=0)={f689-f718:>+8.0f}{mark}")
    print(f"  稳健区间 [{wk_lo}, {wk_hi}]：下界=2×cheap_guard(净赚≥守血一倍·避 break-even {cheap_guard:.0f})；"
          f"上界=4×cheap_guard(钥匙保持小资源)")
    print(f"★ 选定 w_key = {wk_sel}（中值）")

    # ── w_potion 稳健区间：固定 w_key=wk_sel，找 689 稳稳 > 718 ─────────────────────
    print(f"\n{'='*74}\nw_potion 稳健区间（固定 w_key={wk_sel}）\n{'='*74}")
    wins = []
    for i in range(0, 31):
        w = round(0.1 * i, 2)
        f718 = fitness(s718, roster, big, zone_fids, w_potion=w, w_key=wk_sel)
        f689 = fitness(s689, roster, big, zone_fids, w_potion=w, w_key=wk_sel)
        d = f689 - f718
        if d > 0:
            wins.append(w)
        flag = "  689胜" if d > 0 else ""
        if i % 2 == 0 or (0 < d < 60):
            print(f"  w_potion={w:>4}  f718={f718:>9.0f}  f689={f689:>9.0f}  Δ={d:>+8.0f}{flag}")
    # 临界 + 稳健区间（下界=物理锚点 1.0 地上血瓶≈银行HP；上界=血瓶项压过主干前）
    crit = wins[0] - 0.1 if wins else float("nan")
    wp_lo = 1.0
    dom_w = min(abs(bd718["main_equiv_hp"]) / bd718["potion_raw"],
                abs(bd689["main_equiv_hp"]) / bd689["potion_raw"])
    wp_hi = math.floor(dom_w * 10) / 10
    wp_sel = round((wp_lo + wp_hi) / 2, 1)
    print(f"  反超临界≈{crit:.2f}（脆弱）；稳健区间 [{wp_lo}, {wp_hi}]：下界=物理锚点(地上血瓶≈银行HP)、"
          f"上界=血瓶项压过主干生存项临界 {dom_w:.2f} 之下")
    print(f"★ 选定 w_potion = {wp_sel}（中值）")

    # ── 选定 (w_potion, w_key) 下的完整分项对账 ─────────────────────────────────────
    print(f"\n{'='*74}\n完整分项对账 @ w_potion={wp_sel}, w_key={wk_sel}, big={big}\n{'='*74}")
    for tag, s in [("718(耗尽)", s718), ("689(高潜力)", s689)]:
        bd = fitness_breakdown(s, roster, big, zone_fids, w_potion=wp_sel, w_key=wk_sel)
        print(f"\n── {tag} ──")
        print(f"  HP（主干基底）              = {bd['hp']:>10.1f}")
        print(f"  攻防压制 −Σcost             = {bd['atk_def_suppress']:>10.1f}")
        print(f"  ┗ 主干 equiv_hp             = {bd['main_equiv_hp']:>10.1f}")
        print(f"  血瓶 raw / 项               = {bd['potion_raw']:>10.1f} / {bd['potion_term']:>10.1f}")
        print(f"  钥匙手里 {bd['key_in_hand']}把 / 已兑现项     = {bd['key_realized']:>10.1f}")
        print(f"  钥匙地上 项(Σmax(0,wk−守血)) = {bd['key_ground']:>10.1f}")
        print(f"  钥匙家底 合计               = {bd['key_term']:>10.1f}")
        print(f"  通关项 win                  = {bd['win']:>10.1f}")
        print(f"  ── 合计 total               = {bd['total']:>10.1f}")

    f718 = fitness(s718, roster, big, zone_fids, w_potion=wp_sel, w_key=wk_sel)
    f689 = fitness(s689, roster, big, zone_fids, w_potion=wp_sel, w_key=wk_sel)
    print(f"\n★ fitness(689)={f689:.1f}  vs  fitness(718)={f718:.1f}  →  Δ={f689-f718:+.1f}  "
          f"{'✓ 689 胜' if f689 > f718 else '✗ 689 未胜'}")
    print(f"  反超分解：Δmain={dmain:+.0f}（输） + w_potion·Δ血瓶={wp_sel*dpot:+.0f} + "
          f"Δ钥匙地上={f689-f718-dmain-wp_sel*dpot:+.0f} → 净 {f689-f718:+.0f}")


if __name__ == "__main__":
    main()
