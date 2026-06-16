"""【§S25 红钥末腿·max_pops 标定（先标定别拍 30000）】

玩家纪律（§S25）：末腿 max_pops 别拍脑袋用 30000——0 钥红钥探针跑 30000 pops/207s 才放弃，若末腿用大预算，
早代弱基因每条在末腿上烧 ~200s 失败 → 过夜被拖死。正确做法：
  ① 取【强基因】（全 13 属性块·攒满攻防）decode → 强终态；
  ② 从强终态 navigate_to 红钥，测它【成功够到】要多少 pops（二分最小可达 max_pops M*）；
  ③ 末腿 cap = 2×M*（强基因有余量够到 + 弱基因失败快兜底）；
  ④ 再测【弱基因】（仅剑块）末腿在 cap 下【失败耗时】= 过夜每条废基因的末腿成本下界。

只读：不改产品码；navigate_to 用独立 dict 缓存（不碰持久桶）。复刻 launcher 的 34→13 判据（assert）。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from ga_loop import build_harness, _decode_with_order, _taken  # noqa: E402
from ga_navigate import navigate_to                            # noqa: E402
from ga_decode import goal_to_cell                             # noqa: E402
from vzone import _zone_attr_gems                              # noqa: E402
from block_targets import build_block_index                    # noqa: E402
from ga_invalid_rate_34_diag import _triage_gems               # noqa: E402


def rebuild_attr_pool(H):
    """复刻 launcher 的 34 块判据（assert 34）→ 滤掉纯钥块 → 13 属性块（判断4）。返回所需件。"""
    start, zone, zone_fids = H["start"], H["zone"], H["zone_fids"]
    big_cells, ranked, cands = H["big_cells"], H["ranked"], H["cands"]
    afford = H["info_key"]["afford"]
    drp_by_cell = {c: drp for (drp, c, _da, _dd) in ranked}
    gem_tri = _triage_gems(start, zone_fids, afford, zone)
    cand_gems = sorted(c for c, br in gem_tri.items()
                       if br == "②" and c not in big_cells and drp_by_cell.get(c, 0) > 0)
    cand_keys_set = set(sorted(cands))
    cand_cells = set(sorted(big_cells)) | set(cand_gems) | cand_keys_set
    fids = sorted(set(zone_fids) | {c[0] for c in cand_cells})
    block_index = build_block_index(fids)
    c2b = block_index["cell_to_block"]
    cand_cells = [c for c in cand_cells if c in c2b]
    block_markers = {}
    for c in sorted(cand_cells):
        block_markers.setdefault(c2b[c], set()).add(c)
    block_markers = {b: frozenset(cs) for b, cs in block_markers.items()}
    pool = sorted(block_markers, key=lambda b: (b[0], b[1]))
    assert len(pool) == 34, f"pool {len(pool)} ≠ 34"

    def is_pure_key(b):
        return all(c in cand_keys_set for c in block_markers[b])

    pool_attr = [b for b in pool if not is_pure_key(b)]
    block_cells = {b: block_index["block_cells"][b] for b in pool}
    sword_c = next(c for (_d, c, da, _dd) in ranked if c in big_cells and da > 0)
    return dict(pool_attr=pool_attr, block_markers=block_markers, block_cells=block_cells,
                sword_block=c2b[sword_c])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("组装电池组（build_harness·persistent=False）…")
    t0 = time.time()
    H = build_harness(persistent=False)
    start, zone, step = H["start"], H["zone"], H["step"]
    red_block, red_markers = H["red_block"], H["red_markers"]
    print(f"  就绪 {time.time() - t0:.1f}s  红钥块={red_block}  红钥 marker={set(red_markers)}")

    P = rebuild_attr_pool(H)
    pool_attr, sword_block = P["pool_attr"], P["sword_block"]
    bm, bc = P["block_markers"], P["block_cells"]
    print(f"  13 属性块（判断4 后）= {pool_attr}")
    assert len(pool_attr) == 13, f"属性块 {len(pool_attr)} ≠ 13"

    # ── ① 强基因 = §S24 过夜 A 机 gen2 实测最优解（真 GA 涌现·非手写路径）→ decode（禁区开·复刻）→ 强终态 ──
    #    为何不合成：feed 全 13 属性块按任何序 decode 都卡 ATK11/导航腿1——弱英雄从浅层够不到深层守卫块、
    #    navigate_to 原子失败=零进度。攒强须特定序（GA 自己爬出来的）。直接取 overnight_A_best.txt 的真 GA
    #    解（含钥块·块 id 稳定·decode 一字不改照跑）：ATK26 DEF25@MT5(1,8)、剑盾皆进包、ATK26>红钥守卫门槛25。
    #    禁区开（block_cells=bc）：复刻它被 GA 产出时的判据（该解 序列有效·禁区开下能复现 ATK26）。
    STRONG_GENE_S24 = [
        ('MT7', (9, 1)), ('MT1', (7, 3)), ('MT8', (7, 10)), ('MT6', (3, 1)),
        ('MT9', (9, 9)), ('MT9', (1, 1)), ('MT8', (4, 10)), ('MT10', (2, 6)),
        ('MT5', (1, 5)), ('MT4', (3, 11)), ('MT7', (9, 8)), ('MT7', (5, 10)),
        ('MT4', (4, 10)), ('MT4', (7, 9)), ('MT5', (1, 8)),
    ]
    strong_gene = [b for b in STRONG_GENE_S24 if b in bm]
    print("\n[①] 强基因 = §S24 过夜 A gen2 实测最优解（15 块·真 GA 涌现·禁区开）→ decode → 强终态 …")
    print(f"  基因块数={len(strong_gene)}/15（须全在 bm·否则块漂移）")
    assert len(strong_gene) == 15, f"§S24 强基因块 {len(strong_gene)}/15 不全在 bm（块边界漂移·须重取）"
    t1 = time.time()
    cache = {}
    _tok, strong, _norm, vd = _decode_with_order(
        strong_gene, start, zone, step, cache, block_markers=bm, block_cells=bc)
    sh = strong.hero
    print(f"  强终态 {strong.current_floor}({sh.x},{sh.y})  HP={sh.hp} ATK={sh.atk} DEF={sh.def_} "
          f"keys={dict(sh.keys)}  导航腿={vd['navigated']}/15  decode 耗时{time.time() - t1:.1f}s "
          f"（期望 ATK26 DEF25@MT5(1,8)·复刻 §S24）")
    red_already = all(_taken(strong, c) for c in red_markers)
    if red_already:
        print("  ⚠ 强基因 decode 时已顺路吸到红钥（禁区关）→ 末腿 pops 标定意义有限；下方测的是「走到空格」pops。")

    # ── ② 从强终态 navigate_to 红钥：二分最小可达 max_pops M* ──
    red_cell = goal_to_cell(red_block)
    print(f"\n[②] 从强终态 navigate_to 红钥 {red_cell}：二分最小可达 max_pops …")

    def reach_at(mp):
        c = {}
        t = time.time()
        _f, _m, ok = navigate_to(strong, red_cell, zone, step, max_pops=mp, cache=c)
        return ok, time.time() - t

    # 先确认 8000（与其它腿同预算）能否够到
    for mp in (2000, 4000, 6000, 8000, 12000, 16000):
        ok, dt = reach_at(mp)
        print(f"    max_pops={mp:6d}  reached={ok}  {dt:5.1f}s")
        if ok:
            reached_mp = mp
            break
    else:
        print("    ⚠ 16000 内都够不到——强基因攻防不足 or 红钥更深，须加块/调强基因")
        return

    # 二分细化 [prev, reached_mp] 找 M*
    lo = {2000: 0, 4000: 2000, 6000: 4000, 8000: 6000, 12000: 8000, 16000: 12000}[reached_mp]
    hi = reached_mp
    while hi - lo > 500:
        mid = (lo + hi) // 2
        ok, dt = reach_at(mid)
        print(f"    二分 max_pops={mid:6d}  reached={ok}  {dt:5.1f}s")
        if ok:
            hi = mid
        else:
            lo = mid
    M_star = hi
    cap = 2 * M_star
    print(f"\n  ★强基因成功末腿最小 max_pops M* ≈ {M_star}  →  建议 cap = 2×M* = {cap}")

    # ── ③ 弱基因 = 仅剑块 → 末腿在 cap 下失败耗时 ──
    print(f"\n[③] 弱基因 = [剑块] → decode → 末腿在 cap={cap} 下失败耗时（过夜废基因成本下界）…")
    cache2 = {}
    _t, weak, _n, _v = _decode_with_order(
        [sword_block], start, zone, step, cache2, block_markers=bm, block_cells=bc)
    wh = weak.hero
    print(f"  弱终态 ATK={wh.atk} DEF={wh.def_} keys={dict(wh.keys)}")
    c3 = {}
    t3 = time.time()
    _f, _m, wok = navigate_to(weak, red_cell, zone, step, max_pops=cap, cache=c3)
    print(f"  弱基因末腿 reached={wok}（应 False·攻防不足杀不了哨兵）  失败耗时={time.time() - t3:.1f}s")

    print("\n" + "=" * 70)
    print(f"标定结论：末腿 final_max_pops = {cap}（M*≈{M_star} 的 2×）。"
          f"强基因够到、弱基因 cap 内失败快兜底。")
    print("=" * 70)


if __name__ == "__main__":
    main()
