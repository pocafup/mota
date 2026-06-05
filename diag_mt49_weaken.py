"""只读诊断：MT49 竞技场削弱链。
回放 route 到 tok5808..5835 区间，每步后打印：英雄位置/击杀数、autoEvent[1,1] 的 8 个 getBlockId
子句各自真假（用真实 _eval_single 求值，验证 BUG#1 修复）、autoEvent 整体条件、redKing 有效属性
(via _build_monster，验证 BUG#2 的 /=10)。不改任何产品代码/真值/断言。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step, _eval_single, _eval_condition, _build_monster

# MT49 autoEvent[1,1] 的 8 个子句（来自 data/games51/floors/MT49.json autoEvent.1,1.0.condition）
CLAUSES = [
    "core.getBlockId(5,2) === 'whiteKing'",
    "core.getBlockId(6,2) === null",
    "core.getBlockId(7,2) === 'whiteKing'",
    "core.getBlockId(5,3) === null",
    "core.getBlockId(7,3) === null",
    "core.getBlockId(5,4) === 'whiteKing'",
    "core.getBlockId(6,4) === null",
    "core.getBlockId(7,4) === 'whiteKing'",
]
FULL_COND = " && ".join(CLAUSES)

LO, HI = 5808, 5835


def redking_stats(state):
    db = state.floor._monsters_db
    if "redKing" not in db:
        return "redKing 不在本层 monsters_db"
    m = _build_monster(state, "redKing")
    ov = state._enemy_overrides.get("redKing", {})
    return f"redKing 有效 hp={m.hp} atk={m.atk} def={m.def_}  override={ov or '无'}"


def entity_at(state, x, y):
    e = state.floor.entities[y][x]
    return state.floor._tile_to_entity.get(e, f"(空/非实体 tile={e})")


def main():
    tokens = load_tokens()
    state = build_initial_state()
    print(f"route 总 token 数: {len(tokens)}")
    for idx, tok in enumerate(tokens[:HI + 1]):
        state = step(state, tok)
        if idx < LO:
            continue
        h = state.hero
        print(f"\n── tok[{idx}] {tok}  | {state.current_floor}({h.x},{h.y}) "
              f"HP={h.hp} ATK={h.atk} DEF={h.def_} k={h.kill_count}")
        if state.current_floor != "MT49":
            continue
        # 8 子句逐一求值（真实 _eval_single）+ 该格实体
        truths = []
        for cl in CLAUSES:
            t = _eval_single(cl, state)
            truths.append(t)
            # 解析坐标用于打印实体
            import re
            mm = re.search(r"\((\d+),\s*(\d+)\)", cl)
            cx, cy = int(mm.group(1)), int(mm.group(2))
            print(f"     [{'T' if t else 'F'}] {cl:<42} 实际格({cx},{cy})={entity_at(state, cx, cy)}")
        cond = _eval_condition(FULL_COND, state)
        print(f"     >>> autoEvent 整体条件 = {cond}  (8 子句: {sum(truths)}/8 True)")
        print(f"     >>> {redking_stats(state)}")


if __name__ == "__main__":
    main()
