"""【§S47 retrograde V 扩展性验证】把小段验证(b)的 retrograde V 推到更大段。
段：mid=中等段{MT8,MT9,MT10}（起点=首进MT9 tok493 未拿盾·goal=seam MT10(1,10)）；
    redkey=红钥全段9层（起点=铁盾 tok454·goal=红钥 MT8(10,2)·REAL_LEG_FLOORS）。
验：① retrograde V 算得动吗（前向穷尽撞 cap 吗）② 后向 Pareto 传播爆吗（节点/边/耗时）
    ③ beam 用 V 当 score_fn 出口 HP/ATK（红钥段有 ATK headroom·到 27 没）
    ④ fly 有用吗（fly=开/关两文件对照 V[start]/出口）⑤ fly 死循环吗（看 gen 暴涨/hit_cap）
两种结果都有意义：扛住=retrograde V 可扩展（→(d)大段可行）；爆/撞 cap=（d)穷尽大段不可行（→验(b)廉价近似）。
改探针·不碰产品码（forward_enumerate/retrograde/search_quotient 全复用·beam_score_fn 现成钩子）。
用法：python -u analysis/seg_retrograde_v_scale.py --segment {mid,redkey} [--enable-fly] [--max-states N] [--beam-k a,b] [--skip-beam]
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_retrograde_v_probe import (forward_enumerate, retrograde, vkey,   # noqa: E402
                                              fmt_vec, FLY_ATTRS, DISTINGUISH_DOORS)
from analysis.seam_astar_smoke import first_enter_mt9                                 # noqa: E402
from analysis.dir2_redkey_pathloss_beam import (replay_to_token, make_seg_step,       # noqa: E402
                                                TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS)
from solver.quotient import search_quotient, _qfp, _free_cells, value_vector          # noqa: E402

SEG = {
    "mid": dict(name="中等段{MT8,MT9,MT10}",
                start=lambda: first_enter_mt9()[0],
                goal=("MT10", 1, 10),
                allowed=["MT8", "MT9", "MT10"],
                beam_ks=[24, 100]),
    "redkey": dict(name="红钥全段(9层)",
                   start=lambda: replay_to_token(TOK_SHIELD),
                   goal=REDKEY_CELL,
                   allowed=REAL_LEG_FLOORS,
                   beam_ks=[200, 400]),
}


def run_beam(start, goal, step_fn, beam_k, score_fn, enable_fly, max_states, tag):
    fly_attrs = FLY_ATTRS if enable_fly else None
    t0 = time.time()
    res = search_quotient(start, goal, step_fn, max_states=max_states,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=DISTINGUISH_DOORS,
                          enable_fly=enable_fly, fly_attrs=fly_attrs,
                          beam_score_fn=score_fn, beam_diversity="stairs")
    secs = time.time() - t0
    print(f"\n  ── beam_k={beam_k} · {tag} · {secs:.1f}s · found={res.found} "
          f"distinct_fp={res.distinct_fingerprints} cut={res.beam_cut_total} "
          f"hit_cap={res.hit_cap}", flush=True)
    if not res.found:
        print("     ✗ 没搜通", flush=True)
        return None
    fr = res.goal_frontier
    bh = max(fr, key=lambda v: v.get("hp", 0))
    ba = max(fr, key=lambda v: (v.get("atk", 0), v.get("def", 0)))
    print(f"     出口前沿 {len(fr)} 点 | max-HP: {fmt_vec(bh)} | max-ATK: {fmt_vec(ba)}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", choices=list(SEG), required=True)
    ap.add_argument("--enable-fly", action="store_true")
    ap.add_argument("--max-states", type=int, default=2_000_000)
    ap.add_argument("--beam-k", type=str, default="")
    ap.add_argument("--skip-beam", action="store_true",
                    help="只跑阶段1+2（前向穷尽算V+后向传播），跳过阶段3 beam 对照")
    args = ap.parse_args()
    cfg = SEG[args.segment]
    flytag = "开" if args.enable_fly else "关"

    print("=" * 80)
    print(f"§S47 retrograde V 扩展性：{cfg['name']}  fly={flytag}  max_states={args.max_states}")
    print("=" * 80, flush=True)

    start = cfg["start"]()
    h = start.hero
    print(f"起点 = {start.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_}")
    print(f"目标 = {cfg['goal']}  段楼层({len(cfg['allowed'])}) = {cfg['allowed']}", flush=True)
    seg_step = make_seg_step(cfg["allowed"])

    # ── 阶段1：前向穷尽枚举 + 转移图（撞 cap = 算 V 太贵的证据）──
    print("\n[阶段1] 前向穷尽枚举 + 记录转移图 ...", flush=True)
    t0 = time.time()
    g = forward_enumerate(start, cfg["goal"], seg_step, args.max_states, args.enable_fly)
    t_fwd = time.time() - t0
    print(f"  耗时 {t_fwd:.1f}s | 节点={g['n']} 边={g['n_edges']} | distinct_fp={g['distinct_fp']} "
          f"| 生成={g['gen']} | hit_cap={g['hit_cap']}", flush=True)
    print(f"  各层指纹 {dict(g['fp_by_floor'])}", flush=True)
    print(f"  goal-capable 节点数={len(g['goal_hp'])}", flush=True)
    if g["hit_cap"]:
        print("  ⚠⚠ 前向枚举撞 cap → V 不完整(非真 H*)。这本身=（d)穷尽在本段算 V 太贵的证据；"
              "下方 beam 仍用此部分 V 看相对效果。", flush=True)

    # ── 阶段2：后向 retrograde V（Pareto max 标签传播）──
    print("\n[阶段2] 后向 retrograde V（max 标签传播）...", flush=True)
    t0 = time.time()
    V, pops = retrograde(g["succ"], g["goal_hp"], g["n"])
    t_back = time.time() - t0
    v_start = V[0]
    hstar = max(g["goal_hp"].values()) if g["goal_hp"] else None
    print(f"  耗时 {t_back:.2f}s | 松弛 pops={pops}", flush=True)
    print(f"  ★V[start]={v_start} | 出口 max-hp={hstar}", flush=True)

    # 穷尽出口 ground truth（反查 node 的 vkey 拿 atk/def）──③ ATK headroom
    id2node = {i: nd for nd, i in g["node_id"].items()}
    goal_vecs = [dict(id2node[nid][1]) for nid in g["goal_hp"]]
    if goal_vecs:
        gh = max(goal_vecs, key=lambda v: v.get("hp", 0))
        ga = max(goal_vecs, key=lambda v: (v.get("atk", 0), v.get("def", 0)))
        print(f"  穷尽出口 max-HP : {fmt_vec(gh)}", flush=True)
        print(f"  穷尽出口 max-ATK: {fmt_vec(ga)}   ← ③看 ATK 到没到 27(红钥段有 headroom)", flush=True)

    if args.skip_beam:
        print("\n" + "=" * 80)
        print("--skip-beam → 跳过阶段3 beam 对照（本次只验前向穷尽算 V + 后向传播是否爆）", flush=True)
        print("=" * 80, flush=True)
        return

    # ── 阶段3：路线盲 vs retrograde V 当 beam_score_fn ──
    print("\n" + "=" * 80)
    print("[阶段3] 窄 beam 对照：路线盲 vs retrograde V", flush=True)
    print("=" * 80, flush=True)
    v_table = {nd: V[i] for nd, i in g["node_id"].items()}
    miss = [0]

    def v_score(state):
        nd = (_qfp(state, _free_cells(state), DISTINGUISH_DOORS), vkey(value_vector(state)))
        r = v_table.get(nd)
        if r is None:
            miss[0] += 1
            return float(state.hero.hp)
        return float(r)

    ks = [int(x) for x in args.beam_k.split(",") if x.strip()] or cfg["beam_ks"]
    for bk in ks:
        print(f"\n{'#' * 70}\n# beam_k = {bk}\n{'#' * 70}", flush=True)
        run_beam(start, cfg["goal"], seg_step, bk, None, args.enable_fly, args.max_states,
                 "路线盲(equiv_hp)")
        miss[0] = 0
        run_beam(start, cfg["goal"], seg_step, bk, v_score, args.enable_fly, args.max_states,
                 "★retrograde V")
        print(f"     [v_table miss={miss[0]}（撞 cap 时 miss 会多·回退当前血）]", flush=True)

    print("\n" + "=" * 80)
    print("【判读】① 阶段1 hit_cap=False→V 算得动；True→（d)穷尽太贵。"
          "② 阶段2 耗时/pops 小→后向传播没爆。", flush=True)
    print("        ③ 穷尽出口 max-ATK 到 27 没。④ fly：对照 fly=开/关两文件 V[start]/出口。"
          "⑤ fly 死循环：看 fly=开 生成数是否暴涨+hit_cap。", flush=True)
    print("=" * 80, flush=True)


if __name__ == "__main__":
    main()
