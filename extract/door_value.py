"""【门锚定·全臂梯度】钥匙价值 —— 玩家 2026-06-12 拍板【选项1】的落点（驱动层，塔无关）。

病根（idea3 §B 坐实）：开门【花掉一把钥匙】(value_vector key −1)，但门后回报【在门后】、不在当前自由
块的吸收视野里——价值向量把"花掉的钥匙"记成纯损、把"门后价值"记成零 ⇒ 6 例门(#59/60/66/72/95/139)
被【不花钥匙的楼梯】在【仅 key 轴】上 Pareto 淘汰；运行时按指纹分桶后真正约束是 beam 截断(谷-崖)。
病机精确：开门不抬排序键（门后怪 toll 已在 D、门后宝石不是怪不在 D、pull/G 门乐观与开门无关、HP 不变），
却花钥匙 → 穿门那条在建态在【吸到门后价值之前】排序键单调下行被 beam 截掉。

解法（与满额兑现 G / pull_大件【同构】，都把信用锚在【行动】而非【持有】）：给【穿门去吸门后价值】一条
排序键引导梯度 door_pull，锚在【门(花钥匙的不可逆动作)】上，由门后【可兑现奖励】R(d) 加权、距离折扣：

  door_pull(state) = Σ_{d: 门后有未吸价值·够得到} γ · R_未吸(d) / (1 + dist_arc)

  · R(d)【数据涌现·参照态固定常数】= 门后专属 pocket 内【小宝石 ΔRP₀ + 血瓶 HP (+ win 若 boss/goal 在 pocket)】，
    【排除门后怪 toll】(已在 D，再加=二重计上) + 【排除大件】(big_cells，pull_大件 已给其引导，排除防双计)。
    ΔRP₀ 用与满额兑现 G【同一份 ranked】(detect_big_items 参照态)→ 单一事实源、结构关系干净。
  · pocket(d)【门后专属·紧邻】= 门乐观静态图上【远侧紧邻无门分量】∩【gated=full_reach − 把 d 当墙的 reach】。
    取交两层防过计：gated 切掉"绕得过的门"(差集空)；紧邻分量切掉"穿行门下游更深门后的格"(只领到下一扇门那段)
    → 同一宝石只落最贴近它的那扇门(不双计/不虚高、不让穿行门 520 格淹没死袋门)。门可绕过→pocket 空→不引导
    开门(开了纯亏钥匙=算法本就对)；门是死袋唯一入口→pocket=死袋全部价值→引导穿门。
  · dist_arc【全臂=拿钥匙→开门→吸价值整条】= 门乐观 dist 到【最近未吸 pocket 格】 + key_penalty
    (门仍闭 且 手里无该色钥匙 → 加【最近可达同色钥匙】的 dist；无可达钥匙→开不了→该门不计)。
    抓到钥匙 → penalty 归 0 → door_pull 跃升 ⇒ 钥匙价值【经它能开的门兑现】显形，且锚在门、非锚在持有钥匙。

为什么不复发 κ=1（红线，六命门单测钉死）：
  ① 门后宝石被【吸走(entities==0)】→ R_未吸 去掉它 → door_pull 对它归 0，同时满额兑现 G 补 β·ΔRP₀ +
     区势能 base 兑现 → 拿走【严格优于】守着（γ≤β 时 满额 β·ΔRP₀ ≥ 守着 γ·ΔRP₀/(1+dist)，结构性）。
  ② 持有钥匙【本身】零加分：door_pull 只奖励【门后有未吸价值 R>0 且够得到】的门；手里多一把钥匙仅在【存在
     这样一扇门】时经 penalty 归 0 抬分 → 信用恒锚在【那扇门后那片可兑现价值】，无门可开的钥匙=零信用
     （与被否的"选项2 给持有钥匙加分"本质不同：那个无条件奖励持有→囤钥匙 κ=1）。
  ③ 门开后 door_pull【不立即归 0】(锚在 pocket 未吸、非锚门闭)→ 无"开门即掉分"崖 → 穿门吸价值平滑接管。
红线：γ=0 → 空表 → door_pull≡0 字节零回归；只进 beam_score_extra 排序键，绝不进 D/value_vector；
塔无关：门/钥匙/boss 全由 DOOR_KEY_MAP/_KEY_ITEMS/BOSS_FLAG 门禁检测，不写死"红门"/物品 id/层号。
"""
import heapq

from big_item_pull import _region_pot, _delta_rp
from vzone import (_zone_attr_gems, _toll_dist_from, _passable, _NB4,
                   _zone_key_geometry, boss_toll, BOSS_FLAG, BOSS_FLOOR, BOSS_CELL)
from sim.simulator import DOOR_KEY_MAP
from solver.search import _gives_hp_on_pickup

_INF = float("inf")


# ───── 血瓶增益缓存（与 _zone_attr_gems 对偶，数据驱动·不写死 id，镜像引擎 _apply_item_effect）─────

def _hp_gain(items_db, iid, ratio):
    """镜像引擎算血瓶 (+HP)；非 HP pickup → 0。口径同 solver.search._gives_hp_on_pickup 的取值侧。"""
    d = items_db.get(iid)
    if not isinstance(d, dict):
        return 0
    pu = d.get("pickup")
    if not isinstance(pu, dict):
        return 0
    tp = pu.get("type")
    if tp == "stat" and pu.get("stat") == "hp":
        return pu["base"] * ratio if pu.get("ratio_scaled") else pu.get("delta", 0)
    if tp == "multi":
        return sum(op.get("delta", 0) for op in pu["ops"] if op.get("stat") == "hp")
    return 0


def _zone_blood(zone):
    """缓存：本区血瓶 {(fid,x,y): ΔHP}（位置/增益从各层初始地图算；运行时是否还在由 live entities 判）。"""
    if "blood_cells" in zone:
        return zone["blood_cells"]
    blood = {}
    for fid, r in zone["floors"].items():
        fl = r["floor"]
        for y, row in enumerate(fl.entities):
            for x, e in enumerate(row):
                if not e:
                    continue
                iid = fl._tile_to_item.get(e)
                if not iid or not _gives_hp_on_pickup(fl._items_db.get(iid)):
                    continue
                hp = _hp_gain(fl._items_db, iid, fl.ratio)
                if hp > 0:
                    blood[(fid, x, y)] = hp
    zone["blood_cells"] = blood
    return blood


# ───── 门后专属 pocket（门乐观静态图·纯几何·与运行态无关·建图一次）─────
#
# 关键：pocket 取【紧邻分量】而非"门后整条下游"。把【所有门】当墙→图裂成无门自由分量；门 d 的 pocket =
# 它【远离 source 那侧】紧邻的分量。这样：① 主路串联门各自只领【到下一扇门为止】那一段(穿行门 pocket 小)，
# ② 同一宝石只落在【最贴近它的那扇门】的 pocket(不被上游每扇门重复计=不双计/不虚高)，③ 死袋侧室=叶分量、
# 其战利品干净落在唯一入口门上。承接冒烟暴露的"穿行门 pocket=520 格淹没死袋门"病。

def _neighbors(zone, node):
    fid, x, y = node
    nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
    if node in zone["links"]:
        nbrs.append(zone["links"][node])
    return nbrs


def _flood(zone, src, blocked):
    """门乐观静态图（门=零代价可过、楼梯免费边）从 src 的可达格集，把 blocked 里的格当墙。"""
    if not _passable(zone, src) or src in blocked:
        return set()
    seen = {src}
    stack = [src]
    while stack:
        node = stack.pop()
        for nb in _neighbors(zone, node):
            if nb in seen or nb in blocked or not _passable(zone, nb):
                continue
            seen.add(nb)
            stack.append(nb)
    return seen


def _pocket_immediate(zone, door_cell, all_doors, gated):
    """门 door_cell 的【紧邻 gating pocket】= 远侧紧邻无门分量 ∩ gated（仅经此门可达格）。两者取交：
    · 远侧 = 门的【落在 gated 里(只有经此门才够得到)】那侧邻格，其【把所有门当墙】flood 出的紧邻无门分量；
    · gated = full_reach − 把此门单独当墙的 reach（在 build_door_reward 算好传入）。
    效果：穿行门只领【到下一扇门为止】那段(远侧紧邻分量切掉下游)，同一宝石只落最贴近它的门(不双计)；
    门可绕过(有楼梯/平行门替代)→ gated 空 → 远侧邻格不在 gated → pocket 空(开它纯亏钥匙=算法本就对)；
    死袋侧室→远侧紧邻分量=死袋、且全在 gated→干净落在唯一入口门。治冒烟暴露的穿行门 520 格淹没死袋门病。"""
    far_nbrs = [nb for nb in _neighbors(zone, door_cell)
                if nb not in all_doors and nb in gated and _passable(zone, nb)]
    if not far_nbrs:
        return set()
    immediate = set()
    for nb in far_nbrs:
        if nb not in immediate:
            immediate |= _flood(zone, nb, all_doors)            # 远侧那格的无门紧邻分量
    return immediate & gated                                     # ∩ 仅经此门可达 → 切掉下游更深门后的格


# ───── 门后奖励表 R(d)（数据涌现·参照态固定常数；排怪toll、排大件，防二重计上/双引导）─────

def build_door_reward(zone, roster, ref_state, big_cells, ranked, include_win=False):
    """每【闭门】算门后专属 pocket，折出 R(d)=Σ门后小宝石 ΔRP₀ + 血瓶 HP (+ win 若 boss/goal 在 pocket)。
    返回 {door_cell: dict(color, R, gems=[(cell,ΔRP₀)], blood=[(cell,HP)], win=float, pocket=set)}（仅 R>0）。
    · ΔRP₀ 取自【与满额兑现 G 同一份 ranked】(detect_big_items 参照态固定常数)→ 单一事实源。
    · 排除 big_cells（大件由 pull_大件 引导，排除防双引导）；排除门后怪 toll（已在 D，排除防二重计上）。
    · include_win=False（阶段1·短臂门，纯宝石/血 pocket，干净接 G/HP 崖）；True（阶段2·长臂红钥过 boss）。
    塔无关：门由 _zone_key_geometry(DOOR_KEY_MAP) 读出、boss 由 BOSS_FLAG/CELL 门禁检测，不写死红门/层号。"""
    geom = _zone_key_geometry(zone)
    gems = _zone_attr_gems(zone)
    blood = _zone_blood(zone)
    drp0 = {cell: drp for drp, cell, _, _ in ranked}            # 参照态固定 ΔRP₀（与 G 同源）
    all_doors = frozenset(geom["door_color"])
    src = (ref_state.current_floor, ref_state.hero.x, ref_state.hero.y)
    full_reach = _flood(zone, src, frozenset())                 # 门乐观全可达（门=零代价）
    boss_node = (BOSS_FLOOR, *BOSS_CELL)
    win_value = _region_pot(ref_state, roster) if include_win else 0.0   # 解锁通关≈整区待克 grind 势能(hp 当量)

    table = {}
    for dcell, color in geom["door_color"].items():
        gated = full_reach - _flood(zone, src, frozenset({dcell}))   # 仅经此门可达格（绕得过→空）
        pocket = _pocket_immediate(zone, dcell, all_doors, gated)
        if not pocket:
            continue                                            # 门可绕过 / 远侧无解锁新格 → 不引导
        pg = [(c, drp0[c]) for c in pocket
              if c in gems and c not in big_cells and drp0.get(c, 0) > 0]
        pb = [(c, blood[c]) for c in pocket if c in blood]
        win = win_value if (boss_node in pocket) else 0.0
        R = sum(v for _, v in pg) + sum(v for _, v in pb) + win
        if R <= 0:
            continue
        table[dcell] = dict(color=color, R=R, gems=pg, blood=pb, win=win, pocket=pocket)
    return table


# ───── door_pull：beam 排序键的【门后价值引导项】（只进 beam_score_extra，绝不进 D/value_vector）─────

def _unabsorbed(state, info):
    """门后 pocket 当前【未吸】价值之和 R_未吸 + 未吸格表（宝石/血 entities==0 即吸走、boss flag 即清）。"""
    floors = state.floors
    Ru = 0.0
    cells = []
    for (cell, drp) in info["gems"]:
        gfid, gx, gy = cell
        fl = floors.get(gfid)
        if fl is not None and fl.entities[gy][gx] == 0:
            continue                                            # 宝石已吸走 → 离场
        Ru += drp
        cells.append(cell)
    for (cell, hp) in info["blood"]:
        bfid, bx, by = cell
        fl = floors.get(bfid)
        if fl is not None and fl.entities[by][bx] == 0:
            continue                                            # 血瓶已吸走 → 离场
        Ru += hp
        cells.append(cell)
    if info["win"] and not state.hero.flags.get(BOSS_FLAG):
        Ru += info["win"]
        cells.append((BOSS_FLOOR, *BOSS_CELL))
    return Ru, cells


def door_pull(zone, state, door_reward, gamma):
    """beam 排序键的【门后价值引导项】≥0：Σ_{d: 门后有未吸价值·够得到} γ·R_未吸(d)/(1+dist_arc)。
    口径见模块顶。空表/γ=0/区外/已胜 boss/门后全吸完 → 0（早退，省 Dijkstra）。只引导、不兑现、不进 value_vector。"""
    if not door_reward or gamma == 0:
        return 0.0
    h = state.hero
    fid = state.current_floor
    if fid not in zone["floors"] or h.flags.get(BOSS_FLAG):
        return 0.0
    floors = state.floors
    active = []
    for dcell, info in door_reward.items():
        Ru, cells = _unabsorbed(state, info)
        if Ru <= 0 or not cells:
            continue                                            # 门后价值全吸完 → 该门不再引导
        active.append((dcell, info["color"], Ru, cells))
    if not active:
        return 0.0
    dist = _toll_dist_from(zone, (fid, h.x, h.y), h.atk, h.def_, h.mdef)
    geom = _zone_key_geometry(zone)
    total = 0.0
    for (dcell, color, Ru, cells) in active:
        nd = min((dist.get(c, _INF) for c in cells), default=_INF)
        if nd == _INF:
            continue                                            # 门后未吸价值够不到 → 门控 0
        dfid, dx, dy = dcell
        dfl = floors.get(dfid)
        closed = dfl is not None and DOOR_KEY_MAP.get(dfl.terrain[dy][dx]) is not None
        pen = 0.0
        if closed and h.keys.get(color, 0) <= 0:               # 门仍闭 且 手里无该色钥匙 → 加全臂钥匙腿
            kd = _INF
            for (kcell, iid) in geom["key_item"].items():
                if iid != color:
                    continue
                kfid, kx, ky = kcell
                kfl = floors.get(kfid)
                if kfl is not None and kfl.entities[ky][kx] == 0:
                    continue                                    # 该钥匙已被取走 → 不能再供这扇门
                kd = min(kd, dist.get(kcell, _INF))
            if kd == _INF:
                continue                                        # 无可达同色钥匙 → 开不了门 → 不计（不奖励开不了的门）
            pen = kd
        total += gamma * Ru / (1.0 + nd + pen)
    return total
