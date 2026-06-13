"""只读拓扑探针：MT3 骷髅(209)@(1,7) 是不是【出 MT3 上行(→MT4→…→MT5 铁剑)】的必经卡点？

玩家的判定口径(本会话拍板)：
  - 若必经(割点) = 估值救不了，是拓扑约束，别把它当视野/估值病去修；
  - 若可绕       = pull 该能保住"绕骷髅奔上层"前沿，归 pull 管。

铁律：连通性由代码 BFS 算出，绝不手推。本探针只读 data/ 与真实起点，不改 sim/solver、不进搜索。

拓扑稳定性论证：MT3 afterBattle/afterOpenDoor/openDoor 全空，唯一 events 是 (5,9) 一次性开局噩梦
(flag:03 门控，过场后不再触发)。墙体不随拾取/战斗变化(道具本就可踩) → 用 MT3.json 原始地图即权威拓扑。

可通行口径(tiles.json 权威)：
  硬墙 = noPass:true 的 walls/terrains/animates(本层仅 tile 1 yellowWall)；
  门(81-86) 几何上当【可开】(钥匙是另一维资源，不是拓扑墙)；
  怪物默认当【可过路】(战斗是另一维代价)，但提供"把某怪当墙"的逐怪割点测试；
  NPC(121 老人) 撞而不入 → 当障碍。
"""
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).parent.parent
TILES = json.loads((ROOT / "data/games51/tiles.json").read_text(encoding="utf-8"))
MT3 = json.loads((ROOT / "data/games51/floors/MT3.json").read_text(encoding="utf-8"))

GRID = MT3["map"]            # map[y][x]
H = len(GRID)
W = len(GRID[0])

# ── tiles.json 权威分类 ───────────────────────────────────────────────
HARD_WALL = set()
for grp in ("walls", "terrains", "animates"):
    for tid, info in TILES.get(grp, {}).items():
        if info.get("noPass") is True and "keys" not in info:  # 门有 keys，不算硬墙
            HARD_WALL.add(int(tid))
DOOR_TILES = {int(t) for t, i in TILES.get("animates", {}).items() if "keys" in i}
MON_TILES = {int(t) for t in TILES.get("enemys", {})}
NPC_TILES = {int(t) for t in TILES.get("npcs", {})}

SKELETON = (1, 7)            # map[7][1] = 209
EXIT_UP = (11, 11)          # changeFloor["11,11"] → :next(MT4) 上行出口
EXIT_DOWN = (1, 11)         # changeFloor["1,11"]  → :before(MT2) 回退出口
LANDING_DOWNFLOOR = tuple(MT3["downFloor"])   # [2,11] 自上层下来的落点
LANDING_UPFLOOR = tuple(MT3["upFloor"])       # [10,11] 自下层上来的落点


def cell_tiles():
    """枚举本层所有 tile 坐标，便于报告。"""
    out = {}
    for y in range(H):
        for x in range(W):
            out[(x, y)] = GRID[y][x]
    return out


def bfs(start, blocked):
    """4 向 BFS。blocked: 一个 (x,y)->bool 的判定。返回可达 (x,y) 集合。"""
    if blocked(*start):
        return set()
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen and not blocked(nx, ny):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def make_blocked(*, extra_block=frozenset(), doors_as_wall=False,
                 monsters_as_wall=False, allow_monster_cells=frozenset()):
    """构造 blocked 判定。
    硬墙+NPC 永远挡；门可选当墙；怪物可选当墙(allow_monster_cells 里的怪格放行)；
    extra_block 强制额外挡格(测试主体，如骷髅)。"""
    def blocked(x, y):
        if (x, y) in extra_block:
            return True
        t = GRID[y][x]
        if t in HARD_WALL or t in NPC_TILES:
            return True
        if doors_as_wall and t in DOOR_TILES:
            return True
        if monsters_as_wall and t in MON_TILES and (x, y) not in allow_monster_cells:
            return True
        return False
    return blocked


def monster_cells():
    out = []
    for y in range(H):
        for x in range(W):
            if GRID[y][x] in MON_TILES:
                out.append((x, y))
    return out


def reach_report(name, start, blocked, targets):
    seen = bfs(start, blocked)
    line = f"  [{name}] 从 {start} 可达 {len(seen)} 格"
    for tname, tcell in targets:
        mark = "✅可达" if tcell in seen else "❌不可达"
        line += f" | {tname}{tcell} {mark}"
    print(line)
    return seen


def main():
    print("=" * 92)
    print("MT3 拓扑割点探针：骷髅(209)@(1,7) 是否上行出 MT3 的必经卡点")
    print("=" * 92)
    print(f"地图 {W}×{H}；硬墙tile={sorted(HARD_WALL)}；门tile={sorted(DOOR_TILES)}；"
          f"NPCtile={sorted(NPC_TILES)}")
    print(f"骷髅格={SKELETON}(tile {GRID[SKELETON[1]][SKELETON[0]]})  "
          f"上行出口 :next→MT4 ={EXIT_UP}(tile {GRID[EXIT_UP[1]][EXIT_UP[0]]})  "
          f"回退出口 :before→MT2 ={EXIT_DOWN}(tile {GRID[EXIT_DOWN[1]][EXIT_DOWN[0]]})")
    mons = monster_cells()
    print(f"本层怪格({len(mons)})：" + "  ".join(f"{c}={GRID[c[1]][c[0]]}" for c in mons))

    # 真实入口(穿过 82 token 开局噩梦) —— 权威起点；失败则仅用两个楼梯落点
    real_entry = None
    st = None
    try:
        from probe_crossfloor import build_start
        st, _ = build_start()
        real_entry = (st.hero.x, st.hero.y)
        print(f"真实起点(build_start, 穿 82 token 噩梦后): {st.current_floor}{real_entry}  "
              f"HP={st.hero.hp} ATK={st.hero.atk} DEF={st.hero.def_}")
    except Exception as e:
        print(f"⚠ build_start 取真实入口失败({e!r})；改用两个楼梯落点交叉验证")

    entries = []
    if real_entry is not None:
        entries.append(("真实入口", real_entry))
    entries.append(("downFloor落点", LANDING_DOWNFLOOR))
    entries.append(("upFloor落点", LANDING_UPFLOOR))

    targets = [("上行→MT4", EXIT_UP), ("回退→MT2", EXIT_DOWN), ("骷髅格", SKELETON)]

    print("-" * 92)
    print("① 基线(门可开、所有怪可过路、仅硬墙+NPC挡)——确认出口本就可达：")
    base_blocked = make_blocked()
    base_seen = {}
    for name, e in entries:
        base_seen[name] = reach_report(name, e, base_blocked, targets)

    print("-" * 92)
    print("② 骷髅当墙(其余同基线)——若上行出口仍可达=骷髅可绕；不可达=骷髅必经：")
    skel_blocked = make_blocked(extra_block={SKELETON})
    for name, e in entries:
        if e == SKELETON:
            print(f"  [{name}] 起点即骷髅格，跳过")
            continue
        reach_report(name, e, skel_blocked, targets)

    print("-" * 92)
    print("③ 逐怪割点：把单只怪当墙(其余怪可过路、门可开)，看上行出口是否仍可达：")
    primary_entry = entries[0][1]
    for mc in mons:
        b = make_blocked(extra_block={mc})
        seen = bfs(primary_entry, b)
        mid = GRID[mc[1]][mc[0]]
        mname = TILES["enemys"].get(str(mid), {}).get("id", str(mid))
        tag = "❌必经(割点)" if EXIT_UP not in seen else "可绕"
        print(f"  怪 {mname}{mc} 当墙 → 上行出口 {EXIT_UP}: {tag}（从{primary_entry}可达{len(seen)}格）")

    print("-" * 92)
    print("④ 门当墙(无钥匙，所有怪可过路、骷髅可过路)——看门是否单独卡死上行出口：")
    door_blocked = make_blocked(doors_as_wall=True)
    for name, e in entries:
        reach_report(name + "/无钥匙", e, door_blocked, targets)

    print("-" * 92)
    print("⑤ 骷髅到底守着什么：基线可达集 − 骷髅当墙可达集 = 仅经骷髅才能到的格：")
    pe_name, pe = entries[0]
    only_via_skel = base_seen[pe_name] - bfs(pe, skel_blocked)
    if SKELETON in only_via_skel:
        only_via_skel = only_via_skel - {SKELETON}
    if only_via_skel:
        labeled = []
        for c in sorted(only_via_skel):
            t = GRID[c[1]][c[0]]
            tag = ""
            if c == EXIT_UP:
                tag = "[上行出口!]"
            elif c == EXIT_DOWN:
                tag = "[回退出口]"
            elif t in MON_TILES:
                tag = f"[怪{TILES['enemys'].get(str(t), {}).get('id', t)}]"
            elif t in DOOR_TILES:
                tag = "[门]"
            labeled.append(f"{c}{tag}")
        print(f"  仅经骷髅可达({len(only_via_skel)}格，从{pe_name}{pe})：" + "  ".join(labeled))
    else:
        print(f"  无——骷髅不独占任何格(纯死路怪)，绕过它不损失任何可达区域")

    # ⑥ 裸态损血：必经的两只 slime 割点 vs 可绕的骷髅 —— 定位"384 裸打"是哪只、归不归 pull
    if st is not None:
        print("-" * 92)
        print("⑥ 裸态(真实入口属性)损血：引擎 compute_combat 算，非手推。"
              "必经割点 vs 可绕骷髅，定位'384 裸打'：")
        try:
            from sim.simulator import _build_monster
            from sim.combat import PlayerState, compute_combat
            ps = PlayerState(hp=st.hero.hp, atk=st.hero.atk, def_=st.hero.def_, mdef=st.hero.mdef)
            tag_by_cell = {
                (7, 5): "必经割点", (8, 10): "必经割点", (1, 7): "可绕(守宝袋)",
            }
            for (x, y) in [(7, 5), (8, 10), (1, 7)]:
                mid = TILES["enemys"].get(str(GRID[y][x]), {}).get("id")
                if mid is None:
                    continue
                mon = _build_monster(st, mid)
                res = compute_combat(ps, mon)
                dmg = res.damage
                dtxt = "打不动(不可击杀)" if dmg is None else f"{dmg} 损血"
                role = tag_by_cell.get((x, y), "")
                print(f"  {mid}({x},{y}) [{role}]  hp{mon.hp}/atk{mon.atk}/def{mon.def_}"
                      f" special={mon.special} → {dtxt}")
        except Exception as e:
            print(f"  ⚠ 损血计算失败({e!r})")

    # ⑦ 资源感知(钥匙/门)定点可达：骷髅当墙时，靠袋外钥匙能否开门抵达上行出口
    #    —— 钥匙同质(全 yellowKey)，开门只增不减可达，定点迭代即最优用钥结果(非手数)
    YK_TILE = 21      # yellowKey
    YDOOR_TILE = 81   # yellowDoor
    all_doors = [(x, y) for y in range(H) for x in range(W) if GRID[y][x] == YDOOR_TILE]

    def key_aware_reach(start, skeleton_is_wall):
        """怪物可过路(战斗是另一维)，骷髅可选当墙；门需 yellowKey 开(同质可数)。返回(可达集, 最终持钥, 开门数)。"""
        opened = set()
        while True:
            def blk(x, y):
                if skeleton_is_wall and (x, y) == SKELETON:
                    return True
                t = GRID[y][x]
                if t in HARD_WALL or t in NPC_TILES:
                    return True
                if t == YDOOR_TILE and (x, y) not in opened:
                    return True   # 未开的门当墙
                return False       # 其余(含怪/其它道具/楼梯)放行
            R = bfs(start, blk)
            keys = sum(1 for c in R if GRID[c[1]][c[0]] == YK_TILE)
            budget = keys - len(opened)
            boundary = [d for d in all_doors if d not in opened
                        and any((d[0] + dx, d[1] + dy) in R
                                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
            newly = boundary[:max(0, budget)]
            if not newly:
                return R, keys, len(opened)
            opened |= set(newly)

    print("-" * 92)
    print("⑦ 资源感知(钥匙/门)定点可达：骷髅当墙时靠【袋外】钥匙能否开门到上行出口："
          f"（本层 yellowKey={sum(1 for y in range(H) for x in range(W) if GRID[y][x]==YK_TILE)} 把，"
          f"yellowDoor={len(all_doors)} 道）")
    pe = entries[0][1]
    Rc, kc, oc = key_aware_reach(pe, skeleton_is_wall=False)
    print(f"  控制组(骷髅可过路): 从{pe} 可达{len(Rc)}格, 收钥{kc} 开门{oc} → "
          f"上行出口{EXIT_UP} " + ("✅可达" if EXIT_UP in Rc else "❌不可达"))
    Rs, ks, os_ = key_aware_reach(pe, skeleton_is_wall=True)
    print(f"  测试组(骷髅当墙): 从{pe} 可达{len(Rs)}格, 收钥{ks} 开门{os_} → "
          f"上行出口{EXIT_UP} " + ("✅可达=钥匙也不靠骷髅，骷髅彻底可选"
                                 if EXIT_UP in Rs else "❌不可达=出口需骷髅袋里那把钥匙"))

    print("=" * 92)


if __name__ == "__main__":
    main()
