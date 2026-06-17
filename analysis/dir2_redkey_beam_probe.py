"""【方向2·小验证】干净 V_boss 当 best-first 排序 key + beam，跑"铁盾态→红钥"宽楼层段，
看【引导 beam 能否走到穷尽撞 cap 够不到的红钥】=验"有损 beam 能不能让中段可处理"。

背景（§S36）：红钥获取的真实最优腿 = 9 层交错回访
  MT9→MT7→MT6→MT3→MT5→MT8→MT1→MT3→MT5→MT4→MT9→MT10→MT9→MT7→MT8→MT10→MT8
  （为一把红钥要下到 MT1、两进 boss 层 MT10）。穷尽搜 {MT8,MT9}/{MT7,MT8,MT9} 都撞 cap found=False、
  navigate 贪心 218s 步数=0。→ "宽楼层段"超出穷尽/贪心能力。方向2 问：V_boss 引导 + beam 截宽
  能否在【有界状态】下穿过这 9 层走到红钥？

口径（§S37·干净 V_boss）：V_boss(a,d,h)=h+delta(a,d)，delta = boss 段（seam→杀队长·含8守卫）
  纯损血。当 beam 排序键=偏好"高攻防高血"（攒属性=过 boss 潜力↑）。
  ★delta 与 HP_in 无关、a,d≤27 干净（含义见 _vboss_rescan_full.txt / handoff §S37）。

甲'三护栏（§S34·本验证带上）：
  ① V_boss 当排序 key = 终值可替换钩子 → 挂【现成 beam_score_fn 参数】（state→数值），
     ★零产品码改动、search_quotient/beam.py 一字未动 → beam 47 守卫零回归【自明】。
  ② beam 截断保"留存钥匙数"维 → beam_select 的 protection skeleton 已按当前层门数封顶硬保钥匙；
     再加 beam_diversity="stairs"（按推进度分坑）保 climber 不被低层 grinder 一锅端。
     ⚠ 已知 gap：跨区钥匙（超当前层门数那部分）不进保护维——本段红钥是【终点】非通行钥匙、
       通行用黄/蓝钥在各层门数内受保护，故 gap 对本段大概率不咬；若咬，结果会偏保守（低估 beam）。
  ③ 范围可配 = goal_cell（红钥格）+ ALLOWED（楼层集）均参数化。

只读：复用 extract_zone1_milestones 加载（明确指名新存档）、sim.step、solver.quotient.search_quotient。
绝不改产品码。用法：
  python -u analysis/dir2_redkey_beam_probe.py [--beam-k 400] [--max-states 300000]
        [--allowed MT1,MT3,MT4,MT5,MT6,MT7,MT8,MT9,MT10] [--diversity stairs]
"""
import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step
from solver.quotient import search_quotient
from extract.encode_route import write_h5route

TOK_SHIELD = 454               # 铁盾刚到手 MT9(9,7) HP166 ATK22 DEF20 钥黄2蓝1（§S36 坐实）
REDKEY_CELL = ("MT8", 10, 2)   # 一区唯一红钥（tok945 到手）= 本段 goal
REAL_LEG_FLOORS = ["MT1", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10"]  # §S36 真实腿 9 层

BIG = -10**9                   # ATK<18 打不动 boss = 排序键谷底

# ── 干净 V_boss delta(a,d) 矩阵（§S37 / analysis/_vboss_rescan_full.txt @9999 纯 delta）──
ATK_GRID = [18, 21, 24, 27]
DEF_GRID = [15, 18, 21, 24, 27]
DELTA = {
    18: {15: -2964, 18: -2739, 21: -2514, 24: -2289, 27: -2064},
    21: {15: -1730, 18: -1592, 21: -1454, 24: -1316, 27: -1178},
    24: {15: -1170, 18: -1077, 21: -984,  24: -891,  27: -798},
    27: {15: -946,  18: -868,  21: -790,  24: -712,  27: -634},
}
# ATK=15 行 = ✗（打不动，给 9999 血也过不去）→ a<18 一律 BIG。


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _bracket(v, grid):
    """返回 (lo, hi, t)：grid 中夹住 v 的两点 + 线性比例 t∈[0,1]。v 已 clamp 到 [grid0,grid-1]。"""
    if v <= grid[0]:
        return grid[0], grid[0], 0.0
    if v >= grid[-1]:
        return grid[-1], grid[-1], 0.0
    for i in range(len(grid) - 1):
        if grid[i] <= v <= grid[i + 1]:
            lo, hi = grid[i], grid[i + 1]
            return lo, hi, (v - lo) / (hi - lo)
    return grid[-1], grid[-1], 0.0


def delta_interp(atk, def_):
    """双线性插值 delta(atk,def)。atk<18→BIG（打不动）；其余 clamp 到 [18,27]×[15,27]。"""
    if atk < ATK_GRID[0]:
        return BIG
    a = _clamp(atk, ATK_GRID[0], ATK_GRID[-1])
    d = _clamp(def_, DEF_GRID[0], DEF_GRID[-1])
    a0, a1, ta = _bracket(a, ATK_GRID)
    d0, d1, td = _bracket(d, DEF_GRID)
    v00 = DELTA[a0][d0]
    v01 = DELTA[a0][d1]
    v10 = DELTA[a1][d0]
    v11 = DELTA[a1][d1]
    top = v00 * (1 - td) + v01 * td
    bot = v10 * (1 - td) + v11 * td
    return top * (1 - ta) + bot * ta


def v_boss_score(state):
    """方向2 排序键 = V_boss(进场属性) = hp + delta(atk,def)。高=过 boss 潜力大（高攻防高血）。
    delta 与 HP_in 无关（§S37）→ 这就是"带此刻属性去打 boss 剩多少血"的解析估值。"""
    h = state.hero
    return h.hp + delta_interp(h.atk, h.def_)


def make_seg_step(allowed):
    """把搜索框在 allowed 楼层集：踏出本段的子态置 dead 裁掉（同 seg_chain_verify）。"""
    aset = set(allowed)

    def seg_step(state, action):
        ns = step(state, action)
        if ns.current_floor not in aset:
            ns.dead = True
        return ns
    return seg_step


def fmt(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    items = {k: v for k, v in h.items.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 道具={items} kills={h.kill_count} dead={s.dead} won={s.won}")


def replay_to_token(tok_idx):
    s = build_initial_state()
    tokens, _ = load_tokens()
    for t in tokens[:tok_idx + 1]:
        s = step(s, t)
    return s


def export_h5route(res, tag):
    """found=True 时：拼 tokens[:455] 前缀（开局→铁盾·玩家存档真实动作）+ beam RULD（铁盾→红钥）
    → 从开局完整 .h5route + sim 独立重放自检（CLAUDE.md 铁律：解丢回真实引擎走通才导）。
    seed 用玩家存档真实 meta（2097323316）→ 网站从开局正确回放。纯 analysis 层、不碰封板件。"""
    tokens, outer = load_tokens()
    prefix = list(tokens[:TOK_SHIELD + 1])      # 开局 MT1 → 铁盾 MT9(9,7)
    beam_acts = list(res.actions)               # 铁盾 → 红钥（beam 纯 U/D/L/R）
    full = prefix + beam_acts
    print(f"\n  ── 导出 h5route + sim 独立重放自检 ──")
    print(f"  full = 前缀{len(prefix)}(开局→铁盾) + beam{len(beam_acts)}(铁盾→红钥) = {len(full)} token")
    # sim 从开局独立重放（真实 step·无 seg 限制）；到红钥格才导，否则不给玩家坏文件
    s = build_initial_state()
    for t in full:
        s = step(s, t)
        if s.dead:
            break
    gf, gx, gy = REDKEY_CELL
    reached = (s.current_floor == gf and (s.hero.x, s.hero.y) == (gx, gy) and not s.dead)
    print(f"  重放终态: {fmt(s)}")
    if not reached:
        print(f"  ✗ 重放未停在红钥格 {REDKEY_CELL} → 不导出（链路须排查·别给玩家坏文件）")
        return None
    meta = {"name": outer.get("name", "51"), "version": outer.get("version", "Ver 3.0"),
            "hard": outer.get("hard", ""), "seed": outer.get("seed")}
    out_path = ROOT / f"dir2_redkey_fromstart_{tag}.h5route"
    write_h5route(out_path, full, meta)
    print(f"  ✓ sim 重放走到红钥格 → 已导出 {out_path.name}")
    print(f"    (meta seed={meta['seed']}·网站从开局回放；{len(full)} token)")
    return out_path


def export_halfway_h5route(best_acts, tag):
    """found=False 时：导【半截】h5route = beam 跑到的"最接近破门"grind 态（没到红钥）。
    拼 tokens[:455] 前缀（开局→铁盾）+ best_acts['acts']（铁盾→grind 态·on_admit 抓的动作串）
    → sim 独立重放自检终态吻合 on_admit 锚点（非红钥）→ 导出·明确标注半截非通关。"""
    if not best_acts or best_acts.get("acts") is None:
        print("\n  ✗ 无 beam 动作串可导半截（on_admit 未记到态）")
        return None
    tokens, outer = load_tokens()
    prefix = list(tokens[:TOK_SHIELD + 1])      # 开局 MT1 → 铁盾 MT9(9,7)
    beam_acts = list(best_acts["acts"])         # 铁盾 → grind 态（beam 纯 U/D/L/R）
    full = prefix + beam_acts
    snap = best_acts["snap"]
    print(f"\n  ── 导出【半截】h5route(beam 最接近破门态)+ sim 独立重放自检 ──")
    print(f"  锚点态(on_admit) = {snap[0]}({snap[1]},{snap[2]}) ATK={snap[3]} DEF={snap[4]} HP={snap[5]}")
    print(f"  full = 前缀{len(prefix)}(开局→铁盾) + beam{len(beam_acts)}(铁盾→grind态) = {len(full)} token")
    s = build_initial_state()
    for t in full:
        s = step(s, t)
        if s.dead:
            break
    print(f"  重放终态: {fmt(s)}")
    ok = (s.current_floor == snap[0] and (s.hero.x, s.hero.y) == (snap[1], snap[2])
          and s.hero.atk == snap[3] and s.hero.def_ == snap[4]
          and s.hero.hp == snap[5] and not s.dead)
    meta = {"name": outer.get("name", "51"), "version": outer.get("version", "Ver 3.0"),
            "hard": outer.get("hard", ""), "seed": outer.get("seed")}
    out_path = ROOT / f"dir2_redkey_halfway_{tag}.h5route"
    write_h5route(out_path, full, meta)
    flag = "✓" if ok else "⚠ 重放与锚点不符"
    print(f"  {flag} 已导出半截 {out_path.name}（seed={meta['seed']}·网站从开局回放到 grind 态）")
    print(f"    ⚠ 这是半截：beam 卡在 ATK{snap[3]}/DEF{snap[4]}、没破红钥门 → 网站回放走到 grind 态停、非通关")
    return out_path


def run_one(start, goal, allowed, beam_k, max_states, diversity):
    """跑一次 beam 引导段搜索 + 各层进度统计。返回 res。"""
    seg_step = make_seg_step(allowed)
    # on_admit：记各层【到达过】(含日后被 beam 截掉的) 的最优属性/V，看 beam 把队伍推到哪
    best = defaultdict(lambda: {"atk": 0, "def": 0, "hp": 0, "V": BIG, "n": 0})
    best_acts = {"key": (-1, -1), "acts": None, "snap": None}   # 全局“最接近破门”态→半截导出锚点

    def on_admit(child, _acts):
        h = child.hero
        b = best[child.current_floor]
        b["n"] += 1
        if h.atk > b["atk"]:
            b["atk"] = h.atk
        if h.def_ > b["def"]:
            b["def"] = h.def_
        if h.hp > b["hp"]:
            b["hp"] = h.hp
        v = v_boss_score(child)
        if v > b["V"]:
            b["V"] = v
        k = (h.atk, h.hp)                  # 破门接近度：ATK 先过守卫 def22、tie 看 survivable HP
        if k > best_acts["key"]:
            best_acts["key"] = k
            best_acts["acts"] = _acts
            best_acts["snap"] = (child.current_floor, h.x, h.y, h.atk, h.def_, h.hp)

    t0 = time.time()
    res = search_quotient(start, goal, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=True,
                          beam_score_fn=v_boss_score, beam_diversity=diversity,
                          on_admit=on_admit)
    secs = time.time() - t0
    res._secs = secs
    res._best_by_floor = dict(best)
    res._best_acts = best_acts
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beam-k", type=str, default="400", help="beam 上限（逗号分隔=扫多个）")
    ap.add_argument("--max-states", type=int, default=300_000,
                    help="生成上限（§S36 穷尽撞 300k cap·同预算对照）")
    ap.add_argument("--allowed", type=str, default=",".join(REAL_LEG_FLOORS),
                    help="段楼层集（默认=§S36 真实腿 9 层）")
    ap.add_argument("--diversity", type=str, default="stairs",
                    choices=["none", "floor", "stairs"], help="beam 分坑保护维")
    args = ap.parse_args()

    allowed = [f.strip() for f in args.allowed.split(",") if f.strip()]
    diversity = None if args.diversity == "none" else args.diversity
    beam_ks = [int(x) for x in args.beam_k.split(",") if x.strip()]

    print("=" * 84)
    print("方向2 小验证：干净 V_boss 引导 beam → 铁盾态穿 9 层拿红钥（穷尽撞 cap 处）")
    print("=" * 84)

    start = replay_to_token(TOK_SHIELD)
    assert start._single_floor_copy is False, "起点 _single_floor_copy 须 False（跨层安全深拷）"
    print(f"铁盾起点 tok{TOK_SHIELD}：{fmt(start)}")
    print(f"目标红钥格 = {REDKEY_CELL}   段楼层({len(allowed)}) = {allowed}")
    print(f"排序键 = 干净 V_boss(§S37) = hp + delta(atk,def)   分坑维 = {diversity}")
    # 自检 V_boss 排序键在几个属性档的值（确认单调=高攻防高血更优）
    print("\n V_boss 排序键自检（hp 固定 200·看 delta 主导的属性偏好）：")
    for a in (18, 22, 24, 27):
        row = "  ".join(f"d{d}:{200 + delta_interp(a, d):>8.0f}" for d in (15, 20, 24, 27))
        print(f"   ATK{a}:  {row}")

    for bk in beam_ks:
        print("\n" + "=" * 84)
        print(f"■ beam_k={bk}  max_states={args.max_states}  diversity={diversity}")
        print("=" * 84, flush=True)
        res = run_one(start, REDKEY_CELL, allowed, bk, args.max_states, diversity)
        print(f"\n  found={res.found}  耗时={res._secs:.1f}s  hit_cap={res.hit_cap}")
        print(f"  distinct_fp={res.distinct_fingerprints}  expanded={res.states_expanded} "
              f"generated={res.states_generated}  waves={res.n_waves}")
        print(f"  goal_hits={res.goal_hits}  前沿={len(res.goal_frontier)}  "
              f"beam_cut_total={res.beam_cut_total}  overflow_waves={res.beam_overflow_waves}")
        print(f"  fp_by_floor={dict(res.fp_by_floor)}")
        print("\n  ── 各层【到达过】最优属性（on_admit·看 beam 把队伍推到哪）──")
        for f in sorted(res._best_by_floor, key=lambda x: int(x[2:])):
            b = res._best_by_floor[f]
            print(f"    {f:>5}: n={b['n']:>6}  maxATK={b['atk']}  maxDEF={b['def']}  "
                  f"maxHP={b['hp']}  bestV={b['V']:>8.0f}")
        if res.found:
            print(f"\n  ★ 走到红钥！max-HP 出口 HP={res.final_hp}")
            print("  ⟹ 有损 beam + V_boss 引导让 9 层中段【可处理】→ 方向2 路通（量损待对照）。")
            export_h5route(res, f"bk{bk}")
        else:
            mt8 = res._best_by_floor.get("MT8")
            reach8 = f"到过 MT8(maxATK{mt8['atk']}/DEF{mt8['def']}/HP{mt8['hp']})" if mt8 else "没到过 MT8"
            print(f"\n  ✗ 没走到红钥（{reach8}）。hit_cap={res.hit_cap}")
            print("  ⟹ 此 beam_k/分坑下够不到——加宽 beam / 换分坑 / 红钥须更上游资源（看各层进度判）。")
            export_halfway_h5route(res._best_acts, f"bk{bk}")


if __name__ == "__main__":
    main()
