"""【§S53 更聪明Φ·route-aware cost-to-go 到 boss(非截红钥)·无人值守】

承 §S52(route_aware_phi_probe)。§S52 Φ 把"必经集 M"截在红钥(goal=MT8(10,2))→
cost-to-go 漏 boss + MT9/MT10 伏击(玩家钉死=价值跨边界病)。玩家 §S53 三诊断修正：
  ① gem 价值要加 boss 减伤：ATK26→27 对骷髅队长也临界·342→304(DEF27)。第5颗 redGem 真值 =
     守卫省(252→189 ×2=126) + boss 减伤(38) + 伏击群减伤·别只截到红钥漏 boss。
  ② cost-to-go 算到 boss：必经集 M 延伸到 boss(过红钥后 climb MT9→MT10→伏击→boss)。
  ③ 扣必经成本：MT10 红宝石(10,6)要开的黄门/打的怪在去 boss 必经路上(早晚要打)→
     gem 额外成本 = 获取怪集 − 必经集 M(扣掉反正要付的部分) → 很小。

实现(对 §S52 三处改动·全 compute_combat 实算·零手写公式·零魔法数权重)：
  · phi_route(a,d) = Σ_{c∈M} _monster_loss(a,d) —— route-aware(只必经集·含 boss)，
    替 §S52 的 phi_static(全段怪·路线盲)。gem gain = phi_route 差分 → 自然含 boss 减伤(①)。
  · M = leg1(navigate 段起点→红钥·含红钥门守卫) ∪ boss-leg(MT9+MT10 全怪)。boss-leg 用
    "过红钥后必跨层"的全怪做【保守过近似】必经(②)，不跑脆弱的穿伏击 navigate(伏击机关门
    flag 门 + 散怪 GBFS 易卡)。保守=偏高估损血(对所有态一致·排序保真)+把 gem 成本压低=朝
    "鼓励拿 gem 攒攻"的对方向。
  · 阶段1 cost_cells = 获取怪集 − planned − M(③ 扣必经)。

红线(玩家钉死)：这是 A* 启发式正当行为·非 κ 潜力加分病(已兑现价值仍只在 hp/atk/def·
  Φ 只估剩余路线损失引导方向)。Φ 老实扣绕路 HP·rollout HP≤0 该路线 Φ=BIG。当 beam_score_fn·
  守 beam 47 零回归(solver/quotient.py、solver/beam.py 一字未动)。
  score = hp − Φ_smart + key_credit(mult=1·§S43 源码 HP 当量)。

用法：
  自检+小验证(全段跑前【必过】，没过停报玩家)：
    python -u analysis/smart_phi_s53_beam.py --phi-only
  全段跑(无人值守·写独立输出文件)：
    python -u analysis/smart_phi_s53_beam.py --beam-k 800 --max-states 1800000 \
        --out analysis/_s53_smartphi_k800.txt
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# §S52 Φ building blocks(零改动 import)
from analysis.route_aware_phi_probe import (                       # noqa: E402
    enumerate_attr_items, enumerate_monster_cells, _is_cleared,
    cleared_monster_cells, precompute_item_cost, compute_must_cells, fmt_vec,
)
# §S42 全段 building blocks(铁盾起点/段步进/红钥格/损血/h5route 导出·复用自检过的导出器)
from analysis.dir2_redkey_pathloss_beam import (                   # noqa: E402
    TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS, _monster_loss, make_seg_step,
    replay_to_token, fmt, export_halfway_h5route, export_h5route,
)
from sim.simulator import step, _build_monster, _copy_state        # noqa: E402
from solver.quotient import search_quotient                        # noqa: E402
from vzone import build_zone                                       # noqa: E402

# ── 钥匙 HP 当量(源码坐实·shops.json·§S43)：1金=2血 / 黄=20 / 蓝=100 / 红=1600 ──
KEY_HP = {"yellowKey": 20, "blueKey": 100, "redKey": 1600}

# ── fly 魔杖跨层属性(canFlyTo/canFlyFrom·排 MT0/MT44/MT50)·enable_fly=True 时注入 search_quotient ──
#    扩 beam 视野=飞回低层(如 MT1)拿漏拿资源。源码坐实·dir2_keyscarcity_beam 同款加载。
FLY_ATTRS = json.loads(
    (ROOT / "data" / "games51" / "fly_attrs.json").read_text(encoding="utf-8"))["floors"]

# 一区 boss / 红钥门守卫 / MT10 红宝石(数据坐实·_s53_data_probe.py 校验)
BOSS_ID = "skeletonCaptain"      # MT10(6,4)·红钥门后伏击·DEF27 下 ATK26→27 损血 342→304
GUARD_ID = "yellowGuard"         # MT8 红钥门守卫·DEF27 下 ATK26→27 损血 252→189
REDGEM_CELL = ("MT10", 10, 6)    # +1 atk·黄门后(段内够得到)·去 boss 必经路上额外成本小
# boss-leg：过红钥(MT8)后到 boss 必经跨的层。其全怪做【保守过近似】必经集(含伏击+boss)。
BOSS_LEG_FLOORS = ["MT9", "MT10"]


def key_credit(hero, mult):
    """持钥 HP 当量信用(§S43)：Σ 持钥 × 源码 HP 当量 × mult。mult=0 → 0。"""
    if mult == 0:
        return 0
    return sum(hero.keys.get(c, 0) * KEY_HP[c] for c in KEY_HP) * mult


def boost_for_nav(state):
    """影子英雄(只为 navigate 找【路线几何】=哪些怪在路上·非真打)：属性/钥匙拉满 →
    navigate 不被【打不动守卫(ATK22 vs def22=0 伤害)/没钥开门】卡住·能穿全段找出获取/必经怪集。
    ★真损血仍由 _monster_loss 按【在线演化的真实属性】算·boost 只决定 WHICH 怪在路线上·不伪造损血。"""
    s = _copy_state(state)
    h = s.hero
    h.atk += 100000
    h.def_ += 100000
    h.mdef += 100000
    for c in ("yellowKey", "blueKey", "redKey"):
        h.keys[c] = h.keys.get(c, 0) + 999
    return s


def build_phi_s53(start, floors, goal, zone, max_pops, boss_leg_floors):
    """组装 §S53 route-aware cost-to-go Φ(state)→phi_loss。返回 (phi_loss, diag)。

    与 §S52 build_phi 同骨架，三处改动：
      · phi_route(必经集 M·含 boss) 替 phi_static(全段怪)。
      · M = leg1(段起点→红钥) ∪ boss-leg 全怪(②延伸到 boss)。
      · cost_cells 多扣 M(③扣必经)。
    """
    items = enumerate_attr_items(start, floors)
    mon_cells = enumerate_monster_cells(start, floors)
    mons = {c: _build_monster(start, mid) for c, mid in mon_cells.items()}
    mdef0 = start.hero.mdef
    # ★navigate 用 boost 影子英雄(找路线几何·不被打不动守卫/缺钥卡死)·真损血另算(在线真属性)。
    nav_hero = boost_for_nav(start)
    item_precost = precompute_item_cost(nav_hero, items, mon_cells, zone, max_pops)

    # ── 必经集 M：leg1(导航段起点→红钥·含红钥门守卫) ∪ boss-leg(MT9+MT10 全怪·过近似伏击+boss)
    #    ∪ 红钥门守卫(显式必经安全网·守卫定义上必经红钥·防 leg1 漏穿) ──
    must_leg1 = compute_must_cells(nav_hero, goal, mon_cells, zone, max_pops)
    boss_leg = frozenset(c for c in mon_cells if c[0] in boss_leg_floors)
    guard_cells = frozenset(c for c, mid in mon_cells.items() if mid == GUARD_ID)
    must_cells = must_leg1 | boss_leg | guard_cells

    @lru_cache(maxsize=None)
    def loss_one(a, d, cell):
        return _monster_loss(a, d, mons[cell], mdef0)

    @lru_cache(maxsize=None)
    def phi_route(a, d):
        """必经集 M 损血和(route-aware·含 boss/伏击/守卫)。gem gain 用其差分 → 自然含 boss 减伤。"""
        return sum(_monster_loss(a, d, mons[c], mdef0) for c in must_cells)

    def phi_loss(state, trace=None):
        h = state.hero
        a, d = h.atk, h.def_
        planned = set(cleared_monster_cells(state, mon_cells))
        planned_items = {i for i, it in enumerate(items)
                         if _is_cleared(state, (it[0], it[1], it[2]))}
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
                gain = phi_route(a, d) - phi_route(na, nd)
                cost_cells = pc - planned - must_cells       # §S53 ③ 扣必经
                cost = sum(loss_one(a, d, c) for c in cost_cells)
                net = gain - cost
                if net > best_net:
                    best_net, best = net, (i, cost, cost_cells, stat, delta, gain)
            if best is None:
                break
            i, cost, cost_cells, stat, delta, gain = best
            total += cost
            if stat == "atk":
                a += delta
            else:
                d += delta
            planned |= cost_cells
            planned_items.add(i)
            if trace is not None:
                it = items[i]
                trace.append(dict(i=i, cell=(it[0], it[1], it[2]), iid=it[3],
                                  stat=stat, delta=delta, gain=gain, cost=cost,
                                  net=gain - cost, extra=len(cost_cells),
                                  a_after=a, d_after=d))
        # ── 阶段2：用攒够的属性打必经怪 M(到 boss·非截红钥) ──
        for c in must_cells - planned:
            total += loss_one(a, d, c)
        return total

    diag = dict(items=items, mon_cells=mon_cells, mons=mons, item_precost=item_precost,
                must_leg1=must_leg1, boss_leg=boss_leg, must_cells=must_cells,
                phi_route=phi_route, loss_one=loss_one, phi_loss=phi_loss, mdef0=mdef0)
    return phi_loss, diag


# ══════════════════════════ 自检 + 小验证 ══════════════════════════
def cat_cells(mon_cells, mid):
    return frozenset(c for c, m in mon_cells.items() if m == mid)


def self_check(start, diag, score_fn):
    """§S53 Φ 自检：确认 ①gem 含 boss 减伤(342→304) ②扣必经 ③cost-to-go 到 boss(没截红钥)。
    返回 ok(bool)·任一硬性事实不成立 → False(全段跑前停)。"""
    mon_cells = diag["mon_cells"]
    must_cells = diag["must_cells"]
    items = diag["items"]
    item_precost = diag["item_precost"]
    phi_route = diag["phi_route"]
    loss_one = diag["loss_one"]
    boss_cells = cat_cells(mon_cells, BOSS_ID)
    guard_cells = cat_cells(mon_cells, GUARD_ID)
    ok = True

    print("\n" + "═" * 84)
    print("【§S53 Φ 自检】(全段跑前必过·硬性事实不成立则停报玩家)")
    print("═" * 84)

    # ── 必经集 M 构成 ──
    print(f"必经集 M = leg1({len(diag['must_leg1'])}怪·导航段起点→红钥) "
          f"∪ boss-leg({len(diag['boss_leg'])}怪·{BOSS_LEG_FLOORS}全怪) = {len(must_cells)} 怪")
    boss_in = bool(boss_cells & must_cells)
    print(f"  [②cost-to-go 到 boss] boss({BOSS_ID})格={sorted(boss_cells)} ∈ M? {boss_in}  "
          f"{'✓ 没截红钥' if boss_in else '✗ 漏 boss!'}")
    if not boss_in:
        ok = False
    guard_in = guard_cells & must_cells
    print(f"  红钥门守卫({GUARD_ID})格={sorted(guard_cells)} ∈ M? {sorted(guard_in)}  "
          f"{'✓' if guard_in == guard_cells else '⚠ 部分守卫不在 M(leg1 没穿过·gem 守卫收益会少算)'}")
    if not guard_in:
        ok = False

    # ── 数据复核：boss / 守卫损血(DEF27 终态·对照 _s53_data_probe.py)──
    print("\n[数据复核] compute_combat 损血(DEF27 终态·mdef=起点)：")
    if boss_cells:
        bc = sorted(boss_cells)[0]
        b26, b27 = loss_one(26, 27, bc), loss_one(27, 27, bc)
        hit = "✓命中 342→304" if (b26, b27) == (342, 304) else "✗ 与探针不符!"
        print(f"  boss  ATK26→27 = {b26}→{b27}  (减伤 {b26 - b27})  {hit}")
        if (b26, b27) != (342, 304):
            ok = False
    if guard_cells:
        gc = sorted(guard_cells)[0]
        g26, g27 = loss_one(26, 27, gc), loss_one(27, 27, gc)
        print(f"  守卫  ATK26→27 = {g26}→{g27}  (减伤 {g26 - g27}/只 × {len(guard_cells)}只 "
              f"= {(g26 - g27) * len(guard_cells)})")

    # ── ★主键方向核实：ATK26→27 vs DEF26→27 谁对破红钥关键怪更省血(坐实"属性优先=攻优先"·
    #    字典序主键 (atk,def) atk 在前)。loss_one(a,d,cell)·固定一维动另一维。compute_combat 实算。──
    print("\n[★主键核实] 固定一维动另一维·看 ATK/DEF 哪个对关键怪更省血(坐实 atk 主键在前)：")
    for tag, cells in (("boss ", boss_cells), ("守卫 ", guard_cells)):
        if not cells:
            continue
        c = sorted(cells)[0]
        d_atk = loss_one(26, 27, c) - loss_one(27, 27, c)   # ATK26→27·DEF 固定 27
        d_def = loss_one(26, 26, c) - loss_one(26, 27, c)   # DEF26→27·ATK 固定 26
        n = len(cells)
        verdict = "→ ATK 更关键(atk 主键在前✓)" if d_atk >= d_def else "→ DEF 更关键(⚠ 主键顺序存疑)"
        print(f"  {tag}({n}只): ATK26→27 省 {d_atk}/只  vs  DEF26→27 省 {d_def}/只  {verdict}")

    # ── ①gem 含 boss 减伤：红宝石在 boss 临界(ATK26→27·DEF27)的 gain 分解 ──
    print("\n[①gem 含 boss 减伤] MT10 红宝石(+1atk)在 boss 临界 ATK26→27 / DEF27 的 gain 分解：")
    redgem_idx = next((i for i, it in enumerate(items)
                       if (it[0], it[1], it[2]) == REDGEM_CELL), None)
    if redgem_idx is None:
        print(f"  ✗ 没在段内属性道具里找到 MT10 红宝石 {REDGEM_CELL}!")
        ok = False
    else:
        pc = item_precost[redgem_idx]
        gain_total = phi_route(26, 27) - phi_route(27, 27)          # M 全体在该步的减伤
        boss_contrib = sum(loss_one(26, 27, c) - loss_one(27, 27, c) for c in boss_cells)
        guard_contrib = sum(loss_one(26, 27, c) - loss_one(27, 27, c) for c in guard_cells)
        print(f"  红宝石 {REDGEM_CELL} 获取怪集 = {'够不到(None)' if pc is None else str(len(pc)) + '怪'}")
        print(f"  gain(M 全体减伤·phi_route 差分) = {gain_total}")
        print(f"    ├ 含 boss 减伤  = {boss_contrib}   {'✓ 算进去了(≠0)' if boss_contrib else '✗ boss 没贡献(=0·漏了!)'}")
        print(f"    ├ 含守卫减伤    = {guard_contrib}")
        print(f"    └ 含伏击/其他   = {gain_total - boss_contrib - guard_contrib}")
        print(f"  对照：§S52 路线盲(守卫 only ≈ {guard_contrib}) → §S53 多算 boss+伏击 "
              f"{gain_total - guard_contrib}(≥ boss 38)")
        if boss_contrib != 38:
            print(f"  ⚠ boss 减伤 {boss_contrib} ≠ 预期 38(342→304)·查 DEF/atk 口径")
        if pc is None:
            print("  ⚠ 红宝石获取怪集=None(navigate 段起点够不到)→ 阶段1 不会规划它→gem 价值落空!")
            ok = False

        # ── ③扣必经成本：红宝石额外成本 = 获取怪集 − M ──
        if pc is not None:
            extra = pc - must_cells
            a0, d0 = start.hero.atk, start.hero.def_
            cost_raw = sum(loss_one(a0, d0, c) for c in pc)
            cost_extra = sum(loss_one(a0, d0, c) for c in extra)
            print(f"\n[③扣必经成本] 红宝石获取怪集 {len(pc)} 怪@({a0},{d0}) 原始损血={cost_raw}")
            print(f"  扣必经 M 后额外怪 = {len(extra)} 怪·额外损血 = {cost_extra}  "
                  f"(扣掉 {len(pc) - len(extra)} 只必经怪·省 {cost_raw - cost_extra})")

    # ── 阶段1 规划 trace：Φ 到底规划拿哪些 gem(看红宝石入没入选)──
    print("\n[Φ 阶段1 规划 trace] 从起点 state 跑贪心烧血换属性：")
    trace = []
    phi0 = diag["phi_loss"](start, trace=trace)
    if not trace:
        print("  (起点未规划任何 gem·阶段1 没正 net 项)")
    for t in trace:
        flag = " ←★MT10红宝石" if t["cell"] == REDGEM_CELL else ""
        print(f"  规划 {t['cell']} {t['iid']} {t['stat']}+{t['delta']}: "
              f"gain={t['gain']:.0f} cost={t['cost']:.0f} net={t['net']:.0f} "
              f"额外怪={t['extra']} →属性({t['a_after']},{t['d_after']}){flag}")
    redgem_planned = any(t["cell"] == REDGEM_CELL for t in trace)
    print(f"  [小验证] Φ 规划拿 MT10 红宝石? {redgem_planned}  "
          f"{'✓ Φ 给它正价值·beam 会被引去攒攻' if redgem_planned else '✗ 没规划·gem 价值未生效(查 net)'}")

    h0 = start.hero
    sk = score_fn(start)
    print(f"\n起点 Φ_loss(到 boss·非截红钥) = {phi0}  ·  字典序 score key = "
          f"(atk={sk[0]}, def={sk[1]}, hp−Φ+key={sk[2]:.0f})  (hp={h0.hp} atk={h0.atk} def={h0.def_})")
    print("═" * 84)
    print(f"自检结论：{'✓ 通过(可全段跑)' if ok else '✗ 不通过(硬性事实不成立·停·别全段跑)'}")
    print("═" * 84)
    return ok


# ══════════════════════════ 全段 beam ══════════════════════════
def run_full(start, goal, allowed, beam_k, max_states, score_fn, diag, enable_fly=False):
    seg_step = make_seg_step(allowed)
    redgem_cell = REDGEM_CELL
    mon_cells = diag["mon_cells"]

    # 字典序 score 哨兵(元组·比任何真 score key 小)：init 必须是元组·否则 max(int,tuple)/(tuple>int) 崩
    NEG = (-10 ** 18, -10 ** 18, -10 ** 18)
    best = defaultdict(lambda: {"atk": 0, "def": 0, "hp": 0, "V": NEG, "n": 0})
    top = {"V": NEG, "snap": None}
    # best_acts：导 h5route 用·记【最深态(max (atk,hp))】的动作串(沿用 dir2 半截导出约定·
    #   snap 是 (floor,x,y,atk,def,hp) 元组·export_halfway 读 snap[0..5])。
    best_acts = {"key": (-1, -1), "acts": None, "snap": None}

    def on_admit(child, _acts):
        h = child.hero
        b = best[child.current_floor]
        b["n"] += 1
        b["atk"] = max(b["atk"], h.atk)
        b["def"] = max(b["def"], h.def_)
        b["hp"] = max(b["hp"], h.hp)
        v = score_fn(child)
        b["V"] = max(b["V"], v)
        if v > top["V"]:
            top["V"] = v
            top["snap"] = dict(fl=child.current_floor, x=h.x, y=h.y, atk=h.atk,
                               def_=h.def_, hp=h.hp, keys=dict(h.keys),
                               redgem=_is_cleared(child, redgem_cell))
        k = (h.atk, h.hp)
        if k > best_acts["key"]:
            best_acts["key"] = k
            best_acts["acts"] = _acts
            best_acts["snap"] = (child.current_floor, h.x, h.y, h.atk, h.def_, h.hp)

    t0 = time.time()
    res = search_quotient(start, goal, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=True,
                          beam_score_fn=score_fn, beam_diversity="stairs",
                          on_admit=on_admit,
                          enable_fly=enable_fly,
                          fly_attrs=FLY_ATTRS if enable_fly else None)
    res._secs = time.time() - t0
    res._best_by_floor = dict(best)
    res._top = top
    res._best_acts = best_acts
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beam-k", type=int, default=800)
    ap.add_argument("--max-states", type=int, default=1_800_000)
    ap.add_argument("--mult", type=float, default=1.0, help="钥匙 HP 当量乘子(§S43·玩家定 mult=1)")
    ap.add_argument("--nav-maxpops", type=int, default=12000)
    ap.add_argument("--enable-fly", action="store_true",
                    help="开 fly 魔杖跨层边(方案B保守子集·扩视野飞回低层拿漏拿资源·如 MT1)；"
                         "默认关=老路指纹不变零回归")
    ap.add_argument("--phi-only", action="store_true",
                    help="只自检+小验证·不跑 beam(全段跑前必过)")
    ap.add_argument("--out", type=str, default="",
                    help="输出文件(python 直写 utf-8·行缓冲)·供无人值守后台·绕 shell 编码坑")
    args = ap.parse_args()
    if args.out:
        sys.stdout = open(args.out, "w", encoding="utf-8", buffering=1)

    floors, goal = REAL_LEG_FLOORS, REDKEY_CELL
    print("=" * 84)
    print("§S53 更聪明Φ route-aware cost-to-go 到 boss(非截红钥) · 无人值守")
    print("=" * 84)
    print(f"段楼层={floors}  目标红钥格={goal}  boss-leg(过近似必经)={BOSS_LEG_FLOORS}")
    print(f"钥匙 HP 当量(源码)：黄{KEY_HP['yellowKey']} 蓝{KEY_HP['blueKey']} 红{KEY_HP['redKey']}  "
          f"mult={args.mult}")
    print(f"score = hp − Φ_smart(route-aware·含 boss) + key_credit(持钥×当量×mult)")

    t0 = time.time()
    zone = build_zone()
    print(f"build_zone 就绪 {time.time() - t0:.1f}s", flush=True)

    start = replay_to_token(TOK_SHIELD)
    assert start._single_floor_copy is False, "起点须跨层安全深拷(_single_floor_copy=False)"
    print(f"铁盾起点 tok{TOK_SHIELD}: {fmt(start)}", flush=True)

    t1 = time.time()
    phi_loss, diag = build_phi_s53(start, floors, goal, zone, args.nav_maxpops, BOSS_LEG_FLOORS)
    print(f"build_phi_s53(预计算 precost+M) 就绪 {time.time() - t1:.1f}s", flush=True)

    # ── §S55 字典序属性优先 score_fn（候选1·玩家拍板·换掉 §S54 的 hp−Φ 线性相减形式）─────
    #   返回【元组】(atk, def_, hp−Φ+key_credit)。beam_select 只把 score_fn 当排序/max 键
    #   (solver/beam.py:384/432/440 sort/max·全程不做算术)→ Python 元组逐位比较 = 天然字典序·
    #   零魔法数权重(守铁律·没有 atk:def:hp 的任何兑换率)。
    #   主键 atk：治预 credit——看当前【真实】atk(atk24 严格排 atk25 后)·不被 Φ 阶段1 预 credit
    #     未来 gem 骗(那个 bug 只动 Φ·动不了真 atk)→ beam 有动力真去拿第 5 颗 gem 把 atk 变 27。
    #   次键 def：属性优先含防御(atk 同看 def)。
    #   末键 hp−Φ+key_credit：沿用 §S53 自检过的 route-aware 分·同 (atk,def) 时引导"往红钥门推"
    #     (Φ 小=去红钥路上的态排前·§S53 第二目标)。Φ 降为末键后·预 credit 只影响【同属性】态·无害。
    #   ★末键残留观察点(handoff §S54)：hp−Φ 仍是线性相减(囤血态 hp 高排前)·但锁在【同(atk,def)】内·
    #     若实测同属性还囤血不推门 → 把末键换"先进度(离红钥近)再 hp"。先用 hp−Φ(复用现成·最不翻车)。
    def score_fn(state):
        h = state.hero
        return (h.atk, h.def_, h.hp - phi_loss(state) + key_credit(h, args.mult))

    ok = self_check(start, diag, score_fn)
    if not ok:
        print("\n🛑 自检不通过 → 停(别带着错的 Φ 全段跑一夜)。请玩家看上面 ✗ 项。")
        return
    if args.phi_only:
        print("\n(--phi-only：自检+小验证完·未跑 beam。通过后去掉 --phi-only 全段跑。)")
        return

    # ── 全段 beam ──
    print("\n" + "=" * 84)
    print(f"■ 全段 beam：beam_k={args.beam_k}  max_states={args.max_states}  "
          f"fly={'★开(飞回低层拿漏拿资源·如MT1)' if args.enable_fly else '关(老路)'}")
    print("=" * 84, flush=True)
    res = run_full(start, goal, floors, args.beam_k, args.max_states, score_fn, diag,
                   enable_fly=args.enable_fly)

    print(f"\n found={res.found}  耗时={res._secs:.1f}s  hit_cap={res.hit_cap}")
    print(f" expanded={res.states_expanded} generated={res.states_generated} "
          f"distinct_fp={res.distinct_fingerprints} waves={res.n_waves} goal_hits={res.goal_hits}")
    print("\n ── 各层【到达过】最优属性(on_admit)──")
    for f in sorted(res._best_by_floor, key=lambda x: int(x[2:])):
        b = res._best_by_floor[f]
        bv = b['V']
        bv_s = f"(atk{bv[0]},def{bv[1]},{bv[2]:.0f})" if isinstance(bv, tuple) else f"{bv:.0f}"
        print(f"   {f:>5}: n={b['n']:>8}  maxATK={b['atk']}  maxDEF={b['def']}  "
              f"maxHP={b['hp']}  bestV={bv_s}")
    maxatk = max((b["atk"] for b in res._best_by_floor.values()), default=0)
    maxhp = max((b["hp"] for b in res._best_by_floor.values()), default=0)
    print(f"\n ★maxATK(全段)={maxatk}  maxHP(全段)={maxhp}  "
          f"(§S42/S43 基线=ATK25·破 25: {'★破了' if maxatk > 25 else '没破'}; "
          f"目标 ATK27: {'★到了' if maxatk >= 27 else '没到'})")

    sn = res._top["snap"]
    if sn:
        print(f"\n ── beam 最优态(score 最大)──")
        print(f"   位置={sn['fl']}({sn['x']},{sn['y']})  ATK={sn['atk']} DEF={sn['def_']} "
              f"HP={sn['hp']}  钥={sn['keys']}")
        print(f"   有没有拿 MT10 红宝石(redGem 格已清)? {sn['redgem']}")
    print(f"\n ── 玩家关心结论 ──")
    print(f"   found 红钥 = {res.found}  ({'★走到红钥格' if res.found else '没走到红钥'})")
    print(f"   maxATK = {maxatk}  (boss 临界 ATK27·gem 价值生效则应 ≥27)")
    print(f"   拿 MT10 红宝石 = {sn['redgem'] if sn else 'n/a'}")
    print(f"   hit_cap = {res.hit_cap}  ({'⚠ 撞预算上限·没跑完·加 max_states' if res.hit_cap else '✓ 跑透了'})")
    print("=" * 84)

    # ── 导 h5route(给玩家网站回放)·复用 dir2 自检过的导出器(前缀 tokens[:455] + beam RULD + sim 独立重放自检)──
    export_tag = f"s53_smartphi_k{args.beam_k}{'_fly' if args.enable_fly else ''}"
    if res.found:
        export_h5route(res, export_tag)
    else:
        export_halfway_h5route(res._best_acts, export_tag)


if __name__ == "__main__":
    main()
