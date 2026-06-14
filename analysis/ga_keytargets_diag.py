"""【诊断·验证门】detect_key_targets 三分对账 + 手搓 689 式 chromosome 跑 decode（§S9 验证门）。
只读、不改任何产品码。dump：
  ① detect_key_targets 三分（候选②/顺路①/够不到③）+ 与 probe_key_targets 探针对账（同结果）。
  ② detect_big_items 大件（剑/盾 cell）+ 点明「现状目标池无钥匙→689 式路线表达不出」。
  ③ 手搓 chromosome=[盾, MT4 六钥, 门后目标] 跑 decode：逐 goal navigate_to 结果 + 重放逐步 DEF/keys
     跳变（证物理先盾后钥匙、≥3 钥匙取到、开后门花钥匙、引擎可重放）。
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start
from vzone import build_zone
from key_targets import detect_key_targets
from big_item_pull import detect_big_items
from ga_navigate import navigate_to
from solver.beam import build_future_roster
from solver.fitness import build_zone1_roster
from sim.simulator import step


def keys_total(s):
    return sum(v for v in s.hero.keys.values() if isinstance(v, (int, float)))


def by_floor(cells):
    return dict(sorted(Counter(f for f, _, _ in cells).items()))


def decode_trace(chromosome, start, zone, step_fn):
    """复刻 decode 逻辑（不改 decode）+ 逐 goal 记录 reached/位置/家底，供 dump。"""
    state = start
    tokens = []
    seg = []
    for goal in chromosome:
        if state.dead or state.won:
            seg.append((goal, "STOP(dead/won)", 0, state.hero.def_, keys_total(state)))
            break
        final, moves, reached = navigate_to(state, goal, zone, step_fn)
        if reached:
            state = final
            tokens.extend(moves)
        seg.append((goal, reached, len(moves), state.hero.def_, keys_total(state),
                    state.current_floor, (state.hero.x, state.hero.y)))
    return tokens, state, seg


def replay_trace(start, tokens, shield_cell, key_cells):
    """重放 tokens（引擎可重放性自检）+ 记 DEF/keys 跳变事件 + 踏上盾cell/各钥匙cell 的 step。"""
    s = start
    events = []
    shield_step = None
    key_steps = {}
    pd, pk = s.hero.def_, keys_total(s)
    for i, tok in enumerate(tokens):
        s = step(s, tok)
        cur = (s.current_floor, s.hero.x, s.hero.y)
        d, k = s.hero.def_, keys_total(s)
        if d != pd:
            events.append((i, f"DEF {pd}->{d}", cur))
        if k != pk:
            events.append((i, f"KEYS {pk}->{k}" + ("  ★开门花钥匙" if k < pk else "  ★拾钥匙"), cur))
        if cur == shield_cell and shield_step is None:
            shield_step = i
        if cur in key_cells and cur not in key_steps:
            key_steps[cur] = i
        pd, pk = d, k
        if s.dead:
            events.append((i, "DEAD", cur))
            break
    return s, events, shield_step, key_steps


def main():
    start, _ = build_start()
    zone = build_zone()
    roster = build_future_roster(start)              # detect_big_items 用（含 idx_of）
    _, zone_fids, _all = build_zone1_roster(start)   # detect_key_targets 用
    h = start.hero
    print(f"起点 {start.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"keys={dict(h.keys)}  zone_fids={zone_fids}")

    # ── ① detect_key_targets 三分 ──────────────────────────────────────────────
    cands, info = detect_key_targets(start, zone_fids)
    cheap, unreach, allk = info["cheap"], info["unreachable"], info["all_keys"]
    print("\n" + "=" * 74)
    print("① detect_key_targets 三分口径")
    print("=" * 74)
    print(f"  afford 闭包（真能开的门色）= {sorted(info['afford'])}")
    print(f"  全集 {len(allk)} | ①顺路 {len(cheap)} | ②候选 {len(cands)} | ③够不到 {len(unreach)}")
    print(f"  ②候选 by floor: {by_floor(cands)}")
    print(f"  ②候选明细: {sorted(cands)}")
    mt4 = sorted(c for c in cands if c[0] == "MT4")
    mt2 = sorted(c for c in allk if c[0] == "MT2")
    print(f"  ★MT4 六钥（应全在②候选）{len(mt4)}/6: {mt4}")
    print(f"     色: {[(c, info['colors'][c]) for c in mt4]}")
    print(f"  ★MT2 三钥（应全在③够不到）: {[(c, c in unreach) for c in mt2]}")
    print(f"  ★顺路12（应全不在②候选）: 顺路∩候选={sorted(cheap & cands)} (空=对)")
    print(f"  自检 三分无交叠且并==全集: "
          f"{len(cheap | cands | unreach) == len(allk) and not (cheap & cands) and not (cands & unreach) and not (cheap & unreach)}")

    # 与探针对账（同结果）
    try:
        from probe_key_targets import triage, all_key_cells, FULL
        p_afford, p1, p2, p3 = triage(start, zone_fids, all_key_cells(start, zone_fids, FULL))
        print(f"\n  ▸ 对账 probe_key_targets.triage: "
              f"候选 {'一致' if p2 == cands else f'不一致! probe={len(p2)}'} | "
              f"顺路 {'一致' if p1 == cheap else '不一致!'} | "
              f"够不到 {'一致' if p3 == unreach else '不一致!'} | "
              f"afford {'一致' if set(p_afford) == info['afford'] else '不一致!'}")
    except Exception as e:
        print(f"\n  ▸ 对账探针跳过：{e}")

    # ── ② detect_big_items 大件 ────────────────────────────────────────────────
    big_cells, tau, ranked = detect_big_items(zone, roster, start)
    shield = next((c for (drp, c, da, dd) in ranked if c in big_cells and dd > 0), None)
    sword = next((c for (drp, c, da, dd) in ranked if c in big_cells and da > 0), None)
    print("\n" + "=" * 74)
    print("② detect_big_items 大件（现状 GA 目标池）")
    print("=" * 74)
    print(f"  big_cells = {sorted(big_cells)}  tau={tau:.1f}")
    print(f"  盾(dd>0) = {shield} | 剑(da>0) = {sword}")
    big_keys = [c for c in big_cells if c[0] == 'MT4']
    print(f"  ★现状目标池里 MT4 钥匙数 = {len([1 for (drp,c,da,dd) in ranked if c[0]=='MT4'])}（detect_big_items 只产攻防大件/宝石，钥匙根本不在池）")
    print(f"  ★detect_key_targets 补上 MT4 钥匙 {len(mt4)} 把 → 689 式『先盾→回头取 MT4 钥匙』才表达得出")

    # ── ③ 验证门 chromosome ────────────────────────────────────────────────────
    door_goal = sword   # 门后目标：先用剑（深处大件，去它会用到钥匙开门）
    chromosome = [shield] + mt4 + [door_goal]
    print("\n" + "=" * 74)
    print("③ 验证门 chromosome = [盾] + MT4六钥 + [门后目标(剑)]")
    print("=" * 74)
    print(f"  chromosome = {chromosome}")
    tokens, final, seg = decode_trace(chromosome, start, zone, step)
    print(f"\n  逐 goal 解码:")
    for row in seg:
        print(f"    {row}")
    fh = final.hero
    print(f"\n  decode 终态: {final.current_floor}({fh.x},{fh.y}) HP={fh.hp} ATK={fh.atk} "
          f"DEF={fh.def_} keys={dict(fh.keys)}  tokens={len(tokens)}")
    print(f"  钥匙净增（终 - 起）= {keys_total(final) - keys_total(start)}")

    s2, events, shield_step, key_steps = replay_trace(start, tokens, shield, set(mt4))
    print(f"\n  ▸ 引擎可重放自检: 重放终态 == decode 终态? "
          f"{(s2.current_floor, s2.hero.x, s2.hero.y, s2.hero.hp, s2.hero.def_) == (final.current_floor, fh.x, fh.y, fh.hp, fh.def_)}")
    print(f"  ▸ 踏上盾 cell {shield} 的 step = {shield_step}")
    print(f"  ▸ 踏上 MT4 钥匙 cell 的 step = {dict(sorted(key_steps.items(), key=lambda kv: kv[1]))}")
    first_key_step = min(key_steps.values()) if key_steps else None
    print(f"  ▸ 物理先盾后钥匙? 盾 step({shield_step}) < 首钥匙 step({first_key_step}) = "
          f"{shield_step is not None and first_key_step is not None and shield_step < first_key_step}")
    print(f"\n  DEF/keys 跳变事件（{len(events)} 条）:")
    for ev in events:
        print(f"    step {ev[0]:4d}  {ev[1]:24s}  @ {ev[2]}")


if __name__ == "__main__":
    main()
