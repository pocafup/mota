"""【诊断·C==A 物理可疑】dump C=[盾,剑] 是否真"先盾后剑"，还是 navigate_to 顺路把剑抓了。

玩家硬逻辑：C=[盾,剑] 若真"先拿盾"，英雄要在【无剑低 ATK】下横穿一区到 MT9 拿盾，沿途打不动的怪狂
损血 → C 终态 HP 不可能与 A=[剑,盾] 相同。但冒烟报 C/A 都 HP82/ATK21/DEF20、fitness 都 −5180。
逐项查清（不下结论、先 dump 真相）：
  1. C 完整动作串走一遍：物理上【先踏剑格还是盾格】？在第几步、当时 ATK 多少？
  2. C-leg0=navigate_to(start,盾) 返 reached True/False？终态 ATK 升了吗（顺路抓剑）？
  3. 盾到底拿没拿到 → 终态 DEF 坐实（非名义）。
  4. cache=None vs 带 cache：C 终态是否逐字段一致（排缓存误命中）。

运行：python extract/ga_decode_diag.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step
from solver.beam import build_future_roster
from probe_crossfloor import build_start
from vzone import build_zone
from big_item_pull import detect_big_items
from ga_navigate import navigate_to
from ga_decode import decode


def hero_t(s):
    h = s.hero
    ks = {k: v for k, v in h.keys.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"keys={ks} gold={h.gold} dead={s.dead} won={s.won}")


def decode_legs(gene, start, zone, cache, sword, shield):
    """复刻 decode 内循环，逐 leg 打印 navigate_to 的 reached / 终态 / 本 leg 是否抓到剑盾。"""
    state = start
    tokens = []
    for i, goal in enumerate(gene):
        if state.dead or state.won:
            break
        atk0, def0 = state.hero.atk, state.hero.def_
        tag = "剑" if goal == sword else "盾" if goal == shield else str(goal)
        final, moves, reached = navigate_to(state, goal, zone, step, cache=cache)
        if reached:
            gs = " 抓到剑!" if final.hero.atk > atk0 else ""
            gd = " 抓到盾!" if final.hero.def_ > def0 else ""
            print(f"  leg{i} →{tag}{goal}: reached=True 步数={len(moves)}  终态 {hero_t(final)}")
            print(f"        本leg: ATK {atk0}->{final.hero.atk}{gs}   DEF {def0}->{final.hero.def_}{gd}")
            state = final
            tokens.extend(moves)
        else:
            print(f"  leg{i} →{tag}{goal}: reached=False ★跳过★ state不变 {hero_t(state)}")
    return tokens, state


def walk_dump(label, start, tokens, sword, shield):
    """逐 token 真走，记录【首次踏上剑格/盾格】的步号 + 前后 ATK/DEF/HP → 物理顺序真相。"""
    s = start
    first_sword = first_shield = None
    for idx, t in enumerate(tokens):
        p_atk, p_def, p_hp = s.hero.atk, s.hero.def_, s.hero.hp
        s = step(s, t)
        cell = (s.current_floor, s.hero.x, s.hero.y)
        if cell == sword and first_sword is None:
            first_sword = (idx, p_atk, s.hero.atk, p_def, s.hero.def_, p_hp, s.hero.hp)
        if cell == shield and first_shield is None:
            first_shield = (idx, p_atk, s.hero.atk, p_def, s.hero.def_, p_hp, s.hero.hp)
    print(f"\n[{label} 物理顺序] 完整 {len(tokens)} 步走一遍：")
    if first_sword:
        i, a0, a1, d0, d1, h0, h1 = first_sword
        print(f"   首踏剑格 {sword}: 第{i}步  ATK {a0}->{a1}  DEF {d0}->{d1}  HP {h0}->{h1}")
    else:
        print(f"   ★从未踏上剑格 {sword}")
    if first_shield:
        i, a0, a1, d0, d1, h0, h1 = first_shield
        print(f"   首踏盾格 {shield}: 第{i}步  ATK {a0}->{a1}  DEF {d0}->{d1}  HP {h0}->{h1}")
    else:
        print(f"   ★从未踏上盾格 {shield}")
    if first_sword and first_shield:
        who = "剑" if first_sword[0] < first_shield[0] else "盾"
        print(f"   ⇒ 物理上先到【{who}】(剑第{first_sword[0]}步 vs 盾第{first_shield[0]}步)")


def main():
    zone = build_zone()
    start, _ = build_start()
    roster = build_future_roster(start)
    big_cells, _tau, ranked = detect_big_items(zone, roster, start)
    sword = next(c for (drp, c, da, dd) in ranked if c in big_cells and da > 0)
    shield = next(c for (drp, c, da, dd) in ranked if c in big_cells and dd > 0)
    print(f"剑={sword}  盾={shield}  起点 {hero_t(start)}")

    print("\n" + "=" * 88 + "\n=== A=[剑,盾] 逐 leg (cache=None) ===")
    tA, fA = decode_legs([sword, shield], start, zone, None, sword, shield)
    walk_dump("A", start, tA, sword, shield)
    print(f"A 终态: {hero_t(fA)}")

    print("\n" + "=" * 88 + "\n=== C=[盾,剑] 逐 leg (cache=None) ===")
    tC, fC = decode_legs([shield, sword], start, zone, None, sword, shield)
    walk_dump("C", start, tC, sword, shield)
    print(f"C 终态: {hero_t(fC)}")

    print("\n" + "=" * 88 + "\n=== Q4 缓存误命中排查：C cache=None vs 带 cache ===")
    cache = {}
    tCc, fCc = decode([shield, sword], start, zone, step, cache=cache)
    key_none = (fC.current_floor, fC.hero.x, fC.hero.y, fC.hero.hp,
                fC.hero.atk, fC.hero.def_, fC.hero.gold)
    key_cache = (fCc.current_floor, fCc.hero.x, fCc.hero.y, fCc.hero.hp,
                 fCc.hero.atk, fCc.hero.def_, fCc.hero.gold)
    print(f"C cache=None 终态: {hero_t(fC)}")
    print(f"C 带 cache   终态: {hero_t(fCc)}")
    print(f"动作串等长? {len(tC)}=={len(tCc)} -> {len(tC) == len(tCc)}    "
          f"动作串逐 token 同? {tC == tCc}    终态字段同? {key_none == key_cache}")

    print("\n" + "=" * 88 + "\n=== A vs C 终态对比（HP/ATK/DEF 真相）===")
    print(f"A=[剑,盾]: {hero_t(fA)}")
    print(f"C=[盾,剑]: {hero_t(fC)}")
    same_res = (fA.hero.hp, fA.hero.atk, fA.hero.def_) == (fC.hero.hp, fC.hero.atk, fC.hero.def_)
    print(f"HP/ATK/DEF 完全相同? {same_res}   (终层 A={fA.current_floor} C={fC.current_floor})")


if __name__ == "__main__":
    main()
