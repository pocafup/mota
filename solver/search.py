"""塔无关：单层段最优搜索（MVP，朴素 BFS + Pareto 支配去重）。

把注入的 step 当确定性转移函数，对 {U,D,L,R} 四个移动动作做 BFS，
求「停在目标格、且 Pareto 最优（默认看 HP）」的动作序列。

塔无关：入口层 id、目标格、step 全部由调用方注入；本文件无任何
楼层编号 / 怪物 / 道具 / 阈值硬编码。可达性不预计算——每一步都由
注入的 step 从「当前 state」实时判定（撞墙 / 门 / 钥匙 / 活怪都交给 step）。

剪枝（均为确定性引擎下的安全剪枝）：
  · 死亡       —— step 后 dead=True 的子态丢弃（HP≤0 已被引擎冻结）。
  · 离开入口层 —— step 后 current_floor 变（踩楼梯/事件切层）即出界，丢弃。
  · 无变化动作 —— 撞墙/打不动/没钥匙的门：位置+地图+属性全不变，
                  指纹与父相同且向量不更优 → 被 Pareto 去重自然丢弃。

正确性依据（确定性 MDP 的 Pareto 支配）：到达「相同离散指纹」
(当前层 id + 位置 + 当前层地形/实体 + flags + 已触发 afterBattle) 的两条路径，
若一条在所有「越多越好」维度(HP/攻/防/魔防/金/击杀/各类钥匙·道具)上
支配-或-等于另一条，则被支配者的任意后续都能被支配者复制且不更差 →
安全剪掉被支配者，不丢最优解。
"""
from collections import deque
from dataclasses import dataclass

MOVES = ("U", "D", "L", "R")


@dataclass
class SearchResult:
    found: bool
    actions: list                 # 到达目标格的动作序列（U/D/L/R）
    final_hp: int                 # 搜索宣称的出口 HP（待裁判独立重放核对）
    claimed_state: object = None  # 搜索内部 step 推进得到的终态对象
    goal_frontier: list = None    # 到达目标格的多维 Pareto 前沿（list[value_map]）
    # —— 统计（供性能报告 / profile）——
    states_expanded: int = 0      # 出队并展开的状态数
    states_generated: int = 0     # step 产出的子状态数（≈ step 调用数）
    states_admitted: int = 0      # 通过 Pareto 去重、真正入队的状态数
    frontier_peak: int = 0        # 队列长度峰值（内存压力指示）
    distinct_fingerprints: int = 0
    goal_hits: int = 0            # 到达目标格的次数
    hit_cap: bool = False         # 是否触发 max_states 上限提前终止


def _floor_fingerprint(state):
    """离散指纹：捕捉影响可达性的一切地图状态。属性不入指纹，交给 Pareto。"""
    f = state.floors[state.current_floor]
    terrain = tuple(map(tuple, f.terrain))
    entities = tuple(map(tuple, f.entities))
    flags = tuple(sorted(
        (k, v) for k, v in state.hero.flags.items()
        if isinstance(v, (int, float, str, bool))
    ))
    done_ab = tuple(sorted(f._done_after_battle))
    return (state.current_floor, state.hero.x, state.hero.y,
            terrain, entities, flags, done_ab)


def _value_map(state):
    """「越多越好」资源向量：用于 Pareto 支配比较。"""
    h = state.hero
    m = {"hp": h.hp, "atk": h.atk, "def": h.def_, "mdef": h.mdef,
         "gold": h.gold, "kill": h.kill_count}
    for k, v in h.keys.items():
        if isinstance(v, (int, float)):
            m["key:" + k] = v
    for k, v in h.items.items():
        if isinstance(v, (int, float)):
            m["item:" + k] = v
    return m


def _gives_hp_on_pickup(idata):
    """数据驱动判定：拾取该道具是否【增加 HP】（即血瓶类消耗品）。

    依据 items.json 的 pickup 效果结构（与引擎 _apply_item_effect 同口径）：
    type=='stat' 且 stat=='hp'，或 type=='multi' 含一条 stat=='hp' 的 op。
    不写死任何 id / 数值——换塔自动适配。"""
    if not idata:
        return False
    effect = idata.get("pickup")
    if not isinstance(effect, dict):
        return False
    t = effect.get("type")
    if t == "stat":
        return effect.get("stat") == "hp"
    if t == "multi":
        return any(op.get("stat") == "hp" for op in effect.get("ops", ()))
    return False


def _remaining_items(state):
    """当前层地图上「尚未拾取」的【HP 消耗品】(血瓶类)普查——数据驱动区分，塔无关。

    出口价值不止「持有」，还含地图上还留着多少【可后取的 HP 储备】：血瓶留在地上 =
    低血时回头吃 / 配合夹击的战略储备，是「留在地上 ≈ 银行里的 HP」那种可两地等价的储备，
    必须计入出口价值（同持有属性下，留着血瓶的出口 Pareto 优于已吃光的）。

    【只数 HP 消耗品】——宝石/装备(永久增益)与钥匙(硬通货)【不】计入地图剩余：它们拿到才
    兑现(已在持有维 atk/def/mdef/key:* 体现)，留在地上不是优点(该拿就拿)。把三者一视同仁
    当「剩着更好」是错的——A 段实证会让「少拿/不拿」的退化点全成非支配点(前沿从 8 炸到
    143、HP=22 也入前沿)。区分依据 items.json 的 pickup 效果(给 HP=消耗品)，不写死 id。

    只用于【出口前沿】比较；不入内部指纹去重——同指纹地图相同、剩余必然相同。维度键加
    'map:' 前缀，与持有维 'key:'/'item:' 区分。玩家 2026-06-05 裁定「数据驱动区分」，见
    docs/solver-design.md。"""
    f = state.floors[state.current_floor]
    t2i = f._tile_to_item
    db = f._items_db
    out = {}
    for row in f.entities:
        for tile in row:
            if tile:
                iid = t2i.get(tile)
                if iid is not None and _gives_hp_on_pickup(db.get(iid)):
                    k = "map:" + iid
                    out[k] = out.get(k, 0) + 1
    return out


def _ge_all(a, b):
    """a 每个维度 >= b（缺失维当 0）。"""
    for k in a:
        if a[k] < b.get(k, 0):
            return False
    for k in b:
        if a.get(k, 0) < b[k]:
            return False
    return True


def _admit(frontier_vecs, vec):
    """frontier_vecs: 该指纹下当前的非支配向量列表。
    若 vec 被某现有向量支配-或-等于 → 返回 None（丢弃）。
    否则返回新列表（移除被 vec 支配-或-等于的旧点后追加 vec）。"""
    for v in frontier_vecs:
        if _ge_all(v, vec):       # 已有 v 各维 >= vec → vec 无新价值（含相等=去重）
            return None
    kept = [v for v in frontier_vecs if not _ge_all(vec, v)]
    kept.append(vec)
    return kept


def search_segment(entry_state, goal_cell, step_fn, max_states=2_000_000):
    """在单层内搜索：从 entry_state 出发，停在 goal_cell 且出口 HP 最大。

    entry_state : 已重放到段入口的 GameState。
    goal_cell   : (floor_id, x, y) 目标格。
    step_fn     : step(state, action) -> new_state，注入的确定性引擎转移。
    max_states  : 生成状态数上限（保护：超限优雅终止并在结果里置 hit_cap）。
    """
    goal_floor, goal_x, goal_y = goal_cell
    entry_floor = entry_state.current_floor

    visited = {}
    fp0 = _floor_fingerprint(entry_state)
    visited[fp0] = [_value_map(entry_state)]

    queue = deque()
    queue.append((entry_state, ()))

    # 到达目标的多维 Pareto 前沿：(value_map, actions, state)。不塌成 HP 单维——
    # 段间要传整条前沿（A 段实证：HP 略低但永久属性更高的点常是全局最优前身）。
    goal_frontier = []
    st = SearchResult(found=False, actions=[], final_hp=0)
    st.states_admitted = 1

    while queue:
        if len(queue) > st.frontier_peak:
            st.frontier_peak = len(queue)
        state, path = queue.popleft()
        st.states_expanded += 1

        for mv in MOVES:
            child = step_fn(state, mv)
            st.states_generated += 1

            if child.dead:
                continue
            if child.current_floor != entry_floor:
                continue

            child_path = path + (mv,)
            cvec = _value_map(child)

            if (child.current_floor == goal_floor
                    and child.hero.x == goal_x and child.hero.y == goal_y):
                st.goal_hits += 1
                # 出口价值向量 = 持有资源(value_map) + 地图剩余未拾取资源(map:*)。
                # 后者使「留着血瓶/资源」的出口不被「吃光换 HP」的出口支配——同属性下留着严格更优。
                gvec = {**cvec, **_remaining_items(child)}
                # 维护出口多维 Pareto 前沿：被现有点支配-或-等于则丢；否则入前沿并清理被它支配的
                if not any(_ge_all(gv, gvec) for gv, _, _ in goal_frontier):
                    goal_frontier = [t for t in goal_frontier
                                     if not _ge_all(gvec, t[0])]
                    goal_frontier.append((gvec, child_path, child))
                # 不 continue：目标格可能是「过路枢纽」——最优出口可能要先越过目标格去拿
                # 格外的增益、再折返回来。记录出口快照后仍照常入队展开，靠 Pareto 去重 +
                # 拾取改变地图指纹自然收敛，不会无限环。「到达即止」会漏掉这类折返出口。

            fp = _floor_fingerprint(child)
            newlist = _admit(visited.get(fp, []), cvec)
            if newlist is None:
                continue
            visited[fp] = newlist
            st.states_admitted += 1
            queue.append((child, child_path))

            if st.states_generated >= max_states:
                st.hit_cap = True
                break
        if st.hit_cap:
            break

    st.distinct_fingerprints = len(visited)
    if goal_frontier:
        # 主输出取前沿里 HP 最大的点（验收看 HP）；整条前沿一并返回供段间传递。
        best = max(goal_frontier, key=lambda t: t[0]["hp"])
        st.found = True
        st.final_hp = best[0]["hp"]
        st.actions = list(best[1])
        st.claimed_state = best[2]
        st.goal_frontier = [t[0] for t in goal_frontier]
    return st
