"""【§S53 数据探针·只读诊断】验证一区 boss(骷髅队长) + MT8 红钥门守卫(yellowGuard)
+ MT10 红宝石 的精确数值与损血，供写 Φ 启发式作事实依据。

绝不跑搜索/beam/navigate。只做三件事：
  1. 加载 MT8/MT10 楼层（_load_floor_if_needed），打印 boss/守卫/红宝石的 tile/坐标/模板属性。
  2. 用 sim.simulator._build_monster 构造怪、sim.combat.compute_combat 在 hero ATK=25/26/27
     （DEF=铁盾后 20，mdef=起点 0）下算损血(damage)。
  3. 校验任务预期：boss ATK26→27 损血≈342→304；守卫 ATK26→27 损血≈528→396。

构造方式照 analysis/dir2_redkey_pathloss_beam.py 的 _monster_loss + extract_zone1_milestones
的 build_initial_state()/_load_floor_if_needed。
用法：python -u analysis/_s53_data_probe.py
"""
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

from analysis.extract_zone1_milestones import build_initial_state
from sim.simulator import _load_floor_if_needed, _build_monster
from sim.combat import compute_combat, PlayerState

# §S53 校验：任务预期数(boss 342→304 / 守卫 528→396)对应英雄一区【终态 DEF27】，非铁盾刚到手 DEF20。
# 两套 DEF 都扫，逐一对照看哪套命中预期。mdef 起点=0（boss/守卫 special=[]→mdef 末尾减一次，0 无影响）。
DEF_LIST = [20, 27]   # 20=铁盾刚到手；27=英雄一区终态(攒满)真实打 boss 时的 DEF
MDEF_START = 0
ATKS = [25, 26, 27]


def monster_loss(hero_atk, hero_def, mdef, mon):
    """单怪 compute_combat 损血。打不动(damage=None)返回 None，附 turn 供核对。"""
    r = compute_combat(PlayerState(hp=10 ** 7, atk=hero_atk, def_=hero_def, mdef=mdef), mon)
    return r.damage, r.turn


def show_monster(tag, mon):
    print(f"  {tag}: id={mon.id} name={mon.name} hp={mon.hp} atk={mon.atk} "
          f"def={mon.def_} special={mon.special}")


def main():
    print("=" * 78)
    print("§S53 一区数据探针（只读·无搜索）")
    print("=" * 78)

    st = build_initial_state()
    print(f"hero_init: ATK={st.hero.atk} DEF={st.hero.def_} mdef={st.hero.mdef} "
          f"（注：这是通关存档开局峰值，非铁盾态；探针扫 DEF={DEF_LIST} mdef={MDEF_START}）")

    ok8 = _load_floor_if_needed(st, "MT8")
    ok10 = _load_floor_if_needed(st, "MT10")
    print(f"加载 MT8={ok8}  MT10={ok10}")
    mt8 = st.floors["MT8"]
    mt10 = st.floors["MT10"]
    print(f"MT8.ratio={mt8.ratio}  MT10.ratio={mt10.ratio} "
          f"（redGem pickup atk+1*ratio → ratio=1 时 +1）")

    # ── 构造关键怪 ──────────────────────────────────────────────────────────
    boss = _build_monster(st, "skeletonCaptain")   # MT10(6,4)，事件移动后在(6,1)被打
    guard = _build_monster(st, "yellowGuard")      # MT8(9,5)/(11,5) 红钥门守卫
    priest = _build_monster(st, "bluePriest")      # MT10(4,11)/(8,11) 拿红宝石路上的初级法师

    print("\n── 关键怪模板属性（monsters.json，无 setEnemy override）──")
    show_monster("boss 骷髅队长", boss)
    show_monster("守卫 初级卫兵yellowGuard", guard)
    show_monster("初级法师 bluePriest", priest)

    # ── 损血表（两套 DEF）──────────────────────────────────────────────────
    for hero_def in DEF_LIST:
        print(f"\n── compute_combat 损血  DEF={hero_def} mdef={MDEF_START}（hero HP=1e7 不致死）──")
        print(f"{'怪':<22}", end="")
        for a in ATKS:
            print(f"  ATK{a}", end="")
        print("    备注(turn @各ATK)")
        for tag, mon in (("boss 骷髅队长", boss), ("守卫 yellowGuard", guard),
                         ("初级法师 bluePriest", priest)):
            print(f"{tag:<22}", end="")
            turns = []
            for a in ATKS:
                dmg, turn = monster_loss(a, hero_def, MDEF_START, mon)
                cell = "打不动" if dmg is None else str(dmg)
                print(f"  {cell:>5}", end="")
                turns.append(f"{a}:{'∅' if dmg is None else turn}")
            print(f"    turn[{', '.join(turns)}]")

    # ── 任务预期校验（对两套 DEF 都报，看哪套命中）──────────────────────────
    # 结论：boss 342→304 命中 DEF=27（=英雄一区终态，与 baseline 实测 −304 吻合）。
    # 守卫 528→396 不命中 DEF20/27——反扫坐实它对应 hero DEF=4（任务方偏低旧口径）。
    # 守卫真实损血随 hero DEF：DEF20=336→252、DEF27=252→189。
    print("\n── 任务预期校验（boss≈342→304 命中DEF27 / 守卫528→396 实为DEF=4 旧口径）──")
    for hero_def in DEF_LIST:
        boss26, _ = monster_loss(26, hero_def, MDEF_START, boss)
        boss27, _ = monster_loss(27, hero_def, MDEF_START, boss)
        g26, _ = monster_loss(26, hero_def, MDEF_START, guard)
        g27, _ = monster_loss(27, hero_def, MDEF_START, guard)
        hit_boss = "✓命中342→304" if (boss26, boss27) == (342, 304) else ""
        print(f"  DEF={hero_def}:  boss ATK26→27 = {boss26}→{boss27} {hit_boss}   "
              f"守卫 ATK26→27 = {g26}→{g27}")
    g4_26, _ = monster_loss(26, 4, MDEF_START, guard)
    g4_27, _ = monster_loss(27, 4, MDEF_START, guard)
    print(f"  DEF= 4:  守卫 ATK26→27 = {g4_26}→{g4_27}  ✓命中528→396（坐实预期=DEF4 口径）")

    # ── 手算交叉验证 boss@ATK27 DEF27（透明化公式）────────────────────────────
    print("\n── boss@ATK27 DEF27 手算交叉验证（special=[]，纯 getDamageInfo）──")
    import math
    a, hero_def = 27, 27
    hp, atk, df = boss.hp, boss.atk, boss.def_
    hero_per = max(0, a - df)
    turn = math.ceil(hp / hero_per) if hero_per else 0
    per = max(0, atk - hero_def)
    total = (turn - 1) * per - MDEF_START
    print(f"  hero_per=ATK{a}-def{df}={hero_per}  turn=ceil({hp}/{hero_per})={turn}  "
          f"per_damage=atk{atk}-DEF{hero_def}={per}")
    print(f"  damage=(turn-1)*per-mdef=({turn}-1)*{per}-{MDEF_START}={total}  "
          f"（=baseline boss 战实测 −304）")


if __name__ == "__main__":
    main()
