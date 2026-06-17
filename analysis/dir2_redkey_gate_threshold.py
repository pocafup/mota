"""【方向2·便宜诊断①】破红钥门精确阈值（用真实战斗引擎 compute_combat·绝不手算）。

红钥 MT8(10,2) 唯一入口 = specialDoor(10,4)，开门须杀 (9,5)(11,5) 两只 yellowGuard
（hp50/atk48/def22·无 special·MT8.json + monsters.json 坐实）。本脚本回答：
  1. 破门要 ATK 几（超守卫 def22 才打得动）？
  2. survivable（连杀两守卫不死）要 ATK/DEF/HP 几？
  3. beam 攒到的 ATK25/DEF25/HP733 差在哪（能打动但损血太多？还是没到阈值？差几点？）

只读：从 monsters.json 加载守卫真值（数据=唯一事实来源），调 sim.combat.compute_combat
（与游戏引擎 getDamageInfo 同源）。无产品码改动。
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.combat import Monster, PlayerState, compute_combat

# ── 从 monsters.json 加载 yellowGuard 真值（不手敲数值）──
_mdb = json.loads((ROOT / "data/games51/monsters.json").read_text(encoding="utf-8"))
_g = _mdb["yellowGuard"]
GUARD = Monster(id=_g["id"], name=_g["name"], hp=_g["hp"], atk=_g["atk"],
                def_=_g["def"], special=list(_g.get("special", [])))
print(f"守卫 yellowGuard（monsters.json）: hp={GUARD.hp} atk={GUARD.atk} def={GUARD.def_} special={GUARD.special}")
print(f"破门须杀 2 只（MT8 (9,5)+(11,5)）。引擎规则: hero_atk<=def → 打不动; damage>=hp → 拒战(站不住)。\n")


def kill_one(atk, def_, hp_in):
    """杀一个守卫。返回 (ok, damage, turn, hp_out)。
    ok=False 两种: damage is None(打不动 hero_per=0) 或 damage>=hp_in(引擎拒战·站不住)。"""
    r = compute_combat(PlayerState(hp=hp_in, atk=atk, def_=def_), GUARD)
    if r.damage is None:
        return (False, None, 0, hp_in)          # 打不动
    if r.damage >= hp_in:
        return (False, r.damage, r.turn, hp_in)  # 拒战(站不住)
    return (True, r.damage, r.turn, hp_in - r.damage)


def kill_two(atk, def_, hp_in):
    """连杀两守卫(中间不回血=保守下界)。返回 (survivable, d_each, turn_each, hp_final)。"""
    ok1, d1, t1, h1 = kill_one(atk, def_, hp_in)
    if not ok1:
        return (False, d1, t1, h1)
    ok2, d2, t2, h2 = kill_one(atk, def_, h1)
    return (ok2, d2, t2, h2)


print("=" * 78)
print("【1】单守卫损血表（看 ATK 跨过 def22 后 turn/损血怎么掉）")
print("=" * 78)
print(f"{'ATK':>4} | hero_per=ATK-22 | turn=ceil(50/per) | 各DEF单守卫损血 (turn-1)*(48-DEF)")
print(f"{'':>4} | {'':>15} | {'':>17} | DEF20   DEF22   DEF25   DEF27")
for atk in range(22, 33):
    per = max(0, atk - 22)
    if per == 0:
        print(f"{atk:>4} | {per:>15} | {'∞(打不动)':>17} | 打不动")
        continue
    row = []
    for d in (20, 22, 25, 27):
        ok, dmg, turn, _ = kill_one(atk, d, 99999)
        row.append(f"{dmg:>5}")
    _, _, turn, _ = kill_one(atk, 20, 99999)
    print(f"{atk:>4} | {per:>15} | {turn:>17} | {'   '.join(row)}")

print("\n" + "=" * 78)
print("【2】连杀两守卫 survivable 阈值（中间不回血=保守下界）")
print("=" * 78)
print("对每个 (ATK,DEF) 求 survivable 所需最小进场 HP = 2×单守卫损血 + 1：")
print(f"{'ATK':>4} | {'DEF':>4} | 单守卫损血 | 两守卫总损 | 最小进场HP | 备注")
for atk in (23, 24, 25, 26, 27, 28):
    for d in (20, 22, 25, 27):
        ok, dmg, turn, _ = kill_one(atk, d, 99999)
        if not ok:
            print(f"{atk:>4} | {d:>4} | {'打不动':>9} | {'—':>9} | {'—':>9} | ATK≤22打不动")
            continue
        total = dmg * 2
        min_hp = total + 1
        print(f"{atk:>4} | {d:>4} | {dmg:>9} | {total:>9} | {min_hp:>9} | 进场HP≥{min_hp}可破门")

print("\n" + "=" * 78)
print("【3】★beam 攒到的 ATK25/DEF25/HP733 精确差在哪")
print("=" * 78)
for (a, d, h) in [(22, 20, 166), (25, 25, 733), (25, 25, 736), (25, 27, 733),
                  (26, 25, 733), (25, 25, 800), (24, 25, 733)]:
    surv, d2, t2, hf = kill_two(a, d, h)
    ok1, d1, t1, h1 = kill_one(a, d, h)
    tag = "✓ survivable 破门" if surv else "✗"
    if not ok1 and d1 is None:
        detail = "第1守卫就打不动(ATK≤22)"
    elif not ok1:
        detail = f"第1守卫损血{d1}≥HP{h}→拒战站不住"
    elif not surv:
        detail = f"杀1守卫:损{d1}→HP{h1}; 杀2守卫:需损{d2}但HP仅{h1}→{'拒战' if d2>=h1 else '死'}(差{d2-h1+1})"
    else:
        detail = f"杀1守卫损{d1}→HP{h1}; 杀2守卫损{d2}→HP{hf}(余{hf})"
    print(f"  ATK{a}/DEF{d}/HP{h}: {tag}  [{detail}]")

print("\n" + "=" * 78)
print("【4】★找 survivable 的最小属性组合（从 ATK25/DEF25/HP733 出发，差几点？）")
print("=" * 78)
base_a, base_d, base_h = 25, 25, 733
print(f"基线(beam攒到) = ATK{base_a}/DEF{base_d}/HP{base_h}")
print("沿各单维加点，看到哪个值开始 survivable：")
for label, vary in [("加ATK", "a"), ("加DEF", "d"), ("加HP", "h")]:
    found = None
    for inc in range(0, 400):
        a = base_a + (inc if vary == "a" else 0)
        d = base_d + (inc if vary == "d" else 0)
        h = base_h + (inc if vary == "h" else 0)
        if vary in ("a", "d") and inc > 10:
            break
        surv, _, _, _ = kill_two(a, d, h)
        if surv:
            found = (a, d, h, inc)
            break
    if found:
        a, d, h, inc = found
        print(f"  {label}: +{inc} → ATK{a}/DEF{d}/HP{h} 起 survivable")
    else:
        print(f"  {label}: 单维加点(≤上限)无法 survivable")
