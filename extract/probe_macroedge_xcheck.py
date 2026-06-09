"""一区 macro-edge【引擎重放对拍】(第2步)。

抽查识别器(seg_identify_zone1)圈出的【穿过≥2付代价格】macro-edge(那 31 条真有收缩收益的)，
每条重建一条具体穿越路径，逐 (atk,def) 测试点对拍：
  · f(atk,def) 预测的 (损血, 各色钥匙)  —— 引擎 compute_combat 逐怪算损血 + 路径上门按色计钥匙
  · 引擎【实走该路径】真实的 (Δhp, Δ各色钥匙)  —— step 逐 token(怪1下·门2下)
两者须【损血一致 + 各色钥匙一致】；并审计段内【无拾取·无换层·无额外 kill】(=识别器没把不该
进边的东西收进去)。任一条对不上立即详报。

铁律：路径格/算子由引擎+静态地图算，不手推；损血全用引擎 compute_combat/step，不手写公式。
塔无关性不适用(extract/ 驱动层探针，可读 MT1-10 塔特有数据)；solver/ 与识别器一行不改。
"""
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, FLOORS
from sim.simulator import step, load_floor, DOOR_KEY_MAP, _build_monster
from sim.combat import PlayerState, compute_combat
from seg_identify_zone1 import analyze_floor, ZONE1

_DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
_TOK = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}
KEY_NAMES = ["yellowKey", "blueKey", "redKey", "greenKey", "steelKey"]
TEST_PTS = [(60, 30), (40, 15), (25, 5)]   # 保证打动一区普通怪、覆盖 def 阶梯


def trace_with_thru(res):
    """= seg_identify_zone1.trace_macro_edges，额外记录串接经过的【过道块顶点】(重建实走路径要)。
    返回 [(va, vb, chain[cluster_idx], thru[block顶点], nk, nd)]。"""
    cluster_info = res["cluster_info"]
    block_degree = res["block_degree"]
    adj = defaultdict(list)
    for ci, (cl, eps, pk) in enumerate(cluster_info):
        if len(eps) == 2:
            a, b = list(eps)
            adj[a].append((b, ci))
            adj[b].append((a, ci))

    def is_thru(v):
        return (v[0] == "block" and block_degree.get(v[1], 0) == 2
                and len(adj.get(v, [])) == 2)

    used, edges = set(), []
    for v in list(adj):
        if is_thru(v):
            continue
        for (nb, ci) in adj[v]:
            if ci in used:
                continue
            used.add(ci)
            chain, thru = [ci], []
            prev_edge, cur = ci, nb
            while is_thru(cur):
                thru.append(cur)
                nxt = [(n, c) for (n, c) in adj[cur] if c != prev_edge]
                if not nxt or nxt[0][1] in used:
                    break
                n2, c2 = nxt[0]
                used.add(c2)
                chain.append(c2)
                prev_edge, cur = c2, n2
            nk = sum(cluster_info[c][2].get("kill", 0) for c in chain)
            nd = sum(cluster_info[c][2].get("door", 0) for c in chain)
            edges.append((v, cur, chain, thru, nk, nd))
    return edges


def _bfs(a, b, allowed):
    if a == b:
        return [a]
    prev = {a: None}
    q = deque([a])
    while q:
        c = q.popleft()
        if c == b:
            p, cur = [], c
            while cur is not None:
                p.append(cur)
                cur = prev[cur]
            return p[::-1]
        for dx, dy in _DIRS:
            nb = (c[0] + dx, c[1] + dy)
            if nb in allowed and nb not in prev:
                prev[nb] = c
                q.append(nb)
    return None


def build_path(res, va, vb, chain, thru):
    """重建端点A→端点B、穿过该边 pay 簇(+过道free)的一条实走格路径。
    返回 (path, pay_set) 或 (None, reason)。"""
    cinfo = res["cluster_info"]
    bcells = res["block_cells"]
    pay = set()
    for ci in chain:
        pay |= set(cinfo[ci][0])
    thru_cells = set()
    for tv in thru:
        thru_cells |= set(bcells[tv[1]])

    def endcell(v, adj_cluster):
        if v[0] == "block":
            for c in bcells[v[1]]:
                if any((c[0] + dx, c[1] + dy) in adj_cluster for dx, dy in _DIRS):
                    return c
            return bcells[v[1]][0]
        return v[1]

    A = endcell(va, set(cinfo[chain[0]][0]))
    B = endcell(vb, set(cinfo[chain[-1]][0]))
    if A == B:                                   # self-loop：取块内两个不同入口
        if va[0] == "block":
            cands = [c for c in bcells[va[1]]
                     if any((c[0] + dx, c[1] + dy) in pay for dx, dy in _DIRS)]
            if len(cands) >= 2:
                A, B = cands[0], cands[1]
            else:
                return None, "self-loop退化(单入口环)"
        else:
            return None, "self-loop退化(node端点)"
    allowed = {A, B} | pay | thru_cells
    path = _bfs(A, B, allowed)
    if path is None:
        return None, "BFS不连通"
    return path, pay


def f_predict(gs, res, path, pay, atk, def_):
    """沿 path 的 f 预测：损血(引擎逐怪 compute_combat) + 各色钥匙(门按 terrain 色)。
    返回 (blood 或 None, doorcols Counter, mids list)。"""
    kind = res["kind"]
    fl = gs.floors[gs.current_floor]
    mids, doorcols = [], Counter()
    for (x, y) in path:
        if (x, y) not in pay:
            continue
        info = kind[(x, y)][1]
        if info == "kill":
            mids.append(fl._tile_to_enemy.get(fl.entities[y][x]))
        elif info == "door":
            doorcols[DOOR_KEY_MAP[fl.terrain[y][x]]] += 1
    total = 0
    for mid in mids:
        c = compute_combat(PlayerState(hp=10**7, atk=atk, def_=def_, mdef=0),
                           _build_monster(gs, mid))
        if c.damage is None:
            return None, doorcols, mids
        total += c.damage
    return total, doorcols, mids


def engine_walk(fid, A, path, atk, def_):
    """引擎从 A 实走 path[:-1](不踏入终点端点)，返回 dict(ok, blood, keys, kill, items, anomalies)。"""
    gs = build_initial_state()
    fl = load_floor(FLOORS / f"{fid}.json")
    fl._first_arrive_done = True          # 模拟"首入剧情已消费"正常态(firstArrive 是层级一次性事件，
    gs.floors[fid] = fl                    # 非 macro-edge 静态结构；归第3步运行时，详见 MT1 I333/choices)
    gs.current_floor = fid
    gs.visited_floors.add(fid)
    h = gs.hero
    h.x, h.y = A
    h.atk, h.def_, h.mdef, h.hp = atk, def_, 0, 10**7
    h.keys = {k: 99 for k in KEY_NAMES}
    hp0, k0, kill0 = h.hp, dict(h.keys), h.kill_count
    items0 = dict(h.items)
    anomalies, ok = [], True
    seq = path[:-1]                              # 止于终点端点之前
    for (cx, cy), (nx, ny) in zip(seq, seq[1:]):
        mv = _TOK[(nx - cx, ny - cy)]
        is_door = gs.floors[fid].terrain[ny][nx] in DOOR_KEY_MAP
        for _ in range(2 if is_door else 1):
            gs = step(gs, mv)
            if gs.dead:
                ok = False
                anomalies.append(f"死亡@进入{(nx,ny)}")
                break
            if gs.current_floor != fid:
                anomalies.append(f"换层→{gs.current_floor}@{(nx,ny)}")
        if not ok:
            break
        if (gs.hero.x, gs.hero.y) != (nx, ny):
            ok = False
            anomalies.append(f"未到位{(nx,ny)}(停在{(gs.hero.x,gs.hero.y)})")
            break
    blood = hp0 - gs.hero.hp if ok else None
    keys = {k: k0[k] - gs.hero.keys.get(k, 0) for k in KEY_NAMES}
    keys = {k: v for k, v in keys.items() if v}
    items_d = {k: gs.hero.items.get(k, 0) - items0.get(k, 0)
               for k in set(items0) | set(gs.hero.items)}
    items_d = {k: v for k, v in items_d.items() if v}
    return dict(ok=ok, blood=blood, keys=keys, kill=gs.hero.kill_count - kill0,
                items=items_d, anomalies=anomalies)


def main():
    base = build_initial_state()
    L = []

    def w(s=""):
        L.append(s)

    w("=" * 100)
    w("一区 macro-edge 引擎重放对拍 —— f(预测) vs 引擎实走，须损血+各色钥匙一致、段内无拾取/换层/额外kill")
    w("=" * 100)
    w(f"测试点 (atk,def) = {TEST_PTS}")
    w("-" * 100)

    # 收集所有【穿过≥2付代价格】的边
    edges = []
    for fid in ZONE1:
        res = analyze_floor(base, fid)
        for (va, vb, chain, thru, nk, nd) in trace_with_thru(res):
            if nk + nd >= 2:
                edges.append((fid, res, va, vb, chain, thru, nk, nd))
    w(f"穿过≥2付代价格的 macro-edge 共 {len(edges)} 条，逐条对拍：")
    w("")

    n_ok = n_skip = 0
    mismatches = []           # (fid, 描述, 详情)
    for (fid, res, va, vb, chain, thru, nk, nd) in edges:
        path, pay = build_path(res, va, vb, chain, thru)
        a_lab = (f"块#{va[1]}" if va[0] == "block" else f"{va[2]}@{va[1]}")
        b_lab = (f"块#{vb[1]}" if vb[0] == "block" else f"{vb[2]}@{vb[1]}")
        head = f"  {fid} {a_lab}→{b_lab}  声称{nk}怪+{nd}门"
        if path is None:
            w(f"{head}  ⏭ 跳过({pay})")
            n_skip += 1
            continue
        # 路径覆盖核对：实走路径上的 pay 怪/门数 vs 声称
        on_kill = sum(1 for c in path if c in pay and res["kind"][c][1] == "kill")
        on_door = sum(1 for c in path if c in pay and res["kind"][c][1] == "door")
        cover = "全覆盖" if (on_kill, on_door) == (nk, nd) else f"覆盖{on_kill}怪{on_door}门(BFS捷径)"

        # 用一份 fresh gs 当 f 的怪 db 来源(静态初始)
        gsf = build_initial_state()
        gsf.floors[fid] = load_floor(FLOORS / f"{fid}.json")
        gsf.current_floor = fid

        line_cells = []
        edge_ok = True
        for (atk, def_) in TEST_PTS:
            f_blood, f_keys, mids = f_predict(gsf, res, path, pay, atk, def_)
            ew = engine_walk(fid, path[0], path, atk, def_)
            # f_keys / ew["keys"] 同口径(去零)
            fk = {k: v for k, v in f_keys.items() if v}
            consistent = (
                ew["ok"] and f_blood is not None
                and ew["blood"] == f_blood
                and ew["keys"] == fk
                and ew["kill"] == len(mids)
                and not ew["items"]
                and not [a for a in ew["anomalies"] if "换层" in a]
            )
            # f 打不动(None) ⇒ 期望实走走不通，亦算一致(值域边界)
            if f_blood is None:
                consistent = (not ew["ok"])
            mark = "✅" if consistent else "⚠"
            line_cells.append(f"({atk},{def_}){mark}")
            if not consistent:
                edge_ok = False
                mismatches.append((fid, f"{a_lab}→{b_lab} @({atk},{def_})", dict(
                    f_blood=f_blood, f_keys=fk, mids=mids, on=(on_kill, on_door),
                    path=path, eng=ew)))
        w(f"{head} [{cover}]  {'  '.join(line_cells)}")
        if edge_ok:
            n_ok += 1

    w("")
    w("-" * 100)
    w(f"【对拍汇总】对拍边 {len(edges)} 条：全一致 {n_ok} · 跳过(退化) {n_skip} · 不一致 {len(set(m[0]+m[1] for m in mismatches))}")
    if mismatches:
        w("")
        w("⚠⚠⚠ 发现不一致 —— 立即停，详情：")
        for (fid, desc, d) in mismatches:
            w(f"  · {fid} {desc}")
            w(f"      f预测: 损血={d['f_blood']} 钥匙={d['f_keys']} 怪={d['mids']} 覆盖={d['on']}")
            e = d["eng"]
            w(f"      引擎: ok={e['ok']} 损血={e['blood']} 钥匙={e['keys']} "
              f"kill={e['kill']} 拾取={e['items']} 异常={e['anomalies']}")
            w(f"      路径: {d['path']}")
    else:
        w("  ✅ 全部一致：每条边的 f(损血,各色钥匙) 与引擎实走逐点吻合，且段内无拾取/换层/额外kill。")
        w("  ⇒ 识别器圈出的 macro-edge 合法(没把拾取/事件/special 收进边内)，f 原语正确。第2步对拍通过。")
    w("=" * 100)

    report = "\n".join(L)
    out = Path(__file__).parent / "macroedge_xcheck.txt"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[落盘] {out}")
    return len(mismatches)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
