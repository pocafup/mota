"""【只读诊断·不入产品链】navigate_to 动态顺路吸实测 —— 验证静态零损血口径判的"剑/盾顺路性"是否吻合实际。

只读：只调 navigate_to(封板件)看它从 start 实际跑出来吸了谁，绝不改任何文件、不碰基因池、不跑 GA 进化。
动机：ga_pool_triage_diag.py 用 detect_key_targets 的【静态·单层·最弱 ref_state·楼梯多源】零损血口径，
判出『剑=需决策、盾=顺路』，与玩家游戏知识(剑顺路/盾需决策)相反。本脚本用【动态·跨层·运行时属性】的
真 navigate_to 实测：从 start 定向走向各目标，看终态里剑格 MT5(11,11) / 盾格 MT9(9,7) 是否被顺路吸走。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start    # noqa: E402
from vzone import build_zone                # noqa: E402
from ga_navigate import navigate_to         # noqa: E402
from sim.simulator import step              # noqa: E402

SWORD = ("MT5", 11, 11)
SHIELD = ("MT9", 9, 7)


def _taken(state, cell):
    fid, x, y = cell
    fl = state.floors.get(fid)
    return fl is not None and fl.entities[y][x] == 0


def main():
    start, _ = build_start()
    zone = build_zone()
    h0 = start.hero
    print(f"start: {start.current_floor}({h0.x},{h0.y}) HP={h0.hp} ATK={h0.atk} DEF={h0.def_}")
    print(f"剑格 {SWORD}  盾格 {SHIELD}\n")

    targets = [
        ("剑 MT5(11,11)", SWORD),
        ("盾 MT9(9,7)", SHIELD),
        ("宝石 MT9(6,5)·静态判顺路·同盾层", ("MT9", 6, 5)),
        ("宝石 MT1(7,3)·静态判需决策·浅", ("MT1", 7, 3)),
    ]
    header = f"{'导航目标':<28} reached steps  剑被吸  盾被吸   终态 ATK/DEF/HP"
    print(header)
    print("-" * len(header))
    for label, goal in targets:
        final, moves, reached = navigate_to(start, goal, zone, step, cache=None)
        if reached:
            fh = final.hero
            sw = "★是" if _taken(final, SWORD) else " 否"
            sh = "★是" if _taken(final, SHIELD) else " 否"
            print(f"{label:<28} {'是':<6} {len(moves):>4}   {sw:<5} {sh:<5}   "
                  f"{fh.atk}/{fh.def_}/{fh.hp}")
        else:
            print(f"{label:<28} {'否':<6}   —     —     —      （够不到，原子失败）")


if __name__ == "__main__":
    main()
