"""确认"花金币买"盲区范围：搜索撞上 choices 型事件(商人/祭坛/选择NPC)就当拦截跳过
(quotient.py:487-489 无 CHOICE 口径→记录+跳过)。本探针两路举证，仅诊断、零碰核心：
  (A) 数据侧权威全集：从 shops.json 列出 ZONE1(MT1-10) 所有【可购买】choices 拦截格(商人+祭坛)，
      标 floor/pos/price/give —— 这是盲区的完整范围，与具体跑法无关。
  (B) 实跑实证：复跑 V_zone 搜索，dump res.intercept_locs(搜索真撞到并跳过的格(x,y))+floors_seen，
      与 (A) 交叉核对(intercept_locs 只记 (x,y) 无层号，故用 floors_seen 佐证层已到达)。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step
from solver.quotient import search_quotient
from probe_crossfloor import build_start
from seg_identify_zone1 import ZONE1
from vzone import build_zone, v_zone

ROOT = Path(__file__).parent.parent
SHOPS = json.loads((ROOT / "data" / "games51" / "shops.json").read_text(encoding="utf-8"))
ZSET = set(ZONE1)


def section_a():
    print("=" * 84)
    print("(A) 数据侧权威全集：ZONE1(MT1-10) 所有【可购买】choices 拦截格（搜索现在全跳过）")
    print("=" * 84)
    cells = []   # (floor, x, y, kind, desc)
    print("\n── 商人 trader（gold→道具/钥匙，单次买后消失）──")
    for m in SHOPS["merchants"]["items"]:
        fl = m.get("floor")
        if fl in ZSET:
            x, y = map(int, m["pos"].split(","))
            give = ",".join(f"{k}×{v}" for k, v in m["give"].items())
            print(f"   {fl}({x},{y})  price={m['price']:>4}金 → {give}")
            cells.append((fl, x, y, "商人", f"{m['price']}金→{give}"))
    print("\n── 祭坛 altar（gold→atk/def，可重复买、times1 涨价）──")
    for a in SHOPS["altars"]:
        fl = a.get("floor")
        if fl in ZSET:
            x, y = map(int, a["pos"].split(","))
            print(f"   {fl}({x},{y})  +{a['atk_per_purchase']}atk/+{a['def_per_purchase']}def 每次 "
                  f"(花费序列 {SHOPS['_altar_system']['cost_sequence'][:4]}...)")
            cells.append((fl, x, y, "祭坛", f"+{a['atk_per_purchase']}atk/+{a['def_per_purchase']}def"))
    print(f"\n  → ZONE1 可购买盲区共 {len(cells)} 格。这些是【结构性买不了】(无 CHOICE 口径)，"
          f"与跑宽 K 无关。")
    return cells


def section_b(cap, k):
    print("\n" + "=" * 84)
    print(f"(B) 实跑实证：V_zone 搜索 (beam_k={k}, cap={cap}) 的 intercept_locs / floors_seen")
    print("=" * 84)
    start, nopen = build_start()
    zone = build_zone()
    memo = {}

    def beam_score_fn(s):
        hit = memo.get(id(s))
        if hit is not None and hit[0] is s:
            return hit[1]
        v = v_zone(zone, s)[0]
        memo[id(s)] = (s, v)
        return v

    goal_cell = ("MT0", 1, 1)
    t0 = time.perf_counter()
    res = search_quotient(start, goal_cell, step, max_states=cap, cross_floor=True,
                          beam_k=k, beam_score_fn=beam_score_fn)
    dt = time.perf_counter() - t0
    print(f"搜索完成 {dt:.1f}s  hit_cap={res.hit_cap}")
    print(f"floors_seen = {res.floors_seen}")
    print(f"intercept_locs (搜索真撞到并跳过的 (x,y)，无层号) = {res.intercept_locs}")
    return res


def cross(cells, res):
    print("\n" + "=" * 84)
    print("(A)×(B) 交叉核对：每个数据盲区格，搜索是否到达其层 + 是否撞到该 (x,y)")
    print("=" * 84)
    seen = set(res.floors_seen)
    hit_xy = set(tuple(t) for t in res.intercept_locs)
    for fl, x, y, kind, desc in cells:
        floor_ok = "✅到达该层" if fl in seen else "✗未到该层(本次capped)"
        xy_ok = "✅intercept_locs含此(x,y)" if (x, y) in hit_xy else "—(x,y)未在列表"
        print(f"   {kind} {fl}({x},{y}) {desc}")
        print(f"        {floor_ok} ; {xy_ok}")
    print("\n注：intercept_locs 只存 (x,y) 不存层，故 (6,1) 等坐标可能跨层撞名(MT4祭坛(6,1) vs "
          "MT7商人(6,1))；层归属以 floors_seen + 数据(A)为准。结论不依赖实跑——(A) 已证结构性盲区。")


if __name__ == "__main__":
    cells = section_a()
    res = section_b(cap=60000, k=50)
    cross(cells, res)
