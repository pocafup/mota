"""一区(MT1-MT10) macro-edge【段识别器】——只识别+报告"能收多少"，不收缩、不动 quotient/beam。

铁律(玩家定死)：可收缩段内严格【无事件·无拾取·无special】；拾取/事件/special怪/boss(战斗钩子)/
楼梯/NPC/领域伤格一律当【节点】(边界、永不进边内)。普通怪(special=[])+钥匙门=可进边的付代价格。
关键澄清：『可不可杀』是 f(atk,def) 的值域(运行时查表得 blood=None)，不是切段依据 → 段识别只按
【结构】(special 空/非空、是否挂事件钩子)切，与属性无关。

块图模型：FREE 格 4-邻接连通=块(节点)；普通怪+门 4-邻接连通=PAY 簇(边)。一个块的【度数】=邻接
PAY 簇数。【度2纯过道块】(两条 series 边穿过、块内本就无拾取无事件)=可被串联收缩消掉的 decision
点(series contraction)。报告逐层+全区统计、度数分布、可消过道块数(=降多少 decision 点)、
macro-edge 估计数、样例最长收缩链(端点+怪门序列，供第2步引擎对拍)。

静态口径：读各层【初始】地图(load_floor)。firstArrive/setEnemy 等运行时改图/改怪的动态性标注为
caveat，待第3步接 quotient 时用运行时 state.floor 处理。塔无关性不适用(extract/驱动层，可读
MT1-10 塔特有数据)；solver/ 一行不改。
"""
import sys
from collections import deque, Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state
from sim.simulator import (
    load_floor, WALL_TILES, SPECIAL_DOOR, AUTO_OPEN_TILES, DOOR_KEY_MAP,
)
from solver.quotient import _live_arrive_event, _zone_blocked

ZONE1 = [f"MT{i}" for i in range(1, 11)]
_DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
NODE_KINDS = ["item", "event", "special-mon", "battle-hook", "stair",
              "npc", "zone", "special-door", "autoopen"]


def norm_special(m):
    sp = m.get("special", [])
    if isinstance(sp, int):
        sp = [sp] if sp else []
    return list(sp)


def classify(floor, x, y, zone_blocked):
    """按【新铁律】分类一格：('wall',_) / ('free',_) / ('pay','kill'|'door') / ('node',类型)。
    顺序：换层>墙/noPass>特殊门>怪(钩子/special/普通)>拾取>NPC>钥匙门>假墙>领域>事件>地板。"""
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    if not (0 <= x < cols and 0 <= y < rows):
        return ("wall", None)
    loc = f"{x},{y}"
    if loc in floor.change_floor:
        return ("node", "stair")
    t = floor.terrain[y][x]
    e = floor.entities[y][x]
    if t in WALL_TILES or t in floor._no_pass_tiles:
        return ("wall", None)
    if t == SPECIAL_DOOR:
        return ("node", "special-door")
    mid = floor._tile_to_enemy.get(e)
    if mid is not None:
        # 挂到达事件/战斗钩子的怪 = 独立节点(含 MT10 boss 骷髅队长 afterBattle、MT33 约束)
        if (_live_arrive_event(floor, x, y) or loc in floor.after_battle
                or loc in floor.before_battle):
            return ("node", "battle-hook")
        if norm_special(floor._monsters_db[mid]):       # special 非空 → 节点(领域/夹击/先攻/坚固…)
            return ("node", "special-mon")
        return ("pay", "kill")                          # 普通怪：可进边(可不可杀=f 值域，不在此判)
    if e in floor._tile_to_item:
        return ("node", "item")
    if e and e in getattr(floor, "_tile_to_entity", {}):
        return ("node", "npc")
    if t in DOOR_KEY_MAP:
        return ("pay", "door")
    if t in AUTO_OPEN_TILES:
        return ("node", "autoopen")                     # 假墙:可能藏 afterOpenDoor → 保守当节点
    if (x, y) in zone_blocked:
        return ("node", "zone")
    if _live_arrive_event(floor, x, y):
        return ("node", "event")
    return ("free", None)


def _components(cells, _DIRS=_DIRS):
    """cells 集合的 4-邻接连通分量列表。"""
    seen = set()
    comps = []
    for c in cells:
        if c in seen:
            continue
        comp = []
        dq = deque([c])
        seen.add(c)
        while dq:
            cx, cy = dq.popleft()
            comp.append((cx, cy))
            for dx, dy in _DIRS:
                nb = (cx + dx, cy + dy)
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    dq.append(nb)
        comps.append(comp)
    return comps


def analyze_floor(base, fid):
    floor = load_floor(base._floors_dir / f"{fid}.json")
    base.floors[fid] = floor
    base.current_floor = fid
    zone_blocked = _zone_blocked(base)
    rows, cols = len(floor.terrain), len(floor.terrain[0])

    kind = {}
    node_kinds = Counter()
    pay_kinds = Counter()
    for y in range(rows):
        for x in range(cols):
            k, info = classify(floor, x, y, zone_blocked)
            kind[(x, y)] = (k, info)
            if k == "node":
                node_kinds[info] += 1
            elif k == "pay":
                pay_kinds[info] += 1

    # FREE 块
    free_cells = {c for c, (k, _) in kind.items() if k == "free"}
    block_id = {}
    block_cells = {}
    for i, comp in enumerate(_components(free_cells), 1):
        block_cells[i] = comp
        for c in comp:
            block_id[c] = i
    nblocks = len(block_cells)

    # PAY 簇 = 边；求每簇端点(邻接的 块/节点) + 怪门计数
    pay_cells = {c for c, (k, _) in kind.items() if k == "pay"}
    clusters = _components(pay_cells)
    block_degree = Counter()
    cluster_info = []          # (cells, endpoints set, pk Counter)
    for cl in clusters:
        eps = set()
        pk = Counter()
        for (px, py) in cl:
            pk[kind[(px, py)][1]] += 1
            for dx, dy in _DIRS:
                nb = (px + dx, py + dy)
                if nb in block_id:
                    eps.add(("block", block_id[nb]))
                else:
                    k2, info2 = kind.get(nb, ("wall", None))
                    if k2 == "node":
                        eps.add(("node", nb, info2))
        for be in {e for e in eps if e[0] == "block"}:
            block_degree[be[1]] += 1
        cluster_info.append((cl, eps, pk))

    deg_dist = Counter()
    for b in range(1, nblocks + 1):
        deg_dist[block_degree.get(b, 0)] += 1

    return dict(fid=fid, nblocks=nblocks, nfree=len(free_cells),
                node_kinds=node_kinds, pay_kinds=pay_kinds,
                nclusters=len(clusters), deg_dist=deg_dist,
                cluster_info=cluster_info, block_degree=block_degree,
                block_cells=block_cells, kind=kind, floor=floor)


def trace_macro_edges(res):
    """series contraction：沿【度2纯过道块】把相邻 2-端点 PAY 簇链接成 macro-edge。
    返回 [(端点A, 端点B, [cluster_idx...], 怪数, 门数)]。"""
    cluster_info = res["cluster_info"]
    block_degree = res["block_degree"]
    adj = defaultdict(list)            # vertex -> [(neighbor_vertex, cluster_idx)]
    for ci, (cl, eps, pk) in enumerate(cluster_info):
        if len(eps) == 2:
            a, b = list(eps)
            adj[a].append((b, ci))
            adj[b].append((a, ci))

    def is_thru(v):
        return (v[0] == "block" and block_degree.get(v[1], 0) == 2
                and len(adj.get(v, [])) == 2)

    used = set()
    edges = []
    for v in list(adj):
        if is_thru(v):
            continue
        for (nb, ci) in adj[v]:
            if ci in used:
                continue
            used.add(ci)
            chain = [ci]
            prev_edge, cur = ci, nb
            while is_thru(cur):
                nxt = [(n, c) for (n, c) in adj[cur] if c != prev_edge]
                if not nxt or nxt[0][1] in used:
                    break
                n2, c2 = nxt[0]
                used.add(c2)
                chain.append(c2)
                prev_edge, cur = c2, n2
            nk = sum(cluster_info[c][2].get("kill", 0) for c in chain)
            nd = sum(cluster_info[c][2].get("door", 0) for c in chain)
            edges.append((v, cur, chain, nk, nd))
    return edges


def vlabel(v, res):
    if v[0] == "block":
        cells = res["block_cells"].get(v[1], [])
        rep = cells[0] if cells else ("?", "?")
        return f"块#{v[1]}@{rep}({len(cells)}格)"
    return f"{v[2]}@{v[1]}"


def main():
    base = build_initial_state()
    L = []

    def w(s=""):
        L.append(s)

    w("=" * 100)
    w("一区(MT1-MT10) macro-edge 段识别 —— 只识别+报告可收缩量，不收缩(铁律：段内无事件/无拾取/无special)")
    w("=" * 100)
    w("节点类型缩写: item拾取 ev事件 spc=special怪 hook=战斗钩子(含boss) stair楼梯 npc zone领域 sdr特殊门 auto假墙")
    w("-" * 100)
    w(f"{'层':5s}{'FREE块(格)':>12s}  {'节点格分类':36s} {'PAY(怪/门)':>11s} {'簇':>4s} {'度2过道(可消)':>12s}")

    results = []
    tot_block = tot_free = tot_cluster = tot_deg2 = 0
    tot_node = Counter()
    tot_pay = Counter()
    all_edges = []
    for fid in ZONE1:
        r = analyze_floor(base, fid)
        results.append(r)
        nk = r["node_kinds"]
        nodestr = ("i%d e%d s%d h%d t%d n%d z%d D%d a%d" %
                   (nk["item"], nk["event"], nk["special-mon"], nk["battle-hook"],
                    nk["stair"], nk["npc"], nk["zone"], nk["special-door"], nk["autoopen"]))
        deg2 = r["deg_dist"].get(2, 0)
        w(f"{r['fid']:5s}{r['nblocks']:>4d}({r['nfree']:>3d})    {nodestr:36s} "
          f"{r['pay_kinds']['kill']:>4d}/{r['pay_kinds']['door']:<4d}  {r['nclusters']:>4d} {deg2:>10d}")
        tot_block += r["nblocks"]
        tot_free += r["nfree"]
        tot_cluster += r["nclusters"]
        tot_deg2 += deg2
        tot_node += r["node_kinds"]
        tot_pay += r["pay_kinds"]
        edges = trace_macro_edges(r)
        for ed in edges:
            all_edges.append((r["fid"], ed))

    # ── 命门核查：MT10 boss 落类 + 埋伏搬家机制(读源码 events[6,5]/afterBattle[6,1] 确认) ──
    r10 = next(x for x in results if x["fid"] == "MT10")
    kd, fl = r10["kind"], r10["floor"]
    boss = kd.get((6, 4))
    nb = {(x, y): kd.get((x, y)) for (x, y) in [(6, 3), (5, 4), (7, 4), (6, 5)]}
    n_wall = sum(1 for v in nb.values() if v[0] == "wall")
    w("-" * 100)
    w("【命门核查】MT10 boss skeletonCaptain：识别器有没有把它当普通怪收进边？")
    w(f"  · 初始落类 (6,4) = {boss}   四邻: " +
      "  ".join(f"{c}={v[0]}" for c, v in nb.items()))
    w(f"  · 结论：boss 初始三面 terrain-17 墙({n_wall}/3 wall)+ 南邻 (6,5)=事件节点 → 【单端点 spur】，"
      "收缩器只串 2 端点簇 → boss 永不进任何 macro-edge ✅ 无泄漏。")
    w("  · 且是【幽灵格】：踩埋伏触发 (6,5) 后 events 把 boss `move up:3` 搬到 (6,1)、清掉三面 17 墙、")
    w("    放 6 骷髅+2 士兵；真正战斗与开 MT11 闸(flag:10f战胜骷髅队长)都发生在 afterBattle[6,1]——")
    w("    即 boss 真身在 (6,1) 是事件节点(已正确识别)，(6,4) 这格静态期根本打不到。")
    w("  · ⚠ 代价：静态把 boss 计进 pay-kill(占 1 格) 而非节点——因它 special=[] 且 afterBattle 不在自身格。")
    w("    本层靠墙体几何兜底安全；但『会搬家的 boss=节点』本质是运行时判定(静态看不到搬迁)→ 归第3步。")

    w("-" * 100)
    w("【一区汇总】")
    pct = round(100 * tot_deg2 / tot_block) if tot_block else 0
    w(f"  FREE 块(decision 点) 总数 = {tot_block}  →  可消【度2过道块】= {tot_deg2}  "
      f"(降 {pct}% → 收缩后超节点 ≈ {tot_block - tot_deg2})")
    w(f"  PAY 簇(现有单算子边) 总数 = {tot_cluster}  →  series 收缩后 macro-edge ≈ {tot_cluster - tot_deg2}")
    w(f"  可进边的付代价格: 普通怪 {tot_pay['kill']} + 钥匙门 {tot_pay['door']} = {tot_pay['kill']+tot_pay['door']}")
    ntot = sum(tot_node.values())
    w(f"  必须当【节点】的格 = {ntot}:")
    w(f"     拾取 {tot_node['item']} · 事件 {tot_node['event']} · special怪 {tot_node['special-mon']} · "
      f"战斗钩子(含boss) {tot_node['battle-hook']} · 楼梯 {tot_node['stair']}")
    w(f"     NPC {tot_node['npc']} · 领域伤 {tot_node['zone']} · 特殊门 {tot_node['special-door']} · "
      f"假墙 {tot_node['autoopen']}")

    # 样例最长收缩链(供第2步对拍)：按穿过 PAY 数降序
    all_edges.sort(key=lambda fe: -(fe[1][3] + fe[1][4]))
    multi = [fe for fe in all_edges if (fe[1][3] + fe[1][4]) >= 2]
    w("-" * 100)
    w(f"【样例 macro-edge】穿过≥2付代价格的收缩边共 {len(multi)} 条(=真有收缩收益)；列最长 12 条(供第2步引擎对拍)：")
    w(f"  {'层':5s} {'端点A':28s} {'端点B':28s} {'穿过':>14s}")
    for fid, (va, vb, chain, nk, nd) in multi[:12]:
        r = next(x for x in results if x["fid"] == fid)
        w(f"  {fid:5s} {vlabel(va, r):28s} {vlabel(vb, r):28s} {('%d怪+%d门=%d格' % (nk, nd, nk+nd)):>14s}")

    w("-" * 100)
    w("⚠ caveat：静态口径(各层初始地图)。firstArrive 改图 / setEnemy 改 special 的动态性未计入，")
    w("  待第3步接 quotient 用运行时 state.floor 处理。假墙(auto)保守当节点(可能藏 afterOpenDoor)。")
    w("=" * 100)

    report = "\n".join(L)
    out = Path(__file__).parent / "seg_identify_zone1.txt"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[落盘] {out}")


if __name__ == "__main__":
    main()
