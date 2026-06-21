# -*- coding: utf-8 -*-
"""§S63 墙2 诊断探针（只读·零产品码改动）

§S62 全跑结论：墙1(攒 ATK27)=lookahead 解了·墙2(把态走到红钥门 MT8(10,2))=没解·最优态爬 MT10。
本探针回答一个决定方案的问题：墙2 是【主键剪】还是【末键剪】？

  · 主键剪 = MT8 态的 potential_atk(主键)在"去红钥门"vs"上 MT10"两方向【不同】→ 主键先分胜负
    → 距离引导加末键【救不了】(§S60 教训)·须配 atk 主键饱和(玩家临界点洞察)。
  · 末键剪 = 两方向 potential_atk【打平】→ 落末键 hp−Φ+kc 决定 → 距离引导加末键【能救】。

关键代码事实(读出·非猜)：nearest_untaken_gem 只看【当前层】未拿 gem(_s62:76-77)。
  → MT8 的 gem MT8(4,10) 一旦拿掉·MT8 态本层无未拿 gem·potential_atk 退化为当前 atk(跨层不看 MT10 的 gem)。
  → 若分岔点 MT8 gem 已拿·两方向 pa 都退化=打平=末键剪。本探针实测这个退化比例 + 末键为何偏 MT10。

做法：用 §S62 的 score_fn 跑【小预算】run_full·score_fn 外包一层只读记录器·
      捞 MT8 上 atk≥26 的真实态·统计 pa 退化 + 末键 vs 到红钥门距离的关系。
"""
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis._s62_lookahead_full import (                                  # noqa: E402
    setup, make_score_fn, nearest_untaken_gem, potential_atk_prod,
    REDKEY_CELL, REDGEMS, GEM_DETOUR, MULT, BEAM_K, _fmt,
)
from analysis.smart_phi_s53_beam import run_full, key_credit                # noqa: E402
from analysis.dir2_redkey_pathloss_beam import make_seg_step, REAL_LEG_FLOORS  # noqa: E402
from analysis.route_aware_phi_probe import _is_cleared                      # noqa: E402

L = 8
MAX_STATES = 400_000          # ≈10min(§S62 0.74h/1.8M)·够 beam 爬到 MT8 atk26/27 态


def manhattan(state, cell):
    if state.current_floor != cell[0]:
        return None
    return abs(state.hero.x - cell[1]) + abs(state.hero.y - cell[2])


def main():
    t0 = time.time()
    start, phi_loss, diag = setup()
    seg = make_seg_step(REAL_LEG_FLOORS)
    base_score = make_score_fn(phi_loss, seg, L, MULT)
    print(f"setup 就绪 {time.time()-t0:.1f}s · 起点 {_fmt(start)} · L={L} max_states={MAX_STATES}", flush=True)
    print(f"红钥门(goal)={REDKEY_CELL}  MT8 的 gem={GEM_DETOUR}", flush=True)

    # ── 只读记录器：包 score_fn·捞 MT8 上 atk≥26 的态(去重) ──
    seen = set()
    recs = []          # MT8 atk≥26 态
    mt10_recs = []     # MT10 对照

    def rec_score(state):
        v = base_score(state)            # 原 score 照算·零行为改变
        h = state.hero
        f = state.current_floor
        if h.atk >= 26 and f in ("MT8", "MT10"):
            fp = (f, h.x, h.y, h.atk, h.def_, h.hp,
                  h.keys.get("yellowKey", 0), h.keys.get("blueKey", 0))
            if fp not in seen:
                seen.add(fp)
                phi = phi_loss(state)
                kc = key_credit(h, MULT)
                tgt = nearest_untaken_gem(state)
                pa = potential_atk_prod(state, seg, L)
                row = dict(f=f, x=h.x, y=h.y, atk=h.atk, dv=h.def_, hp=h.hp,
                           mt8gem=_is_cleared(state, GEM_DETOUR),
                           tgt=tgt, pa=pa, phi=phi, kc=kc,
                           tail=h.hp - phi + kc,
                           man_red=manhattan(state, REDKEY_CELL))
                (recs if f == "MT8" else mt10_recs).append(row)
        return v

    res = run_full(start, REDKEY_CELL, REAL_LEG_FLOORS, BEAM_K, MAX_STATES, rec_score, diag,
                   enable_fly=True)
    print(f"\n跑完 found={res.found} 耗时={res._secs:.1f}s expanded={res.states_expanded} "
          f"generated={res.states_generated} hit_cap={res.hit_cap}", flush=True)

    print("\n" + "=" * 92)
    print(f"§S63 墙2 诊断 · 捞到 MT8 atk≥26 态 {len(recs)} 个 · MT10 atk≥26 态 {len(mt10_recs)} 个")
    print("=" * 92)

    if not recs:
        print("⚠ 没捞到 MT8 atk≥26 态（预算太小没爬到）→ 加大 MAX_STATES 重跑")
        return

    # ── 主键退化统计（墙2 = 主键剪 还是 末键剪 的核心判据）──
    n = len(recs)
    n_mt8gem = sum(1 for r in recs if r["mt8gem"])
    n_tgt_none = sum(1 for r in recs if r["tgt"] is None)
    n_pa_eq = sum(1 for r in recs if r["pa"] == r["atk"])
    n_pa_gt = sum(1 for r in recs if r["pa"] > r["atk"])
    print("\n[A] 主键 potential_atk 退化情况（决定主键剪 vs 末键剪）")
    print(f"   MT8 的 gem 已拿的态：{n_mt8gem}/{n}  ({100*n_mt8gem/n:.0f}%)")
    print(f"   nearest_untaken_gem=None(本层无未拿gem·pa退化)：{n_tgt_none}/{n}  ({100*n_tgt_none/n:.0f}%)")
    print(f"   pa==atk(主键退化·不分方向)：{n_pa_eq}/{n}  ({100*n_pa_eq/n:.0f}%)")
    print(f"   pa> atk(主键仍朝本层gem升)：{n_pa_gt}/{n}  ({100*n_pa_gt/n:.0f}%)")
    verdict = "末键剪(主键退化打平·距离引导加末键能救)" if n_pa_eq >= 0.7 * n \
        else "主键剪(主键仍分方向·距离引导救不了·须配 atk 饱和)" if n_pa_gt >= 0.5 * n \
        else "混合(部分态主键还在升·须看分岔点·见 [B])"
    print(f"   → 判定：{verdict}")

    # ── 末键 vs 到红钥门距离：beam 是否在淘汰"靠近红钥门"的态 ──
    print("\n[B] 末键 hp−Φ+kc vs 到红钥门曼哈顿距离（man_red）的关系")
    print("    （若靠近红钥门 man_red 小的态末键【更低】→ beam 淘汰它们 → 距离引导正好纠正）")
    by_dist = sorted([r for r in recs if r["man_red"] is not None], key=lambda r: r["man_red"])
    if by_dist:
        near = by_dist[:max(1, len(by_dist)//4)]      # 最靠红钥门 1/4
        far = by_dist[-max(1, len(by_dist)//4):]      # 最远 1/4
        print(f"   最靠红钥门 1/4（man_red≈{near[0]['man_red']}~{near[-1]['man_red']}）：均末键={sum(r['tail'] for r in near)/len(near):.0f}")
        print(f"   最远红钥门 1/4（man_red≈{far[0]['man_red']}~{far[-1]['man_red']}）：均末键={sum(r['tail'] for r in far)/len(far):.0f}")

    # ── score 最高的几个 MT8 态长啥样（beam 真正留住的）──
    print("\n[C] beam 末键最高的 5 个 MT8 态（这些被留住·看它们离红钥门多远）")
    print(f"   {'(x,y)':<9} {'atk':>3} {'def':>3} {'hp':>5} {'mt8gem':>6} {'pa':>3} {'man_red':>7} {'tail':>7}")
    for r in sorted(recs, key=lambda r: r["tail"], reverse=True)[:5]:
        mr = r["man_red"] if r["man_red"] is not None else -1
        print(f"   ({r['x']:>2},{r['y']:>2})  {r['atk']:>3} {r['dv']:>3} {r['hp']:>5} "
              f"{str(r['mt8gem']):>6} {r['pa']:>3} {mr:>7} {r['tail']:>7.0f}")

    # ── 距离引导标定：加 −W·man_red 后·最靠红钥门的态能否进末键 top（粗看·BFS 留下一步）──
    print("\n[D] 距离引导粗标定（曼哈顿先看方向·BFS 真实路距留实现阶段）")
    if by_dist:
        red_state = by_dist[0]               # 最靠红钥门的态
        base_rank = sorted(recs, key=lambda r: r["tail"], reverse=True).index(red_state) + 1
        print(f"   最靠红钥门的态 (x{red_state['x']},y{red_state['y']}) man_red={red_state['man_red']} "
              f"原末键 rank={base_rank}/{n}")
        for W in (5, 10, 20, 30, 50):
            def keyd(r):
                mr = r["man_red"] if r["man_red"] is not None else 999
                return r["tail"] - W * mr
            rank = sorted(recs, key=keyd, reverse=True).index(red_state) + 1
            print(f"     W={W:>3}: rank={rank}/{n}")

    print("\n" + "=" * 92)
    print("判定小结：[A] 看墙2 是主键剪/末键剪 → 决定要不要 atk 饱和；[B][C] 看末键是否反向淘汰近门态；")
    print("         [D] 看距离引导多大 W 能把近门态提进 beam。BFS 真实路距留方案落地阶段。")
    print("=" * 92)


if __name__ == "__main__":
    main()
