"""【GA decoder · 定向导航器】navigate_to —— ga_design.md 钉死点2 里【唯一要新写的核心件】。

契约（ga_design.md 钉死点2.2 + 2.3）：
    navigate_to(state, goal_cell, zone, step_fn) -> (final_state, moves, reached)
  从当前态【定向】走向单个 goal_cell=(fid,x,y)：
    · 够到 → (走到/拾起 goal 的真态, 从入口起的合法动作串, True)；
    · 够不到（无钥/打不过/真不可达/撞 cap）→ (入口态原样, [], False)，【原子失败、零副作用】。
  全程用现成原语组装、每个 token 经真 step 推进 → 产物【必然引擎可重放的合法路线】（撞墙/无钥/打不过
  的动作要么不生成、要么 no-op）。绝不报错、绝不产非法路线。

复用的现成原语（100%，零塔特定硬编码——楼层/怪/门全从注入 state/zone 通用字段读）：
  · solver/quotient.py：_free_cells（英雄当前零损血自由块）/ _bfs_moves（块内走法）/
    _boundary_ops(cross_floor=True)（块边界付代价算子：楼梯/杀怪/开门/假墙/触发）/ _expand_op（真 step
    展开一个算子）/ _absorb（进块吸光零损血道具）/ _qfp（块图身份指纹，做导航去重）。
  · extract/vzone.py：_passable / _NB4 / zone["links"]（楼层拓扑）—— 建【结构 hop 距离场】用。

红线（与 fitness 隔离，ga_design.md 钉死点3 的对偶形态）：本器【绝不读任何 fitness/终评】。它只把英雄
  合法推向 goal；走法好坏（潜力/HP/家底）是 fitness 的事，两者彻底隔离。方向启发只用【纯结构距离】
  （走几格到 goal，非价值评分）。

═══ 实现选型：为什么不是钉死点2.2 描述的「贪心单算子单路」（实现期实测纠偏，诚实标注 ga_design 风险节①）═══
  设计稿原描述【贪心单算子单路推进 + optimistic 损血距离启发】。本 session 独立验证（tests/test_ga_navigate）
  实测【证伪了这条路】，逐一排除如下，最终落到 GBFS + 支配剪枝 + 结构 hop 启发：

  1) optimistic 损血距离（toll）做启发会【塌缩】：导航沿途【杀怪】→ 英雄与 goal 之间无活怪 → toll→0
     成一大片平台（与属性无关，纯因清怪）。平台上启发失去方向性，退化成盲目 BFS，跨层 clearing 组合
     爆炸（实测到盾 MT9 撞 5000 cap 仍困在 MT7、或 2.6万 pops/5min 才偶达且路线劣）。
     → 改用【结构 hop 距离】（墙阻、楼梯无向边、门/怪当通的最短格数，反向 BFS 一次性建场）：纯几何、
        不随清怪塌缩、永远指向 goal。剑（近）15 pops 最优达；盾（深）稳定可达。
  2) 纯贪心 / 小束(beam) / slack 限界【均被证伪】：跨层钥匙-门依赖要求「先离 goal 方向去夺钥再回来」的
     逆梯度绕行，任何局部界都把这步剪掉 → 卡在 MT6/MT7 过不去。必须【无界前沿带回溯】才跨得过。
  3) 无界前沿的 clearing 爆炸用【支配剪枝】压：同一 _qfp 块下，(atk,def,mdef,hp,各色钥匙) 全 ≥ 即支配
     ——弱者能做的强者全能做 → 弃弱者。把「同位置不同家底」的指数膨胀收敛。

  与设计稿一致处：仍【定向】（前沿按到 goal 的结构距离升序弹）、仍【单路输出】（返回首个够到 goal 的
  动作串）、仍只求一条合法路首达即停（非段搜索/非 Pareto/不带 value_vector）。方向启发选差最多让这条
  基因解码得差→被 fitness 淘汰，绝不产非法路线（红线）。

  ⚠ 已知效率短板（留给后续「棒」，本 session 不优化）：深目标（盾 MT9）因跨层钥匙-门搜索本质复杂，
     需 ~2000-4000 pops / 10-20s；navigate_to 是 GA 内循环、将被调千百次 → 需后续【分阶段单层导航 /
     路径跟随】等优化提速。本 session 只验证【够得到、路线在界内】，效率优化是下一棒。

trade/CHOICE【留空接口】：导航器遇商人/祭坛 choices 拦截态（_event_intercepting）直接【跳过该算子】、
  不决策买卖——买不买是 GA 基因/decoder 上层的事（ga_design.md 钉死点1 trade 决策位），本器只管"导航到点"。
"""
import heapq
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))   # solver / sim
sys.path.insert(0, str(Path(__file__).parent))           # vzone（同目录）

from solver.quotient import (
    _free_cells, _bfs_moves, _boundary_ops, _expand_op, _absorb, _qfp, _zone_blocked,
)
from vzone import _passable, _NB4

_INF = float("inf")


# ═══ 禁区（§S15 序列有效性的另一半）：navigate_to 定向走向块 X 时，禁止踏入「排在 X 之后、尚未进包」
#     的块的任何 cell——治【跨块顺路吸】（去盾顺路把还没轮到的剑块吸进包＝剑早进＝谎报）与 navigate 选路
#     bias。forbidden=那些后续块的初始 block_cells 并集（跨层 (fid,x,y)）。够不到禁区外的路 → 该腿无解
#     （上层据此判情况1够不到/情况2被禁逼死），navigate_to 本身只管「带禁区能否走到」，绝不换序。═══

def _zb_with_forbidden(state, forbidden):
    """把禁区 cell 投影成 _free_cells 用的 zone_blocked（领域伤格∪本层禁区格）。
    forbidden 是跨层 (fid,x,y)，而 _free_cells 的 floodfill 只看英雄【当前层】、zone_blocked 是无 fid 的
    (x,y) 集 → 须按 state.current_floor 把禁区投影到当前层。
    · forbidden 空 / 禁区全在别层 → 返回 None：让 _free_cells 走原路自算 _zone_blocked，【字节级零回归】
      （None 分支即封板前的原始代码路径，非新行为）。"""
    if not forbidden:
        return None
    cur = state.current_floor
    fb_here = {(x, y) for (fid, x, y) in forbidden if fid == cur}
    if not fb_here:
        return None
    return _zone_blocked(state) | fb_here


def _absorb_avoiding(state, step_fn, forbidden):
    """_absorb 的禁区版：复刻 quotient._absorb，【唯一差别】是 _free_cells 传 zone_blocked=本层禁区∪领域
    伤格 → 禁区 cell 被排出自由块（既不被吸纳、也不可踏过，等效一堵墙）。forbidden 空 → 直接走原 _absorb
    （字节级零回归）。块内零损血、顺序无关、装备扩边界跑到不动点——与 _absorb 一致。"""
    if not forbidden:
        return _absorb(state, step_fn)
    moves_all = []
    s = state
    while True:
        free = _free_cells(s, zone_blocked=_zb_with_forbidden(s, forbidden))
        floor = s.floor
        target = None
        for (x, y) in free:
            if floor.entities[y][x] in floor._tile_to_item:
                target = (x, y)
                break
        if target is None:
            return s, moves_all
        path = _bfs_moves(s, free, target)
        if not path:
            return s, moves_all
        for m in path:
            s = step_fn(s, m)
            if s.dead:
                return s, moves_all
        moves_all.extend(path)


def _hop_field_to_goal(zone, goal_cell):
    """一次性反向 BFS：goal 到全图各格的【结构 hop 距离】（墙阻、楼梯无向边、门/怪当通行）。
    纯几何、不随沿途清怪塌缩 → 永远指向 goal 的方向启发。返回 {cell: hop}（够不到的格不在表中）。"""
    floors = zone["floors"]
    adj = {}
    for a, b in zone["links"].items():
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    dist = {goal_cell: 0}
    dq = deque([goal_cell])
    while dq:
        node = dq.popleft()
        d = dist[node]
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        nbrs.extend(adj.get(node, ()))
        for nb in nbrs:
            # 区外/未知楼层的格直接跳过（_passable 会对未知 fid KeyError）——区外 goal → 空场 → 必不可达
            if nb not in dist and nb[0] in floors and _passable(zone, nb):
                dist[nb] = d + 1
                dq.append(nb)
    return dist


def _res_vector(state):
    """导航资源向量：同块位置下做【支配】判定用。atk/def/mdef/hp 单调好，每色钥匙越多越好。"""
    h = state.hero
    return (h.atk, h.def_, h.mdef, h.hp, tuple(sorted(h.keys.items())))


def _dominates(a, b):
    """a 支配 b：atk/def/mdef/hp 全 ≥ 且每色钥匙 ≥（b 有而 a 缺的色 → 不支配）。a 能做的 b 全能做 → b 没用。"""
    if not (a[0] >= b[0] and a[1] >= b[1] and a[2] >= b[2] and a[3] >= b[3]):
        return False
    ka = dict(a[4])
    for color, cnt in b[4]:
        if ka.get(color, 0) < cnt:
            return False
    return True


def _nav_key(state):
    """navigate_to 缓存身份键：捕获【所有会被 step 改写的可变态字段】，依据 _copy_state(simulator.py)
    的深拷清单——它深拷/重建的字段=会变的，共享引用的=全局只读不变(events/db/楼梯表/怪表，整轮 GA 不变)。
    正确性：step 是确定纯函数、只读「可变字段 + 只读共享引用」→ _nav_key 相等 ⟺ 两态全部可变字段逐字段
    相同 ⟹ 同一 step 下走出逐字段相同的搜索树 ⟹ navigate_to 返回逐字段相同的 (final, moves, reached)。
    任何会改导航/损血/可达的差异(远层一道门没开/少一把钥匙/少 1 点防/某怪没死/假墙没撞/auto 没开)都落在
    某个纳入字段 → key 不同 → 不命中。
    · 含 gold/items/kill_count：它们不影响可达(故导航器内 _res_vector 支配剪枝不用)，但是 final_state 的
      字段——不纳入会让「仅 gold 不同」两态误命中、返回错 final。凡可变字段全纳入，保 final 逐字段正确。
    · 不复用 _qfp：_qfp 只编码英雄【当前自由块】局部形状、不含持有资源、更不含远处楼层状态；navigate_to 是
      跨层导航，远层门/怪/钥匙差异会改结果 → _qfp 不足以当跨层缓存键，故另造此全局键(_qfp 仍在导航器内做
      块去重，不动)。"""
    h = state.hero
    hero_k = (h.x, h.y, h.hp, h.atk, h.def_, h.mdef, h.gold, h.kill_count,
              tuple(sorted(h.keys.items())),
              tuple(sorted(h.items.items())),
              tuple(sorted((k, v) for k, v in h.flags.items()
                           if isinstance(v, (int, float, str, bool)))))
    floors_k = []
    for fid in sorted(state.floors):
        f = state.floors[fid]
        floors_k.append((
            fid,
            tuple(map(tuple, f.entities)),        # 怪死=0/门开=0/道具拾=0/移怪 → 实体层改
            tuple(map(tuple, f.terrain)),         # 假墙撞开 setBlock → 地形层改
            frozenset(f._suppressed_events),      # 一次性到达事件已触发 → 该格是否还挡路
            frozenset(f._done_after_battle),
            f._first_arrive_done, f._event_break, f._event_intercepting,
            tuple(f._event_pending_xy),
        ))
    return (state.current_floor, hero_k, tuple(floors_k),
            frozenset(state.visited_floors),
            tuple(sorted(state.pending_floor_change.items()))
            if state.pending_floor_change else None,
            repr(state._enemy_overrides),         # setEnemy 改怪(值可含 list special)→ repr 稳定可哈希
            state.dead, state.won, state.auto_mode)


def _navigate_to_uncached(start_state, goal_cell, zone, step_fn, max_pops=8000, forbidden=frozenset()):
    """定向走向单个 goal_cell=(fid,x,y)。返回 (final_state, moves:list, reached:bool)。契约/选型见模块头。
    GBFS：前沿按【结构 hop 距离】升序弹（次键 path-length 破平台、末键序号保堆稳定）；visited 用
    【支配剪枝】（同 _qfp 块只留非被支配资源向量）压跨层 clearing 爆炸。
    max_pops：前沿弹出护栏（失控/真不可达兜底）。
    forbidden（§S15 禁区）：跨层 (fid,x,y) 集，导航全程不得踏入（既不吸纳也不路过）——经 _zb_with_forbidden
      投影进每处 _free_cells/_absorb_avoiding 的 zone_blocked。空集 → 字节级回到原行为。"""
    gfid, gx, gy = goal_cell
    hop = _hop_field_to_goal(zone, goal_cell)

    def h_of(state):
        return hop.get((state.current_floor, state.hero.x, state.hero.y), _INF)

    # visited: dict[_qfp] -> list(非被支配的资源向量)。返回 True=被既有支配（剪），False=已纳入。
    visited = {}

    def seen_or_add(state, free):
        qf = _qfp(state, free)
        res = _res_vector(state)
        lst = visited.get(qf)
        if lst is None:
            visited[qf] = [res]
            return False
        for old in lst:
            if _dominates(old, res):
                return True
        visited[qf] = [o for o in lst if not _dominates(res, o)] + [res]
        return False

    # 进块即吸光块内零损血道具（钥匙/宝石/装备）——没钥匙开不了门、到不了楼梯。失败仍返回【原始入口态】。
    # 禁区版 _absorb_avoiding：吸纳时也绕开 forbidden（治去盾顺路吸剑块的根）。
    s0, m0 = _absorb_avoiding(start_state, step_fn, forbidden)
    start_free = _free_cells(s0, zone_blocked=_zb_with_forbidden(s0, forbidden))
    seen_or_add(s0, start_free)
    # 前沿元素 (h=结构距离, g_dmg=累计真损血, length=步数, counter 序号 tiebreak, state, 动作 tuple)。
    # 排序键 (h, g_dmg, length)：h 主【定向不塌缩】；同结构进度下 g_dmg 次【偏低损血路】（_absorb 零损血→
    # 单步损血=该算子的 HP 下降，免 Dijkstra 现成可取）；length 末破平台。纯路径代价，绝不掺 fitness（红线）。
    frontier = [(h_of(s0), 0, len(m0), 0, s0, tuple(m0))]
    counter = 1
    pops = 0

    while frontier and pops < max_pops:
        pops += 1
        _, g_dmg, _, _, s, moves = heapq.heappop(frontier)
        free = _free_cells(s, zone_blocked=_zb_with_forbidden(s, forbidden))

        # 够到：goal 已在当前自由块内 → 块内 BFS 走过去（沿途踩到即拾取）、首达即返回单路
        if s.current_floor == gfid and (gx, gy) in free:
            walk = _bfs_moves(s, free, (gx, gy))
            if walk is not None:
                gs = s
                ok = True
                for mv in walk:
                    gs = step_fn(gs, mv)
                    if gs.dead:
                        ok = False
                        break
                if ok and (gs.hero.x, gs.hero.y) == (gx, gy):
                    return gs, list(moves) + list(walk), True

        # 朝 goal 推进：展开块边界付代价算子（cross_floor=True → 楼梯作免费跨层边），按结构距离排序入前沿
        for op in _boundary_ops(s, free, cross_floor=True):
            res = _expand_op(s, free, op, step_fn)
            if res is None:
                continue
            child, op_moves = res
            if child.dead:
                continue
            if child.floor._event_intercepting:
                continue                      # 商人/祭坛 CHOICE：导航器不决策买卖（留空接口给 GA 层）
            op_dmg = max(0, s.hero.hp - child.hero.hp)   # 该算子真损血（_absorb 前取；_absorb 零损血不计）
            child, abs_moves = _absorb_avoiding(child, step_fn, forbidden)   # 进新块即吸光道具（绕禁区）
            if child.dead:
                continue
            child_free = _free_cells(child, zone_blocked=_zb_with_forbidden(child, forbidden))
            if seen_or_add(child, child_free):
                continue
            child_moves = moves + tuple(op_moves) + tuple(abs_moves)
            heapq.heappush(
                frontier,
                (h_of(child), g_dmg + op_dmg, len(child_moves), counter, child, child_moves),
            )
            counter += 1

    return start_state, [], False             # 前沿耗尽/撞 cap → 够不到，原样返回（原子失败）


# ═══ 缓存外壳：只在导航器【外面】包一层 memoization，GBFS 主体(_navigate_to_uncached)一步不动 ═══
_NAV_CACHE = {}   # 模块级默认缓存，按 id(zone) 分桶。GA 可传专用 dict；cache=None 则禁用(对照/调试)。


def navigate_to(start_state, goal_cell, zone, step_fn, max_pops=8000, cache=_NAV_CACHE, forbidden=frozenset()):
    """navigate_to 的缓存外壳：【不改 GBFS 一步】，只在 _navigate_to_uncached 外包 memoization。
    动机：GA 一代上百个体反复导航到同样几个目标(剑/盾等大件就那么几个)——(规整起点态, 目标)相同 → 直接
    返缓存、省掉重复搜索。命中返回与首算【逐字段一致】的 (final, moves, reached)(正确性见 _nav_key)。
    cache：默认模块级 _NAV_CACHE(测试/GA 共享、按 id(zone) 分桶防串味)；传 None → 禁用、字节回到原行为；
      传自有 dict → 专用缓存。拦截态入口(罕见、pending 难规整成键)直接绕过缓存，行为同原算法。
    forbidden（§S15 禁区）：纳入缓存键 frozenset(forbidden)——禁区不同 → 同(起点,目标)也是不同搜索、不可
      串味；空集时与封板行为一致(键多一个空 frozenset、不影响命中正确性)。判无效上层会以「带禁区 vs 不带
      禁区」两次调用区分情况1/情况2，不带禁区那次因键不同独立命中、近免费。
    返回值约定与原函数一致：成功 (final_state, moves:list, True)；够不到 (入口态本体, [], False)。
    命中时 moves 返回新 list 副本(调用方可安全改)，final_state 返回缓存引用(step 纯函数→不会被就地改写)。"""
    if cache is None or start_state.floor._event_intercepting:
        return _navigate_to_uncached(start_state, goal_cell, zone, step_fn, max_pops, forbidden)
    key = (id(zone), max_pops, goal_cell, frozenset(forbidden), _nav_key(start_state))
    hit = cache.get(key)
    if hit is not None:
        final, moves_t, reached = hit
        if reached:
            return final, list(moves_t), True
        return start_state, [], False         # 原子失败命中：返回【当前入口态本体】保 `final is start` 契约
    final, moves, reached = _navigate_to_uncached(start_state, goal_cell, zone, step_fn, max_pops, forbidden)
    cache[key] = (final if reached else None, tuple(moves), reached)
    return final, moves, reached
