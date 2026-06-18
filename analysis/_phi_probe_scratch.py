"""【临时探查·非封板】枚举铁盾态(tok454)后 9 层段剩余怪集，验 Φ_total 枚举口径。
目标：复现 §S41 的 ΔΦ(+1ATK @25/24)≈612、ΔΦ(+1DEF)≈204、怪数≈112 → 坐实枚举与 §S41 评估一致。
只读：build_initial_state/step/_load_floor_if_needed/_build_monster/compute_combat，不改产品码。
跑完即弃（或转正进 path-loss 探针）。
"""
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step, _load_floor_if_needed, _build_monster
from sim.combat import compute_combat, PlayerState

TOK_SHIELD = 454
FLOORS = ["MT1", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10"]

s = build_initial_state()
tokens, _ = load_tokens()
for t in tokens[:TOK_SHIELD + 1]:
    s = step(s, t)
h = s.hero
print(f"铁盾态 tok{TOK_SHIELD}: {s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
      f"钥={ {k: v for k, v in h.keys.items() if v} }")

# 确保 9 层加载
for f in FLOORS:
    ok = _load_floor_if_needed(s, f)
    if not ok:
        print(f"  ⚠ {f} 加载失败(文件缺)")

# 枚举每层现存怪(已打的已从 entities 移除 → 天然=剩余怪集)
roster = []                       # [(floor, mid)]
per_floor = defaultdict(Counter)
for f in FLOORS:
    fl = s.floors[f]
    ent = fl.entities
    for y in range(len(ent)):
        for x in range(len(ent[y])):
            mid = fl._tile_to_enemy.get(ent[y][x])
            if mid:
                roster.append((f, mid))
                per_floor[f][mid] += 1

print(f"\n剩余怪集总数 = {len(roster)} 只 (§S41 预期≈112)")
for f in FLOORS:
    if per_floor[f]:
        print(f"  {f:>5}: {dict(per_floor[f])}")

# 看哪些怪带 special(吸血 11 会让 Φ 依赖 HP_in → 须确认有无)
specials = {}
for f, mid in roster:
    m = _build_monster(s, mid)
    if m.special:
        specials[mid] = m.special
print(f"\n带 special 的怪种: {specials}")


def phi(atk, def_, hp=100000):
    """Σ 全怪 compute_combat 损血。打不动(damage=None)单列、不计入 total。"""
    total = 0
    undef = Counter()
    for f, mid in roster:
        m = _build_monster(s, mid)
        r = compute_combat(PlayerState(hp=hp, atk=atk, def_=def_, mdef=0), m)
        if r.damage is None:
            undef[mid] += 1
        else:
            total += r.damage
    return total, undef


print("\n── Φ_total(a,d) @ 大HP(避免中途死) ──")
for (a, d) in [(18, 15), (22, 20), (24, 24), (25, 24), (26, 24), (27, 27), (30, 30), (33, 33)]:
    t, u = phi(a, d)
    print(f"  ATK{a:>2} DEF{d:>2}: Φ={t:>7}  打不动{sum(u.values())}只 {dict(u)}")

# §S41 数值校验
t25, _ = phi(25, 24)
t26, _ = phi(26, 24)
t25d, _ = phi(25, 25)
print(f"\n§S41 校验:")
print(f"  ΔΦ(+1ATK @ATK25→26,DEF24) = {t25 - t26}  (§S41 预期≈612)")
print(f"  ΔΦ(+1DEF @DEF24→25,ATK25) = {t25 - t25d}  (§S41 预期≈204)")
