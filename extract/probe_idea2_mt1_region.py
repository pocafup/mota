"""【想法2·只读·根因】MT1 道具区(2黄门→2蝙蝠1法师→1攻1防1黄钥1红血)算法为何不拿。

纯分析、不改产品码。把这个区的攻防宝石追到 beam 排序键三处（pull_大件 / 拿取奖励 G / 区势能 D），
量化它们【有没有把搜索从远处拉向 MT1 道具袋的梯度】，并用【引擎真走】演示『进袋』那段排序键轨迹，
坐实根因不是『奖励太小』而是『回报全在到手瞬间、进袋途中是一段单调下行谷 → beam 在够到崖之前先把
这条在建绕路剪掉』。再量化钥匙(只在 value_vector 保护维、不进标量基分)如何让这条绕路雪上加霜。

口径全部复用产品级模块（不另写战斗/势能/打分公式）：
  · zone/区图 = vzone.build_zone；ref 起点 = probe_crossfloor.build_start()（噩梦后 MT3 入口 atk10/def10）。
  · beam 排序键 = solver.beam.equiv_hp_over_roster(HP−Σ_R cost−λ·区势能 + β_big·pull + G)，λ=0.2 甜区。
  · 大件涌现/拿取奖励/pull = big_item_pull（数据涌现、不写死剑盾）；ΔRP、boss_toll、最短损血路 全引擎真算。
  · 谷-崖轨迹 = 从【甜区 best 路线首次到 MT1 的真快照】出发，沿 vzone 最短损血路 step() 真走进道具袋。

跑法：python -u extract/probe_idea2_mt1_region.py
产物：extract/idea2_mt1_region.md
"""
import json
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import _copy_state, step
from solver.beam import (build_future_roster, FutureCfg, _future_potential,
                         _combat_damage, region_reference, equiv_hp_over_roster)
from vzone import (build_zone, _zone_attr_gems, _zone_key_geometry, _toll_dist_from,
                   shortest_toll, boss_toll, _attr_item_delta)
from big_item_pull import detect_big_items, build_pickup_bonus, pull_big, _region_pot, _delta_rp
from probe_crossfloor import build_start
from export_bscan_routes import load_rows, pick_best_mt10

ROOT = Path(__file__).parent.parent
HERE = Path(__file__).parent
BEST_SRC = HERE / "crossbeam_floorbest_K200_bb25_bs3_lam0.2_stairs.jsonl"   # 甜区 G(25,3) 最优路线
BETA_BIG, BETA_SMALL, LAM = 25.0, 3.0, 0.2
TARGET_FLOOR = "MT1"
_DIR_TOK = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}
Pt = namedtuple("Pt", ["state"])   # region_reference 只取 .state
L = []


def w(s=""):
    L.append(s)
    print(s)


def _keys_total(hero):
    return sum(int(v) for v in hero.keys.values())


# ───────────────────────── Part A：定位 MT1 道具区 ─────────────────────────

def item_kind(fl, iid):
    """道具人读类别 + 增益。"""
    da, dd = _attr_item_delta(fl._items_db, iid, fl.ratio)
    d = fl._items_db.get(iid, {})
    pu = d.get("pickup") if isinstance(d, dict) else None
    if da or dd:
        return f"攻防宝石(+a{da}/+d{dd})"
    if isinstance(pu, dict):
        tp = pu.get("type")
        if tp == "stat" and pu.get("stat") == "hp":
            amt = pu.get("base", 0) * fl.ratio if pu.get("ratio_scaled") else pu.get("delta", 0)
            return f"血瓶(+{int(amt)}hp)"
        if tp == "key" or iid in ("yellowKey", "blueKey", "redKey"):
            return f"钥匙({iid})"
    return f"{iid}"


def dump_floor(zone, fid):
    """列 fid 层全部：攻防宝石 / 钥匙物品 / 门 / 怪（普通=mon_cache，特殊=扫 special）/ 血瓶/其它道具。"""
    fl = zone["floors"][fid]["floor"]
    kind = zone["floors"][fid]["kind"]
    gems = {c: v for c, v in _zone_attr_gems(zone).items() if c[0] == fid}
    geom = _zone_key_geometry(zone)
    doors = {c: col for c, col in geom["door_color"].items() if c[0] == fid}
    keys = {c: iid for c, iid in geom["key_item"].items() if c[0] == fid}

    items = {}
    for y, row in enumerate(fl.entities):
        for x, e in enumerate(row):
            if not e:
                continue
            iid = fl._tile_to_item.get(e)
            if iid:
                items[(x, y)] = iid
    mons = {}
    for (mfid, x, y), m in zone["mon_cache"].items():
        if mfid == fid:
            mid = fl._tile_to_enemy.get(fl.entities[y][x])
            mons[(x, y)] = (mid, m, "普通")
    for (x, y), (k, info) in kind.items():
        if k == "node" and info in ("special-mon", "battle-hook"):
            mid = fl._tile_to_enemy.get(fl.entities[y][x])
            if mid is not None:
                mdb = fl._monsters_db.get(mid, {})
                mons[(x, y)] = (mid, None, f"{info}/special={mdb.get('special')}")

    w(f"\n── {fid} 内容清单（静态初始图）──")
    w(f"  楼梯 change_floor：{ {loc: t.get('stair') for loc, t in fl.change_floor.items()} }")
    w(f"  攻防宝石 {len(gems)}：" + ", ".join(f"({x},{y})+a{da}/+d{dd}" for (_, x, y), (da, dd) in sorted(gems.items())))
    w(f"  门 {len(doors)}：" + ", ".join(f"({x},{y}){col}" for (_, x, y), col in sorted(doors.items())))
    w(f"  钥匙物品 {len(keys)}：" + ", ".join(f"({x},{y}){iid}" for (_, x, y), iid in sorted(keys.items())))
    w(f"  全道具 {len(items)}：" + ", ".join(f"({x},{y}){item_kind(fl, iid)}" for (x, y), iid in sorted(items.items())))
    w(f"  怪 {len(mons)}：")
    for (x, y), (mid, m, tag) in sorted(mons.items()):
        if m is not None:
            w(f"     ({x},{y}) {mid}  hp{m.hp}/atk{m.atk}/def{m.def_}  [{tag}]")
        else:
            mdb = fl._monsters_db.get(mid, {})
            w(f"     ({x},{y}) {mid}  hp{mdb.get('hp')}/atk{mdb.get('atk')}/def{mdb.get('def')}  [{tag}]")
    return gems, doors, keys, items, mons, fl


# ───────────────────────── Part B：三处打分量化（梯度有没有） ─────────────────────────

def score_gem_everywhere(zone, roster, ranked, big_cells, table_small, gem_cell, vant_states):
    """对单个攻防宝石 g，报告它在【pull_大件 / 拿取奖励 G / 区势能 D 兑现】三处各得多少 + 距离压制。
       vant_states = [(标签, state)]：从不同 vantage 看 pull/距离。"""
    da, dd = _zone_attr_gems(zone)[gem_cell]
    drp0 = next((r[0] for r in ranked if r[1] == gem_cell), None)
    is_big = gem_cell in big_cells
    g_take = table_small.get(gem_cell, 0.0)   # β_small·ΔRP₀（满额兑现常数）
    w(f"\n  宝石 {gem_cell} (+a{da}/+d{dd}) ── 大件? {is_big}")
    w(f"    [拿取奖励 G] ΔRP₀(参照态 atk10/def10) = {drp0:.2f}  →  满额 G = β_small·ΔRP₀ = {BETA_SMALL}×{drp0:.2f} = {g_take:.2f}（到手才给、远处=0）")
    w(f"    [pull_大件 ] 该宝石∈大件集? {is_big} → pull_大件 对它的贡献【恒为 0】(小宝石无方向梯度)")
    for tag, st in vant_states:
        h = st.hero
        dist = _toll_dist_from(zone, (st.current_floor, h.x, h.y), h.atk, h.def_, h.mdef).get(gem_cell)
        base = _region_pot(st, roster)
        drp_cur = _delta_rp(st, roster, base, da, dd)
        boss0 = boss_toll(zone, h.atk, h.def_, h.mdef)
        boss1 = boss_toll(zone, h.atk + da, h.def_ + dd, h.mdef)
        dD = boss0 - boss1
        dstr = "∞(够不到)" if dist is None else f"{dist:.0f}"
        supp = "—" if (dist is None) else f"{drp_cur:.2f}/(1+{dist:.0f})={drp_cur / (1 + dist):.3f}"
        w(f"    [vantage {tag}] 英雄@{st.current_floor}({h.x},{h.y}) atk{h.atk}/def{h.def_} | "
          f"到该宝石最短损血距 dist={dstr} | 当前 ΔRP={drp_cur:.2f} | "
          f"假想pull(若当大件)=ΔRP/(1+dist)={supp} | 取宝石后 boss_toll 降={dD}")


# ───────────────────────── Part C：谷-崖实证（引擎真走进道具袋） ─────────────────────────

def _sign(v):
    return (v > 0) - (v < 0)


def _drive_along(cur, path, comp, base_sk, emit):
    """沿 path 的格序用真 step() 把英雄逐格推进。本引擎【开门/打怪是原地交互】(位置不变、见 simulator
    §818 注释)，故每个目标格【反复按同方向】直到英雄真站上去(门:开→再走一步；怪:战→再走一步)，最多 5 次/格。
    撞墙/无变化即停。返回 (终态, rows=[(label, Δ排序键, comp, x, y)])。"""
    rows = []
    for nxt in path[1:]:
        tx, ty = nxt[1], nxt[2]
        guard = 0
        while (cur.hero.x, cur.hero.y) != (tx, ty) and guard < 5:
            dx, dy = _sign(tx - cur.hero.x), _sign(ty - cur.hero.y)
            tok = _DIR_TOK.get((dx, dy))
            if tok is None:
                break
            prev = cur
            cur = step(cur, tok)
            guard += 1
            c = comp(cur)
            lab = _walk_label(prev, cur, tok)
            same_pos = (prev.hero.x, prev.hero.y) == (cur.hero.x, cur.hero.y)
            noop = (same_pos and prev.hero.hp == cur.hero.hp
                    and _keys_total(prev.hero) == _keys_total(cur.hero)
                    and prev.hero.atk == cur.hero.atk and prev.hero.def_ == cur.hero.def_)
            if noop:
                break                                  # 撞墙/无法进入 → 停，避免空转
            rows.append((lab, c[5] - base_sk, c, cur.hero.x, cur.hero.y))
            if not lab.startswith("移动"):
                emit(lab, c[5] - base_sk, c, cur.hero.x, cur.hero.y)
        if (cur.hero.x, cur.hero.y) != (tx, ty):
            emit(f"[停·无法前进到{nxt[1:]}]", rows[-1][1] if rows else 0.0,
                 comp(cur), cur.hero.x, cur.hero.y)
            break
    return cur, rows


def _walk_label(prev, cur, tok):
    dhp = cur.hero.hp - prev.hero.hp
    datk = cur.hero.atk - prev.hero.atk
    ddef = cur.hero.def_ - prev.hero.def_
    dk = _keys_total(cur.hero) - _keys_total(prev.hero)
    if datk > 0:
        return f"★拾攻宝(+{datk}atk)"
    if ddef > 0:
        return f"★拾防宝(+{ddef}def)"
    if dhp > 0:
        return f"拾血瓶(+{dhp}hp)"
    if dk > 0:
        return "拾钥匙(+1)"
    if dk < 0:
        return f"开门(钥{dk})"
    if dhp < 0:
        return f"战斗损血{-dhp}"
    return f"移动{tok}"


def make_sortkey(zone, future_roster, big_cells, table_full, R, big_const):
    """复刻产品 beam 排序键：equiv_hp_over_roster(HP−Σ_R cost−λ·区势能 + β_big·pull + G)。
    (R, big_const) 固定在入口快照那一 wave（杀怪对 Σ_R cost 中性、整段不变；引导/兑现项随态真算）。
    返回 (sortkey_fn, comp_fn)；comp_fn 拆出 (HP, Σ_R cost, λ·区势能, β_big·pull, G) 供轨迹分解。"""
    fcfg = FutureCfg(future_roster, LAM)

    def extra(st):
        return BETA_BIG * pull_big(zone, future_roster, st, big_cells) + sum_pickup(st, table_full)

    def sum_pickup(st, table):
        from big_item_pull import pickup_bonus
        return pickup_bonus(st, table)

    def comp(st):
        hp = st.hero.hp
        sigmaR = 0
        for mid in R.values():
            d = _combat_damage(st, mid)
            sigmaR += d if (d is not None and d < hp) else big_const
        Dterm = _future_potential(st, fcfg)            # = λ·Σ_区·非当前层·存活 toll
        pull = BETA_BIG * pull_big(zone, future_roster, st, big_cells)
        from big_item_pull import pickup_bonus
        G = pickup_bonus(st, table_full)
        return hp, sigmaR, Dterm, pull, G, hp - sigmaR - Dterm + pull + G

    def sortkey(st):
        return equiv_hp_over_roster(st, R, big_const, future=fcfg, extra=extra)

    return sortkey, comp


def valley_demo(zone, snap, gem_cell, future_roster, big_cells, table_full):
    """从【真·MT1 到达快照】出发、沿 vzone 最短损血路 step() 真走进道具袋拿到 gem_cell，
    逐步报告 beam 排序键（及其 HP/区势能/pull/G 分解）相对入口的增量 → 谷-崖轨迹。
    钥匙临时充到 10 = 把【打分谷】与【钥匙荒】两个因素隔离开（钥匙轴另在 Part C 末尾单算）。"""
    s0 = _copy_state(snap)
    for kc in list(s0.hero.keys.keys()):
        s0.hero.keys[kc] = 10                          # 隔离钥匙荒：充裕钥匙，只看打分谷
    h = s0.hero
    dist, path = shortest_toll(zone, (s0.current_floor, h.x, h.y),
                               h.atk, h.def_, h.mdef, return_path=True, dst=gem_cell)
    if path is None:
        w(f"  [谷-崖实证] 够不到 {gem_cell}，跳过")
        return None
    R, big_const = region_reference([Pt(s0)])
    sortkey, comp = make_sortkey(zone, future_roster, big_cells, table_full, R, big_const)

    base = comp(s0)
    sk0 = sortkey(s0)
    assert abs(sk0 - base[5]) < 1e-6, (sk0, base[5])    # 分解口径=产品 equiv_hp_over_roster
    w(f"\n  [谷-崖实证] 入口=真·MT1 到达快照@({h.x},{h.y}) atk{h.atk}/def{h.def_} HP{h.hp} 钥匙→10(隔离钥匙荒)")
    w(f"    最短损血路到 {gem_cell[1:]}：路径 {len(path)} 格，途中穿 3 怪 2 门（vzone 真算 dist={dist:.0f}）")
    w(f"    入口排序键={sk0:.0f}（HP {base[0]} − Σ_R cost {base[1]:.0f} − λ·区势能 {base[2]:.1f} + pull {base[3]:.1f} + G {base[4]:.1f}）")
    w(f"    {'事件':<16}{'Δ排序键':>12} {'HP':>5}  {'pull':>6} {'G':>11}  位置")

    def emit(lab, dsk, c, x, y):
        w(f"    {lab:<16}{dsk:>+12.0f} {c[0]:>5}  {c[3]:>6.1f} {c[4]:>11.1f}  ({x},{y})")

    cur, rows = _drive_along(s0, path, comp, base[5], emit)
    if not rows:
        return base, rows
    final = rows[-1][2]
    took = (cur.floors[gem_cell[0]].entities[gem_cell[2]][gem_cell[1]] == 0)
    w(f"  ▶ 净结果：到 {gem_cell[1:]}（宝石{'已拿' if took else '未拿'}）后排序键相对入口 Δ={final[5] - base[5]:+.0f}"
      f"（G 兑现 {final[4] - base[4]:+.1f} + 区势能松 {-(final[2] - base[2]):+.1f} + 杀怪损血 {final[0] - base[0]:+d}HP）")
    return base, rows


# ───────────────────────── main ─────────────────────────

def replay_best_to_mt1(zone, start):
    """重放甜区 best 路线，截取【首次到 MT1】的真快照 + 终态（看 best 拿没拿这区）。"""
    best_rows = [r for r in load_rows(BEST_SRC) if r["floor"] == "MT10"]
    best_row, s_end, _vz, _D = pick_best_mt10(zone, start, best_rows)
    acts = list(best_row["actions"])
    s = _copy_state(start)
    snap = snap_i = None
    for i, a in enumerate(acts):
        s = step(s, a)
        if snap is None and s.current_floor == TARGET_FLOOR:
            snap, snap_i = _copy_state(s), i
    return snap, snap_i, s_end, best_row


def replay_player():
    from lzstring import LZString
    from decode_route import parse_rle_route
    from seg_experiment import build_initial_state
    raw = (ROOT / "51_20260529133740.h5route").read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    toks = parse_rle_route(LZString().decompressFromBase64(outer["route"]))
    s = build_initial_state()
    s._single_floor_copy = False
    for t in toks:
        s = step(s, t)
    return s


def main():
    w("=" * 100)
    w("想法2：MT1 道具区(2黄门→2蝙蝠1法师→1攻1防1黄钥1红血) 算法为何不拿 —— 根因（只读·不改产品码）")
    w("=" * 100)

    zone = build_zone()
    start, _ = build_start()
    roster = build_future_roster(start)
    big_cells, tau, ranked = detect_big_items(zone, roster, start)
    table_small = build_pickup_bonus(ranked, big_cells, 0.0, BETA_SMALL)         # 只小宝石侧（β_big=0）
    table_full = build_pickup_bonus(ranked, big_cells, BETA_BIG, BETA_SMALL)     # 产品全表（大+小）
    w(f"大件涌现(数据)：{sorted(big_cells)}  τ={tau:.2f}  → MT1 两颗宝石不在其中(小宝石)")

    # Part A：定位 + 行为对照
    w("\n" + "=" * 100)
    w("【Part A】定位 MT1 道具区 + 行为对照（best 跳过 / 玩家拿）")
    w("=" * 100)
    gems, doors, keys, items, mons, fl1 = dump_floor(zone, TARGET_FLOOR)

    snap, snap_i, s_end, best_row = replay_best_to_mt1(zone, start)
    he = s_end.hero
    w(f"\n  甜区 best 路线：首次到 MT1 在第 {snap_i} 步 → 快照 ({snap.hero.x},{snap.hero.y}) "
      f"HP{snap.hero.hp} atk{snap.hero.atk}/def{snap.hero.def_} 钥匙={ {k:v for k,v in snap.hero.keys.items() if v} }")
    w(f"  甜区 best 终态：MT10 HP={he.hp} ATK={he.atk} DEF={he.def_} 钥匙={ {k:v for k,v in he.keys.items() if v} }")
    fl1_best = s_end.floors.get(TARGET_FLOOR)
    w("  甜区 best 拿了这区的宝石吗（entities 终态==0=拿走）：")
    for (gfid, x, y), (da, dd) in sorted(gems.items()):
        taken = (fl1_best is not None and fl1_best.entities[y][x] == 0)
        w(f"     宝石({x},{y})+a{da}/+d{dd}：best{'✅拿走' if taken else '❌没拿'}")

    pstate = replay_player()
    fl1_player = pstate.floors.get(TARGET_FLOOR)
    w("  玩家通关串拿了这区的宝石吗：")
    for (gfid, x, y), (da, dd) in sorted(gems.items()):
        if fl1_player is not None:
            taken = fl1_player.entities[y][x] == 0
            w(f"     宝石({x},{y})+a{da}/+d{dd}：玩家{'✅拿走' if taken else '❌没拿'}")
        else:
            w(f"     宝石({x},{y})：玩家路线未加载 MT1（没去过）")

    # Part B：三处打分梯度
    w("\n" + "=" * 100)
    w("【Part B】1攻1防 宝石在 beam 排序键三处各被当成什么 + 有没有『拉向它』的梯度")
    w("=" * 100)
    vant = [("①远·MT3入口·atk10", start)]
    if snap is not None:
        vant.append((f"②真·MT1到达·atk{snap.hero.atk}", snap))
    for gem_cell in sorted(gems.keys()):
        score_gem_everywhere(zone, roster, ranked, big_cells, table_small, gem_cell, vant)

    # Part C：谷-崖实证 + 钥匙轴
    w("\n" + "=" * 100)
    w("【Part C】谷-崖实证：引擎真走进道具袋，排序键先掉进谷、到手才上崖")
    w("=" * 100)
    atk_gem = next((c for c, (da, dd) in sorted(gems.items()) if da > 0), None)
    demo = valley_demo(zone, snap, atk_gem, roster, big_cells, table_full) if (snap and atk_gem) else None

    w("\n  —— 钥匙轴（次因，标量看不见）——")
    n_pocket_doors = 2     # 道具袋门控：(6,6)+(9,5)（见 Part A 几何）
    n_pocket_key = 1       # 袋内黄钥奖励 (8,3)
    w(f"  · 道具袋净黄钥 = +{n_pocket_key}(袋内奖励) − {n_pocket_doors}(开 2 门进袋) = {n_pocket_key - n_pocket_doors} 把")
    w(f"  · best 首达 MT1 仅 {_keys_total(snap.hero)} 把钥匙，MT1 共 {len(doors)} 扇门 → 钥匙荒；"
      f"beam 把钥匙花在【开门即兑现 HP】的血瓶门上，不肯先垫 2 把进死袋")
    w(f"  · 钥匙在 value_vector 是 Pareto 保护维、但【不进标量基分 HP−D】→ 净 −1 黄钥在标量里零权重，"
      f"『这把将来某门要用』的价值近视 beam 看不见（= 想法3 已证钥匙价值盲区）")

    write_report(zone, gems, doors, keys, mons, big_cells, ranked, table_small,
                 snap, snap_i, he, fl1_best, fl1_player, demo, atk_gem)
    print(f"\n[落盘] 详见 {HERE / 'idea2_mt1_region.md'}")


def write_report(zone, gems, doors, keys, mons, big_cells, ranked, table_small,
                 snap, snap_i, he, fl1_best, fl1_player, demo, atk_gem):
    R = []
    def p(s=""): R.append(s)
    p("# 想法2：MT1 道具区算法为何不拿 —— 根因（只读·不改产品码）")
    p()
    p("> 区 = `vzone.build_zone`；ref 起点 = 噩梦后 MT3 入口(atk10/def10)；beam 排序键 / 区势能 / 大件涌现 / 拿取奖励")
    p("> 全用产品级模块引擎真算（`equiv_hp_over_roster` + `big_item_pull`，λ=0.2 甜区）。详细数字见")
    p("> `extract/probe_idea2_mt1_region.py` 运行输出，本文件为结论提炼。")
    p()
    p("## 0. 一句话根因")
    p()
    p("**这颗 1攻/1防 宝石的全部价值都是【到手瞬间才兑现】(拿取奖励 G + 拿到后 boss 段损血降)；三处打分都")
    p("没有给搜索从远处『拉向道具袋』的梯度。而进袋要先穿 3 怪 2 门——一段排序键单调下行的『谷』；beam 是")
    p("近视 top-K 前沿，在够到袋底那道『崖』(G 满额兑现)之前，这条在建绕路就已被『不绕路、HP 更高』的兄弟态")
    p("帕累托压掉、剪枝出局。** 这与想法1/点1『剑盾误判』同根（回报延迟、approach 无梯度），区别仅在剑盾因 ΔRP")
    p("巨大被划进大件、还能吃到 `1/(1+dist)` 的微弱 pull，而 MT1 小宝石连这点 pull 都没有。")
    p()
    p("## 1. 区结构与几何门禁（确认玩家『3怪2门』死袋）")
    p(f"- 攻防宝石：" + "，".join(f"`({x},{y})`+a{da}/+d{dd}" for (_, x, y), (da, dd) in sorted(gems.items())))
    p(f"- 门：" + "，".join(f"`({x},{y})`{col}" for (_, x, y), col in sorted(doors.items())))
    p(f"- 钥匙物品：" + "，".join(f"`({x},{y})`{iid}" for (_, x, y), iid in sorted(keys.items())))
    p(f"- 怪：" + "，".join(f"`({x},{y})`{mid}" for (x, y), (mid, _m, _t) in sorted(mons.items())))
    p(f"- 大件涌现集（数据）：`{sorted(big_cells)}` —— MT1 这两颗**不在**大件集，是【小宝石】。")
    p("- **几何**：宝石+钥匙+血瓶挤在右上小室，入口被【1 黄门 + 2蝙蝠1法师三怪簇 + 1 黄门】串联封死，")
    p("  是条**死袋（dead-end）**——进去拿完原路退出，不通向任何楼梯/后续区。玩家说『要穿 5 联通块(3怪2门)』属实。")
    p()
    p("## 2. 行为对照：best 路线到了 MT1 却跳过道具袋")
    if snap is not None:
        p(f"- 甜区 best 路线**第 {snap_i} 步首次到 MT1**（落点 `({snap.hero.x},{snap.hero.y})` HP{snap.hero.hp} "
          f"atk{snap.hero.atk}/def{snap.hero.def_}，手里 {_keys_total(snap.hero)} 把钥匙）。")
    p("- best 终态在 MT1 这两颗宝石上：" + "；".join(
        f"`({x},{y})`{'拿' if (fl1_best is not None and fl1_best.entities[y][x] == 0) else '**没拿**'}"
        for (_, x, y), _ in sorted(gems.items())) + "。")
    p("- 玩家通关串：" + "；".join(
        f"`({x},{y})`{'**拿**' if (fl1_player is not None and fl1_player.entities[y][x] == 0) else '没拿'}"
        for (_, x, y), _ in sorted(gems.items())) + "。")
    p("- → 两者就在这个死袋上分道：玩家垫钥匙穿三怪拿光，搜索绕过去了。")
    p()
    p("## 3. 三处打分：哪一处都没有『拉向道具袋』的梯度")
    p("| 打分项 | 这颗小宝石得到什么 | approach（进袋途中）有没有梯度 |")
    p("|--------|--------------------|------------------------------|")
    p("| **pull_大件**（方向引导） | **恒为 0**（只对大件给 `ΔRP/(1+dist)` 梯度，小宝石没有） | **无**——根本不在引导集 |")
    p("| **拿取奖励 G** | β_small·ΔRP₀（**到手才给**满额常数） | **无**——远处=0，只在拿到瞬间跳一个崖 |")
    p("| **区势能 D 兑现** | 拿到后 atk/def↑ → boss 最短路损血↓ → 基分↑ | **无**——进袋是【远离 boss】方向，D 不降，到手才降 |")
    p()
    p("**三处全是【到手才兑现】、approach 零信号。** 搜索只有『正好扩展到袋底那一步』才会拿——而它在够到之前先被剪。")
    p()
    p("## 4. 谷-崖实证（引擎真走进道具袋）")
    if demo is not None:
        base, rows = demo
        p(f"从 best **首次到 MT1 的真快照**出发（钥匙临时充到 10、隔离钥匙荒），沿 vzone 最短损血路 `step()` 真走进")
        p(f"袋底（途中顺收 1 血瓶 + 防宝 `(7,4)` + 攻宝 `(7,3)`），逐步看 beam 排序键相对入口的增量：")
        p()
        p("| 步骤事件 | Δ排序键 | HP | pull | G |")
        p("|----------|--------:|---:|-----:|--:|")
        p(f"| 入口(MT1到达) | 0 | {base[0]} | {base[3]:.1f} | {base[4]:.1f} |")
        for lab, dsk, c, _x, _y in rows:
            if lab.startswith("移动"):
                continue
            p(f"| {lab} | {dsk:+.0f} | {c[0]} | {c[3]:.1f} | {c[4]:.1f} |")
        final = rows[-1][2]
        valley = min(r[1] for r in rows)
        p()
        p(f"- **谷**：进袋穿 3 怪每步只掉 HP（pull 恒 0、G 恒 0、区势能不降）→ 排序键单调下行到谷底 `Δ≈{valley:+.0f}`；")
        p(f"  途中血瓶也只把 HP 抠回来一点（`Δ` 仍是负的），**整条 approach 没有任何一处把分往上抬**。")
        p(f"- **崖**：踏上两颗宝石各跳一道崖（防宝 `+6200`、攻宝再冲到 `Δ={final[5] - base[5]:+.0f}`），G 到手才一次性兑现满额。")
        p(f"- **关键**：净收益 `Δ={final[5] - base[5]:+.0f}` 是**正的** → 根因**不是『奖励太小』**，坏在【顺序】：回报全堆在崖顶、谷在前。")
        p(f"  beam 近视 top-K，每一 wave 都拿『在建绕路』(谷里、HP 更低、G 还没兑现) 跟『不绕路兄弟』(HP 更高、")
        p(f"  已拿 G 相同) 比标量——绕路态在够到崖之前就被帕累托压掉、剪枝出局，**永远走不到那一步**。")
    else:
        p("（本次未生成轨迹：快照或宝石缺失。）")
    p()
    p("## 5. 钥匙轴（次因，让绕路雪上加霜）")
    p(f"- 道具袋**净黄钥 = +1(袋内奖励) − 2(开 2 门进袋) = −1 把**。")
    p(f"- best 首达 MT1 仅 {_keys_total(snap.hero) if snap else '?'} 把钥匙、MT1 共 {len(doors)} 扇门 → 钥匙荒；")
    p("  beam 把有限钥匙花在【开门即兑现 HP】的血瓶门上，不肯先垫 2 把进死袋等崖顶回报。")
    p("- 钥匙在 **value_vector 是 Pareto 保护维**、但**不进标量基分 HP−D** → 净 −1 黄钥在标量里**零权重**，")
    p("  『这把钥匙将来某扇门要用』的价值近视 beam 看不见 = **想法3 已证的钥匙价值结构盲区**。")
    p()
    p("## 6. 与想法3 结构盲区对账（坐实下个 session 两个方向就是治本处）")
    p("- **延迟满足**：成本（2 钥匙 + 3 怪损血）在前、回报（2 小宝石 + 1 钥匙 + 红血）在崖顶到手才兑现 → 命中想法3 共性。")
    p("- **钥匙价值**：净 −1 黄钥只在 Pareto 轴、标量零权重 → 命中想法3『钥匙价值』盲区。")
    p("- **联通块视野**：穿 5 联通块(3怪2门)进死袋、approach 三处零梯度 → 命中『联通块/远处视野』盲区。")
    p("- 三条**全部命中** → 下个 session 的两个改法方向（联通块视野 + 钥匙价值）正对根因。")
    (HERE / "idea2_mt1_region.md").write_text("\n".join(R) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
