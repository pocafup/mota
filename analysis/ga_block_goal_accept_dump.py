"""【块为目标·端到端验收 dump】§S18 块为目标落地后给玩家拍板的 4 个 dump（只读·不改产品码）。

玩家红线（docs/handoff §S17→§S19）：端到端实现做完【给 4 个块 dump 让玩家看·不是 beam 绿就 commit】。
本脚本把那 4 个 dump 一次跑齐（全走【已实现的产品码】：build_harness/build_block_index/decode/规整/
partition_floor_blocks，不另造逻辑、不碰封板件）：

  dump①  pool 折叠 + 来源：10 个 detect 物品 cell → 折成几块（同块 cell 合并·五钥归并的直接证据），每块来源。
  dump②  ★+16826 块版生死线：无盾 [剑块,5钥块] ≠ [5钥块,剑块] 仍不折叠、终态仍差 +16826
         （剑块 MT5 / 钥块 MT4 异层必不同块·天然不折叠）。
  dump③  一区分裂验证：重放标尺 route，MT1–MT9 逐步重算块划分，检"1 旧块 → ≥2 新块"分裂事件（应零反例
         → 印证单向吸纳只合并不分裂 → 块 id（含 min 锚）全局稳定）。
  dump④  一条块为目标 GA 解的 decode：块 id 序列 → 代表 cell → navigate 吸光整块；含"空块跳过"两形态
         （自欺·顺路已吸空 + 钉死点 2.3·不可达原子跳过）；玩家据 normalized 真实进包序用游戏眼睛看走得对不对。

运行：python analysis/ga_block_goal_accept_dump.py  （--no-persistent 用内存缓存·首跑深盾 ~26s）
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from ga_loop import build_harness, run_ga, _decode_with_order, _taken      # noqa: E402
from ga_decode import decode, goal_to_cell                                 # noqa: E402
from ga_navigate import navigate_to                                        # noqa: E402
from block_targets import make_static_state                               # noqa: E402
from solver.quotient import partition_floor_blocks                        # noqa: E402
from solver.fitness import fitness                                        # noqa: E402
from export_mt10_boss_route import make_initial_state                     # noqa: E402
from decode_route import parse_rle_route, decompress                      # noqa: E402
from sim.simulator import step                                            # noqa: E402

W_POTION, W_KEY = 1.5, 39.0
DUMP3_FIDS = ["MT1", "MT2", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9"]
ROUTE = ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"


def tag_of(bid, meta):
    if bid == meta["sword"]:
        return "剑"
    if bid == meta["shield"]:
        return "盾"
    if bid in meta["keys"]:
        return "钥"
    if bid in meta["gems"]:
        return "宝石"
    return "?"


# ════════════════════════════════════════════════════════════════════════════════
def dump1_pool_fold(H):
    meta, pool = H["meta"], H["pool"]
    cells, roles = meta["cells"], meta["block_roles"]
    rep, bcells = meta["block_rep"], meta["block_cells"]
    bm = H["block_markers"]
    print("\n" + "=" * 80)
    print("dump① pool 折叠 + 来源：10 物品 cell → 块 id（同块合并·五钥归并的直接证据）")
    print("=" * 80)
    print("  ▸ detect 涌现的 10 物品 cell（口径一字不改·守 beam 零影响）→ 各自所属初始块：")
    c2b = H["block_index"]["cell_to_block"]
    for role, lst in [("剑", [cells["sword"]]), ("盾", [cells["shield"]]),
                      ("钥", cells["keys"]), ("宝石", cells["gems"])]:
        for c in lst:
            print(f"      [{role:2}] cell {c}  → 块 {c2b[c]}")
    print(f"\n  ▸ 折叠结果：10 cell → pool({len(pool)} 块)。逐块来源（块内折进了哪些 detect 物品）：")
    for b in pool:
        members = roles[b]
        rolestr = "+".join(f"{r}{c}" for r, c in members)
        merged = "  ★多物品归并" if len(members) > 1 else ""
        print(f"      块 {b}  代表cell={rep[b]}  块大小={len(bcells[b])}  含[{len(members)}]={rolestr}{merged}")
    nkeys_cells = len(cells["keys"])
    nkeys_blocks = len(meta["keys"])
    print(f"\n  ▸ 五钥归并核对：5 个 MT4 钥 cell {cells['keys']}")
    print(f"      → 折成 {nkeys_blocks} 个钥块 {meta['keys']}（{nkeys_cells}→{nkeys_blocks} 归并）")
    for b in meta["keys"]:
        kc = sorted(c for c in bm[b] if c in cells["keys"])
        print(f"        钥块 {b}：含钥 cell {kc}")
    print(f"\n  ▸ 结论：cell 池(10) → pool({len(pool)} 块) = {pool}")


# ════════════════════════════════════════════════════════════════════════════════
def dump2_lifeline(H):
    start, zone, step_fn = H["start"], H["zone"], H["step"]
    cache, meta, bm = H["decode_cache"], H["meta"], H["block_markers"]
    roster, big, zfids = H["roster_fit"], H["big"], H["zone_fids"]
    sword, keys = meta["sword"], meta["keys"]
    print("\n" + "=" * 80)
    print("dump② ★+16826 块版生死线：无盾 [剑块,5钥块] ≠ [5钥块,剑块]（不折叠·终态差 +16826）")
    print("=" * 80)
    X1 = [sword] + keys                # 剑块早
    Y1 = keys + [sword]                # 剑块晚
    out = {}
    for nm, g in (("X1 剑早", X1), ("Y1 剑晚", Y1)):
        _t, final, norm, _vd = _decode_with_order(g, start, zone, step_fn, cache, block_markers=bm)
        f = fitness(final, roster, big, zfids, w_potion=W_POTION, w_key=W_KEY)
        h = final.hero
        out[nm] = (norm, f, final)
        print(f"\n  {nm}  gene = {[ (tag_of(b, meta), b) for b in g ]}")
        print(f"     normalized(真实进包块序) = {norm}")
        print(f"     终态 ATK={h.atk} DEF={h.def_} HP={h.hp}   fitness={f:.1f}")
    n1, f1, _ = out["X1 剑早"]
    n2, f2, _ = out["Y1 剑晚"]
    print(f"\n  ▸ 剑块={sword}(MT5)  钥块={keys}(MT4) → 异层必不同块 → 天然不该折叠")
    print(f"  ▸ normalized 是否相同? {n1 == n2}（应 False＝不折叠）")
    print(f"  ▸ Δfitness(剑早 − 剑晚) = {f1 - f2:+.1f}（应 = +16826.0：生死线守住）")
    ok = (n1 != n2) and abs((f1 - f2) - 16826.0) < 1e-6
    print(f"  ▸ 判定：{'✅ 生死线守住（不折叠 + Δ=+16826）' if ok else '❌ 生死线破！'}")


# ════════════════════════════════════════════════════════════════════════════════
def dump3_split_check():
    print("\n" + "=" * 80)
    print("dump③ 一区分裂验证：MT1–MT9 重放标尺 route，检 '1 旧块 → ≥2 新块' 分裂事件（应零反例）")
    print("=" * 80)
    print("  (单向吸纳模型：块只合并不分裂 → 含 min 锚的块 id 全局稳定。分裂=反例=结构事件·须人工核)")
    zone1 = set(DUMP3_FIDS)
    outer = json.loads(decompress(ROUTE.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    prev_floor = s.current_floor
    prev_blocks = partition_floor_blocks(s) if prev_floor in zone1 else None
    checked = Counter()
    splits = []
    for i, a in enumerate(actions, 1):
        s = step(s, a)
        if s.dead:
            break
        f = s.current_floor
        if f not in zone1:
            prev_floor, prev_blocks = f, None
            continue
        cur = partition_floor_blocks(s)
        if f == prev_floor and prev_blocks is not None:
            checked[f] += 1
            for ob in prev_blocks:
                overlap = [nb for nb in cur if ob & nb]
                if len(overlap) >= 2:
                    splits.append((i, f, min(ob), sorted(min(nb) for nb in overlap)))
        prev_floor, prev_blocks = f, cur
    print(f"  ▸ 同层步检查覆盖（MT1–MT9 同层相邻步数）：{dict(sorted(checked.items()))}")
    print(f"      合计检查 {sum(checked.values())} 步 · 跨这些步的块划分重算")
    if splits:
        print(f"  ⚠⚠ 分裂反例 {len(splits)} 起（1 旧块裂成 ≥2 新块）——须人工核对是否结构事件：")
        for si, fid, ob_min, new_mins in splits[:20]:
            print(f"      step#{si} [{fid}] 旧块锚 {ob_min} → 裂成新块锚 {new_mins}")
    else:
        print("  ▸ 结论：MT1–MT9 全程【零分裂反例】✅ → 单向吸纳成立·块 id 全局稳定")
    return len(splits)


# ════════════════════════════════════════════════════════════════════════════════
def _decode_verbose(gene, start, zone, step_fn, cache, bm, meta, label):
    """复刻封板 decode 的逐目标 navigate_to（封板件原样调·只读），旁记每腿：
    代表 cell / reached / 步数 / 本腿新吸的 pool 物品 cell（区分'本块'与'顺路吸别块'）/ 勇者属性。"""
    pool_cells = set().union(*bm.values())          # 全部 detect 物品 cell（进包追踪域）
    absorbed = {c for c in pool_cells if _taken(start, c)}
    state = start
    print(f"\n  —— {label}：逐腿 decode（块 id → 代表 cell → 吸光块）——")
    for k, goal in enumerate(gene, 1):
        rolab = f"{tag_of(goal, meta)}{goal}"
        if state.dead or state.won:
            print(f"    {k:2d}. {rolab}: 停（勇者 dead/won 冻结·decode 同口径）")
            continue
        rep = goal_to_cell(goal)
        final, moves, reached = navigate_to(state, rep, zone, step_fn, cache=cache)
        nstate = final if reached else state
        after = {c for c in pool_cells if _taken(nstate, c)}
        newly = after - absorbed
        own = sorted(c for c in newly if c in bm.get(goal, frozenset()))
        side = sorted(c for c in newly if c not in bm.get(goal, frozenset()))
        already = bm.get(goal, frozenset()) <= absorbed     # 本腿之前本块已空
        h = nstate.hero
        if not reached:
            status = "❌不可达→原子跳过（state 不变·钉死点 2.3）"
        elif already and not own:
            status = "空块跳过（本块顺路已吸空·navigate 到代表 cell 零新增）"
        else:
            status = f"吸到本块 {own}" + (f" + 顺路吸 {side}" if side else "")
        print(f"    {k:2d}. {rolab} → 代表cell {rep}  reached={reached} 步数={len(moves) if reached else 0}")
        print(f"        {status}")
        print(f"        勇者→ {nstate.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} keys={dict(h.keys)}")
        absorbed = after
        state = nstate
    return state


def dump4_decode(H):
    start, zone, step_fn = H["start"], H["zone"], H["step"]
    cache, meta, bm = H["decode_cache"], H["meta"], H["block_markers"]
    pool = H["pool"]
    roster, big, zfids = H["roster_fit"], H["big"], H["zone_fids"]
    sword, shield = meta["sword"], meta["shield"]
    print("\n" + "=" * 80)
    print("dump④ 一条块为目标 GA 解的 decode（块 id 序列 → 代表 cell → 吸光块 + 空块跳过）")
    print("=" * 80)

    # —— 一条 GA 解（短跑·注入含盾·定种子·只为给玩家眼睛看 decode·非追最优）——
    print("  跑一条短 GA（pop10 gen5·注入[盾块]·交叉0.3·seed 固定）取一条块为目标解…")
    t = time.time()
    res = run_ga(pool, H["eval_fn"], population=10, generations=5, tournament_k=3,
                 elite=2, crossover_rate=0.3, inject=[[shield]], seed=20260614)
    best = res.best_individual
    print(f"    GA 就绪 {time.time() - t:.1f}s  best fitness={res.best_fitness:.1f}  去重评估={res.n_unique_evals}")
    print(f"\n  ▸ GA 最优基因（执行序·{len(best)} 块）→ 角色 + 代表 cell：")
    for b in best:
        print(f"      {tag_of(b, meta):2} 块 {b}  代表cell={meta['block_rep'].get(b, goal_to_cell(b))}")

    _decode_verbose(best, start, zone, step_fn, cache, bm, meta, "GA 最优解")

    # normalized 真实进包序（玩家据此用游戏眼睛看"先拿盾→顺路吸剑→五钥…"对不对）
    _tk, final, norm, _vd = _decode_with_order(best, start, zone, step_fn, cache, block_markers=bm)
    f = fitness(final, roster, big, zfids, w_potion=W_POTION, w_key=W_KEY)
    print(f"\n  ★normalized 真实进包块序（{len(norm)} 块·玩家据此判像不像样）=")
    for j, b in enumerate(norm, 1):
        print(f"      {j:2d}. {tag_of(b, meta):2} {b}")
    h = final.hero
    print(f"  终态 {final.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"keys={dict(h.keys)}  fitness={f:.1f}")

    # —— 空块跳过·形态一：自欺（盾腿顺路吸空剑块 → 之后到剑块代表 cell 零新增）——
    print("\n  ▸ 空块跳过·形态①（§S11 自欺）：[盾块,剑块] —— 盾腿顺路吸空剑块 → 剑块这腿空块跳过")
    _decode_verbose([shield, sword], start, zone, step_fn, cache, bm, meta, "[盾块,剑块]")

    # —— 空块跳过·形态二：不可达原子跳过（钉死点 2.3·合成离图探针·非真目标）——
    print("\n  ▸ 空块跳过·形态②（钉死点 2.3·不可达原子跳过）：基因首位放【合成离图块】(MT9,(-1,-1))")
    print("     —— navigate 够不到 → reached=False → 原子跳过、state 不变、后续照常 decode（任何基因永远可解码）")
    probe = ("MT9", (-1, -1))                       # 合成离图块 id（演示跳过·非真目标·非可达坐标）
    tok_probe, final_p = decode([probe] + best[:2], start, zone, step_fn, cache=cache)
    tok_base, final_b = decode(best[:2], start, zone, step_fn, cache=cache)
    same = (final_p.hero.x, final_p.hero.y, final_p.hero.hp, final_p.current_floor) == \
           (final_b.hero.x, final_b.hero.y, final_b.hero.hp, final_b.current_floor)
    print(f"     decode([离图探针]+前2块) 终态 == decode(前2块) 终态? {same}  "
          f"（应 True＝探针被原子跳过、不污染路线）  tokens {len(tok_probe)} vs {len(tok_base)}")


# ════════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-persistent", action="store_true", help="用内存缓存（默认持久化暖桶）")
    args = ap.parse_args()
    persistent = not args.no_persistent

    print("=" * 80)
    print("块为目标·端到端验收 4 dump（全走已实现产品码·只读·不 commit·待玩家拍板）")
    print("=" * 80)
    t0 = time.time()
    print(f"组装 GA 电池组（build_harness·persistent={persistent}·首跑深盾 ~26s）…")
    H = build_harness(persistent=persistent)
    print(f"  电池组就绪 {time.time() - t0:.1f}s   pool({len(H['pool'])}) = {H['pool']}")

    dump1_pool_fold(H)
    dump2_lifeline(H)
    n_split = dump3_split_check()
    dump4_decode(H)

    print("\n" + "=" * 80)
    print(f"4 dump 跑齐（耗时 {time.time() - t0:.1f}s）。dump③ 分裂反例数={n_split}（应 0）。")
    print("⏸ 按红线【停在此·不 commit】，等玩家看 dump 验收。")
    print("=" * 80)


if __name__ == "__main__":
    main()
