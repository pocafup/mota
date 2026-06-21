"""§S60 评估"去掉字典序换距离引导"——核心实测蓝门例子要什么机制才判得对（只读·零产品码改动）。

玩家判断：字典序判不了"开蓝门(6,3) vs 走两黄门到同颗 redGem(MT9 6,5)"这种【严格更优】
（两黄门省下稀缺蓝钥给 MT8(3,11)）。本探针在真实决策点 tok469（MT9(6,2) ATK22 Y2 B1）实测：
  (a) 字典序 (atk,def,hp−Φ+kc)         —— 判得对吗（应判错·选开蓝门）
  (b) 距离引导 −dist(→gem(6,5))         —— 判得对吗（怀疑也判错·蓝门路更短）
  (c) 价值=rollout 到拿 gem 后比最终态   —— 同 atk23 时 key_credit 决出"省蓝钥更优"

做法：从 S 出发分别走 BLUE 路（开 6,3 蓝门→拿 gem）与 YELLOW 路（禁开 6,3·靠黄门绕到 gem），
各 rollout 到 atk 涨（拿到 6,5 gem）的最终态·对比三机制各自把哪条排前。

只读复用 _s58 setup + quotient 内部。用法：python -u analysis/_s60_bluedoor_eval.py
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

from analysis._s58_gem27_probe import setup, decode_route               # noqa: E402
from analysis.smart_phi_s53_beam import key_credit, FLY_ATTRS           # noqa: E402
from analysis.dir2_redkey_pathloss_beam import REAL_LEG_FLOORS, make_seg_step  # noqa: E402
from analysis.extract_zone1_milestones import build_initial_state       # noqa: E402
from sim.simulator import step                                          # noqa: E402

GEM = ("MT9", 6, 5)            # MT9 redGem（这次决策要拿的那颗·atk22→23）
BLUE_DOOR = (6, 3)            # MT9 (6,3) 蓝门
AT_TOKEN = 469               # 路线在此用蓝钥开 (6,3)
ROUTE = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly.h5route"


def expand_ops(S, seg, forbid=()):
    """枚举 S 同层边界候选子态。forbid=要跳过的目标格集合（如禁开蓝门）。返回 [(op, child)]。"""
    from solver.quotient import _free_cells, _boundary_ops, _expand_op, _absorb
    free = _free_cells(S)
    ops = _boundary_ops(S, free, cross_floor=False, enable_fly=False, fly_attrs=None)
    out = []
    for op in ops:
        if op[0] == "fly":
            continue
        if (op[1], op[2]) in forbid:
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


def dist(st, target=GEM):
    if st.current_floor != target[0]:
        return 999
    return abs(st.hero.x - target[1]) + abs(st.hero.y - target[2])


def rollout_to_gem(S, seg, forbid=(), max_steps=18):
    """从 S 贪心朝 gem 走（每步选最小化 dist(→gem) 的候选），直到 atk 上升（拿到 gem）或步尽。
    返回 (final_state, path_ops, reached)。forbid 跳过指定门（如蓝门）。"""
    cur = S
    a0 = S.hero.atk
    ops = []
    for _ in range(max_steps):
        cands = expand_ops(cur, seg, forbid=forbid)
        if not cands:
            break
        # 贪心：选落点离 gem 最近的候选（同距离取先到的）
        cands.sort(key=lambda oc: dist(oc[1]))
        op, ch = cands[0]
        ops.append((op[0], op[1], op[2]))
        cur = ch
        if cur.hero.atk > a0:
            return cur, ops, True
    return cur, ops, False


def fmt(st):
    h = st.hero
    return (f"{st.current_floor}({h.x},{h.y}) ATK{h.atk} DEF{h.def_} HP{h.hp} "
            f"Y{h.keys.get('yellowKey',0)} B{h.keys.get('blueKey',0)} "
            f"kc={key_credit(h,1.0):.0f}")


def main():
    start, phi_loss, diag = setup()
    seg = make_seg_step(REAL_LEG_FLOORS)

    toks = decode_route(ROUTE)
    S = build_initial_state()
    for i in range(AT_TOKEN):
        S = step(S, toks[i])

    print("=" * 96)
    print(f"§S60 蓝门例子实测 @ tok{AT_TOKEN}")
    print(f"决策态 S：{fmt(S)}   目标 gem={GEM}（atk22→23）  蓝门={('MT9',)+BLUE_DOOR}")
    print("=" * 96)

    # ── BLUE 路：开 (6,3) 蓝门 → 拿 gem ──
    blue_final, blue_ops, blue_ok = rollout_to_gem(S, seg, forbid=(), max_steps=18)
    # ── YELLOW 路：禁开 (6,3) 蓝门 → 靠黄门绕到 gem ──
    yel_final, yel_ops, yel_ok = rollout_to_gem(S, seg, forbid={BLUE_DOOR}, max_steps=18)

    print("\n[两条路 rollout 到拿 gem 的最终态]")
    print(f"  BLUE  (允许开蓝门)：到 gem={blue_ok}  steps={len(blue_ops)}")
    print(f"        ops={blue_ops}")
    print(f"        最终态：{fmt(blue_final)}")
    print(f"  YELLOW(禁开蓝门)  ：到 gem={yel_ok}  steps={len(yel_ops)}")
    print(f"        ops={yel_ops}")
    print(f"        最终态：{fmt(yel_final)}")

    if not (blue_ok and yel_ok):
        print("\n⚠ 有一条没走到 gem（YELLOW 没绕通？）→ 需要看 ops 调试·停。")
        return

    # ── 决策点的【即时子态】（一步后）：字典序/距离怎么判 ──
    print("\n" + "=" * 96)
    print("【机制 a/b 在【即时子态】判（决策点一步后）】")
    print("=" * 96)
    # BLUE 的即时子：第一步（开蓝门）后的态；YELLOW 即时子：第一步（黄向）后的态
    blue_step1 = rollout_to_gem(S, seg, forbid=(), max_steps=1)[0]
    yel_step1 = rollout_to_gem(S, seg, forbid={BLUE_DOOR}, max_steps=1)[0]

    def lex_key(st):
        h = st.hero
        return (h.atk, h.def_, h.hp - phi_loss(st) + key_credit(h, 1.0))

    print(f"  BLUE   一步后：{fmt(blue_step1)}  字典序键={tuple(round(v) if isinstance(v,float) else v for v in lex_key(blue_step1))}  dist→gem={dist(blue_step1)}")
    print(f"  YELLOW 一步后：{fmt(yel_step1)}  字典序键={tuple(round(v) if isinstance(v,float) else v for v in lex_key(yel_step1))}  dist→gem={dist(yel_step1)}")
    a_lex = "BLUE" if lex_key(blue_step1) > lex_key(yel_step1) else "YELLOW"
    b_dist = "BLUE" if dist(blue_step1) < dist(yel_step1) else "YELLOW"
    print(f"\n  (a) 字典序选：{a_lex}   {'❌判错(选了开蓝门浪费蓝钥)' if a_lex=='BLUE' else '✅判对'}")
    print(f"  (b) 距离引导选：{b_dist}（−dist→gem 大者）  {'❌判错(蓝门路更短·更近 gem)' if b_dist=='BLUE' else '✅判对'}")

    # ── 机制 c：rollout 到完成后比最终态（同 atk 时 key_credit 决） ──
    print("\n" + "=" * 96)
    print("【机制 c 在【完成态】判（rollout 到都拿了 gem·同 atk23）】")
    print("=" * 96)
    bk, yk = lex_key(blue_final), lex_key(yel_final)
    print(f"  BLUE   最终：atk{blue_final.hero.atk} B{blue_final.hero.keys.get('blueKey',0)} "
          f"kc={key_credit(blue_final.hero,1.0):.0f}  字典序键={tuple(round(v) if isinstance(v,float) else v for v in bk)}")
    print(f"  YELLOW 最终：atk{yel_final.hero.atk} B{yel_final.hero.keys.get('blueKey',0)} "
          f"kc={key_credit(yel_final.hero,1.0):.0f}  字典序键={tuple(round(v) if isinstance(v,float) else v for v in yk)}")
    c_val = "YELLOW" if yk > bk else "BLUE"
    print(f"\n  (c) 完成态比较选：{c_val}  "
          f"{'✅判对(同 atk23·YELLOW 留住蓝钥 kc 高)' if c_val=='YELLOW' else '❌'}")
    print(f"      key_credit 差（YELLOW−BLUE）= {key_credit(yel_final.hero,1.0)-key_credit(blue_final.hero,1.0):.0f}"
          f"（>0=省蓝钥的资源价值·这就是判'两黄更优'的依据）")

    print("\n" + "=" * 96)
    print("结论：判'两黄门省蓝钥更优'的关键 = 在【同 atk 完成态】比 key_credit（资源价值·已在末键里）。")
    print("字典序/距离都在【即时子态】判（BLUE 先到 gem→先 atk23/更近）→ 都判错。")
    print("=" * 96)


if __name__ == "__main__":
    main()
