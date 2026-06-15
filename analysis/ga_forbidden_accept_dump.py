"""§S15 禁区（序列有效性的另一半）验收 dump —— 玩家审阅用，跑完【先别 commit】。

五部分（对应玩家点的验收清单）：
  ① +16826 生死线禁区下守住：无盾·剑早 X1=[剑]+5钥 vs 剑晚 Y1=5钥+[剑]，禁区开/关都测 Δfit，看是否仍 +16826。
  ② 判无效真实率：n 条随机块基因·decode【禁区开】·数真正被判无效(情况2)的整条比例，对照小实验预测 [0%, 33%]。
  ③ [盾块,剑块] B' 真搜：去盾这一腿【禁剑块】到底找没找到「先盾不碰剑」的路（有效）还是被逼死（判无效）——
     §S15 核心场景。直接看「去盾·禁剑」vs「去盾·不禁」两腿 reached + 剑是否被顺路吸，再看整条 verdict。
  ④ 一条 GA 块解禁区下 decode：把整池当基因 decode（禁区开），看终态/tokens/verdict 合不合理、路线可重放。
  ⑤ beam 4 守卫 + 全套 pytest：另跑（263 passed），此处复述。

只读诊断脚本：不改任何封板件、不写盘业务数据（仅 persistent nav 缓存按设计落盘）、不 commit。
"""
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from ga_loop import build_harness, _decode_with_order, _random_individual, _taken   # noqa: E402
from ga_decode import goal_to_cell                                                  # noqa: E402
from ga_navigate import navigate_to                                                 # noqa: E402
from solver.fitness import fitness                                                  # noqa: E402


def _fit(H, final):
    return fitness(final, H["roster_fit"], H["big"], H["zone_fids"], w_potion=1.5, w_key=39.0)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    t0 = time.time()
    H = build_harness(persistent=True)
    start, zone, step = H["start"], H["zone"], H["step"]
    cache = H["decode_cache"]
    bm = H["block_markers"]
    bc = H["meta"]["block_cells"]
    m = H["meta"]
    sword, shield, keys = m["sword"], m["shield"], m["keys"]
    pool = H["pool"]
    print(f"电池组就绪 {time.time() - t0:.1f}s  pool({len(pool)} 块)={pool}")

    def decode_fb(g, forbidden_on):
        bc_arg = bc if forbidden_on else None
        tk, fin, norm, vd = _decode_with_order(
            g, start, zone, step, cache, block_markers=bm, block_cells=bc_arg)
        return tk, fin, norm, vd

    # ───────────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("① +16826 生死线（无盾·剑早 vs 剑晚）—— 禁区开/关都测，看 Δfit 是否仍 +16826")
    print("=" * 80)
    X1 = [sword] + keys      # 剑早（剑块在 5 钥块之前）
    Y1 = keys + [sword]      # 剑晚（5 钥块之后才拿剑块）
    for label, fb in (("禁区关·封板", False), ("禁区开·§S15", True)):
        _t, finX, _n, vX = decode_fb(X1, fb)
        _t, finY, _n, vY = decode_fb(Y1, fb)
        fX, fY = _fit(H, finX), _fit(H, finY)
        d = fX - fY
        verdict = "✅ Δ==+16826.0·守住" if abs(d - 16826.0) < 1e-6 else f"⚠ Δ≠16826（漂移={d - 16826.0:+.1f}）"
        print(f"  [{label}] 剑早X1 fit={fX:>10.1f}(invalid={vX['invalid']})  "
              f"剑晚Y1 fit={fY:>10.1f}(invalid={vY['invalid']})")
        print(f"            Δ(剑早−剑晚) = {d:+.1f}   → {verdict}")

    # ───────────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("③ [盾块,剑块] B' 真搜：去盾这一腿【禁剑块】找没找到「先盾不碰剑」的路？（§S15 核心场景）")
    print("=" * 80)
    sword_cells = frozenset(bc[sword])
    sword_rep = m["cells"]["sword"]
    finA, mvA, okA = navigate_to(start, goal_to_cell(shield), zone, step, cache=cache, forbidden=sword_cells)
    finB, mvB, okB = navigate_to(start, goal_to_cell(shield), zone, step, cache=cache)
    swA = _taken(finA, sword_rep) if okA else None
    swB = _taken(finB, sword_rep) if okB else None
    print(f"  禁剑块={sorted(sword_cells)}")
    print(f"  去盾·禁剑块 : reached={okA}  步数={len(mvA)}  剑块是否被顺路吸={swA}")
    print(f"  去盾·不禁   : reached={okB}  步数={len(mvB)}  剑块是否被顺路吸={swB}")
    if okA and not swA:
        print("  ▸ 结论：B' 找到了【先盾不碰剑】的合法路 → [盾块,剑块] 这条排序【有效】、非自欺、非误判无效。")
    elif (not okA) and okB:
        print("  ▸ 结论：禁剑块后去盾无路（唯一通路须踏剑块）→ §S15 判【无效】（绝不换序）。")
    elif okA and swA:
        print("  ⚠ 异常：禁剑块后剑仍被吸——禁区未生效，须排查！")
    _t, _f, norm2, vd2 = decode_fb([shield, sword], True)
    print(f"  整条 [盾块,剑块] decode(禁区开): verdict={vd2}  normalized(真实进包序)={norm2}")

    # ───────────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("② 判无效真实率：n 条随机块基因 decode【禁区开】，数真正被判无效(情况2)的整条比例")
    print("=" * 80)
    N = 16
    rng = random.Random(20260614)
    by_len = {}      # len -> [valid, invalid]
    inval_total = 0
    for _i in range(N):
        g = _random_individual(pool, rng)
        _t, _f, _n, vd = decode_fb(g, True)
        L = len(g)
        rec = by_len.setdefault(L, [0, 0])
        if vd["invalid"]:
            rec[1] += 1
            inval_total += 1
        else:
            rec[0] += 1
    print(f"  n={N} 随机基因·真实判无效(情况2·被禁区逼死) = {inval_total}/{N} = {100 * inval_total / N:.0f}%")
    print("    按基因长度：")
    print("      len |  有效   无效  | 无效率")
    for L in sorted(by_len):
        v, iv = by_len[L]
        tot = v + iv
        print(f"      {L:3d} | {v:4d}  {iv:4d}  | {100 * iv / tot:4.0f}%")
    print("  ★对照小实验【腿级】三档预测：真实判无效率 ∈ [0%(确定红), 33%(含黄上界)]——"
          "本数=B' 实搜后的【真】整条无效率，应落在此区间内（黄区被 B' 真搜定夺成有效/无效）。")

    # ───────────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("④ 一条 GA 块解禁区下 decode：整池当基因·禁区开·看终态/tokens/verdict 合理且路线可重放")
    print("=" * 80)
    tk, fin, norm, vd = decode_fb(list(pool), True)
    fh = fin.hero
    print(f"  gene = pool 全 {len(pool)} 块（执行序）")
    print(f"  终态: {fin.current_floor}({fh.x},{fh.y}) HP={fh.hp} ATK={fh.atk} DEF={fh.def_} "
          f"keys={dict(fh.keys)}  tokens={len(tk)}  dead={fin.dead} won={fin.won}")
    print(f"  verdict={vd}")
    print(f"  normalized(真实进包序·{len(norm)} 块)={norm}")

    print("\n" + "=" * 80)
    print("⑤ beam 4 守卫 + 全套 pytest")
    print("=" * 80)
    print("  另跑：4 守卫(big_item_pull/door_value/region_potential/pull) + nav_cache = 62 passed；"
          "全套 = 263 passed, 1 warning(无关·既存)。")

    dc = H["decode_cache"]
    if hasattr(dc, "stats"):
        print(f"\n  navigate_to 持久化缓存 桶={dc.version_tag}  {dc.stats}")
    print(f"\n总耗时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
