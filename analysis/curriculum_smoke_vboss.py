"""【§S29 小验证·甲/乙关键判决】gene→seam→查 V_boss 配线 smoke（只读·不碰封板件）。

判决：score = fitness + λ·V_boss。跑 λ=10 与 λ=0(纯 fitness 基线)对照·同 seed·只差 λ。
  · V_boss 评 SEAM(boss 入口 MT10(1,11) 到达态·非中间态瞬时·§S29【二】)：
    gene → _decode_with_order(【不传 final_goal】) 得 term_state(攒攻防自然终态) → base=fitness(term)；
    seam 腿 navigate_to(term, SEAM) 用返回的 reached 布尔判到没到(★不能用红钥末腿 reached_final——楼梯
      格无物品 _taken 恒 False)；reached → search_quotient(seam, MT11 出口, 限{MT10,MT11}, cross_floor,
      beam_k=None, distinguish_doors) 取 res.final_hp 当 V_boss(else 0)；
    seam_state 带 gene 自己的钥匙/红钥(非真存档)→ 没红钥 gene 开不了红门到不了 boss → V_boss=0 是真信号。

报(每组)：①有没有 gene 到达 V_boss>0 的 seam ②最优解 seam 态属性 ATK/DEF/HP/钥匙 + V_boss
  ③λ=10 vs λ=0：λ=10 组 best 的 seam HP/属性是否比 λ=0 更往「能过 boss 的 HP≈700 拐点」靠。
判据(★玩家拍·脚本只出客观数)：任一组有 V_boss>0 → 甲(GA+V_boss)可行；仍全 0(seam 在 zone 已确认排除
  配置假信号·§S29 钉死前提)→ navigate/搜索力瓶颈(GA「选块不带路线」架构锅)→ 上乙(state-centric)。

效率：V_boss memo 键=_nav_key(seam)(导航等价 ⟺ seam 全可变字段相同 ⟹ boss 段逐字段相同·两组共享不重搜)；
  decode_cache 暖桶让两组的 navigate(到 term + 到 seam)近免费；只 reached 的 gene 才搜贵的 boss 段。
用法：python -u analysis/curriculum_smoke_vboss.py --pop 8 --gen 3 --minlen 7 --maxlen 10 --lam 10 --persistent
      冒烟先跑 --pop 2 --gen 1 确认配线通(不崩)，再正式 pop8/gen3。太慢可 --pop 6 --gen 2。
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from ga_loop import build_harness, run_ga, _decode_with_order, _invalid_score   # noqa: E402
from ga_navigate import navigate_to, _nav_key                                   # noqa: E402
from solver.fitness import fitness                                              # noqa: E402
from solver.quotient import search_quotient                                     # noqa: E402
from block_targets import build_block_index                                     # noqa: E402
from vzone import _zone_attr_gems                                               # noqa: E402
from ga_invalid_rate_34_diag import _triage_gems                               # noqa: E402

SEAM = ("MT10", 1, 11)            # boss 入口楼梯格(MT9↔MT10 免费边·在 zone 内·§S29 钉死前提)
BOSS_GOAL = ("MT11", 6, 10)       # boss 段目标(下到 MT11 出口)·复刻 curriculum_scan_vboss 口径
ALLOWED = {"MT10", "MT11"}        # boss 段楼层·离段(回 MT9 等)裁掉
W_POTION, W_KEY = 1.5, 39.0       # fitness 标尺(与 build_harness/test_fitness 同尺·GA 分与 fitness(689) 可比)


def make_seg_step(step):
    """把 V_boss 搜索框在 boss 段：踏出 {MT10,MT11} 的子态置 dead 裁掉(复刻 curriculum_scan_vboss.seg_step)。"""
    def seg_step(state, action):
        ns = step(state, action)
        if ns.current_floor not in ALLOWED:
            ns.dead = True
        return ns
    return seg_step


def _parse_args():
    p = argparse.ArgumentParser(description="§S29 小验证：gene→seam→查 V_boss(λ=10 vs λ=0)")
    p.add_argument("--pop", type=int, default=8)
    p.add_argument("--gen", type=int, default=3)
    p.add_argument("--minlen", type=int, default=7)
    p.add_argument("--maxlen", type=int, default=10)
    p.add_argument("--lam", type=float, default=10.0, help="V_boss 权重(实验组)；对照组固定 λ=0")
    p.add_argument("--seed", type=int, default=20260616)
    p.add_argument("--maxpops", type=int, default=8000, help="seam 腿 navigate_to 弹出护栏")
    p.add_argument("--max-states", dest="max_states", type=int, default=400_000,
                   help="V_boss 段 search_quotient 状态上限(安全网)")
    p.add_argument("--persistent", action="store_true", help="navigate_to 跨 run 持久暖桶")
    return p.parse_args()


def build_pool_13(H):
    """复刻 analysis/ga_overnight_34.py 的 13 块 pool 就地重建(判断4 砍纯钥块·不碰 build_min_pool)。
    返回 (pool, block_markers, block_cells, sword_block, shield_block)。"""
    start, zone, zone_fids = H["start"], H["zone"], H["zone_fids"]
    big_cells, ranked = H["big_cells"], H["ranked"]
    info_key = H["info_key"]
    afford = info_key["afford"]
    drp_by_cell = {c: drp for (drp, c, _da, _dd) in ranked}
    gem_tri = _triage_gems(start, zone_fids, afford, zone)

    cand_gems = sorted(c for c, br in gem_tri.items()
                       if br == "②" and c not in big_cells and drp_by_cell.get(c, 0) > 0)
    cand_cells = set(sorted(big_cells)) | set(cand_gems)

    fids = sorted(set(zone_fids) | {c[0] for c in cand_cells})
    block_index = build_block_index(fids)
    c2b = block_index["cell_to_block"]
    cand_cells = [c for c in cand_cells if c in c2b]
    bm = {}
    for c in sorted(cand_cells):
        bm.setdefault(c2b[c], set()).add(c)
    block_markers = {b: frozenset(cs) for b, cs in bm.items()}
    pool = sorted(block_markers, key=lambda b: (b[0], b[1]))
    block_cells = {b: block_index["block_cells"][b] for b in pool}
    assert len(pool) == 13, f"pool 块数 {len(pool)} ≠ 13(判断4 砍钥后·判据/数据漂移·须核对再跑)"

    sword_c = next(c for (_d, c, da, _dd) in ranked if c in big_cells and da > 0)
    shield_c = next(c for (_d, c, _da, dd) in ranked if c in big_cells and dd > 0)
    return pool, block_markers, block_cells, c2b[sword_c], c2b[shield_c]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = _parse_args()

    print(f"=== §S29 小验证 gene→seam→V_boss  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    print(f"组装电池组(build_harness · persistent={args.persistent})…", flush=True)
    t0 = time.time()
    H = build_harness(persistent=args.persistent)
    start, zone, step = H["start"], H["zone"], H["step"]
    roster_fit, big, zone_fids = H["roster_fit"], H["big"], H["zone_fids"]
    decode_cache = H["decode_cache"]
    red_block = H["red_block"]
    print(f"  电池组就绪 {time.time() - t0:.1f}s", flush=True)

    pool, block_markers, block_cells, sword_block, shield_block = build_pool_13(H)
    seg_step = make_seg_step(step)
    f689 = fitness(H["s689"], roster_fit, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
    f718 = fitness(H["s718"], roster_fit, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
    print(f"  pool=13 块  红钥块={red_block}(不在 pool:{red_block not in pool})  剑块={sword_block} 盾块={shield_block}")
    print(f"  标尺: fitness(689)={f689:.1f}  fitness(718)={f718:.1f}  SEAM={SEAM} BOSS_GOAL={BOSS_GOAL}")
    print(f"  配置: pop={args.pop} gen={args.gen} len=[{args.minlen}..{args.maxlen}] seed={args.seed} "
          f"maxpops={args.maxpops} max_states={args.max_states}\n", flush=True)

    # ── V_boss memo(两组共享·键=_nav_key(seam)：导航等价 ⟹ boss 段逐字段相同·安全)──
    vboss_memo = {}

    def query_vboss(seam_state):
        k = _nav_key(seam_state)
        if k in vboss_memo:
            return vboss_memo[k]
        assert seam_state._single_floor_copy is False, \
            "seam 态须 _single_floor_copy=False(多层安全深拷)否则跨层搜共享引用污染——配线前提破，报玩家"
        res = search_quotient(seam_state, BOSS_GOAL, seg_step, max_states=args.max_states,
                              cross_floor=True, beam_k=None, distinguish_doors=True)
        v = (res.final_hp if res.found else 0, res.found)
        vboss_memo[k] = v
        return v

    def make_eval(lam, records):
        def eval_fn(gene):
            ta = time.time()
            _tokens, term, _norm, verdict = _decode_with_order(    # ★不传 final_goal → term_state(无红钥末腿)
                gene, start, zone, step, decode_cache,
                block_markers=block_markers, block_cells=block_cells)
            if verdict["invalid"]:                                 # §S15 无效序列：复刻 make_decode_fitness_eval·不评 V_boss
                return _invalid_score(verdict)
            base = fitness(term, roster_fit, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
            tb = time.time()
            seam_state, _moves, reached = navigate_to(             # seam 腿(禁区空·像红钥末腿)
                term, SEAM, zone, step, max_pops=args.maxpops, cache=decode_cache)
            tc = time.time()
            v_boss, found = 0, False
            if reached:
                v_boss, found = query_vboss(seam_state)
            td = time.time()
            score = base + lam * v_boss
            sh = seam_state.hero
            records.append(dict(
                gene=list(gene), base=base, reached=reached, score=score,
                seam_hp=(sh.hp if reached else None), seam_atk=(sh.atk if reached else None),
                seam_def=(sh.def_ if reached else None),
                seam_keys=({k: v for k, v in sh.keys.items() if v} if reached else None),
                v_boss=v_boss, vboss_found=found,
                decode_s=tb - ta, nav_s=tc - tb, vboss_s=td - tc))
            return score
        return eval_fn

    seeds = [[shield_block], [sword_block]]    # 注入有效短种子·保 gen0 有起点(不受 minlen 约束)

    def make_log(tag, t_run):
        def on_gen(gl):
            print(f"  [{tag}] gen {gl.gen}  best={gl.best_fitness:14.1f}  len={len(gl.best_individual):2d}  "
                  f"无效={gl.n_invalid}  uniq={gl.n_unique_evals}  累计{(time.time()-t_run)/60:.1f}min", flush=True)
        return on_gen

    def run_one(tag, lam):
        records = []
        print(f"── 跑组 [{tag}] λ={lam} ──", flush=True)
        t_run = time.time()
        res = run_ga(pool, make_eval(lam, records), population=args.pop, generations=args.gen,
                     min_len=args.minlen, max_len=args.maxlen, inject=seeds,
                     seed=args.seed, log=make_log(tag, t_run))
        secs = time.time() - t_run
        return tag, lam, records, res, secs

    runs = [run_one("λ=10", args.lam), run_one("λ=0", 0.0)]

    # ── 报告 ──
    print("\n" + "=" * 78)
    print("【小验证结果·甲/乙判据】★关键 = 有没有任一 gene 到达 V_boss>0 的 seam")
    print("=" * 78)
    any_vboss_pos_global = False
    summary = {}
    for tag, lam, records, res, secs in runs:
        reached = [r for r in records if r["reached"]]
        vpos = [r for r in records if r["v_boss"] > 0]
        any_vboss_pos_global = any_vboss_pos_global or bool(vpos)
        best_rec = next((r for r in records if r["gene"] == list(res.best_individual)), None)
        max_vboss = max((r["v_boss"] for r in records), default=0)
        d_s = sum(r["decode_s"] for r in records)
        n_s = sum(r["nav_s"] for r in records)
        v_s = sum(r["vboss_s"] for r in records)
        summary[tag] = best_rec
        print(f"\n── 组 [{tag}] λ={lam}  耗时 {secs/60:.1f}min({secs:.0f}s)  unique_evals={res.n_unique_evals} ──")
        print(f"  到达 seam(reached) 的 gene: {len(reached)}/{len(records)}")
        print(f"  V_boss>0 的 gene:           {len(vpos)}/{len(records)}    最大 V_boss={max_vboss}")
        print(f"  阶段耗时累计: decode={d_s:.0f}s  nav(到seam)={n_s:.0f}s  V_boss(boss段)={v_s:.0f}s")
        if best_rec is not None:
            print(f"  最优解 best: score={res.best_fitness:.1f}  base(fitness)={best_rec['base']:.1f}  "
                  f"reached_seam={best_rec['reached']}  V_boss={best_rec['v_boss']}(found={best_rec['vboss_found']})")
            if best_rec["reached"]:
                print(f"    └ 最优解 seam 态: HP={best_rec['seam_hp']} ATK={best_rec['seam_atk']} "
                      f"DEF={best_rec['seam_def']} 钥={best_rec['seam_keys']}")
            else:
                print(f"    └ 最优解【未到达 seam】(navigate 送不出可存活 MT10(1,11) 到达态)")
        if vpos:
            top = max(vpos, key=lambda r: r["v_boss"])
            print(f"  ★V_boss>0 最高的 gene: V_boss={top['v_boss']}  seam HP={top['seam_hp']} "
                  f"ATK={top['seam_atk']} DEF={top['seam_def']} 钥={top['seam_keys']}  base={top['base']:.1f}")

    # ── λ=10 vs λ=0 对比(往过 boss 拉?)──
    print("\n" + "-" * 78)
    print("【λ=10 vs λ=0 对比】best seam 态(看 λ=10 是否更往能过 boss 的 HP≈700 拐点靠)")
    print("-" * 78)
    b10, b0 = summary.get("λ=10"), summary.get("λ=0")
    for tag, br in (("λ=10", b10), ("λ=0", b0)):
        if br and br["reached"]:
            print(f"  [{tag}] best seam: HP={br['seam_hp']} ATK={br['seam_atk']} DEF={br['seam_def']} "
                  f"V_boss={br['v_boss']}")
        else:
            print(f"  [{tag}] best 未到达 seam(seam 态属性 N/A)")

    print("\n" + "=" * 78)
    if any_vboss_pos_global:
        print("★判据信号：有 gene 到达 V_boss>0 的 seam → 倾向【甲(GA+V_boss)可行】。详数交玩家拍。")
    else:
        print("★判据信号：两组【全 V_boss=0】(seam 在 zone 已确认排除配置假信号)→ 倾向【上乙(state-centric)】。")
        print("  (即 GA navigate 送不出『能存活打 boss』的 seam 到达态 / gene 没攒够红钥+血——评估非瓶颈、架构是)")
    print("=" * 78)
    print("\n★最终甲/乙由玩家拍(脚本只出客观数)。")


if __name__ == "__main__":
    main()
