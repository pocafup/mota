"""【GA decoder · 定向导航器 navigate_to 的独立单元验证】（这一棒的成败判据）。

只测 navigate_to 本身能否【合法地走到目标格】，绝不进任何 GA（无种群/fitness/交叉变异/主循环）。
目标对取自一区【人手已知怎么走】的落点（detect_big_items 数据涌现，不硬编码坐标）：
  · 开局态(噩梦后 MT3 入口) → 拿剑（大件·da>0）
  · 拿剑后态               → 拿盾（大件·dd>0）
  · 开局态 → 1~2 个小宝石（ranked 非大件·ΔRP>0）
每个断言：真走到该格（final 英雄在目标格 + 实体已拾取）、未死、损血与【乐观 toll 下界】相当（不绕大远路/
不无谓挨怪），且【动作串独立重放】从入口逐字段复现（CLAUDE.md 验证铁律：路线丢回真引擎须走通）。
另钉【原子失败】：够不到的目标 → 原样返回入口态（同一对象）+ 空动作 + False。

电池组全 engine-true：start=probe_crossfloor.build_start()（穿强制开局噩梦后首个自由态，MT3/HP400/
atk10/def10，_single_floor_copy=False 多层安全）；step 纯函数 → start 永不被改、多测复用。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest

import json

from probe_crossfloor import build_start
from sim.simulator import step
from solver.beam import build_future_roster
from vzone import build_zone, _toll_dist_from
from big_item_pull import detect_big_items
from ga_navigate import navigate_to
from decode_route import parse_rle_route, decompress
from export_mt10_boss_route import make_initial_state


@pytest.fixture(scope="module")
def zone():
    return build_zone()


@pytest.fixture(scope="module")
def start():
    s, _ = build_start()
    return s


@pytest.fixture(scope="module")
def roster():
    s, _ = build_start()
    return build_future_roster(s)


@pytest.fixture(scope="module")
def targets(zone, roster):
    """大件/小宝石目标【数据涌现】：detect_big_items 找 ΔRP 最大乘性缝；不硬编码"剑盾"/坐标。"""
    s, _ = build_start()
    big_cells, tau, ranked = detect_big_items(zone, roster, s)
    sword = next((c for (drp, c, da, dd) in ranked if c in big_cells and da > 0), None)
    shield = next((c for (drp, c, da, dd) in ranked if c in big_cells and dd > 0), None)
    small = [c for (drp, c, da, dd) in ranked if c not in big_cells and drp > 0]
    return {"big": big_cells, "sword": sword, "shield": shield, "small": small}


@pytest.fixture(scope="module")
def human_dmg_at():
    """人手 α_big=0.7 route 回放 → 首次到达各格时的累计真损血（只累加 HP 下降段，隔离回血）。
    CLAUDE.md：基准/存档路线只作正确性校验 + 基准下界——导航损血须【不差于人手对应段】。
    返回 {cell: 累计损血}。深目标(盾)的乐观 toll 下界忽略夺钥绕行代价，用人手段才是真"相当"参照。"""
    route_file = ROOT / "route" / "alphabig07_route.h5route"
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    dmg = 0
    at = {}
    for a in actions:
        prev = s.hero.hp
        s = step(s, a)
        if s.hero.hp < prev:
            dmg += prev - s.hero.hp
        at.setdefault((s.current_floor, s.hero.x, s.hero.y), dmg)
        if s.dead:
            break
    return at


def _optimistic_toll(nav_start, goal_cell, zone):
    """从 nav_start 英雄格到 goal 的乐观跨层 toll 距离（损血下界，当前属性算）。"""
    h = nav_start.hero
    dist = _toll_dist_from(zone, (nav_start.current_floor, h.x, h.y), h.atk, h.def_, h.mdef)
    return dist.get(goal_cell, float("inf"))


def _assert_reached_ok(nav_start, final, moves, goal_cell, zone, label, human_seg=0):
    """够到目标的完整判据：到格 + 拾取 + 未死 + 真损血(只累加 HP 下降段)在界内 + 动作串独立重放复现。
    注：导航进块即 _absorb 吸光血瓶 → 净 HP 常【上升】，故损血须在重放时单独累加 HP 下降段（隔离回血），
    才是"绕路/无谓挨怪"的真指标。损血上界取 max(乐观下界宽限, 1.3×人手对应段)：浅目标受乐观界约束，
    深目标(跨层夺钥绕行,opt 低估)放宽到人手 α_big=0.7 基准段——导航须【不差于人手】，非追求最优。"""
    gfid, gx, gy = goal_cell
    assert (final.current_floor, final.hero.x, final.hero.y) == (gfid, gx, gy), \
        f"{label}：未停在目标格，落在 {final.current_floor}({final.hero.x},{final.hero.y})"
    assert not final.dead, f"{label}：导航途中死亡"
    assert final.floors[gfid].entities[gy][gx] == 0, f"{label}：到了格但目标物未拾取（实体仍在）"

    opt = _optimistic_toll(nav_start, goal_cell, zone)
    assert opt != float("inf"), f"{label}：乐观图都到不了（目标不在可达区？）"

    # 独立重放（CLAUDE.md 铁律：路线丢回真引擎须走通）：逐 token 真 step，复现同一终态；
    # 同时累加 HP【下降段】= 真损血(战斗/地形)，隔离 _absorb 的回血。
    s = nav_start
    dmg_taken = 0
    for m in moves:
        prev_hp = s.hero.hp
        s = step(s, m)
        if s.hero.hp < prev_hp:
            dmg_taken += prev_hp - s.hero.hp
    assert not s.dead and (s.current_floor, s.hero.x, s.hero.y) == (gfid, gx, gy), \
        f"{label}：动作串重放未走到目标格（路线非法/不可重放）"
    assert s.hero.hp == final.hero.hp, f"{label}：重放 HP {s.hero.hp} ≠ 导航终态 HP {final.hero.hp}"

    budget = max(2 * opt + 60, int(1.3 * human_seg))
    assert dmg_taken <= budget, \
        f"{label}：真损血 {dmg_taken} 超上界 {budget}（乐观下界 {opt}/人手段 {human_seg}；绕大远路/无谓挨怪？）"
    assert final.hero.hp > 50, f"{label}：终态 HP {final.hero.hp} 过低（疑似无谓硬刚）"
    assert len(moves) < 600, f"{label}：步数 {len(moves)} 过多（疑似乱晃/绕大远路）"

    print(f"\n[{label}] goal={goal_cell} 步数={len(moves)} 真损血={dmg_taken} "
          f"乐观下界={opt} 人手段={human_seg} 上界={budget} 净HP {nav_start.hero.hp}->{final.hero.hp}")
    return dmg_taken, opt


# ─────────────── 目标涌现 sanity（不硬编码坐标，但核对落在人手已知的 MT5/MT9）───────────────

def test_targets_emerge(targets):
    """大件涌现非空且剑(da>0)/盾(dd>0)各一；核对落在人手已知的 MT5(剑)/MT9(盾)层（信息性，验我对数据理解）。"""
    assert targets["big"], "未涌现任何大件（detect_big_items 缝检测失败）"
    assert targets["sword"] is not None, "未找到攻击大件（da>0）"
    assert targets["shield"] is not None, "未找到防御大件（dd>0）"
    assert targets["small"], "未涌现任何小宝石目标（ranked 非大件 ΔRP>0 为空）"
    print(f"\n[涌现] 大件={sorted(targets['big'])}  剑={targets['sword']}  盾={targets['shield']}"
          f"  小宝石数={len(targets['small'])}")
    assert targets["sword"][0] == "MT5", f"攻击大件不在 MT5：{targets['sword']}"
    assert targets["shield"][0] == "MT9", f"防御大件不在 MT9：{targets['shield']}"


# ─────────────── 核心验证：定向走到剑 / 盾（顺序）/ 小宝石 ───────────────

def test_navigate_to_sword(start, zone, targets, human_dmg_at):
    """开局态 → 拿剑：真走到 + 拾取 + 未死 + 损血≤人手基准 + 重放复现。"""
    sword = targets["sword"]
    final, moves, reached = navigate_to(start, sword, zone, step)
    assert reached, f"navigate_to 未够到剑 {sword}"
    _assert_reached_ok(start, final, moves, sword, zone, "拿剑", human_dmg_at.get(sword, 0))


def test_navigate_to_shield_after_sword(start, zone, targets, human_dmg_at):
    """拿剑后态 → 拿盾：链式导航，第二段从拿剑终态出发；并整链(剑+盾)从入口重放复现。"""
    sword, shield = targets["sword"], targets["shield"]
    after_sword, moves1, ok1 = navigate_to(start, sword, zone, step)
    assert ok1, f"前置拿剑失败 {sword}"
    final, moves2, ok2 = navigate_to(after_sword, shield, zone, step)
    assert ok2, f"navigate_to 未够到盾 {shield}"
    # 人手对应段 = α_big=0.7 route 的【剑→盾】段损血（盾累计 - 剑累计）
    human_seg = human_dmg_at.get(shield, 0) - human_dmg_at.get(sword, 0)
    _assert_reached_ok(after_sword, final, moves2, shield, zone, "拿盾(剑后)", human_seg)

    # 整链独立重放：入口 → 剑 → 盾 一串动作须复现到盾格
    gfid, gx, gy = shield
    s = start
    for m in list(moves1) + list(moves2):
        s = step(s, m)
    assert not s.dead and (s.current_floor, s.hero.x, s.hero.y) == (gfid, gx, gy), \
        "整链(剑+盾)重放未走到盾格"
    assert s.hero.hp == final.hero.hp, "整链重放 HP 与分段终态不一致"


def test_navigate_to_small_gem(start, zone, targets, human_dmg_at):
    """开局态 → 最高价值小宝石：定向导航同样适用于非大件目标。"""
    gem = targets["small"][0]
    final, moves, reached = navigate_to(start, gem, zone, step)
    assert reached, f"navigate_to 未够到小宝石 {gem}"
    _assert_reached_ok(start, final, moves, gem, zone, "拿小宝石", human_dmg_at.get(gem, 0))


# ─────────────── 原子失败：够不到 → 原样返回入口态 ───────────────

def test_unreachable_goal_atomic_return(start, zone):
    """够不到的目标（区外格 MT0）→ 原子失败：原样返回【入口态本体】+ 空动作 + False（零副作用、不报错）。"""
    off_zone = ("MT0", 1, 1)
    final, moves, reached = navigate_to(start, off_zone, zone, step, max_pops=40)
    assert reached is False, "区外目标竟报够到"
    assert moves == [], "原子失败应返回空动作串"
    assert final is start, "原子失败应原样返回入口态【同一对象】（零副作用）"


# ─────────────── 缓存外壳：命中【逐字段等于首算、也等于无缓存】（缓存不改变导航行为的直接证明）─────────

def test_cache_hit_returns_identical(start, zone, targets):
    """同一(规整起点态,目标)二次导航第二次命中缓存 → final 全字段 + moves + reached 须与首算一致，且与
    cache=None(旁路原算法)一致。原 5 个验证另证未破坏首算/重放；本测专钉 hit 路径。"""
    sword = targets["sword"]
    cache = {}
    f1, m1, r1 = navigate_to(start, sword, zone, step, cache=cache)
    assert r1 and len(cache) == 1, "首算应 miss 并存入恰 1 项"
    f2, m2, r2 = navigate_to(start, sword, zone, step, cache=cache)
    assert len(cache) == 1, "二次应命中、不新增缓存项"
    assert r2 is r1 and m2 == m1, "命中 moves/reached 与首算不一致"
    assert (f2.current_floor, f2.hero.x, f2.hero.y) == (f1.current_floor, f1.hero.x, f1.hero.y)
    assert (f2.hero.hp, f2.hero.atk, f2.hero.def_, f2.hero.mdef) == \
           (f1.hero.hp, f1.hero.atk, f1.hero.def_, f1.hero.mdef)
    assert f2.hero.keys == f1.hero.keys and f2.hero.gold == f1.hero.gold

    # 旁路对照：cache=None 走原算法，须与带缓存首算逐字段一致（证缓存外壳零回归）
    f0, m0, r0 = navigate_to(start, sword, zone, step, cache=None)
    assert r0 is r1 and m0 == m1, "无缓存与带缓存结果不一致（缓存外壳改变了行为）"
    assert f0.hero.hp == f1.hero.hp and \
           (f0.current_floor, f0.hero.x, f0.hero.y) == (f1.current_floor, f1.hero.x, f1.hero.y)

    # 命中返回的 moves 是独立 list 副本：调用方改动不得污染缓存
    m2.append("__POISON__")
    _, m3, _ = navigate_to(start, sword, zone, step, cache=cache)
    assert m3 == m1, "命中应返回独立 list 副本，调用方改动污染了缓存"


def test_cache_atomic_failure_hit(start, zone):
    """原子失败也进缓存：二次命中仍须返回【入口态本体】+ 空动作 + False（保 `final is start` 契约）。"""
    cache = {}
    off = ("MT0", 1, 1)
    a1 = navigate_to(start, off, zone, step, max_pops=40, cache=cache)
    a2 = navigate_to(start, off, zone, step, max_pops=40, cache=cache)
    assert a1[0] is start and a1[1] == [] and a1[2] is False
    assert a2[0] is start and a2[1] == [] and a2[2] is False, "失败命中须返回入口态本体"
