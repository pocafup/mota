"""塔无关：状态相关价值函数 V（Δ形式·对杀怪中性）+ beam 控宽（保护维 Pareto 骨架 + V 填充）。

动机（实测）：缩点把段内搜索从 23min→8s，但段间前沿在 ~1.2 万饱和、每段要拿上万个入口点
逐个重搜大层 → seg9 单段 85min、10 段共 2.3h。缩点【无损】合并价值无关维度（块内站位 / 自由
拾取顺序）；本层 beam【有损】丢弃低估值态——两层正交，beam 直接砍掉「传给下一段的入口点数」
（上万 → K），消掉那个乘数。见 docs/solver-design.md「状态相关价值函数 + beam 控宽」。

V 标量（玩家 2026-06-08 方案 C-Δ形式，修 v1「−Σ活怪集」把杀怪与加攻混为一谈的信用错配）：
  v1 缺陷：Σ 对【当前态仍活的可杀怪】求和——杀一只怪它就离开怪集、Σ 变小 → 杀怪本身被记功，
  且截断偏好「已清楼的小怪集点」、把保守高 HP 未清点当债务砍掉 → 路线退化成无脑清楼、HP 754→92。
  Δ形式修法：Σ 改对一个【固定参照怪集 R】求和，R 不随某点杀怪而缩小 → V 对杀怪中性，只测
  「当前 atk/def 等级把 R 怪的损血压到多低」——atk/def 是永久等级、杀怪是一次性动作，两者解耦。

  V(state) = HP − Σ_{m∈R} cost(state, m)。
    · R（旋钮①Σ锚怪集，取值=段末前沿存活并集）：本批（beam 同次调用）所有前沿点里【任一点】
      仍活且 _killable 的怪 (floor,x,y)→mid 的并集。全批共享同一 R → V 成为 (atk/def,hp) 的纯
      函数：同 atk 点对 R 的 Σ 相同（按 HP 排序，保守高 HP 点不再被误截）；高 atk 点对 R 每只怪
      损血更小 → Σ 更小 → V 更高（攒攻被奖励）。某点杀掉 R 里的怪不会把它移出 R（按 mid 重建怪
      照算损血）→ 对杀怪中性。
    · cost(state, m)：可杀（引擎 compute_combat 损血 < 当前 HP）→ 记该损血；打不动（atk≤怪防）
      或会被打死（损血≥HP）→ 记 BIG。BIG = 全批 (点×R) 所有可杀对里的最大单怪损血。打不动记
      BIG（≥任何可杀损血）→ 跨过防御阈值（打不动→可杀）时 cost 从 BIG 降到实际损血，必降 → V
      跳升（玩家要的「差 1 攻跨减伤阈值 → 等效血量暴涨」由 compute_combat 真损血自然涌现）。
      BIG 是全批常量、不耦合各点 HP、不内联任何硬编码阈值（数据驱动，引擎算）。
  diff 基线 ATK（旋钮②）：仅影响展示数值、不影响排序——见 export_path 的双值显示。Δ 等价式
  V = HP + Σ_R[dmg(基线)−dmg(当前)]，其中 Σ_R dmg(基线) 在同批内是可加常量，对排序无影响。
  钥匙 / 消耗道具 / 血瓶不进 V 标量：钥匙 / 道具走【保护维】、血瓶残留走【身份维】，见下。

beam 截断（玩家拍板：钥匙 / 消耗道具走独立保护维做硬保护；钥匙够用后不再奖励多拿）：
  · 保护维 = 消耗道具各类(item:*) + 钥匙各类(key:*)，但【钥匙按当前层剩余门数封顶】：
    cap = 当前层 terrain 上该色门的剩余数；持有超过 cap 的钥匙不计入保护维。修 v1「钥匙越多
    保护维组合越多 → 低 HP 钥匙囤积点被白白保住」的鼓励囤钥匙缺陷（玩家：钥匙够用后边际价值
    骤降、亏血拿多余钥匙纯亏）。封顶口径 = 当前层门（与 V 怪集「当前层」同口径）；跨层未来门
    需要的钥匙不在此保护，留待下一段以那层为当前层时再评估（merge_frontier 仍按 value_vector
    保 key:* 多样性兜底）。
  · 硬保护 = 保护维 Pareto 骨架必留：「保护维严格更少的点不得挤掉更多的」（防「省钥匙换血」
    假优）。骨架 = 保护维非支配组合，每个留 V 最高代表；剩余配额按 V 标量 top 填到 K。
  · 血瓶残留落在【身份维】（merge_frontier residual_fingerprint 含 floor.entities），由指纹分组
    天然保护，不进 V 标量；beam 跨指纹截断会丢部分血瓶残留态——有损来源，调用方落盘审计 +
    三保险（引擎裁判 / route 基准 / 玩家终审）兜底。

塔无关：无任何楼层 / 怪 / 道具 / 阈值硬编码；可杀 / 损血 / 门→钥匙全由注入 state 的通用字段 +
sim 判定函数读出（compute_combat / DOOR_KEY_MAP，与引擎同源）。
"""
import json
from collections import namedtuple

from sim.simulator import _build_monster, DOOR_KEY_MAP
from sim.combat import PlayerState, compute_combat
from solver.quotient import _killable
from solver.search import _value_map

value_vector = _value_map  # 对外别名：与段内 Pareto / 段间 merge 同口径


# ─── V 标量（Δ形式）：固定参照怪集 R + 不可杀代价 BIG，对杀怪中性 ─────────────────────

def _combat_damage(state, mid):
    """引擎算：state 当前属性打 mid 怪的损血；None=打不动（atk≤怪防，compute_combat 判无解）。
    对杀怪中性的关键：按 roster 记录的 mid【重建】怪，不要求它在当前态仍存活——已杀的怪也照算
    损血，使「杀没杀」不改变 V。"""
    h = state.hero
    ps = PlayerState(hp=h.hp, atk=h.atk, def_=h.def_, mdef=h.mdef)
    mon = _build_monster(state, mid)
    res = compute_combat(ps, mon,
                         has_cross=h.items.get("cross", 0) > 0,
                         has_knife=h.items.get("knife", 0) > 0)
    if res is None or res.damage is None:
        return None
    return res.damage


def _build_roster(points):
    """固定参照怪集 R（旋钮①Σ锚怪集 取值=段末前沿存活并集）：本批所有前沿点里【任一点】仍活
    且 _killable 的怪 (floor,x,y)→mid 并集。塔无关：怪 id 由 floor._tile_to_enemy 读出。"""
    roster = {}
    for p in points:
        s = p.state
        ents = s.floor.entities
        for y in range(len(ents)):
            row = ents[y]
            for x in range(len(row)):
                mid = s.floor._tile_to_enemy.get(row[x])
                if mid is not None and _killable(s, x, y):
                    roster[(s.current_floor, x, y)] = mid
    return roster


def score_points(points, future=None, extra=None):
    """【单遍打分】构建 R 后，对每点只算一次「对 R 各怪损血」，分类缓存 (Σ可杀损血, 打不动计数)；
    全批扫完得 BIG=最大可杀单怪损血，再算每点 V=hp−Σ可杀−打不动×BIG−远区势能(+引导项)。返回 (roster,
    big, scores)，scores: id(state)→V。每 (点,怪) 对仅一次引擎战斗——消掉旧版 region_reference(算BIG)
    + equiv_hp_over_roster(重算V) 的双遍 compute_combat（段间前沿上万点 × R 时是主成本）。
    与双遍版数学等价：Σcost = Σ可杀损血 + 打不动×BIG，BIG 取同一可杀集最大值。
    future（FutureCfg 或 None）：区势能 cfg。None/lam=0 → _future_potential 返回 0（int）→ 与
    原版【字节一致】（off 路径不引入 float）。on 时 V 再减 λ·Σ_区·存活 toll，见 _future_potential。
    extra（可调用 state→数值 或 None）：驱动层注入的【可加引导项】(如 β_big·pull_大件)，只进此排序键、
    绝不进 value_vector/D。None（默认）→ 不加、与原版【字节一致】（off 路径不引入任何项）；给函数 →
    每点 V 再【加】extra(state)。塔无关：solver 不认 extra 内部逻辑（闭包持塔特有 zone 在驱动层 extract/）。"""
    roster = _build_roster(points)
    mids = list(roster.values())
    big = 0
    rows = []
    for p in points:
        hp = p.state.hero.hp
        sk = uk = 0
        for mid in mids:
            d = _combat_damage(p.state, mid)
            if d is not None and d < hp:
                sk += d
                if d > big:
                    big = d
            else:
                uk += 1
        rows.append((id(p.state), p.state, hp, sk, uk))
    if extra is None:
        scores = {sid: hp - sk - uk * big - _future_potential(st, future)
                  for (sid, st, hp, sk, uk) in rows}
    else:
        scores = {sid: hp - sk - uk * big - _future_potential(st, future) + extra(st)
                  for (sid, st, hp, sk, uk) in rows}
    return roster, big, scores


def region_reference(points):
    """构建 (roster, big) 供【批外】态一次性打分（如引擎重放末态）。批内点打分用 score_points
    （单遍、缓存，免双遍）。R/BIG 口径见 _build_roster / score_points。"""
    roster = _build_roster(points)
    big = 0
    for p in points:
        hp = p.state.hero.hp
        for mid in roster.values():
            d = _combat_damage(p.state, mid)
            if d is not None and d < hp and d > big:
                big = d
    return roster, big


def equiv_hp_over_roster(state, roster, big, future=None, extra=None):
    """V 标量 = HP − Σ_{m∈R} cost(m) − 远区势能(+引导项)。cost = 可杀(损血<HP)→损血；打不动/会被打死→BIG。
    越大越优；R 固定 → 对杀怪中性；跨防御阈值时 cost 由 BIG 降到实际损血 → V 跳升。
    这是 beam 排序的【唯一】打分键（钥匙 / 道具 / 血瓶不进，走保护维 / 身份维）。
    future=None → 区势能项=0（int）→ 与原版字节一致；on 时再减 λ·Σ_区·存活 toll（见 _future_potential）。
    extra=None → 不加引导项、与原版字节一致；给函数 → 再加 extra(state)（口径同 score_points，只进排序键）。"""
    hp = state.hero.hp
    total = 0
    for mid in roster.values():
        d = _combat_damage(state, mid)
        total += d if (d is not None and d < hp) else big
    base = hp - total - _future_potential(state, future)
    return base if extra is None else base + extra(state)


# ─── 区势能（永久属性对【当前区·剩余存活怪】的总减伤；玩家 2026-06-08 时序性裁定）──────────
#
# 动机①（修 R 近视，2026-06-08 早）：现行 R近 只含【当前批可达怪】，上层那个盾对远期整区怪的减伤
# 在搜索踩上去之前【零 V 信号】→ 爬升被读成纯失血、前沿在中层饿死。魔塔核心：打完一区上去拿永久
# 增益(盾/剑)回来=对整区降维打击，故"拿盾值不值"要用【对接下来整区的总减伤】衡量、不用当前损血。
# 动机②（时序性，2026-06-08 晚，玩家钉死估值最本质缺陷）：减伤只对【拿到装备之后才打的怪】生效，
# 对【已打掉的怪】零价值。例：一区十怪每只盾减 10 血——一上来拿盾省 10×10=100；先打 5 只再拿只剩
# 5 只享受=10×5=50。【早拿盾价值是晚拿的两倍】。病根：怪集若按【静态地图】(已杀仍计)算，盾价值
# 不随回收缩水 → 估不出"早拿值钱"。修法：怪集改按【当前存活残留】算。
#
#   V = HP − Σ_{m∈R近}cost_exact − λ·Σ_{m∈区·非当前层·存活} toll(atk,def,m)
#   · 视野=【当前区到 boss】：每区须打 boss 才进下一区，故区跨度 = (上一区 boss 之上 .. 最近的 boss
#     层含)。boss 层由门禁结构塔无关读出（_is_region_boundary：上行楼梯格 changeFloor :next 且
#     events[loc] 初始 enable==false=打 boss 才开；源码事实 floor_graph.md §4 MT10）。不写死层号。
#   · 怪集=【存活残留】：已访问层读 state.floors[fid].entities(杀怪置 0→自动少)、未访问层回落静态
#     地图(全活)。→ 拿盾/宝石的 V 增益 = 减伤 × 这一区还剩多少怪能享受；回收(杀怪)使剩余缩水→新宝石
#     边际价值递减(时序性自然涌现，非硬塞"早拿盾"权重，守铁律)。含【当前层下方】未清回收层(R近 只覆盖
#     当前层、漏下方回收)——这正是"先上去拿盾、回来收属性"那段回收的 V 来源。
#   · toll = 引擎 compute_combat 在【强制可杀参照 atk=max(atk,怪防+1)】下算的损血(复用引擎真实伤害，
#     铁律不手写公式)；对【所有】区内怪有定义(含当前打不动的高防怪/boss)，盾的 DEF 增益对整区减伤自然
#     涌现为巨大势能、足以让搜索"宁可早期属性平平也冲去拿盾"——巨大值是塔数据真算、非硬塞权重。
#   · λ（折扣旋钮）：<1 让近区精确主导本地排序、区势能只提供"拿盾/回收"梯度。off(future=None/λ=0)→
#     项=0(int)→零回归。一次只动一个变量。
# 塔无关：怪 id 由共享 _tile_to_enemy 读、stats 由 _build_monster 算、楼序由 state.floor_ids、区界由
# changeFloor/events 门禁结构读出；无任何楼层/怪/道具/阈值/区号硬编码。
#
# ⚠ 已知近似（v1，明记不静默）：R近 在跨层批里是【本批所有点 current_floor 的并集】(Δ形式固定参照)，
#   可能与区势能在某些层重叠双计；两项同单调于属性(都随 atk/def 升而降)，λ<1 下只温和放大属性梯度、
#   不翻号。若实测显示重叠扭曲再收紧(如区势能排除本批出现过的 current_floor)。
#
# ⚠ 已知近似（v1）：存活残留按【静态怪位】查 state.floors[fid].entities——对原地不动的怪精确(杀即置0
#   自动剔)；对 setBlock/generateMove 动态移位的怪(如 MT10 埋伏)在其已访问层可能少计，一区爬升段
#   (MT1-9 静止怪)不受影响、MT10 埋伏只在踏入该层后才相关(本轮验证 MT9 铁盾够不到)。

FutureCfg = namedtuple("FutureCfg", ["roster", "lam"])   # roster=build_future_roster 产物；lam=折扣

_TOLL_HP = 10 ** 9   # 参照英雄 HP：恒 > 任何 toll，使 compute_combat 不把 toll 当致死、damage 有定义


def _is_region_boundary(floor_data):
    """塔无关【区边界(boss 层)】判定：该层有【上行楼梯格】(changeFloor 某格 floorId==':next') 且其
    events[loc] 是初始禁用门禁(dict 且 enable is False) → 上行出口被 boss 门禁封 → 它是区边界。
    源码事实 floor_graph.md §4：MT10 changeFloor['6,11']→:next、events['6,11'].enable=false，
    打骷髅队长 afterBattle 才置 flag 开门。纯从 changeFloor/events 结构读、不写死层号。
    注：本塔 MT40/MT24 区界用【事件传送】(events 脚本 if flag→changeFloor)而非 enable=false 楼梯格，
    本判定不覆盖(留待飞行边/后续区接入按需扩)；一区 boss MT10 用本模式，足够验证 MT9 铁盾。"""
    change_floor = floor_data.get("changeFloor", {})
    events = floor_data.get("events", {})
    for loc, cf in change_floor.items():
        if isinstance(cf, dict) and cf.get("floorId") == ":next":
            ev = events.get(loc)
            if isinstance(ev, dict) and ev.get("enable") is False:
                return True
    return False


def build_future_roster(state):
    """全塔【区势能】基础设施：① 读 _floors_dir 每层 floor JSON 静态 map → 怪位 {idx:[(x,y,mid)]}
    (mon_cells，未访问层 alive 兜底 + 已访问层按位查残留)；② 检测【区边界 boss 层 idx】
    (_is_region_boundary，塔无关门禁结构)。一次构建、带 per-monster toll 记忆化 dict。
    塔无关：只读注入 state 的 _floors_dir/floor_ids，区界由结构读出，不写死塔特有 id/层号/数量。"""
    floors_dir = state._floors_dir
    floor_ids = state.floor_ids
    tile_to_enemy = state.floor._tile_to_enemy   # 共享全塔表(tiles.json enemys)，任一已载层皆同
    mon_cells = {}     # {idx: [(x,y,mid),...]} 静态怪位（含坐标，供已访问层按位查存活）
    by_floor = {}      # {idx: [mid,...]} 仅 mid（标定展示/兜底用）
    boss_idxs = []     # 区边界层 idx：上行出口被初始门禁的层
    for idx, fid in enumerate(floor_ids):
        path = floors_dir / f"{fid}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        cells = []
        for y, row in enumerate(data.get("map", [])):
            for x, t in enumerate(row):
                mid = tile_to_enemy.get(t)
                if mid is not None:
                    cells.append((x, y, mid))
        if cells:
            mon_cells[idx] = cells
            by_floor[idx] = [c[2] for c in cells]
        if _is_region_boundary(data):
            boss_idxs.append(idx)
    return {"mon_cells": mon_cells,
            "by_floor": by_floor,
            "idx_of": {fid: i for i, fid in enumerate(floor_ids)},
            "floor_ids": list(floor_ids),
            "boss_idxs": sorted(boss_idxs),
            "min_idx": 0,
            "max_idx": len(floor_ids) - 1,
            "_toll_memo": {}}


def _future_toll(state, mid):
    """单只上层怪的损血 toll：引擎 compute_combat 在【强制可杀参照 atk】下算。
    ref_atk = max(当前 atk, 怪防+1) → hero_per_damage>0(除纯无敌，本塔无)→ toll 对所有上层怪有定义
    (含当前 atk 打不动的高防怪：用怪防+1 的最小可杀 atk 估其 grind 损血，自然给"该上去攒装"强信号)。
    复用引擎真实伤害函数(铁律：solver 不手写战斗公式)；hp=_TOLL_HP 恒不致死。打不动(None)→0。"""
    h = state.hero
    mon = _build_monster(state, mid)
    ref_atk = h.atk if h.atk > mon.def_ else mon.def_ + 1
    ps = PlayerState(hp=_TOLL_HP, atk=ref_atk, def_=h.def_, mdef=h.mdef)
    res = compute_combat(ps, mon,
                         has_cross=h.items.get("cross", 0) > 0,
                         has_knife=h.items.get("knife", 0) > 0)
    if res is None or res.damage is None:
        return 0
    return res.damage


def _region_bounds(roster, cur_idx):
    """当前层所在【区】的 idx 闭区间 [lo,hi]（塔无关，由 boss_idxs 切）：
      hi = 最近的【≥当前】boss 层 idx（含；无则塔顶 max_idx）——每区须打它(boss)才出区；
      lo = 最近的【<当前】boss 层 idx +1（上一区 boss 之上；无则塔底 min_idx）。
    即「当前区到 boss」的层跨度。"""
    boss = roster["boss_idxs"]
    hi = min((b for b in boss if b >= cur_idx), default=roster["max_idx"])
    below = [b for b in boss if b < cur_idx]
    lo = (below[-1] + 1) if below else roster["min_idx"]
    return lo, hi


def _alive_mids_on(state, roster, idx):
    """区内第 idx 层【当前存活】怪 mid 序列：已访问层(在 state.floors)按静态怪位查残留 entities——
    杀怪后该格置 0 → _tile_to_enemy.get(0)=None 自动剔除；未访问层回落静态全活。这就是「剩余可享受
    减伤的怪」：杀一只少一只、回收一区就缩水。"""
    cells = roster["mon_cells"].get(idx, ())
    if not cells:
        return ()
    fl = state.floors.get(roster["floor_ids"][idx])
    if fl is None:                       # 未访问层：静态全活
        return [c[2] for c in cells]
    tte = fl._tile_to_enemy
    ents = fl.entities
    out = []
    for (x, y, _mid0) in cells:          # 只查静态怪位(廉价)，读当前格 tile 判存活
        mid = tte.get(ents[y][x])
        if mid is not None:
            out.append(mid)
    return out


def _future_potential(state, future):
    """区势能项 = λ·Σ_{当前区(到boss)·非当前层·当前存活的怪} toll(atk,def,mdef,怪)。
    off(future=None/lam=0)→返回 0(int) 与原版字节一致；on→V 再减它。
    时序性(玩家 2026-06-08)：怪集按【存活残留】算→拿盾/宝石的 V 增益 = 减伤 × 这一区还剩多少怪能享受；
    回收(杀怪)使剩余缩水→新宝石边际价值递减(早拿盾值钱)。视野=当前区到 boss(每区须打 boss 才进下一区)、
    含【当前层下方】未清回收层(补 R近 只覆盖当前层之漏)。详见上方区势能段。
    记忆化：per-monster toll 按 (atk,def,mdef,cross,knife, mid) 缓存(单怪 toll 与他怪存亡无关)→整搜索
    摊销 compute_combat；每点 sum 按存活集现加(dict 查+加，廉价；不再 memo 整 total 因 total 随存活变)。"""
    if future is None or future.lam == 0:
        return 0
    roster = future.roster
    cur_idx = roster["idx_of"].get(state.current_floor)
    if cur_idx is None:
        return 0
    lo, hi = _region_bounds(roster, cur_idx)
    h = state.hero
    attrs = (h.atk, h.def_, h.mdef,
             h.items.get("cross", 0) > 0, h.items.get("knife", 0) > 0)
    memo = roster["_toll_memo"]
    total = 0
    for idx in range(lo, hi + 1):
        if idx == cur_idx:
            continue
        for mid in _alive_mids_on(state, roster, idx):
            key = (attrs, mid)
            t = memo.get(key)
            if t is None:
                t = _future_toll(state, mid)
                memo[key] = t
            total += t
    return future.lam * total


# ─── beam 截断：保护维 Pareto 骨架（钥匙按当前层门数封顶）+ V 填充 ─────────────────────

def _floor_key_need(state):
    """当前层 terrain 上各色门的剩余数 → {"key:<color>Key": count}（钥匙保护维封顶值）。
    塔无关：门→钥匙映射用 DOOR_KEY_MAP（与引擎开门同源），不写死任何楼层 / 数量。"""
    need = {}
    for row in state.floor.terrain:
        for t in row:
            kn = DOOR_KEY_MAP.get(t)
            if kn:
                kk = "key:" + kn
                need[kk] = need.get(kk, 0) + 1
    return need


def _protect_dims(state, value_vec_fn):
    """从价值向量取【保护维】子向量：消耗道具各类(item:*) 全保；钥匙各类(key:*) 按当前层剩余
    门数封顶（持有超过 cap 的部分不计入 → 不再奖励囤多余钥匙）。塔无关——维名由 value_vector
    动态产出、cap 由 DOOR_KEY_MAP 读 terrain 算，不写死任何 id / 数量。"""
    vec = value_vec_fn(state)
    need = _floor_key_need(state)
    out = {}
    for k, v in vec.items():
        if k.startswith("item:"):
            out[k] = v
        elif k.startswith("key:"):
            cv = min(v, need.get(k, 0))
            if cv > 0:
                out[k] = cv
    return out


def _strictly_dominates(a, b):
    """a 在所有保护维 >= b（缺失维=0）且至少一维严格 >：a 严格支配 b。"""
    keys = set(a) | set(b)
    ge = all(a.get(k, 0) >= b.get(k, 0) for k in keys)
    if not ge:
        return False
    return any(a.get(k, 0) > b.get(k, 0) for k in keys)


def _protection_skeleton(points, score_fn, value_vec_fn):
    """一个点集的【保护骨架】：按保护维向量(item:* 全保 + key:* 按门数封顶)分组 → 求 distinct
    保护向量的 Pareto 非支配集 → 每个非支配组合留 V 最高代表。返回骨架点 list（顺序=保护向量
    首见序）。被 beam_select 对【每个分坑分区】各调一次（分坑维度见 beam_select 的 diversity_key_fn）。"""
    groups = {}
    pvecs = {}
    for p in points:
        pv = _protect_dims(p.state, value_vec_fn)
        key = frozenset(pv.items())
        groups.setdefault(key, []).append(p)
        pvecs[key] = pv
    keys = list(groups)
    nondom = [ki for ki in keys
              if not any(_strictly_dominates(pvecs[kj], pvecs[ki]) for kj in keys if kj != ki)]
    return [max(groups[ki], key=lambda p: score_fn(p.state)) for ki in nondom]


def _partition(points, diversity_key_fn):
    """按分坑维度把点集切成若干分区。diversity_key_fn=None → 单分区(全体)→ beam_select 退化为原版
    (字节一致)；给函数(如 lambda st: st.current_floor) → 按 key 分区，各区在 beam 里独立保骨架。"""
    if diversity_key_fn is None:
        return [points]
    pmap = {}
    for p in points:
        pmap.setdefault(diversity_key_fn(p.state), []).append(p)
    return list(pmap.values())


def beam_select(points, k, score_fn=None, value_vec_fn=value_vector, diversity_key_fn=None):
    """把 points（list[FrontierPoint]）按 beam 控宽截到 k 个，返回 (kept, cut)。

    口径（玩家 2026-06-07 框架 + 2026-06-08 Δ形式 V / 钥匙封顶 + 分坑保护维）：
      0. score_fn 未给 → 用 score_points 单遍现算本批 V（带缓存，免双遍 compute_combat）；
      1. 按 diversity_key_fn 把点集【分坑】（None=单坑=原版；"楼层"=按 current_floor 分坑）；
      2. 每坑各求【保护骨架】(_protection_skeleton：保护维 Pareto 非支配、V 最高代表)；合并去重；
      3. 剩余配额 (k − |合并骨架|) 从非骨架点里按【全局 V】降序填充。
    若合并骨架已 ≥ k，保护被迫让位：骨架内按 V 取 top-k，调用方应记录警告（保护未全保）。

    分坑动机（玩家 2026-06-08 裁定，修 beam 多样性饥饿）：原版单坑下，K 槽位被【低层就近刷怪
    攒属性】的便宜货按 V 占满，【掉血往上爬拿盾】的 climber 中途属性低、V 低被挤出 top-K 剪掉 →
    前沿在中层饿死(λ 扫描实证：加远区势能反而更早死)。按推进度分坑、每坑强制保留其骨架 → 高层
    climber 不被低层 grinder 一锅端。塔无关：diversity_key_fn 从 state 读(楼层=current_floor)，
    不写死任何塔特有维度。玩家洞察：楼层只是起步，更本质分坑维=【已合并块组合/推进度】，floor 版
    不够再升级(见 search_quotient beam_diversity)。"""
    if k is None or len(points) <= k:
        return list(points), []

    if score_fn is None:
        roster, big, scores = score_points(points)
        score_fn = lambda st: scores[id(st)] if id(st) in scores \
            else equiv_hp_over_roster(st, roster, big)

    # 1+2. 每个分坑各求保护骨架，合并去重（顺序=分区序内骨架序，保证可复现）
    skeleton = []
    skel_ids = set()
    for part in _partition(points, diversity_key_fn):
        for p in _protection_skeleton(part, score_fn, value_vec_fn):
            if id(p) not in skel_ids:
                skeleton.append(p)
                skel_ids.add(id(p))

    if len(skeleton) >= k:
        skeleton.sort(key=lambda p: score_fn(p.state), reverse=True)
        kept = skeleton[:k]
        kept_ids = {id(p) for p in kept}
        cut = [p for p in points if id(p) not in kept_ids]
        return kept, cut

    # 3. 剩余按全局 V 填充
    rest = [p for p in points if id(p) not in skel_ids]
    rest.sort(key=lambda p: score_fn(p.state), reverse=True)
    fill = rest[:k - len(skeleton)]
    kept = skeleton + fill
    kept_ids = {id(p) for p in kept}
    cut = [p for p in points if id(p) not in kept_ids]
    return kept, cut


def beam_protection_overflow(points, k, value_vec_fn=value_vector, diversity_key_fn=None):
    """诊断助手：判定 beam_select 是否会触发「保护骨架 ≥ k」让位（调用方据此记录审计警告）。
    返回 (overflow: bool, skeleton_size: int)。分坑时骨架=各坑骨架并集（按 id 去重），与 beam_select
    口径一致；diversity_key_fn=None → 单坑（与原版字节一致）。"""
    if k is None or len(points) <= k:
        return False, 0
    # 用恒 0 打分：骨架【数量】只由保护维 Pareto 非支配集决定，与 V 无关（max 代表取谁不影响计数）
    zero = lambda st: 0
    skel_ids = set()
    for part in _partition(points, diversity_key_fn):
        for p in _protection_skeleton(part, zero, value_vec_fn):
            skel_ids.add(id(p))
    return len(skel_ids) >= k, len(skel_ids)
