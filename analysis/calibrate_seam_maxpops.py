"""【§S29 小验证·假阴性排除】标定 navigate_to 到 SEAM=MT10(1,11) 的 max_pops 够不够。

小验证(pop8/gen3)出「0/18 到 seam·全 V_boss=0」→ 表面倾向上乙。但 max_pops=8000 是 §S26 给红钥
末腿(MT8(9,1))标定的(redcap=8000)、seam=MT10(1,11) 更深一层(再下一道楼梯)→ reached=0 可能是
【预算不够的假阴性】而非「架构到不了」。判甲/乙前必须排除(verify_before_prune)。

做法：对这次 GA 最扎实的几个 gene(重跑同 seed·暖桶热近免费拿 base 最高 top-N + 全 13 块上界)的
term 态，递增 max_pops 测能否 reached seam：
  · 某档 reached → 8000 假阴性坐实、标出 seam 需多少 pops → 重标定后再判甲/乙；
  · 顶档(默认 100k)仍 reached=False → 强信号「真到不了」(没攒够钥匙路/路被封)→ 支持乙(须查因)。
navigate_to 缓存键含 max_pops → 8000 档命中 smoke 旧缓存(近免费)、更大档冷算。

只读：复用 build_harness/run_ga/_decode_with_order/navigate_to + smoke 的 build_pool_13/常量·不碰封板件。
用法：python -u analysis/calibrate_seam_maxpops.py [--topn 2] [--ladder 8000,20000,50000,100000]
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
sys.path.insert(0, str(ROOT / "analysis"))

from ga_loop import build_harness, run_ga, _decode_with_order, _invalid_score   # noqa: E402
from ga_navigate import navigate_to                                            # noqa: E402
from solver.fitness import fitness                                             # noqa: E402
from curriculum_smoke_vboss import SEAM, W_POTION, W_KEY, build_pool_13        # noqa: E402（复用同口径）


def _parse_args():
    p = argparse.ArgumentParser(description="§S29 假阴性排除：标定到 seam 的 max_pops")
    p.add_argument("--topn", type=int, default=2, help="测 base 最高的前 N 个 gene")
    p.add_argument("--ladder", type=str, default="8000,20000,50000,100000",
                   help="max_pops 阶梯(逗号分隔·从小到大)")
    p.add_argument("--pop", type=int, default=8)
    p.add_argument("--gen", type=int, default=3)
    p.add_argument("--minlen", type=int, default=7)
    p.add_argument("--maxlen", type=int, default=10)
    p.add_argument("--seed", type=int, default=20260616)
    return p.parse_args()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = _parse_args()
    ladder = [int(x) for x in args.ladder.split(",") if x.strip()]

    print(f"=== §S29 假阴性排除·标定 seam max_pops  {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    print(f"组装电池组(build_harness · persistent=True·暖桶热)…", flush=True)
    H = build_harness(persistent=True)
    start, zone, step = H["start"], H["zone"], H["step"]
    roster_fit, big, zone_fids = H["roster_fit"], H["big"], H["zone_fids"]
    decode_cache = H["decode_cache"]
    pool, block_markers, block_cells, sword_block, shield_block = build_pool_13(H)
    print(f"  pool=13 块  SEAM={SEAM}  ladder={ladder}", flush=True)

    def decode_term(gene):
        """decode 一条基因 → (term_state, base, invalid)。不传 final_goal(同 smoke 口径)。"""
        _t, term, _n, verdict = _decode_with_order(
            gene, start, zone, step, decode_cache,
            block_markers=block_markers, block_cells=block_cells)
        if verdict["invalid"]:
            return None, _invalid_score(verdict), True
        base = fitness(term, roster_fit, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
        return term, base, False

    # ── 重跑同 seed GA(暖桶热·decode 近免费)收集所有 unique gene 的 (base, gene, term) ──
    print("重跑同 seed GA 拿候选 gene(暖桶热·近免费)…", flush=True)
    seen = {}

    def base_eval(gene):
        term, base, invalid = decode_term(gene)
        if not invalid:
            seen[tuple(gene)] = (base, term)
        return base

    seeds = [[shield_block], [sword_block]]
    run_ga(pool, base_eval, population=args.pop, generations=args.gen,
           min_len=args.minlen, max_len=args.maxlen, inject=seeds, seed=args.seed)

    # base 最高的 top-N 有效 gene + 全 13 块上界
    ranked = sorted(seen.items(), key=lambda kv: -kv[1][0])
    candidates = [(f"GA-top{i+1}", list(g), b, term)
                  for i, (g, (b, term)) in enumerate(ranked[:args.topn])]
    # 全 13 块(最扎实上界·攻防最高最可能有路)——直接 decode(可能 invalid)
    full_term, full_base, full_invalid = decode_term(pool)
    if full_invalid:
        print(f"  (全 13 块基因 decode 判 invalid·跳过·只测 GA-top{args.topn})")
    else:
        candidates.append(("全13块上界", list(pool), full_base, full_term))

    print(f"  候选 {len(candidates)} 条(GA-top{args.topn} + 全13块若有效)\n", flush=True)

    # ── 对每个候选 term 态测递增 max_pops 到 seam ──
    print("=" * 78)
    print("【标定】每个扎实 gene 的 term 态·递增 max_pops 测能否 reached seam=MT10(1,11)")
    print("=" * 78)
    any_reached = False
    min_reach_pops = None
    for name, gene, base, term in candidates:
        th = term.hero
        keys = {k: v for k, v in th.keys.items() if v}
        print(f"\n── [{name}] base={base:.1f}  len={len(gene)}  "
              f"term={term.current_floor}({th.x},{th.y}) HP={th.hp} ATK={th.atk} DEF={th.def_} 钥={keys} ──",
              flush=True)
        for mp in ladder:
            t0 = time.time()
            seam, _moves, reached = navigate_to(term, SEAM, zone, step, max_pops=mp, cache=decode_cache)
            secs = time.time() - t0
            if reached:
                sh = seam.hero
                print(f"  max_pops={mp:>7}  ★REACHED  {secs:5.0f}s  → seam HP={sh.hp} ATK={sh.atk} "
                      f"DEF={sh.def_} 钥={{k:v for k,v in sh.keys.items() if v}}", flush=True)
                any_reached = True
                min_reach_pops = mp if min_reach_pops is None else min(min_reach_pops, mp)
                break
            else:
                print(f"  max_pops={mp:>7}  reached=False  {secs:5.0f}s(烧满)", flush=True)

    # ── 判据 ──
    print("\n" + "=" * 78)
    if any_reached:
        print(f"★假阴性【坐实】：加大 max_pops 后能到 seam(最小够用档≈{min_reach_pops})。")
        print(f"  → 小验证用的 8000 对 seam【不够】、'0/18 到 seam' 是预算假信号、【不能据此上乙】。")
        print(f"  → 下一步：用够用的 max_pops 重标定后重跑小验证，再判甲/乙。")
    else:
        top = ladder[-1]
        print(f"★假阴性【排除】：连最扎实 gene + 顶档 max_pops={top} 都到不了 seam。")
        print(f"  → '到不了 seam' 不是预算问题、是【真到不了】(gene 没攒够钥匙路 / 路被封)。")
        print(f"  → 这【支持乙(state-centric)】方向；但仍须查『为什么到不了』(看上面各 term 态钥匙数 vs")
        print(f"     MT9→MT10 路上的门)——交玩家游戏知识判，别在此推演。")
    print("=" * 78)
    print("\n★甲/乙最终由玩家拍(脚本只出客观数·本脚本只排除 max_pops 假阴性这一项)。")


if __name__ == "__main__":
    main()
