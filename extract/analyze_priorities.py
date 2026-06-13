"""剑盾优先级 + MT8左下谷 诊断（只读·重放真引擎·不改产品码）。

两问（玩家 2026-06-12）：
 A. 为何"已拿剑、盾在MT9远处、小宝石在MT1-5近处"时搜索先扫小宝石、最后才拿盾？
    沿真实 bb25_gd1 路线步进，量化三项打分：pull_大件(在场折扣引导)、G(满额兑现拿取)、door_pull(门后价值)，
    定位"远盾 pull"被"近小宝石 G/door_pull"压过的量级。
 B. MT8左下(攻防宝石)算法从不去：蓝钥误判(色稀缺度) vs 门后谷(门后价值+怪墙被beam近视剪)？
    用 door_reward 几何 + 钥匙色稀缺度数清。

用法：python analyze_priorities.py <bb25_gd1.jsonl> [beta_big=25] [beta_small=3] [gamma=1]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, DOOR_KEY_MAP
from solver.verify import replay
from solver.beam import build_future_roster
from probe_crossfloor import build_start, _fidx
from vzone import build_zone, _zone_key_geometry, _toll_dist_from
from vzone import _zone_attr_gems as _gems_of
from big_item_pull import (detect_big_items, pull_big, build_pickup_bonus, pickup_bonus,
                           _region_pot, _delta_rp)
from door_value import build_door_reward, door_pull, _unabsorbed

INF = float("inf")


def pick_deepest(rows, start):
    best = None
    for r in rows:
        fin = replay(start, r["actions"], step, _copy_state)
        key = (_fidx(fin.current_floor), fin.hero.hp)
        if best is None or key > best[0]:
            best = (key, r, fin)
    return best[1], best[2]


def gem_pickup_timeline(start, actions, watch):
    """步进重放，记录 watch 里每个 cell 第一次 entities==0(被拿走) 的 step 与当时楼层/HP/atk/def。"""
    s = _copy_state(start)
    taken = {}
    snaps = {}  # step -> state copy (only at pickup steps we care)
    for i, a in enumerate(actions):
        s = step(s, a)
        for cell in watch:
            if cell in taken:
                continue
            fid, x, y = cell
            fl = s.floors.get(fid)
            if fl is not None and fl.entities[y][x] == 0:
                taken[cell] = (i, s.hero.x, s.hero.y, s.current_floor,
                               s.hero.hp, s.hero.atk, s.hero.def_)
    return taken


def state_after_step(start, actions, target_step):
    s = _copy_state(start)
    for i, a in enumerate(actions):
        s = step(s, a)
        if i == target_step:
            return _copy_state(s)
    return s


def first_arrival_state(start, actions, floor):
    s = _copy_state(start)
    for a in actions:
        s = step(s, a)
        if s.current_floor == floor:
            return _copy_state(s)
    return None


def isolated_pull(zone, roster, state, cell, da, dd):
    """单格大件的 pull 分量（不乘 β）：ΔRP(当前)/(1+dist)。"""
    h = state.hero
    base = _region_pot(state, roster)
    dist = _toll_dist_from(zone, (state.current_floor, h.x, h.y), h.atk, h.def_, h.mdef)
    d = dist.get(cell, INF)
    if d == INF:
        return None, INF
    drp = _delta_rp(state, roster, base, da, dd)
    return drp / (1.0 + d), d


def isolated_door_pull(zone, state, dcell, info, gamma, geom):
    """单扇门的 door_pull 分量：γ·Ru/(1+nd+pen)。复刻 door_value.door_pull 内层、只读。"""
    h = state.hero
    Ru, cells = _unabsorbed(state, info)
    if Ru <= 0 or not cells:
        return 0.0, None, None
    dist = _toll_dist_from(zone, (state.current_floor, h.x, h.y), h.atk, h.def_, h.mdef)
    nd = min((dist.get(c, INF) for c in cells), default=INF)
    if nd == INF:
        return 0.0, INF, None
    dfid, dx, dy = dcell
    dfl = state.floors.get(dfid)
    closed = dfl is not None and DOOR_KEY_MAP.get(dfl.terrain[dy][dx]) is not None
    pen = 0.0
    color = info["color"]
    if closed and h.keys.get(color, 0) <= 0:
        kd = INF
        for (kcell, iid) in geom["key_item"].items():
            if iid != color:
                continue
            kfid, kx, ky = kcell
            kfl = state.floors.get(kfid)
            if kfl is not None and kfl.entities[ky][kx] == 0:
                continue
            kd = min(kd, dist.get(kcell, INF))
        if kd == INF:
            return 0.0, nd, INF
        pen = kd
    return gamma * Ru / (1.0 + nd + pen), nd, pen


def main():
    if len(sys.argv) < 2:
        sys.exit("用法：python analyze_priorities.py <bb25_gd1.jsonl> [beta_big] [beta_small] [gamma]")
    fb = Path(sys.argv[1])
    if not fb.is_absolute():
        fb = Path(__file__).parent / fb.name
    beta_big = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
    beta_small = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
    gamma = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0

    start, _ = build_start()
    roster = build_future_roster(start)
    zone = build_zone()
    big_cells, tau, ranked = detect_big_items(zone, roster, start)
    bonus = build_pickup_bonus(ranked, big_cells, beta_big, beta_small)
    reward = build_door_reward(zone, roster, start, big_cells, ranked, include_win=True)
    gems = _gems_of(zone)
    geom = _zone_key_geometry(zone)
    drp0 = {cell: drp for drp, cell, _, _ in ranked}

    print("=" * 100)
    print(f"β_big={beta_big:g} β_small={beta_small:g} γ={gamma:g}  大件 {len(big_cells)} 件 τ={tau:,.0f}")
    print("【大件/小宝石 ΔRP₀ 与满额兑现 G】(数据涌现·参照态固定常数)")
    for drp, cell, da, dd in ranked:
        if drp <= 0:
            continue
        big = cell in big_cells
        g = bonus.get(cell, 0)
        print(f"   {'★大件 ' if big else '  小宝石'} {cell[0]}({cell[1]},{cell[2]}) +atk{da}/+def{dd}"
              f"  ΔRP₀={drp:>9,.0f}  G拿取={g:>12,.0f}")

    # ───────── PART A：剑盾 vs 小宝石 沿真实路线对账 ─────────
    rows = [json.loads(ln) for ln in fb.read_text(encoding="utf-8").splitlines() if ln.strip()]
    row, fin = pick_deepest(rows, start)
    actions = list(row["actions"])
    print("\n" + "=" * 100)
    print(f"PART A  源 {fb.name}  挑中最深态 终={fin.current_floor}({fin.hero.x},{fin.hero.y}) "
          f"HP={fin.hero.hp} ATK={fin.hero.atk} DEF={fin.hero.def_}  {len(actions)}步")

    watch = list(gems.keys())
    taken = gem_pickup_timeline(start, actions, watch)
    timeline = sorted(taken.items(), key=lambda kv: kv[1][0])
    print(f"\n【攻防道具拾取时间线】(共 {len(gems)} 件攻防物，路线吃了 {len(taken)} 件)")
    sword_step = shield_step = None
    for cell, (st, hx, hy, hf, hp, atk, df) in timeline:
        big = cell in big_cells
        tag = "★大件" if big else "  小宝石"
        print(f"   step{st:>4}  {tag} {cell[0]}({cell[1]},{cell[2]})  → HP{hp} ATK{atk} DEF{df}")
        if big and da_dd(gems, cell)[0] > da_dd(gems, cell)[1]:  # atk-heavy = 剑
            if sword_step is None:
                sword_step = st
        elif big:
            if shield_step is None:
                shield_step = st
    # 大件两件：按 atk/def 偏向粗标剑/盾（仅显示用）
    bigs = [(c, gems[c]) for c in big_cells]
    print(f"\n   大件明细：" + "  ".join(f"{c[0]}({c[1]},{c[2]})+atk{v[0]}/def{v[1]}@step{taken.get(c,['?'])[0]}"
                                       for c, v in bigs))

    # 找"最后拿的那件大件"= 盾（最深/最后），和"第一件大件"= 剑
    big_taken = [(c, taken[c][0]) for c in big_cells if c in taken]
    big_taken.sort(key=lambda t: t[1])
    if len(big_taken) >= 2:
        first_big, fb_step = big_taken[0]
        last_big, lb_step = big_taken[-1]
        # 后拿大件之前，吃了哪些小宝石、共 G 多少
        mid_small = [(c, taken[c]) for c in taken
                     if c not in big_cells and fb_step < taken[c][0] < lb_step]
        gsum = sum(bonus.get(c, 0) for c, _ in mid_small)
        print(f"\n【关键窗口】先拿大件 {first_big} @step{fb_step} → 后拿大件 {last_big} @step{lb_step}")
        print(f"   这中间吃了 {len(mid_small)} 个小宝石，合计 G = {gsum:,.0f}")
        # 后拿大件(盾)在"先拿大件后那一刻"的远 pull
        s_post = state_after_step(start, actions, fb_step)
        da, dd = gems[last_big]
        pull_unit, dist_sh = isolated_pull(zone, roster, s_post, last_big, da, dd)
        if pull_unit is not None:
            print(f"   刚拿完第一件大件时(HP{s_post.hero.hp}/{s_post.hero.atk}/{s_post.hero.def_} "
                  f"@{s_post.current_floor}({s_post.hero.x},{s_post.hero.y}))：")
            print(f"     后拿大件{last_big} 的【在场引导】= β_big·ΔRP/(1+dist) = "
                  f"{beta_big:g}·{_delta_rp(s_post, roster, _region_pot(s_post,roster), da, dd):,.0f}/"
                  f"(1+{dist_sh:,.0f}) = {beta_big*pull_unit:,.0f}")
            print(f"     它的【拿到兑现】G = {bonus.get(last_big,0):,.0f}  "
                  f"(兑现/引导 = {bonus.get(last_big,0)/(beta_big*pull_unit+1e-9):,.1f}×)")
            print(f"   ⇒ 远盾在场引导 {beta_big*pull_unit:,.0f}  vs  中途小宝石累计兑现 {gsum:,.0f}  "
                  f"= 小宝石群体压过远盾引导 {gsum/(beta_big*pull_unit+1e-9):,.1f}×")

    # ───────── PART B：MT8左下 蓝钥误判 vs 门后谷 ─────────
    print("\n" + "=" * 100)
    print("PART B  MT8 左下攻防 vs MT9 路线")
    mt8_gems = {c: v for c, v in gems.items() if c[0] == "MT8"}
    print(f"\n【MT8 攻防宝石】{len(mt8_gems)} 件：")
    for c, (da, dd) in sorted(mt8_gems.items()):
        print(f"   {c} +atk{da}/+def{dd}  ΔRP₀={drp0.get(c,0):,.0f}  在拾取线上={'是' if c in taken else '否(从不拿)'}")

    # 钥匙色稀缺度（zone-1 总量）
    from collections import Counter
    key_cnt = Counter(geom["key_item"].values())
    door_cnt = Counter(geom["door_color"].values())
    print(f"\n【钥匙色稀缺度·一区总量】(door_pull/value_vector 不按色加权，只看真稀缺)")
    for col in sorted(set(list(key_cnt) + list(door_cnt))):
        print(f"   {col:<9} 地图钥匙 {key_cnt.get(col,0):>2} 把   门 {door_cnt.get(col,0):>2} 扇   "
              f"{'富余' if key_cnt.get(col,0) >= door_cnt.get(col,0) else '稀缺(钥<门)'}")

    # MT8 的门 + door_reward
    mt8_doors = {c: col for c, col in geom["door_color"].items() if c[0] == "MT8"}
    print(f"\n【MT8 门 {len(mt8_doors)} 扇 → door_reward 引导】")
    for dcell, col in sorted(mt8_doors.items()):
        info = reward.get(dcell)
        if info is None:
            print(f"   门{dcell} {col:<9} → 不在奖励表(可绕过/门后无可兑现价值=不引导开它)")
            continue
        pg = info["gems"]
        has_attr = [g for g in pg if g[0] in mt8_gems]
        print(f"   门{dcell} {col:<9} R={info['R']:,.0f} pocket={len(info['pocket'])} "
              f"宝石{len(pg)} 血{len(info['blood'])}  门后含MT8攻防={[g[0] for g in has_attr]}")

    # 所有蓝门按 R 排序（判 MT8左下是否值得花稀缺蓝钥=该不该跳过）
    blue_doors = sorted([(d, info) for d, info in reward.items() if info["color"] == "blueKey"],
                        key=lambda t: -t[1]["R"])
    print(f"\n【一区蓝门 R 排名】(蓝钥 {key_cnt.get('blueKey',0)} 把 / 蓝门 {door_cnt.get('blueKey',0)} 扇，"
          f"奖励表里有价值的蓝门 {len(blue_doors)} 扇 → 稀缺蓝钥该投给 R 最高的)")
    for rank, (dcell, info) in enumerate(blue_doors, 1):
        star = "  ← MT8左下" if dcell == ("MT8", 3, 11) else ""
        print(f"   #{rank} 门{dcell} R={info['R']:>10,.0f} "
              f"宝石{len(info['gems'])}血{len(info['blood'])}{' win' if info['win'] else ''}{star}")

    # 在 MT8 首次到达态，比 MT8左下门 vs MT9 黄门 的 door_pull
    s8 = first_arrival_state(start, actions, "MT8")
    if s8 is not None:
        print(f"\n【MT8 首次到达态】HP{s8.hero.hp}/{s8.hero.atk}/{s8.hero.def_} @({s8.hero.x},{s8.hero.y})  "
              f"持钥={ {k:v for k,v in s8.hero.keys.items() if v} }")
        cand = [(d, reward[d]) for d in reward if d[0] in ("MT8", "MT9")]
        cand.sort(key=lambda t: -t[1]["R"])
        for dcell, info in cand[:8]:
            dp, nd, pen = isolated_door_pull(zone, s8, dcell, info, gamma, geom)
            pentag = "" if pen in (0.0, None) else f" +keypen{pen:,.0f}"
            print(f"   门{dcell} {info['color']:<9} R={info['R']:>10,.0f}  door_pull={dp:>10,.2f}  "
                  f"(dist门后={nd}{pentag})")
    else:
        print("\n   (路线未到 MT8，无法取首次到达态)")
    print("\n" + "=" * 100)


def da_dd(gems, cell):
    return gems[cell]


if __name__ == "__main__":
    main()
