"""塔无关：缩点商图搜索（连通块抽象 + 付代价合并算子）。

动机（实测）：朴素 BFS 在富实体层把「站位 × 拾取幂集」全展开 → MT3 撞 2M cap、23 分钟。
本层把「无损血自由连通区」缩成块——块内坐标不进状态、块内免费资源（钥匙/宝石/装备/血瓶，
拿到即兑现）自动吸（顺序无关），状态只记「英雄当前自由块 = 哪些付代价对象已消除」。

口径（玩家 2026-06-06 裁定）：
  · 块内自动吸：所有道具（含血瓶，第一版从简、不做跨块 bank 开关；见 docs/solver-design.md
    「血瓶简化」+ 升级条件）。
  · 付代价合并算子：可击杀怪（damage<hp 才可战，否则硬墙节点）、钥匙门（持钥匙才可开）、
    自开假墙。执行 = 走到对象旁 + 触发，引擎 step 做真实合并（扣血/消钥匙/删墙）。
  · 独立节点（不并入块，保留可达性差异 = 残留指纹）：挂事件格/怪（MT33 硬约束）、当前打不动
    的怪、NPC/商人/老人/祭坛、特殊门、领域/夹击/阻击伤格（块内须零损血）。
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
    _is_adjacent, _build_monster,
)
from sim.combat import PlayerState, compute_combat
from solver.search import SearchResult, _value_map, _ge_all

value_vector = _value_map

_DELTAS = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}


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
    if isinstance(ev, dict) and not ev.get("enable", True):
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


def count_floor_blocks(state, zone_blocked=None):
    """整层自由格的 4-邻接连通块数（覆盖式 floodfill，非仅英雄块）。返回 (块数, 自由格数)。
    报告缩点规模用：朴素「可达格」→ 缩点「块数」的塌缩比例。与 _is_free_tile 同口径。"""
    floor = state.floor
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    if zone_blocked is None:
        zone_blocked = _zone_blocked(state)
    free_all = {(x, y) for y in range(rows) for x in range(cols)
                if _is_free_tile(state, x, y, zone_blocked)}
    seen, nblk = set(), 0
    for c in free_all:
        if c in seen:
            continue
        nblk += 1
        dq = deque([c])
        seen.add(c)
        while dq:
            cx, cy = dq.popleft()
            for dx, dy in _DELTAS:
                nb = (cx + dx, cy + dy)
                if nb in free_all and nb not in seen:
                    seen.add(nb)
                    dq.append(nb)
    return nblk, len(free_all)


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
    """(x,y) 的怪当前是否可战可杀（damage<hp 才可战，引擎 canBattle）。返回 bool。"""
    floor = state.floor
    e = floor.entities[y][x]
    mid = floor._tile_to_enemy.get(e)
    if mid is None:
        return False
    loc = f"{x},{y}"
    if (_live_arrive_event(floor, x, y) or loc in floor.after_battle
            or loc in floor.before_battle):
        return False                # 挂事件怪 = 独立节点（到达事件未消/战斗钩子），MT33 约束
    h = state.hero
    mon = _build_monster(state, mid)
    res = compute_combat(PlayerState(hp=h.hp, atk=h.atk, def_=h.def_, mdef=h.mdef), mon,
                         has_cross=h.items.get("cross", 0) > 0,
                         has_knife=h.items.get("knife", 0) > 0)
    return res is not None and res.damage is not None and res.damage < h.hp


def _boundary_ops(state, free, cross_floor=False):
    """枚举自由块边界上的付代价算子：（跨层时）走楼梯 / 杀怪 / 开钥匙门 / 撞自开假墙 / 撞触发型事件格。
    返回 [(kind, ox, oy, fx, fy, mv)]：从自由格 (fx,fy) 朝 (ox,oy) 发 mv 触发。
    cross_floor=True 时，边界上的 changeFloor 格作 stair 算子（免资源代价的跨层【免费边】，但仍真实
    step() 走过去触发换层、保 firstArrive/落点/剧情副作用）；门禁未满足的楼梯格 step() 不触发换层，
    由 _expand_op 检测后不生成边（§7-B：满足门禁本身=另一个付代价合并，如打 boss）。
    trigger = 边界上挂【会触发的到达事件】的非怪格（NPC/踩格机关）：撞它会改地图（开门/移怪/
    显隐），是改变可达性的算子（地图连通性动态、CLAUDE.md 建图铁律）。撞 choices 型（商人/老人）
    会陷入拦截态，由 search_quotient 检测后裁掉并记录（不强解，留作放开决策依据）。
    挂事件的【怪】= 独立节点（MT33 约束），不在此列为 trigger（_killable 已排除）。"""
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
    return ops


def _expand_op(state, free, op, step_fn):
    """展开一个算子为动作序列并推进：走到触发格 (fx,fy) + 发 mv。返回 (new_state, moves) 或 None。
    stair 型（走楼梯）：发 mv 踏上 changeFloor 格 → 引擎 _apply_stair_change 真实换层。若换层未发生
    （门禁 enable=False / 目标层未加载 → 引擎不触发）则返回 None（无跨层边，§7-B 自然门控）。
    trigger 型（撞 NPC/踩格机关）：撞一下先触发事件（引擎对 noPass NPC 是停原格、不移入）；
    若事件清掉了该格实体且未陷拦截态，再发同向一步真正踏入（小偷暗道：撞→开道→走入），
    与钥匙门/假墙的「开了再走入」两步一致。门已开/实体仍在/陷拦截 → 不补步。"""
    kind, ox, oy, fx, fy, mv = op
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


# ─── 商图指纹 + 搜索 ──────────────────────────────────────────────────────────

def _qfp(state, free):
    """商图身份维：当前层 + 自由块（frozenset 自由格，剔除换层格）+ flags + 全局开关。自由格集合
    已编码「哪些怪/门已消除」（消除即并入自由块）→ 不同可达态 = 不同指纹。持有资源不入（归价值维）。
    剔除换层格：跨层落点英雄正踩楼梯格 vs 吸收后离开，可达块本体相同 → 身份维不应因「是否正踩楼梯」
    分裂（楼梯格不连通 floodfill、仅作英雄落点单格出现，剔除不会并掉两个真实分量）。"""
    h = state.hero
    flags = tuple(sorted((k, v) for k, v in h.flags.items()
                         if isinstance(v, (int, float, str, bool))))
    cf_xy = {tuple(map(int, k.split(","))) for k in state.floor.change_floor}
    ident = frozenset(c for c in free if c not in cf_xy)
    return (state.current_floor, ident, flags,
            state.auto_mode, state.dead, state.won)


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


def _beam_truncate_wave(next_pts, beam_k, st, wave_idx, sink, future=None, diversity_key_fn=None):
    """把一个 BFS wave 的 admitted 子态 [(state, acts)] 按【Δ形式 V + 保护维 Pareto 骨架】截到
    beam_k 个（口径见 solver/beam.py：V=HP−Σ_R cost 对杀怪中性；保护维=消耗道具全保+钥匙按当前层
    门数封顶硬保护）。被截点交 sink 落盘审计（红线：不静默丢）。返回保留的 [(state, acts)]。
    函数级 import solver.beam：beam 模块级 `from solver.quotient import _killable`，此处反向调用
    若写模块级 import 会成循环依赖，故延迟到调用时导入（运行期两模块均已加载，无副作用）。
    future（FutureCfg 或 None）：远区势能 cfg，透传给打分（None→V 与原版字节一致，见 beam.py）。
    塔无关：V/保护维全由引擎 compute_combat + DOOR_KEY_MAP 算，本函数无任何楼层/怪/道具/阈值硬编码。"""
    from solver.beam import (score_points, beam_select, equiv_hp_over_roster,
                             beam_protection_overflow)
    pts = [_BeamPt(state=c, actions=a) for (c, a) in next_pts]
    overflow, skel = beam_protection_overflow(pts, beam_k, diversity_key_fn=diversity_key_fn)
    roster, big, scores = score_points(pts, future=future)   # 单遍 V：选点/落盘复用同批缓存
    score_fn = lambda stt: scores[id(stt)] if id(stt) in scores \
        else equiv_hp_over_roster(stt, roster, big, future=future)
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
                    beam_diversity=None):
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
      state 读，不写死维度。"""
    goal_floor, gx, gy = goal_cell

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
    visited[_qfp(start, free0)] = [value_vector(start)]
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
            ops = _boundary_ops(state, free, cross_floor)
            n_ops_total += len(ops)
            for op in ops:
                res = _expand_op(state, free, op, step_fn)
                st.states_generated += 1
                if res is None:
                    continue
                child, op_moves = res
                if child.floor._event_intercepting:
                    intercept_locs.add((op[1], op[2]))   # choices 事件：陷拦截态，无 CHOICE 口径→跳过+记录
                    continue
                if child.current_floor != state.current_floor:
                    # 离层子态：单层版一律裁掉；跨层版只放行楼梯边，事件传送(重置/结局/门禁传送)排除
                    if not cross_floor or op[0] != "stair":
                        continue
                child, abs_moves = _absorb(child, step_fn)
                if child.dead:
                    continue
                child_free = _free_cells(child)
                fp = _qfp(child, child_free)
                cvec = value_vector(child)
                cur = visited.get(fp)
                if cur is not None and any(_ge_all(v, cvec) for v in cur):
                    continue
                if cur is None:
                    visited[fp] = [cvec]
                else:
                    visited[fp] = [v for v in cur if not _ge_all(cvec, v)] + [cvec]
                st.states_admitted += 1
                child_acts = acts + tuple(op_moves) + tuple(abs_moves)
                if on_admit is not None:
                    on_admit(child, child_acts)
                next_pts.append((child, child_acts))
                if st.states_generated >= max_states:
                    st.hit_cap = True
                    break
            if st.hit_cap:
                break

        st.n_waves += 1
        raw_out = len(next_pts)
        # beam 控宽：本 wave 子态超 K 则按 V+保护维截断、落盘被截点（beam_k=None 时整段跳过→零回归）
        if beam_k is not None and len(next_pts) > beam_k:
            next_pts = _beam_truncate_wave(next_pts, beam_k, st, st.n_waves - 1,
                                           beam_cut_sink, beam_future, div_fn)
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
