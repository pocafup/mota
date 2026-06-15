"""塔无关：GA 终局适应度 fitness —— ga_design.md 钉死点 3「真引擎终局局面价值（带潜力）」的落地。

契约（钉死点 3.4 κ=1 红线，实现期守死）：fitness 只对【一条已跑完死路线的终态】评【一次】分，
绝不参与任何中途逐步决策、绝不反馈给 decoder/navigate_to 的推进。潜力项（血瓶/钥匙/攻防）都是这条
路线【真实留下的既成事实】，不是「守着没拿的期权」——逐条对 3.4 三条件：无中途逐步决策（✗1）、
潜力是既成事实非期权（✗2）、繁殖压力反惩罚赖着不动（✗3），三条都不成立 → 不构成 κ=1。

标量定义（ga_design 3.2 推荐式，最大化复用塔无关现成件）：
    fitness(final) = equiv_hp_over_roster(final, roster, big)        # 主干：HP + 攻防对一区怪压制
                   + w_potion · 一区地上剩余血瓶名义回血             # _gives_hp_on_pickup 数据驱动
                   + 钥匙家底 = w_key·手里余钥匙                     # 已兑现：满权重
                              + Σ_地上够得到钥匙 max(0, w_key−守怪损血)  # 潜力：A类地上计数·扣血成本防κ=1
                   + win_bonus (若通关)                              # 通关大奖
  死亡 → DEATH_FLOOR + 小深度项（恒低于任何活态，给 GA「虽死但更深」的爬坡梯度）。

第一版口径（玩家 2026-06-13 拍板）：
  · 参照怪集【只取一区怪】（boss_idxs 切）——一区不加攻防对后期势能无影响，避免下层怪噪声稀释 fitness 差。
  · 区势能 future=None（不叠 _future_potential）：roster 已取一区全集、主干 Σcost 已覆盖「攻防对一区
    所有怪压制」，再叠区势能会对同批区内怪重叠双计；区势能本是 beam 中途爬坡梯度、终评用不上。
  · 钥匙潜力=A类【地上剩余够得到钥匙计数】(对齐血瓶·这条死路线终态客观还剩的家底)，按 max(0,w_key−守怪损血)
    扣【拿到它的血成本】——「13 血净赚 1 把」的经济学，防 κ=1 影子(裸地上计数会奖励"别去拿钥匙")。手里钥匙
    满权重(已兑现)、地上钥匙扣血成本，使"捡 vs 不捡便宜钥匙"≈中性。
    可达=楼梯出发能走过【终态手里有钥匙的门】(乐观近似:1 把当整色门可过，因钥匙便宜·门→钥匙链自给)拿到地上
    钥匙；没钥匙的门当墙(门后钥匙拿不到)、守怪打不动→断边(可达性门控，红线B)。可达门控用【终态手里预算】=
    既成事实(type-A)，不是 door_value 把钥匙按未来开门折算(type-B 第二阶段红钥长臂课题、耦合 κ=1，第一版不碰)。
    数据坐实(analysis/probe_key_reachability)：此模型还原 718 地上 2 便宜钥匙 vs 689 的 5(MT4+MT7 黄门蝙蝠
    守、~13 血)——689 把 718 已吃掉的便宜黄门钥匙留在地上，与「689 多 250 地上血瓶」同性质的真潜力分歧。

roster/big【外部注入】（同 beam 的 equiv_hp_over_roster 风格）：由调用方用 build_zone1_roster +
calibrate_big 构造【固定参照】一次，喂给所有要评的态 → 不同基因 fitness 可比。GA 主循环复用同一对。

塔无关：怪 id 由 build_future_roster 读 _tile_to_enemy、区界由 boss_idxs 结构读、血瓶由 items.json
pickup 效果判，无任何楼层号/怪 id/物品名硬编码。引擎只当裁判，玩家真实游戏终审。
"""
import heapq

from solver.beam import equiv_hp_over_roster, _combat_damage, build_future_roster
from solver.search import _gives_hp_on_pickup
from sim.simulator import _KEY_ITEMS, WALL_TILES, DOOR_KEY_MAP

# 死亡态地板：恒 ≪ 任何活态 fitness（活态下界 ≈ HP − big×|roster| ≈ −5万量级；地板取 −1e9 远低于它）。
DEATH_FLOOR = -10 ** 9

# 序列结构无效态地板（§S15 禁区）：某腿被禁区逼死＝该排序物理不可实现（"先盾不碰剑"无路可走）→ 整条无效。
# 取 −2e9：恒 ≪ 任何死亡态（死亡 ∈ [−1e9, −1e9+层数]）→ 无效序列永远排在「能实现但会死」之下。进度分
# （已导航块数/最深层）在 eval 层叠加（量级 ≤ 7500，远小于两带间距 1e9）→ 无效序列间有梯度、GA 朝可实现
# 排序爬，但整段恒低于死亡带、不与之重叠。fitness() 本身【绝不返回此值】（κ=1：只评可实现终态一次）。
INVALID_BASE = -2 * 10 ** 9

_NB4 = ((0, -1), (0, 1), (-1, 0), (1, 0))


# ─── 一区静态参照怪集 + big 标定（外部注入，固定参照使不同基因可比）─────────────────────

def build_zone1_roster(seed_state):
    """一区【静态全集】参照怪 roster {(idx,x,y): mid} + 一区层 id 列表 + 全塔层序。
    用 build_future_roster 的 mon_cells（静态怪位、与评谁无关）按 boss_idxs[0] 切到第一区 boss（含）。
    塔无关：区界由 _is_region_boundary 结构读出，不写死层号/怪数。seed_state 仅供读塔结构（任一态皆可，
    mon_cells/boss_idxs 是塔静态属性）。"""
    fr = build_future_roster(seed_state)
    boss0 = fr["boss_idxs"][0] if fr["boss_idxs"] else fr["max_idx"]
    roster = {}
    for idx in range(0, boss0 + 1):
        for (x, y, mid) in fr["mon_cells"].get(idx, []):
            roster[(idx, x, y)] = mid
    zone_fids = [fr["floor_ids"][i] for i in range(0, boss0 + 1)]
    return roster, zone_fids, list(fr["floor_ids"])


def calibrate_big(states, roster):
    """固定 big = 一组【参照态】对 roster 的最大可杀单怪损血（同 region_reference 口径）。
    big 须 ≥ 任何态对任何怪的可杀损血，使「打不动/会被打死」记 big 始终是最差、跨防御阈值时 V 跳升。
    GA 阶段用全塔静态参照态集；本版用两条标尺 route 终态 + 起点态标定。"""
    big = 0
    for st in states:
        hp = st.hero.hp
        for mid in roster.values():
            d = _combat_damage(st, mid)
            if d is not None and d < hp and d > big:
                big = d
    return big


# ─── 潜力原料：一区地上剩余血瓶（数据驱动、跨区扫描，零回归不改 search._remaining_items）──────

def _hp_gain(idata):
    """单个道具的【名义回血量】（数据驱动，items.json pickup 效果）：stat 类取 base（ratio_scaled
    名义值）或 delta；multi 类取 ops 里 hp 的 delta。非 hp 道具 → 0。
    注：ratio_scaled=true 时引擎实际 gain=base×楼层ratio，这里用 base 名义值（留在地上的「潜在回血」，
    回头吃时才乘 ratio，名义值是塔无关、不依赖拾取时机的稳定刻度）。不写死任何 id/数值。"""
    if not idata:
        return 0
    e = idata.get("pickup")
    if not isinstance(e, dict):
        return 0
    if e.get("type") == "stat" and e.get("stat") == "hp":
        return e.get("base", e.get("delta", 0))
    if e.get("type") == "multi":
        return sum(op.get("delta", 0) for op in e.get("ops", ()) if op.get("stat") == "hp")
    return 0


def zone_remaining_potions(state, zone_fids):
    """一区各层【地上剩余血瓶名义回血总量】（"留在地上≈银行里的 HP"）。
    已访问层（在 state.floors）读残留 entities（吃掉的置 0 自动剔）；未访问层读静态 floor JSON（全剩）。
    血瓶判定走 _gives_hp_on_pickup（items.json pickup stat==hp / multi 含 hp），回血量走 _hp_gain，
    全数据驱动、不写死 id。零回归：不动 search._remaining_items（beam 段搜按 current_floor 在用），
    本函数另算【整区】口径供 GA 终评。
    塔无关：tile→item 与 items_db 取自共享全塔表（state.floor 任一已载层皆同）；未访问层路径用
    state._floors_dir，与 build_future_roster 同源。"""
    import json
    from pathlib import Path

    shared_t2i = state.floor._tile_to_item
    shared_db = state.floor._items_db
    floors_dir = getattr(state, "_floors_dir", None)
    total = 0
    for fid in zone_fids:
        fl = state.floors.get(fid)
        if fl is not None:                       # 已访问：读残留实体
            t2i, db, rows = fl._tile_to_item, fl._items_db, fl.entities
        elif floors_dir is not None:             # 未访问：读静态 JSON 全图
            path = Path(floors_dir) / f"{fid}.json"
            if not path.exists():
                continue
            rows = json.loads(path.read_text(encoding="utf-8")).get("map", [])
            t2i, db = shared_t2i, shared_db
        else:
            continue
        for row in rows:
            for tile in row:
                if tile:
                    iid = t2i.get(tile)
                    if iid is not None and _gives_hp_on_pickup(db.get(iid)):
                        total += _hp_gain(db.get(iid))
    return total


def hero_key_count(state):
    """手里【已兑现】余钥匙计数（各色钥匙总数）。已实现资源 → 满权重，无血成本折扣。"""
    return sum(v for v in state.hero.keys.values() if isinstance(v, (int, float)))


# ─── 潜力原料：一区地上剩余【够得到的】钥匙 + 守怪血成本（数据驱动、可达门控，防 κ=1 裸计数）──────

def _afford_colors(state):
    """终态【手里持有】的钥匙色集（count>0）。决定哪些钥匙门在可达判断里算「能开」。"""
    return {k for k, v in state.hero.keys.items()
            if isinstance(v, (int, float)) and v > 0}


def _zone_floor_cells(state, fid, afford):
    """规整化一区某层供守怪 Dijkstra：返回 (h, w, is_wall, mid_at, key_cells, src_cells) 或 None。
    已访问层(state.floors)读 terrain(墙)+entities(反映已杀已捡)；未访问层读静态 JSON map(全 present)。
    塔无关：墙=WALL_TILES∪_no_pass、怪=_tile_to_enemy、钥匙=_tile_to_item∩_KEY_ITEMS、楼梯源=change_floor，
    门→钥色=DOOR_KEY_MAP，全引擎共享表读，无楼层/怪/坐标/门色硬编。
    ★【预算门控·乐观可达】(红线A·type-A 不碰门后经济B)：钥匙门可过 ⇔ 终态手里持有该色钥匙(afford)。
    依据(数据坐实，见 analysis/probe_key_reachability)：用户「够得到」=能走过【手里有钥匙的门】拿地上钥匙、
    成本只算守怪损血(钥匙便宜·门→钥匙链自给故 1 把当作整色可过=乐观近似)。挡【没钥匙的门】(本塔=钢/红门，
    手里 0 把)=拿不到门后钥匙；放【有钥匙的门】(本塔=黄门)过=拿到 718/689 真实分歧的便宜地上钥匙。
    这是 type-A 既成事实(终态手里预算+地上残留)，不是 door_value 把钥匙按未来开门折算(type-B 第一版不碰)。"""
    import json
    from pathlib import Path

    shared_t2i = state.floor._tile_to_item
    shared_t2e = state.floor._tile_to_enemy
    fl = state.floors.get(fid)
    if fl is not None:                                # 已访问：terrain 判墙/锁门、entities 判怪/钥匙（route 真态）
        terrain, ents = fl.terrain, fl.entities
        t2i, t2e, nopass = fl._tile_to_item, fl._tile_to_enemy, fl._no_pass_tiles
        cf = fl.change_floor
        h, w = len(terrain), len(terrain[0])

        def is_wall(x, y):
            t = terrain[y][x]
            if t in WALL_TILES or t in nopass:
                return True
            return t in DOOR_KEY_MAP and DOOR_KEY_MAP[t] not in afford   # 没钥匙的门=墙

        def ent_at(x, y):
            return ents[y][x]
    else:                                             # 未访问：静态 JSON 合并 map（怪/钥匙/门同格记 tile id，门全锁）
        floors_dir = getattr(state, "_floors_dir", None)
        if floors_dir is None:
            return None
        path = Path(floors_dir) / f"{fid}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        grid = data.get("map", [])
        if not grid:
            return None
        cf = data.get("changeFloor", {})
        t2i, t2e = shared_t2i, shared_t2e
        h, w = len(grid), len(grid[0])

        def is_wall(x, y):
            t = grid[y][x]
            if t in WALL_TILES:
                return True
            return t in DOOR_KEY_MAP and DOOR_KEY_MAP[t] not in afford

        def ent_at(x, y):
            return grid[y][x]

    mid_at, key_cells = {}, []
    for y in range(h):
        for x in range(w):
            if is_wall(x, y):
                continue
            e = ent_at(x, y)
            if not e:
                continue
            mid = t2e.get(e)
            if mid is not None:
                mid_at[(x, y)] = mid
            if t2i.get(e) in _KEY_ITEMS:
                key_cells.append((x, y))
    src_cells = []
    for loc in cf:
        try:
            sx, sy = map(int, loc.split(","))
        except (ValueError, AttributeError):
            continue
        if 0 <= sx < w and 0 <= sy < h and not is_wall(sx, sy):
            src_cells.append((sx, sy))
    return h, w, is_wall, mid_at, key_cells, src_cells


def _ground_key_costs(state, fid, afford):
    """该层每把【地上剩余】钥匙的最小守怪损血（楼梯多源 Dijkstra）：可过门(手里有钥匙的色)/空地零代价
    过路、怪格付【实战】损血(real-atk gated)、打不动的怪=断边（怪杀不动是真够不到）。
    返回 {(fid,x,y): cost}；被打不动守怪或没钥匙的门封死的钥匙不在表内（可达性门控，红线B）。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return {}
    h, w, is_wall, mid_at, key_cells, src_cells = info
    if not key_cells or not src_cells:
        return {}

    cost_cache = {}

    def enter_cost(cell):
        """进入该格的损血：怪格=实战损血(打不动→None=断边)，非怪格=0。"""
        if cell not in mid_at:
            return 0
        if cell not in cost_cache:
            cost_cache[cell] = _combat_damage(state, mid_at[cell])
        return cost_cache[cell]

    dist = {}
    pq = []
    for s in src_cells:
        c0 = enter_cost(s)
        if c0 is not None and c0 < dist.get(s, float("inf")):
            dist[s] = c0
            heapq.heappush(pq, (c0, s))
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if d > dist.get((x, y), float("inf")):
            continue
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or is_wall(nx, ny):
                continue
            c = enter_cost((nx, ny))
            if c is None:                             # 打不动的守怪 → 断边（这条路不通）
                continue
            nd = d + c
            if nd < dist.get((nx, ny), float("inf")):
                dist[(nx, ny)] = nd
                heapq.heappush(pq, (nd, (nx, ny)))
    return {(fid, x, y): dist[(x, y)] for (x, y) in key_cells if (x, y) in dist}


def zone_ground_key_costs(state, zone_fids):
    """一区所有【地上剩余够得到】钥匙 → 守怪损血 {(fid,x,y): cost}（展示/对账用，跨层汇总）。
    可达门控按终态手里钥匙色（afford）算一次喂全层。"""
    afford = _afford_colors(state)
    out = {}
    for fid in zone_fids:
        out.update(_ground_key_costs(state, fid, afford))
    return out


def zone_key_potential(state, zone_fids, w_key):
    """钥匙家底（HP 当量，已含 w_key）= w_key·手里余钥匙 + Σ_地上够得到钥匙 max(0, w_key − 守怪损血)。
    红线A（A类地上计数，对齐血瓶）：地上钥匙是这条死路线终态客观还剩的家底，不碰 door_value 门后折算B。
    红线B（防 κ=1 影子）：手里钥匙满权重(已兑现)、地上钥匙按守怪血成本扣(w_key−cost)——「13 血净赚 1 把」
    的经济学：净潜力=钥匙值−拿到它的血；拿不动(cost≥w_key)→0、够不到(守怪断边)→不计。这样「捡 vs 不捡
    便宜钥匙」≈中性（捡=地上(w_key−cost)→手里 w_key、+cost 入钥匙项抵掉 −cost 主干 HP），不奖励守着不拿。"""
    realized = w_key * hero_key_count(state)
    ground = 0.0
    for cost in zone_ground_key_costs(state, zone_fids).values():
        ground += max(0.0, w_key - cost)
    return realized + ground


def _depth_of(state):
    """区内推进度（死亡态爬坡梯度用）：当前层在全塔层序的下标。塔无关，floor_ids 由 state 读。"""
    try:
        return state.floor_ids.index(state.current_floor)
    except (ValueError, AttributeError):
        return 0


# ─── fitness 标量 + 分项对账 ───────────────────────────────────────────────────────

def fitness(final_state, roster, big, zone_fids, *,
            w_potion=1.5, w_key=40.0, win_bonus=100000, future=None):
    """终局适应度标量（越大越优）。契约/口径见模块头。roster/big/zone_fids 外部注入（固定参照）。
    死亡 → DEATH_FLOOR + 深度项（恒 < 任何活态）；通关 → 主干 + 潜力 + win_bonus。
    权重由 cap480k 718/689 对照标定（稳健区间中值，见 analysis/calibrate_fitness.py）：
      w_potion=1.5 ∈[1.0,2.0]（下界=物理锚点 地上血瓶≈银行HP·稳在脆弱临界 0.84 上方；上界=血瓶项压过主干前）；
      w_key=40   ∈[?,?]（钥匙值需 > 守怪损血~13 才「净赚」；地上钥匙按 max(0,w_key−守怪损血) 扣血成本防 κ=1）。"""
    if final_state.dead:
        return DEATH_FLOOR + _depth_of(final_state)
    base = equiv_hp_over_roster(final_state, roster, big, future=future)
    base += w_potion * zone_remaining_potions(final_state, zone_fids)
    base += zone_key_potential(final_state, zone_fids, w_key)
    if final_state.won:
        base += win_bonus
    return base


def fitness_breakdown(final_state, roster, big, zone_fids, *,
                      w_potion=1.5, w_key=40.0, win_bonus=100000, future=None):
    """分项对账（展示/标定用，不改标量定义）：把主干 equiv_hp 拆成【HP + 攻防压制】两组成，
    钥匙项拆成【手里已兑现 + 地上够得到(各守怪损血)】两组成。total 与 fitness() 逐项一致。"""
    if final_state.dead:
        return {"dead": True, "depth": _depth_of(final_state),
                "total": DEATH_FLOOR + _depth_of(final_state)}
    hp = final_state.hero.hp
    main = equiv_hp_over_roster(final_state, roster, big, future=future)
    potion_raw = zone_remaining_potions(final_state, zone_fids)
    key_in_hand = hero_key_count(final_state)
    key_realized = w_key * key_in_hand
    ground_costs = zone_ground_key_costs(final_state, zone_fids)
    key_ground = sum(max(0.0, w_key - c) for c in ground_costs.values())
    key_term = key_realized + key_ground
    win = win_bonus if final_state.won else 0
    return {
        "dead": False,
        "won": bool(final_state.won),
        "hp": hp,
        "atk_def_suppress": main - hp,        # −Σcost：攻防对一区怪的压制（越接近 0 越强）
        "main_equiv_hp": main,                # 主干 = hp + 攻防压制
        "potion_raw": potion_raw,
        "potion_term": w_potion * potion_raw,
        "key_in_hand": key_in_hand,           # 手里已兑现钥匙数
        "key_realized": key_realized,         # w_key·手里
        "ground_keys": dict(ground_costs),    # {(fid,x,y): 守怪损血}
        "key_ground": key_ground,             # Σ max(0, w_key − 守怪损血)
        "key_term": key_term,                 # 钥匙家底总 = 手里 + 地上
        "win": win,
        "total": main + w_potion * potion_raw + key_term + win,
    }
