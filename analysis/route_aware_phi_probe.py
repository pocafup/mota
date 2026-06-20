"""【更聪明Φ·廉价档·§S52】前向贪心 rollout 损血当 beam_score_fn。

定位（§S46 轴 b→d）：retrograde V = 后向精确 max-over-all-routes（贵·MT7 爆炸）；
更聪明Φ = 前向贪心估【一条合理路线】的损血（便宜·无穷尽·无搜索）；现Φ(§S42 path-loss)
= 当前属性打光【全怪集】（无属性前瞻·路线盲）。三者同轴、保真度递减。

Φ(state) 算法（每态一次·多项式·零搜索）：模拟影子英雄从 state 出发——
  阶段1 贪心烧血换属性：对每个剩余属性道具算 net = gain(拿了它剩余损血降多少·Φ_static 差分)
        − cost(获取它要打的怪损血·compute_combat)，选 net 最大且 >0 的拿、shadow 属性递增、
        累加 cost。反复到没有正 net。★net>0 才拿 = 烧血换属性的数学（先亏 cost 后赚 gain）。
  阶段2 用攒够的 shadow 属性打【必经怪集 M】+ 目标。
  Φ = 总损血。score = state.hp − Φ。

廉价档（§S51 玩家选）：precost(获取怪集)与 M 段初一次性预计算（navigate 从段起点），
在线纯查表+compute_combat 缓存、零在线寻路。先在小段(MT9盾→seam)对照 retrograde V H*=324 验证。

铁律：损血全走 compute_combat（_monster_loss）·不手写战斗公式；gain/cost/net 全由怪属性
+道具增量算出·零预设魔法数权重；当 beam_score_fn(现成钩子)·零产品码改动·守 beam 零回归。

用法：python -u analysis/route_aware_phi_probe.py [--segment small|redkey] [--beam-k 8,24] [--phi-only]
"""
import argparse
import json
import os
import sys
import time
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_astar_smoke import first_enter_mt9, SEAM, seg_step  # noqa: E402
from analysis.dir2_redkey_pathloss_beam import _monster_loss          # noqa: E402
from sim.simulator import step, _load_floor_if_needed, _build_monster  # noqa: E402
from solver.quotient import search_quotient                           # noqa: E402
from extract.ga_navigate import navigate_to                           # noqa: E402
from vzone import build_zone                                          # noqa: E402

_ITEMS_DB = json.loads((ROOT / "data" / "games51" / "items.json").read_text(encoding="utf-8"))

# 段定义：小段=只验证场(有精确 retrograde V H*=324 对照)；红钥段=整一区真考验(无精确 V·对照 §S42)。
SEG = {
    "small":  {"floors": ["MT9", "MT10"], "goal": SEAM,            "hstar": 324},
    "redkey": {"floors": ["MT1", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10"],
               "goal": ("MT8", 10, 2),                              "hstar": None},
}


def item_attr_delta(item_id, ratio):
    """属性道具→(stat∈{atk,def}, delta)。非属性(钥/血瓶/mdef/multi)→None。一区 ratio=1。
    ★段内道具均为单 stat 的 gem/sword/shield(inventory 清单坐实无 yellowGem multi)。"""
    idata = _ITEMS_DB.get(item_id)
    if not idata:
        return None
    eff = idata.get("pickup")
    if not isinstance(eff, dict) or eff.get("type") != "stat":
        return None
    stat = eff.get("stat")
    if stat not in ("atk", "def"):
        return None
    delta = eff["base"] * ratio if eff.get("ratio_scaled") else eff.get("delta", 0)
    return (stat, delta)


def enumerate_attr_items(start, floors):
    """段内属性道具格：[(floor,x,y,item_id,stat,delta)]·遍历各层初始 entities·过滤 atk/def 道具。"""
    out = []
    for f in floors:
        if not _load_floor_if_needed(start, f):
            print(f"  ⚠ {f} 加载失败(文件缺)")
            continue
        fl = start.floors[f]
        for y in range(len(fl.entities)):
            for x in range(len(fl.entities[y])):
                iid = fl._tile_to_item.get(fl.entities[y][x])
                if not iid:
                    continue
                d = item_attr_delta(iid, fl.ratio)
                if d:
                    out.append((f, x, y, iid, d[0], d[1]))
    return out


def enumerate_monster_cells(start, floors):
    """段内怪格全集：{(floor,x,y): monster_id}。"""
    out = {}
    for f in floors:
        if not _load_floor_if_needed(start, f):
            continue
        fl = start.floors[f]
        for y in range(len(fl.entities)):
            for x in range(len(fl.entities[y])):
                mid = fl._tile_to_enemy.get(fl.entities[y][x])
                if mid:
                    out[(f, x, y)] = mid
    return out


def _is_cleared(state, cell):
    """该怪/道具格是否已清空(怪打了/道具拿了)。未 load 的层→当作还在(False)。"""
    f, x, y = cell
    fl = state.floors.get(f)
    if fl is None:
        return False
    return fl.entities[y][x] == 0


def cleared_monster_cells(state, mon_cells):
    return {c for c in mon_cells if _is_cleared(state, c)}


def precompute_item_cost(start, items, mon_cells, zone, max_pops):
    """每个属性道具的【获取怪集】：navigate 段起点→道具格，取路径上新打的怪格。
    够不到(reached=False)→None(该属性不规划)。一次性预计算·在线纯查表。"""
    base_cleared = cleared_monster_cells(start, mon_cells)
    out = {}
    for i, (f, x, y, iid, stat, delta) in enumerate(items):
        final, _moves, reached = navigate_to(start, (f, x, y), zone, step, max_pops=max_pops)
        if not reached:
            out[i] = None
            continue
        out[i] = frozenset(cleared_monster_cells(final, mon_cells) - base_cleared)
    return out


def compute_must_cells(start, goal, mon_cells, zone, max_pops):
    """必经怪集 M(廉价档近似)：navigate 段起点→目标，取路径上的怪格。
    小段够用；整一区将换乐观图割点法(留后续档)。"""
    base_cleared = cleared_monster_cells(start, mon_cells)
    final, _moves, reached = navigate_to(start, goal, zone, step, max_pops=max_pops)
    if not reached:
        print("  ⚠ navigate 到目标失败 → 必经集 M 空(Φ 会偏低)")
        return frozenset()
    return frozenset(cleared_monster_cells(final, mon_cells) - base_cleared)


def build_phi(start, floors, goal, zone, max_pops):
    """组装更聪明Φ(state)→score。返回 (score_fn, diag)。"""
    items = enumerate_attr_items(start, floors)
    mon_cells = enumerate_monster_cells(start, floors)
    mons = {c: _build_monster(start, mid) for c, mid in mon_cells.items()}
    mdef0 = start.hero.mdef
    item_precost = precompute_item_cost(start, items, mon_cells, zone, max_pops)
    must_cells = compute_must_cells(start, goal, mon_cells, zone, max_pops)

    @lru_cache(maxsize=None)
    def loss_one(a, d, cell):
        return _monster_loss(a, d, mons[cell], mdef0)

    @lru_cache(maxsize=None)
    def phi_static(a, d):
        """全怪集损血和(gain 用其差分·高估但作贪心相对排序够用·近似软点1)。"""
        return sum(_monster_loss(a, d, m, mdef0) for m in mons.values())

    def phi_loss(state):
        h = state.hero
        a, d = h.atk, h.def_
        planned = cleared_monster_cells(state, mon_cells)
        planned_items = {i for i, it in enumerate(items) if _is_cleared(state, (it[0], it[1], it[2]))}
        total = 0
        # ── 阶段1：贪心烧血换属性(net=gain−cost·选正 net 最大) ──
        while True:
            best_net, best = 0.0, None
            for i, it in enumerate(items):
                if i in planned_items:
                    continue
                pc = item_precost[i]
                if pc is None:
                    continue
                stat, delta = it[4], it[5]
                na, nd = (a + delta, d) if stat == "atk" else (a, d + delta)
                gain = phi_static(a, d) - phi_static(na, nd)
                cost_cells = pc - planned
                cost = sum(loss_one(a, d, c) for c in cost_cells)
                net = gain - cost
                if net > best_net:
                    best_net, best = net, (i, cost, cost_cells, stat, delta)
            if best is None:
                break
            i, cost, cost_cells, stat, delta = best
            total += cost
            if stat == "atk":
                a += delta
            else:
                d += delta
            planned |= cost_cells
            planned_items.add(i)
        # ── 阶段2：用攒够的属性打必经怪 M ──
        for c in must_cells - planned:
            total += loss_one(a, d, c)
        return total

    def score_fn(state):
        return state.hero.hp - phi_loss(state)

    diag = dict(items=items, mon_cells=mon_cells, item_precost=item_precost,
                must_cells=must_cells, phi_static=phi_static, phi_loss=phi_loss)
    return score_fn, diag


def fmt_vec(v):
    return (f"HP={v.get('hp', 0)} ATK={v.get('atk', 0)} DEF={v.get('def', 0)} "
            f"金={v.get('gold', 0)} 杀={v.get('kill', 0)}")


def run_beam(start, goal, beam_k, score_fn, max_states, tag):
    t0 = time.time()
    res = search_quotient(start, goal, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=True,
                          beam_score_fn=score_fn, beam_diversity="stairs")
    secs = time.time() - t0
    print(f"\n  ── beam_k={beam_k} · {tag} · {secs:.1f}s · found={res.found} "
          f"distinct_fp={res.distinct_fingerprints} cut={res.beam_cut_total}")
    if not res.found:
        print("     ✗ 没搜通")
        return None
    fr = res.goal_frontier
    best_hp = max(fr, key=lambda v: v.get("hp", 0))
    best_atk = max(fr, key=lambda v: (v.get("atk", 0), v.get("def", 0)))
    print(f"     出口前沿 {len(fr)} 点 | max-HP: {fmt_vec(best_hp)} | max-ATK: {fmt_vec(best_atk)}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", choices=["small", "redkey"], default="small")
    ap.add_argument("--beam-k", default="8,24", help="逗号分隔的 beam_k 档")
    ap.add_argument("--max-states", type=int, default=600_000)
    ap.add_argument("--nav-maxpops", type=int, default=8000)
    ap.add_argument("--phi-only", action="store_true", help="只 dump Φ 自检·不跑 beam")
    args = ap.parse_args()

    seg = SEG[args.segment]
    floors, goal, hstar = seg["floors"], seg["goal"], seg["hstar"]
    print("=" * 84)
    print(f"§S52 更聪明Φ廉价档 · segment={args.segment} 楼层={floors} goal={goal} "
          f"H*={hstar if hstar else '无精确V对照'}")
    print("=" * 84)

    t0 = time.time()
    zone = build_zone()
    print(f"build_zone 就绪 {time.time() - t0:.1f}s", flush=True)

    start, idx = first_enter_mt9()
    if start is None:
        print("🛑 没找到 MT9 起点")
        return
    h0 = start.hero
    print(f"起点 = 真实存档首进 MT9 token[{idx}]: {start.current_floor}({h0.x},{h0.y}) "
          f"HP={h0.hp} ATK={h0.atk} DEF={h0.def_} mdef={h0.mdef}")

    t1 = time.time()
    score_fn, diag = build_phi(start, floors, goal, zone, args.nav_maxpops)
    print(f"build_phi(预计算 precost+M) 就绪 {time.time() - t1:.1f}s", flush=True)

    # ── Φ 自检 dump ──
    items = diag["items"]
    print(f"\n[Φ 自检] 段内属性道具 {len(items)} 个 · 怪格 {len(diag['mon_cells'])} 只 · "
          f"必经集 M {len(diag['must_cells'])} 只")
    for i, (f, x, y, iid, stat, delta) in enumerate(items):
        pc = diag["item_precost"][i]
        pc_s = "够不到" if pc is None else f"{len(pc)}怪"
        print(f"   #{i} {f}({x},{y}) {iid} {stat}+{delta} · 获取怪集={pc_s}")
    print(f"\n[Φ 自检] 起点 Φ_loss={diag['phi_loss'](start)} · "
          f"phi_static(全怪集@{h0.atk},{h0.def_})={diag['phi_static'](h0.atk, h0.def_)} · "
          f"起点 score=hp−Φ={score_fn(start)}")

    if args.phi_only:
        return

    # ── 对照 beam：默认路线盲基线 / 现Φ路线盲全怪集 / ★更聪明Φ ──
    def phi_static_score(state):  # 现Φ(§S42 path-loss)：hp − 全怪集×当前属性损血(无前瞻)
        h = state.hero
        return h.hp - diag["phi_static"](h.atk, h.def_)

    for bk in [int(x) for x in args.beam_k.split(",")]:
        print("\n" + "─" * 84 + f"\n  beam_k={bk}")
        run_beam(start, goal, bk, None, args.max_states, "默认(equiv_hp 路线盲基线)")
        run_beam(start, goal, bk, phi_static_score, args.max_states, "现Φ path-loss(全怪集·无前瞻)")
        run_beam(start, goal, bk, score_fn, args.max_states, "★更聪明Φ(前向贪心 rollout)")
    if hstar:
        print(f"\n★金标准对照：retrograde V 精确 H*={hstar}（更聪明Φ 的 max-HP 越接近越好）")


if __name__ == "__main__":
    main()
