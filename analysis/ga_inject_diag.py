"""【GA 第二棒诊断·根因 B 搜索侧修法】三组对照 A/B/C，验【加交叉 + 注入含盾个体】能否搜到/留住含盾解。

背景（docs/handoff.md §S10）：最小 GA(pop12/gen6/纯变异) 爬坡 +872 但最优个体【不拿盾】，诊断=根因 B
（fitness 给含盾 -1488 > 不拿盾 -3729 > ……、排序经玩家游戏知识确认对，fitness 一字不动）。本棒在【搜索侧】
加力度：OX 变体交叉 + 初始种群注入含盾个体，看：
  · 组 A（加交叉·不注入）：光加交叉能不能【自己探到】含盾解？
  · 组 B（加交叉·注入含盾）：注入后 GA 末代最优【还含盾吗】？
      ── 留住并改进 = 纯变异够不到、加力度有效（方向对）；
      ── 又淘汰回不拿盾 = 选择/fitness 有更深洞（矛盾、要回头查）。
  · 组 C（纯变异·基线）：≈第一棒算法形态、pop12/gen8 的可比基线。
三组干净控制变量：同 pop12/gen8/同 seed，唯一变量 = {交叉开关, 注入开关}。
【小规模快侦察】pop12/gen8（非 pop25/gen15）：先用最便宜规模拿方向信号，全规模待方向确认后再付那一小时。
【执行序 B→C→A】先跑最便宜最关键的 B（盾已注入、只看留没留住、冷算少），再 C（纯变异便宜），
A（光交叉现探深盾·最贵）放最后——B/C 结果先落地可见，A 慢也不挡关键诊断。
【可见性硬要求】python -u + reconfigure(line_buffering) + 每代 flush 一行（代号/best/含盾），绝不再盲跑卡 88 字节。

红线：本脚本【只读复用】ga_loop 的 run_ga/build_harness + 封板四零件，fitness 一字不改、beam 零影响。
注入个体先 decode+fitness【自检确实含盾且分合理】再跑三组（防注入了废基因还以为在测注入）。
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))            # ROOT: solver / sim
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extract"))  # ga_loop / ga_decode

from ga_loop import build_harness, run_ga                # noqa: E402
from ga_decode import decode                             # noqa: E402
from solver.fitness import fitness                       # noqa: E402

POP, GEN, SEED, KX = 12, 8, 20260613, 0.7                # 小规模快侦察超参（唯一变量=交叉/注入开关）
WP, WK = 1.5, 39.0                                       # fitness 权重（同 test_fitness / ga_loop.main 标尺）


def _eval_decode(gene, H):
    """decode 基因→终态 + fitness 终评（同 ga_loop.eval_fn 口径、复用共享 decode_cache）。"""
    tokens, final = decode(gene, H["start"], H["zone"], H["step"], cache=H["decode_cache"])
    f = fitness(final, H["roster_fit"], H["big"], H["zone_fids"], w_potion=WP, w_key=WK)
    return final, f, len(tokens)


def _tag(g, meta):
    if g == meta["sword"]:
        return "剑"
    if g == meta["shield"]:
        return "盾"
    if g in meta["keys"]:
        return "钥"
    if g in meta["gems"]:
        return "宝石"
    return "?"


def _has_shield(gene, meta):
    """含盾判定·基因层：GA 是否把盾选进了基因（目标层）。"""
    return meta["shield"] in gene


def _dump_gene(gene, meta, indent="        "):
    for g in gene:
        print(f"{indent}{g}  [{_tag(g, meta)}]")


def _mk_gen_logger(name, meta):
    """run_ga 每代回调：立即 flush 一行「代号/best fitness/含盾/多样性」。
    python -u + line_buffering + 每行 flush 三保险 → 绝不再「卡 88 字节盲跑」。含盾标记在这侧加（run_ga 塔无关）。"""
    tag = name.split()[0]                       # "B"/"C"/"A"

    def _log(gl):
        sh = "★含盾" if meta["shield"] in gl.best_individual else " 无盾"
        print(f"    [{tag}] gen{gl.gen:2d}: best={gl.best_fitness:>10.1f}  {sh}  "
              f"len={len(gl.best_individual):2d}  uniq={gl.n_unique_evals:3d}  "
              f"spread=[{gl.spread_lo:.0f}..{gl.spread_hi:.0f}]", flush=True)

    return _log


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

    print("组装 GA 电池组（build_start 重放 + 标尺 route 回放 + 目标池涌现）…")
    t0 = time.time()
    H = build_harness()
    meta, pool = H["meta"], H["pool"]
    print(f"  电池组就绪 {time.time() - t0:.1f}s")
    print(f"  pool({len(pool)}) = {pool}")
    print(f"  剑={meta['sword']}  盾={meta['shield']}  MT4 五钥={meta['keys']}  宝石={meta['gems']}")

    f689 = fitness(H["s689"], H["roster_fit"], H["big"], H["zone_fids"], w_potion=WP, w_key=WK)
    f718 = fitness(H["s718"], H["roster_fit"], H["big"], H["zone_fids"], w_potion=WP, w_key=WK)

    # ── 注入个体 = §S9 验证 chromosome [盾,MT4六钥,剑] 投影到最小 pool（去深钥 9,2）= [盾,MT4五钥,剑] ──
    inject_ind = [meta["shield"]] + list(meta["keys"]) + [meta["sword"]]
    assert all(g in pool for g in inject_ind) and len(inject_ind) == len(set(inject_ind))

    print("\n" + "=" * 74)
    print("⓪ 注入个体自检（防注入了废基因还以为在测注入）")
    print("=" * 74)
    print(f"  注入基因 = [盾] + MT4 五钥 + [剑] = {inject_ind}")
    t1 = time.time()
    final, f_inj, ntok = _eval_decode(inject_ind, H)
    fh = final.hero
    print(f"  解码终态: {final.current_floor}({fh.x},{fh.y}) HP={fh.hp} ATK={fh.atk} "
          f"DEF={fh.def_} keys={dict(fh.keys)}  tokens={ntok}  (冷算 {time.time() - t1:.1f}s)")
    print(f"  含盾判定: 基因层 shield∈gene={_has_shield(inject_ind, meta)} / "
          f"物理层 DEF={fh.def_}（不拿盾基线 DEF≈11）")
    print(f"  fitness(注入含盾个体) = {f_inj:.1f}")
    print(f"  §S10 锚点对照: 不拿盾≈-3729  <  含盾≈-1488  <  689 骨架≈-725")
    print(f"  真 route 标尺(同 fitness 尺): fitness(689)={f689:.1f}  fitness(718)={f718:.1f}")
    if fh.def_ <= 11:
        print("\n  ❌ 自检不通过：注入个体 DEF 未超过不拿盾基线 11 → 盾没真取到 → 是废基因。中止，不跑三组。")
        return
    print("  ✅ 自检通过：盾真取到（DEF 提升）、fitness 量级在含盾区间 → 注入的是合理含盾个体，开跑三组。")

    # ── 三组对照（同 pop/gen/seed，唯一变量=交叉/注入开关；共享 eval_fn → decode_cache 跨组复用省时）──
    configs = [
        ("B 加交叉·注入含盾", dict(crossover_rate=KX, inject=[list(inject_ind)])),
        ("C 纯变异·基线", dict(crossover_rate=0.0, inject=None)),
        ("A 加交叉·不注入", dict(crossover_rate=KX, inject=None)),
    ]
    results = {}
    for name, cfg in configs:
        print("\n" + "=" * 74)
        print(f"组【{name}】 pop{POP} gen{GEN} k3 elite2 seed{SEED}  cfg={cfg}")
        print("=" * 74)
        t1 = time.time()
        res = run_ga(pool, H["eval_fn"], population=POP, generations=GEN,
                     tournament_k=3, elite=2, seed=SEED,
                     log=_mk_gen_logger(name, meta), **cfg)
        dt = time.time() - t1
        best = res.best_individual
        final, fbest, ntok = _eval_decode(best, H)
        fh = final.hero
        results[name] = (res, best, final, fbest)

        print(f"\n  ▸ 每代最优 gen_best = {[round(x, 1) for x in res.gen_best_fitness]}")
        print(f"  ▸ 末代最优 − 初代最优 = {res.gen_best_fitness[-1] - res.gen_best_fitness[0]:.1f}")
        print(f"  ▸ uniq_evals={res.n_unique_evals}（fitness 缓存）  GA 净耗时 {dt:.1f}s")
        print(f"  ▸ 末代最优基因（{len(best)} 目标·按执行序）=")
        _dump_gene(best, meta)
        print(f"  ▸ ★含盾? 基因层 shield∈gene={_has_shield(best, meta)} / 物理层 DEF={fh.def_}")
        print(f"  ▸ 解码终态: {final.current_floor}({fh.x},{fh.y}) HP={fh.hp} ATK={fh.atk} "
              f"DEF={fh.def_} keys={dict(fh.keys)}  tokens={ntok}")
        print(f"  ▸ 末代最优 fitness = {fbest:.1f}   (对照 689={f689:.1f})")

        if name.startswith("B"):     # 本棒首要问题：注入含盾留住了吗（B 先跑 → 这里立刻回答，不等总结表）
            kept = _has_shield(best, meta)
            improved = best != inject_ind and fbest > f_inj
            print(f"\n  ★★ 组 B 关键诊断（注入含盾·留住了吗）：留住={kept}  "
                  f"末代最优==注入个体? {best == inject_ind}  改进(基因变且分更高)={improved}")
            if kept and improved:
                print("     → 留住并改进 = 纯变异够不到、加力度有效、方向对。")
            elif kept:
                print("     → 留住未改进（精英原样保住）= 加力度保得住、但交叉/变异未在其上更优。")
            else:
                print("     → ⚠ 注入后又淘汰回不拿盾 = 选择/fitness 有更深洞（矛盾、要回头查）。")

    # ── 总结表 ──
    print("\n" + "=" * 74)
    print("★ 三组对照总结（重点：A 光交叉探到含盾没？B 注入后留住含盾没？）")
    print("=" * 74)
    print(f"  {'组':<20}{'含盾(基因)':<11}{'末代fitness':>13}{'终态DEF':>9}{'终态HP':>8}")
    for name, _ in configs:
        res, best, final, fbest = results[name]
        print(f"  {name:<20}{str(_has_shield(best, meta)):<11}{fbest:>13.1f}"
              f"{final.hero.def_:>9}{final.hero.hp:>8}")
    print(f"\n  注入含盾个体 fitness={f_inj:.1f}  |  锚点 不拿盾≈-3729 / 含盾≈-1488 / 689={f689:.1f}")

    # 组 B 专项：留住 / 改进判定
    resB, bestB, finalB, fbestB = results["B 加交叉·注入含盾"]
    kept = _has_shield(bestB, meta)
    improved = bestB != inject_ind and fbestB > f_inj
    print(f"\n  组 B 注入诊断: 留住含盾={kept}  |  末代最优==注入个体? {bestB == inject_ind}  |  "
          f"改进(基因变且分更高)={improved}")
    if kept and improved:
        print("    → 留住并改进 = 纯变异够不到、加力度有效、方向对。")
    elif kept:
        print("    → 留住未改进（精英原样保住）= 加力度保得住、但交叉/变异未在它基础上更优。")
    else:
        print("    → ⚠ 注入后又淘汰回不拿盾 = 选择/fitness 有更深洞（矛盾、要回头查）。")


if __name__ == "__main__":
    main()
