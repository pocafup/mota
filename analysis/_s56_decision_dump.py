"""§S56 决策点 dump（玩家严查·先看清再改末键·别擅自改）。

解码 fly 半截路径 → 重放定位事件 → 在【决策态】用 quotient._boundary_ops 复现 beam 当时
面对的候选算子 → 把字典序 score 末键 (hp − Φ + key_credit) 拆成 hp / Φ / key_credit 三项，
看是哪一项让 beam 选错（MT9 浪费蓝钥 / 打无意义怪）。

只读：复用 build_phi_s53 / key_credit（smart_phi_s53_beam）、_boundary_ops / _expand_op /
_absorb / _free_cells（solver.quotient）、decode_route。★产品码（sim/solver）零改动。

用法：
  python -u analysis/_s56_decision_dump.py --events            # 列全程打怪/开门/换层事件 + token 号
  python -u analysis/_s56_decision_dump.py --dump 908,930      # dump 指定决策 token 的候选三项
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))   # vzone.py 等用无前缀 import（seg_identify_zone1 等）
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from extract.decode_route import parse_rle_route, decompress          # noqa: E402
from analysis.extract_zone1_milestones import build_initial_state     # noqa: E402
from sim.simulator import step, _copy_state                          # noqa: E402

ROUTE = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly.h5route"
DXDY = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
KEYS = ("yellowKey", "blueKey", "redKey")


def decode(path):
    outer = json.loads(decompress(path.read_text(encoding="utf-8").strip()))
    return parse_rle_route(decompress(outer["route"]))


def adj_cell(before, tok):
    """决策动作 tok（UDLR）朝向的相邻格 = 被打的怪格 / 被开的门格。"""
    dx, dy = DXDY.get(tok, (0, 0))
    return before.hero.x + dx, before.hero.y + dy


def keys_str(hero):
    return "{" + ",".join(f"{k[:1].upper()}{hero.keys.get(k, 0)}" for k in KEYS) + "}"


# ══════════════════════════ events 模式 ══════════════════════════
def events_mode():
    tokens = decode(ROUTE)
    print(f"解码 {ROUTE.name} → token 总数={len(tokens)}（期望 998 = 前缀455 + beam543）")
    s = build_initial_state()
    print(f"初态 floor={s.current_floor} ({s.hero.x},{s.hero.y}) HP{s.hero.hp}\n")
    n_kill = n_door = 0
    for i, t in enumerate(tokens):
        b = s
        s = step(s, t)
        bh, sh = b.hero, s.hero
        if sh.kill_count > bh.kill_count:
            ox, oy = adj_cell(b, t)
            ent = None
            try:
                ent = b.floor.entities[oy][ox]
            except Exception:
                pass
            n_kill += 1
            print(f"  tok{i:4d} KILL  {b.current_floor}({ox},{oy}) ent={ent}  "
                  f"损血={bh.hp - sh.hp:>3}  →HP{sh.hp} ATK{sh.atk} DEF{sh.def_} "
                  f"钥{keys_str(sh)} kills{sh.kill_count}")
        for k in KEYS:
            if sh.keys.get(k, 0) < bh.keys.get(k, 0):
                ox, oy = adj_cell(b, t)
                n_door += 1
                print(f"  tok{i:4d} DOOR  {b.current_floor}({ox},{oy}) 开{k} "
                      f"{bh.keys.get(k, 0)}→{sh.keys.get(k, 0)}  钥{keys_str(sh)}")
        if s.current_floor != b.current_floor:
            print(f"  tok{i:4d} FLOOR {b.current_floor}→{s.current_floor}  (tok={t})")
    sh = s.hero
    print(f"\n终态: {s.current_floor}({sh.x},{sh.y}) HP{sh.hp} ATK{sh.atk} DEF{sh.def_} "
          f"钥{keys_str(sh)} kills{sh.kill_count}")
    print(f"事件计数: KILL={n_kill}  DOOR={n_door}")


# ══════════════════════════ dump 模式 ══════════════════════════
def build_scoring():
    from extract.vzone import build_zone
    from analysis.smart_phi_s53_beam import (
        build_phi_s53, key_credit, FLY_ATTRS, BOSS_LEG_FLOORS)
    from analysis.dir2_redkey_pathloss_beam import (
        TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS, make_seg_step, replay_to_token)

    zone = build_zone()
    start = replay_to_token(TOK_SHIELD)
    phi_loss, diag = build_phi_s53(start, REAL_LEG_FLOORS, REDKEY_CELL,
                                   zone, 12000, BOSS_LEG_FLOORS)

    def score_parts(st):
        h = st.hero
        phi = phi_loss(st)
        kc = key_credit(h, 1.0)
        return dict(atk=h.atk, dv=h.def_, hp=h.hp, phi=phi, kc=kc, tail=h.hp - phi + kc)

    seg = make_seg_step(REAL_LEG_FLOORS)
    return score_parts, seg, FLY_ATTRS, diag


def candidates(S, seg, fly_attrs):
    """复现 search_quotient 主循环对单个态 S 的展开（cross_floor=True, enable_fly=True）：
    _boundary_ops 枚举算子 → _expand_op → _absorb → 候选子态。"""
    from solver.quotient import _free_cells, _boundary_ops, _expand_op, _absorb
    free = _free_cells(S)
    ops = _boundary_ops(S, free, cross_floor=True, enable_fly=True, fly_attrs=fly_attrs)
    out = []
    for op in ops:
        res = _expand_op(S, free, op, seg)
        if res is None:
            continue
        child, _mv = res
        if child.dead:
            continue
        if child.current_floor != S.current_floor and op[0] not in ("fly", "stair"):
            continue
        if getattr(child.floor, "_event_intercepting", False):
            continue
        rchild, _ = _absorb(child, seg)
        if rchild.dead:
            continue
        out.append((op, rchild))
    return out


def dump_mode(target_idxs):
    tokens = decode(ROUTE)
    print(f"解码 {ROUTE.name} → {len(tokens)} token")
    print("构建 Φ（route-aware cost-to-go·含 boss）+ score_fn 三项 …", flush=True)
    score_parts, seg, fly_attrs, diag = build_scoring()
    mon_cells = diag["mon_cells"]

    targets = sorted(set(target_idxs))
    saved = {}
    s = build_initial_state()
    for i, t in enumerate(tokens):
        if i in targets:
            saved[i] = (_copy_state(s), t)
        if i >= max(targets):
            break
        s = step(s, t)

    for idx in targets:
        S, tok = saved[idx]
        ox, oy = adj_cell(S, tok)
        cell = (S.current_floor, ox, oy)
        mon_id = mon_cells.get(cell)
        print("\n" + "=" * 92)
        print(f"决策 tok{idx}：实际走 token='{tok}' → 目标格 {S.current_floor}({ox},{oy})  "
              f"怪/门id={mon_id}")
        print(f"决策态 S：{S.current_floor}({S.hero.x},{S.hero.y}) "
              f"HP{S.hero.hp} ATK{S.hero.atk} DEF{S.hero.def_} 钥{keys_str(S.hero)}")
        in_must = cell in diag["must_cells"]
        print(f"该目标格 ∈ 必经集 M（Φ 认为必经·打它降 Φ）? {in_must}")
        print("-" * 92)

        cands = candidates(S, seg, fly_attrs)
        rows = []
        for op, rc in cands:
            p = score_parts(rc)
            actual = (op[1], op[2]) == (ox, oy) and op[0] != "fly"
            rows.append((actual, op, rc, p))
        # 字典序 (atk, def, hp−Φ+kc) 降序 = beam 偏好序（beam 会从顶部留）
        rows.sort(key=lambda r: (r[3]["atk"], r[3]["dv"], r[3]["tail"]), reverse=True)

        print(f"候选算子数={len(rows)}  排序=字典序 (atk,def,hp−Φ+kc) 降序（=beam 偏好序·顶部被留）")
        print(f"{'选':>2} {'rk':>2} {'kind':<8} {'目标格':<13} {'子态落点':<14} "
              f"{'atk':>3} {'def':>3} {'hp':>5} {'Φ':>6} {'kc':>5} {'末键(hp−Φ+kc)':>13}")
        for rank, (actual, op, rc, p) in enumerate(rows, 1):
            mark = "★" if actual else ""
            if op[0] == "fly":
                tgt = f"fly→{op[1]}"
            else:
                tgt = f"{S.current_floor}({op[1]},{op[2]})"
            pos = f"{rc.current_floor}({rc.hero.x},{rc.hero.y})"
            print(f"{mark:>2} {rank:>2} {op[0]:<8} {tgt:<13} {pos:<14} "
                  f"{p['atk']:>3} {p['dv']:>3} {p['hp']:>5} {p['phi']:>6.0f} "
                  f"{p['kc']:>5} {p['tail']:>13.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", action="store_true", help="列全程打怪/开门/换层事件清单")
    ap.add_argument("--dump", type=str, default="", help="逗号分隔的决策 token idx（触发事件的 token）")
    args = ap.parse_args()
    if args.events:
        events_mode()
    elif args.dump:
        dump_mode([int(x) for x in args.dump.split(",") if x.strip()])
    else:
        print("指定 --events 或 --dump <token,...>")


if __name__ == "__main__":
    main()
