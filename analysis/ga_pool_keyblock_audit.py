"""【§S25 判断4 只读审计】34 块 pool 里哪些是「纯钥块」？全舍纯钥块后剩几块？

玩家方向（§S25）：
  · navigate_to 自己绕拿开门钥（命门已坐实）→ 纯钥块（只含钥、无攻防/大件）可全舍，钥交 navigate_to 自理。
  · 红钥块留（判断4）：红钥是「攒够攻防后最后一步」的硬目标（判断3），不是普通顺路钥。
  · 留攻防/宝石/大件块。

本脚本复刻 ga_overnight_34.py 的【统一 pool 判据】（assert 34），逐块打：
  role（剑/盾/钥色/宝攻/宝防）+ marker cell + 分类（纯钥块 vs 含攻防块）。
  → 数出：纯钥块几块（按色拆）、含属性块几块、全舍纯钥块后 pool 剩几块。
并单独确认红钥的三分归属（①顺路 / ②候选 / ③够不到）——坐实「红钥不在普通候选②、是 ③ 硬目标」。

只读：不改任何产品码/fitness/navigate_to。不跑 navigate_to（只看块结构·秒级）。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from ga_loop import build_harness                       # noqa: E402
from vzone import _zone_attr_gems                        # noqa: E402
from block_targets import build_block_index              # noqa: E402
from ga_invalid_rate_34_diag import _triage_gems         # noqa: E402


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("组装电池组（build_harness·persistent=False）…")
    t0 = time.time()
    H = build_harness(persistent=False)
    start, zone, zone_fids = H["start"], H["zone"], H["zone_fids"]
    big_cells, ranked, cands = H["big_cells"], H["ranked"], H["cands"]
    info_key = H["info_key"]
    afford, colors = info_key["afford"], info_key["colors"]
    print(f"  就绪 {time.time() - t0:.1f}s")

    # ── 复刻 34 块 pool 判据（与 ga_overnight_34.py 一字一致）──
    drp_by_cell = {c: drp for (drp, c, _da, _dd) in ranked}
    gem_dadd = _zone_attr_gems(zone)
    gem_tri = _triage_gems(start, zone_fids, afford, zone)

    cand_gems = sorted(c for c, br in gem_tri.items()
                       if br == "②" and c not in big_cells and drp_by_cell.get(c, 0) > 0)
    cand_keys = sorted(cands)
    cand_keys_set = set(cand_keys)
    cand_cells = set(sorted(big_cells)) | set(cand_gems) | set(cand_keys)

    fids = sorted(set(zone_fids) | {c[0] for c in cand_cells})
    block_index = build_block_index(fids)
    c2b = block_index["cell_to_block"]
    cand_cells = [c for c in cand_cells if c in c2b]
    block_markers = {}
    for c in sorted(cand_cells):
        block_markers.setdefault(c2b[c], set()).add(c)
    block_markers = {b: frozenset(cs) for b, cs in block_markers.items()}
    pool = sorted(block_markers, key=lambda b: (b[0], b[1]))
    assert len(pool) == 34, f"pool 块数 {len(pool)} ≠ 34（判据/数据漂移）"

    def role_cells(b):
        """逐 marker cell → (role 标签, cell)。"""
        out = []
        for c in sorted(block_markers[b]):
            if c in big_cells:
                da, _dd = gem_dadd.get(c, (0, 0))
                out.append(("剑(大件)" if da > 0 else "盾(大件)", c))
            elif c in cand_keys_set:
                out.append((f"钥-{colors.get(c, '?')}", c))
            else:
                da, _dd = gem_dadd.get(c, (0, 0))
                out.append(("宝攻" if da > 0 else "宝防", c))
        return out

    def is_pure_key(b):
        return all(c in cand_keys_set for c in block_markers[b])

    # ── 红钥三分归属（坐实它不在普通候选②）──
    red_cells = sorted(c for c, col in colors.items() if col == "redKey")
    print("\n" + "=" * 78)
    print("【红钥三分归属】（坐实红钥不是普通顺路/候选钥、是 ③ 硬目标）")
    print("=" * 78)
    cheap, unreach = info_key.get("cheap", set()), info_key.get("unreachable", set())
    print(f"  redKey cell（detect 全集 redKey 色）= {red_cells}")
    print(f"  afford 闭包（零钥起步滚到的可开门色）= {sorted(afford)}")
    for rc in red_cells:
        loc = ("②候选" if rc in cands else
               "①顺路" if rc in cheap else
               "③够不到" if rc in unreach else "（未分类）")
        print(f"    红钥 {rc}：三分={loc}   在34块pool? {rc in c2b and c2b[rc] in pool}")

    # ── 逐块打 role + 分类 ──
    pure_key_blocks, attr_blocks = [], []
    print("\n" + "=" * 78)
    print("【34 块逐块审计】(role / marker cell / 纯钥块?)")
    print("=" * 78)
    for b in pool:
        rcs = role_cells(b)
        roles = "+".join(r for r, _ in rcs)
        pure = is_pure_key(b)
        (pure_key_blocks if pure else attr_blocks).append(b)
        flag = "★纯钥块(可舍)" if pure else "  含属性(留)"
        print(f"  {flag}  block={b}  [{roles}]")
        for r, c in rcs:
            print(f"                marker {c}  → {r}")

    # ── 纯钥块按色拆 ──
    from collections import Counter
    pure_color = Counter()
    for b in pure_key_blocks:
        for c in block_markers[b]:
            pure_color[colors.get(c, "?")] += 1

    print("\n" + "=" * 78)
    print("【判断4 结论】")
    print("=" * 78)
    print(f"  34 块总计：纯钥块 {len(pure_key_blocks)} 块 + 含属性块 {len(attr_blocks)} 块")
    print(f"  纯钥块按色（marker 计数）：{dict(pure_color)}")
    print(f"  ★全舍纯钥块后 pool 剩 = {len(attr_blocks)} 块（=含攻防/宝石/大件块）")
    print(f"  含属性块清单：")
    for b in attr_blocks:
        roles = "+".join(r for r, _ in role_cells(b))
        print(f"      {b}  [{roles}]")
    has_red_in_pool = any(c2b.get(rc) in pool for rc in red_cells if rc in c2b)
    print(f"\n  红钥在 34 块 pool 里? {has_red_in_pool}  "
          f"→ {'红钥块在pool(判断4留它)' if has_red_in_pool else '红钥本就不在pool(③够不到)·判断3须另加为硬目标'}")


if __name__ == "__main__":
    main()
