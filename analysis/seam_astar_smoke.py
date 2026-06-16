"""【§S32 小验证·纯搜索范式第一步】MT9 盾区 → seam MT10(1,11)：现有 search_quotient 穷尽 Pareto
vs navigate_to 贪心 GBFS。只读·不碰封板件。

回答玩家四问：
  ① 能不能搜通这一小段（从真实 MT9 起点搜到 seam=MT10(1,11)）？
  ② HP 留得好不好（对比 navigate_to 这段把 HP 留多少·§S30 探针 navigate 一路烧）？
  ③ 状态爆不爆（MT9 富层·块抽象压得住吗·搜一次多久·指纹/展开数）？
  ④ 有没有路径决策（出口 Pareto 前沿是否含「拿盾 vs 不拿盾」等取舍 = navigate 给不出的）？

起点不猜：重放真实通关存档到【第一次踏入 MT9】的那一刻（落上楼梯 (1,10)、紧邻下楼梯 (1,11)）。
  这是真实、可复现、未被任何 navigate 污染的 MT9 起点。属性 = 真实存档当时值（低属性、还没拿盾）。

口径复刻 curriculum_scan_vboss：cross_floor=True 限 {MT9,MT10}、beam_k=None 穷尽 Pareto、
  distinguish_doors=True（修红门 Pareto bug）。seam=MT10(1,11)（MT9↔MT10 楼梯免费边·§S29 钉死前提）。

用法：python -u analysis/seam_astar_smoke.py [--max-states 600000] [--nav-maxpops 8000]
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.verify_all_checkpoints import build_initial_state, load_tokens   # noqa: E402
from sim.simulator import step                                                 # noqa: E402
from solver.quotient import (search_quotient, count_floor_blocks,              # noqa: E402
                             partition_floor_blocks, _free_cells)
from ga_navigate import navigate_to                                           # noqa: E402
from vzone import build_zone                                                  # noqa: E402

# §S32 数据真相修正：MT9.changeFloor "1,11"→:next(MT10) stair=downFloor ⟹ 踩 MT9(1,11) 落到
# MT10.downFloor=(1,10)；MT10(1,11) 是【下楼回 MT9】的楼梯格(换层格·非自由·踩上即弹走)，
# 任何楼梯落点都不会把英雄放到 (1,11) → goal 的 in-free 判据【永不成立】=结构不可达。
# 真正"刚跨进 MT10"的落点 = MT10(1,10)（demo 已证 navigate 可达、落点正是 (1,10)）。
SEAM = ("MT10", 1, 10)
ALLOWED = {"MT9", "MT10"}


def seg_step(state, action):
    """把穷尽搜框在 {MT9,MT10}：踏出本段（回 MT8 等）的子态置 dead 裁掉。"""
    ns = step(state, action)
    if ns.current_floor not in ALLOWED:
        ns.dead = True
    return ns


def fmt(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    items = {k: v for k, v in h.items.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 道具={items}")


def first_enter_mt9():
    """重放真实存档，返回【第一次 current_floor 变成 MT9】那一刻的态 + token index。"""
    s = build_initial_state()
    tokens = load_tokens()
    for i, tok in enumerate(tokens):
        s = step(s, tok)
        if s.current_floor == "MT9":
            return s, i
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=600_000,
                    help="search_quotient 穷尽搜状态上限（安全网·撞 cap=爆）")
    ap.add_argument("--nav-maxpops", type=int, default=8000, help="navigate_to 弹出护栏")
    args = ap.parse_args()

    print("=" * 78)
    print("§S32 小验证：MT9 盾区 → seam MT10(1,11)  现有 search_quotient 穷尽 vs navigate 贪心")
    print("=" * 78)

    t0 = time.time()
    zone = build_zone()
    print(f"build_zone 就绪 {time.time()-t0:.1f}s", flush=True)

    mt9, idx = first_enter_mt9()
    if mt9 is None:
        print("🛑 存档里没找到 MT9（解析/路线异常）")
        sys.exit(1)
    print(f"\n起点 = 真实存档第一次进 MT9：token[{idx}]")
    print(f"  起点态：{fmt(mt9)}")
    print(f"  _single_floor_copy={mt9._single_floor_copy}（须 False=多层安全深拷·cross_floor 前提）")
    assert mt9._single_floor_copy is False, "起点 _single_floor_copy 非 False → cross_floor 搜会污染！"

    nblk, nfree = count_floor_blocks(mt9)
    free0 = _free_cells(mt9)
    print(f"  MT9 起点态缩点规模：自由块数={nblk}  自由格合计={nfree}  英雄当前自由块大小={len(free0)}")

    # ── ① navigate_to 贪心基准（cache=None 干净对照）──────────────────────────────
    print("\n" + "-" * 78)
    print("① navigate_to 贪心 GBFS → seam（h=结构距离主导·血够不绕路·§S30 天花板）")
    print("-" * 78)
    tn = time.time()
    seam_nav, moves_nav, reached_nav = navigate_to(mt9, SEAM, zone, step,
                                                   max_pops=args.nav_maxpops, cache=None)
    print(f"  reached={reached_nav}  耗时 {time.time()-tn:.1f}s  步数={len(moves_nav)}")
    if reached_nav:
        print(f"  navigate seam 态：{fmt(seam_nav)}")
    else:
        print("  navigate 送不到 seam（max_pops 内）")

    # ── ② search_quotient 穷尽 Pareto 基线（零改动·算子级够不够用的直接证据）────────
    print("\n" + "-" * 78)
    print("② search_quotient 穷尽 Pareto → seam（cross_floor 限{MT9,MT10}·beam_k=None·distinguish_doors）")
    print("-" * 78)
    tq = time.time()
    res = search_quotient(mt9, SEAM, seg_step, max_states=args.max_states,
                          cross_floor=True, beam_k=None, distinguish_doors=True)
    secs = time.time() - tq
    print(f"  found={res.found}  耗时 {secs:.1f}s  hit_cap={res.hit_cap}")
    print(f"  状态规模：distinct_fingerprints={res.distinct_fingerprints}  "
          f"states_expanded={res.states_expanded}  states_generated={res.states_generated}")
    print(f"  n_waves={res.n_waves}  frontier_peak={res.frontier_peak}  "
          f"n_blocks_peak={res.n_blocks_peak}  goal_hits={res.goal_hits}")
    print(f"  各层指纹分布 fp_by_floor={dict(res.fp_by_floor)}")
    if getattr(res, "intercept_locs", None):
        print(f"  ⚠ 撞 choices 拦截态（未解·商人/祭坛）：{res.intercept_locs}")

    if res.found:
        fr = res.goal_frontier  # value_vector dict 列表
        print(f"\n  ★出口 Pareto 前沿 {len(fr)} 个点（= MT9 内可达的非支配资源态·下楼即达 seam）：")
        # 按 hp 降序打印
        def_keys = lambda v: {k: v.get(k) for k in ("yellowKey", "blueKey", "redKey") if v.get(k)}
        rows = sorted(fr, key=lambda v: -v.get("hp", 0))
        for v in rows:
            print(f"     HP={v.get('hp'):>4} ATK={v.get('atk'):>3} DEF={v.get('def'):>3} "
                  f"钥={def_keys(v)}  其他={{k:v[k] for k in v if k not in ('hp','atk','def','yellowKey','blueKey','redKey')}}")
        best_hp = max(fr, key=lambda v: v.get("hp", 0))
        print(f"\n  ★max-HP 出口：HP={best_hp.get('hp')} ATK={best_hp.get('atk')} DEF={best_hp.get('def')}")
        # 有没有「拿盾」出口（DEF 高于起点 = 拿了盾）
        start_def = mt9.hero.def_
        shield_outs = [v for v in fr if v.get("def", 0) > start_def]
        print(f"  ★含「DEF>起点({start_def})=拿了盾/防具」的出口：{len(shield_outs)} 个"
              + (f"（最高 DEF={max(v['def'] for v in shield_outs)}）" if shield_outs else ""))
    else:
        print("  ✗ 没搜通（found=False）→ 这个起点态从 MT9 到不了 seam（属性/钥匙不够 or 段裁切）")

    # ── 解读对照 ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("【对照解读】")
    print("=" * 78)
    if reached_nav and res.found:
        nv = seam_nav.hero
        bh = max(res.goal_frontier, key=lambda v: v.get("hp", 0))
        print(f"  navigate 贪心 seam：HP={nv.hp} ATK={nv.atk} DEF={nv.def_}")
        print(f"  穷尽 max-HP 出口  ：HP={bh.get('hp')} ATK={bh.get('atk')} DEF={bh.get('def')}")
        print(f"  穷尽前沿点数={len(res.goal_frontier)}（>1 = 给出 navigate 给不出的取舍 = 路径决策被打开）")
    print(f"\n  状态爆不爆：distinct_fp={res.distinct_fingerprints} / cap={args.max_states} "
          f"/ hit_cap={res.hit_cap} / {secs:.1f}s")
    print("=" * 78)


if __name__ == "__main__":
    main()
