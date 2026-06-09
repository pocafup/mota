"""V_zone 第一版【格级损血最短路】MVP 实现（extract/ 隔离，不碰 solver 核心）。

  V_zone(state) = HP − D ；  D = (当前格 →到达 MT10 boss 层 的最小累计损血) + boss 战损血

第一版口径（全部 admissible 方向 = D 低估真实损血 → V_zone 乐观上界，剪枝不错杀）：
  · 损血来源 = 普通怪门格(pay-kill)：toll = 引擎 compute_combat 在【强制可杀参照 atk=max(atk,怪防+1)】
    下算（复用 beam._future_toll 口径，铁律不手写战斗公式）。一区 special-mon=0 → 全普通怪、无 special
    修正，这是损血主体且精确。
  · 钥匙门/special-door/event/npc/假墙/battle-hook 格 = 零代价过路（钥匙第一版忽略交 beam 保护维；
    其余忽略损血 → D 偏小 → 仍下界）。⚠ MT2(6,2)(8,2)/MT8(9,5)(11,5) 4 个 battle-hook 怪被当零代价
    略过(序章+boss区少数，标注不静默)。
  · 跨层 = 楼梯免费边（change_floor 的 downFloor↔对面 upFloor 配对），零损血。
  · 属性固定当前值算全路径（不预见路上拿剑涨属性）→ 误差只在剑/盾大跳变处大、小宝石小（玩家已认可）。
    "预见拿剑"靠 beam 展开到拿剑态看 V_zone 跳升，不靠单点最短路内部绕路。
  · boss：到 MT10 层(任意格)即停 + boss 战 toll(同强制可杀参照)；打不过→grind 巨大值→V_zone 极低(满足型)。
    MT10 层内到 boss 真身的损血+埋伏可达忽略(归第3步运行时)。

格级 vs 块级：数值等价"收缩图最短路"(FREE 块内零损血、收缩无损)；用格级避免块级 ≥3 端点簇"整簇全穿"
高估端点对损血而破坏 admissible。167块/83边的块塌缩=纯性能优化，格级(~800格 Dijkstra 微秒级)已够。
"""
import heapq
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state
from sim.simulator import _build_monster
from sim.combat import PlayerState, compute_combat
from seg_identify_zone1 import analyze_floor, ZONE1

_BIG_HP = 10 ** 9


def _toll(mon, atk, def_, mdef):
    """单怪损血：强制可杀参照 atk=max(atk,怪防+1)，复用引擎 compute_combat。打不动→grind 估、纯无敌→0。"""
    ref_atk = atk if atk > mon.def_ else mon.def_ + 1
    ps = PlayerState(hp=_BIG_HP, atk=ref_atk, def_=def_, mdef=mdef)
    res = compute_combat(ps, mon)
    if res is None or res.damage is None:
        return 0
    return res.damage


def build_zone(base=None):
    """建一区格级跨层图：每层格分类(kind) + 楼梯配对(links) + 普通怪 monster 缓存 + boss monster。"""
    if base is None:
        base = build_initial_state()
    floors = {}
    for fid in ZONE1:
        floors[fid] = analyze_floor(base, fid)   # dict(kind, floor, ...)；并 set base.floors[fid]

    # 楼梯配对：downFloor 格 ↔ 下一层 upFloor 格
    up_stair, down_stair = {}, {}
    for fid in ZONE1:
        fl = floors[fid]["floor"]
        for loc, tgt in fl.change_floor.items():
            x, y = map(int, loc.split(","))
            s = tgt.get("stair")
            if s == "downFloor":
                down_stair[fid] = (x, y)
            elif s == "upFloor":
                up_stair[fid] = (x, y)
    links = {}
    for i, fid in enumerate(ZONE1[:-1]):
        nf = ZONE1[i + 1]
        if fid in down_stair and nf in up_stair:
            a = (fid, *down_stair[fid])
            b = (nf, *up_stair[nf])
            links[a] = b
            links[b] = a

    # 普通怪 monster 缓存（与 hero 无关，建图一次）
    mon_cache = {}
    for fid in ZONE1:
        r = floors[fid]
        fl = r["floor"]
        base.current_floor = fid
        base.floors[fid] = fl
        for (x, y), (k, info) in r["kind"].items():
            if k == "pay" and info == "kill":
                mid = fl._tile_to_enemy.get(fl.entities[y][x])
                if mid is not None:
                    mon_cache[(fid, x, y)] = _build_monster(base, mid)

    # boss monster：MT10 (6,4) 队长（静态格；stats 与位置/搬家无关）
    base.current_floor = "MT10"
    fl10 = floors["MT10"]["floor"]
    boss_mid = fl10._tile_to_enemy.get(fl10.entities[4][6])
    boss_mon = _build_monster(base, boss_mid) if boss_mid is not None else None

    return dict(floors=floors, links=links, mon_cache=mon_cache,
                boss_mon=boss_mon, boss_mid=boss_mid,
                up_stair=up_stair, down_stair=down_stair)


def _passable(zone, node):
    fid, x, y = node
    k = zone["floors"][fid]["kind"].get((x, y))
    return k is not None and k[0] != "wall"


_NB4 = [(0, -1), (0, 1), (-1, 0), (1, 0)]


def _enter_cost(zone, node, atk, def_, mdef):
    m = zone["mon_cache"].get(node)
    return _toll(m, atk, def_, mdef) if m is not None else 0


def shortest_toll(zone, src, atk, def_, mdef, return_path=False, dst=None):
    """src=(fid,x,y) → 到达【MT10 层任意格(dst=None)】或【指定格 dst】的最小累计损血(不含 boss 战)。无路→inf。"""
    dist = {src: 0}
    prev = {}
    pq = [(0, src)]
    target = None
    while pq:
        d, node = heapq.heappop(pq)
        if d > dist.get(node, float("inf")):
            continue
        reached = (node == dst) if dst is not None else (node[0] == "MT10")
        if reached:
            target = node
            break                                   # 第一个弹出即最小 dist
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in zone["links"]:
            nbrs.append(zone["links"][node])
        for nb in nbrs:
            if not _passable(zone, nb):
                continue
            nd = d + _enter_cost(zone, nb, atk, def_, mdef)
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = node
                heapq.heappush(pq, (nd, nb))
    if target is None:
        return (float("inf"), None) if return_path else float("inf")
    if not return_path:
        return dist[target]
    path = []
    n = target
    while n is not None:
        path.append(n)
        n = prev.get(n)
    path.reverse()
    return dist[target], path


def boss_toll(zone, atk, def_, mdef):
    if zone["boss_mon"] is None:
        return 0
    return _toll(zone["boss_mon"], atk, def_, mdef)


def vzone(zone, fid, x, y, hp, atk, def_, mdef):
    reach = shortest_toll(zone, (fid, x, y), atk, def_, mdef)
    if reach == float("inf"):
        return float("-inf"), float("inf"), 0
    bf = boss_toll(zone, atk, def_, mdef)
    D = reach + bf
    return hp - D, reach, bf


# ────────────────────────────── 自检 ──────────────────────────────
def _selfcheck():
    zone = build_zone()
    print("=" * 84)
    print("V_zone 模块自检")
    print("=" * 84)
    print("【楼梯链】")
    seen = set()
    for a, b in zone["links"].items():
        key = tuple(sorted([a, b]))
        if key in seen:
            continue
        seen.add(key)
        print(f"   {a}  ↔  {b}")

    bm = zone["boss_mon"]
    print(f"\n【boss】MT10(6,4) mid={zone['boss_mid']}  "
          f"hp={bm.hp} atk={bm.atk} def={bm.def_}")
    for a in (10, 20, 40, 80):
        print(f"   boss_toll(atk={a},def=10) = {boss_toll(zone, a, 10, 0)}")

    print("\n【MT3 普通怪 toll：找骷髅(玩家 oracle 裸打~400 / 拿剑后<100)】")
    for (fid, x, y), m in sorted(zone["mon_cache"].items()):
        if fid != "MT3":
            continue
        t10 = _toll(m, 10, 10, 0)
        t20 = _toll(m, 20, 10, 0)
        tag = "  ← 疑似骷髅(裸打~400)" if 300 <= t10 <= 600 else ""
        print(f"   {fid}({x},{y}) mid={m.id if hasattr(m,'id') else '?'} "
              f"hp={m.hp} atk={m.atk} def={m.def_}  toll(atk10)={t10}  toll(atk20)={t20}{tag}")

    print("\n【验证 A2 雏形：MT3 入口(1,11)→boss 最短路损血】")
    for a in (10, 20):
        reach, path = shortest_toll(zone, ("MT3", 1, 11), a, 10, 0, return_path=True)
        bf = boss_toll(zone, a, 10, 0)
        plen = len(path) if path else 0
        print(f"   atk={a},def=10 :  到MT10损血={reach}  + boss战={bf}  = D={reach + bf}"
              f"   (路径 {plen} 格)")

    print("=" * 84)


if __name__ == "__main__":
    _selfcheck()
