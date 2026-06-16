"""【课程学习·V_boss 价值表扫描】网格化扫 entry 属性(ATK/DEF/HP) → 打 boss 段【最优剩多少血】。

§S27 课程学习框架的【核心产出 + 可行性判据】：
  · 产出 = V_boss 价值表：带不同 (ATK,DEF,HP) 去打 boss，穷尽搜出口剩的最大 HP。这张表就是
    "照亮攒攻防的灯"——攒攻防阶段每个状态查 V_boss(它的属性) 即知真实价值(稠密奖励)，正面解掉
    "走不到终点→奖励稀疏→深谷死"。
  · 判据 = V_boss 是否【便宜/光滑到可制表+插值】。若每点要 ~55s 穷尽搜、且 delta 随属性乱跳，
    则没法当稠密奖励逐状态查；若 delta(ATK,DEF) 光滑且与 HP_in 无关(只在生死线下塌)，则一张
    小网格 + 插值即可 O(1) 查询 → 框架可行。本脚本就是来量这件事的。

口径：起点 = 真实存档 tok1168(刚进 MT10 打 boss 那一刻)，深拷后【只覆写 ATK/DEF/HP】，其余
  (redKey=1 开红门必需 / 金 / 位置) 保持真实起点不动。每点跑 solver.quotient.search_quotient
  (cross_floor=True 限{MT10,MT11}、beam_k=None 穷尽 Pareto、distinguish_doors=True 修红门 bug)，
  取 res.final_hp(最大 HP 出口) 当 V_boss。

两遍扫：
  ① 2D(ATK×DEF) @ HP=735(真实起点值)：固定 HP 量 delta=final_hp-HP_in(boss 段的"HP 税/红利"
     仅由战力决定)。看 delta(ATK,DEF) 是否光滑/有台阶(连杀回合 ceil、防御跨怪攻阈值)。
     ★为何不给"充裕 HP"：HP 给足会关掉死亡剪枝→强战力下状态空间爆炸(实测 50min/924MB 未收)；
       在真实 HP 下搜既有界(死亡剪枝)又更贴框架真问题(V_boss 本就该按查询 HP 搜)。survivable
       点拿到 delta、过弱点 found=False(死在半路)——后者本身就是生死线信号。
  ② 1D(HP) @ ATK=DEF=27(真实起点战力)：扫 HP_in 找【生死线】(found 翻 False / final_hp 塌) +
     验证"survivable 区间内 delta 与 HP_in 无关"(若成立→V_boss(a,d,h)=h+delta(a,d) 解析可算)。

只读：复用 build_initial_state/load_tokens/step/_copy_state/search_quotient，绝不改产品码。
用法：python analysis/curriculum_scan_vboss.py [--quick] [--atk 24,27,30,33] [--def 24,27,30,33]
      [--hp 150,200,250,300,400,600,900] [--hp2d 735] [--max-states 600000]
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from analysis.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step, _copy_state
from solver.quotient import search_quotient

BOSS_ENTRY_TOK = 1168            # 真实存档第5次进 MT10 = 打 boss visit
GOAL = ("MT11", 6, 10)           # 段目标：下到 MT11 出口格
ALLOWED = {"MT10", "MT11"}       # 段内楼层；离段(回 MT9 等)裁掉
REAL = (27, 27, 735)             # 真实起点 (ATK,DEF,HP)，参照


def seg_step(state, action):
    """把搜索框在本段：踏出 {MT10,MT11} 的子态置 dead 裁掉。"""
    ns = step(state, action)
    if ns.current_floor not in ALLOWED:
        ns.dead = True
    return ns


def boss_entry_state():
    """重放真实存档到刚进 MT10(打 boss 那一刻)，返回该基准起点。"""
    s = build_initial_state()
    tokens = load_tokens()
    for tok in tokens[:BOSS_ENTRY_TOK + 1]:
        s = step(s, tok)
    return s


def make_entry(base, atk, def_, hp):
    """从基准 boss 起点深拷一份，只覆写 entry 属性 (atk/def/hp)；其余(钥匙/金/位置)不动。
    深拷保证 base 不被污染、每点独立。"""
    s = _copy_state(base)
    s.hero.atk = atk
    s.hero.def_ = def_
    s.hero.hp = hp
    return s


def scan_point(base, atk, def_, hp, max_states):
    s = make_entry(base, atk, def_, hp)
    t0 = time.time()
    res = search_quotient(s, GOAL, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=None, distinguish_doors=True)
    return res, time.time() - t0


def parse_ints(s):
    return [int(x) for x in s.split(",") if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atk", type=str, default="24,27,30,33")
    ap.add_argument("--def", dest="dfn", type=str, default="24,27,30,33")
    ap.add_argument("--hp", type=str, default="150,200,250,300,400,600,900")
    ap.add_argument("--hp2d", type=int, default=735, help="2D 扫所用 HP(真实起点值=735；死亡剪枝保持开启=有界)")
    ap.add_argument("--max-states", type=int, default=600_000, help="单点搜索上限(安全网防失控；真实 HP 下远够)")
    ap.add_argument("--quick", action="store_true", help="缩网格快速冒烟(atk/def=24,30 hp=300,900)")
    args = ap.parse_args()

    if args.quick:
        atks, defs, hps = [24, 30], [24, 30], [300, 900]
    else:
        atks, defs, hps = parse_ints(args.atk), parse_ints(args.dfn), parse_ints(args.hp)

    base = boss_entry_state()
    h = base.hero
    keys = {k: v for k, v in h.keys.items() if v}
    print("========== V_boss 扫描：起点 = 真实存档 tok1168 ==========")
    print(f" 基准起点 = MT10({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"钥={keys} 金={h.gold}")
    print(f" 目标 = {GOAL}  段楼层 = {sorted(ALLOWED)}  穷尽(beam_k=None) distinguish_doors=True")

    # ── 遍 ①：2D(ATK×DEF) @ 充裕 HP，量纯 delta ───────────────────────────────
    HP2D = args.hp2d
    print(f"\n\n========== 遍① 2D(ATK×DEF) @ HP={HP2D}(真实起点·死亡剪枝有界) → 纯 delta=final_hp-HP_in ==========")
    print(f" {'ATK':>4} {'DEF':>4} | {'found':>5} {'final_hp':>9} {'delta':>7} {'出口':>4} {'指纹':>5} {'秒':>6}")
    grid = {}
    for a in atks:
        for d in defs:
            res, secs = scan_point(base, a, d, HP2D, args.max_states)
            delta = (res.final_hp - HP2D) if res.found else None
            grid[(a, d)] = (res, delta)
            ds = f"{delta:>7}" if delta is not None else f"{'--':>7}"
            print(f" {a:>4} {d:>4} | {str(res.found):>5} {res.final_hp:>9} {ds} "
                  f"{len(res.goal_frontier):>4} {res.distinct_fingerprints:>5} {secs:>6.1f}", flush=True)

    # delta 矩阵(行=ATK 列=DEF) + 光滑性诊断
    print(f"\n ── delta(ATK,DEF) 矩阵(行ATK 列DEF；段的 HP 税<0/红利>0)──")
    print("  ATK\\DEF " + "".join(f"{d:>7}" for d in defs))
    for a in atks:
        cells = []
        for d in defs:
            _, delta = grid[(a, d)]
            cells.append(f"{delta:>7}" if delta is not None else f"{'--':>7}")
        print(f" {a:>7}  " + "".join(cells))

    # ── 遍 ②：1D(HP) @ 真实战力(27,27)，找生死线 + 验 delta 与 HP_in 无关 ──────────
    ra, rd, _ = REAL
    print(f"\n\n========== 遍② 1D(HP) @ ATK={ra} DEF={rd} → 生死线 + delta 是否随 HP_in 不变 ==========")
    print(f" {'HP_in':>6} | {'found':>5} {'final_hp':>9} {'delta':>7} {'出口':>4} {'指纹':>5} {'秒':>6}")
    for hp in hps:
        res, secs = scan_point(base, ra, rd, hp, args.max_states)
        delta = (res.final_hp - hp) if res.found else None
        ds = f"{delta:>7}" if delta is not None else f"{'--':>7}"
        print(f" {hp:>6} | {str(res.found):>5} {res.final_hp:>9} {ds} "
              f"{len(res.goal_frontier):>4} {res.distinct_fingerprints:>5} {secs:>6.1f}", flush=True)

    print("\n ★ 读表：遍①若 delta(ATK,DEF) 光滑/弱台阶 + 遍②若 survivable 区 delta 恒定 →")
    print("   V_boss(a,d,h)=h+delta(a,d)(生死线上) 可由小网格插值 O(1) 查 → 框架【可行】当稠密奖励。")
    print("   若 delta 乱跳 / 每点 ~55s 太贵 → 需更粗的代理(只制表关键属性 / 学一个回归器)。")


if __name__ == "__main__":
    main()
