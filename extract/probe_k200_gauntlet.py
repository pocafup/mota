"""K=200 跑 V_zone 后，MT10 到达态 HP=720/atk23/def21 能不能扛过埋伏 gauntlet？
真实重放到埋伏触发后的活态，逐怪用引擎 compute_combat 算 toll（不手推）。仅诊断，零碰核心。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from vzone import build_zone, boss_toll, _toll
from vzone_verify_d_ambush import seed_post_trigger, AMBUSH_POS, CAPTAIN
from sim.simulator import _build_monster

# K=200 MT10 到达态属性（per-floor 表：指纹=1，HP=720 ATK=23 DEF=21）
ATK, DEF, MDEF, HP = 23, 21, 0, 720

zone = build_zone()
seed, idx = seed_post_trigger()
fl = seed.floors["MT10"]

print("=" * 80)
print(f"K=200 MT10 到达态: HP={HP} ATK={ATK} DEF={DEF}  vs  埋伏 gauntlet")
print(f"埋伏触发后种子（真实重放 tok 0..{idx}）")
print("=" * 80)

total_amb = 0
unkillable = []
print("8 埋伏怪 toll @ atk23/def21（强制可杀参照）:")
for (x, y) in AMBUSH_POS:
    mid = fl._tile_to_enemy.get(fl.entities[y][x])
    if mid is None:
        print(f"  ({x},{y}): 空格（无怪/已清）")
        continue
    m = _build_monster(seed, mid)
    t = _toll(m, ATK, DEF, MDEF)
    total_amb += t
    can = ATK > m.def_
    if not can:
        unkillable.append((x, y, m.def_))
    print(f"  ({x},{y}) mid={mid:<14} hp={m.hp:>4} atk={m.atk:>3} def={m.def_:>3} "
          f"→ toll={t:>5}  {'' if can else f'⚠atk23≤def{m.def_} 打不动(用强制参照低估)'}")
print(f"  8 怪 toll 合计 = {total_amb}")

# 队长 (6,1)（埋伏后 move 到此）
cx, cy = CAPTAIN
cmid = fl._tile_to_enemy.get(fl.entities[cy][cx])
print("-" * 80)
if cmid is not None:
    cm = _build_monster(seed, cmid)
    ct = _toll(cm, ATK, DEF, MDEF)
    can_cap = ATK > cm.def_
    print(f"队长(6,1) mid={cmid} hp={cm.hp} atk={cm.atk} def={cm.def_} → toll={ct}"
          f"  {'' if can_cap else f'⚠atk23≤def{cm.def_} 真打不动!'}")
else:
    ct = boss_toll(zone, ATK, DEF, MDEF)
    can_cap = True
    print(f"队长(6,1) 不在场，用静态 boss_toll={ct}")

gauntlet = total_amb + ct
print("=" * 80)
print(f"整段 gauntlet (8 怪 + 队长) @ atk23/def21 = {gauntlet}")
print(f"到达 HP={HP}  vs  gauntlet={gauntlet}  →  "
      f"{'✅ 够，余 ' + str(HP - gauntlet) if HP >= gauntlet else '❌ 不够，差 ' + str(gauntlet - HP)}")
if unkillable:
    print(f"⚠ 注意：有埋伏怪 atk23 打不动（{unkillable}）→ 上面 toll 是强制可杀参照、低估真实；"
          f"真实可能根本清不掉这只 = 卡死，与 HP 无关。")
print("=" * 80)

# ── 攻防敏感度扫描：gauntlet 随 (atk,def) 怎么变？固定 K=200 到达 HP=720 看哪些 (atk,def) 够 ──
print()
print("=" * 80)
print(f"gauntlet(8怪+队长) 随 atk/def 变化（固定 K=200 到达 HP={HP}，问哪些属性下够过）:")
print("=" * 80)
# 预建怪列表（8 埋伏 + 队长），避免重复 _build_monster
mons = []
for (x, y) in AMBUSH_POS:
    mid = fl._tile_to_enemy.get(fl.entities[y][x])
    if mid is not None:
        mons.append(_build_monster(seed, mid))
if cmid is not None:
    mons.append(_build_monster(seed, cmid))


def gauntlet_at(a, d, md=0):
    return sum(_toll(m, a, d, md) for m in mons)


print(f"{'':6}" + "".join(f"def{d:>2}    " for d in (21, 23, 25, 30)))
for a in (23, 24, 25, 26, 28, 30, 35, 40):
    cells = []
    for d in (21, 23, 25, 30):
        g = gauntlet_at(a, d)
        mark = "✅" if HP >= g else "  "
        cells.append(f"{g:>5}{mark} ")
    print(f"atk{a:>2} " + "".join(cells))
print(f"（✅ = 该 atk/def 下 gauntlet ≤ 720，即 K=200 已达到的 HP 就够过；空白=仍不够）")
print("=" * 80)
