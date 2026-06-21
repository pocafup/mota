"""§S59 评估两个修法（只读探针·产品码零改动·不碰生产 score_fn）。

回答玩家"先评估别擅自改"：在 §S58 那个真实绕路决策点上，分别用三种【末键】重算
gem-ward 算子的字典序排名，看哪种修法真能把"去拿第5颗 gem 的态"排到前面：

  末键①pre   = hp − Φ_pre   + kc   （现状·Φ 阶段1 预 credit 未来 gem）
  末键②nopre = hp − Φ_nopre + kc   （修法1·Φ 只按【当前已拿】属性算 M 损血·不 plan 未来 gem）
  末键③dist  = hp − Φ_nopre + kc − W·dist(→gem)  （修法2·在修法1 上叠距离引导）

主键仍是 (atk, def)（字典序·零魔法数）——三种只动【末键】。

附：sanity——构造"刚拿 gem 的 atk26 态" vs "没拿的 atk25 态"，确认字典序主键是否
已让 atk26 碾压 atk25（验证玩家描述的 X>Y 拖延在 §S55 是否【已被主键治掉】）。

只读复用 _s58_gem27_probe 的 setup/链机制 + build_phi_s53 的 diag。
用法：python -u analysis/_s59_fix_eval.py
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis._s58_gem27_probe import (                               # noqa: E402
    setup, free_reach_step_toward, decode_route)
from analysis.smart_phi_s53_beam import key_credit, FLY_ATTRS         # noqa: E402
from analysis.dir2_redkey_pathloss_beam import (                      # noqa: E402
    REAL_LEG_FLOORS, make_seg_step)
from analysis.route_aware_phi_probe import cleared_monster_cells      # noqa: E402
from analysis.extract_zone1_milestones import build_initial_state     # noqa: E402
from sim.simulator import step                                        # noqa: E402

TARGET = ("MT8", 4, 10)
AT_TOKEN = 773  # §S58 用过的真实 atk25 MT8 决策点
ROUTE = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly.h5route"


def make_phis(diag):
    """返回 (phi_pre, phi_nopre)。
    phi_pre   = 生产 phi_loss（阶段1 贪心预 credit + 阶段2 残余）。
    phi_nopre = 只算【当前真实属性】下未清必经集 M 的损血（去掉阶段1·不 plan 未来 gem）。"""
    phi_pre = diag["phi_loss"]
    must_cells = diag["must_cells"]
    loss_one = diag["loss_one"]
    mon_cells = diag["mon_cells"]

    def phi_nopre(state):
        h = state.hero
        a, d = h.atk, h.def_
        planned = set(cleared_monster_cells(state, mon_cells))
        return sum(loss_one(a, d, c) for c in (must_cells - planned))

    return phi_pre, phi_nopre


def candidates(S, seg):
    """枚举 S 同层全部边界候选子态（只读复用 quotient）。返回 list[(op, child)]。"""
    from solver.quotient import _free_cells, _boundary_ops, _expand_op, _absorb
    free = _free_cells(S)
    ops = _boundary_ops(S, free, cross_floor=False, enable_fly=False, fly_attrs=None)
    out = []
    for op in ops:
        if op[0] == "fly":
            continue
        res = _expand_op(S, free, op, seg)
        if res is None:
            continue
        child, _mv = res
        if child.dead or child.current_floor != S.current_floor:
            continue
        if getattr(child.floor, "_event_intercepting", False):
            continue
        rchild, _ = _absorb(child, seg)
        if rchild.dead:
            continue
        out.append((op, rchild))
    return out


def dist_to_gem(st):
    if st.current_floor != TARGET[0]:
        return 999
    return abs(st.hero.x - TARGET[1]) + abs(st.hero.y - TARGET[2])


def rank_of(cands, gw_op, keyfn):
    """gw_op 在 cands 按 keyfn 降序里的字典序排名 / 候选数。"""
    rows = sorted(cands, key=lambda oc: keyfn(oc[1]), reverse=True)
    for r, (op, ch) in enumerate(rows, 1):
        if op == gw_op:
            return r, len(rows)
    return -1, len(rows)


def key_pre(phi_pre):
    return lambda st: (st.hero.atk, st.hero.def_,
                       st.hero.hp - phi_pre(st) + key_credit(st.hero, 1.0))


def key_nopre(phi_nopre):
    return lambda st: (st.hero.atk, st.hero.def_,
                       st.hero.hp - phi_nopre(st) + key_credit(st.hero, 1.0))


def key_dist(phi_nopre, W):
    return lambda st: (st.hero.atk, st.hero.def_,
                       st.hero.hp - phi_nopre(st) + key_credit(st.hero, 1.0)
                       - W * dist_to_gem(st))


def replay_to(at_token):
    tokens = decode_route(ROUTE)
    S = build_initial_state()
    for i in range(at_token):
        S = step(S, tokens[i])
    return S


def main():
    start, phi_loss, diag = setup()
    phi_pre, phi_nopre = make_phis(diag)
    seg = make_seg_step(REAL_LEG_FLOORS)

    S = replay_to(AT_TOKEN)
    h = S.hero
    print("=" * 96)
    print(f"§S59 修法评估 @ tok{AT_TOKEN}：{S.current_floor}({h.x},{h.y}) "
          f"HP{h.hp} ATK{h.atk} DEF{h.def_}  目标 gem={TARGET} 距={dist_to_gem(S)}")
    print(f"  Φ_pre(预credit)={phi_pre(S):.0f}   Φ_nopre(只算当前已拿)={phi_nopre(S):.0f}   "
          f"差={phi_pre(S)-phi_nopre(S):.0f}（=阶段1 预 credit 压低的量）")
    print("=" * 96)

    # ── 沿绕路链逐步：三种末键下 gem-ward 排名 ──
    print("\n[沿贪心绕路链·每步 gem-ward 算子在三种末键下的字典序排名/候选数]")
    print(f"  末键①pre=hp−Φ_pre+kc(现状)  ②nopre=hp−Φ_nopre+kc(修法1)  "
          f"③dist=②−W·dist(修法2·W=30)\n")
    print(f"{'步':>2} {'位置':<10} {'gem-ward算子':<16} {'atk':>3} {'hp':>5} "
          f"{'Φpre':>6} {'Φnopre':>7} {'rk①pre':>7} {'rk②nopre':>9} {'rk③dist':>8}")
    W = 30
    cur = S
    for stepn in range(0, 14):
        cands = candidates(cur, seg)
        gw = free_reach_step_toward(cur, seg, TARGET, FLY_ATTRS)
        if not cands or gw is None:
            print("  （无候选 / 朝 gem 无算子·停）")
            break
        gw_op, gw_child = gw
        r1, n = rank_of(cands, gw_op, key_pre(phi_pre))
        r2, _ = rank_of(cands, gw_op, key_nopre(phi_nopre))
        r3, _ = rank_of(cands, gw_op, key_dist(phi_nopre, W))
        ch = gw_child
        opd = f"{gw_op[0]}@({gw_op[1]},{gw_op[2]})"
        reached = (ch.hero.x, ch.hero.y) == (TARGET[1], TARGET[2])
        mark = " ★到gem" if reached else ""
        print(f"{stepn:>2} {cur.current_floor}({cur.hero.x},{cur.hero.y}) {opd:<16} "
              f"{ch.hero.atk:>3} {ch.hero.hp:>5} {phi_pre(ch):>6.0f} {phi_nopre(ch):>7.0f} "
              f"{r1:>3}/{n:<3} {r2:>4}/{n:<3} {r3:>3}/{n:<3}{mark}")
        cur = ch
        if reached:
            print("  ★拿到 gem：atk +1 → 主键跃升（三种末键此后都排第1·问题在能否【走到】这步）")
            break

    # ── 入口决策点：现状末键 vs 修法1 末键·完整候选三项（看修法1 动没动相对序）──
    print("\n[入口决策点全候选·末键①pre vs ②nopre 正面对照·看修法1 改没改 gem-ward 相对名次]")
    cands = candidates(S, seg)
    gw = free_reach_step_toward(S, seg, TARGET, FLY_ATTRS)
    gw_op = gw[0] if gw else None
    for tag, kf in (("①pre", key_pre(phi_pre)), ("②nopre", key_nopre(phi_nopre))):
        rows = sorted(cands, key=lambda oc: kf(oc[1]), reverse=True)
        print(f"\n  末键{tag}：")
        print(f"  {'rk':>2} {'算子':<16} {'落点':<12} {'atk':>3} {'def':>3} {'hp':>5} "
              f"{'末键值':>9}")
        for r, (op, ch) in enumerate(rows, 1):
            mark = "→gem" if op == gw_op else ""
            opd = f"{op[0]}@({op[1]},{op[2]})"
            pos = f"{ch.current_floor}({ch.hero.x},{ch.hero.y})"
            tv = kf(ch)[2]
            print(f"{mark:>4}{r:>2} {opd:<16} {pos:<12} {ch.hero.atk:>3} "
                  f"{ch.hero.def_:>3} {ch.hero.hp:>5} {tv:>9.0f}")

    # ── 入口处把 gem-ward 翻到 rk1 需要多大 W（修法2 标定）──
    print("\n[入口处·修法2 距离权重标定：gem-ward 翻到 rk1 需要多大 W]")
    cands = candidates(S, seg)
    gw = free_reach_step_toward(S, seg, TARGET, FLY_ATTRS)
    if gw:
        gw_op = gw[0]
        flipped = None
        for W in (0, 5, 10, 20, 30, 50, 80, 120, 200, 400):
            r, n = rank_of(cands, gw_op, key_dist(phi_nopre, W))
            print(f"  W={W:>3}: gem-ward rk={r}/{n}")
            if r == 1 and flipped is None:
                flipped = W
        print(f"  → gem-ward 第一次到 rk1 的 W ≈ {flipped}（HP/步·这是修法2 要调的旋钮量级）")

    # ── sanity：字典序主键是否已让 atk26(拿了) 碾压 atk25(没拿) ──
    print("\n[sanity：构造'刚拿gem的atk26态' vs '没拿的atk25态'·验主键是否已治 X>Y 拖延]")
    walk = S
    grabbed = None
    for _ in range(20):
        nxt = free_reach_step_toward(walk, seg, TARGET, FLY_ATTRS)
        if nxt is None:
            break
        walk = nxt[1]
        if (walk.hero.x, walk.hero.y) == (TARGET[1], TARGET[2]) or walk.hero.atk > S.hero.atk:
            grabbed = walk
            break
    if grabbed is not None:
        kf = key_pre(phi_pre)
        vx = kf(S)         # 没拿(atk25)
        vy = kf(grabbed)   # 拿了(atk≥26)
        print(f"  X 没拿: atk{S.hero.atk} hp{S.hero.hp}  字典序键={tuple(round(v,0) if isinstance(v,float) else v for v in vx)}")
        print(f"  Y 拿了: atk{grabbed.hero.atk} hp{grabbed.hero.hp}  字典序键={tuple(round(v,0) if isinstance(v,float) else v for v in vy)}")
        print(f"  Y > X（字典序）? {vy > vx}  "
              f"{'→ 主键已让 atk↑ 态碾压·X>Y 拖延在 §S55 已治' if vy > vx else '→ 仍 X>Y·主键没治住'}")
    else:
        print("  （没走到拿 gem 的态·跳过 sanity）")


if __name__ == "__main__":
    main()
