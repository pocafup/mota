"""【§S23 步3-5·过夜大跑 launcher（A/B 双机参数化）】34 块候选 pool 上跑 GA，配成「玩家起床手动
Ctrl-C 停、停时已跑代数都有效、截止最优解可导出」。不碰 build_min_pool（产品涌现红线）——34 块 pool
在本脚本内就地重建（复刻已被玩家拍过的统一判据·assert 34），喂给现成 run_ga。

★§S23 步5 两机分工（玩家 2026-06-15 拍板·治昨晚 34 块 gen2 塌的早熟）：
  · 机器A=长基因/大 pop 治早熟（看大 pop 修早熟后长基因能否搜出比白天 7 块 -1002 更深的解）；
  · 机器B=短基因（--maxlen 封短·看 34 块里精炼短组合能否超过白天 7 块短解 -1002）。
  两机【同 git commit】（同 fitness 尺才能比）、各自本地持久暖桶、各自每代落盘 → 睡醒同尺取高。

早熟修法 = 只改【GA 进化机器超参/多样性】（封板件 fitness/decode/navigate/detect 一字不改·beam 零影响）：
  · --pop 大（机器A·抗早熟靠群体规模）；
  · --mut N（mutations_per_child·每后代复合 N 次单点变异=更大变异步长维持多样性）；
  · --immig M（random_immigrants·每代精英后注入 M 条全新随机基因=抗种群塌缩·gen2 收敛的直接解药）；
  · --maxlen L（基因长度上限·机器B 短基因）。四旋钮默认=原版行为（字节级零回归·见 tests/test_ga_loop）。

落盘/日志（tag 驱动文件名·两机不互踩）：
  · python -u + 逐 eval/逐代写 analysis/overnight_{tag}.log → 玩家睡醒看全过程；
  · ★每代原子落盘 analysis/overnight_{tag}_best.txt（防 Ctrl-C 丢）：含基因/含盾否/剑实际进包否/真实
    进包序 normalized/三方对照 fitness(689)(718)/解码终态(含 tokens)。Ctrl-C 干净停（最新一代已落盘）。
  · --persistent 暖桶：34 块深目标首跑冷算慢（前几代尤其慢）、无妨、逐代可见。

跑法（两机各一条·见 §S23 步5 方案）：
  机器A: python -u analysis/ga_overnight_34.py --tag A --pop 40 --gen 200 --mut 2 --immig 6 --cross 0.6 --seed 20260615 --persistent
  机器B: python -u analysis/ga_overnight_34.py --tag B --pop 20 --gen 300 --maxlen 8 --immig 3 --cross 0.6 --seed 20260616 --persistent
红线：大 gen 玩家停、逐代日志可见、每代落盘防丢、persistent、不改 build_min_pool、早熟修法只动 GA 超参。
"""
import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from ga_loop import (build_harness, run_ga, make_decode_fitness_eval,        # noqa: E402
                     _decode_with_order, _taken)
from solver.fitness import fitness                                            # noqa: E402
from vzone import _zone_attr_gems                                             # noqa: E402
from block_targets import build_block_index                                   # noqa: E402
from ga_invalid_rate_34_diag import _triage_gems                             # noqa: E402（同钥匙口径宝石三分）


def _parse_args():
    p = argparse.ArgumentParser(description="34 块 pool 过夜大跑（A/B 双机参数化）")
    p.add_argument("--tag", default="", help="机器标签（驱动 overnight_{tag}.log/_best.txt·两机不互踩）")
    p.add_argument("--pop", type=int, default=15, help="种群大小（机器A 大 pop 抗早熟）")
    p.add_argument("--gen", type=int, default=150, help="代数（设大·玩家起床 Ctrl-C 停）")
    p.add_argument("--cross", type=float, default=0.6, help="交叉率 crossover_rate")
    p.add_argument("--mut", type=int, default=1, help="mutations_per_child（每后代复合变异次数·>1 维持多样性）")
    p.add_argument("--immig", type=int, default=0, help="random_immigrants（每代注入新随机基因数·抗塌缩）")
    p.add_argument("--maxlen", type=int, default=None, help="基因长度上限（机器B 短基因·缺省=不限）")
    p.add_argument("--minlen", type=int, default=None, help="基因长度下限（机器A 长基因区间·缺省=不限）")
    p.add_argument("--elite", type=int, default=2, help="精英保留数")
    p.add_argument("--k", type=int, default=3, help="锦标赛 k")
    p.add_argument("--seed", type=int, default=20260613, help="随机种子（两机用不同 seed 探不同区域）")
    p.add_argument("--persistent", action="store_true", help="navigate_to 跨 run 持久暖桶")
    return p.parse_args()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = _parse_args()
    persistent = args.persistent
    population, generations = args.pop, args.gen
    suffix = f"_{args.tag}" if args.tag else ""
    LOG = ROOT / "analysis" / f"overnight{suffix}.log"
    BEST = ROOT / "analysis" / f"overnight{suffix}_best.txt"

    logf = open(LOG, "w", encoding="utf-8", buffering=1)

    def log_line(msg=""):
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    log_line(f"=== 34 块过夜大跑 启动 {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    log_line(f"组装电池组（build_harness · persistent={persistent}）…")
    t0 = time.time()
    H = build_harness(persistent=persistent)
    start, zone, step = H["start"], H["zone"], H["step"]
    roster_fit, big, zone_fids = H["roster_fit"], H["big"], H["zone_fids"]
    decode_cache = H["decode_cache"]
    log_line(f"  电池组就绪 {time.time() - t0:.1f}s")

    # ── 34 块候选 pool 就地重建（复刻统一判据·不碰 build_min_pool）──
    big_cells, ranked, cands = H["big_cells"], H["ranked"], H["cands"]
    info_key = H["info_key"]
    afford, colors = info_key["afford"], info_key["colors"]
    drp_by_cell = {c: drp for (drp, c, _da, _dd) in ranked}
    gem_dadd = _zone_attr_gems(zone)
    gem_tri = _triage_gems(start, zone_fids, afford, zone)

    cand_gems = sorted(c for c, br in gem_tri.items()
                       if br == "②" and c not in big_cells and drp_by_cell.get(c, 0) > 0)
    cand_keys = sorted(cands)
    cand_keys_set = set(cand_keys)
    cand_cells = set(sorted(big_cells)) | set(cand_gems) | set(cand_keys)

    fids = sorted(set(zone_fids) | {c[0] for c in cand_cells})
    block_index = build_block_index(fids)
    c2b = block_index["cell_to_block"]
    cand_cells = [c for c in cand_cells if c in c2b]
    block_markers = {}
    for c in sorted(cand_cells):
        block_markers.setdefault(c2b[c], set()).add(c)
    block_markers = {b: frozenset(cs) for b, cs in block_markers.items()}
    pool = sorted(block_markers, key=lambda b: (b[0], b[1]))
    block_cells = {b: block_index["block_cells"][b] for b in pool}
    assert len(pool) == 34, f"pool 块数 {len(pool)} ≠ 34（判据/数据漂移·须核对再跑）"

    sword_c = next(c for (_d, c, da, _dd) in ranked if c in big_cells and da > 0)
    shield_c = next(c for (_d, c, _da, dd) in ranked if c in big_cells and dd > 0)
    sword_block, shield_block = c2b[sword_c], c2b[shield_c]

    def role_of(b):
        parts = []
        for c in sorted(block_markers[b]):
            if c in big_cells:
                da, _dd = gem_dadd.get(c, (0, 0))
                parts.append("剑" if da > 0 else "盾")
            elif c in cand_keys_set:
                parts.append(f"钥{colors.get(c, '?')}")
            else:
                da, _dd = gem_dadd.get(c, (0, 0))
                parts.append("宝攻" if da > 0 else "宝防")
        return "+".join(parts) or "?"

    # ── eval_fn（34 pool·禁区开·复用持久暖桶）+ 三方对照基线 ──
    eval_fn, _dc = make_decode_fitness_eval(
        start, zone, step, roster_fit, big, zone_fids,
        decode_cache=decode_cache, block_markers=block_markers, block_cells=block_cells)
    f689 = fitness(H["s689"], roster_fit, big, zone_fids, w_potion=1.5, w_key=39.0)
    f718 = fitness(H["s718"], roster_fit, big, zone_fids, w_potion=1.5, w_key=39.0)

    seeds = [[shield_block], [sword_block]]        # 短有效种子（长度 1 必有效·保 gen0 有起点）

    maxlen_str = "不限" if args.maxlen is None else str(args.maxlen)
    minlen_str = "不限" if args.minlen is None else str(args.minlen)
    log_line("")
    log_line("=" * 70)
    log_line(f"机器 tag={args.tag or '(无)'}  pool=34 块  pop={population}  gen={generations}  "
             f"交叉={args.cross}  精英{args.elite}  k{args.k}  seed={args.seed}")
    log_line(f"  早熟旋钮: 长度区间=[{minlen_str}..{maxlen_str}]  mut/child={args.mut}  随机移民={args.immig}/代  "
             f"(默认 1/0/不限=原版·>则抗早熟·注入种子不受下限约束)")
    log_line(f"  剑块={sword_block}[{role_of(sword_block)}]  盾块={shield_block}[{role_of(shield_block)}]")
    log_line(f"  注种子: {[ [role_of(b) for b in s] for s in seeds ]}")
    log_line(f"  三方对照基线: fitness(689)={f689:.1f}  fitness(718)={f718:.1f}  (白天7块GA到 -1002)")
    log_line(f"  ★最优解逐代落盘 → {BEST}（防 Ctrl-C 丢）  日志 → {LOG}")
    log_line("=" * 70)
    log_line("")

    # ── 逐 eval 日志（gen0 冷算前即见活动·玩家确认在跑）──
    eval_count = [0]

    def eval_logged(gene):
        t = time.time()
        f = eval_fn(gene)
        eval_count[0] += 1
        log_line(f"    eval#{eval_count[0]:4d}  len={len(gene):2d}  fit={f:14.1f}  {time.time() - t:5.0f}s")
        return f

    # ── 最优解原子落盘（防 Ctrl-C 丢）──
    def dump_best(gen, gene, fit, tag=""):
        tokens, final, normalized, verdict = _decode_with_order(
            gene, start, zone, step, decode_cache,
            block_markers=block_markers, block_cells=block_cells)
        fh = final.hero
        shield_in = shield_block in gene
        sword_in = sword_block in gene
        shield_got = _taken(final, shield_c)
        sword_got = _taken(final, sword_c)
        sword_norm = (normalized.index(sword_block) + 1) if sword_block in normalized else None
        lines = [
            f"截止最优解  gen={gen}{('  ['+tag+']') if tag else ''}  {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"最优 fitness = {fit:.1f}   (对照 fitness(689)={f689:.1f} 差={fit - f689:+.1f}  "
            f"fitness(718)={f718:.1f} 差={fit - f718:+.1f})",
            f"序列有效 = {'是' if not verdict['invalid'] else '否(全种群无可实现排序?)'}   "
            f"导航腿={verdict['navigated']}  最深层下标={verdict['depth']}",
            f"含盾(在基因) = {'是' if shield_in else '否'}    盾实际进包(终态) = {'是' if shield_got else '否'}",
            f"含剑(在基因) = {'是' if sword_in else '否'}    剑实际进包(终态) = {'是' if sword_got else '否'}"
            + (f"   剑进包序=第{sword_norm}个(共{len(normalized)}块进包)" if sword_norm
               else "   (剑块不在基因·块模式normalized不追非基因块·看终态'实际进包')"),
            "",
            f"基因（{len(gene)} 块·执行序）:",
        ]
        for b in gene:
            tag2 = "  ← 盾" if b == shield_block else ("  ← 剑" if b == sword_block else "")
            lines.append(f"    {b}  [{role_of(b)}]{tag2}")
        lines.append("")
        lines.append(f"真实进包序 normalized（{len(normalized)} 块·含顺路吸·按真实拿到先后）:")
        for b in normalized:
            tag2 = "  ← 盾" if b == shield_block else ("  ← 剑" if b == sword_block else "")
            lines.append(f"    {b}  [{role_of(b)}]{tag2}")
        lines.append("")
        lines.append(f"解码终态: {final.current_floor}({fh.x},{fh.y})  HP={fh.hp}  ATK={fh.atk}  "
                     f"DEF={fh.def_}  keys={dict(fh.keys)}  tokens={len(tokens)}")
        tmp = str(BEST) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, BEST)

    # ── 逐代回调：落盘最优 + 写摘要 ──
    t_run = time.time()

    def on_gen(gl):
        contains_shield = shield_block in gl.best_individual
        dump_best(gl.gen, gl.best_individual, gl.best_fitness)
        elapsed = time.time() - t_run
        log_line(f"━━ gen {gl.gen:3d}  best={gl.best_fitness:14.1f}  len={len(gl.best_individual):2d}  "
                 f"含盾={'Y' if contains_shield else 'N'}  无效个体={gl.n_invalid:2d}  "
                 f"uniq_evals={gl.n_unique_evals:4d}  spread=[{gl.spread_lo:.0f}..{gl.spread_hi:.0f}]  "
                 f"累计{elapsed / 60:.1f}min  → 已落盘最优解")

    log_line(f"开跑 run_ga（gen0 冷算约 {population} 条·首条≈深目标冷算·稍候即见 eval#1）…")
    try:
        res = run_ga(pool, eval_logged, population=population, generations=generations,
                     tournament_k=args.k, elite=args.elite, crossover_rate=args.cross,
                     inject=seeds, seed=args.seed, log=on_gen,
                     max_len=args.maxlen, min_len=args.minlen, mutations_per_child=args.mut,
                     random_immigrants=args.immig)
        log_line("")
        log_line(f"=== run_ga 跑完 gen{generations}（已收敛或代数用尽）===")
        dump_best(generations - 1, res.best_individual, res.best_fitness, tag="FINAL-跑完")
        log_line(f"全程最优 fitness={res.best_fitness:.1f}  uniq_evals={res.n_unique_evals}  "
                 f"总耗时{(time.time() - t_run) / 60:.1f}min")
    except KeyboardInterrupt:
        log_line("")
        log_line(f"=== Ctrl-C 玩家手动停 {datetime.now():%Y-%m-%d %H:%M:%S} ===")
        log_line(f"  截止最优解已落盘（最新一代）→ {BEST}")
        log_line(f"  累计耗时 {(time.time() - t_run) / 60:.1f}min  共 eval {eval_count[0]} 次")
    finally:
        if hasattr(decode_cache, "stats"):
            log_line(f"  navigate_to 暖桶: 桶={decode_cache.version_tag}  {decode_cache.stats}")
        logf.flush()


if __name__ == "__main__":
    main()
