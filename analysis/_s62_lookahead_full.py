"""§S62 lookahead 全跑 + L 风险预验（产品码零改动·复用 smart_phi_s53_beam.run_full）。

把 §S55 字典序 score_fn 的【主键 atk】换成【potential_atk(L)】——乐观朝【最近未拿红宝石】
贪心走【最多 L 步】内可达的最大 atk（够到 gem→atk+1，够不到→原 atk）。其余全部保留：
  · def 次键        （字典序不变）
  · hp − Φ + key_credit 末键（§S55 字典序 + §S43 钥匙稀缺 mult=1）
  · fly 开           （§S56 飞回低层拿漏拿资源·如 MT1）
→ 严格遵守 CLAUDE.md「加 X = 在现有所有做法之上叠加」：lookahead 是叠在
  「字典序 + mult=1 + fly」之上，不是单独做 lookahead。

为什么换主键能救「分支存活」（§S60/§S61）：硬 atk 主键把「暂时 atk 低但 L 步内能涨 atk」
的中间态（蓝门 YELLOW / 绕路拿 gem）提前剪掉；potential_atk 让这些态按【乐观最终 atk】排，
活到能用末键(key_credit/hp)判价值。

★L 的两难（§S61 实测·本脚本 --verify 复验）：
  · L 太浅(=2) 只够蓝门 1 步，够不到 MT1/MT8 的深绕路 gem；
  · L 太深(≥11) 会把「囤血态」也乐观升档 → 复活 §S54 囤血病（maxHP 暴涨、atk 被囤血态压下）；
  · 囤血态与绕路 gem 起点是同一个态 → L 无法同时(救深绕路)+(不复活囤血)。
  · L=8 是玩家选的折中（够 MT1/MT8、且 <11 理论不复活）——但须先验：①真不复活 ②跑得完。

用法：
  预验(几分钟·别直接挂全跑赌一晚)：
    python -u analysis/_s62_lookahead_full.py --verify --L 8
  全跑(无人值守·结果写文件明早读)：
    python -u analysis/_s62_lookahead_full.py --L 8 --max-states 1800000 --out <file>
"""
import sys
import os
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.smart_phi_s53_beam import (                              # noqa: E402
    key_credit, FLY_ATTRS, run_full)
from analysis.dir2_redkey_pathloss_beam import (                       # noqa: E402
    TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS, make_seg_step, load_tokens)
from analysis.route_aware_phi_probe import _is_cleared                 # noqa: E402
from analysis._s58_gem27_probe import (                                # noqa: E402
    setup, decode_route, free_reach_step_toward)
from analysis._s60_bluedoor_eval import (                              # noqa: E402
    expand_ops, rollout_to_gem, GEM as GEM_BLUE, BLUE_DOOR)
from analysis._s61_branch_survival_eval import potential_atk          # noqa: E402
from analysis.extract_zone1_milestones import build_initial_state     # noqa: E402
from sim.simulator import step                                        # noqa: E402

# ── 一区 8 颗红宝石(+1atk)·来源 data/games51/floors/MT*.json 的 redGem(27)·(floor,x,y) ──
REDGEMS = [
    ("MT1", 7, 3), ("MT3", 2, 9), ("MT4", 7, 10), ("MT5", 3, 1),
    ("MT7", 3, 1), ("MT8", 4, 10), ("MT9", 6, 5), ("MT10", 10, 6),
]
# MT1 还有血瓶(redPotion)·玩家一直头疼 MT1 被忽略·全跑报告查这些拿没拿
MT1_GEM = ("MT1", 7, 3)
MT1_POTIONS = [("MT1", 1, 3), ("MT1", 8, 4), ("MT1", 1, 10), ("MT1", 1, 11)]
GEM_DETOUR = ("MT8", 4, 10)      # 第5颗 gem(破红钥关键·§S58)·离 P2 起点 11 步(深绕路)
ROUTE = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly.h5route"
MULT = 1.0                        # §S43 钥匙稀缺 mult=1(玩家定)
BEAM_K = 800                      # §S55 基线宽度


def nearest_untaken_gem(state):
    """当前层【未拿】红宝石里曼哈顿最近的一颗(potential_atk 同层贪心·跨层 gem 靠 Φ 引导去那层)。
    无 → None(该态附近没可乐观够到的 gem·potential_atk 退化为当前 atk)。"""
    h = state.hero
    f = state.current_floor
    best, bd = None, 10 ** 9
    for cell in REDGEMS:
        if cell[0] != f:
            continue
        if _is_cleared(state, cell):              # 已拿
            continue
        d = abs(h.x - cell[1]) + abs(h.y - cell[2])
        if d < bd:
            bd, best = d, cell
    return best


def potential_atk_prod(state, seg, L):
    """生产版乐观 lookahead：朝【最近未拿红宝石】贪心走最多 L 步·返回 L 步内可达 max atk。
    复用 §S61 potential_atk(固定 target 贪心链·O(L) 每态·非指数展开·不撞 MT7 爆炸)。"""
    tgt = nearest_untaken_gem(state)
    if tgt is None:
        return state.hero.atk
    return potential_atk(state, seg, tgt, (), L)


def make_score_fn(phi_loss, seg, L, mult=MULT):
    """字典序主键换 potential_atk·其余全留(def 次键·hp−Φ+key_credit 末键)。L=0 → 退回纯 §S55。"""
    if L <= 0:
        def score_fn0(state):
            h = state.hero
            return (h.atk, h.def_, h.hp - phi_loss(state) + key_credit(h, mult))
        return score_fn0

    def score_fn(state):
        h = state.hero
        pa = potential_atk_prod(state, seg, L)
        return (pa, h.def_, h.hp - phi_loss(state) + key_credit(h, mult))
    return score_fn


# ════════════════════════════════ 预验(--verify) ════════════════════════════════
def _replay_route_to(tok):
    toks = decode_route(ROUTE)
    S = build_initial_state()
    for i in range(tok):
        S = step(S, toks[i])
    return S


def _fmt(st):
    h = st.hero
    return (f"{st.current_floor}({h.x},{h.y}) ATK{h.atk} DEF{h.def_} HP{h.hp} "
            f"Y{h.keys.get('yellowKey',0)} B{h.keys.get('blueKey',0)} kc={key_credit(h,MULT):.0f}")


def verify(L, phi_loss, seg):
    print("=" * 96)
    print(f"§S62 预验 L={L}：①复活囤血? ②救蓝门? ③速度跑得完?  （别直接挂全跑赌一晚）")
    print("=" * 96)

    def tail(st):
        h = st.hero
        return h.hp - phi_loss(st) + key_credit(h, MULT)

    # ── 验①：P2 绕路/囤血 tok773 —— L=8 会不会让囤血态 X 乐观升档(复活 §S54) ──
    print("\n[验① 复活囤血? · P2 绕路 tok773 · 正确=Y拿了 gem(atk↑)·X囤血赢即复活]")
    S2 = _replay_route_to(773)
    X = S2                                   # 囤血/绕路起点 atk25 高 HP
    walk, Y = X, None
    for _ in range(20):                      # 朝 gem 走到 atk 涨 = 刚拿 gem 的 Y
        nxt = free_reach_step_toward(walk, seg, GEM_DETOUR, FLY_ATTRS)
        if nxt is None:
            break
        walk = nxt[1]
        if walk.hero.atk > X.hero.atk:
            Y = walk
            break
    print(f"  X 囤血起点：{_fmt(X)}   最近未拿 gem={nearest_untaken_gem(X)}")
    if Y is not None:
        print(f"  Y 刚拿gem ：{_fmt(Y)}")
    paX = potential_atk_prod(X, seg, L)
    paY = potential_atk_prod(Y, seg, L) if Y is not None else None
    print(f"  potential_atk(L={L}): X→{paX}   Y→{paY}")
    print(f"  L 扫描 X 的 potential_atk（跨过=升档=复活临界）：")
    crit = None
    for LL in (2, 5, 8, 10, 11, 12, 15):
        pa = potential_atk_prod(X, seg, LL)
        up = pa > X.hero.atk
        if up and crit is None:
            crit = LL
        print(f"     L={LL:>2} → {pa}{'  ←升档(复活囤血)' if up else ''}")
    # 主键判：lookahead 下 X vs Y 谁排前（X 排前=复活）
    if Y is not None:
        kX = (paX, X.hero.def_, tail(X))
        kY = (paY, Y.hero.def_, tail(Y))
        revive = kX > kY
        print(f"  → lookahead(L={L}) 主键: X={kX[0]} Y={kY[0]}  "
              f"{'❌ X≥Y·复活囤血!' if revive else '✅ Y>X·不复活'}  "
              f"(复活临界 L≈{crit})")
        v1_ok = not revive
    else:
        print("  ⚠ 没走到拿 gem 的 Y(绕路没通)·跳过主键判")
        v1_ok = (paX <= X.hero.atk)

    # ── 验②：P1 蓝门 tok469 —— L=8 能不能救 YELLOW(走两黄省蓝钥) ──
    print("\n[验② 救蓝门? · P1 蓝门 tok469 · 正确=YELLOW(省蓝钥)·硬 atk 主键会选 BLUE]")
    S1 = _replay_route_to(469)
    print(f"  决策态：{_fmt(S1)}")
    blue1 = rollout_to_gem(S1, seg, forbid=(), max_steps=1)[0]          # 开蓝门一步(atk23)
    yel1 = rollout_to_gem(S1, seg, forbid={BLUE_DOOR}, max_steps=1)[0]  # 走黄门一步(atk22)
    paB = potential_atk_prod(blue1, seg, L)
    paY2 = potential_atk_prod(yel1, seg, L)
    print(f"  BLUE 即时子：{_fmt(blue1)}  potential_atk(L={L})={paB}")
    print(f"  YELLOW即时子：{_fmt(yel1)}  potential_atk(L={L})={paY2}  最近gem={nearest_untaken_gem(yel1)}")
    kB = (paB, blue1.hero.def_, tail(blue1))
    kY2 = (paY2, yel1.hero.def_, tail(yel1))
    pick = "YELLOW" if kY2 > kB else "BLUE"
    v2_ok = (pick == "YELLOW")
    print(f"  → lookahead(L={L}) 主键: BLUE={kB[0]} YELLOW={kY2[0]}  选 {pick}  "
          f"{'✅ 救对(同主键比末键·YELLOW 留蓝钥)' if v2_ok else '❌ 还选 BLUE'}")

    # ── 验③：速度 —— 小批全跑测每态成本·推算 1.8M 够不够 5 小时 ──
    print("\n[验③ 速度? · 小批全跑(max_states=30000)测每态成本·推算全跑]")
    start, phi2, diag = setup()
    score_look = make_score_fn(phi2, make_seg_step(REAL_LEG_FLOORS), L)
    score_base = make_score_fn(phi2, make_seg_step(REAL_LEG_FLOORS), 0)
    SMALL = 30000
    rb = run_full(start, REDKEY_CELL, REAL_LEG_FLOORS, BEAM_K, SMALL, score_base, diag, enable_fly=True)
    rl = run_full(start, REDKEY_CELL, REAL_LEG_FLOORS, BEAM_K, SMALL, score_look, diag, enable_fly=True)
    # ★max_states 限制的是 states_generated(quotient.py:647 `states_generated >= max_states`)·
    #   不是 expanded！per-state 必须按 generated 算·否则 per_expanded×max_states(=generated) 混单位虚报。
    pb = rb._secs / max(rb.states_generated, 1)
    pl = rl._secs / max(rl.states_generated, 1)
    print(f"  基线(atk主键)  ：{rb._secs:6.1f}s / gen={rb.states_generated} (exp={rb.states_expanded}) = {pb*1e3:.3f} ms/gen")
    print(f"  lookahead(L={L})：{rl._secs:6.1f}s / gen={rl.states_generated} (exp={rl.states_expanded}) = {pl*1e3:.3f} ms/gen")
    print(f"  lookahead 增量倍数 ≈ {pl/max(pb,1e-9):.1f}×")
    for cap in (1_800_000, 2_500_000, 3_000_000):
        est = pl * cap
        print(f"  推算 max_states(gen)={cap:>9}: ≈ {est:7.0f}s = {est/3600:.2f}h  "
              f"{'✅ 5h 内' if est <= 5*3600 else '❌ 超 5h'}")
    # 给个能 5h 跑完的 max_states(generated) 上界
    cap_5h = int(5 * 3600 / max(pl, 1e-9))
    print(f"  → 5 小时能跑完的 max_states 上界 ≈ {cap_5h}")

    print("\n" + "=" * 96)
    print(f"预验结论 L={L}：①复活囤血={'否✅' if v1_ok else '是❌'}  "
          f"②救蓝门={'是✅' if v2_ok else '否❌'}  "
          f"③5h跑完 cap上界≈{cap_5h}")
    print("=" * 96)
    return dict(L=L, no_revive=v1_ok, saves_blue=v2_ok, cap_5h=cap_5h,
                ms_per_state=pl * 1e3, crit_L=crit)


# ════════════════════════════════ 全跑(无人值守) ════════════════════════════════
def _replay_pickups(acts):
    """从 build_initial_state 重放【前缀(开局→铁盾) + beam acts】到终态·查各 gem/血瓶拿没拿。"""
    try:
        tokens, _outer = load_tokens()
        full = list(tokens[:TOK_SHIELD + 1]) + list(acts)
        s = build_initial_state()
        for t in full:
            s = step(s, t)
            if s.dead:
                break
        picks = {f"{c[0]}({c[1]},{c[2]})": _is_cleared(s, c) for c in REDGEMS}
        mt1pot = sum(1 for c in MT1_POTIONS if _is_cleared(s, c))
        return s, picks, mt1pot
    except Exception as e:
        return None, {"_error": str(e)}, None


def full_run(L, max_states, mult=MULT):
    print("=" * 96)
    print(f"§S62 lookahead 全跑 · L={L} · max_states={max_states} · mult={mult} · fly=开 · beam_k={BEAM_K}")
    print(f"score = (potential_atk(L={L}·朝最近未拿红宝石乐观走), def, hp−Φ+key_credit×mult)")
    print(f"= §S55字典序 + §S43 mult=1 + §S56 fly  之上叠 lookahead 主键（CLAUDE.md 加X=结合）")
    print("=" * 96)
    t0 = time.time()
    start, phi_loss, diag = setup()
    seg = make_seg_step(REAL_LEG_FLOORS)
    print(f"setup(zone+Φ预计算) 就绪 {time.time()-t0:.1f}s · 起点 {_fmt(start)}", flush=True)

    score_fn = make_score_fn(phi_loss, seg, L, mult)
    res = run_full(start, REDKEY_CELL, REAL_LEG_FLOORS, BEAM_K, max_states, score_fn, diag,
                   enable_fly=True)

    maxatk = max((b["atk"] for b in res._best_by_floor.values()), default=0)
    maxhp = max((b["hp"] for b in res._best_by_floor.values()), default=0)
    print(f"\n found={res.found}  耗时={res._secs:.1f}s ({res._secs/3600:.2f}h)  hit_cap={res.hit_cap}")
    print(f" expanded={res.states_expanded} generated={res.states_generated} "
          f"distinct_fp={res.distinct_fingerprints} waves={res.n_waves} goal_hits={res.goal_hits}")
    print(f" 每态 ≈ {res._secs/max(res.states_expanded,1)*1e3:.3f} ms")

    print("\n ── 各层【到达过】最优属性 ──")
    for f in sorted(res._best_by_floor, key=lambda x: int(x[2:])):
        b = res._best_by_floor[f]
        bv = b["V"]
        bv_s = f"(atk{bv[0]},def{bv[1]},{bv[2]:.0f})" if isinstance(bv, tuple) else f"{bv:.0f}"
        print(f"   {f:>5}: n={b['n']:>8}  maxATK={b['atk']}  maxDEF={b['def']}  maxHP={b['hp']}  bestV={bv_s}")

    print(f"\n ★maxATK(全段)={maxatk}  maxHP(全段)={maxhp}")
    print(f"   破 25 (§S42/43基线)? {'★破了' if maxatk > 25 else '没破'}   "
          f"到 ATK27 (破红钥门临界)? {'★到了' if maxatk >= 27 else '没到'}")
    mt1_n = res._best_by_floor.get("MT1", {}).get("n", 0)
    print(f"   MT1 到达过? n={mt1_n} {'(fly 飞回去了)' if mt1_n else '(没到·MT1 仍被忽略)'}")

    sn = res._top["snap"]
    if sn:
        print(f"\n ── beam 最优态(score 最大) ──")
        print(f"   位置={sn['fl']}({sn['x']},{sn['y']})  ATK={sn['atk']} DEF={sn['def_']} HP={sn['hp']}  钥={sn['keys']}")
        print(f"   拿 MT10 红宝石? {sn['redgem']}")

    # ── gem/血瓶 pickup(重放最优锚点)──
    anchor = res._best_score if res._best_score.get("acts") is not None else res._best_acts
    print(f"\n ── gem/血瓶 pickup(重放 {'score最优' if anchor is res._best_score else 'max(atk,hp)'} 锚点)──")
    s_end, picks, mt1pot = _replay_pickups(anchor.get("acts") or [])
    if "_error" in picks:
        print(f"   ⚠ 重放查 pickup 失败: {picks['_error']}")
    else:
        print(f"   终态 {_fmt(s_end)}")
        for k, v in picks.items():
            star = " ★" if k.startswith("MT1(") or k.startswith("MT8(") else ""
            print(f"     红宝石 {k:<12}: {'拿了✓' if v else '没拿✗'}{star}")
        print(f"     MT1 血瓶(4颗中): 拿了 {mt1pot} 颗  {'✓' if mt1pot else '✗(MT1 仍被忽略)'}")

    print(f"\n ── 玩家关心结论(明早读)──")
    print(f"   用的 L = {L}")
    print(f"   found 红钥 = {res.found}  ({'★走到红钥格·破红钥!' if res.found else '没走到红钥(还差)'})")
    print(f"   maxATK = {maxatk}  (到27=拿到第5颗gem攒攻够·破红钥门临界)")
    print(f"   maxHP(全段) = {maxhp}  (基线§S55=579·§S54囤血=626·暴涨远超=复活囤血信号)")
    print(f"   MT1 gem 拿了? {picks.get('MT1(7,3)', 'n/a') if '_error' not in picks else 'n/a'}   "
          f"MT8 第5颗 gem 拿了? {picks.get('MT8(4,10)', 'n/a') if '_error' not in picks else 'n/a'}")
    print(f"   hit_cap = {res.hit_cap}  ({'⚠ 撞预算·没跑完·该加 max_states 或降 L' if res.hit_cap else '✓ 跑透了'})")
    print("=" * 96)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="只预验 L(复活囤血+救蓝门+速度)·不全跑")
    ap.add_argument("--L", type=int, default=8, help="lookahead 步数(主键=potential_atk(L))")
    ap.add_argument("--max-states", type=int, default=1_800_000)
    ap.add_argument("--mult", type=float, default=MULT)
    ap.add_argument("--out", type=str, default="", help="全跑输出文件(utf-8 行缓冲·无人值守)")
    args = ap.parse_args()
    if args.out:
        sys.stdout = open(args.out, "w", encoding="utf-8", buffering=1)

    if args.verify:
        start, phi_loss, diag = setup()
        seg = make_seg_step(REAL_LEG_FLOORS)
        verify(args.L, phi_loss, seg)
    else:
        full_run(args.L, args.max_states, args.mult)


if __name__ == "__main__":
    main()
