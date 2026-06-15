"""【只导出 GA 最优解 route · 不改产品码 · 不 commit】
复刻 run_ga_zone1_scaleup.py 的【完全相同】GA 跑(pop15/gen10/seed20260614/交叉0.3/注入[盾]·禁区开)，
取末代最优基因 → _decode_with_order(禁区开·与 eval 同口径)出 tokens+终态 → 拼 83 步开局前缀 →
封板 sim replay 预检【replay 终态 == decode 终态】才写盘。供玩家拖进 h5mota 网站看游戏引擎实地回放。

红线：只读复用 build_harness/run_ga/_decode_with_order/navigate_to/fitness + 编码器 + 前缀；不改任何产品码。
跑法：python -u analysis/ga_export_best_route.py   产物：route/ga_zone1_s22_best_hp171.h5route
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

from ga_loop import build_harness, run_ga, _decode_with_order   # noqa: E402
from solver.fitness import fitness                              # noqa: E402
from probe_crossfloor import OPENING_PREFIX                     # noqa: E402
from export_mt10_boss_route import load_tokens                  # noqa: E402
from gen_h5routes import replay_all                             # noqa: E402
from encode_route import write_h5route, DEFAULT_META            # noqa: E402

W_POTION, W_KEY = 1.5, 39.0
POP, GEN, SEED, XRATE = 15, 10, 20260614, 0.3      # 与 run_ga_zone1_scaleup.py 默认值【完全一致】
OUT = ROOT / "route" / "ga_zone1_s22_best_hp171.h5route"


def main():
    print("组装 GA 电池组(build_harness·persistent=True 暖桶)…")
    H = build_harness(persistent=True)
    start, zone, step_fn = H["start"], H["zone"], H["step"]
    meta, dc, eval_fn = H["meta"], H["decode_cache"], H["eval_fn"]
    bm, bc = H["block_markers"], meta["block_cells"]
    shield = meta["shield"]

    # ── 完全复刻 scaleup 的 GA 跑(同参同种子同注入) → 末代最优基因 ──
    res = run_ga(H["pool"], eval_fn, population=POP, generations=GEN,
                 tournament_k=3, elite=2, crossover_rate=XRATE,
                 inject=[[shield]], seed=SEED)
    best = res.best_individual
    print(f"  GA 末代最优 fitness={res.best_fitness:.1f}  基因({len(best)} 块)")

    # ── 禁区开·与 eval 同口径 decode → tokens + 终态 ──
    tokens, final, norm, verdict = _decode_with_order(
        best, start, zone, step_fn, dc, block_markers=bm, block_cells=bc)
    fh = final.hero
    f = fitness(final, H["roster_fit"], H["big"], H["zone_fids"], w_potion=W_POTION, w_key=W_KEY)
    print(f"  decode 终态: {final.current_floor}({fh.x},{fh.y}) "
          f"HP={fh.hp} ATK={fh.atk} DEF={fh.def_} keys={dict(fh.keys)}  "
          f"tokens={len(tokens)}  fitness={f:.1f}")

    assert not verdict["invalid"], "最优个体被判序列无效——不应发生"
    assert (fh.hp, fh.atk, fh.def_) == (171, 23, 21), \
        f"终态与报告值(HP171/ATK23/DEF21)不符: HP{fh.hp}/A{fh.atk}/D{fh.def_} → GA 跑出别的解，须排查"
    assert round(f, 1) == -1002.0, f"fitness {f:.1f} ≠ 报告 -1002.0"

    # ── 拼 83 步开局前缀 → 封板 sim replay 预检(replay 终态必须 == decode 终态) ──
    prefix = list(load_tokens()[:OPENING_PREFIX])
    pre = replay_all(prefix)
    assert pre.current_floor == "MT3" and pre.hero.hp == 400, \
        f"前缀终态不符: {pre.current_floor} HP{pre.hero.hp}"
    spliced = prefix + list(tokens)
    rfin = replay_all(spliced)
    rh = rfin.hero
    assert (rfin.current_floor, rh.x, rh.y, rh.hp, rh.atk, rh.def_) == \
        (final.current_floor, fh.x, fh.y, fh.hp, fh.atk, fh.def_), \
        (f"拼接 replay 终态 {rfin.current_floor}({rh.x},{rh.y})HP{rh.hp}/A{rh.atk}/D{rh.def_} "
         f"≠ decode 终态 {final.current_floor}({fh.x},{fh.y})HP{fh.hp}/A{fh.atk}/D{fh.def_}")
    print(f"  封板 sim replay 预检 ✅ replay 终态 == decode 终态 "
          f"({rfin.current_floor}({rh.x},{rh.y}) HP{rh.hp}/A{rh.atk}/D{rh.def_})")

    # ── 写盘 ──
    write_h5route(OUT, spliced, DEFAULT_META)
    print(f"\n✅ 已写: route/{OUT.name}  (前缀{len(prefix)} + GA{len(tokens)} = {len(spliced)} token)")
    print("   可直接拖进 h5mota.com 看游戏自己的引擎实地回放。")


if __name__ == "__main__":
    main()
