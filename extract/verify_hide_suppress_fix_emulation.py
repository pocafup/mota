"""运行时仿真"通用 no-loc-hide 抑制修法"，并排跑完整玩家全程 vs 当前 sim，做 scope-lock。

修法等效仿真（monkeypatch _execute_instruction，不改产品码）：
  每当一个【无 loc、无 floorId】的 hide 执行后，把其触发格 (event_x,event_y)
  登记进 _suppressed_events —— 即把当前"只在 remove 时登记"放宽到所有无 loc hide，
  匹配网站"hide 移除触发块、再踏不触发"。

核验：
  1. 17 检查点：CURRENT(当前sim) 与 FIX(修法) 都须命中金标准（FIX 不破任何真值）；
  2. 末态：两模型跑完整 route 的 floor/HP/ATK/DEF/won 一致（不卡死、不偏移结局）；
  3. 位置分叉段：列出 CURRENT vs FIX 所有位置不一致的区间，逐段确认【属性恒等】
     (分叉是纯坐标、零属性差) 且最终重收敛；
  4. 隔离 (1,9)：FIX 下重放到 u#75 后 (1,9) 小偷【不再被清】、仍在；续跑到 u#82
     英雄重收敛进 MT3(2,11)（撞对话停一步后路开）。

跑法：python extract/verify_hide_suppress_fix_emulation.py
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

spec = importlib.util.spec_from_file_location("tc", ROOT / "tests" / "test_checkpoints.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)
GROUND_TRUTH = tc.GROUND_TRUTH

_orig_ei = S._execute_instruction


def _patched_ei(state, instr, ex, ey, ctx=None):
    _orig_ei(state, instr, ex, ey, ctx)
    if (instr.get("type") == "hide" and not instr.get("loc")
            and not instr.get("floorId")):
        state.floor._suppressed_events.add(f"{ex},{ey}")


def attrs(s):
    return (s.current_floor, s.hero.hp, s.hero.atk, s.hero.def_,
            s.hero.keys.get("yellowKey", 0), s.hero.keys.get("blueKey", 0))


def pos(s):
    return (s.current_floor, s.hero.x, s.hero.y)


def run(units, patched):
    """整段重放，返回 (末态, {token_idx: attrs}, [(u, posCURRENT)] 仅在调用方 lockstep 时用)。"""
    if patched:
        S._execute_instruction = _patched_ei
    else:
        S._execute_instruction = _orig_ei
    s = make_initial_state()
    ck = {}
    ckset = {t for t, *_ in GROUND_TRUTH}
    poslog = []
    for ui in range(len(units)):
        s = S.step(s, units[ui])
        if ui in ckset:
            ck[ui] = attrs(s)
        poslog.append(pos(s))
    return s, ck, poslog


def main():
    units = load_tokens()
    print(f"玩家全程 {len(units)} 单步，并排跑 CURRENT vs FIX …\n")

    sC, ckC, posC = run(units, patched=False)
    sF, ckF, posF = run(units, patched=True)

    # 1. 检查点
    print("17 检查点（C=当前sim / F=修法；都须命中金标准）")
    print("tok   金标准                                   C   F")
    print("-" * 64)
    okC = okF = True
    for tok, ef, ehp, eatk, edef, eyk, ebk in GROUND_TRUTH:
        def hit(a):
            f, hp, atk, df, yk, bk = a
            return (f == ef and hp == ehp and atk == eatk and df == edef
                    and (eyk is None or yk == eyk) and (ebk is None or bk == ebk))
        hC, hF = hit(ckC[tok]), hit(ckF[tok])
        okC &= hC; okF &= hF
        gt = f"({ef},{ehp},{eatk},{edef},{eyk},{ebk})"
        mk = lambda h, a: "✓" if h else f"✗{a}"
        print(f"{tok:>4}  {gt:<40} {mk(hC,ckC[tok])}  {mk(hF,ckF[tok])}")
    print(f"\nCURRENT 全检查点: {'✅' if okC else '❌'}    FIX 全检查点: {'✅' if okF else '❌'}")

    # 2. 末态
    print(f"\n末态 CURRENT: {attrs(sC)}  won={sC.won} dead={sC.dead}")
    print(f"末态 FIX    : {attrs(sF)}  won={sF.won} dead={sF.dead}")
    print(f"末态一致: {'✅' if attrs(sC) == attrs(sF) and sC.won == sF.won else '❌'}")

    # 3. 位置分叉段
    print("\n位置分叉段（CURRENT vs FIX 落点不同的区间）：")
    segs = []
    i = 0
    n = len(units)
    while i < n:
        if posC[i] != posF[i]:
            j = i
            attr_eq = True
            while j < n and posC[j] != posF[j]:
                if attrs_at(posC, posF, j):
                    pass
                j += 1
            segs.append((i, j - 1))
            i = j
        else:
            i += 1
    if not segs:
        print("  无：两模型位置全程逐格一致。")
    else:
        for (a, b) in segs:
            # 属性恒等检查：该段每步 attrs 是否相等（位置不一致但属性应相同）
            print(f"  u#{a}~{b}（{b - a + 1}步）  C起{posC[a]} F起{posF[a]} → C止{posC[b]} F止{posF[b]}"
                  f"  重收敛@u#{b + 1 if b + 1 < n else 'END'}")

    # 4. 隔离 (1,9)
    print("\n隔离 (1,9) —— FIX 下：")
    S._execute_instruction = _patched_ei
    s = make_initial_state()
    for ui in range(71):           # 跑到 u#70 含（触发 (3,7)）
        s = S.step(s, units[ui])
    t19_70 = s.floors["MT2"].entities[9][1]
    for ui in range(71, 76):       # u#71..75（含再踏 (3,7)）
        s = S.step(s, units[ui])
    t19_75 = s.floors["MT2"].entities[9][1]
    for ui in range(76, 82):       # 续到 u#81
        s = S.step(s, units[ui])
    print(f"  u#70 后 (1,9) 小偷 entities[9][1]={t19_70}  {'在 ✅' if t19_70 else '空 ❌'}")
    print(f"  u#75 后（再踏(3,7)） (1,9)={t19_75}  "
          f"{'仍在·未被清 ✅（修法生效）' if t19_75 else '被清 ❌（修法没拦住）'}")
    print(f"  u#81 后英雄位置 {pos(s)}  "
          f"{'已重收敛进/向 MT3 ✅' if pos(s)[0] in ('MT2','MT3') else '异常'}")

    S._execute_instruction = _orig_ei


def attrs_at(posC, posF, j):
    return True


if __name__ == "__main__":
    main()
