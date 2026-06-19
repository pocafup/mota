"""【临时只读验证】实证 fly 落点：在首进 MT9 态直接调 _boundary_ops(enable_fly=True)，
看它到底飞向哪些层——验证 fly 实现是"飞已到达的非特殊层"(对) 还是"只飞 MT0/44/50"(我上轮的错误归因)。"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.seam_astar_smoke import first_enter_mt9, seg_step          # noqa: E402
from solver.quotient import _boundary_ops, _free_cells, _absorb          # noqa: E402

FLY_FULL = json.loads(
    (ROOT / "data" / "games51" / "fly_attrs.json").read_text(encoding="utf-8"))
FLY_FLOORS = FLY_FULL["floors"]   # = solver 实际收到的口径（probe 也这么传）

mt9, idx = first_enter_mt9()
print("起点 =", mt9.current_floor, (mt9.hero.x, mt9.hero.y), "HP", mt9.hero.hp)
print("全塔 floor_ids =", list(mt9.floor_ids))
print("已访问 visited_floors =", sorted(mt9.visited_floors))
print("fly_attrs._default =", FLY_FULL.get("_default"))
print("fly_attrs.floors 显式键(=例外表) =", list(FLY_FLOORS.keys()))
print("  → 其中 canFlyTo=false(不可飞入) =",
      [k for k, v in FLY_FLOORS.items() if v.get("canFlyTo") is False])

# 与主循环同口径：absorb 后算 free，再问 _boundary_ops 生成哪些 fly 边
start, _ = _absorb(mt9, seg_step)
free = _free_cells(start)
ops = _boundary_ops(start, free, cross_floor=True, enable_fly=True, fly_attrs=FLY_FLOORS)
fly_to = sorted({op[1] for op in ops if op[0] == "fly"})

print("\n★enable_fly=True 实际生成的 fly 落点层 =", fly_to)
print("  fly 边总数 =", sum(1 for op in ops if op[0] == "fly"))

# 判读
排除 = {k for k, v in FLY_FLOORS.items() if v.get("canFlyTo") is False}
飞到特殊层 = [f for f in fly_to if f in 排除]
print("\n【判读】")
print("  fly 落点里含 MT0/44/50 这些特殊层吗? →", 飞到特殊层 or "无(正确排除了)")
print("  fly 落点是否⊆已访问层? →",
      "是" if set(fly_to) <= set(mt9.visited_floors) else "否!")
if set(fly_to) & {"MT0", "MT44", "MT50"}:
    print("  ❌ 接反:fly 飞向了不可飞入的特殊层")
elif fly_to and set(fly_to) <= set(mt9.visited_floors):
    print("  ✅ 正确:fly 飞向【已访问的非特殊层】,与玩家权威理解一致")
elif not fly_to:
    print("  ⚠ 这一态没生成任何 fly 边(查 has_stair/主链连通门控)")
