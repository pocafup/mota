"""【地基核查·DEF30 结构误判】玩家游戏事实：一区 DEF 上限=27、30 不存在；MT10 的 3 颗蓝宝石
(9,3)(10,3)(11,3) 是【队长 afterBattle 死后 setBlock 才出现】的奖励。但 boss 段搜索出口 ATK/DEF
从 27→30（+3/+3）。本脚本 dump 那条 max-HP 解的逐步资源时序，定死 +3 来自哪里、在杀队长之前还是之后：

  若 ATK/DEF+3 发生在【杀队长（kills→70）之前】且踩的是死后宝石格 → 搜索把"死后奖励"当战中可用资源
  = 结构误判 bug（疑 §S28 afterBattle 事件污染未修干净的 setBlock 部分）→ V_boss/完胜存档全要重评。

  若 +3 发生在【杀队长之后】（先到 6,1 杀队长→afterBattle 放宝石→再走去 (9,3) 等拿）→ 那 goal 判据
  "到达队长格"被搜索绕到"杀完队长再回头扫战利品"，出口态含死后奖励 → goal 口径要收紧到"杀队长瞬间"。

只读·不改产品码。MT10.json 已读出的关键坐标（来源 data/games51/floors/MT10.json）：
  战前 blueGem(28)=(2,6)  redGem(27)=(10,6)
  afterBattle["6,1"] setBlock 死后奖励：redGem→(1,3)(2,3)(3,3)  blueGem→(9,3)(10,3)(11,3)
                                       bluePotion(32)→(1,4)(2,4)(3,4)  id21→(9,4)(10,4)(11,4)
用法：python -u analysis/dump_boss_solution.py
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

from analysis.seg_chain_verify import replay_to_token, make_seg_step, CAPTAIN, fmt
from sim.simulator import step
from solver.quotient import search_quotient

# MT10.json 已核对坐标（写明来源·非心算）
PRE_GEMS = {(2, 6): "战前blueGem(+DEF)", (10, 6): "战前redGem(+ATK)"}
POST_BATTLE = {
    (1, 3): "★死后redGem", (2, 3): "★死后redGem", (3, 3): "★死后redGem",
    (9, 3): "★死后blueGem", (10, 3): "★死后blueGem", (11, 3): "★死后blueGem",
    (1, 4): "★死后bluePotion", (2, 4): "★死后bluePotion", (3, 4): "★死后bluePotion",
    (9, 4): "★死后id21", (10, 4): "★死后id21", (11, 4): "★死后id21",
}


def main():
    start = replay_to_token(1019)
    print("起点(replay tok1019)：", fmt(start))
    seg_step = make_seg_step({"MT10"})
    res = search_quotient(start, CAPTAIN, seg_step, max_states=600_000,
                          cross_floor=False, beam_k=None, distinguish_doors=True)
    print(f"found={res.found} 前沿={len(res.goal_frontier)} "
          f"goal_frontier_actions={len(res.goal_frontier_actions)}")

    # 选 max-HP 出口那条动作串（重放重建，挑 HP 最大）
    best = None  # (hp, acts, exit_state)
    for acts in res.goal_frontier_actions:
        s = start
        for a in acts:
            s = step(s, a)
        if s.current_floor == "MT10" and (s.hero.x, s.hero.y) == (6, 1) and not s.dead:
            if best is None or s.hero.hp > best[0]:
                best = (s.hero.hp, acts, s)
    if best is None:
        print("⚠ 没有到达队长格的出口可 dump")
        return
    hp_end, acts, exit_state = best
    print(f"\n选中 max-HP 出口：{fmt(exit_state)}  动作串长={len(acts)}")
    print("=" * 100)
    print("逐步资源时序（只打印 ATK/DEF/kills/HP 发生变化的步 + 杀队长步）")
    print("=" * 100)

    s = start
    prev_atk, prev_def, prev_kills, prev_hp = s.hero.atk, s.hero.def_, s.hero.kill_count, s.hero.hp
    captain_step = None
    atk_gain_steps, def_gain_steps = [], []
    for i, a in enumerate(acts):
        s = step(s, a)
        h = s.hero
        pos = (h.x, h.y)
        d_atk = h.atk - prev_atk
        d_def = h.def_ - prev_def
        d_kills = h.kill_count - prev_kills
        d_hp = h.hp - prev_hp
        tags = []
        if pos in PRE_GEMS:
            tags.append(PRE_GEMS[pos])
        if pos in POST_BATTLE:
            tags.append(POST_BATTLE[pos])
        # 杀队长：大额掉血或 kills 跳到含队长（这条解 kills 起61→70，队长是最后那只大额掉血）
        is_captain = d_hp <= -100
        if is_captain:
            captain_step = i
            tags.append(f"◆◆杀队长 HP{prev_hp}→{h.hp}({d_hp})")
        if d_atk:
            atk_gain_steps.append((i, pos, d_atk, h.atk))
        if d_def:
            def_gain_steps.append((i, pos, d_def, h.def_))
        if d_atk or d_def or d_kills or is_captain or pos in PRE_GEMS or pos in POST_BATTLE:
            mark = ""
            if d_atk:
                mark += f" ATK+{d_atk}→{h.atk}"
            if d_def:
                mark += f" DEF+{d_def}→{h.def_}"
            if d_kills:
                mark += f" kills+{d_kills}→{h.kill_count}"
            print(f"  step[{i:>3}] {a!s:>6} → ({pos[0]:>2},{pos[1]:>2}) HP={h.hp:>4}"
                  f"{mark}   {' '.join(tags)}")
        prev_atk, prev_def, prev_kills, prev_hp = h.atk, h.def_, h.kill_count, h.hp

    # ── 判读 ──
    print("\n" + "=" * 100)
    print("【判读】")
    print("=" * 100)
    print(f"  杀队长发生在 step[{captain_step}]（大额掉血那步）")
    print(f"  ATK 增点步：{atk_gain_steps}")
    print(f"  DEF 增点步：{def_gain_steps}")

    def verdict(gain_steps, name):
        for i, pos, d, val in gain_steps:
            when = "杀队长【后】" if (captain_step is not None and i > captain_step) else "杀队长【前/中】"
            src = POST_BATTLE.get(pos) or PRE_GEMS.get(pos) or "非宝石格?"
            flag = ""
            if pos in POST_BATTLE and (captain_step is not None and i <= captain_step):
                flag = "  ←★★BUG嫌疑：死后奖励在杀队长前就被吃"
            print(f"    {name}+{d} @ step{i} 格{pos}={src}  时机={when}{flag}")
    verdict(atk_gain_steps, "ATK")
    verdict(def_gain_steps, "DEF")
    print("\n  起点 ATK/DEF=27/27 → 出口 ATK/DEF={}/{}".format(exit_state.hero.atk, exit_state.hero.def_))
    print("  玩家游戏事实：一区(不含boss死后奖励) DEF 上限=27。出口 30 = 多 3 点。")


if __name__ == "__main__":
    main()
