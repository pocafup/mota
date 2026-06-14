"""【钥匙可达性·数据摸底诊断】回放 718/689 到终态，逐层 dump 钥匙家底，定位「718地上够得到1把、
689够得到3把」这个真实游戏观察【到底落在哪】——代码两套模型都对不上(门可过→14/21，门当墙→1/1)，
先用数据看清，绝不靠猜定口径(CLAUDE.md：数据不清就停下，不猜)。

每条 route 终态、逐一区层 dump：
  · 手里钥匙预算（各色）
  · 该层【仍锁】的钥匙门（terrain∈DOOR_KEY_MAP）位置+色；【已开】门（静态图是门但 terrain=0）位置+色
  · 地上剩余钥匙（entities∩_KEY_ITEMS）位置+色
  · 两套可达模型下每把钥匙的守怪损血：A门可过(doors-free) / B门当墙(doors-blocked)
回放与 tests/test_ga_navigate 同源。
"""
import sys
import json
import heapq
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, WALL_TILES, DOOR_KEY_MAP, _KEY_ITEMS
from solver.beam import _combat_damage
from solver.fitness import build_zone1_roster
from decode_route import parse_rle_route, decompress
from export_mt10_boss_route import make_initial_state

_NB4 = ((0, -1), (0, 1), (-1, 0), (1, 0))


def replay(route_file):
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    for a in actions:
        s = step(s, a)
        if s.dead:
            break
    return s, len(actions)


def _static_map(state, fid):
    floors_dir = getattr(state, "_floors_dir", None)
    if floors_dir is None:
        return None
    path = Path(floors_dir) / f"{fid}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("map", [])


def floor_layers(state, fid):
    """返回 (h, w, terrain_get, ent_get, t2i, t2e, visited)。
    visited 层 terrain/entities 真态；未访问层 terrain=ent=静态 map（门全锁、怪/钥匙全present）。"""
    shared_t2i = state.floor._tile_to_item
    shared_t2e = state.floor._tile_to_enemy
    fl = state.floors.get(fid)
    if fl is not None:
        ter, ents = fl.terrain, fl.entities
        h, w = len(ter), len(ter[0])
        return (h, w, lambda x, y: ter[y][x], lambda x, y: ents[y][x],
                fl._tile_to_item, fl._tile_to_enemy, True)
    grid = _static_map(state, fid)
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    return (h, w, lambda x, y: grid[y][x], lambda x, y: grid[y][x],
            shared_t2i, shared_t2e, False)


def reach_costs(state, fid, mode, afford=None):
    """楼梯多源 Dijkstra → 每把地上钥匙的守怪损血。
    mode='free' 门全可过 / 'block' 门全当墙 / 'budget' 仅手里有该色钥匙的门可过(afford=色集)。
    返回 ({(x,y): cost}, key_cells, locked_doors, opened_doors, src_cells)。"""
    lay = floor_layers(state, fid)
    if lay is None:
        return {}, [], [], [], []
    h, w, ter_get, ent_get, t2i, t2e, visited = lay
    static = _static_map(state, fid)
    afford = afford or set()

    def is_wall(x, y):
        t = ter_get(x, y)
        if t in WALL_TILES:
            return True
        if t in DOOR_KEY_MAP:                # 仍锁的钥匙门
            if mode == "free":
                return False
            if mode == "block":
                return True
            return DOOR_KEY_MAP[t] not in afford   # budget：手里有该色钥匙才可过
        return False

    # 静态图是门、但当前 terrain 已 0 → 该 route 已开的门（既成事实差异）
    opened, locked = [], []
    if static:
        for y in range(min(h, len(static))):
            for x in range(min(w, len(static[y]))):
                st = static[y][x]
                if st in DOOR_KEY_MAP:
                    cur = ter_get(x, y)
                    (opened if cur not in DOOR_KEY_MAP else locked).append(
                        (x, y, DOOR_KEY_MAP[st]))

    key_cells, mid_at, src_cells = [], {}, []
    for y in range(h):
        for x in range(w):
            if ter_get(x, y) in WALL_TILES:
                continue
            e = ent_get(x, y)
            if e and t2i.get(e) in _KEY_ITEMS:
                key_cells.append((x, y, t2i.get(e)))
            if e and t2e.get(e) is not None:
                mid_at[(x, y)] = t2e.get(e)
    cf = (state.floors[fid].change_floor if visited
          else json.loads((Path(state._floors_dir) / f"{fid}.json").read_text(encoding="utf-8")).get("changeFloor", {}))
    for loc in cf:
        try:
            sx, sy = map(int, loc.split(","))
        except (ValueError, AttributeError):
            continue
        if 0 <= sx < w and 0 <= sy < h and not is_wall(sx, sy):
            src_cells.append((sx, sy))

    cache = {}

    def enter(cell):
        if cell not in mid_at:
            return 0
        if cell not in cache:
            cache[cell] = _combat_damage(state, mid_at[cell])
        return cache[cell]

    dist, pq = {}, []
    for s in src_cells:
        c0 = enter(s)
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
            c = enter((nx, ny))
            if c is None:
                continue
            nd = d + c
            if nd < dist.get((nx, ny), float("inf")):
                dist[(nx, ny)] = nd
                heapq.heappush(pq, (nd, (nx, ny)))
    costs = {(x, y): dist[(x, y)] for (x, y, _k) in key_cells if (x, y) in dist}
    return costs, key_cells, locked, opened, src_cells


def main():
    R718 = ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"
    R689 = ROOT / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route"
    s718, _ = replay(R718)
    s689, _ = replay(R689)
    _roster, zone_fids, _all = build_zone1_roster(s718)
    print(f"一区层 zone_fids = {zone_fids}\n")

    CHEAP = 20   # 「便宜」阈值：守怪损血 ≤ 此值算用户口径的「13血净赚」cheap key
    for tag, s in [("718(耗尽)", s718), ("689(高潜力)", s689)]:
        afford = {k for k, v in s.hero.keys.items() if isinstance(v, (int, float)) and v > 0}
        print(f"{'='*78}\n{tag}  HP={s.hero.hp} ATK={s.hero.atk} DEF={s.hero.def_}  "
              f"手里钥匙={dict(s.hero.keys)}  可过门色={afford}\n{'='*78}")
        tot_free = tot_block = tot_budget = cheap_budget = 0
        for fid in zone_fids:
            cf, kc, locked, opened, src = reach_costs(s, fid, "free")
            cb, *_ = reach_costs(s, fid, "block")
            cu, *_ = reach_costs(s, fid, "budget", afford)
            if not kc and not locked and not opened:
                continue
            visited = fid in s.floors
            print(f"\n── {fid} ({'已访问' if visited else '未访问'}) 楼梯源={src}")
            if locked:
                print(f"   仍锁门: {[(x, y, k) for x, y, k in locked]}")
            if opened:
                print(f"   已开门: {[(x, y, k) for x, y, k in opened]}")
            if kc:
                print(f"   地上钥匙({len(kc)}): {[(x, y, k) for x, y, k in kc]}")
                for (x, y, k) in kc:
                    def fmt(d):
                        return "断" if d.get((x, y)) is None else str(d.get((x, y)))
                    tag_cheap = "  ★cheap" if (cu.get((x, y)) is not None
                                               and cu.get((x, y)) <= CHEAP) else ""
                    print(f"      ({x},{y},{k}): free={fmt(cf)} block={fmt(cb)} "
                          f"budget={fmt(cu)}{tag_cheap}")
            tot_free += len(cf)
            tot_block += len(cb)
            tot_budget += len(cu)
            cheap_budget += sum(1 for v in cu.values() if v <= CHEAP)
        print(f"\n  ▸ {tag} 地上够得到钥匙: free={tot_free}  block={tot_block}  "
              f"budget(手里钥色可过门)={tot_budget}  其中cheap(≤{CHEAP}血)={cheap_budget}")
        print()


if __name__ == "__main__":
    main()
