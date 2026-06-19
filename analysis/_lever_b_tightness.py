"""【Lever B 第7步·离线紧度验证·只读·零产品码】R1 形上界 U=hp+G−D 能砍多少 6262 指纹。

在 forward_enumerate（§S49/Lever A 同口径）枚举出的【每个节点】上离线算可采纳上界 U，
数各层（重点 MT7）剪枝率 U≤LB，判定"可采纳界分支定界"对 MT7 指纹爆炸是否有判断力。

【为什么算【一对括号】夹住答案（同一 G=全取剩余血·都是引擎实算）】
  恒等式（HP 守恒·从 node0 起）：U_adm0(s) = hp(s) + G_remaining(s) = (hp0+G_total) − lost_so_far(s)。
    G_remaining = s 视图里地图上还剩的血（引擎 items.json hp 效果实算）。lost_so_far = 从 node0 起已损血。
  · U_adm0 = hp + G_remaining            （D=0·最松【严格可采纳】上界 U≥V；绝不低估 → 绝不剪最优）
        → 它的剪枝率 = 可采纳分支定界能力的【严格下界】（真 U 加 D≥0 只会更小、剪更多）。
  · U_aggr = hp + G_remaining − Φ_killall（Φ=compute_combat 杀光剩余怪损血·D 取上界 → U 取下界）
        → 非可采纳（会误剪），但剪枝率 = 这族(hp+G_full−D)上界能力的【乐观天花板】。
  真·可采纳 B&B（精确 D必经）剪枝率 ∈ [prune(U_adm0), prune(U_aggr)]（同 G_full 族内）。
    ① 下界(U_adm0)已高 → Lever B 必成、直接实现分支定界。
    ② 天花板(U_aggr)已低 → 乐观也砍不动 MT7 → 别实现 B&B、走兜底【更聪明 Φ】。
    ③ 跨界(低..高) → 答案取决于精确 D必经（割点法）→ 值得实现割点 D 收窄；本脚本据实报、不替玩家拍。

★铁律遵守：G 用 items.json 的 hp 效果（_item_hp_value 复刻引擎 _apply_item_effect）、
  D/Φ 用引擎 compute_combat（复用 dir2 的 _monster_loss 口径），【绝不手写战斗公式】。
★只读：不碰任何产品码/封板件（forward_enumerate 逻辑就地复刻+加 U 钩子·beam 一字未动）。
★G_full 是【松】上界（全 9 层血数千 HP）→ 预判 U_adm0 在现实 LB 下剪枝率可能≈0；这正是要【实测】的，
  别先验下结论（玩家红线）。lost_so_far 分布同时打出来，让"要剪到 LB 需损血≥X、但实测最多 Y"一目了然。

用法：python -u analysis/_lever_b_tightness.py [--max-states 300000]
"""
import argparse
import os
import sys
import time
from collections import Counter, deque
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.dir2_redkey_pathloss_beam import (replay_to_token, make_seg_step,   # noqa: E402
                                                TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS)
from sim.simulator import _load_floor_if_needed, _build_monster                    # noqa: E402
from sim.combat import compute_combat, PlayerState                                 # noqa: E402
from solver.quotient import (_absorb, _boundary_ops, _expand_op, _free_cells,      # noqa: E402
                             _qfp, _bfs_moves, value_vector)
from solver.search import _ge_all                                                  # noqa: E402

DISTINGUISH_DOORS = True
SEG = REAL_LEG_FLOORS
SEGSET = set(SEG)

# Φ/loss 密网格范围（与 dir2 一致·铁盾 ATK22/DEF20 起步·宽到远超红钥所需）
A_LO, A_HI = 15, 45
D_LO, D_HI = 10, 45
_BIG_HP = 10 ** 7


def vkey(vec):
    return tuple(sorted(vec.items()))


def _item_hp_value(idata, ratio):
    """拾取该道具【增加多少 HP】——复刻引擎 _apply_item_effect 的 hp 分支（sim/simulator.py:1281）。
    stat+hp: ratio_scaled→base*ratio 否则 delta；multi: 累加 hp op 的 delta。其余→0。"""
    eff = idata.get("pickup") if idata else None
    if not isinstance(eff, dict):
        return 0
    t = eff.get("type")
    if t == "stat" and eff.get("stat") == "hp":
        return eff["base"] * ratio if eff.get("ratio_scaled") else eff.get("delta", 0)
    if t == "multi":
        return sum(op.get("delta", 0) for op in eff.get("ops", ()) if op.get("stat") == "hp")
    return 0


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _monster_loss_val(atk, def_, mon, mdef):
    """单怪 compute_combat 损血（引擎实算）。打不动(atk≤mon_def)→用刚好可打(atk=mon_def+1)的损血
    当惩罚（同 dir2 口径·纯怪属性·无魔法数）。【绝不手写战斗公式】。"""
    r = compute_combat(PlayerState(hp=_BIG_HP, atk=atk, def_=def_, mdef=mdef), mon)
    if r.damage is not None:
        return r.damage
    r2 = compute_combat(PlayerState(hp=_BIG_HP, atk=mon.def_ + 1, def_=def_, mdef=mdef), mon)
    return r2.damage if r2.damage is not None else mon.hp


def build_tables(start):
    """普查段内 9 层全部楼层，预存：
      blood_val[f]  = {tile_id: hp_value}      （地图血瓶 tile → 引擎 hp 增量）
      full_blood[f] = 该层满血总量（未拾任何道具时）
      full_mons[f]  = [mid,...]                （该层全部怪·供未加载层 Φ 用）
      mon_obj[mid]  = 怪对象（compute_combat 入参）
      superpot_cnt  = 段内 superPotion 数（pickup=null 不入 _gives_hp_on_pickup·须单独保上界·防 G 低估）
    """
    blood_val, full_blood, full_mons = {}, {}, {}
    mon_obj = {}
    superpot_cnt = 0
    for f in SEG:
        if not _load_floor_if_needed(start, f):
            print(f"  ⚠ {f} 加载失败(文件缺)→ 该层按空处理")
            blood_val[f], full_blood[f], full_mons[f] = {}, 0, []
            continue
        fl = start.floors[f]
        t2i, db, t2e, ratio = fl._tile_to_item, fl._items_db, fl._tile_to_enemy, fl.ratio
        bv, tot, mons = {}, 0, []
        for row in fl.entities:
            for tile in row:
                if not tile:
                    continue
                iid = t2i.get(tile)
                if iid is not None:
                    hv = _item_hp_value(db.get(iid), ratio)
                    if hv:
                        bv[tile] = hv
                        tot += hv
                    if iid == "superPotion":
                        superpot_cnt += 1
                    continue
                mid = t2e.get(tile)
                if mid:
                    mons.append(mid)
                    if mid not in mon_obj:
                        mon_obj[mid] = _build_monster(start, mid)
        blood_val[f], full_blood[f], full_mons[f] = bv, tot, mons
    return blood_val, full_blood, full_mons, mon_obj, superpot_cnt


def make_compute_U(blood_val, full_blood, full_mons, mon_obj, mdef, superpot_bonus):
    """返回 compute_U(state) -> (U_adm0, U_aggr, G_remaining, Phi_killall)。
    G_remaining = 该 state 视图地图剩余血（已加载层扫实体·未加载层用满血常量）。
    Phi_killall = 杀光该 state 全部剩余怪的 compute_combat 损血（已加载层扫·未加载层全怪）。"""
    loss_cache = {}

    def loss_at(mid, atk, def_):
        a, d = _clamp(atk, A_LO, A_HI), _clamp(def_, D_LO, D_HI)
        k = (mid, a, d)
        r = loss_cache.get(k)
        if r is None:
            r = _monster_loss_val(a, d, mon_obj[mid], mdef)
            loss_cache[k] = r
        return r

    def compute_U(state):
        h = state.hero
        atk, def_ = h.atk, h.def_
        G = float(superpot_bonus)
        Phi = 0.0
        loaded = set(state.floors) & SEGSET
        for f in SEG:
            if f in loaded:
                fl = state.floors[f]
                bv, t2e = blood_val[f], fl._tile_to_enemy
                for row in fl.entities:
                    for tile in row:
                        if not tile:
                            continue
                        hv = bv.get(tile)
                        if hv:
                            G += hv
                            continue
                        mid = t2e.get(tile)
                        if mid:
                            Phi += loss_at(mid, atk, def_)
            else:
                G += full_blood[f]
                for mid in full_mons[f]:
                    Phi += loss_at(mid, atk, def_)
        U0 = h.hp + G
        return U0, U0 - Phi, G, Phi

    return compute_U


def enumerate_with_U(start_state, goal_cell, step_fn, max_states, compute_U):
    """就地复刻 forward_enumerate（cross_floor·fly OFF·DISTINGUISH_DOORS·同节点口径），
    每【新建节点】用 compute_U(state) 记一条 (floor, gid, U_adm0, U_aggr, G, Phi)。"""
    cross_floor = True
    goal_floor, gx, gy = goal_cell

    start, _sm = _absorb(start_state, step_fn)
    start_fp = _qfp(start, _free_cells(start), DISTINGUISH_DOORS)
    start_node = (start_fp, vkey(value_vector(start)))
    node_id = {start_node: 0}
    goal_hp = {}

    fp_gid = {start_fp: 0}
    gid_floor = [start_fp[0]]
    floor_of_id = [start_fp[0]]
    gid_of_id = [0]
    u0_0, _uag0, _g0, phi_0 = compute_U(start)
    U0_of_id = [u0_0]
    Phi_of_id = [phi_0]
    amax = [start.hero.atk]
    dmax = [start.hero.def_]
    visited = {start_fp: [value_vector(start)]}

    def get_gid(fp):
        g = fp_gid.get(fp)
        if g is None:
            g = len(gid_floor)
            fp_gid[fp] = g
            gid_floor.append(fp[0])
        return g

    def add_node(fp, vec, state):
        nd = (fp, vkey(vec))
        i = node_id.get(nd)
        if i is None:
            i = len(node_id)
            node_id[nd] = i
            g = get_gid(fp)
            floor_of_id.append(fp[0])
            gid_of_id.append(g)
            u0, _uag, _g, phi = compute_U(state)
            U0_of_id.append(u0)
            Phi_of_id.append(phi)
            if state.hero.atk > amax[0]:
                amax[0] = state.hero.atk
            if state.hero.def_ > dmax[0]:
                dmax[0] = state.hero.def_
        return i

    wave = [(start, 0)]
    gen = 0
    hit_cap = False
    while wave and not hit_cap:
        nxt = []
        for state, pid in wave:
            free = _free_cells(state)
            if state.current_floor == goal_floor and (gx, gy) in free:
                walk = _bfs_moves(state, free, (gx, gy))
                if walk is not None:
                    gs, ok = state, True
                    for m in walk:
                        gs = step_fn(gs, m)
                        if gs.dead:
                            ok = False
                            break
                    if ok and (gs.hero.x, gs.hero.y) == (gx, gy):
                        ghp = value_vector(gs)["hp"]
                        if goal_hp.get(pid, -1) < ghp:
                            goal_hp[pid] = ghp
            ops = _boundary_ops(state, free, cross_floor, False, None)
            for op in ops:
                res = _expand_op(state, free, op, step_fn)
                gen += 1
                if res is None:
                    continue
                child, _om = res
                if child.floor._event_intercepting:
                    continue
                rchild = child
                if rchild.current_floor != state.current_floor:
                    if not (op[0] == "fly" or op[0] == "stair"):
                        continue
                rchild, _abs = _absorb(rchild, step_fn)
                if rchild.dead:
                    continue
                fp = _qfp(rchild, _free_cells(rchild), DISTINGUISH_DOORS)
                cvec = value_vector(rchild)
                cur = visited.get(fp)
                dom_strict = equal = False
                if cur is not None:
                    for v in cur:
                        if _ge_all(v, cvec):
                            if _ge_all(cvec, v):
                                equal = True
                            else:
                                dom_strict = True
                            break
                if dom_strict:
                    continue
                add_node(fp, cvec, rchild)
                if equal:
                    continue
                if cur is None:
                    visited[fp] = [cvec]
                else:
                    visited[fp] = [v for v in cur if not _ge_all(cvec, v)] + [cvec]
                nxt.append((rchild, _node_id_of(node_id, fp, cvec)))
                if gen >= max_states:
                    hit_cap = True
                    break
            if hit_cap:
                break
        wave = nxt

    return dict(n=len(node_id), gen=gen, hit_cap=hit_cap, distinct_fp=len(visited),
                goal_hp=goal_hp, floor_of_id=floor_of_id, gid_of_id=gid_of_id,
                gid_floor=gid_floor, U0=U0_of_id, Phi=Phi_of_id,
                atk_max=amax[0], def_max=dmax[0])


def _node_id_of(node_id, fp, vec):
    return node_id[(fp, vkey(vec))]


def by_floor(g, alpha):
    """给定 α，算 U_α(node)=U0−α·Φ_clear，按层返回：
       node_U[floor]=[U_α,...]（节点）  fp_U[floor]=[max_gid U_α,...]（指纹·全 vec 都≤LB 才算灭）。"""
    floor_of_id, gid_of_id = g["floor_of_id"], g["gid_of_id"]
    gid_floor, U0, Phi = g["gid_floor"], g["U0"], g["Phi"]
    node_U = {}
    gid_max = [float("-inf")] * len(gid_floor)
    for cid in range(g["n"]):
        u = U0[cid] - alpha * Phi[cid]
        node_U.setdefault(floor_of_id[cid], []).append(u)
        gg = gid_of_id[cid]
        if u > gid_max[gg]:
            gid_max[gg] = u
    fp_U = {}
    for gg, fl in enumerate(gid_floor):
        fp_U.setdefault(fl, []).append(gid_max[gg])
    return node_U, fp_U


def _pct(vals, lb):
    if not vals:
        return 0.0
    return 100.0 * sum(1 for v in vals if v <= lb) / len(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=300_000)
    args = ap.parse_args()

    print("=" * 88)
    print(f"Lever B 第7步·离线紧度验证 (redkey 段·max_states={args.max_states}·fly OFF)")
    print("=" * 88, flush=True)

    start = replay_to_token(TOK_SHIELD)
    seg_step = make_seg_step(SEG)
    h = start.hero
    print(f"起点 {start.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"goal={REDKEY_CELL} 段={SEG}", flush=True)

    t0 = time.time()
    blood_val, full_blood, full_mons, mon_obj, superpot_cnt = build_tables(start)
    g_total_full = sum(full_blood.values())
    n_mons = sum(len(v) for v in full_mons.values())
    superpot_bonus = 0
    if superpot_cnt:
        superpot_bonus = superpot_cnt * (round(0.74 * (A_HI + D_HI)) * 10)
    print(f"\n段内血/怪普查 {time.time()-t0:.1f}s：满血 G_total(tok454)={g_total_full} "
          f"(各层 {{{', '.join(f'{f}:{full_blood[f]}' for f in SEG if full_blood[f])}}})")
    print(f"  怪 {n_mons} 只（{len(mon_obj)} 种）| superPotion={superpot_cnt} "
          f"→ G 加常量上界 {superpot_bonus}（pickup=null·防 G 低估·略松但保可采纳）")

    compute_U = make_compute_U(blood_val, full_blood, full_mons, mon_obj, h.mdef, superpot_bonus)

    print("\n[枚举] 复刻 §S49/Lever A 前向（每新节点算 U_adm0/U_aggr）...", flush=True)
    t0 = time.time()
    g = enumerate_with_U(start, REDKEY_CELL, seg_step, args.max_states, compute_U)
    print(f"  {time.time()-t0:.1f}s | 节点={g['n']} distinct_fp={g['distinct_fp']} "
          f"生成={g['gen']} hit_cap={g['hit_cap']}", flush=True)

    REF = g["U0"][0]   # = hp0+G_total0（node0 处 lost=0）→ lost_so_far(cid)=REF−U0[cid]
    ilb = max(g["goal_hp"].values()) if g["goal_hp"] else None
    print(f"  node0: U_adm0={REF:.0f} (=hp0+G_remaining@node0)  内部LB(到红钥最优hp)="
          f"{ilb if ilb is not None else '无(300k没够到红钥·同§S47)→靠外部LB/扫描'}")
    print(f"  段内属性天花板(实测 max)：ATK={g['atk_max']} DEF={g['def_max']}"
          f"（玩家'够用血量受段内属性天花板钉死'→ D必经 在此天花板下接近精确）")

    # node U0/Phi（α=0 时 U=U0=严格可采纳上界；α=1 时 U=U0−Φ=杀光怪）
    nodeU0, fpU0 = by_floor(g, 0.0)
    floors = sorted(nodeU0, key=lambda f: -len(nodeU0[f]))

    print("\n【lost_so_far 分布（从 node0 起已损血 = REF−U_adm0）·各层 min/中位/max】")
    print("  （U_adm0=hp+G_full 严格可采纳·D=0；要剪到 LB 需 lost≥REF−LB={:.0f}−LB）".format(REF))
    print(f"  {'层':>5} {'指纹':>6} {'节点':>7} | {'lost_min':>9} {'lost_中位':>9} {'lost_max':>9}")
    print("  " + "-" * 60)
    for fl in floors:
        lost = sorted(REF - u for u in nodeU0[fl])
        print(f"  {fl:>5} {len(fpU0[fl]):>6} {len(nodeU0[fl]):>7} | "
              f"{lost[0]:>9.0f} {median(lost):>9.0f} {lost[-1]:>9.0f}")

    # ── α 敏感度：D = α·Φ_clear(从该节点清光剩余怪的损血)。α=0=严格可采纳【下界】。──
    #    α 不是真路线、是"必打损血占清光损血的比例"敏感度旋钮；真 D必经 需割点法定。
    alphas = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]
    lbs = [0, 50, 100, 150, 200, 300, 400, 500, 587]
    if ilb is not None:
        lbs = sorted(set(lbs + [int(ilb)]))

    cache = {a: by_floor(g, a) for a in alphas}   # α -> (nodeU_by_floor, fpU_by_floor)

    def _series(a, floor_key, kind):
        nodeU, fpU = cache[a]
        src = fpU if kind == "fp" else nodeU
        if floor_key is None:                      # 全段合计
            return [v for vs in src.values() for v in vs]
        return src.get(floor_key, [])

    def grid(floor_key, title, kind):
        print(f"\n{title}")
        head = "  " + "LB\\α".rjust(6) + " | " + " ".join(f"{a:>6.2f}" for a in alphas)
        print(head)
        print("  " + "-" * (len(head) - 2))
        for lb in lbs:
            cells = [f"{_pct(_series(a, floor_key, kind), lb):>5.0f}%" for a in alphas]
            star = " ←内部LB" if ilb is not None and lb == int(ilb) else ""
            print(f"  {lb:>6} | " + " ".join(cells) + star)

    print("\n" + "=" * 88)
    print("【核心·MT7 指纹消灭%】行=LB·列=α(必打损血/清光损血比例)。α=0=严格可采纳下界(=0预期)。")
    print("  指纹消灭=该指纹【全部】vec 的 U≤LB（直接砍 6262 MT7 指纹的比例）。读法：现实 α 大约多少→对应列。")
    grid("MT7", "—— MT7 指纹消灭% ——", "fp")
    grid("MT7", "—— MT7 节点剪枝% ——", "node")
    grid(None, "—— 全段 节点剪枝%（None=全部楼层合计）——", "node")

    print("\n【判读·据实不替玩家拍】")
    print("  · α=0 列 = 严格可采纳【下界】(hp+G_full·D=0)：≈0% 是预期(G_full 太松·见 lost_max)。")
    print("  · 看 MT7 指纹消灭% 随 α 上升的【曲线拐点】：若需 α 很大(必打≈清光全怪)才砍得动 → 说明红钥有")
    print("    旁路(钥门绕守卫)使 D必经【小】→ 可采纳 B&B 砍不动 MT7 → 倾向兜底【更聪明 Φ】。")
    print("    若 α 很小(少量必打)就砍掉大半 MT7 指纹 → D必经 足够大 → 值得实现【割点法精确 D必经 + B&B】。")
    print("  · 真 α(=D必经/清光) 须割点法(乐观图:开全门/怪可穿·求 start→goal 的割怪)定，本脚本不臆断、留玩家拍。")


if __name__ == "__main__":
    main()
