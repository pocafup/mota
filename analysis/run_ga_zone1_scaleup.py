"""【路线图② 小步上规模】跑 GA 一区好解 + 三方对照(比红钥前局面潜力)。

小步配置(玩家拍板)：pop=15(下限)/gen=12、固定种子、注入含盾种子[盾]+交叉0.3+规整(默认开)。
--persistent 暖桶(首次冷算落盘·之后热启)。只跑【GA 一区解·不含红钥】(红钥是 §S13③ 一区站稳后才做)
→ 三方对照比的是【红钥前的局面潜力】，不是追平 689/tok789 的含红钥最终成果。

★警惕血瓶软点(§S14 诚实标注)：血瓶项不做可达/守怪 gating、纯名义计数。若 GA 跑出 fitness 高但
  【属性平平+血瓶满地】= 踩血瓶软点的假优 → 本脚本自动标出、别当真优。

红线：不改 fitness/四封板件、import 现成 build_harness/run_ga、beam 零影响。权重=GA 真实尺 w_potion=1.5/w_key=39。
"""
import sys
import json
import time
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
from ga_decode import decode
from ga_loop import build_harness, run_ga, _decode_with_order
from solver.fitness import fitness, fitness_breakdown

W_POTION, W_KEY = 1.5, 39.0
POP, GEN, SEED, XRATE = 15, 10, 20260614, 0.3   # 小步起(pop15/gen10)·argparse 可覆盖(后续放大 pop25/gen15 不改码)


def replay_player_until_floor(route_file, target_floor):
    """回放玩家存档，停在 current_floor 首次 == target_floor 那刻；返回 (state, action_idx)。(复刻 §S14)"""
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    for i, a in enumerate(actions):
        s = step(s, a)
        if s.dead:
            return s, i
        if s.current_floor == target_floor:
            return s, i + 1
    return s, len(actions)


def deepest_zone_floor(state, zone_fids):
    """终态到达的最深一区层(zone_fids 按 MT0..MT10 有序)。"""
    visited = [fid for fid in zone_fids if fid in state.floors]
    return visited[-1] if visited else state.current_floor


def tag_of(cell, meta):
    if cell == meta["sword"]:
        return "剑"
    if cell == meta["shield"]:
        return "盾"
    if cell in meta["keys"]:
        return "钥"
    if cell in meta["gems"]:
        return "宝石"
    return "?"


def show(label, state, roster, big, zone_fids):
    """打印一条解的 fitness 分项对账 + 终态(复刻 §S14 show)；返回 bd。"""
    bd = fitness_breakdown(state, roster, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
    h = state.hero
    deepest = deepest_zone_floor(state, zone_fids)
    print(f"\n── {label} ──")
    print(f"  终态 {state.current_floor}({h.x},{h.y})  HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"MDEF={h.mdef}  keys={dict(h.keys)}  最深层={deepest}  dead={state.dead} won={state.won}")
    if bd.get("dead"):
        print(f"  ☠ 死亡态 total={bd['total']}")
        return bd
    print(f"  主干 equiv_hp (HP{bd['hp']:.0f} + 攻防压制{bd['atk_def_suppress']:.0f}) = {bd['main_equiv_hp']:>10.1f}")
    print(f"  血瓶 raw / 项(×{W_POTION})                          = {bd['potion_raw']:>10.1f} / {bd['potion_term']:>10.1f}")
    print(f"  钥匙 手里{bd['key_in_hand']}把(兑现{bd['key_realized']:.0f}) + 地上{bd['key_ground']:.0f} = 家底 {bd['key_term']:>10.1f}")
    print(f"  通关 win = {bd['win']:.0f}      ══ total = {bd['total']:>10.1f}")
    return bd


def main():
    import argparse
    ap = argparse.ArgumentParser(description="路线图② 上规模跑 GA 一区好解 + 三方对照")
    ap.add_argument("--pop", type=int, default=POP)
    ap.add_argument("--gen", type=int, default=GEN)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--xrate", type=float, default=XRATE)
    args, _ = ap.parse_known_args()       # parse_known：忽略 --persistent 等(本脚本恒 persistent=True 暖桶)
    pop, gen, seed, xrate = args.pop, args.gen, args.seed, args.xrate

    print("=" * 78)
    print(f"路线图② 小步上规模：pop={pop} gen={gen} seed={seed} 交叉={xrate} 注入=[盾] 规整=默认开")
    print("=" * 78)

    t0 = time.time()
    print("组装 GA 电池组(build_harness·persistent=True 暖桶·首次深盾冷算 ~26s)…")
    H = build_harness(persistent=True)
    t_harness = time.time() - t0
    print(f"  电池组就绪 {t_harness:.1f}s")

    start, zone, step_fn = H["start"], H["zone"], H["step"]
    roster, big, zone_fids = H["roster_fit"], H["big"], H["zone_fids"]
    meta, dc, eval_fn = H["meta"], H["decode_cache"], H["eval_fn"]
    bm = H["block_markers"]                       # 块为目标：进包判据（_decode_with_order 块模式必传）
    bc = meta["block_cells"]                       # §S15 禁区集：_decode_with_order 须与 eval_fn 同口径(禁区开)，否则展示终态/normalized 与 GA 实评不符
    sword, shield = meta["sword"], meta["shield"]   # 现为块 id（meta 角色→块 id），tag_of/sword 比较照旧

    print(f"\n  目标池 pool({len(H['pool'])}) = {H['pool']}")
    print(f"  剑={sword}  盾={shield}")

    # ── 标尺：689 / 718 / tok789 ───────────────────────────────────────────────
    f689 = fitness(H["s689"], roster, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
    f718 = fitness(H["s718"], roster, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
    player = ROOT / "51_20260529133740.h5route"
    s_tok, idx = replay_player_until_floor(player, "MT10")
    f_tok = fitness(s_tok, roster, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
    print(f"\n  标尺(同 fitness 尺·含红钥努力): 689={f689:.1f}  718={f718:.1f}  tok{idx}={f_tok:.1f}")

    # ── ② GA 爬坡(注入[盾]+交叉0.3+规整) ───────────────────────────────────────
    print("\n" + "=" * 78)
    print("② GA 爬坡曲线(逐代：含盾? 剑第几进包? best fitness)")
    print("=" * 78)

    valid_curve = []      # 逐代 (gen, 有效个体数, pop)·跑完画爬坡健康度曲线(判读③·先短后拼长)

    def logcb(gl):
        gene = gl.best_individual
        has_shield = shield in gene
        _t, _f, norm, _vd = _decode_with_order(gene, start, zone, step_fn, dc, block_markers=bm, block_cells=bc)
        sword_pos = (norm.index(sword) + 1) if sword in norm else None
        sp = f"剑第{sword_pos}进包" if sword_pos else "剑未进包"
        sh = "含盾✅" if has_shield else "无盾  "
        valid = pop - gl.n_invalid
        valid_curve.append((gl.gen, valid, pop))
        print(f"  gen {gl.gen:2d}: best={gl.best_fitness:>11.1f}  {sh}  {sp:9s}  "
              f"有效{valid:2d}/{pop:2d}  基因len={len(gene):2d}  进包len={len(norm):2d}  "
              f"uniq_evals={gl.n_unique_evals:3d}  spread=[{gl.spread_lo:.0f}..{gl.spread_hi:.0f}]")

    t1 = time.time()
    res = run_ga(H["pool"], eval_fn, population=pop, generations=gen,
                 tournament_k=3, elite=2, crossover_rate=xrate,
                 inject=[[shield]], seed=seed, log=logcb)
    t_ga = time.time() - t1
    climb = res.gen_best_fitness[-1] - res.gen_best_fitness[0]
    print(f"\n  ▸ gen_best = {[round(x, 1) for x in res.gen_best_fitness]}")
    print(f"  ▸ 末代−初代 = {climb:.1f} → {'✅ 在爬坡(>0)' if climb > 0 else '❌ 没爬(≤0)'}")
    print(f"  ▸ 真 decode+评估去重数 = {res.n_unique_evals}   GA 净耗时 {t_ga:.1f}s")

    # ── GA 最优解 → 解码终态 + normalized 真实进包序 ───────────────────────────
    best = res.best_individual
    _tok, ga_final, ga_norm, _vd = _decode_with_order(best, start, zone, step_fn, dc, block_markers=bm, block_cells=bc)
    print("\n" + "=" * 78)
    print("③ GA 最优解：基因(执行序) vs normalized(真实进包序)")
    print("=" * 78)
    print(f"  基因(执行序·{len(best)}) =")
    for g in best:
        print(f"      {g}  [{tag_of(g, meta)}]")
    print(f"  ★normalized 真实进包序({len(ga_norm)})=  (玩家据此判'像不像样·是否真先拿下面')")
    for i, g in enumerate(ga_norm, 1):
        print(f"      {i:2d}. {g}  [{tag_of(g, meta)}]")

    # ── ④ 三方对照表 ──────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("④ 三方对照(比红钥前局面潜力)：GA最优 vs 689 vs tok789")
    print("=" * 78)
    bd_ga = show("GA 最优(不含红钥)", ga_final, roster, big, zone_fids)
    bd_689 = show("689 (beam·含红钥努力)", H["s689"], roster, big, zone_fids)
    bd_tok = show(f"tok{idx} (玩家·含红钥努力)", s_tok, roster, big, zone_fids)

    # ── ⑤ 判读：①逼近689/tok? ②含盾/剑早涌现? ③踩血瓶软点? ────────────────────
    print("\n" + "=" * 78)
    print("⑤ 判读")
    print("=" * 78)
    print(f"  ① fitness 对照：GA={bd_ga['total']:.1f}  vs  689={bd_689['total']:.1f}  vs  tok{idx}={bd_tok['total']:.1f}")
    print(f"     (GA 不含红钥·比红钥前局面；GA−689={bd_ga['total']-bd_689['total']:+.1f})")

    has_shield = shield in best
    sword_pos = (ga_norm.index(sword) + 1) if sword in ga_norm else None
    print(f"  ② 含盾涌现：{'✅ 是' if has_shield else '❌ 否'}   "
          f"剑早涌现：{'剑第'+str(sword_pos)+'进包' if sword_pos else '剑未进包'}")

    # ③ 爬坡健康度(先短后拼长·§S21)：初代无效率高→进度分(INVALID_BASE+导航块×1000+最深层×10)把 GA 往有效序拽→末代有效率升
    print(f"  ③ 爬坡健康(有效序列率·先短后拼长)：")
    for gen_i, v, p in valid_curve:
        bar = "█" * v + "░" * (p - v)
        print(f"       gen {gen_i:2d}: 有效 {v:2d}/{p:2d}  {bar}")
    if valid_curve:
        v0, vN = valid_curve[0][1], valid_curve[-1][1]
        trend = "✅ 有效率升(进度分把 GA 往有效序拽)" if vN > v0 else "＝持平" if vN == v0 else "⚠ 有效率降(查进度分梯度)"
        print(f"       初代有效 {v0}/{valid_curve[0][2]} → 末代有效 {vN}/{valid_curve[-1][2]}  {trend}")

    # ④ 血瓶软点探测：GA 主干显著弱于 689 但血瓶项不低于 689 → 疑似踩软点(属性平平+血瓶虚高)
    main_gap = bd_ga["main_equiv_hp"] - bd_689["main_equiv_hp"]   # <0 = GA 属性更弱
    potion_hoard = bd_ga["potion_term"] >= bd_689["potion_term"]   # 血瓶不低于 689
    soft_spot = (main_gap < -2000) and potion_hoard
    print(f"  ④ 血瓶软点探测：GA主干−689主干={main_gap:+.1f}  GA血瓶={bd_ga['potion_term']:.0f} vs 689血瓶={bd_689['potion_term']:.0f}")
    if soft_spot:
        print(f"     ⚠⚠ 疑似踩血瓶软点：GA 属性显著弱于 689(主干差{main_gap:.0f})却靠血瓶撑分 → 假优、别当真！")
    else:
        print(f"     ✅ 未踩软点：GA 解{'主干不弱于689' if main_gap >= -2000 else '虽属性弱但血瓶也未虚高'}、靠兑现属性非满地血瓶撑分。")

    # ── cache 状态 ────────────────────────────────────────────────────────────
    if hasattr(dc, "stats"):
        print(f"\n  navigate_to 持久化缓存: 桶={dc.version_tag}  {dc.stats}")
    print(f"\n  ▸▸ 耗时：build_harness={t_harness:.1f}s   GA={t_ga:.1f}s   总={time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
