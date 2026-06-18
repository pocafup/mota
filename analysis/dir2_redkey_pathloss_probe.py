"""【方向2·诊断·只读·可行性评估】Φ_path(a,d)=段内全怪损血加总 能不能当「属性价值含路上损血」的排序键修正？
诚实回答玩家三问（2026-06-17·先评估能不能实现、再给方案、玩家拍板后才动产品码）：

 【甲·能不能估】Φ_path(a,d) 是不是像 §S37 delta 矩阵一样的【静态 (a,d)→HP 表】：可预计算、O(1)查、
     引擎 compute_combat 实算、无魔法数、无距离引导、无路线依赖（=无惰性·与位置/可达区无关）。→ 本脚本直接算出来给看。

 【乙·路上损血好不好估】玩家自己点破的鸡生蛋：路线还没定→精确"打哪些怪"不知道。但排序键只需要【梯度】
     （+1 属性在路上能省多少血）指对方向，不需要绝对精确。近似=用"段内 9 层全怪"当必打集 → 这是【上界】
     （真打的怪 ⊆ 全怪·绕开的不算）→ 真实路上损血 ≤ Φ_path；而梯度同号（属性越高每只怪损血越少）。

 【丙·梯度够不够大】★关键 go/no-go：gΦ = Σ_怪[dmg(a,d) − dmg(a+1,d)] = +1 属性在【全段】省的血。
     现在 beam 排序键 v_boss=hp+delta，delta 只算 boss 段（seam→队长）→ +1 属性只值 ~60；而一瓶血值 +400
     → blood 400 碾压 attr 60 → beam 拿血（病根）。
     若把 Φ_path 加进去：+1 属性 = 60 + gΦ。若 gΦ ≈ 或 > 400 → +1 属性 ≥ 一瓶血 → beam 翻成"先攒属性"=病根被修。
     若 gΦ 只有几十 → 这修法推不动 beam、得换思路。→ 本脚本报数、写清含义、【不替玩家拍板】。

只读：不碰封板件（solver/quotient.py·solver/beam.py·solver/fitness.py），只构造诊断态调 compute_combat。
绝不改产品码、绝不手算损血（引擎权威）。用法：python -u analysis/dir2_redkey_pathloss_probe.py
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

from analysis.extract_zone1_milestones import build_initial_state   # noqa: E402
from solver.fitness import _zone_floor_cells                        # noqa: E402
from solver.beam import _combat_damage                              # noqa: E402
from extract.key_targets import _FULL_AFFORD                        # noqa: E402

try:
    from analysis.dir2_redkey_beam_probe import delta_interp         # noqa: E402
except Exception:
    delta_interp = None

# 与 §S39 三探针一致：方向2"铁盾态穿9层拿红钥"沿途的真实 9 层（MT2 不在腿上）。
REAL_LEG = ["MT1", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10"]
HUGE_HP = 10 ** 7   # 诊断时把 hp 设极大 → 永不拒战 → _combat_damage 给原始损血（拒战是调用方的事）
# 细网格（步长1）→ 直接读每点梯度。覆盖 beam 卡住的 ATK24-25/DEF23-25 与破红钥需要的 +1。
ATK_GRID = list(range(22, 29))   # 22..28
DEF_GRID = list(range(22, 29))   # 22..28
BLOOD = 400                      # 一瓶大血瓶≈+400 → beam 现在拿血的诱惑基准（仅作对照·非写进排序）


def enum_path_monsters(s):
    """枚举 9 层全部怪格 → 扁平 [(fid, mid)]。怪位置与 hero 属性无关（读 terrain/entities/静态JSON）。
    afford=_FULL_AFFORD（全色·门不锁）→ 最大化枚举（门后的怪也算进必打集上界）。"""
    flat, per_floor = [], {}
    for fid in REAL_LEG:
        info = _zone_floor_cells(s, fid, _FULL_AFFORD)
        if info is None:
            per_floor[fid] = 0
            continue
        _h, _w, _is_wall, mid_at, _kc, _src = info
        mids = list(mid_at.values())
        per_floor[fid] = len(mids)
        flat.extend((fid, mid) for mid in mids)
    return flat, per_floor


def damages_at(s, flat, a, d):
    """在 (a,d) 态下逐怪算损血（引擎 compute_combat）→ 与 flat 对齐的 list；None=打不动(atk≤防)。"""
    s.hero.atk, s.hero.def_, s.hero.hp = a, d, HUGE_HP
    return [_combat_damage(s, mid) for (_fid, mid) in flat]


def main():
    s = build_initial_state()
    flat, per_floor = enum_path_monsters(s)
    N = len(flat)
    print("=" * 92)
    print("方向2·只读可行性评估：Φ_path(a,d)=段内9层全怪损血加总 能否修正排序键的属性价值")
    print("=" * 92)
    print(f"枚举 {len(REAL_LEG)} 层全部怪格 = {N} 只（afford=全色·上界·门后怪也算）")
    print("  每层怪数：" + "  ".join(f"{fid}:{per_floor[fid]}" for fid in REAL_LEG))

    # 预算每个 (a,d) 的逐怪损血表 → D[(a,d)] = 与 flat 对齐的 list
    D = {}
    for a in ATK_GRID:
        for d in DEF_GRID:
            D[(a, d)] = damages_at(s, flat, a, d)

    def phi_kill(a, d):
        return sum(x for x in D[(a, d)] if x is not None)

    def n_unkill(a, d):
        return sum(1 for x in D[(a, d)] if x is None)

    # ── 【甲】Φ_kill(a,d) 是个干净静态表（可预计算·O(1)查·像 delta 矩阵）──
    print("\n" + "─" * 92)
    print("【甲·能不能估】Φ_kill(a,d) = Σ可杀怪损血（引擎实算）→ 干净的静态 (a,d)→HP 表，可像 delta 矩阵预存：")
    print("─" * 92)
    print("  DEF→ " + "".join(f"{d:>9}" for d in DEF_GRID))
    for a in ATK_GRID:
        row = "".join(f"{phi_kill(a, d):>9}" for d in DEF_GRID)
        print(f"  ATK{a:<2} {row}")
    print("  ⟹ ATK≥23 后单调：属性越高 Φ_kill 越小（沿途越省血）= 方向对；可预存查表 O(1)、无路线依赖=无惰性。")
    print("  ⚠ 唯一非单调=ATK22 行反比 ATK23 低：因 ATK22 有 2 只打不动的怪被排除出和（见【乙】），跨过门槛后才计入→")
    print("    这是'打不动→可杀'门槛跳变（不是省血）。beam 操作区 ATK24-25 全 112 只可杀(n_unkill=0)→该区干净无此跳变。")

    # ── 【乙】组成：打不动的怪数（=你只能绕开的怪·不进必打集）──
    print("\n" + "─" * 92)
    print("【乙·路上损血好不好估】路线没定→精确不知；但'全怪'=必打集【上界】(真打⊆全怪)、梯度同号即可指路。")
    print("  下表=各 (a,d) 打不动的怪数(atk≤防·只能绕)。随 ATK 升而降=门槛被跨过解锁(梯度的另一来源)：")
    print("─" * 92)
    print("  DEF→ " + "".join(f"{d:>6}" for d in DEF_GRID))
    for a in ATK_GRID:
        row = "".join(f"{n_unkill(a, d):>6}" for d in DEF_GRID)
        print(f"  ATK{a:<2} {row}")

    # ── 【丙】★go/no-go：+1 属性在全段省多少血（公共可杀集上的纯损血下降 + 解锁的怪）──
    print("\n" + "─" * 92)
    print("【丙·★go/no-go】gΦ = +1属性在全段省的血。对照基准：一瓶血≈+400；现 delta 的 boss段梯度只 ~60。")
    print("  gΦ 拆两部分：①公共可杀集上的损血下降(纯属性省血) ②新解锁的怪(门槛跨过·此前打不动)。")
    print("─" * 92)

    def grad_atk(a, d):
        """a→a+1：①公共可杀集损血下降之和 ②新解锁怪数。"""
        cur, nxt = D[(a, d)], D[(a + 1, d)]
        drop = sum(cur[i] - nxt[i] for i in range(N)
                   if cur[i] is not None and nxt[i] is not None)
        unlocked = sum(1 for i in range(N) if cur[i] is None and nxt[i] is not None)
        return drop, unlocked

    def grad_def(a, d):
        """d→d+1：DEF 不解锁怪(可杀性看 ATK vs 怪防)，纯损血下降。"""
        cur, nxt = D[(a, d)], D[(a, d + 1)]
        drop = sum(cur[i] - nxt[i] for i in range(N)
                   if cur[i] is not None and nxt[i] is not None)
        return drop

    def boss_grad_atk(a, d):
        if delta_interp is None:
            return None
        return delta_interp(a + 1, d) - delta_interp(a, d)   # delta 是负的损血·越大越好→差=改善

    def boss_grad_def(a, d):
        if delta_interp is None:
            return None
        return delta_interp(a, d + 1) - delta_interp(a, d)

    print(f"  {'态(a,d)':>10} | {'+1ATK全段省血':>26} | {'+1DEF全段省血':>16} | {'对照:boss段梯度(delta)':>24}")
    print(f"  {'':>10} | {'(纯省血 / 新解锁怪)':>26} | {'(纯省血)':>16} | {'+1ATK / +1DEF':>24}")
    focus = [(24, 23), (24, 24), (25, 23), (25, 24), (25, 25), (26, 25), (26, 26)]
    for (a, d) in focus:
        if (a + 1, d) not in D or (a, d + 1) not in D:
            continue
        da_drop, da_unlock = grad_atk(a, d)
        dd_drop = grad_def(a, d)
        ba, bd = boss_grad_atk(a, d), boss_grad_def(a, d)
        bstr = f"{ba:>+11} /{bd:>+11}" if ba is not None else f"{'n/a':>24}"
        print(f"  ATK{a}/DEF{d:<2} | {da_drop:>14} 省 / 解锁{da_unlock:>2}只 | {dd_drop:>14} 省 | {bstr}")

    # 汇总判据（报数·写清含义·不替玩家拍板）
    print("\n" + "─" * 92)
    print("【结论·诚实报数·不替玩家拍板】")
    print("─" * 92)
    # 取 beam 卡住的代表态 ATK25/DEF24 看 +1 属性能不能逼近/超过一瓶血(400)
    a0, d0 = 25, 24
    da_drop, da_unlock = grad_atk(a0, d0)
    dd_drop = grad_def(a0, d0)
    print(f"  代表态 ATK{a0}/DEF{d0}（beam 卡住区）：")
    print(f"    • +1 ATK 在全段省血 = {da_drop}（另解锁 {da_unlock} 只此前打不动的怪）")
    print(f"    • +1 DEF 在全段省血 = {dd_drop}")
    print(f"    • 对照：一瓶血 = +{BLOOD}；现排序键里 +1 属性只值 ~60（仅 boss 段 delta）。")
    best = max(da_drop, dd_drop)
    print(f"\n  【甲】Φ_path 能像 delta 一样预存成静态 (a,d) 表（上方表格即是）：可行、O(1)、引擎实算、无魔法数/无距离。")
    print(f"  【乙】'路上损血'用'段内全怪'估 = 必打集上界（真实 ≤ 此）；排序只用梯度、方向恒对（属性越高越省）。")
    if best >= BLOOD:
        print(f"  【丙】✓ +1 属性全段省血(上界 {best}) ≥ 一瓶血({BLOOD})：把 Φ_path 加进排序键后，攒属性的吸引力可超过拿血")
        print(f"        → 有把握把 beam 从'拿血'翻成'先攒属性'。⚠ 但这是上界(全怪)，真打子集会打折→见下方折扣敏感度。")
    elif best >= BLOOD * 0.5:
        print(f"  【丙】~ +1 属性全段省血(上界 {best}) 约为半瓶~一瓶血：方向对、但因是上界(全怪)、真实打折后可能不够碾压拿血")
        print(f"        → 修法大概率改善、但未必单独翻盘；可能需配合'血够时不拿血'的够用判断（玩家精确策略）。")
    else:
        print(f"  【丙】✗ +1 属性全段省血(上界 {best}) 仍 < 半瓶血：纵是上界也压不过拿血 → 这个修法推不动 beam、得换思路。")
    # 折扣敏感度：真打的怪只是全怪的一部分
    print(f"\n  折扣敏感度（真打的怪 ⊆ 全怪·按比例打折看 +1ATK 省血 vs 一瓶血 {BLOOD}）：")
    for frac in (1.0, 0.6, 0.4, 0.3):
        v = da_drop * frac
        mark = "≥血" if v >= BLOOD else "<血"
        print(f"    若实打 {int(frac * 100):>3}% 的怪：+1ATK 省血≈{v:>7.0f}  ({mark})")
    print("\n  （以上全引擎 compute_combat 实算·只读·未改任何产品码。下步=玩家看数拍板要不要把 Φ_path 加进排序键。）")


if __name__ == "__main__":
    main()
