"""§S58 攻 ATK27：dump"为什么 beam 不为第5颗 gem(MT8(4,10)) 绕路顶 atk27"。

只读探针（复用 build_phi_s53 / key_credit / quotient·产品码零改动）。回答玩家两个候选原因：
  原因A=主键贪近：绕路中间态 atk 不变(还没拿 gem)·hp 降→字典序末键把它排后被截。
  原因B=Φ估值不够：Φ 对 MT8(4,10) 的价值(boss 减伤)算得不够→去拿它的态 Φ 没降→score 不够。

分两部分：
  --val   :  Φ 阶段1 对 5 颗 redGem 的 net=gain−cost 估值（含 MT8(4,10) vs MT10(10,6) 对照）
  --chain :  MT8 内部走绕路到 (4,10) 的决策链·每步拆 hp/Φ/key_credit·看 Φ 降不降+排名
"""
import argparse
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

from analysis.smart_phi_s53_beam import (                            # noqa: E402
    build_phi_s53, key_credit, FLY_ATTRS, BOSS_LEG_FLOORS, REDGEM_CELL,
    BOSS_ID, GUARD_ID)
from analysis.dir2_redkey_pathloss_beam import (                     # noqa: E402
    TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS, make_seg_step, replay_to_token,
    _monster_loss)
from analysis.route_aware_phi_probe import cleared_monster_cells     # noqa: E402
from sim.simulator import _copy_state                                # noqa: E402
from vzone import build_zone                                         # noqa: E402

GEM5 = [("MT1", 7, 3), ("MT3", 2, 9), ("MT8", 4, 10),
        ("MT9", 6, 5), ("MT10", 10, 6)]
MAX_POPS = 12000


def setup():
    zone = build_zone()
    start = replay_to_token(TOK_SHIELD)
    phi_loss, diag = build_phi_s53(start, REAL_LEG_FLOORS, REDKEY_CELL,
                                   zone, MAX_POPS, BOSS_LEG_FLOORS)
    return start, phi_loss, diag


def gem_index(items, cell):
    for i, it in enumerate(items):
        if (it[0], it[1], it[2]) == cell:
            return i
    return None


# ════════════════ --val：Φ 对 5 颗 gem 的估值 ════════════════
def val_mode():
    start, phi_loss, diag = setup()
    items = diag["items"]
    item_precost = diag["item_precost"]
    must_cells = diag["must_cells"]
    mon_cells = diag["mon_cells"]
    mons = diag["mons"]
    phi_route = diag["phi_route"]
    loss_one = diag["loss_one"]

    print("=" * 96)
    print("第1部分：5 颗 redGem 的可达性 + 必经集 M 重叠（看绕路成本来源）")
    print("=" * 96)
    print(f"必经集 M = {len(must_cells)} 怪（leg1 段起点→红钥 ∪ boss-leg MT9+MT10 全怪 ∪ 守卫）")
    print(f"REDGEM_CELL（Φ 专门算过 boss 价值的锚点）= {REDGEM_CELL}\n")
    print(f"{'gem':<14} {'idx':>3} {'precost(到达要打的怪)':>20} {'∈M的怪':>7} {'净绕路怪(precost−M)':>18}")
    for cell in GEM5:
        i = gem_index(items, cell)
        pc = item_precost[i] if i is not None else None
        if pc is None:
            print(f"{str(cell):<14} {str(i):>3} {'够不到(None)':>20}")
            continue
        in_m = pc & must_cells
        detour = pc - must_cells
        print(f"{str(cell):<14} {i:>3} {len(pc):>20} {len(in_m):>7} {len(detour):>18}")

    print("\n" + "=" * 96)
    print("第2部分：Φ 阶段1 贪心规划 trace（从铁盾起点 atk22·看哪些 gem 入选·net=gain−cost）")
    print("=" * 96)
    trace = []
    phi_loss(start, trace=trace)
    print(f"起点 atk={start.hero.atk} def={start.hero.def_}")
    print(f"{'步':>2} {'gem/道具':<16} {'stat':<4} {'a→':>4} {'gain':>7} {'cost':>7} "
          f"{'net':>8} {'净绕路怪数':>9}")
    planned_cells = set()
    for k, t in enumerate(trace, 1):
        planned_cells.add(t["cell"])
        print(f"{k:>2} {str(t['cell']):<16} {t['stat']:<4} {t['a_after']:>4} "
              f"{t['gain']:>7.0f} {t['cost']:>7.0f} {t['net']:>8.0f} {t['extra']:>9}")
    print(f"\n阶段1 规划入选道具格：{sorted(planned_cells)}")
    for cell in GEM5:
        mark = "✅入选" if cell in planned_cells else "❌没入选"
        print(f"  {str(cell):<14} {mark}")

    print("\n" + "=" * 96)
    print("第3部分：MT8(4,10) vs MT10(10,6) 在【a=26 boss临界点】的 gain/cost/net 手工对照")
    print("（gain 用 phi_route(26)−phi_route(27) 差分·含 boss 减伤；这是第5颗 gem 该被估到的价值）")
    print("=" * 96)
    a26, d = 26, start.hero.def_
    # boss/守卫 减伤独立量化（26→27）
    boss_cells = [c for c, m in mon_cells.items() if m == BOSS_ID]
    guard_cells = [c for c, m in mon_cells.items() if m == GUARD_ID]
    print(f"\n[26→27 对关键怪的减伤]（def={d}·_monster_loss 实算）")
    for c in boss_cells:
        l26 = _monster_loss(26, d, mons[c], diag["mdef0"])
        l27 = _monster_loss(27, d, mons[c], diag["mdef0"])
        print(f"  boss   {c}: 损血 {l26}→{l27}  省 {l26-l27}")
    for c in guard_cells:
        l26 = _monster_loss(26, d, mons[c], diag["mdef0"])
        l27 = _monster_loss(27, d, mons[c], diag["mdef0"])
        print(f"  守卫   {c}: 损血 {l26}→{l27}  省 {l26-l27}")
    gain_full = phi_route(26, d) - phi_route(27, d)
    print(f"\nphi_route(26,{d})−phi_route(27,{d}) = 必经集 M 全减伤 = {gain_full:.0f}"
          f"  （这是 26→27 任意 +1atk gem 的 gain·含 boss+守卫+M 内全怪）")
    print("\n各 gem 在 a=26 的【独立】成本（净绕路怪 precost−M·按 a=26,d 实算损血）：")
    for cell in (("MT8", 4, 10), REDGEM_CELL):
        i = gem_index(items, cell)
        pc = item_precost[i]
        detour = pc - must_cells
        cost = sum(loss_one(26, d, c) for c in detour)
        net = gain_full - cost
        flag = "✅净正" if net > 0 else "❌净负→Φ不规划→不给信用"
        print(f"  {str(cell):<14} 净绕路怪={len(detour):>2}  cost={cost:>5.0f}  "
              f"net=gain{gain_full:.0f}−cost{cost:.0f}={net:>6.0f}  {flag}")
        if detour:
            print(f"      绕路怪明细：", end="")
            for c in sorted(detour):
                print(f"{c}({mons[c].id if hasattr(mons[c],'id') else '?'},"
                      f"loss{loss_one(26,d,c):.0f})", end=" ")
            print()


# ════════════════ --chain：MT8 绕路到 (4,10) 决策链 ════════════════
def free_reach_step_toward(S, seg, target, fly_attrs):
    """从 S 出发·用 quotient 边界算子里【最朝向 target】的算子展开一步（贪心逼近 gem）。
    返回 (op, child) 或 None。只读复用 quotient 内部。"""
    from solver.quotient import _free_cells, _boundary_ops, _expand_op, _absorb
    free = _free_cells(S)
    ops = _boundary_ops(S, free, cross_floor=False, enable_fly=False, fly_attrs=None)
    tf, tx, ty = target
    best = None
    best_d = None
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
        # 距 target 的曼哈顿（同层）
        if rchild.current_floor != tf:
            continue
        dist = abs(rchild.hero.x - tx) + abs(rchild.hero.y - ty)
        if best_d is None or dist < best_d:
            best_d, best = dist, (op, rchild)
    return best


def all_candidates_tail(S, seg, score_parts):
    """枚举 S 的全部同层边界候选·返回按字典序降序的 (op, child, parts) 列表（=beam 偏好序）。"""
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
        out.append((op, rchild, score_parts(rchild)))
    out.sort(key=lambda r: (r[2]["atk"], r[2]["dv"], r[2]["tail"]), reverse=True)
    return out


def decode_route(path):
    import json as _json
    from extract.decode_route import parse_rle_route, decompress
    outer = _json.loads(decompress(Path(path).read_text(encoding="utf-8").strip()))
    return parse_rle_route(decompress(outer["route"]))


def chain_mode(at_token):
    """从真实路线 replay 到 at_token（英雄此时在 MT8）·贪心朝 gem(4,10) 走·每步拆三项·
    看绕路链上 atk 是否不变[原因A]·Φ 是否随接近 gem 下降[原因B]·tail 保不保。"""
    from analysis.extract_zone1_milestones import build_initial_state
    from sim.simulator import step
    start, phi_loss, diag = setup()
    seg = make_seg_step(REAL_LEG_FLOORS)
    KEY_HP = {"yellowKey": 20, "blueKey": 100, "redKey": 1600}

    def score_parts(st):
        h = st.hero
        phi = phi_loss(st)
        kc = key_credit(h, 1.0)
        return dict(atk=h.atk, dv=h.def_, hp=h.hp, phi=phi, kc=kc,
                    tail=h.hp - phi + kc)

    route = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly.h5route"
    tokens = decode_route(route)
    S = build_initial_state()
    for i in range(at_token):
        S = step(S, tokens[i])
    print("=" * 96)
    print(f"--chain：replay 到 tok{at_token}·英雄在 {S.current_floor}({S.hero.x},{S.hero.y})·"
          f"贪心朝 gem(4,10) 走·拆三项")
    print("=" * 96)
    if S.current_floor != "MT8":
        print(f"⚠ tok{at_token} 不在 MT8（在 {S.current_floor}）·换 token")
        return
    target = ("MT8", 4, 10)
    p0 = score_parts(S)
    print(f"起点态：HP{p0['hp']} ATK{p0['atk']} DEF{p0['dv']} "
          f"Φ={p0['phi']:.0f} kc={p0['kc']:.0f} tail(hp−Φ+kc)={p0['tail']:.0f}\n")

    # ── 入口决策点：全候选三项分解（gem-ward 态 vs 留下来的态正面对照）──
    print("[入口决策点全候选·字典序降序=beam 偏好序·顶部被留]")
    cand0 = all_candidates_tail(S, seg, score_parts)
    gw = free_reach_step_toward(S, seg, target, FLY_ATTRS)
    gw_op = gw[0] if gw else None
    print(f"{'':>2} {'rk':>2} {'算子':<16} {'落点':<12} {'atk':>3} {'def':>3} "
          f"{'hp':>5} {'Φ':>6} {'kc':>5} {'tail':>7}")
    for rk, (op, ch, p) in enumerate(cand0, 1):
        mark = "→gem" if op == gw_op else ""
        opd = f"{op[0]}@({op[1]},{op[2]})"
        pos = f"{ch.current_floor}({ch.hero.x},{ch.hero.y})"
        print(f"{mark:>4} {rk:>2} {opd:<16} {pos:<12} {p['atk']:>3} {p['dv']:>3} "
              f"{p['hp']:>5} {p['phi']:>6.0f} {p['kc']:>5} {p['tail']:>7.0f}")
    print()
    print(f"{'步':>2} {'到达格':<10} {'打/开':<22} {'atk':>3} {'hp':>5} {'Φ':>6} "
          f"{'kc':>5} {'tail':>7} {'Δtail':>7} {'gem-ward排名/候选数':>16}")
    cur = S
    prev_tail = p0["tail"]
    for stepn in range(1, 30):
        cand = all_candidates_tail(cur, seg, score_parts)
        if not cand:
            print("  （无候选·停）")
            break
        nxt = free_reach_step_toward(cur, seg, target, FLY_ATTRS)
        if nxt is None:
            print("  （朝 gem 无可走算子·停）")
            break
        op, child = nxt
        # gem-ward 算子在全候选里的字典序排名
        rank = next((r for r, (o, c, p) in enumerate(cand, 1)
                     if o == op), -1)
        p = score_parts(child)
        opdesc = f"{op[0]}@({op[1]},{op[2]})"
        dtail = p["tail"] - prev_tail
        reached = (child.hero.x, child.hero.y) == target
        mark = "  ★到gem" if reached else ""
        print(f"{stepn:>2} ({child.hero.x},{child.hero.y})    {opdesc:<22} "
              f"{p['atk']:>3} {p['hp']:>5} {p['phi']:>6.0f} {p['kc']:>5} "
              f"{p['tail']:>7.0f} {dtail:>+7.0f} {rank:>6}/{len(cand):<5}{mark}")
        prev_tail = p["tail"]
        cur = child
        if reached:
            print("\n★到达 gem·atk +1（主键跃升·若能走到这一步则被 beam 留住）")
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", action="store_true", help="Φ 对 5 颗 gem 的估值")
    ap.add_argument("--chain", action="store_true", help="MT8 绕路决策链三项")
    ap.add_argument("--atk", type=int, default=26)
    args = ap.parse_args()
    if args.val:
        val_mode()
    elif args.chain:
        chain_mode(args.atk)
    else:
        print("指定 --val 或 --chain")


if __name__ == "__main__":
    main()
