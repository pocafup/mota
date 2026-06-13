"""一区(MT1-10) 真实可达钥匙稀缺度【只读测量探针】(extract/ 隔离，零碰 sim/solver/beam)。

玩家纠正的根本错误(2026-06-10)：算钥匙稀缺度【不能用地图总钥匙数】，要用「当前阶段(打一区时)
真正可达、且代价合理值得拿的钥匙」。很多钥匙被高区怪/强守门怪挡着，要后面阶段(打通 boss、上高区
加属性)才回来拿——铁例子：MT2 三把黄钥守的是【三区的怪】、MT8 右下钥匙守门怪很强。

本探针不解塔、不手推：所有可达性/可杀性/属性增长全部走引擎原语——
  · 可杀门禁 = compute_combat(英雄【实际】atk) 是否打得动(damage 非 None)；打不动=高区怪硬墙。
  · 属性增长 = _apply_item_effect(引擎拾取效果)，吸到剑/宝石→atk/def 涨→更多怪可杀→可达扩张。
  · 钥匙/门色 = DOOR_KEY_MAP / _tile_to_item∩_KEY_ITEMS，从源码地形读，不写死。
  · 起点 = build_start()(穿强制开局噩梦后的真 MT3 态 hp400/atk10/def10/keys=0)，不硬编码。
  · 一区静态图 = build_zone()(各层初始 terrain，与 vzone/seg_identify_zone1 同口径)。

口径(admissible 方向，专防「过高估供给→误判富余」的老错误)：
  · 单调能力不动点：吸可达的属性道具→atk/def 涨→重新泛洪，直到无新道具(能力只增→可达只增→停机)。
  · 门用【两括号】：
      U(上界可达) door=免费过路(∞钥)、node 一律放行(generous)、普通怪只挡【实际 atk 打不动】的。
      L(下界可达) door=墙(0 钥不开任何门)、node 只放行 楼梯/拾取(保守)、普通怪同 U 门禁。
    → 供给上界 supply_U ≥ 真可达供给 ≥ supply_L 下界；门需求 demand_L ≤ 真需求 ≤ demand_U。
  · 稀缺判定(严格)：supply_U < demand_L ⇒【确定稀缺、必抉择】；supply_L ≥ demand_U ⇒【确定充裕】；
    其间 ⇒ 取决于开门次序(=本身就要抉择)。这样即便对特殊怪/特殊门「乐观放行」也不会错判成富余。

⚠ 局限(明记不静默)：① 静态初始 terrain，firstArrive/setEnemy 动态未应用(同 vzone 口径，归运行时)。
  ② 不建模特殊怪战斗(U 里乐观当可杀放行=可能高估供给→所以稀缺判定用 supply_U<demand_L 兜)。
  ③ 不跟踪血预算(可达=结构可达，不含「血不够」)；可达钥匙的损血代价单列(§5)供「值不值得拿」参考。
  ④ after_get_item 副作用未结算(同其他探针归第3步)。塔无关性不适用(extract/驱动层，可读 MT1-10)。
"""
import copy
import sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start
from seg_experiment import FLOORS, build_initial_state
from sim.simulator import (load_floor, _apply_item_effect, _KEY_ITEMS,
                           DOOR_KEY_MAP, _build_monster)
from sim.combat import PlayerState, compute_combat
from vzone import build_zone, _zone_key_geometry
from seg_identify_zone1 import ZONE1

_BIG_HP = 10 ** 9
_NB4 = [(0, -1), (0, 1), (-1, 0), (1, 0)]
_COLOR_ORDER = ["yellowKey", "blueKey", "redKey", "greenKey", "steelKey", "bigKey"]


def _cname(c):
    return c.replace("Key", "")


# ───────────────── 引擎原语封装(不手写战斗/拾取) ─────────────────

def _real_toll(mon, atk, def_, mdef, has_cross, has_knife):
    """实际 atk 下单怪损血；打不动(atk≤防、无破甲穿透)→None(= 高区怪硬墙)。"""
    res = compute_combat(PlayerState(hp=_BIG_HP, atk=atk, def_=def_, mdef=mdef),
                         mon, has_cross=has_cross, has_knife=has_knife)
    if res is None or res.damage is None:
        return None
    return res.damage


def build_all_monsters(zone):
    """全怪缓存：一区每个怪格→Monster(含【战斗钩子/special 怪】，不止 build_zone 的普通怪)。
    关键修正：守门怪(MT2 blueGuard def110、MT8 yellowGuard def22)挂 afterBattle→被 classify 当
    battle-hook 节点，但它【是怪】，可不可过得看打不打得动，不能因挂钩子就免费放行。"""
    base = build_initial_state()
    cache = {}
    for fid in ZONE1:
        fl = zone["floors"][fid]["floor"]
        base.current_floor = fid
        base.floors[fid] = fl
        for y in range(len(fl.entities)):
            for x in range(len(fl.entities[y])):
                mid = fl._tile_to_enemy.get(fl.entities[y][x])
                if mid is not None:
                    cache[(fid, x, y)] = _build_monster(base, mid)
    return cache


def _absorb_one(hero, fl, iid):
    """照搬引擎 _pickup_item 的拾取分支(略 after_get_item 副作用)：钥匙→预算；属性道具→_apply_item_effect。"""
    if iid in _KEY_ITEMS:
        hero.keys[iid] = hero.keys.get(iid, 0) + 1
        return
    idata = fl._items_db.get(iid)
    if not idata:
        return
    effect = idata.get("pickup")
    if effect is None:
        hero.items[iid] = hero.items.get(iid, 0) + 1
    else:
        _apply_item_effect(hero, effect, fl.ratio)


# ───────────────── 可达性泛洪 + 单调能力不动点 ─────────────────

def _passable(zone, all_mon, geom, nb, hero, door_mode, open_colors, record_block=None):
    """nb 在当前能力下是否可过。door_mode:
       'free'(U 上界·门全免费) / 'wall'(L 下界·门全当墙) / 'color'(真可达·门按色门禁)。
    'color'：某色门可过 ⟺ 该色【已到手≥1 把钥匙】(open_colors)；0 钥色(钢)门=永久墙=精确，
       ≥1 钥色门一律放行=不追踪花费=上界(开 ALL 同色门乐观)。→ 仍是上界，但封死『拿不到的钥匙』所在坑。
    任何【怪格】(普通/战斗钩子/special 一视同仁)：可过 ⟺ 实际 atk 打得动(compute_combat damage≠None)。
    record_block: 给定 list 时，把【实际 atk 打不动】的怪记进去(供挡路怪报告)，附其节点分类 info。"""
    fid, x, y = nb
    kinfo = zone["floors"][fid]["kind"].get((x, y))
    if kinfo is None:
        return False
    k, info = kinfo
    if k == "wall":
        return False
    mon = all_mon.get(nb)
    if mon is not None:                     # 怪格(含 battle-hook 守门怪)：打不动=硬墙，不因挂钩子放行
        has_cross = hero.items.get("cross", 0) > 0
        has_knife = hero.items.get("knife", 0) > 0
        t = _real_toll(mon, hero.atk, hero.def_, hero.mdef, has_cross, has_knife)
        if t is None:
            if record_block is not None:
                record_block.append((nb, mon, info))
            return False
        return True
    if k == "free":
        return True
    if k == "pay":                          # pay 但无怪缓存 → 钥匙门
        if info == "door":
            if door_mode == "free":
                return True                 # U：门全免费
            if door_mode == "wall":
                return False                # L：门全当墙
            return geom["door_color"].get(nb) in open_colors  # color：按到手钥匙色放行
        return True
    if k == "node":                         # 非怪节点：拾取/楼梯/事件/假墙/特殊门/NPC/领域
        if door_mode == "wall":
            return info in ("stair", "item")  # L：保守下界，只放行 楼梯/拾取
        return True                          # U/color：generous 上界(除墙/打不动怪/锁死门外全放行)
    return False


def _flood(zone, all_mon, geom, start, hero, door_mode, open_colors, record_block=None):
    """从 start 跨层泛洪(楼梯 links 当边)，返回可达 (fid,x,y) 集合。"""
    seen = {start}
    dq = deque([start])
    while dq:
        node = dq.popleft()
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in zone["links"]:
            nbrs.append(zone["links"][node])
        for nb in nbrs:
            if nb in seen:
                continue
            if _passable(zone, all_mon, geom, nb, hero, door_mode, open_colors, record_block):
                seen.add(nb)
                dq.append(nb)
    return seen


def reach_fixpoint(zone, all_mon, geom, start, hero0, door_mode):
    """单调能力+钥匙不动点：泛洪→吸可达道具(剑/宝石→atk/def 涨；钥匙→开新色门)→重洪，直至无新道具。
    color 模式下 open_colors 随到手钥匙色单调扩张(能力&可达只增→停机)。
    返回 (R 可达集, hero 终态, absorbed 已吸道具格, blockers 打不动怪, iters, open_colors 终态)。"""
    hero = copy.deepcopy(hero0)
    absorbed = set()
    iters = 0
    while True:
        iters += 1
        blockers = []
        open_colors = ({c for c in _COLOR_ORDER if hero.keys.get(c, 0) > 0}
                       if door_mode == "color" else set())
        R = _flood(zone, all_mon, geom, start, hero, door_mode, open_colors, record_block=blockers)
        new = []
        for node in R:
            if node in absorbed:
                continue
            fid, x, y = node
            fl = zone["floors"][fid]["floor"]
            iid = fl._tile_to_item.get(fl.entities[y][x])
            if iid is not None:
                new.append((node, fl, iid))
        if not new:
            return R, hero, absorbed, blockers, iters, open_colors
        for (node, fl, iid) in new:
            absorbed.add(node)
            _absorb_one(hero, fl, iid)


# ───────────────── 普查(全图 / 一区静态) ─────────────────

def census_wholemap():
    """全图(所有 MT*.json)各色门 tile 数、钥匙物品数。"""
    doors, keys = Counter(), Counter()
    nfloors = 0
    for p in sorted(FLOORS.glob("MT*.json")):
        fl = load_floor(p)
        nfloors += 1
        for y in range(len(fl.terrain)):
            for x in range(len(fl.terrain[y])):
                c = DOOR_KEY_MAP.get(fl.terrain[y][x])
                if c:
                    doors[c] += 1
                iid = fl._tile_to_item.get(fl.entities[y][x])
                if iid in _KEY_ITEMS:
                    keys[iid] += 1
    return doors, keys, nfloors


def census_from_geom(geom):
    """一区静态(MT1-10 初始 terrain)各色门/钥匙数(= _zone_key_geometry 计数)。"""
    doors, keys = Counter(), Counter()
    for c in geom["door_color"].values():
        doors[c] += 1
    for iid in geom["key_item"].values():
        keys[iid] += 1
    return doors, keys


def _count_in(geom, R):
    """可达集 R 内各色 门 / 钥匙物品 计数。"""
    doors, keys = Counter(), Counter()
    for node, c in geom["door_color"].items():
        if node in R:
            doors[c] += 1
    for node, iid in geom["key_item"].items():
        if node in R:
            keys[iid] += 1
    return doors, keys


# ───────────────── 可达钥匙的损血代价(§5：值不值得拿) ─────────────────

def cost_to_keys(zone, all_mon, geom, start, hero, R_keys_nodes, door_mode, open_colors):
    """终态能力下，从 start 到各【可达钥匙格】的最小累计损血(Dijkstra，门按 door_mode 门禁、怪付实际损血)。
    只在该可达集语义内走(打不动怪自然 inf)。返回 {node: blood}。"""
    import heapq
    has_cross = hero.items.get("cross", 0) > 0
    has_knife = hero.items.get("knife", 0) > 0
    targets = set(R_keys_nodes)

    def enter_cost(nb):
        mon = all_mon.get(nb)
        if mon is None:
            return 0
        t = _real_toll(mon, hero.atk, hero.def_, hero.mdef, has_cross, has_knife)
        return None if t is None else t

    dist = {start: 0}
    pq = [(0, start)]
    out = {}
    while pq:
        d, node = heapq.heappop(pq)
        if d > dist.get(node, float("inf")):
            continue
        if node in targets and node not in out:
            out[node] = d
            if len(out) == len(targets):
                break
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in zone["links"]:
            nbrs.append(zone["links"][node])
        for nb in nbrs:
            if not _passable(zone, all_mon, geom, nb, hero, door_mode, open_colors):
                continue
            c = enter_cost(nb)
            if c is None:
                continue
            nd = d + c
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                heapq.heappush(pq, (nd, nb))
    return out


# ───────────────────────────── 主流程 ─────────────────────────────

def _fmt_row(label, counter):
    cells = []
    for c in _COLOR_ORDER:
        if counter.get(c):
            cells.append(f"{_cname(c)}={counter[c]}")
    return f"  {label:<22}" + ("  ".join(cells) if cells else "(无)")


def main():
    L = []

    def w(s=""):
        L.append(s)

    real, nopen = build_start()
    rh = real.hero
    start = (real.current_floor, rh.x, rh.y)

    zone = build_zone()
    geom = _zone_key_geometry(zone)

    w("=" * 100)
    w("一区(MT1-10) 真实可达钥匙稀缺度 —— 只读测量(引擎原语门禁，不手推)")
    w("=" * 100)
    w(f"真起点(穿 {nopen} token 强制开局噩梦后): {start}  "
      f"HP={rh.hp} ATK={rh.atk} DEF={rh.def_} MDEF={rh.mdef}  "
      f"keys={ {k: v for k, v in dict(rh.keys).items() if v} or '空'}  "
      f"items={ {k: v for k, v in dict(rh.items).items() if v} }")
    sk = zone["floors"][start[0]]["kind"].get((start[1], start[2]))
    w(f"起点格在静态图分类={sk}（应非 wall）")

    # ── §1 三级普查：全图 → 一区静态 → (下面)一区可达 ──
    wm_doors, wm_keys, nfl = census_wholemap()
    z_doors, z_keys = census_from_geom(geom)
    w("-" * 100)
    w(f"【§1 普查逐级收窄】各色 门 / 钥匙物品 数（钥匙地图总数 ≠ 可用数，这是老错误的根）")
    w(f"  扫描层数：全图={nfl} 层，一区=MT1-10")
    w("  ① 门数：")
    w(_fmt_row(f"全图({nfl}层)", wm_doors))
    w(_fmt_row("一区静态(MT1-10)", z_doors))
    w("  ② 钥匙物品数：")
    w(_fmt_row(f"全图({nfl}层)", wm_keys))
    w(_fmt_row("一区静态(MT1-10)", z_keys))
    w("  ⇒ 第一步收窄：全图总数里只有落在 MT1-10 的才与一区相关；但这仍是【静态印在地图上】，")
    w("     还没扣『打一区时拿不到』的——下面不动点泛洪做第二步收窄(真可达)。")

    # ── §2 可达性不动点：U(松上界) / C(真可达上界·按色门禁) / L(下界) ──
    all_mon = build_all_monsters(zone)
    R_U, hero_U, abs_U, blk_U, it_U, _ = reach_fixpoint(zone, all_mon, geom, start, rh, "free")
    R_C, hero_C, abs_C, blk_C, it_C, oc_C = reach_fixpoint(zone, all_mon, geom, start, rh, "color")
    R_L, hero_L, abs_L, blk_L, it_L, _ = reach_fixpoint(zone, all_mon, geom, start, rh, "wall")
    su_doors, su_keys = _count_in(geom, R_U)
    sc_doors, sc_keys = _count_in(geom, R_C)
    sl_doors, sl_keys = _count_in(geom, R_L)
    floors_U = sorted({n[0] for n in R_U}, key=lambda f: int(f[2:]))
    floors_C = sorted({n[0] for n in R_C}, key=lambda f: int(f[2:]))
    floors_L = sorted({n[0] for n in R_L}, key=lambda f: int(f[2:]))
    w("-" * 100)
    w("【§2 可达性不动点(单调能力+钥匙增长：吸剑/宝石→atk/def 涨；吸钥匙→开新色门→可达扩张)】")
    w(f"  U 松上界(门【全免费】·只挡实际打不动怪)——会穿过开不了的门，故高估：")
    w(f"     终态 ATK={hero_U.atk} DEF={hero_U.def_}（吸 {len(abs_U)} 道具，{it_U} 轮）"
      f"，可达 {len(R_U)} 格，触达 {floors_U}")
    w(f"  C 真可达上界(门【按到手钥匙色】放行：0 钥色=钢→永久墙·精确；≥1 钥色→乐观全开)：")
    w(f"     终态 ATK={hero_C.atk} DEF={hero_C.def_}（吸 {len(abs_C)} 道具，{it_C} 轮）"
      f"，可达 {len(R_C)} 格，触达 {floors_C}")
    w(f"     终态已解锁门色 open_colors={ {_cname(c) for c in oc_C} or '空' }（钢始终锁死=0 钢钥）")
    w(f"  L 下界(门【全当墙】·只放行楼梯/拾取)：")
    w(f"     终态 ATK={hero_L.atk} DEF={hero_L.def_}（吸 {len(abs_L)} 道具，{it_L} 轮）"
      f"，可达 {len(R_L)} 格，触达 {floors_L}")
    w("  ⇒ 真可达供给落在 [L, C] 之间；C 比 U 更可信(U 穿了开不了的门、把封死的钥匙误算可达)。")

    # ── §3 供需对账 + 稀缺判定(静态计数即证稀缺，可达性只会更紧) ──
    w("-" * 100)
    w("【§3 供需对账 + 稀缺判定】钥匙=一次性消耗品：每把开且仅开一扇门")
    w("  ⇒ 能开的门 ≤ 能拿到的钥匙 ≤ 静态钥匙数。故【静态门 D > 静态钥 K】即证：至少 D−K 扇永远开不了")
    w("    (哪怕地图所有钥匙都拿得到)→铁定稀缺，无需可达性。可达性(真可达钥 ≤ 静态钥)只会让缺口更大。")
    w(f"  {'色':<7}{'门D':<6}{'静态钥K':<9}{'真可用钥[L,C]':<16}{'松上界U':<9}判定")
    verdicts = {}
    for c in _COLOR_ORDER:
        Dc = z_doors.get(c, 0)
        Kc = z_keys.get(c, 0)
        if not (Dc or Kc):
            continue
        sL, sC, sU = sl_keys.get(c, 0), sc_keys.get(c, 0), su_keys.get(c, 0)
        gap_static = Dc - Kc      # 静态(发钥全拿)缺口——airtight 下界
        gap_real = Dc - sC        # 真可用(C 上界)缺口——含可达性
        if Dc == 0:
            v = "无门(此色钥匙纯富余)"
        elif Kc == 0:
            v = f"★★一区无此色钥(0 把)→{Dc} 扇门全开不了"
        elif gap_static > 0:
            v = f"★铁定稀缺：静态门{Dc}>钥{Kc}→≥{gap_static}扇永久关(真可用更少 C={sC})"
        elif gap_real > 0:
            v = f"★可达稀缺：真可用钥仅{sC}<门{Dc}→≥{gap_real}扇开不了(静态看似够 K={Kc})"
        else:
            v = "够用(真可用钥≥门数)"
        verdicts[c] = v
        w(f"  {_cname(c):<7}{Dc:<6}{Kc:<9}[{sL},{sC}]{'':<10}{sU:<9}{v}")

    # ── §4 拿不到的钥匙：被「打不动怪」或「开不了的门(钢)」封死在一区可达外 ──
    w("-" * 100)
    w("【§4 一区拿不到的钥匙(C 真可达都够不到)——被 打不动怪 / 开不了的门(0 钥色=钢) 封死】")
    blk_uniq = {}
    blk_info = {}
    for (node, mon, info) in blk_C:
        blk_uniq[node] = mon
        blk_info[node] = info
    by_floor = Counter(n[0] for n in blk_uniq)
    w(f"  ① 打不动怪边界(C 终态 ATK={hero_C.atk})：{len(blk_uniq)} 处，按层 {dict(by_floor)}")
    shown = sorted(blk_uniq.items(), key=lambda kv: (-kv[1].def_, kv[0]))
    for (node, mon) in shown[:10]:
        w(f"     {node} mid={getattr(mon,'id','?')} hp={mon.hp} atk={mon.atk} "
          f"def={mon.def_} [{blk_info.get(node,'?')}]（atk {hero_C.atk}≤def → 打不动）")

    # C 真可达都够不到的钥匙——这些就是「打一区拿不到/不该现在拿」(老错误把它们当富余)
    unreach_C = [(node, iid) for node, iid in geom["key_item"].items() if node not in R_C]
    reach_only_U = [n for n, _ in unreach_C if n in R_U]   # U 够到但 C 够不到 = 全被开不了的门封死
    w(f"  ② C 真可达够不到的钥匙物品 {len(unreach_C)} 把"
      f"（其中 {len(reach_only_U)} 把【U 松上界够到但 C 够不到】= 纯被开不了的门(钢)封死）：")
    uk_by = Counter()
    for node, iid in unreach_C:
        uk_by[(node[0], iid)] += 1
    for (fid, iid), n in sorted(uk_by.items()):
        w(f"     {fid} {_cname(iid)}×{n}")
    if not unreach_C:
        w("     （无：C 够到了所有一区钥匙——稀缺只来自门多于钥匙）")
    w("  ▸ 铁例验证：MT2 三把黄钥(3,4)(4,4)(3,5)困在唯一出口=钢门(5,5)的坑里，0 钢钥→一区永远拿不到。")

    # ── §5 真可达钥匙的损血代价(值不值得拿) ──
    w("-" * 100)
    w("【§5 C 真可达钥匙的最小损血代价(值不值得拿；代价畸高=技术可达但一区未必该拿)】")
    reach_key_nodes = [n for n in geom["key_item"] if n in R_C]
    costs = cost_to_keys(zone, all_mon, geom, start, hero_C, reach_key_nodes, "color", oc_C)
    rows = sorted(costs.items(), key=lambda kv: kv[1])
    by_color_cost = Counter()
    for node, blood in rows:
        by_color_cost[geom["key_item"][node]] += 1
    w(f"  C 真可达钥匙 {len(rows)} 把，按色：{ {_cname(k): v for k, v in by_color_cost.items()} }")
    w(f"  代价最低的若干(损血少=一区该优先拿)：")
    for node, blood in rows[:12]:
        iid = geom["key_item"][node]
        w(f"     {node} {_cname(iid):<7} 到手最小损血≈{blood}")
    if rows:
        w(f"  代价最高的若干(损血多=一区未必划算)：")
        for node, blood in rows[-5:]:
            iid = geom["key_item"][node]
            w(f"     {node} {_cname(iid):<7} 到手最小损血≈{blood}")
    else:
        w("     （C 可达集内无钥匙物品）")

    # ── 结论 ──
    w("=" * 100)
    w("【结论：一区钥匙到底稀不稀缺？】")
    hard = [c for c, v in verdicts.items() if v.startswith("★★") or "铁定稀缺" in v]
    reach = [c for c, v in verdicts.items() if v.startswith("★可达")]
    ok = [c for c, v in verdicts.items() if c not in hard and c not in reach]
    if hard:
        w(f"  · 铁定稀缺(静态门>钥/0钥，airtight，必抉择开哪些门)：{ {_cname(c) for c in hard} }")
    if reach:
        w(f"  · 可达性致稀缺(静态看似够、真可用钥不足)：{ {_cname(c) for c in reach} }")
    if ok:
        w(f"  · 够用/富余：{ {_cname(c) for c in ok} }")
    w(f"  · C 真可达够不到的钥匙 {len(unreach_C)} 把（含 {len(reach_only_U)} 把纯被开不了的门封死）"
      f" = 老错误把它们当『富余』的来源。")
    w("  · ∴ 用『地图总钥匙数』判富余是错的；一区钥匙确实稀缺、必须抉择开哪些门 → 钥匙价值评估是真问题。")
    w("=" * 100)

    text = "\n".join(L)
    out = Path(__file__).parent / "zone1_key_scarcity.txt"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[落盘] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
