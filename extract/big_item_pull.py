"""【结合·大件引导】detect_big_items + pull_big —— 玩家 2026-06-11 拍板【结合】的落点（驱动层，塔无关）。

把 vzone 的 pull「只对大件」版接回 region 区势能基分：
  · region 区势能基分 = 【兑现侧】（小宝石/血的价值拿到才兑现，已验证够用，不动）。
  · pull_大件      = 【引导侧】，只对【高减伤大件】(如剑盾)给"去拿它"的梯度——治【剑盾误判】
                      （现行病：搜索在 MT3 裸打近 500 血的小蝙蝠+骷髅，不先去 MT5 拿铁剑再回头）。
排序键 = region 基分(beam_future) + β_big·pull_大件(本模块, 经 search_quotient(beam_score_extra=))。

【大件由数据涌现，不硬编码"剑盾"/物品 id】：对每件攻防物算 ΔRP(整区减伤)，按 ΔRP 降序找【最大乘性缝】，
缝上方=大件（本塔自然落到 {铁剑,铁盾}，与小宝石间有数量级落差）。缝由 ΔRP 分布自动找、塔无关。

口径与 probe_big_item_gap.py 一致：
  · ΔRP(g, state) = region_pot(state) − region_pot(state+g增益)；region_pot = _future_potential(λ=1 原始和)
    （与兑现侧同源、引擎真损血、不手写公式）。
  · dist = 当前格→g 格最短累计损血（vzone._toll_dist_from，跨层 toll-Dijkstra），引导折扣 1/(1+dist)。
  · pull_big = Σ_{g∈大件·还在地上·够得到} ΔRP(g,state)/(1+dist)。

红线（守】value_vector 零回归）：本项【只】进 beam 排序键（search_quotient 的 beam_score_extra），
绝不进 value_vector/D。拿到大件即离场→pull 归 0，同时区势能基分因该大件减伤而跃升 ≈ΔRP（兑现），
而守着的引导分 ≤ β_big·ΔRP/(1+dist)（dist≥1）→ 拾取兑现严格 > 守着引导 → 不复发 κ=1（与小宝石全进
引导会守着不拿的病本质不同：小宝石不在大件集里，只走兑现侧）。
"""
from solver.beam import FutureCfg, _future_potential
from vzone import _zone_attr_gems, _toll_dist_from, BOSS_FLAG


def _region_pot(state, roster):
    """区势能原始和（λ=1）：Σ_{当前区到boss·非当前层·存活怪} toll。与兑现侧/探针同源。"""
    return _future_potential(state, FutureCfg(roster, 1.0))


def _delta_rp(state, roster, base_pot, da, dd):
    """ΔRP = base_pot − region_pot(state 临时 +da/+dd)。原地改 hero atk/def 算完即还原
    （_future_potential 纯读、单线程；try/finally 保证还原）——避开 _copy_state 深拷 floors 的高成本。"""
    h = state.hero
    h.atk += da
    h.def_ += dd
    try:
        bumped = _future_potential(state, FutureCfg(roster, 1.0))
    finally:
        h.atk -= da
        h.def_ -= dd
    return base_pot - bumped


def detect_big_items(zone, roster, ref_state, min_gap=2.0):
    """从【数据涌现】划出大件格集：对每件攻防物算 ΔRP(ref_state)，按 ΔRP 降序找【最大乘性缝】，缝上=大件。
    返回 (big_cells:set[(fid,x,y)], tau:float, ranked:list[(ΔRP,cell,da,dd)])。
    · ref_state：固定参照（干净起点·噩梦后 MT3 入口）——定"本塔什么算大件"，集静态、与运行态无关。
    · min_gap：缝的最小乘性落差（默认 2.0=下一件减伤的两倍才算"清晰分界"）。最大缝 < min_gap → 视为
      无清晰大件、返回空集（pull 全程 0、纯 region、字节零回归）——防把平滑分布误切出"大件"（塔无关稳健）。
    塔无关：不认物品 id/名，纯按 ΔRP 减伤量分；剑盾减伤远超小宝石→自然落到缝上方。"""
    gems = _zone_attr_gems(zone)
    base = _region_pot(ref_state, roster)
    ranked = []
    for (cell, (da, dd)) in gems.items():
        drp = _delta_rp(ref_state, roster, base, da, dd)
        ranked.append((drp, cell, da, dd))
    ranked.sort(key=lambda r: -r[0])
    vals = [r[0] for r in ranked if r[0] > 0]
    big_cells = set()
    tau = 0.0
    best_gap = 0.0
    best_i = None
    for i in range(len(vals) - 1):
        hi_v, lo_v = vals[i], vals[i + 1]
        if lo_v <= 0:
            continue
        ratio = hi_v / lo_v
        if ratio > best_gap:
            best_gap = ratio
            best_i = i
    if best_i is not None and best_gap >= min_gap:
        tau = (vals[best_i] * vals[best_i + 1]) ** 0.5
        big_cells = {r[1] for r in ranked[:best_i + 1]}
    return big_cells, tau, ranked


def pull_big(zone, roster, state, big_cells):
    """beam 排序键的【大件引导项】≥0：Σ_{g∈big_cells·还在地上·够得到} ΔRP(g,state)/(1+dist)。
    大件全拿光/区外/已过 boss → 0（早退，省 Dijkstra）。只引导、不兑现、不进 value_vector（红线）。
    口径：ΔRP 用【当前态】（引导梯度反映当下边际减伤），dist 用当前格全图 toll-Dijkstra（vzone 同源）。"""
    if not big_cells:
        return 0.0
    h = state.hero
    fid = state.current_floor
    if fid not in zone["floors"] or h.flags.get(BOSS_FLAG):
        return 0.0
    floors = state.floors
    remaining = []
    for cell in big_cells:
        gfid, x, y = cell
        fl = floors.get(gfid)
        if fl is not None and fl.entities[y][x] == 0:
            continue                               # 已拿走 → 离场、不引导
        remaining.append(cell)
    if not remaining:
        return 0.0                                 # 大件全拿光 → 早退（不算 Dijkstra）
    gems = _zone_attr_gems(zone)
    base = _region_pot(state, roster)
    dist = _toll_dist_from(zone, (fid, h.x, h.y), h.atk, h.def_, h.mdef)
    total = 0.0
    for cell in remaining:
        d = dist.get(cell)
        if d is None or d == float("inf"):
            continue                               # 够不到 → 门控 0（可达性）
        da, dd = gems[cell]
        drp = _delta_rp(state, roster, base, da, dd)
        if drp <= 0:
            continue
        total += drp / (1.0 + d)
    return total


def build_pickup_bonus(ranked, big_cells, beta_big, beta_small):
    """【满额兑现·拿取奖励表】把 detect_big_items 的 ranked(ΔRP₀ 参照态固定常数·数据涌现)折成 {cell: 拿到即加常数}。
      · 大件(cell∈big_cells)：β_big·ΔRP₀(g)。   · 小宝石(其余·ΔRP₀>0)：β_small·ΔRP₀(g)。
    满额兑现形式：拿走时给【满额】β·ΔRP₀，而在场只给【折扣】β·ΔRP(当前)/(1+dist)；ΔRP₀(参照态·最弱)是当前 ΔRP 的上界
    ⇒ 拾取兑现 β·ΔRP₀ ≥ 守着引导 β·ΔRP/(1+dist)，单调不降、结构性保证【拿走≥守着】——不靠调参、不犯就近病/κ=1。
    红线：β=0 → 空表 → G≡0 字节零回归。塔无关：只认 ΔRP 减伤量、不认物品 id/名。"""
    table = {}
    for (drp, cell, da, dd) in ranked:
        if drp <= 0:
            continue                               # 无减伤 → 不奖励（与 pull_big 同口径）
        beta = beta_big if cell in big_cells else beta_small
        if beta <= 0:
            continue                               # β=0 → 不入表（空表=字节零回归）
        table[cell] = beta * drp
    return table


def pickup_bonus(state, bonus_table):
    """【拿取奖励 G(state)】≥0：Σ_{cell∈bonus_table·已拿走(entities==0)} bonus_table[cell]。
    '已拿走' 用现成 entities==0 判定（与 pull_big 离场判定同口径；floor 未加载=没拿、不给）。
    拿到才兑现 → 天然不犯 κ=1（没拿不给、拿了即满额）；空表 → 0（字节零回归）。
    只进 beam 排序键、绝不进 value_vector/D（红线）。"""
    if not bonus_table:
        return 0.0
    floors = state.floors
    total = 0.0
    for (cell, bonus) in bonus_table.items():
        gfid, x, y = cell
        fl = floors.get(gfid)
        if fl is not None and fl.entities[y][x] == 0:
            total += bonus                         # 已拿走 → 满额兑现
    return total
