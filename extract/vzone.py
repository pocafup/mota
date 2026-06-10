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
from sim.simulator import _build_monster, WALL_TILES
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


# ───── 前置2：boss 层 V_zone 退化修复（beam-core 形态：吃 live GameState，D 指向 boss 格）─────
#
# 旧口径 shortest_toll(dst=None) = "到 MT10 任意格即 reach"。src 已在 MT10 → 立即 reach=0 →
# D=boss_toll=常量 → MT10 各格 V_zone=HP−常量、零朝 boss 梯度，每杀一只埋伏怪纯失血、零进度信用
# （vzone_verify_d_ambush 的 D0 诊断坐实：(6,5)/(6,4)/(1,11)/(6,8) reach 全 0、D 全 1045）。
#
# 修法：D 改成"走到并【打掉】boss 格的最短累计损血"——boss 格 enter-cost 即含 boss 战，不再单加 boss_toll：
#   · boss 已败(flag:BOSS_FLAG)   → D=0（区清，剩走到出口是零损血路）→ V_zone=HP（吸完奖励→出口最高）；
#   · 在 boss 层(BOSS_FLOOR)       → live 单层 Dijkstra 指向 live 队长格（埋伏后 (6,4)→(6,1)，扫 entities
#                                   实时定位），读现场 state.floors[MT10] → 杀掉的埋伏怪 enter-cost 归 0、
#                                   boss 战 toll 随属性现算（铁律：改图事件后不复用静态）；
#   · 在区内他层                   → 静态跨层图 shortest_toll 指向静态 boss 格(BOSS_CELL)，MT1-9 静止精确；
#   · 区外层                       → D=0（无区信息）。
#
# beam-core 形态：v_zone(zone, state) 吃【活 GameState】（与 beam.equiv_hp_over_roster 同形），将来按
# λ 旋钮塞进 beam 打分（V=…−λ·D）、λ=0 零回归。boss 层/格/旗此处在 extract/ 驱动层硬编（允许读 MT1-10）；
# 搬进 solver/ 时须改由 beam._is_region_boundary/build_future_roster 的塔无关门禁检测产出（不写死层号）。
#
# ⚠ 固有局限（明记不静默、非退化 bug，不可硬编码绕过）：最短路 D 只对【路径上】障碍记损血。MT10 埋伏是
#   "封房须清全 8 怪"语义——但乐观松弛下机关门 (6,3) 当可过、队长 (6,1) 经中央走廊((6,4)→(6,3)→(6,2))可达，
#   8 埋伏怪里只有踩在中央走廊上的 (6,4) 那只在到队长的最短路上（清它 D 才降），另 7 只在侧格、清它们 D 不降。
#   → kill-8 段 HP 降而 D 近平 → V_zone 会先跌、再于杀队长(预测的 boss 损血兑现，V_zone 近平)+吸奖励(D=0、
#   HP 跃升)一举到顶。这是最短路启发式建不出"封房全清"的本质，非 boss 层退化；且 D-findings 已证埋伏室一旦
#   踏入即被封、块抽象上连杀是唯一推进（怯战不可表达）→ 该 V_zone 跌幅无害（无更高-V 替代可逃）。

BOSS_FLOOR = "MT10"
BOSS_CELL = (6, 4)              # 静态队长格（埋伏前）；live 队长由 boss_cell_live 扫 entities 实时定位
BOSS_FLAG = "10f战胜骷髅队长"


def boss_cell_live(state, boss_mid):
    """扫当前 live 层 entities 找 boss(boss_mid) 当下坐标：埋伏后队长 (6,4)→(6,1)；杀后不在场→None。"""
    fl = state.floor
    ents = fl.entities
    for y in range(len(ents)):
        row = ents[y]
        for x in range(len(row)):
            if fl._tile_to_enemy.get(row[x]) == boss_mid:
                return (x, y)
    return None


def _live_passable(floor, x, y):
    """live 单层乐观可过：非硬墙(WALL_TILES ∪ _no_pass_tiles)即可过 —— 门/特殊门/假墙/楼梯/事件/拾取/
    怪格全当可过（admissible：D 低估真实损血、剪枝不错杀）。读现场 terrain（改图事件后不复用静态，铁律）。"""
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    if not (0 <= x < cols and 0 <= y < rows):
        return False
    t = floor.terrain[y][x]
    return t not in WALL_TILES and t not in floor._no_pass_tiles


def live_shortest_toll(state, src, dst, atk, def_, mdef):
    """live 单层 Dijkstra：src→走到并【打掉】dst 格的最小累计损血（dst enter-cost 即含其战斗）。
    enter_cost(格) = 该格 live 怪的强制可杀 toll（无怪→0），读现场 entities（铁律：改图后不复用静态）。
    无路→inf。src 任意（不限英雄当前格，供逐格梯度采样）。"""
    floor = state.floor
    dist = {src: 0}
    pq = [(0, src)]
    while pq:
        d, node = heapq.heappop(pq)
        if d > dist.get(node, float("inf")):
            continue
        if node == dst:
            return d
        x, y = node
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if not _live_passable(floor, nx, ny):
                continue
            mid = floor._tile_to_enemy.get(floor.entities[ny][nx])
            cost = _toll(_build_monster(state, mid), atk, def_, mdef) if mid is not None else 0
            nd = d + cost
            if nd < dist.get((nx, ny), float("inf")):
                dist[(nx, ny)] = nd
                heapq.heappush(pq, (nd, (nx, ny)))
    return float("inf")


def v_zone(zone, state):
    """【beam-core 形态】V_zone = HP − D，吃 live GameState。返回 (vz, D, info)。
    D = 走到并打掉 boss 的最短累计损血；boss 格 enter-cost 即含 boss 战，不再单加 boss_toll。口径见上段。"""
    h = state.hero
    fid = state.current_floor
    if fid not in zone["floors"]:
        return h.hp, 0, "off-zone"
    if h.flags.get(BOSS_FLAG):
        return h.hp, 0, "boss-cleared"            # 区已清 → D=0
    if fid == BOSS_FLOOR:
        bc = boss_cell_live(state, zone["boss_mid"])
        if bc is None:
            return h.hp, 0, "boss-gone"           # boss 不在场又没旗（异常）→ 保守 D=0
        D = live_shortest_toll(state, (h.x, h.y), bc, h.atk, h.def_, h.mdef)
        info = f"live→boss{bc}"
    else:
        dst = (BOSS_FLOOR, *BOSS_CELL)
        D = shortest_toll(zone, (fid, h.x, h.y), h.atk, h.def_, h.mdef, dst=dst)
        if D != float("inf") and dst not in zone["mon_cache"]:
            D += boss_toll(zone, h.atk, h.def_, h.mdef)   # boss 格非 pay-kill 时补 boss 战 toll
        info = f"static→{BOSS_FLOOR}{BOSS_CELL}"
    if D == float("inf"):
        return float("-inf"), float("inf"), info + "/UNREACH"
    return h.hp - D, D, info


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
