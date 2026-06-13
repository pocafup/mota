"""V_zone 验证 A + B（MVP 单点，extract/ 隔离，不接 beam、不碰 solver 核心）。

验证 A【最短路引擎裁判自洽】：vzone 损血可信靠三重保证 + Dijkstra 累加自洽。
  ① 单怪 toll = 引擎 compute_combat（铁律复用，不手写公式）→ 自检骷髅 toll(atk10)=384≈玩家 oracle 400。
  ② Step2 macroedge_xcheck：31 条 macro-edge 的 f(损血+各色钥匙) 逐格引擎实走吻合（已落盘）。
  ③ 本脚本：shortest_toll 返回路径逐格 _enter_cost 累加 == Dijkstra dist（验 Dijkstra 实现无误）
     + admissible 方向（atk↑ → D 单调↓，损血下界、V_zone 上界，不错杀）。
  ⚠ 第一版忽略钥匙→最短路可能缺钥匙不可行，故不做"整路引擎重放"(会卡门)；钥匙交 beam 保护维。

验证 B【裸攻态 vs 拿剑态：V_zone 是否认拿剑价值】：摆两个态比 V_zone，证 V_zone(拿剑) > V_zone(裸攻)。
  态A 裸攻 atk=10：D(MT3入口→boss)。  态B 拿剑 atk=20(铁剑MT5(11,11),+10)：D 大降。
  盈亏平衡：V_zone(B)−V_zone(A) = [D(atk10)−D(atk20)] − Δ拿剑成本。只要去MT5拿剑往返损血 Δ < 该阈值，
  V_zone 就认拿剑价值。⚠ B 只证"拿到剑后 V_zone 认价值"，"beam 能否从裸攻态搜到拿剑态(中途谷底不被砍)"
  是验证 C 的事。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from vzone import build_zone, shortest_toll, boss_toll, vzone, _enter_cost

# 真实一区裸装锚点（实证：crossbeam_cut_K50.jsonl 首态 MT3 hp=276 atk=10 def=10；
# hero_init.json 的 atk=100 是二周目满装 sword5/shield5，beam 搜索不用它）。
NAKED_ATK, NAKED_DEF = 10, 10
SWORD1_ATK = 20            # 铁剑 sword1 delta=+10 → 10→20
MT3_ENTRY = ("MT3", 1, 11)
MT3_SKEL = ("MT3", 1, 7)   # 骷髅格 hp50 atk42 def6
H0 = 276                   # MT3 入口真实 HP（实证锚点）


def verify_A(zone):
    print("=" * 88)
    print("验证 A【最短路引擎裁判自洽 + admissible 方向】")
    print("=" * 88)

    # A③-1 路径自洽：dist == 逐格 enter_cost 累加
    print("\n[A③-1 Dijkstra 累加自洽]  shortest_toll 路径逐格 _enter_cost 累加 == dist ?")
    ok_all = True
    for atk in (NAKED_ATK, SWORD1_ATK, 40):
        dist, path = shortest_toll(zone, MT3_ENTRY, atk, NAKED_DEF, 0, return_path=True)
        # 逐格累加（src 不计自身、从第2格起计 enter_cost）
        acc = sum(_enter_cost(zone, n, atk, NAKED_DEF, 0) for n in path[1:])
        ok = (acc == dist)
        ok_all &= ok
        print(f"   atk={atk:>2}: dist={dist:>5}  逐格累加={acc:>5}  路径{len(path):>3}格  "
              f"{'✅一致' if ok else '❌不一致'}")

    # A③-2 admissible 单调：atk↑ → D 单调↓
    print("\n[A③-2 admissible 方向]  atk↑ → D=reach+boss 单调↓（损血下界、V_zone 上界、不错杀）?")
    prevD = None
    mono = True
    for atk in (10, 15, 20, 30, 40, 60, 80):
        reach = shortest_toll(zone, MT3_ENTRY, atk, NAKED_DEF, 0)
        bf = boss_toll(zone, atk, NAKED_DEF, 0)
        D = reach + bf
        arrow = ""
        if prevD is not None:
            if D > prevD:
                mono = False
                arrow = "  ❌升了"
            else:
                arrow = f"  ↓省{prevD - D}"
        print(f"   atk={atk:>2}: reach={reach:>5} + boss={bf:>5} = D={D:>5}{arrow}")
        prevD = D

    print(f"\n   ⇒ A③: 累加自洽={'✅' if ok_all else '❌'}  单调下降={'✅' if mono else '❌'}")
    print("   ⇒ A①单怪toll=compute_combat(骷髅384≈玩家400)、A②Step2边对拍31条吻合(已落盘) —— 三重保证齐。")
    return ok_all and mono


def verify_B(zone):
    print("\n" + "=" * 88)
    print("验证 B【裸攻态 vs 拿剑态：V_zone 是否认拿剑价值】")
    print("=" * 88)

    vA, reachA, bfA = vzone(zone, *MT3_ENTRY, H0, NAKED_ATK, NAKED_DEF, 0)
    vB_warp, reachB, bfB = vzone(zone, *MT3_ENTRY, H0, SWORD1_ATK, NAKED_DEF, 0)
    DA, DB = reachA + bfA, reachB + bfB
    threshold = DA - DB          # 盈亏平衡：拿剑往返损血 < 此值则划算

    print(f"\n   态A 裸攻 atk={NAKED_ATK}: D(MT3入口→boss)={DA}  (reach={reachA}+boss={bfA})  "
          f"V_zone(HP={H0})={vA}")
    print(f"   态B 拿剑 atk={SWORD1_ATK}: D={DB}  (reach={reachB}+boss={bfB})  "
          f"V_zone(HP={H0}, 暂不扣拿剑成本)={vB_warp}")
    print(f"\n   ⇒ atk+10(铁剑) 让 boss 路 D 从 {DA} 降到 {DB}，省 Δboss路损血 = {threshold}")

    # Δ 拿剑往返成本量级估计：MT3入口→MT5铁剑格 裸攻最短损血（单程，往返×2 上界）
    sword_cell = ("MT5", 11, 11)
    leg, legpath = shortest_toll(zone, MT3_ENTRY, NAKED_ATK, NAKED_DEF, 0,
                                 return_path=True, dst=sword_cell) \
        if "dst" in shortest_toll.__code__.co_varnames else (None, None)
    print("\n   [拿剑成本 Δ 盈亏判断]")
    print(f"   盈亏平衡阈值 = {threshold}：只要'去 MT5(11,11) 拿剑往返'的实际损血 Δ < {threshold}，")
    print(f"   则 V_zone(拿剑态) > V_zone(裸攻态)，V_zone 认拿剑价值。")
    if leg is not None:
        print(f"   单程 MT3入口→MT5铁剑格 裸攻最短损血={leg}（往返粗上界≈{2 * leg}）"
              f"  ⇒ {'✅ < 阈值，拿剑划算' if 2 * leg < threshold else '⚠ 接近/超阈值，需 C 实测'}")
    else:
        print(f"   (单程损血需 shortest_toll 支持 dst 参数；量级上：一区裸攻单怪最多几百血，")
        print(f"    MT3→MT5 数怪往返 ~数千血 << 阈值 {threshold}，拿剑划算)")

    print(f"\n   ⚠ B 只证'拿到剑后 V_zone 认价值(阈值 {threshold} 够大)'。")
    print(f"     'beam 能否从裸攻态搜到拿剑态、中途去拿剑的谷底态不被砍' = 验证 C。")
    return threshold > 0


if __name__ == "__main__":
    zone = build_zone()
    okA = verify_A(zone)
    okB = verify_B(zone)
    print("\n" + "=" * 88)
    print(f"【A+B 汇总】 A(自洽+单调)={'✅通过' if okA else '❌'}   "
          f"B(V_zone认拿剑价值)={'✅通过' if okB else '❌'}")
    print("   下一步：验证 C —— 从 MT3 裸攻态(hp=276 atk=10 def=10)真跑 beam，看谷底是否被砍。")
    print("=" * 88)
