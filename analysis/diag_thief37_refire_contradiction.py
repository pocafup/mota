"""诊断"sim 在玩家 route 上比网站少停一步、46 检查点却全绿"的矛盾。

并排跑两套模型，逐 token 比位置与属性：
  A = 当前 sim（u#75 再踩 (3,7) re-fire → 把 (1,9) 小偷清掉 → 不停步）
  B = 网站忠实模型（u#70 第一次触发后，给 MT2 "3,7" 登记 _suppressed_events，
      复刻网站"hide 移除触发块、再踏不触发"→ (1,9) 小偷留着 → 下行撞上停一步）
  注：B 是【拟议修法的等效仿真】，不改产品码（只在重放中给该格登记抑制）。

输出三件事：
  1. u#66~92 位置表：A/B 每步落点是否一致、谁在哪步原地（吸收那一步）；
  2. 重收敛点：A、B 位置从哪一步起重新一致并保持；
  3. 17 个检查点(token_idx)：A、B 的 floor/HP/ATK/DEF/yk/bk 是否都等于金标准
     —— 若 B 也全部命中金标准，则拟议修法不破坏任何检查点。

跑法：python extract/diag_thief37_refire_contradiction.py
"""
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import sim.simulator as S
from extract.export_mt10_boss_route import make_initial_state, load_tokens

# 从测试文件直接取金标准，避免重复定义漂移
spec = importlib.util.spec_from_file_location("tc", ROOT / "tests" / "test_checkpoints.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)
GROUND_TRUTH = tc.GROUND_TRUTH
MAX_TOKEN = max(t for t, *_ in GROUND_TRUTH)

SUPPRESS_AFTER = 70   # B 模型：步进完 u#70 后给 (3,7) 登记抑制


def snap(s):
    return (s.current_floor, s.hero.x, s.hero.y)


def attrs(s):
    return (s.current_floor, s.hero.hp, s.hero.atk, s.hero.def_,
            s.hero.keys.get("yellowKey", 0), s.hero.keys.get("blueKey", 0))


def main():
    units = load_tokens()
    A = make_initial_state()
    B = make_initial_state()

    ck = {t: None for t, *_ in GROUND_TRUTH}      # token_idx -> (attrsA, attrsB)
    pos_rows = []
    reconverge = None
    diverged = False

    for ui in range(min(len(units), MAX_TOKEN) + 1):
        u = units[ui]
        a0, b0 = snap(A), snap(B)
        A = S.step(A, u)
        B = S.step(B, u)
        if ui == SUPPRESS_AFTER:
            B.floors["MT2"]._suppressed_events.add("3,7")
        a1, b1 = snap(A), snap(B)

        if 66 <= ui <= 92:
            pos_rows.append((ui, u, a0, a1, b0, b1))
        if a1 != b1:
            diverged = True
            reconverge = None
        elif diverged and reconverge is None:
            reconverge = ui
        if ui in ck:
            ck[ui] = (attrs(A), attrs(B))

    # ── 1. 位置表 ──────────────────────────────────────────────────────────────
    print("u#   单步  A当前sim 前→后            B网站模型 前→后            一致  备注")
    print("-" * 92)
    for (ui, u, a0, a1, b0, b1) in pos_rows:
        same = "✓" if a1 == b1 else "✗"
        note = ""
        if a0 == a1 and b0 != b1:
            note = "A原地(吸收)"
        elif b0 == b1 and a0 != a1:
            note = "B原地(撞(1,9)小偷停步)"
        elif a0 == a1 and b0 == b1:
            note = "都原地"
        print(f"{ui:>3}  {u:>4}  {str(a0):>16}→{str(a1):<16}{str(b0):>16}→{str(b1):<16}  {same}   {note}")

    print(f"\n重收敛：A、B 位置从 u#{reconverge} 起重新一致并保持到 u#{MAX_TOKEN}"
          if reconverge is not None else "\n⚠ 到 MAX_TOKEN 仍未重收敛")

    # ── 2. 检查点核对 ───────────────────────────────────────────────────────────
    print("\n17 检查点核对（A=当前sim / B=网站模型；都须等于金标准）")
    print("tok   金标准(floor,hp,atk,def,yk,bk)            A命中  B命中")
    print("-" * 78)
    allA = allB = True
    for row in GROUND_TRUTH:
        tok, ef, ehp, eatk, edef, eyk, ebk = row
        aA, aB = ck[tok]
        def hit(a):
            f, hp, atk, df, yk, bk = a
            ok = (f == ef and hp == ehp and atk == eatk and df == edef
                  and (eyk is None or yk == eyk) and (ebk is None or bk == ebk))
            return ok
        hA, hB = hit(aA), hit(aB)
        allA &= hA
        allB &= hB
        gt = f"({ef},{ehp},{eatk},{edef},{eyk},{ebk})"
        print(f"{tok:>4}  {gt:<40}  {'✓' if hA else '✗ '+str(aA)}   {'✓' if hB else '✗ '+str(aB)}")

    print(f"\nA(当前sim) 全检查点命中金标准: {'✅' if allA else '❌'}")
    print(f"B(网站模型) 全检查点命中金标准: {'✅' if allB else '❌'}"
          f"   → {'拟议修法不破坏任何检查点' if allB else '拟议修法会破坏检查点，需复查'}")


if __name__ == "__main__":
    main()
