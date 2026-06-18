"""塔无关：缩点商图搜索（连通块抽象 + 付代价合并算子）。

动机（实测）：朴素 BFS 在富实体层把「站位 × 拾取幂集」全展开 → MT3 撞 2M cap、23 分钟。
本层把「无损血自由连通区」缩成块——块内坐标不进状态、块内免费资源（钥匙/宝石/装备/血瓶，
拿到即兑现）自动吸（顺序无关），状态只记「英雄当前自由块 = 哪些付代价对象已消除」。

口径（玩家 2026-06-06 裁定）：
  · 块内自动吸：所有道具（含血瓶，第一版从简、不做跨块 bank 开关；见 docs/solver-design.md
    「血瓶简化」+ 升级条件）。
  · 付代价合并算子：可击杀怪（damage<hp 才可战，否则硬墙节点）、钥匙门（持钥匙才可开）、
    自开假墙。执行 = 走到对象旁 + 触发，引擎 step 做真实合并（扣血/消钥匙/删墙）。
  · 独立节点（不并入块，保留可达性差异 = 残留指纹）：所有怪（可杀者另生 kill 算子、挂 afterBattle
    /到达事件的怪也可杀=死后触发，「是否独立节点」与「是否可杀」解耦见 _killable）、挂到达事件的
    非怪格（trigger）、NPC/商人/老人/祭坛、特殊门、领域/夹击/阻击伤格（块内须零损血）。
  · coin×2 兑现时机：杀怪 = 让该格并入自由块（残留指纹变）→ 「现在杀 vs 暂不杀」天然成两个
    指纹都保留，决策不被段内压掉。coin 金币翻倍的【价值】待 sim 接入 coin 机制后插入（见
    mechanics_status 待确认项）；本层只保证结构（杀/不杀分叉）在。

增量重算（玩家 4a）：拾装备/涨 atk → 更多怪变可杀、更多格变透明 → 块只会【合并不分裂】，
故每步消除算子后重算自由块即可，并查集天然适配（本实现每步重跑 floodfill，单层规模够小）。

裁判链（玩家验收硬标准）：算子/吸收全程用注入 step 推进真实 GameState，累积 U/D/L/R 动作序列；
search_quotient 输出契约与 solver.search.search_segment 对齐（found/goal_frontier/
goal_frontier_actions），调用方（phase1._run_block）照旧 solver.verify.replay 独立重放核对，
最终整条线路逐字段一致、可直接照着走。

塔无关：无任何楼层/怪/道具/阈值硬编码；可通行、可击杀、零伤、领域全由注入 state 的通用字段
+ sim 的判定函数读出。cross_floor=False（默认，phase1 段内）= 单层内搜索（离层子态裁掉）；
cross_floor=True 开启【跨层楼梯边】：changeFloor 格作 stair 算子、真实 step() 触发换层（免资源
代价），门禁未满足的楼梯格因引擎不触发而自然不生成边。事件传送（MT3 重置/MT40/MT24 结局）仍排除，
飞行边留待第二步（口径见 data/games51/floor_graph.md §7/§8）。
"""
from collections import deque, Counter, namedtuple

from sim.simulator import (
    WALL_TILES, SPECIAL_DOOR, AUTO_OPEN_TILES, DOOR_KEY_MAP,
    _in_alive_monster_footprint, _live_zone_monsters, _in_zone_range,
    _is_adjacent, _build_monster, _eff_enable,
)
from sim.combat import PlayerState, compute_combat
from solver.search import SearchResult, _value_map, _ge_all

value_vector = _value_map

_DELTAS = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}

# 门类 tile（通用引擎语义，非塔特有）：钥匙门 + 特殊门 + 自开假墙。开门 = 该格 terrain→0 移出本集。
_DOOR_TILES = set(DOOR_KEY_MAP) | {SPECIAL_DOOR} | AUTO_OPEN_TILES


# ─── 自由块（零损血连通区）─────────────────────────────────────────────────────

def _zone_blocked(state):
    """领域/阻击伤格集合：走入即损血 → 不算自由格（块内须零损血）。夹击(16)依赖 hero.hp 动态，
    第一版按「两同 special16 怪之间」静态标记其连线格（保守，宁可多留为边界）。"""
    floor = state.floor
    zms = _live_zone_monsters(state)
    blocked = set()
    for (mx, my, mid, sp, value, rng, zsq) in zms:
        if value <= 0:
            continue
        rows, cols = len(floor.terrain), len(floor.terrain[0])
        for y in range(rows):
            for x in range(cols):
                if 15 in sp and _in_zone_range(x, y, mx, my, rng, zsq):
                    blocked.add((x, y))
                if 18 in sp and _is_adjacent(x, y, mx, my, zsq):
                    blocked.add((x, y))
    return blocked


def _live_arrive_event(floor, x, y):
    """该格是否挂【会真正触发】的到达事件(arrive event)：在 events、未被抑制、未禁用。
    复刻引擎 _fire_events 门控(simulator.py:1415-1424)：已 fire 的一次性事件落入
    _suppressed_events、enable=False 的事件为空操作 → 两者皆视作不触发(该格可自由通行)。
    注：before/after_battle 是战斗钩子(仅 _fight_monster/_use_bomb 消费)，空地到达不触发，
    故不在此判定；怪格的战斗事件在 _killable 另行排除。"""
    loc = f"{x},{y}"
    if loc in floor._suppressed_events:
        return False
    ev = floor.events.get(loc)
    if ev is None:
        return False
    if isinstance(ev, dict) and not _eff_enable(floor, loc, ev, default=True):
        return False
    return True


def _is_free_tile(state, x, y, zone_blocked):
    """(x,y) 是否「自由透明格」：可零代价移入/驻留。空地或地上道具(拾取=吸收)，
    且非墙/门/noPass/大怪 footprint/领域伤格。怪一律【非自由】(可杀=算子，不可杀=节点)。"""
    floor = state.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    if not (0 <= x < cols and 0 <= y < rows):
        return False
    if (x, y) in zone_blocked:
        return False
    if f"{x},{y}" in floor.change_floor:
        return False               # 换层格：换层是显式 stair 算子，不并入自由块（防块内行走误触发换层）
    t = floor.terrain[y][x]
    if (t in WALL_TILES or t in floor._no_pass_tiles or t == SPECIAL_DOOR
            or t in DOOR_KEY_MAP or t in AUTO_OPEN_TILES):
        return False
    if _in_alive_monster_footprint(floor, x, y):
        return False
    e = floor.entities[y][x]
    if e:
        if e in floor._tile_to_item:
            return True            # 道具格：踩上=拾取=吸收，算自由
        return False               # 怪 / NPC / 商人 / 祭坛 → 非自由
    # 空地：仅当挂【会触发】的到达事件才是独立节点；已 fire/禁用的事件视作可通行
    if _live_arrive_event(floor, x, y):
        return False
    return True


def _free_cells(state, zone_blocked=None):
    """从英雄格 4-邻接 floodfill 出可零代价到达的自由透明格集合（英雄当前自由块）。"""
    if zone_blocked is None:
        zone_blocked = _zone_blocked(state)
    h = state.hero
    start = (h.x, h.y)
    seen = {start}
    dq = deque([start])
    while dq:
        cx, cy = dq.popleft()
        for dx, dy in _DELTAS:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in seen:
                continue
            if _is_free_tile(state, nx, ny, zone_blocked):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return seen


def partition_floor_blocks(state, zone_blocked=None):
    """整层自由格的 4-邻接连通块【列表】（覆盖式 floodfill，非仅英雄块）。返回 [frozenset(cells), ...]。
    与 _is_free_tile / count_floor_blocks 同口径（后者 = len(本函数) + 自由格合计）。
    块为目标涌现层用：每个零损血连通块 = 一个 GA 目标单元；块身份由初始态 entities/门/事件【纯函数】定
    （与勇者属性无关、单向吸纳只合并不分裂——见 analysis/ga_block_initial_model_diag 实测 A/B 坐实）。
    塔无关：自由格判定全走 _is_free_tile（读引擎通用字段），无任何楼层/怪/道具硬编码。"""
    floor = state.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    if zone_blocked is None:
        zone_blocked = _zone_blocked(state)
    free_all = {(x, y) for y in range(rows) for x in range(cols)
                if _is_free_tile(state, x, y, zone_blocked)}
    seen, blocks = set(), []
    for c in free_all:
        if c in seen:
            continue
        comp, dq = set(), deque([c])
        seen.add(c)
        while dq:
            cx, cy = dq.popleft()
            comp.add((cx, cy))
            for dx, dy in _DELTAS:
                nb = (cx + dx, cy + dy)
                if nb in free_all and nb not in seen:
                    seen.add(nb)
                    dq.append(nb)
        blocks.append(frozenset(comp))
    return blocks


def count_floor_blocks(state, zone_blocked=None):
    """整层自由格的 4-邻接连通块数（覆盖式 floodfill，非仅英雄块）。返回 (块数, 自由格数)。
    报告缩点规模用：朴素「可达格」→ 缩点「块数」的塌缩比例。块列表本体见 partition_floor_blocks
    （本函数 = 它的计数视图；块为目标涌现层直接用 partition_floor_blocks 取块集）。"""
    blocks = partition_floor_blocks(state, zone_blocked)
    return len(blocks), sum(len(b) for b in blocks)


def _bfs_moves(state, free, target):
    """在 free 集合内从英雄格 BFS 到 target，返回 U/D/L/R 动作列表（target 必须 ∈ free）。"""
    h = state.hero
    start = (h.x, h.y)
    if start == target:
        return []
    prev = {start: None}
    dq = deque([start])
    while dq:
        cur = dq.popleft()
        if cur == target:
            break
        cx, cy = cur
        for (dx, dy), mv in _DELTAS.items():
            nb = (cx + dx, cy + dy)
            if nb in free and nb not in prev:
                prev[nb] = (cur, mv)
                dq.append(nb)
    if target not in prev:
        return None
    moves = []
    node = target
    while prev[node] is not None:
        pcell, mv = prev[node]
        moves.append(mv)
        node = pcell
    moves.reverse()
    return moves


# ─── 付代价算子 ─────────────────────────────────────────────────────────────────

def _killable(state, x, y):
    """(x,y) 的怪当前是否可战可杀（damage<hp 才可战，引擎 canBattle）。返回 bool。

    只判战斗胜负，【不】掺「是否独立节点」——后者由 _is_free_tile 独立保证（怪一律非自由格、
    永不并入自由块，故未杀前的残留指纹天然保留，与可不可杀正交）。挂 afterBattle/beforeBattle
    （战斗钩子）或到达事件的怪格【同样可杀】：怪是 noPass，英雄活着踩不上怪格 → 怪格上的任何
    事件都是「怪死后」语义——引擎 step 杀怪即在 _fight_monster 内自然触发 afterBattle；之后那个
    空格若仍挂到达事件，降级为 trigger 节点（_boundary_ops 的 trigger 分支有 e∉_tile_to_enemy
    门控，怪格永不误判为 trigger）。全塔已核对：无任何「活怪格可踩触发剧情」的情形（MT33 单向阀
    走 flower 地形+outEvents 通道、不经本函数；MT40/MT42 怪格到达事件皆为死后通行守卫）。
    历史 bug：旧版把事件钩子并入不可杀 → MT10 骷髅队长(6,1)既非 kill 又非 trigger=无算子死节点、
    boss 过不去。解耦后队长可 kill、afterBattle 开三门、boss 区按新态重算进自由块。"""
    floor = state.floor
    e = floor.entities[y][x]
    mid = floor._tile_to_enemy.get(e)
    if mid is None:
        return False
    h = state.hero
    mon = _build_monster(state, mid)
    res = compute_combat(PlayerState(hp=h.hp, atk=h.atk, def_=h.def_, mdef=h.mdef), mon,
                         has_cross=h.items.get("cross", 0) > 0,
                         has_knife=h.items.get("knife", 0) > 0)
    return res is not None and res.damage is not None and res.damage < h.hp


def _boundary_ops(state, free, cross_floor=False, enable_fly=False, fly_attrs=None):
    """枚举自由块边界上的付代价算子：（跨层时）走楼梯 / 杀怪 / 开钥匙门 / 撞自开假墙 / 撞触发型事件格。
    返回 [(kind, ox, oy, fx, fy, mv)]：从自由格 (fx,fy) 朝 (ox,oy) 发 mv 触发。
    cross_floor=True 时，边界上的 changeFloor 格作 stair 算子（免资源代价的跨层【免费边】，但仍真实
    step() 走过去触发换层、保 firstArrive/落点/剧情副作用）；门禁未满足的楼梯格 step() 不触发换层，
    由 _expand_op 检测后不生成边（§7-B：满足门禁本身=另一个付代价合并，如打 boss）。
    trigger = 边界上挂【会触发的到达事件】的非怪格（NPC/踩格机关）：撞它会改地图（开门/移怪/
    显隐），是改变可达性的算子（地图连通性动态、CLAUDE.md 建图铁律）。撞 choices 型（商人/老人）
    会陷入拦截态，由 search_quotient 检测后裁掉并记录（不强解，留作放开决策依据）。
    挂事件的【怪】走 kill 算子（杀掉后引擎 step 自然触发 afterBattle/到达事件=死后语义）：trigger
    分支 e∉_tile_to_enemy 门控保证怪格永不误判为 trigger，杀后那个空格若仍挂到达事件再降级 trigger。"""
    floor = state.floor
    h = state.hero
    ops = []
    seen_targets = set()
    for (fx, fy) in free:
        for (dx, dy), mv in _DELTAS.items():
            ox, oy = fx + dx, fy + dy
            if (ox, oy) in free or (ox, oy) in seen_targets:
                continue
            rows, cols = len(floor.terrain), len(floor.terrain[0])
            if not (0 <= ox < cols and 0 <= oy < rows):
                continue
            t = floor.terrain[oy][ox]
            e = floor.entities[oy][ox]
            if cross_floor and f"{ox},{oy}" in floor.change_floor:
                ops.append(("stair", ox, oy, fx, fy, mv)); seen_targets.add((ox, oy))
            elif e in floor._tile_to_enemy and _killable(state, ox, oy):
                ops.append(("kill", ox, oy, fx, fy, mv)); seen_targets.add((ox, oy))
            elif t in DOOR_KEY_MAP and h.keys.get(DOOR_KEY_MAP[t], 0) > 0:
                ops.append(("door", ox, oy, fx, fy, mv)); seen_targets.add((ox, oy))
            elif t in AUTO_OPEN_TILES:
                ops.append(("autoopen", ox, oy, fx, fy, mv)); seen_targets.add((ox, oy))
            elif e not in floor._tile_to_enemy and _live_arrive_event(floor, ox, oy):
                ops.append(("trigger", ox, oy, fx, fy, mv)); seen_targets.add((ox, oy))
    # fly 魔杖跨层边（方案B保守子集，仅 enable_fly 开；默认关=逐字节零回归，守 beam 封板）。
    # 不作弊（只少不多）：gate2 = canFlyFrom[cur] ∧ canFlyTo[to]（fly_attrs 排 MT0/MT44/MT50）；
    # hasVisitedFloor 取【精确访问】保守子集（真实引擎 §I.4.1 高索引代理只会更宽，这里故意取窄）；
    # gate1 楼梯连通 = 当前块够到任一楼梯格(接入主链) ∧ [to..cur] 连续主链层全访问过(连通的保守
    # 近似；未逐层实时 canConnect——动态门隔断罕见，且 fly 落点真实 step、不产作弊资源)。fly 不耗
    # HP/不耗道具(constants)，换层走 FLOOR: token 复用引擎真实落点(§I.3.2)。塔无关：canFlyTo/From
    # 由驱动层注入 fly_attrs，floor_ids/visited/change_floor 全读 state，无任何塔特有坐标硬编码。
    if enable_fly and fly_attrs is not None \
            and fly_attrs.get(state.current_floor, {}).get("canFlyFrom", True):
        fids = state.floor_ids
        cur = state.current_floor
        if cur in fids:
            cur_idx = fids.index(cur)
            visited = state.visited_floors
            has_stair = any(f"{fx + dx},{fy + dy}" in floor.change_floor
                            for (fx, fy) in free for (dx, dy) in _DELTAS)
            if has_stair:
                for to in visited:
                    if to == cur or to not in fids:
                        continue
                    if not fly_attrs.get(to, {}).get("canFlyTo", True):
                        continue
                    to_idx = fids.index(to)
                    lo, hi = (to_idx, cur_idx) if to_idx < cur_idx else (cur_idx, to_idx)
                    if all(fids[i] in visited for i in range(lo, hi + 1)):
                        ops.append(("fly", to, None, h.x, h.y, None))
    return ops


def _expand_op(state, free, op, step_fn):
    """展开一个算子为动作序列并推进：走到触发格 (fx,fy) + 发 mv。返回 (new_state, moves) 或 None。
    stair 型（走楼梯）：发 mv 踏上 changeFloor 格 → 引擎 _apply_stair_change 真实换层。若换层未发生
    （门禁 enable=False / 目标层未加载 → 引擎不触发）则返回 None（无跨层边，§7-B 自然门控）。
    trigger 型（撞 NPC/踩格机关）：撞一下先触发事件（引擎对 noPass NPC 是停原格、不移入）；
    若事件清掉了该格实体且未陷拦截态，再发同向一步真正踏入（小偷暗道：撞→开道→走入），
    与钥匙门/假墙的「开了再走入」两步一致。门已开/实体仍在/陷拦截 → 不补步。"""
    kind, ox, oy, fx, fy, mv = op
    if kind == "fly":
        # fly 魔杖：物品原地使用，发 FLOOR:to token 真实换层（落点/副作用由引擎处理，§I.3.2）。
        # gate（canFlyTo/From + 访问 + 连通）已在 _boundary_ops 把关，此处只执行换层；
        # 换层未发生（目标层未加载等）→ current_floor 不变 → 无边（返 None）。
        to_id = ox
        s = step_fn(state, f"FLOOR:{to_id}")
        if s.dead or s.current_floor == state.current_floor:
            return None
        return s, [f"FLOOR:{to_id}"]
    walk = _bfs_moves(state, free, (fx, fy))
    if walk is None:
        return None
    moves = list(walk) + [mv]
    s = state
    for m in moves:
        s = step_fn(s, m)
        if s.dead:
            return None
    if kind == "stair":
        if s.current_floor == state.current_floor:
            return None            # 楼梯未触发（门禁未满足/目标层未加载）→ 无跨层边
        return s, moves
    if (kind == "trigger" and not s.floor._event_intercepting
            and (s.hero.x, s.hero.y) != (ox, oy)):
        s2 = step_fn(s, mv)
        if not s2.dead and (s2.hero.x, s2.hero.y) == (ox, oy):
            s, moves = s2, moves + [mv]
    return s, moves


def _absorb(state, step_fn):
    """吸收当前自由块内所有道具（走过去拾，顺序无关）。装备改 atk 会扩边界 → 重跑到不动点。
    返回 (new_state, moves)。块内零损血，路径长短不影响价值（唯一目标 HP）。"""
    moves_all = []
    s = state
    while True:
        free = _free_cells(s)
        floor = s.floor
        target = None
        for (x, y) in free:
            if floor.entities[y][x] in floor._tile_to_item:
                target = (x, y)
                break
        if target is None:
            return s, moves_all
        path = _bfs_moves(s, free, target)
        if not path:                       # target 即英雄格（理论上 free 含英雄格无道具）→ 防御
            return s, moves_all
        for m in path:
            s = step_fn(s, m)
            if s.dead:
                return s, moves_all
        moves_all.extend(path)


def _resolve_choices(state, base_moves, step_fn, max_depth=64):
    """allow_purchase 专用：把陷入 choices 拦截态的子态，按【每个选项分支】真实 step CHOICE:i 解开，
    枚举到脱离拦截为止，返回 [(已脱离拦截子态, 含 CHOICE token 的动作序列 tuple), ...]。
    祭坛「买→再入循环」链由 (gold/atk/def/mdef/钥匙) 去重天然有界（每买一次 gold 降→状态变→不重复，
    选离开 / 买到买不动即脱离）；max_depth 仅作失控护栏。「买几次」自收敛 = 价值决定，绝不写死。
    只回非拦截态（深度耗尽 / 空 choices 仍拦截者丢弃，等价老版 intercept 跳过）。
    塔无关：CHOICE / _event_pending_choices 是通用引擎拦截口径，solver 不认任何塔特有商店逻辑。"""
    out = []
    seen = set()
    stack = [(state, base_moves, 0)]
    while stack:
        s, mv, depth = stack.pop()
        if not s.floor._event_intercepting:
            out.append((s, mv))
            continue
        if depth >= max_depth:
            continue                       # 失控护栏：丢弃仍拦截态
        choices = s.floor._event_pending_choices
        if not choices:
            continue                       # 拦截但无选项（非 choices 型）：丢弃，等价老版跳过
        h = s.hero
        key = (s.current_floor, h.x, h.y, h.gold, h.atk, h.def_, h.mdef,
               tuple(sorted((k, v) for k, v in h.keys.items() if v)))
        if key in seen:
            continue
        seen.add(key)
        for i in range(len(choices)):
            nxt = step_fn(s, f"CHOICE:{i}")
            if nxt.dead:
                continue
            stack.append((nxt, mv + (f"CHOICE:{i}",), depth + 1))
    return out


# ─── 商图指纹 + 搜索 ──────────────────────────────────────────────────────────

def _closed_door_cells(floor):
    """当前层仍关着的门格集合（terrain ∈ 门类 tile）。开门 = 该格 terrain→0 移出本集 → 身份维变。
    塔无关：门类 tile 取自通用 DOOR_KEY_MAP/SPECIAL_DOOR/AUTO_OPEN_TILES，不写死任何塔特有坐标；
    只读当前 terrain，不解释任何事件（区别于『修自由格』须判事件条件分支=解释自定义事件，踩红线）。"""
    return frozenset((x, y)
                     for y, row in enumerate(floor.terrain)
                     for x, t in enumerate(row)
                     if t in _DOOR_TILES)


def _qfp(state, free, distinguish_doors=False):
    """商图身份维：当前层 + 自由块（frozenset 自由格，剔除换层格）+ flags + 全局开关。自由格集合
    已编码「哪些怪/门已消除」（消除即并入自由块）→ 不同可达态 = 不同指纹。持有资源不入（归价值维）。
    剔除换层格：跨层落点英雄正踩楼梯格 vs 吸收后离开，可达块本体相同 → 身份维不应因「是否正踩楼梯」
    分裂（楼梯格不连通 floodfill、仅作英雄落点单格出现，剔除不会并掉两个真实分量）。

    distinguish_doors（默认 False=字节零回归，beam/历史调用全走此路、指纹逐字段不变）：True 时把
    「当前层仍关着的门格集合」追加进身份维。修『红门支配 bug』——开门若落到惰性事件格(自由块不增、
    无 flag)，则『开门态(少钥)』与『未开门态(多钥)』身份维全同 → 开门态被 Pareto 支配剪掉 → boss
    真起点搜不通。把门开闭编码进身份后两态分指纹、开门态不再被剪。仅课程学习路开启（守 beam 红线）。"""
    h = state.hero
    flags = tuple(sorted((k, v) for k, v in h.flags.items()
                         if isinstance(v, (int, float, str, bool))))
    cf_xy = {tuple(map(int, k.split(","))) for k in state.floor.change_floor}
    ident = frozenset(c for c in free if c not in cf_xy)
    base = (state.current_floor, ident, flags,
            state.auto_mode, state.dead, state.won)
    if not distinguish_doors:
        return base
    return base + (_closed_door_cells(state.floor),)


def _stairs_key(state):
    """beam 分坑维（推进度签名）：(当前层, 当前自由块边界上可达的 changeFloor 楼梯格集合)。
    「可达」与 _boundary_ops 的 stair 算子同口径——楼梯格 ∈ change_floor 且 4-邻接某自由格即算
    本块边界上可走的楼梯。语义：打开了通往某楼梯的路（多杀一只怪/多开一道门把上行梯并进自由块）的态
    自成一坑、被 beam 强制保护，与原地刷怪攒属性的 grinder 分离 → 修『爬楼 climber 中途属性低、被
    低层 grinder 占满 K 槽挤死』。比纯 current_floor 细（同层内"够到上行梯"vs"没够到"分两坑），比
    完整块组合粗（楼梯数有界 → 永不退化成每态一坑）。塔无关：change_floor 是通用引擎数据，可达性由
    floodfill 实算，不写死任何塔特有坐标。"""
    floor = state.floor
    cf_xy = {tuple(map(int, k.split(","))) for k in floor.change_floor}
    if not cf_xy:
        return (state.current_floor, frozenset())
    free = _free_cells(state)
    reachable = set()
    for fx, fy in free:
        for dx, dy in _DELTAS:
            nb = (fx + dx, fy + dy)
            if nb in cf_xy:
                reachable.add(nb)
    return (state.current_floor, frozenset(reachable))


# ─── beam 控宽（按 BFS wave 截断；V/保护维口径全在 solver/beam.py，塔无关）──────────────

_BeamPt = namedtuple("_BeamPt", ["state", "actions"])   # beam_select 只需 .state，落盘需 .actions


def _beam_truncate_wave(next_pts, beam_k, st, wave_idx, sink, future=None, diversity_key_fn=None,
                        score_override=None, score_extra=None):
    """把一个 BFS wave 的 admitted 子态 [(state, acts)] 按【Δ形式 V + 保护维 Pareto 骨架】截到
    beam_k 个（口径见 solver/beam.py：V=HP−Σ_R cost 对杀怪中性；保护维=消耗道具全保+钥匙按当前层
    门数封顶硬保护）。被截点交 sink 落盘审计（红线：不静默丢）。返回保留的 [(state, acts)]。
    函数级 import solver.beam：beam 模块级 `from solver.quotient import _killable`，此处反向调用
    若写模块级 import 会成循环依赖，故延迟到调用时导入（运行期两模块均已加载，无副作用）。
    future（FutureCfg 或 None）：远区势能 cfg，透传给打分（None→V 与原版字节一致，见 beam.py）。
    score_override（可调用 state→数值 或 None）：驱动层注入的【替换式】打分键（如 V_zone=HP−D）。
      None（默认）→ 走原 score_points/equiv_hp_over_roster（区势能 future 口径）、与原版字节一致；
      给函数 → 直接用它当 beam 排序键（旁路 roster 单遍打分），solver 不 import 任何塔特有模块（闭包
      持塔特有 zone 在驱动层 extract/）。两者互斥、override 优先；λ=0 零回归约定=驱动层在 λ=0 时传 None。
    score_extra（可调用 state→数值 或 None）：【加性】引导项，叠加到区势能基分上（base + extra(st)），
      只在 override=None 的区势能打分路生效（与 override 替换式互斥）。None（默认）→ 字节零回归；给函数
      → 驱动层注入的"大件 pull 引导"（β_big·pull_大件，只进排序键、不进 value_vector 剪枝键）。塔无关：
      闭包持塔特有 zone/大件判据在驱动层 extract/，solver 只透传不解释。
    塔无关：V/保护维全由引擎 compute_combat + DOOR_KEY_MAP 算，本函数无任何楼层/怪/道具/阈值硬编码。"""
    from solver.beam import (score_points, beam_select, equiv_hp_over_roster,
                             beam_protection_overflow)
    pts = [_BeamPt(state=c, actions=a) for (c, a) in next_pts]
    overflow, skel = beam_protection_overflow(pts, beam_k, diversity_key_fn=diversity_key_fn)
    if score_override is not None:
        score_fn = score_override                            # 注入式替换打分（如 V_zone），旁路 roster
    else:
        roster, big, scores = score_points(pts, future=future, extra=score_extra)  # 单遍 V：选点/落盘复用同批缓存
        score_fn = lambda stt: scores[id(stt)] if id(stt) in scores \
            else equiv_hp_over_roster(stt, roster, big, future=future, extra=score_extra)
    kept, cut = beam_select(pts, beam_k, score_fn=score_fn, diversity_key_fn=diversity_key_fn)
    st.beam_cut_total += len(cut)
    st.beam_waves_truncated += 1
    if overflow:
        st.beam_overflow_waves += 1
    if sink is not None:
        sink([{"wave": wave_idx, "floor": p.state.current_floor,
               "V": score_fn(p.state), "value": value_vector(p.state),
               "hp": p.state.hero.hp, "atk": p.state.hero.atk, "def": p.state.hero.def_,
               "actions": "".join(p.actions)} for p in cut])
    return [(p.state, p.actions) for p in kept]


def search_quotient(entry_state, goal_cell, step_fn, max_states=2_000_000, cross_floor=False,
                    beam_k=None, beam_cut_sink=None, on_admit=None, beam_future=None,
                    beam_diversity=None, beam_score_fn=None, allow_purchase=False,
                    beam_score_extra=None, distinguish_doors=False, enable_fly=False, fly_attrs=None):
    """块图搜索：从 entry_state 出发，停在 goal_cell 且出口价值 Pareto 最优。
    输出契约对齐 solver.search.search_segment（found/goal_frontier/goal_frontier_actions/统计）。
    cross_floor=False（默认，phase1 段内）：任何离层子态裁掉（跨层由 phase1 forced 骨架处理）。
    cross_floor=True（跨层缩点）：楼梯(changeFloor)格作 stair 算子，真实 step() 触发换层、免资源
      代价生成跨层子态；事件传送类离层（MT3 重置/MT40/MT24 结局）仍裁掉（第一步只接楼梯，见 §8）。
      调用方须保证 entry_state._single_floor_copy=False（多层安全深拷），否则共享引用污染兄弟分支。
    beam_k=None（默认）：无控宽，穷尽 Pareto 前沿（单层段内 / 小搜索用）。BFS 按 wave 推进（逐层
      FIFO，与原扁平 deque 同处理序：所有深度 d 态先于 d+1、组内按生成序）→ 输出逐字段不变。
    beam_k 设定（跨层大搜索控宽）：每个 wave 把本层 admitted 子态按 Δ形式 V + 保护维 Pareto 骨架
      （solver/beam.py）截到 beam_k；被截点经 beam_cut_sink 落盘审计（红线不静默丢）。visited 无损
      Pareto 去重与 beam 有损截断正交叠加：被截态留在 visited，他路若以【更优】向量重达同指纹仍放行。
    beam_cut_sink(records)：回调，records=本 wave 被截点 [{wave,floor,V,value,hp,atk,def,actions}]；
      None 则只计数不落盘。塔无关：驱动层(extract/)持有文件路径，solver 不写死任何路径。
    on_admit(child, actions)：每个【通过去重入队】的子态回调一次（含日后被 beam 截掉的——「到达过」
      即触发）；供驱动层做诊断统计（如各层可达最优属性 / 爬升轨迹）。None 则不调用、零开销。
    beam_future（FutureCfg 或 None）：远区势能 cfg（修 R 近视、给"上层盾对整区减伤"以 V 信号），透传
      到 beam 打分。None（默认）→ V 项=0、与原版字节一致；驱动层(extract/)用 build_future_roster
      建集后传入。塔无关：roster 由共享表读全塔静态地图，solver 不写死任何塔特有数据。
    beam_diversity（None / "floor" / "stairs"）：beam 截断的【分坑保护维】，修多样性饥饿（低层刷怪
      便宜货占满 K 槽、爬楼 climber 被挤死）。None（默认）→ 单坑、与原版字节一致；"floor" → 按
      current_floor 分坑，每层各保其保护骨架；"stairs" → 按 (current_floor, 当前块可达楼梯集) 分坑
      （推进度签名，比楼层细：同层内"够到上行梯 vs 没够到"分两坑，强制保护 climber）。塔无关：key 从
      state 读，不写死维度。
    beam_score_fn（可调用 state→数值 或 None）：beam 截断的【替换式】打分键，透传给 _beam_truncate_wave
      的 score_override。None（默认）→ 走原区势能/roster 打分（与原版字节一致）；给函数 → 直接当排序键
      （如 V_zone=HP−D，驱动层 extract/ 闭包持塔特有 zone 注入）。与 beam_future 互斥、它优先。λ=0 零回归
      约定=驱动层在 λ=0 时传 None。塔无关：solver 不 import 任何塔特有模块，打分逻辑由注入闭包决定。
    beam_score_extra（可调用 state→数值 或 None）：beam 截断的【加性】引导项，与 beam_future 区势能基分
      相叠（base+extra），透传给 _beam_truncate_wave 的 score_extra。None（默认）→ 字节零回归；给函数 →
      驱动层注入"大件 pull 引导"（只进 beam 排序键、不进 value_vector 剪枝键，守红线）。与 beam_score_fn
      替换式互斥（仅区势能打分路生效）。塔无关：闭包持塔特有大件判据在 extract/，solver 只透传。
    allow_purchase（默认 False）：是否解开 choices 拦截态（商人/祭坛等付金购买事件）。False（默认）→
      撞 choices 即记 intercept_locs 并跳过、与原版【字节一致】（搜索结构性买不了任何东西）；True →
      对每个拦截子态用 _resolve_choices 按选项分支真实 step CHOICE，把「买/不买、买 N 次」全展开成
      并列子态进同一去重/入队管线，让「买不买、买几次」由价值（Pareto+beam）自行收敛，不写死次数。
      这是补【购买能力】、非加估值项；intercept_locs 两路都照记（开时=买过的点也留痕，便于审计）。
    distinguish_doors（默认 False）：是否把「当前层仍关着的门格集合」并入商图身份维（_qfp）。False
      （默认）→ 指纹与历史逐字段一致、beam 字节零回归；True → 修『红门支配 bug』（开门落惰性事件格时
      开门态被未开门态 Pareto 支配剪掉、boss 真起点搜不通），仅课程学习路开启。详见 _qfp 注释。
    enable_fly（默认 False）：是否启用 fly 魔杖跨层边（方案B保守子集，见 _boundary_ops fly 分支注释）。
      False（默认）→ 不生成任何 fly 算子、与历史逐字节一致（守 beam 封板，仅方向2开）；True → 生成
      "当前块够到楼梯 ∧ 精确访问过 ∧ canFlyTo/From 允许（fly_attrs 排 MT0/MT44/MT50）∧ [to..cur] 主链
      连续访问"的 fly 边，真实 step FLOOR: token 换层（不耗 HP/道具）。须同时传 fly_attrs，否则报错。
    fly_attrs（dict 或 None）：{floor_id: {canFlyTo, canFlyFrom}}，由驱动层从 data/<塔>/fly_attrs.json
      注入（塔无关）。enable_fly=True 时必给；enable_fly=False 时忽略。"""
    goal_floor, gx, gy = goal_cell
    if enable_fly and fly_attrs is None:
        raise ValueError(
            "enable_fly=True 须提供 fly_attrs（canFlyTo/canFlyFrom 表）；"
            "缺表则默认 True 兜底会作弊飞入 MT0/MT44/MT50（隐藏层/结局层）")

    if beam_diversity is None:
        div_fn = None
    elif beam_diversity == "floor":
        div_fn = lambda s: s.current_floor
    elif beam_diversity == "stairs":
        div_fn = _stairs_key
    else:
        raise ValueError(
            f"未知 beam_diversity={beam_diversity!r}（仅支持 None / 'floor' / 'stairs'）")

    st = SearchResult(found=False, actions=[], final_hp=0)
    st.goal_frontier = []
    st.goal_frontier_actions = []
    st.n_waves = 0                  # BFS wave（深度层）数
    st.beam_cut_total = 0          # beam 累计被截点数（落盘审计总量）
    st.beam_waves_truncated = 0    # 触发截断的 wave 数
    st.beam_overflow_waves = 0     # 保护骨架≥K 让位的 wave 数（保护未全保警告）
    st.wave_log = []               # 每 wave (入宽, 原始出宽, 截后出宽)：膨胀曲线/控宽诊断
    goal_pts = []   # (vec, actions) 出口多维 Pareto 前沿

    start, start_moves = _absorb(entry_state, step_fn)
    visited = {}
    free0 = _free_cells(start)
    visited[_qfp(start, free0, distinguish_doors)] = [value_vector(start)]
    st.states_admitted = 1
    n_ops_total = 0
    block_sizes_seen = []
    intercept_locs = set()   # 撞 choices 型事件(商人/老人/祭坛)→陷拦截态，记录不强解

    wave = [(start, tuple(start_moves))]
    while wave:
        if len(wave) > st.frontier_peak:
            st.frontier_peak = len(wave)
        next_pts = []   # 本 wave 全体 admitted 子态（下一 wave 候选，beam 在此截断）
        for state, acts in wave:
            st.states_expanded += 1
            free = _free_cells(state)
            block_sizes_seen.append(len(free))

            # 目标可达（在当前自由块内）→ 走过去记一个出口前沿点
            if state.current_floor == goal_floor and (gx, gy) in free:
                walk = _bfs_moves(state, free, (gx, gy))
                if walk is not None:
                    gs = state
                    ok = True
                    for m in walk:
                        gs = step_fn(gs, m)
                        if gs.dead:
                            ok = False
                            break
                    if ok and (gs.hero.x, gs.hero.y) == (gx, gy):
                        gvec = value_vector(gs)
                        gacts = acts + tuple(walk)
                        if not any(_ge_all(v, gvec) for v, _ in goal_pts):
                            goal_pts = [(v, a) for (v, a) in goal_pts if not _ge_all(gvec, v)]
                            goal_pts.append((gvec, gacts))
                        st.goal_hits += 1

            # 枚举付代价算子，逐个展开推进
            ops = _boundary_ops(state, free, cross_floor, enable_fly, fly_attrs)
            n_ops_total += len(ops)
            for op in ops:
                res = _expand_op(state, free, op, step_fn)
                st.states_generated += 1
                if res is None:
                    continue
                child, op_moves = res
                if child.floor._event_intercepting:
                    intercept_locs.add((op[1], op[2]))   # choices 事件：陷拦截态（记录留痕）
                    if not allow_purchase:
                        continue                          # 老版口径：无 CHOICE→跳过（字节一致）
                    resolved = _resolve_choices(child, tuple(op_moves), step_fn)  # 解开买/不买/买N次
                else:
                    resolved = [(child, op_moves)]
                for rchild, rmoves in resolved:
                    if rchild.current_floor != state.current_floor:
                        # 离层子态：单层版裁掉；跨层版放行楼梯边；fly 边(enable_fly)独立放行(不依赖
                        # cross_floor)；事件传送(MT3重置/MT40/MT24结局/门禁传送)仍排除
                        if not (op[0] == "fly" or (cross_floor and op[0] == "stair")):
                            continue
                    rchild, abs_moves = _absorb(rchild, step_fn)
                    if rchild.dead:
                        continue
                    child_free = _free_cells(rchild)
                    fp = _qfp(rchild, child_free, distinguish_doors)
                    cvec = value_vector(rchild)
                    cur = visited.get(fp)
                    if cur is not None and any(_ge_all(v, cvec) for v in cur):
                        continue
                    if cur is None:
                        visited[fp] = [cvec]
                    else:
                        visited[fp] = [v for v in cur if not _ge_all(cvec, v)] + [cvec]
                    st.states_admitted += 1
                    child_acts = acts + tuple(rmoves) + tuple(abs_moves)
                    if on_admit is not None:
                        on_admit(rchild, child_acts)
                    next_pts.append((rchild, child_acts))
                    if st.states_generated >= max_states:
                        st.hit_cap = True
                        break
                if st.hit_cap:
                    break
            if st.hit_cap:
                break

        st.n_waves += 1
        raw_out = len(next_pts)
        # beam 控宽：本 wave 子态超 K 则按 V+保护维截断、落盘被截点（beam_k=None 时整段跳过→零回归）
        if beam_k is not None and len(next_pts) > beam_k:
            next_pts = _beam_truncate_wave(next_pts, beam_k, st, st.n_waves - 1,
                                           beam_cut_sink, beam_future, div_fn, beam_score_fn,
                                           score_extra=beam_score_extra)
        st.wave_log.append((len(wave), raw_out, len(next_pts)))
        wave = next_pts
        if st.hit_cap:
            break

    st.distinct_fingerprints = len(visited)
    st.fp_by_floor = Counter(fp[0] for fp in visited)   # 跨层膨胀诊断：各层指纹数（fp[0]=current_floor）
    st.floors_seen = sorted(st.fp_by_floor)
    st.n_blocks_peak = max(block_sizes_seen) if block_sizes_seen else 0
    st.n_ops_total = n_ops_total
    st.intercept_locs = sorted(intercept_locs)
    if goal_pts:
        best = max(goal_pts, key=lambda t: t[0]["hp"])
        st.found = True
        st.final_hp = best[0]["hp"]
        st.actions = list(best[1])
        st.claimed_state = None
        st.goal_frontier = [v for v, _ in goal_pts]
        st.goal_frontier_actions = [list(a) for _, a in goal_pts]
    return st
