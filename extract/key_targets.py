"""【GA 钥匙目标涌现器】detect_key_targets —— ga_design.md 钉死点1 的 pickup_key 一等目标候选池（驱动层·塔无关）。

与 detect_big_items（big_item_pull.py，攻防大件/宝石涌现）【同族·独立】：都从塔数据涌现兴趣点 cell、
塔无关零硬编码、只产候选不决定取舍（取不取/何时取留 GA 搜）。本器专产【代价型钥匙】候选——
navigate_to 顺路 _absorb 吸不到的钥匙（要打守门怪付血才到），它们有「何时取（等属性高、减伤少再取）」
的时机价值，必须进 GA 目标池让基因显式控制；否则 pickup_key 这条一等目标表达不出（钉死点1 的核心增量、
beam 卡死红钥长臂的症结）。

═══ 三分口径（§S9 已定死、analysis/probe_key_targets.py 实测坐实 12/44/3）═══
一区地上钥匙全集，用【真实 key-chain afford 闭包】（零钥起步、把 door-wise 真拿得到的钥匙色滚到不动点）
+ 门拓扑，一次自然产出三档（非加规则）：
  ① 顺路   = 零损血够到（afford 门 + 仅穿 0 损血守怪）→ navigate_to 顺手白捡 = 非候选。
  ② 候选   = door-wise 可达但非零损血（afford 门内·要付守怪血）→ 进候选池、GA 决策何时取。
  ③ 够不到 = door-wise 不可达（每条路被一道开不起的门锁死，如铁门无铁钥）→ 一区外、不进池。
判据「门色 ∉ afford 闭包」全数据滚出、换塔自动重算 = 塔无关。③ 只锁门（铁钥拿不到=硬结构、与属性无关）；
守怪可行性留 runtime（navigate_to 到不了 = reached False / decode 跳过），本器【不预判】（只产候选）。

固定参照 ref_state（噩梦后 MT3 入口·atk10/def10·手里 0 钥匙，与 detect_big_items 同源）：定「本塔什么
算顺路/候选」的静态划分——零损血判定按【最弱态】（运行时属性更高 → 更多钥匙被 navigate_to 顺吸，不影响
候选池正确性：列为候选的钥匙若运行时被顺吸/已拿，decode 发现 reached 即合法、GA 不依赖它必须作目标）。

塔无关：钥匙=_tile_to_item∩_KEY_ITEMS、门→钥色=DOOR_KEY_MAP、守怪损血=_combat_damage、楼梯源/墙/门控
全走 fitness._zone_floor_cells 的引擎共享表，无楼层/怪/坐标/门色硬编码（换塔换一份 data/ 即重算）。
"""
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # solver / sim

from sim.simulator import _KEY_ITEMS, DOOR_KEY_MAP                 # noqa: E402  (DOOR_KEY_MAP 间接经 _zone_floor_cells 用，import 作塔无关口径锚)
from solver.beam import _combat_damage                            # noqa: E402
from solver.fitness import _afford_colors, _zone_floor_cells      # noqa: E402

_NB4 = ((0, -1), (0, 1), (-1, 0), (1, 0))
_FULL_AFFORD = set(_KEY_ITEMS)   # 全色 afford：门不锁，纯枚举全集用（不做可达门控）


def _floor_tile_at(state, fid, x, y):
    """取 (fid,x,y) 的 tile id（已访问层读 entities 真态，未访问层读静态 JSON map）。塔无关。"""
    fl = state.floors.get(fid)
    if fl is not None:
        return fl.entities[y][x]
    floors_dir = getattr(state, "_floors_dir", None)
    if floors_dir is None:
        return None
    path = Path(floors_dir) / f"{fid}.json"
    if not path.exists():
        return None
    grid = json.loads(path.read_text(encoding="utf-8")).get("map", [])
    return grid[y][x] if grid and 0 <= y < len(grid) and 0 <= x < len(grid[0]) else None


def _key_color_at(state, fid, x, y):
    """该钥匙格的钥匙色（item id ∈ _KEY_ITEMS）：key-chain 自给 afford 闭包用。t2i 取共享全塔表。"""
    t = _floor_tile_at(state, fid, x, y)
    return state.floor._tile_to_item.get(t) if t else None


def _all_key_cells(state, zone_fids):
    """一区地上钥匙全集 set[(fid,x,y)]（全色 afford·门不锁枚举，不经可达，纯枚举钥匙格）。"""
    out = set()
    for fid in zone_fids:
        info = _zone_floor_cells(state, fid, _FULL_AFFORD)
        if info is None:
            continue
        _h, _w, _isw, _mid, key_cells, _src = info
        out.update((fid, x, y) for (x, y) in key_cells)
    return out


def _reachable_doorwise(state, fid, afford):
    """单层【门拓扑可达】钥匙格：afford 门通 / 非 afford 门（铁红无钥）当墙 / 守怪一律可穿（只看门墙拓扑、
    不管打不打得过）。楼梯多源 BFS。门控经 _zone_floor_cells 的 is_wall（『没钥匙的门=墙』）。
    判 ②/③ 用——door-wise 够不到 = 每条路都被一道开不起的门锁死。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, _mid_at, key_cells, src_cells = info
    seen, dq = set(), deque()
    for s in src_cells:
        if not is_wall(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not is_wall(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return {(fid, x, y) for (x, y) in key_cells if (x, y) in seen}


def _reachable_zerodmg(state, fid, afford):
    """单层【零损血够到】钥匙格（楼梯多源 BFS·afford 门通·只穿 0 损血守怪）。这正是 navigate_to「顺路」
    语义：_absorb 不杀怪、只零损血开 afford 门 + 顺手杀 op_dmg=0 的怪；损血>0 / 打不动(_combat_damage None)
    = 边界。损血按【固定参照 ref_state 属性】算 → 不随搜索漂移。判 ① 用。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return set()
    h, w, is_wall, mid_at, key_cells, src_cells = info

    def passable(x, y):
        if is_wall(x, y):
            return False
        if (x, y) in mid_at:
            return _combat_damage(state, mid_at[(x, y)]) == 0   # None(打不动)/>0 都不算顺路
        return True

    seen, dq = set(), deque()
    for s in src_cells:
        if passable(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and passable(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return {(fid, x, y) for (x, y) in key_cells if (x, y) in seen}


def _afford_closure(state, zone_fids):
    """零钥起步、钥匙-门自给到不动点：door-wise 够到的钥匙色并入 afford，迭代。返回最终可得色集。
    最宽口径（穿怪也算够到）→ 某色（如铁钥）在一区根本拿不到 → 必不在 afford → 该色门=永久墙 → 门后=③。
    起步 _afford_colors(ref_state)（固定参照手里 0 钥匙 → ∅，纯靠地图滚出本塔 {黄,蓝,红}）。"""
    afford = set(_afford_colors(state))
    while True:
        reached = set()
        for fid in zone_fids:
            reached |= _reachable_doorwise(state, fid, afford)
        colors = {_key_color_at(state, *c) for c in reached}
        colors.discard(None)
        if colors <= afford:
            return afford
        afford |= colors


def detect_key_targets(ref_state, zone_fids):
    """从【数据涌现】划出 GA pickup_key 候选池（②代价型钥匙）。契约/三分口径见模块头。
    返回 (candidates, info)：
      candidates : set[(fid,x,y)] = ② 候选（afford 门内·付守怪血·GA 决策何时取）= GA 目标池。
      info       : dict(
          afford      = set 钥匙色闭包（一区真能开的门色），
          cheap       = set ① 顺路（零损血白捡·非候选），
          unreachable = set ③ 够不到（door-wise 锁死·不进池），
          all_keys    = set 全集，
          colors      = {cell: 钥匙色})  —— 供 dump / 单测钉三档、不进 GA 决策。
    ref_state：固定参照（噩梦后 MT3 入口·atk10/def10·手里 0 钥匙，detect_big_items 同源）——定本塔
      顺路/候选静态划分、与运行态无关。【只产候选不决定取舍】（取不取/何时取留 GA 搜；守怪可行性留 runtime）。"""
    afford = _afford_closure(ref_state, zone_fids)
    all_keys = _all_key_cells(ref_state, zone_fids)
    cheap, door_reach = set(), set()
    for fid in zone_fids:
        cheap |= _reachable_zerodmg(ref_state, fid, afford)
        door_reach |= _reachable_doorwise(ref_state, fid, afford)
    candidates = door_reach - cheap            # ② door-wise 可达但非零损血
    unreachable = all_keys - door_reach        # ③ door-wise 锁死（每条路过开不起的门）
    colors = {c: _key_color_at(ref_state, *c) for c in all_keys}
    info = dict(afford=afford, cheap=cheap, unreachable=unreachable,
                all_keys=all_keys, colors=colors)
    return candidates, info
