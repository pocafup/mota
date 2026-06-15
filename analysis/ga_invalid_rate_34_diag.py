"""【只读诊断·§S23 步2】34 块候选 pool 下【长基因禁区无效率】实测（给玩家拍配置·不跑 GA 训练）。

目的：玩家拍板 34 块候选集后，跑长基因（len8/10/12/15）前先量【禁区无效率】——
  序列有效性两半治齐后（§S20 块为目标 + §S21 禁区），随机长基因里有多少比例排序物理不可实现
  （某腿唯一通路须踏入「排其后未进包」的块 → 情况2 判 invalid）。无效率太高＝初代基本全废、
  过夜白跑 → 据此定配置（限基因长度上限 / 注长有效种子 / 调 pop·gen）。

只读：① 不碰 build_min_pool（绝不改产品涌现路径·红线）——34 块 pool 在本脚本内【就地重建】
  （复刻 ga_candidate_blocks_diag.py 已被玩家拍过的统一判据 cand_cells·assert 34）；② 不跑 run_ga、
  不评 fitness——无效率只需 _decode_with_order 吐的 verdict（invalid/navigated/depth），fitness 不参与；
  ③ 复用封板/GA 现成件：_decode_with_order（GA eval 同口径·禁区开）、PersistentNavCache（§S13 暖桶）、
  detect_*/build_block_index（同 build_harness 涌现）。

进度分梯度（'先短后拼长' 爬坡能不能动的关键）：无效基因评分 = INVALID_BASE + 1000×navigated + 10×depth。
  navigated = 撞上第一个不可实现腿【之前】成功导航的腿数。若无效基因 navigated 普遍 >0 且有谱
  → 进度分能把 GA 往「能多走几腿的排序」拽（有梯度）；若清一色 navigated=0（首腿即废）→ 无梯度、
  只能靠初代里【真有有效短基因】起步 → 据此判要不要注种子。

跑法：python analysis/ga_invalid_rate_34_diag.py [N=每长度采样数·默认20] [--persistent]
  --persistent：用落盘暖桶（强烈建议·34 块多数目标对当前桶是冷的、首跑慢、后续基因命中近免费）。
"""
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from probe_crossfloor import build_start                       # noqa: E402
from vzone import build_zone, _zone_attr_gems                  # noqa: E402
from big_item_pull import detect_big_items                     # noqa: E402
from key_targets import detect_key_targets                     # noqa: E402
from block_targets import build_block_index                    # noqa: E402
from solver.beam import build_future_roster                    # noqa: E402
from solver.fitness import build_zone1_roster                  # noqa: E402
from sim.simulator import step                                 # noqa: E402
from ga_loop import _decode_with_order                         # noqa: E402（GA eval 同口径·禁区开）
from ga_candidate_blocks_diag import _reach_set                # noqa: E402（同钥匙口径单层可达集）

LENGTHS = (8, 10, 12, 15)


def _triage_gems(state, zone_fids, afford, zone):
    """攻防宝石逐 cell 三档（同 ga_candidate_blocks_diag·钥匙口径）：①顺路/②代价/③够不到。"""
    gems = _zone_attr_gems(zone)
    out = {}
    for fid in zone_fids:
        zset = _reach_set(state, fid, afford, zero_blood=True)
        dset = _reach_set(state, fid, afford, zero_blood=False)
        for (gfid, x, y) in gems:
            if gfid != fid:
                continue
            out[(gfid, x, y)] = "①" if (x, y) in zset else ("②" if (x, y) in dset else "③")
    return out


def build_candidate_pool():
    """就地重建玩家拍过的 34 块候选 pool（复刻统一判据·不碰 build_min_pool）。
    返回 (start, zone, step, pool, block_markers, block_cells, diag)。"""
    start, _ = build_start()
    zone = build_zone()
    roster_big = build_future_roster(start)
    _rk, zone_fids, _ak = build_zone1_roster(start)

    big_cells, tau, ranked = detect_big_items(zone, roster_big, start)
    drp_by_cell = {c: drp for (drp, c, _da, _dd) in ranked}
    cands, info_key = detect_key_targets(start, zone_fids)
    afford = info_key["afford"]
    gem_tri = _triage_gems(start, zone_fids, afford, zone)

    # 统一判据 → 候选 cell 集（大件安全网 ∪ ②代价宝石[ΔRP>0·∉大件] ∪ ②代价钥匙）
    big_list = sorted(big_cells)
    cand_gems = sorted(c for c, br in gem_tri.items()
                       if br == "②" and c not in big_cells and drp_by_cell.get(c, 0) > 0)
    cand_keys = sorted(cands)
    cand_cells = set(big_list) | set(cand_gems) | set(cand_keys)

    # 折成初始块（同 ga_candidate_blocks_diag）
    fids = sorted(set(zone_fids) | {c[0] for c in cand_cells})
    block_index = build_block_index(fids)
    c2b = block_index["cell_to_block"]
    missing = sorted(c for c in cand_cells if c not in c2b)
    valid_cells = [c for c in cand_cells if c in c2b]

    block_markers = {}
    for c in sorted(valid_cells):
        block_markers.setdefault(c2b[c], set()).add(c)
    block_markers = {b: frozenset(cs) for b, cs in block_markers.items()}
    pool = sorted(block_markers, key=lambda b: (b[0], b[1]))       # 确定性块序
    block_cells = {b: block_index["block_cells"][b] for b in pool}

    diag = dict(n_big=len(big_list), n_gem=len(cand_gems), n_key=len(cand_keys),
                n_cells=len(valid_cells), missing=missing, tau=tau,
                afford=sorted(afford), big_cells=set(big_cells))
    return start, zone, step, pool, block_markers, block_cells, diag


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    persistent = "--persistent" in sys.argv
    n_per = int(args[0]) if args else 20

    print(f"组装 34 块候选 pool（就地重建·不碰 build_min_pool · persistent={persistent} · N/长度={n_per}）…")
    t0 = time.time()
    start, zone, step_fn, pool, block_markers, block_cells, d = build_candidate_pool()
    print(f"  就绪 {time.time() - t0:.1f}s")

    print("\n" + "=" * 78)
    print(f"候选 pool 重建：{d['n_cells']} cell（大件 {d['n_big']} + ②宝石 {d['n_gem']}"
          f" + ②钥匙 {d['n_key']}）→ 折成 {len(pool)} 块")
    print(f"  afford 闭包={d['afford']}  大件 tau={d['tau']:.0f}  大件 cell={sorted(d['big_cells'])}")
    if d["missing"]:
        print(f"  ⚠ 候选 cell 不在任何初始块（已排除·须核对）：{d['missing']}")
    if len(pool) != 34:
        print(f"  ⚠ 块数 {len(pool)} ≠ 玩家拍板的 34！判据/数据可能漂移、请核对后再据此定配置。")
    else:
        print(f"  ✓ 块数=34（与玩家拍板一致）")

    cache = None
    if persistent:
        from nav_cache import PersistentNavCache
        cache = PersistentNavCache()
        print(f"  暖桶：{cache.version_tag}")
    else:
        cache = {}

    print("\n" + "=" * 78)
    print(f"★ 长基因禁区无效率实测（每长度随机采样 {n_per} 条·rng.sample 同 GA _random_individual）")
    print("=" * 78)

    rng = random.Random(20260615)
    summary = []
    for L in LENGTHS:
        if L > len(pool):
            print(f"\n  长度 {L} > pool {len(pool)}，跳过")
            continue
        print(f"\n  ── 长度 L={L} ──", flush=True)
        rows = []      # (invalid, navigated, depth, dt)
        tL = time.time()
        for i in range(n_per):
            gene = rng.sample(pool, L)
            tg = time.time()
            _tok, _fin, _norm, verdict = _decode_with_order(
                gene, start, zone, step_fn, cache,
                block_markers=block_markers, block_cells=block_cells)
            dt = time.time() - tg
            rows.append((verdict["invalid"], verdict["navigated"], verdict["depth"], dt))
            mark = "✗无效" if verdict["invalid"] else "✓有效"
            print(f"    [{i + 1:2d}/{n_per}] {mark}  nav={verdict['navigated']:2d}  "
                  f"depth={verdict['depth']:2d}  {dt:5.1f}s", flush=True)

        n_inv = sum(1 for r in rows if r[0])
        n_val = n_per - n_inv
        inv_nav = sorted(r[1] for r in rows if r[0])
        val_nav = sorted(r[1] for r in rows if not r[0])
        inv_nav_pos = sum(1 for v in inv_nav if v > 0)
        dt_tot = time.time() - tL
        rate = 100.0 * n_inv / n_per
        print(f"    ▸ 无效 {n_inv}/{n_per} ({rate:.0f}%)   有效 {n_val}/{n_per}")
        if inv_nav:
            print(f"    ▸ 无效基因 navigated: min={inv_nav[0]} max={inv_nav[-1]} "
                  f"mean={sum(inv_nav) / len(inv_nav):.1f}  (>0 占 {inv_nav_pos}/{n_inv}"
                  f" → 进度分{'有' if inv_nav_pos else '无'}梯度)  谱={inv_nav}")
        if val_nav:
            print(f"    ▸ 有效基因 navigated（初代能存活的）= {val_nav}")
        print(f"    ▸ 耗时 总={dt_tot:.0f}s 均={dt_tot / n_per:.1f}s/基因")
        summary.append((L, n_inv, n_per, rate, n_val, inv_nav_pos, inv_nav))

    print("\n" + "=" * 78)
    print("★★ 汇总（给玩家拍配置）")
    print("=" * 78)
    print(f"  {'长度':>4} {'无效率':>7} {'有效条数':>8} {'无效nav>0占比':>14}  进度分梯度")
    for (L, n_inv, n, rate, n_val, pos, inv_nav) in summary:
        grad = f"{pos}/{n_inv}" if n_inv else "—"
        has = "有" if pos else "无"
        print(f"  {L:>4} {rate:>6.0f}% {n_val:>6}/{n:<2} {grad:>14}  {has}梯度")

    if hasattr(cache, "stats"):
        print(f"\n  navigate_to 暖桶: 桶={cache.version_tag}  {cache.stats}")
    print("\n  （只读·未跑 GA、未改 build_min_pool。配置由玩家据上表拍：限长上限 / 注种子 / pop·gen。）")


if __name__ == "__main__":
    main()
