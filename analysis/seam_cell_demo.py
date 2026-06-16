"""【§S32 一锤定音·只读】证明 seam=(MT10,1,11) 是【结构不可达目标格】，正确落点是 (MT10,1,10)。

数据真相(已读 JSON)：
  MT9.changeFloor "1,11" → :next(MT10) stair=downFloor ⟹ 踩 MT9(1,11) 落到 MT10.downFloor=(1,10)。
  MT10.changeFloor "1,11" → :before(MT9) stair=upFloor ⟹ MT10(1,11) 是【下楼回 MT9】的楼梯格，
    踩它落到 MT9.upFloor=(1,10)。
引擎真相：(1,11) 是 changeFloor 格→_is_free_tile 判非自由→floodfill 不收；且没有任何楼梯落点
  把英雄放到 (1,11)；走上去就换层弹走。故 goal=(MT10,1,11) 的 in-free 判据【永不成立】。

本脚本拿【最强 MT9 回访态】(属性碾压·可达性=纯结构、与血无关) 直接对照两个 goal：
  navigate_to(state,(MT10,1,10))  期望 reached=True，落点 (1,10)
  navigate_to(state,(MT10,1,11))  期望 reached=False(结构不可达)
强态→快；这测的是【目标格能不能站上】，与 A*/穷尽/血量都无关。只读。
用法：python -u analysis/seam_cell_demo.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.verify_all_checkpoints import build_initial_state, load_tokens  # noqa: E402
from sim.simulator import step                                                # noqa: E402
from ga_navigate import navigate_to                                           # noqa: E402
from vzone import build_zone                                                  # noqa: E402


def strongest_mt9():
    s = build_initial_state()
    best = None
    for tok in load_tokens():
        s = step(s, tok)
        if s.current_floor == "MT9":
            key = (s.hero.def_, s.hero.atk, s.hero.hp)
            if best is None or key > best[0]:
                best = (key, s)
    return best[1] if best else None


def main():
    zone = build_zone()
    st = strongest_mt9()
    h = st.hero
    print(f"起点(最强 MT9 回访)：MT9({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_}")
    print("（属性碾压→可达性纯结构，排除『血不够』混淆）\n")

    for goal in (("MT10", 1, 10), ("MT10", 1, 11)):
        fs, moves, reached = navigate_to(st, goal, zone, step, max_pops=20000, cache=None)
        landing = f"{fs.current_floor}({fs.hero.x},{fs.hero.y})" if reached else "—"
        print(f"navigate_to {goal}: reached={reached}  步数={len(moves)}  落点={landing}")

    print("\n结论：(MT10,1,10) 可达=真 seam 落点；(MT10,1,11) reached=False=结构不可达楼梯格。")


if __name__ == "__main__":
    main()
