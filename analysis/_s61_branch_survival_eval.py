"""§S61 评估"怎么让暂时 atk 低但最终更优的中间态不被 atk 主键提前剪"（只读·零产品码改动）。

接 §S60 钉死的病：失败不是评分少项（key_credit 本就对），是 atk 主键提前剪中间态（分支存活/
lookahead 病）。本探针在【两个】真实决策点上用代码实测三条候选解法各自的判决，给玩家拍：

  决策点 P1=蓝门 tok469（MT9 6,2 atk22）——【主键剪】：BLUE 一步开蓝门即 atk23、YELLOW 走两黄门
     还 atk22，主键当场分胜负、末键（YELLOW 其实赢）轮不到说话。正确答案=YELLOW（省蓝钥+60）。
  决策点 P2=绕路/囤血 tok773（MT8 1,2 atk25）——【末键剪】：候选全 atk25（凹陷期 10 步长），
     gem 方向子态末键 hp−Φ+kc 输给囤血子态。正确答案两面：gem 方向该活（破红钥），且 X(没拿)
     不该压过 Y(拿了)（§S54 囤血/拖延病）。

三条解法（都只在探针里模拟·不碰生产 score_fn）：
  ① 硬主键（现状字典序）：key=(atk, def, tail)
  ② 容忍一档 τ=1（放松主键）：|Δatk|≤τ 归同档→比 tail，否则比 atk
  ③ lookahead L 步（潜在 atk 当主键）：key=(potential_atk(st,L), def, tail)
     potential_atk = 从 st 乐观贪心朝 gem 走 L 步内可达的最大 atk。

判据：每条解法 (能否救 P1 的 YELLOW 中间态) × (会否在 P2 复活囤血 X>Y) × (lookahead 的 L 步数耦合)。
用法：python -u analysis/_s61_branch_survival_eval.py
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

from analysis._s58_gem27_probe import setup, free_reach_step_toward, decode_route  # noqa: E402
from analysis._s60_bluedoor_eval import expand_ops, rollout_to_gem                 # noqa: E402
from analysis.smart_phi_s53_beam import key_credit, FLY_ATTRS                      # noqa: E402
from analysis.dir2_redkey_pathloss_beam import REAL_LEG_FLOORS, make_seg_step      # noqa: E402
from analysis.extract_zone1_milestones import build_initial_state                  # noqa: E402
from sim.simulator import step                                                     # noqa: E402

ROUTE = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly.h5route"
GEM_BLUE = ("MT9", 6, 5)      # P1 蓝门要拿的 gem（atk22→23）
BLUE_DOOR = (6, 3)           # P1 (6,3) 蓝门
TOK_BLUE = 469
GEM_DETOUR = ("MT8", 4, 10)  # P2 第5颗 gem（atk25→26·破红钥）
TOK_DETOUR = 773


def replay_to(at_token):
    toks = decode_route(ROUTE)
    S = build_initial_state()
    for i in range(at_token):
        S = step(S, toks[i])
    return S


def dist_to(st, target):
    if st.current_floor != target[0]:
        return 999
    return abs(st.hero.x - target[1]) + abs(st.hero.y - target[2])


def potential_atk(S, seg, target, forbid, L):
    """乐观 lookahead：从 S 贪心朝 target 走【最多 L 步】，返回这 L 步内可达的最大 atk。
    L 步内摸到 gem → atk+1；摸不到 → 原 atk。模拟"按最终 atk 排"的浅 lookahead。"""
    cur = S
    a0 = S.hero.atk
    best = a0
    for _ in range(L):
        cands = expand_ops(cur, seg, forbid=forbid)
        if not cands:
            break
        cands.sort(key=lambda oc: dist_to(oc[1], target))
        _op, ch = cands[0]
        cur = ch
        best = max(best, cur.hero.atk)
        if cur.hero.atk > a0:
            break
    return best


def steps_to_gem(S, seg, target, forbid, cap=20):
    """贪心朝 target 走，返回拿到 gem（atk 升）需要的算子步数（cap 内没拿到返 None）。"""
    cur = S
    a0 = S.hero.atk
    for n in range(1, cap + 1):
        cands = expand_ops(cur, seg, forbid=forbid)
        if not cands:
            return None
        cands.sort(key=lambda oc: dist_to(oc[1], target))
        _op, ch = cands[0]
        cur = ch
        if cur.hero.atk > a0:
            return n
    return None


def fmt(st):
    h = st.hero
    return (f"{st.current_floor}({h.x},{h.y}) ATK{h.atk} DEF{h.def_} HP{h.hp} "
            f"Y{h.keys.get('yellowKey',0)} B{h.keys.get('blueKey',0)} "
            f"kc={key_credit(h,1.0):.0f}")


def main():
    start, phi_loss, diag = setup()
    seg = make_seg_step(REAL_LEG_FLOORS)

    def lex(st):
        h = st.hero
        return (h.atk, h.def_, h.hp - phi_loss(st) + key_credit(h, 1.0))

    def tail(st):
        return lex(st)[2]

    # ───────────────────────── 决策点 P1：蓝门 tok469（主键剪）─────────────────────────
    Sb = replay_to(TOK_BLUE)
    blue1 = rollout_to_gem(Sb, seg, forbid=(), max_steps=1)[0]            # 即时子：开蓝门(atk23)
    yel1 = rollout_to_gem(Sb, seg, forbid={BLUE_DOOR}, max_steps=1)[0]    # 即时子：走黄门(atk22)
    blueF = rollout_to_gem(Sb, seg, forbid=(), max_steps=18)[0]           # 完成态
    yelF = rollout_to_gem(Sb, seg, forbid={BLUE_DOOR}, max_steps=18)[0]

    print("=" * 98)
    print(f"决策点 P1 = 蓝门 tok{TOK_BLUE}（【主键剪】）   S：{fmt(Sb)}   gem={GEM_BLUE}")
    print("=" * 98)
    print(f"  BLUE  即时子（开蓝门1步）：{fmt(blue1)}  lex={_rk(lex(blue1))}")
    print(f"  YELLOW即时子（走黄门1步）：{fmt(yel1)}  lex={_rk(lex(yel1))}")
    print(f"  正确答案=YELLOW（完成态都 atk23·YELLOW 留蓝钥 kc"
          f"{key_credit(yelF.hero,1.0):.0f}>{key_credit(blueF.hero,1.0):.0f}·省"
          f"{key_credit(yelF.hero,1.0)-key_credit(blueF.hero,1.0):.0f}）")
    # lookahead 潜在 atk（YELLOW 即时子距 gem 几步）
    yel_steps = steps_to_gem(yel1, seg, GEM_BLUE, forbid={BLUE_DOOR})
    print(f"\n  YELLOW 即时子→gem 还需 {yel_steps} 步 | potential_atk: "
          f"L=1→{potential_atk(yel1,seg,GEM_BLUE,{BLUE_DOOR},1)}  "
          f"L=2→{potential_atk(yel1,seg,GEM_BLUE,{BLUE_DOOR},2)}")

    print("\n  三解法判决（P1·正确=YELLOW）：")
    _verdict_pair(("BLUE", blue1), ("YELLOW", yel1), lex, tail,
                  seg, GEM_BLUE, forbid_b={BLUE_DOOR}, correct="YELLOW")

    # ───────────────────────── 决策点 P2：绕路/囤血 tok773（末键剪）────────────────────
    Sx = replay_to(TOK_DETOUR)   # X = 囤血/绕路起点 atk25（没拿 gem）
    # Y = 沿 gem 方向走到真拿到 gem（atk26）
    walk = Sx
    Y = None
    for _ in range(20):
        nxt = free_reach_step_toward(walk, seg, GEM_DETOUR, FLY_ATTRS)
        if nxt is None:
            break
        walk = nxt[1]
        if walk.hero.atk > Sx.hero.atk:
            Y = walk
            break

    print("\n" + "=" * 98)
    print(f"决策点 P2 = 绕路/囤血 tok{TOK_DETOUR}（【末键剪】）   X(没拿)：{fmt(Sx)}   gem={GEM_DETOUR}")
    print("=" * 98)
    x_steps = steps_to_gem(Sx, seg, GEM_DETOUR, forbid=())
    print(f"  X(囤血/绕路起点)：{fmt(Sx)}  lex={_rk(lex(Sx))}   X→gem 还需 {x_steps} 步")
    if Y is not None:
        print(f"  Y(刚拿gem)      ：{fmt(Y)}  lex={_rk(lex(Y))}")
    print(f"  正确答案：Y 该 > X（拿 gem 优于囤血·§S54 病=别让没拿的 X 压过拿了的 Y）")
    print(f"  X potential_atk 随 L（X 离 gem {x_steps} 步·跨过即乐观升档=复活囤血临界）：")
    for L in (2, 5, 10, 11, 12, 15):
        pa = potential_atk(Sx, seg, GEM_DETOUR, (), L)
        flag = "  ← 升档(复活囤血)" if pa > Sx.hero.atk else ""
        print(f"      L={L:>2} → potential_atk={pa}{flag}")

    if Y is not None:
        print("\n  三解法判决（P2·正确=Y·X 赢即【复活囤血】）：")
        _verdict_pair(("X没拿", Sx), ("Y拿了", Y), lex, tail,
                      seg, GEM_DETOUR, forbid_b=(), correct="Y拿了",
                      label_a="X没拿", label_b="Y拿了", win_bad="X没拿",
                      look_Ls=(2, 10, 12, 15))

    # ───────────────────────── 汇总 ─────────────────────────
    print("\n" + "=" * 98)
    print("汇总（每条解法：P1 救 YELLOW 中间态? × P2 会否复活囤血(X>Y)? × lookahead 步数耦合）")
    print("=" * 98)
    print("  详见上面两决策点的逐条判决。lookahead 关键：")
    print(f"    · P1 蓝门 YELLOW 离 gem {yel_steps} 步（浅）→ L=2 即救")
    print(f"    · P2 绕路/囤血 X 离 gem {x_steps} 步（深）→ L<{x_steps} 救不了绕路(破不了红钥)、"
          f"L≥{x_steps} 才救绕路但同时把囤血 X 乐观升档=复活")
    print("    · 囤血 X 与绕路 gem 起点是【同一个态】→ lookahead 的 L 无法同时(救深绕路)+(不复活囤血)")


def _rk(t):
    return tuple(round(v) if isinstance(v, float) else v for v in t)


def _verdict_pair(a, b, lex, tail, seg, gem, forbid_b, correct,
                  label_a=None, label_b=None, win_bad=None, look_Ls=(2, 10)):
    """a,b=(name,state)。打印硬主键/容忍一档τ=1/lookahead(L=2,L=10) 各自选谁 + 对错。
    forbid_b：b 这条路 rollout 时要禁的门（P1 的 YELLOW 禁蓝门）。"""
    na, sa = a
    nb, sb = b
    la, lb = lex(sa), lex(sb)

    # ① 硬主键（现状字典序）
    w_hard = na if la > lb else nb
    # ② 容忍一档 τ=1
    if abs(sa.hero.atk - sb.hero.atk) <= 1:
        w_soft = na if tail(sa) > tail(sb) else nb        # 同档比 tail
    else:
        w_soft = na if sa.hero.atk > sb.hero.atk else nb  # 跨档比 atk

    def look_winner(L):
        forb_a = () if win_bad is None else ()      # a(BLUE/X) 不禁门
        pa = potential_atk(sa, seg, gem, forb_a, L)
        pb = potential_atk(sb, seg, gem, forbid_b, L)
        if pa != pb:
            return na if pa > pb else nb
        return na if tail(sa) > tail(sb) else nb    # 潜在 atk 平→比 tail

    def mark(w):
        return "✅" if w == correct else "❌"

    print(f"    ① 硬主键(现状)   选 {w_hard:<7}{mark(w_hard)}")
    print(f"    ② 容忍一档τ=1    选 {w_soft:<7}{mark(w_soft)}"
          + ("   ← 同档比 tail" if abs(sa.hero.atk-sb.hero.atk) <= 1 else "   ← 跨档比 atk"))
    for L in look_Ls:
        wl = look_winner(L)
        print(f"    ③ lookahead L={L:<2}  选 {wl:<7}{mark(wl)}")


if __name__ == "__main__":
    main()
