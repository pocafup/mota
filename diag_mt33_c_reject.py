"""只读裁判：把【修复前】C段支配点#1 的旧动作序列（曾宣称 HP=586 到 MT33(10,1)）丢回
【修复后】的引擎独立重放，逐帧定位——证明它现已【走不通】（防回头墙封死后无法回头穿 (8,10)）。

旧 #1 序列来源：mvp_c_out.txt（修复前 C 段输出）支配点#1（80 步）。
旧宣称终态：@MT33(10,1) HP=586 ATK=154 DEF=70 金=671 kill=181 keys{yellowKey:3}。

本探针不进搜索、不改产品代码——纯独立重放，用运行结果判定（不靠手推）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import step

ENTRY_TOKEN = 2894
GOAL = ("MT33", 10, 1)
OLD_1_SEQ = "LLLLDDLDDRRDDLLLLLLDDRRDDRRRRURRRUUUULUDRDDDDLLLDLLLLUULLDDUUUURRRUURUUUULRRRRRR"
CLAIMED = dict(floor="MT33", x=10, y=1, hp=586, atk=154, def_=70, gold=671, kill=181)


def main():
    tokens = load_tokens()
    state = build_initial_state()
    for tok in tokens[:ENTRY_TOKEN]:
        state = step(state, tok)
    h = state.hero
    print(f"入口(tokens[:{ENTRY_TOKEN}]): {state.current_floor}({h.x},{h.y}) "
          f"HP={h.hp} ATK={h.atk} DEF={h.def_} 金={h.gold} kill={h.kill_count} "
          f"keys={dict(h.keys)}")
    print(f"旧 #1 序列（{len(OLD_1_SEQ)} 步）: {OLD_1_SEQ}")
    print(f"旧宣称终态: @MT33(10,1) HP=586 ATK=154 DEF=70 金=671 kill=181 keys[yellowKey=3]\n")

    blocked = []      # 撞墙原地不动的步（封格后回头被拒会出现在这里）
    crossed_810 = []  # 站上 (8,10) 的步
    seal_step = None  # (8,10) 被封成墙(tile!=168)的首帧
    for i, mv in enumerate(OLD_1_SEQ):
        bx, by = state.hero.x, state.hero.y
        prev_810 = state.floors["MT33"].terrain[10][8]
        state = step(state, mv)
        ax, ay = state.hero.x, state.hero.y
        now_810 = state.floors["MT33"].terrain[10][8]
        if (ax, ay) == (8, 10):
            crossed_810.append(i)
        if prev_810 == 168 and now_810 != 168 and seal_step is None:
            seal_step = (i, now_810)
        if (ax, ay) == (bx, by):
            # 原地不动：尝试穿墙/无效动作。重点抓「目标格是 (8,10) 且已封」的回头拒。
            tx, ty = {"U": (bx, by - 1), "D": (bx, by + 1),
                      "L": (bx - 1, by), "R": (bx + 1, by)}[mv]
            blocked.append((i, mv, (bx, by), (tx, ty),
                            state.floors["MT33"].terrain[ty][tx]
                            if state.current_floor == "MT33"
                            and 0 <= ty < 13 and 0 <= tx < 13 else None))

    f = state.current_floor
    h = state.hero
    reached = (f == GOAL[0] and h.x == GOAL[1] and h.y == GOAL[2])
    match = (reached and h.hp == CLAIMED["hp"] and h.atk == CLAIMED["atk"]
             and h.def_ == CLAIMED["def_"] and h.gold == CLAIMED["gold"]
             and h.kill_count == CLAIMED["kill"])

    print("=== 修复后独立重放结果 ===")
    print(f"  踏上 (8,10) 的步: {crossed_810 or '从未'}")
    if seal_step:
        print(f"  (8,10) 被封成墙(terrain {seal_step[1]}) 于 第{seal_step[0]}步 离开后")
    else:
        print(f"  (8,10) 全程未被封（该路径未左→右穿越 flower）")
    print(f"  撞墙原地不动的步: {len(blocked)} 处")
    for (i, mv, frm, tgt, tt) in blocked:
        tag = "  <<< 回头穿已封 (8,10) 被拒" if tgt == (8, 10) else ""
        print(f"      第{i:>2}步 '{mv}' 在{frm} 撞 目标{tgt}(terrain={tt}){tag}")
    print(f"\n  最终落点: {f}({h.x},{h.y})  "
          f"HP={h.hp} ATK={h.atk} DEF={h.def_} 金={h.gold} kill={h.kill_count} "
          f"keys={dict(h.keys)} dead={state.dead}")
    print(f"  到达目标格 {GOAL}? {'是' if reached else '否'}")
    print(f"  与旧宣称终态一致? {'是' if match else '否'}")
    print("\n" + "=" * 60)
    if match:
        print("[未拒] 旧 #1 仍走得通且终态吻合——修复无效，需复查！")
    else:
        print("[已拒] 旧 #1 在修复后引擎中走不通（防回头墙生效）。假赢路线被裁判否决。")
    print("=" * 60)


if __name__ == "__main__":
    main()
