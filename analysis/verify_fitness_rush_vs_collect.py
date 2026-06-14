"""【本 session 一次性验尺】fitness 在「先拿下面(B) vs MT9拿盾冲MT10(A)」上判得准不准？

只验、不改 fitness、不上规模、不跑大 GA。标尺=人类已知「先拿下面(B型)更优」(689/tok788 都是 B型)。
判读：fitness(B) > fitness(A) → 尺准；fitness(A) ≥ fitness(B) → 尺不准 + 定位哪项虚高。

A 型(冲上楼)：decode([盾])／decode([盾, MT10]) 从 build_start(MT3) 出发——拿盾(+顺路吸)、不绕路拿
  MT4 代价钥/离路血瓶 → 属性弱、地上潜力高。
B 型(先拿下面)：689/718(beam·MT0 全程回放) + tok788(玩家存档·截到首进 MT10)；另加【同起点对照】
  decode(整池) 从 build_start 出发(排除起点不一致干扰)。

权重用 GA 真实尺(make_decode_fitness_eval)：w_potion=1.5, w_key=39。
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step
from decode_route import parse_rle_route, decompress
from export_mt10_boss_route import make_initial_state
from ga_decode import decode
from solver.fitness import (
    fitness, fitness_breakdown, zone_remaining_potions, zone_ground_key_costs,
)
import ga_loop

W_POTION, W_KEY = 1.5, 39.0


def replay_player_until_floor(route_file, target_floor):
    """回放玩家存档，停在 current_floor 首次 == target_floor 的那一刻；返回 (state, action_idx)。"""
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    for i, a in enumerate(actions):
        s = step(s, a)
        if s.dead:
            return s, i
        if s.current_floor == target_floor:
            return s, i + 1
    return s, len(actions)


def visited_zone_floors(state, zone_fids):
    return [fid for fid in zone_fids if fid in state.floors]


def show(label, state, roster, big, zone_fids):
    bd = fitness_breakdown(state, roster, big, zone_fids, w_potion=W_POTION, w_key=W_KEY)
    h = state.hero
    print(f"\n── {label} ──")
    print(f"  位置 {state.current_floor}({h.x},{h.y})  HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"MDEF={h.mdef}  keys={dict(h.keys)}  dead={state.dead} won={state.won}")
    if bd.get("dead"):
        print(f"  ☠ 死亡态 total={bd['total']}")
        return bd
    print(f"  HP(主干基底)              = {bd['hp']:>10.1f}")
    print(f"  攻防压制 −Σcost           = {bd['atk_def_suppress']:>10.1f}")
    print(f"  ┗主干 equiv_hp            = {bd['main_equiv_hp']:>10.1f}")
    print(f"  血瓶 raw / 项(×{W_POTION})       = {bd['potion_raw']:>10.1f} / {bd['potion_term']:>10.1f}")
    print(f"  钥匙手里 {bd['key_in_hand']:>2}把 / 已兑现项   = {bd['key_realized']:>10.1f}")
    print(f"  钥匙地上 项 Σmax(0,wk−守血) = {bd['key_ground']:>10.1f}  (地上够得到 {len(bd['ground_keys'])} 把)")
    print(f"  钥匙家底 合计              = {bd['key_term']:>10.1f}")
    print(f"  通关 win                  = {bd['win']:>10.1f}")
    print(f"  ══ total                  = {bd['total']:>10.1f}")
    return bd


def main():
    print("组装电池组(build_harness·persistent=True 暖桶·首次深盾冷算 ~26s)…")
    H = ga_loop.build_harness(persistent=True)
    start, zone, step_fn = H["start"], H["zone"], H["step"]
    roster, big, zone_fids = H["roster_fit"], H["big"], H["zone_fids"]
    meta, dc = H["meta"], H["decode_cache"]
    sword, shield = meta["sword"], meta["shield"]

    print(f"\nzone_fids = {zone_fids}")
    print(f"big = {big}   w_potion={W_POTION} w_key={W_KEY}")
    print(f"剑格 sword={sword}   盾格 shield={shield}")
    print(f"目标池 pool({len(H['pool'])}) = {H['pool']}")

    # ── 起点诊断：build_start(MT3) vs s689(MT0全程) 各访问了哪些一区层 ──────────────
    print("\n" + "=" * 78)
    print("起点诊断(查公平性：未访问层按静态 JSON 全图算潜力 → 可能虚高)")
    print("=" * 78)
    print(f"  build_start: {start.current_floor}({start.hero.x},{start.hero.y}) "
          f"已访问一区层={visited_zone_floors(start, zone_fids)}")
    print(f"  s689       : {H['s689'].current_floor} "
          f"已访问一区层={visited_zone_floors(H['s689'], zone_fids)}")
    print(f"  s718       : {H['s718'].current_floor} "
          f"已访问一区层={visited_zone_floors(H['s718'], zone_fids)}")

    # ── B 型(先拿下面)：beam 689/718 + 玩家 tok788 ────────────────────────────────
    print("\n" + "=" * 78)
    print("B 型(先拿下面·人类标尺) —— 689 / 718(beam·MT0全程) + tok788(玩家·截首进MT10)")
    print("=" * 78)
    bd718 = show("718 (beam·耗尽)", H["s718"], roster, big, zone_fids)
    bd689 = show("689 (beam·高潜力)", H["s689"], roster, big, zone_fids)

    player = ROOT / "51_20260529133740.h5route"
    s_tok, idx = replay_player_until_floor(player, "MT10")
    print(f"\n  [玩家存档回放到首进 MT10：action_idx={idx}(≈tok788)]")
    bd_tok = show(f"tok{idx} (玩家·先拿下面)", s_tok, roster, big, zone_fids)

    # ── A 型(冲上楼)：decode([盾]) / decode([盾, MT10]) 从 build_start ────────────
    print("\n" + "=" * 78)
    print("A 型(冲上楼·猥琐解) —— decode 从 build_start(MT3)：拿盾(+顺路吸)、不绕路拿下面")
    print("=" * 78)
    tokA1, sA1 = decode([shield], start, zone, step_fn, cache=dc)
    bdA1 = show("A1 = decode([盾]) 拿盾即停", sA1, roster, big, zone_fids)

    tokA2, sA2 = decode([shield, ("MT10", 1, 11)], start, zone, step_fn, cache=dc)
    bdA2 = show("A2 = decode([盾, MT10入口]) 拿盾冲MT10", sA2, roster, big, zone_fids)

    # ── 同起点对照 B'(先拿下面)：decode(整池) 从 build_start，排除起点不一致干扰 ──────
    print("\n" + "=" * 78)
    print("同起点对照 B'(先拿下面) —— decode(整池) 从 build_start，与 A 同起点同管线")
    print("=" * 78)
    collect_chrom = [sword] + meta["gems"] + meta["keys"] + [shield]
    print(f"  collect 基因(先拿剑/宝石/钥匙·盾最后) = {collect_chrom}")
    tokB, sB = decode(collect_chrom, start, zone, step_fn, cache=dc)
    bdB = show("B' = decode(整池) 同起点先拿下面", sB, roster, big, zone_fids)

    # ── 判读 ────────────────────────────────────────────────────────────────────
    def F(bd):
        return bd["total"]

    print("\n" + "=" * 78)
    print("★ 判读：fitness(B 先拿下面) 是否 > fitness(A 冲上楼)？")
    print("=" * 78)
    print(f"  B型: 718={F(bd718):.1f}  689={F(bd689):.1f}  tok{idx}={F(bd_tok):.1f}  B'(同起点)={F(bdB):.1f}")
    print(f"  A型: A1[盾]={F(bdA1):.1f}  A2[盾,MT10]={F(bdA2):.1f}")
    print()

    pairs = [
        ("689 vs A1[盾]", bd689, bdA1),
        ("689 vs A2[盾,MT10]", bd689, bdA2),
        (f"tok{idx} vs A1[盾]", bd_tok, bdA1),
        (f"tok{idx} vs A2[盾,MT10]", bd_tok, bdA2),
        ("B'(同起点) vs A1[盾]", bdB, bdA1),
        ("B'(同起点) vs A2[盾,MT10]", bdB, bdA2),
    ]
    for name, b, a in pairs:
        d = F(b) - F(a)
        verdict = "✅ 尺准(B>A)" if d > 0 else "❌ 尺不准(A≥B)"
        print(f"  {name:28s}: Δ(B−A)={d:>+10.1f}  {verdict}")
        # 分项归因：B 赢/输在哪
        dmain = b["main_equiv_hp"] - a["main_equiv_hp"]
        dpot = b["potion_term"] - a["potion_term"]
        dkey = b["key_term"] - a["key_term"]
        print(f"      Δ主干(已兑现属性)={dmain:>+9.1f}  Δ血瓶项={dpot:>+9.1f}  Δ钥匙项={dkey:>+9.1f}")


if __name__ == "__main__":
    main()
