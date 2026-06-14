"""【诊断·盾缺失根因 A/B 判别 + 三路线 h5route 导出】§S10 诊断棒。只读，不改任何产品码 / 不调参 / 不 commit。

GA 最小主循环最优个体【不拿盾】，玩家游戏知识坐实"一区内拿盾能回本、绝对该拿"=真问题。本脚本分清两根因
（指向完全不同的修法）：
  根因A=fitness错  : fitness 真给"不拿盾" > "拿盾" → 一区盾减伤价值没算进来 → GA 朝错指南针爬坡(爬坡是假的)
                     → 须回头【修 fitness】。
  根因B=搜索没探到: fitness 给"拿盾" > "不拿盾"、但 GA(pop12/gen6/变异) 没探到那个解 → 搜索力度问题
                     → 【加大 pop/gen/加交叉】能解决，fitness 不用动。
★关键判别 = fitness(②含盾) vs fitness(①不拿盾) 谁高，这一个对比就分开 A 和 B。

三条路线（都用 sim.step 真引擎重放对账 + 导 .h5route 供玩家 h5mota 网站终审）：
  ① GA 末代最优个体(剑→MT4钥→宝石·不拿盾) —— seed=20260613 run_ga.best_individual（extract/ga_loop.py __main__ 跑出）。
  ② §S9 含盾 [盾, MT4六钥, 剑]            —— detect_big_items 盾/剑 + detect_key_targets ②候选六钥。
  ③ 689 骨架(route/ 已有·完整深 route)   —— deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route。
①② 是从 build_start(MT3 噩梦后) 解算的【中途】动作串 → 导出须拼开局前缀 tokens[:OPENING_PREFIX]
（开局噩梦→MT3 入口）整条才能在网站从游戏起点回放（encode_route 模块头铁律）。

跑法：python analysis/ga_shield_diag.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from ga_loop import build_harness
from ga_decode import decode
from solver.fitness import fitness, fitness_breakdown
from export_mt10_boss_route import load_tokens
from probe_crossfloor import OPENING_PREFIX, _fidx
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META
from decode_route import parse_rle_route, decompress

W = dict(w_potion=1.5, w_key=39.0)   # 标定权重（同 tests/test_fitness）→ 分数与 fitness(689) 同尺可比

# ① GA 末代最优个体（seed=20260613 run_ga.best_individual，extract/ga_loop.py __main__ 输出·不拿盾）
GENE_NOSHIELD = [("MT5", 11, 11), ("MT4", 2, 1), ("MT4", 5, 11),
                 ("MT1", 7, 4), ("MT4", 3, 11), ("MT4", 7, 10)]
R689 = ROOT / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route"


def held(s):
    return {k: v for k, v in s.hero.keys.items() if v}


def deepest(s):
    return max(s.visited_floors, key=_fidx)


def core(s):
    """决定后续行为 + 对照表要报的关键态（floor/坐标/HP/攻防/各色钥匙）。引擎确定性 → 此元组相等即后续重放相等。"""
    h = s.hero
    return (s.current_floor, h.x, h.y, h.hp, h.atk, h.def_, tuple(sorted(held(s).items())))


def ck(label, a, b):
    ok = core(a) == core(b)
    print(f"    {'✅' if ok else '❌'} {label}: {'一致' if ok else f'不一致 {core(a)} vs {core(b)}'}")
    return ok


def main():
    print("组装电池组（build_harness）…")
    H = build_harness()
    start, zone, step = H["start"], H["zone"], H["step"]
    roster, big, zfids = H["roster_fit"], H["big"], H["zone_fids"]
    mp = H["meta"]
    sword, shield = mp["sword"], mp["shield"]
    mt4_six = sorted(c for c in H["cands"] if c[0] == "MT4")
    assert len(mt4_six) == 6, f"MT4 候选六钥异常: {mt4_six}"
    gene_sh = [shield] + mt4_six + [sword]            # §S9 含盾 = [盾]+六钥+[剑]
    print(f"  起点 {core(start)[:6]}  盾={shield} 剑={sword}")
    print(f"  ①不拿盾基因 = {GENE_NOSHIELD}")
    print(f"  ②含盾基因   = {gene_sh}")

    # ── decode 两条（专用 cache，不污染 harness）──────────────────────────────────
    cache = {}
    print("\ndecode ①不拿盾 …")
    tok_ns, fin_ns = decode(GENE_NOSHIELD, start, zone, step, cache=cache)
    print(f"  done tokens={len(tok_ns)}  终态 {core(fin_ns)[:6]} DEF={fin_ns.hero.def_}")
    print("decode ②含盾（盾≈26s + 深钥≈18s 冷算，稍等）…")
    tok_sh, fin_sh = decode(gene_sh, start, zone, step, cache=cache)
    print(f"  done tokens={len(tok_sh)}  终态 {core(fin_sh)[:6]} DEF={fin_sh.hero.def_}")

    shield_taken = fin_sh.hero.def_ > start.hero.def_
    print(f"  ②盾是否拿到（DEF {start.hero.def_}→{fin_sh.hero.def_}）= {shield_taken}")

    # ── ③ 689 完整 route 重放 ────────────────────────────────────────────────────
    o689 = json.loads(decompress(R689.read_text(encoding="utf-8").strip()))
    tok_689 = parse_rle_route(decompress(o689["route"]))
    fin_689 = replay_all(tok_689)

    # ── 前缀拼接 + 真引擎重放对账（①②）──────────────────────────────────────────
    print("\n真引擎(sim.step)重放对账：")
    prefix = load_tokens()[:OPENING_PREFIX]
    pre = replay_all(prefix)
    print(f"    前缀 tokens[:{OPENING_PREFIX}] 终态 = {core(pre)[:6]}（应 MT3 HP400）")
    ck("前缀重放起点 == build_start 起点", pre, start)

    spliced_ns = prefix + tok_ns
    spliced_sh = prefix + tok_sh
    rep_ns = replay_all(spliced_ns)
    rep_sh = replay_all(spliced_sh)
    ok_ns = ck("①整串(前缀+解算) 重放 == decode 终态", rep_ns, fin_ns)
    ok_sh = ck("②整串(前缀+解算) 重放 == decode 终态", rep_sh, fin_sh)

    # ── 导出 h5route + round-trip 自检 ───────────────────────────────────────────
    out_ns = ROOT / "route" / "diag_ga_noshield.h5route"
    out_sh = ROOT / "route" / "diag_s9_shield.h5route"
    write_h5route(out_ns, spliced_ns, DEFAULT_META)
    write_h5route(out_sh, spliced_sh, DEFAULT_META)
    print("\nh5route 导出 + 文件 round-trip 自检：")
    for path, spliced in ((out_ns, spliced_ns), (out_sh, spliced_sh)):
        back = parse_rle_route(decompress(json.loads(decompress(path.read_text(encoding="utf-8")))["route"]))
        rt = back == spliced
        print(f"    {'✅' if rt else '❌'} {path.name}  ({len(spliced)} token, 含 {OPENING_PREFIX} 前缀)")

    # ── 分项对账 ─────────────────────────────────────────────────────────────────
    bd_ns = fitness_breakdown(fin_ns, roster, big, zfids, **W)
    bd_sh = fitness_breakdown(fin_sh, roster, big, zfids, **W)
    bd_689 = fitness_breakdown(fin_689, roster, big, zfids, **W)
    f_ns = fitness(fin_ns, roster, big, zfids, **W)
    f_sh = fitness(fin_sh, roster, big, zfids, **W)
    f_689 = fitness(fin_689, roster, big, zfids, **W)

    print("\n" + "=" * 92)
    print("★ 关键判别 dump：fitness 分项并排（①不拿盾 vs ②含盾，③689 作参考）")
    print("=" * 92)
    rowlabels = [
        ("HP                  hp", "hp"),
        ("攻防压制   atk_def_suppress", "atk_def_suppress"),
        ("主干   main_equiv_hp", "main_equiv_hp"),
        ("血瓶名义回血 potion_raw", "potion_raw"),
        ("血瓶项  potion_term", "potion_term"),
        ("手里钥匙数  key_in_hand", "key_in_hand"),
        ("手里钥匙项 key_realized", "key_realized"),
        ("地上钥匙项  key_ground", "key_ground"),
        ("钥匙家底  key_term", "key_term"),
        ("总分      total", "total"),
    ]
    print(f"  {'项目':28s}{'①不拿盾':>14s}{'②含盾':>14s}{'③689':>14s}{'①−②':>12s}")
    print("  " + "-" * 90)
    for label, k in rowlabels:
        v_ns, v_sh, v_689 = bd_ns.get(k, 0), bd_sh.get(k, 0), bd_689.get(k, 0)
        d = v_ns - v_sh
        mark = "  ← ①占优" if (d > 0.5 and k not in ("hp",)) else ""
        print(f"  {label:28s}{v_ns:>14.1f}{v_sh:>14.1f}{v_689:>14.1f}{d:>+12.1f}{mark}")

    print("\n" + "=" * 92)
    print("★ A/B 判别结论")
    print("=" * 92)
    print(f"  fitness(①不拿盾) = {f_ns:.1f}")
    print(f"  fitness(②含盾)   = {f_sh:.1f}")
    print(f"  fitness(③689)    = {f_689:.1f}")
    if f_sh > f_ns:
        print(f"\n  → 根因 B（搜索没探到）：fitness(②含盾)={f_sh:.1f} > fitness(①不拿盾)={f_ns:.1f}")
        print("    fitness 指南针指向对（含盾分更高），是 GA(pop12/gen6/单点变异) 没搜到含盾解。")
        print("    修法方向：加大 pop/gen、加交叉(OX/PMX)、或初始种群注入含盾个体。【fitness 不用改】。")
    else:
        print(f"\n  → 根因 A（fitness 错）：fitness(①不拿盾)={f_ns:.1f} ≥ fitness(②含盾)={f_sh:.1f}")
        print("    一区内盾的减伤价值没被正确算进 fitness，GA 朝错指南针爬坡（+872 爬坡是假的）。")
        print("    逐项定位（①−②，>0=该项让'不拿盾'占优=嫌疑）：")
        main_d = bd_ns["main_equiv_hp"] - bd_sh["main_equiv_hp"]
        hp_d = bd_ns["hp"] - bd_sh["hp"]
        sup_d = bd_ns["atk_def_suppress"] - bd_sh["atk_def_suppress"]
        print(f"      主干 main_equiv_hp 差 = {main_d:+.1f}  (其中 HP 差 {hp_d:+.1f} / 攻防压制差 {sup_d:+.1f})")
        print("    盾的减伤本应体现在【攻防压制 suppress】：def↑ → 对一区怪损血↓ → suppress 更接近 0 → 主干↑。")
        if sup_d > 0:
            print(f"      ❗含盾的攻防压制并未更优（①比②还高 {sup_d:+.1f}）→ 盾的 def 在 roster 上压不出减伤价值。")
            print("        嫌疑：参照怪 roster 不含一区硬怪 / equiv_hp 把去深盾的 HP 损耗按全程记、减伤收益只在一区怪上（视野错配）。")
        else:
            print(f"      含盾攻防压制确实更优（②比①好 {-sup_d:+.1f}），但被去深盾的 HP 损失（{hp_d:+.1f}）淹没 → 主干仍判①赢。")
            print("        嫌疑：equiv_hp 主干把【去拿盾途中耗血】和【盾的减伤收益】放同一尺度相减，且收益只算到 roster 怪，低估一区回本。")

    # ── 三方真实局面对照（真引擎重放确认）────────────────────────────────────────
    print("\n" + "=" * 92)
    print("★ 三方真实局面对照（sim.step 真引擎重放终态）")
    print("=" * 92)
    rows = [
        ("①GA最优·不拿盾", fin_ns, len(tok_ns), len(spliced_ns), f_ns, out_ns.name, ok_ns),
        ("②§S9·含盾",      fin_sh, len(tok_sh), len(spliced_sh), f_sh, out_sh.name, ok_sh),
        ("③689骨架",       fin_689, len(tok_689), len(tok_689), f_689, R689.name, True),
    ]
    print(f"  {'路线':16s}{'终态floor(x,y)':18s}{'HP':>6s}{'ATK':>5s}{'DEF':>5s}"
          f"{'最深':>6s}{'解算tok':>8s}{'总tok':>8s}{'fitness':>11s}  重放")
    print("  " + "-" * 100)
    for name, s, ntok, ntot, f, fname, okrep in rows:
        h = s.hero
        floc = f"{s.current_floor}({h.x},{h.y})"
        print(f"  {name:16s}{floc:18s}{h.hp:>6d}{h.atk:>5d}{h.def_:>5d}"
              f"{deepest(s):>6s}{ntok:>8d}{ntot:>8d}{f:>11.1f}  {'✅' if okrep else '❌'}")
        print(f"  {'':16s}持钥={held(s)}")
    print("\n  h5route 文件：")
    print(f"    ① route/{out_ns.name}")
    print(f"    ② route/{out_sh.name}")
    print(f"    ③ route/{R689.name}")


if __name__ == "__main__":
    main()
