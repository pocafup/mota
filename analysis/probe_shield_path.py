"""拿盾具体卡点【只读诊断】——对照玩家观察"拿盾只要两三把钥匙"。

不改求解逻辑。算从【搜索起点】(噩梦后 MT3) 到 MT9 铁盾格的【最省钥匙】路：
  · 列这条路要开哪几道门(颜色/层/坐标)、各色几把钥匙；
  · 列路上挡着的怪(坐标/防/在 atkX 下可不可杀/真损血)；
  · 起点持钥够不够；
分 atk=10(起点裸属性) 与 atk=20(拿了 MT5 铁剑后) 两档跑——看"拿盾"是否被"先拿剑杀挡路怪"耦合。

门/怪/楼梯全读 data/ 经 build_zone 真算（铁律：不手推路径、不写死层号）。
"""
import heapq
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import _build_monster, DOOR_KEY_MAP, _KEY_ITEMS
from sim.combat import PlayerState, compute_combat
from vzone import build_zone, _passable, _zone_attr_gems
from probe_crossfloor import build_start

_NB4 = [(0, -1), (0, 1), (-1, 0), (1, 0)]
_BIG = 10 ** 9


def _door_color(zone, node):
    fid, x, y = node
    fl = zone["floors"][fid]["floor"]
    return DOOR_KEY_MAP.get(fl.terrain[y][x])     # None=非门


def _ground_key(zone, node):
    fid, x, y = node
    fl = zone["floors"][fid]["floor"]
    iid = fl._tile_to_item.get(fl.entities[y][x])
    return iid if iid in _KEY_ITEMS else None


def _monster(zone, node):
    return zone["mon_cache"].get(node)


def _killable(mon, atk):
    return atk > mon.def_                          # 一区无 special：能破防⟺可杀


def _blood(base, mon, atk, def_, mdef=0):
    ps = PlayerState(hp=_BIG, atk=atk, def_=def_, mdef=mdef)
    res = compute_combat(ps, mon)
    if res is None or res.damage is None:
        return None
    return res.damage


def min_key_path(zone, src, dst, atk, def_, mdef=0):
    """最省钥匙路：代价向量按字典序 (开门总数, 损血, 步数)。挡路怪在 atk 下不可杀→当墙(此 atk 走不过)。
    返回 (cost_tuple, path) 或 (None, None)。门免费过(只计数)、地上钥匙不抵扣(单算净需，gross 门数=要花的钥)。"""
    start = (0, 0, 0, src)            # (doors, blood, steps, node)
    best = {src: (0, 0, 0)}
    prev = {}
    pq = [start]
    while pq:
        doors, blood, steps, node = heapq.heappop(pq)
        if (doors, blood, steps) > best.get(node, (1e18,)):
            continue
        if node == dst:
            path = [node]
            n = node
            while n in prev:
                n = prev[n]
                path.append(n)
            path.reverse()
            return (doors, blood, steps), path
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in zone["links"]:
            nbrs.append(zone["links"][node])
        for nb in nbrs:
            if not _passable(zone, nb):
                continue
            mon = _monster(zone, nb)
            if mon is not None and not _killable(mon, atk):
                continue                              # 此 atk 杀不动→挡死(当墙)
            nd = doors + (1 if _door_color(zone, nb) else 0)
            nbl = blood + (_blood(zone["_base"], mon, atk, def_, mdef) or 0 if mon else 0)
            nst = steps + 1
            cand = (nd, nbl, nst)
            if cand < best.get(nb, (1e18,)):
                best[nb] = cand
                prev[nb] = node
                heapq.heappush(pq, (nd, nbl, nst, nb))
    return None, None


def describe(zone, path, atk, def_, mdef=0):
    doors, mons, gkeys = [], [], []
    for node in path:
        c = _door_color(zone, node)
        if c:
            doors.append((node, c))
        gk = _ground_key(zone, node)
        if gk:
            gkeys.append((node, gk))
        mon = _monster(zone, node)
        if mon is not None:
            mons.append((node, mon.def_, _killable(mon, atk),
                         _blood(zone["_base"], mon, atk, def_, mdef)))
    return doors, mons, gkeys


def main():
    start = build_start()[0]
    base = start                       # build_zone 会读 floors；用全初始态建静态区图
    zone = build_zone()
    zone["_base"] = base
    h = start.hero
    src = (start.current_floor, h.x, h.y)
    start_keys = {k: v for k, v in h.keys.items() if v}

    # 定位 MT9 铁盾格（def+10 攻防宝石）
    gems = _zone_attr_gems(zone)
    shield = [(cell, d) for cell, d in gems.items() if cell[0] == "MT9" and d[1] >= 10]
    print("=" * 90)
    print(f"搜索起点: {src}  HP={h.hp} ATK={h.atk} DEF={h.def_}  持钥={start_keys}")
    print(f"MT9 def+10 盾格候选: {shield}")
    if not shield:
        print("⚠ 没在 MT9 找到 def+10 盾格——核对 _zone_attr_gems")
        return
    dst = shield[0][0]
    print(f"目标盾格 dst={dst}  (玩家口径 (9,7))")
    print("=" * 90)

    for atk in (h.atk, 20):           # 起点裸 atk vs 拿铁剑后 atk20
        print(f"\n──── 在 ATK={atk} DEF={h.def_} 下，起点→盾格 最省钥匙路 ────")
        cost, path = min_key_path(zone, src, dst, atk, h.def_)
        if path is None:
            print(f"  ✗ ATK={atk} 下【走不到】盾格（被杀不动的挡路怪截断）")
            continue
        doors, mons, gkeys = describe(zone, path, atk, h.def_)
        from collections import Counter
        dc = Counter(c for _, c in doors)
        print(f"  路长 {cost[2]} 步，开门 {cost[0]} 道，路上损血 {cost[1]}")
        print(f"  开门明细(共{len(doors)}): " + (", ".join(f"{c}@{n[0]}{n[1:]}" for n, c in doors) or "无"))
        print(f"  各色钥匙需求: {dict(dc)}   起点持钥: {start_keys}")
        if gkeys:
            print(f"  路上可捡地上钥匙(抵扣净需): {[(g, n) for n, g in gkeys]}")
        if mons:
            print(f"  路上挡路怪(共{len(mons)}): "
                  + ", ".join(f"{n}(def{d},{'可杀'if k else '杀不动'},血{b})" for n, d, k, b in mons))
        else:
            print("  路上无怪")
        # 经过哪些层
        floors_seq = []
        for n in path:
            if not floors_seq or floors_seq[-1] != n[0]:
                floors_seq.append(n[0])
        print(f"  跨层序: {' → '.join(floors_seq)}")
    print("=" * 90)


if __name__ == "__main__":
    main()
