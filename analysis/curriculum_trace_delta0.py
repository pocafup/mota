"""【课程学习·坐实 delta=0 的真实机制】只读 trace。

§S28 handoff 留的"诚实保留·未坐实"：固定 ATK=DEF=27 扫 HP_in，
  HP_in=200/300/400/500/600 → delta=final_hp-HP_in = 精确 0（连续 5 个值）
  HP_in=700/735/900 → delta=226（拐点在 600→700 之间、上方完全恒定）
为什么 HP<=600 时 delta 精确为 0？绝不靠推理——本脚本 dump 两条最优路径坐实。

口径与 curriculum_scan_vboss.py 完全一致：
  起点 = 真实存档 tok1168（刚进 MT10 打 boss 那一刻，ATK27 DEF27 HP735 redKey=1），
  深拷后【只覆写 ATK/DEF/HP】；每点跑 search_quotient(cross_floor=True 限{MT10,MT11}、
  beam_k=None 穷尽 Pareto、distinguish_doors=True、seg_step 把踏出{MT10,MT11}的子态置 dead)。

对 HP_in=600(delta=0) 和 HP_in=700(delta=226) 两点：取 res.actions(最大 HP 出口动作串)
用 sim.simulator.step 独立 replay，逐步 dump：kills 变化 / ATK/DEF 是否上涨(=拿战利品) /
是否踩 boss 埋伏触发格(6,5) / 是否杀队长(6,1 afterBattle) / 是否开红门(6,9) / 是否经下楼梯(6,11) /
楼层切换 / HP 谷底 / 最终落点 / 净损血；并 dump 两点各自的出口 Pareto 前沿 res.goal_frontier。

只读：复用 build_initial_state/load_tokens/step/_copy_state/search_quotient，绝不改产品码。
用法：python analysis/curriculum_trace_delta0.py [--max-states 600000]
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

# 关键格(MT10 boss 段拓扑，来源 data/games51/floors/MT10.json + docs/mechanics_51.md §G)
AMBUSH_TRIGGER = ("MT10", 6, 5)  # 踩此格触发埋伏 events["6,5"]（关机关门、8 骷髅就位、队长上移(6,1)）
CAPTAIN_CELL = ("MT10", 6, 1)    # 骷髅队长(队长被移上来后的格)；杀它触发 afterBattle["6,1"]
RED_DOOR = ("MT10", 6, 9)        # 红门(redDoor 83)，唯一通往下楼梯的门，redKey 可开
DOWN_STAIR = ("MT10", 6, 11)     # 下楼梯格(changeFloor :next → MT11)；初始 events enable=False
KEY_CELLS = {AMBUSH_TRIGGER: "埋伏触发(6,5)", CAPTAIN_CELL: "队长格(6,1)",
             RED_DOOR: "红门(6,9)", DOWN_STAIR: "下楼梯(6,11)"}


def seg_step(state, action):
    """把搜索框在本段：踏出 {MT10,MT11} 的子态置 dead 裁掉（与 scan 脚本同口径）。"""
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
    """从基准 boss 起点深拷一份，只覆写 entry 属性；其余(钥匙/金/位置)不动。"""
    s = _copy_state(base)
    s.hero.atk = atk
    s.hero.def_ = def_
    s.hero.hp = hp
    return s


def snap(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 金={h.gold} kills={h.kill_count}")


def red_door_open(s):
    """红门(6,9)当前是否已开：terrain==0(被开/清除)。MT10 红门 tile=83。"""
    try:
        return s.floors["MT10"].terrain[9][6] == 0
    except Exception:
        return None


def stair_enabled(s):
    """下楼梯(6,11)的 events.enable 当前值(show 后变 True 才能下楼，见 simulator _apply_stair_change)。"""
    try:
        ev = s.floors["MT10"].events.get("6,11")
        return ev.get("enable") if isinstance(ev, dict) else "(非dict)"
    except Exception:
        return None


def trace_replay(start, actions, tag):
    """从 start 用真实 step 独立 replay 动作串，逐步追踪关键事件。返回终态。"""
    print(f"\n────── {tag}：最优(最大HP)出口动作串独立 replay（共 {len(actions)} 步）──────")
    print(f" 起点 {snap(start)}")
    print(f"   红门(6,9)已开={red_door_open(start)} 下楼梯(6,11).enable={stair_enabled(start)}")
    s = start
    hp0 = start.hero.hp
    kills0 = start.hero.kill_count
    atk0, def_0 = start.hero.atk, start.hero.def_
    hp_min = hp0
    visited_key = {}          # 关键格 → 首次到达步号
    prev_floor = s.current_floor
    prev_kills = s.hero.kill_count
    prev_atk, prev_def = s.hero.atk, s.hero.def_
    captain_killed_step = None
    for i, a in enumerate(actions, 1):
        s = step(s, a)
        h = s.hero
        hp_min = min(hp_min, h.hp)
        # 关键格到达
        cur = (s.current_floor, h.x, h.y)
        if cur in KEY_CELLS and cur not in visited_key:
            visited_key[cur] = i
            print(f"   步{i:3} 抵达【{KEY_CELLS[cur]}】 | {snap(s)}")
        # 楼层切换
        if s.current_floor != prev_floor:
            print(f"   步{i:3} ★楼层切换 {prev_floor}→{s.current_floor} | {snap(s)}")
            prev_floor = s.current_floor
        # 杀怪（kills 上涨）
        if h.kill_count > prev_kills:
            print(f"   步{i:3} 杀怪 kills {prev_kills}→{h.kill_count} | {snap(s)}")
            prev_kills = h.kill_count
        # 属性上涨（拿战利品/装备）
        if h.atk != prev_atk or h.def_ != prev_def:
            print(f"   步{i:3} 属性变 ATK {prev_atk}→{h.atk} DEF {prev_def}→{h.def_} | {snap(s)}")
            prev_atk, prev_def = h.atk, h.def_
        # 队长 afterBattle 触发标志
        if captain_killed_step is None and _captain_flag(s):
            captain_killed_step = i
            print(f"   步{i:3} ★flag:10f战胜骷髅队长=True（杀队长触发 afterBattle）| {snap(s)}")
    print(f" 终点 {snap(s)}  dead={s.dead} won={s.won}")
    print(f" ── {tag} 汇总 ──")
    print(f"   净损血 = HP {hp0} → {s.hero.hp}（差 {hp0 - s.hero.hp}）；全程谷底 HP = {hp_min}")
    print(f"   kills {kills0}→{s.hero.kill_count}（杀 {s.hero.kill_count - kills0} 只）"
          f"  ATK {atk0}→{s.hero.atk}  DEF {def_0}→{s.hero.def_}")
    踩埋伏 = AMBUSH_TRIGGER in visited_key
    杀队长 = _captain_flag(s)
    开红门 = red_door_open(s)
    print(f"   踩埋伏触发格(6,5) = {踩埋伏}"
          + (f"（步{visited_key[AMBUSH_TRIGGER]}）" if 踩埋伏 else ""))
    print(f"   杀队长(flag:10f战胜骷髅队长) = {杀队长}"
          + (f"（步{captain_killed_step}）" if captain_killed_step else ""))
    print(f"   开红门(6,9) = {开红门}  下楼梯(6,11).enable(终态) = {stair_enabled(s)}")
    经下楼梯 = DOWN_STAIR in visited_key
    print(f"   经下楼梯格(6,11) = {经下楼梯}"
          + (f"（步{visited_key[DOWN_STAIR]}）" if 经下楼梯 else ""))
    到达目标 = (s.current_floor, s.hero.x, s.hero.y) == GOAL
    print(f"   终点到达目标 MT11(6,10) = {到达目标}")
    return s


def _captain_flag(s):
    """flag:10f战胜骷髅队长 是否已置（杀队长 afterBattle 设此 flag）。"""
    try:
        return bool(s.hero.flags.get("flag:10f战胜骷髅队长")) or \
               bool(s.hero.flags.get("10f战胜骷髅队长"))
    except Exception:
        return False


def dump_frontier(res, tag, hp_in):
    """dump 出口 Pareto 前沿（各点 HP/ATK/DEF/kills），看是否含'打 boss 的高 HP 出口'。"""
    print(f"\n────── {tag}：出口 Pareto 前沿 res.goal_frontier（{len(res.goal_frontier)} 个）──────")
    rows = []
    for v in res.goal_frontier:
        rows.append((v.get("hp", 0), v.get("atk", 0), v.get("def", 0),
                     v.get("kill", 0), v.get("gold", 0),
                     {k: vv for k, vv in v.items() if k.startswith("key:") and vv}))
    rows.sort(key=lambda r: r[0], reverse=True)
    print(f" {'HP':>6} {'ATK':>4} {'DEF':>4} {'kills':>5} {'金':>4}  钥/note")
    for hp, atk, df, kc, gold, keys in rows:
        note = f"  Δ={hp - hp_in:+d}" + (f" 钥={keys}" if keys else "")
        print(f" {hp:>6} {atk:>4} {df:>4} {kc:>5} {gold:>4}{note}")
    打boss出口 = [r for r in rows if r[1] > 27 or r[2] > 27 or r[3] > 0]
    print(f" → 前沿里'打了 boss / 涨了属性 / 有击杀'的出口数 = {len(打boss出口)}"
          f"（0 个 = 最优全是零损血绕路、boss 高 HP 出口被死亡剪枝剪掉）")


def run_point(base, hp_in, max_states):
    print("\n" + "=" * 78)
    print(f"========== HP_in={hp_in}（ATK=DEF=27）==========")
    s = make_entry(base, 27, 27, hp_in)
    t0 = time.time()
    res = search_quotient(s, GOAL, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=None, distinguish_doors=True)
    secs = time.time() - t0
    delta = (res.final_hp - hp_in) if res.found else None
    print(f" found={res.found} final_hp={res.final_hp} "
          f"delta={delta} hit_cap={res.hit_cap} 耗时={secs:.1f}s")
    print(f" states_expanded={res.states_expanded} admitted={res.states_admitted} "
          f"generated={res.states_generated} 指纹={res.distinct_fingerprints}")
    print(f" floors_seen={res.floors_seen} fp_by_floor={dict(res.fp_by_floor)}")
    if res.hit_cap:
        print(" ⚠ 撞 max_states 上限——结果可能不完整，如实记录。")
    if not res.found:
        print(" ⚠ 未找到到 MT11(6,10) 的出口（found=False）。")
        return res, delta
    dump_frontier(res, f"HP_in={hp_in}", hp_in)
    trace_replay(make_entry(base, 27, 27, hp_in), res.actions, f"HP_in={hp_in}")
    return res, delta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=600_000,
                    help="单点搜索上限(安全网防失控；真实 HP 下远够)")
    args = ap.parse_args()

    base = boss_entry_state()
    h = base.hero
    keys = {k: v for k, v in h.keys.items() if v}
    print("========== delta=0 真实机制坐实：起点 = 真实存档 tok1168 ==========")
    print(f" 基准起点 = {snap(base)} 金={h.gold}")
    print(f"   红门(6,9)已开={red_door_open(base)} 下楼梯(6,11).enable={stair_enabled(base)}")
    print(f" 目标 = {GOAL}  段楼层 = {sorted(ALLOWED)}  穷尽(beam_k=None) distinguish_doors=True")
    print(f" 关键格：埋伏触发(6,5) 队长(6,1) 红门(6,9) 下楼梯(6,11)")

    res600, d600 = run_point(base, 600, args.max_states)
    res700, d700 = run_point(base, 700, args.max_states)

    # ── 第三段：坐实 scan_vboss 里 HP<=600 "delta=0" 是【测量污染】假象 ────────────────
    # 根因：sim.simulator._copy_state 深拷 FloorState 时 events=f.events 是【共享引用】(line~190)，
    #   不深拷。搜索 HP=735 打 boss 时 afterBattle["6,1"] 的 show([6,11]) 执行 ev["enable"]=True，
    #   就地改了这个共享 dict → 永久污染 base 及之后所有从 base 深拷的态。scan_vboss 先跑遍①
    #   (HP=735 打 boss) 再跑遍②(HP=600)，故 HP=600 起点的 (6,11).enable 已被污染成 True →
    #   零损血走 (6,11) 下楼梯绕路下楼可行 → found=True delta=0(假)。本对照在干净 base 上复现。
    print("\n" + "=" * 78)
    print("========== 第三段：坐实 'HP<=600 delta=0' = 测量污染假象（非真实机制）==========")
    base2 = boss_entry_state()   # 全新干净 base，未被任何搜索污染
    print(f" 干净 base 起点 (6,11).enable = {stair_enabled(base2)}（应为 False）")
    print(" ── 制造污染：先跑 HP=735(打 boss·会执行 show([6,11])) ──")
    s735 = make_entry(base2, 27, 27, 735)
    r735 = search_quotient(s735, GOAL, seg_step, max_states=args.max_states,
                           cross_floor=True, beam_k=None, distinguish_doors=True)
    print(f"   HP=735 found={r735.found} final_hp={r735.final_hp}（打 boss）")
    print(f"   ★ 跑完后 base2 起点 (6,11).enable = {stair_enabled(base2)}"
          f"  ← 若变 True 即【共享 events dict 被就地污染】")
    print(" ── 污染后再跑 HP=600（应翻成 found=True delta=0，复现 scan_vboss 假象）──")
    s600c = make_entry(base2, 27, 27, 600)
    r600c = search_quotient(s600c, GOAL, seg_step, max_states=args.max_states,
                            cross_floor=True, beam_k=None, distinguish_doors=True)
    dc = (r600c.final_hp - 600) if r600c.found else None
    print(f"   污染后 HP=600 found={r600c.found} final_hp={r600c.final_hp} delta={dc}")
    if r600c.found:
        trace_replay(make_entry(base2, 27, 27, 600), r600c.actions, "污染后 HP=600")

    print("\n" + "=" * 78)
    print("========== 对比小结 ==========")
    print(f" 干净 HP_in=600（无污染）: found={res600.found} final_hp={res600.final_hp} delta={d600}")
    print(f" 干净 HP_in=700（无污染）: found={res700.found} final_hp={res700.final_hp} delta={d700}")
    print(f" 污染后 HP_in=600       : found={r600c.found} final_hp={r600c.final_hp} delta={dc}")
    print("\n ★ 结论（以上述 dump 为准）：")
    print("   · HP=700 delta=226 真相 = 血够撑过 boss 战谷底(HP↓到~66)，最优【打 boss】拿战利品")
    print("     (ATK/DEF 各+3、杀~10 怪净赚)；非'零损血绕路'。")
    print("   · 干净态 HP<=600：boss 战谷底会死(死亡剪枝)，且不打 boss 时 (6,11) 下楼梯 enable=False")
    print("     物理下不去 → found=False，根本【没有】delta=0 的出口。")
    print("   · scan_vboss 的 'HP<=600 delta=0' = 遍①(HP=735 打boss)经共享 events dict 把 (6,11)")
    print("     永久启用，污染遍②→ HP=600 走被污染启用的下楼梯零损血绕路。是测量污染、非真实机制。")


if __name__ == "__main__":
    main()
