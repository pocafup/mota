"""
MT10 出口轨迹复核：聚焦 events["6,9"] 触发、小偷离场、(6,11) 通行时间点。
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from sim.simulator import GameState, HeroState, FloorState, step, load_floor

DATA   = ROOT / "data" / "games51"
FLOORS = DATA / "floors"


def make_initial_state() -> GameState:
    floor = load_floor(FLOORS / "MT10.json")
    hero = HeroState(
        x=1, y=10,
        hp=1000, atk=100, def_=100, mdef=0,
        gold=0,
        keys={"yellowKey": 10, "blueKey": 3, "redKey": 3},
        items={},
        flags={"魔法免疫": True},
    )
    return GameState(hero=hero, floor=floor)


def load_tokens() -> list:
    trace = json.loads((DATA / "mt10_route_trace.json").read_text(encoding="utf-8"))
    return [t["token"] for t in trace["tokens"]]


def main():
    tokens = load_tokens()
    state = make_initial_state()

    lines = []
    lines.append(f"Total tokens: {len(tokens)}")
    lines.append("")
    lines.append(f"{'idx':>4}  {'tok':<12}  {'from':>8}  {'to':>8}  {'moved':>5}  {'e[11][6]':>8}  note")
    lines.append("-" * 75)

    prev_e611 = 0
    for idx, tok in enumerate(tokens):
        prev_x, prev_y = state.hero.x, state.hero.y
        prev_e = state.floor.entities[11][6]
        state = step(state, tok)
        after_x, after_y = state.hero.x, state.hero.y
        after_e = state.floor.entities[11][6]

        moved = (prev_x != after_x or prev_y != after_y)

        # 标注关键事件
        notes = []
        if prev_e != after_e:
            notes.append(f"e[11][6]: {prev_e}→{after_e}")
        if after_x == 6 and after_y == 11 and (prev_x != 6 or prev_y != 11):
            notes.append("*** 英雄首次抵达(6,11) ***")
        if prev_x == 6 and prev_y == 11 and (after_x != 6 or after_y != 11):
            notes.append("*** 英雄离开(6,11) ***")
        if tok not in ("U","D","L","R") and tok.startswith("CHOICE"):
            notes.append("CHOICE token")

        line = (
            f"{idx:>4}  {tok:<12}  "
            f"({prev_x},{prev_y})"
            f"  ({after_x},{after_y})"
            f"  {'Y' if moved else '-':>5}"
            f"  {after_e:>8}"
        )
        if notes:
            line += "  " + "; ".join(notes)
        lines.append(line)

    lines.append("")
    lines.append("=== 关键摘要 ===")
    lines.append(f"final hero pos: ({state.hero.x},{state.hero.y})")
    lines.append(f"final e[11][6]: {state.floor.entities[11][6]}")
    lines.append(f"suppressed_events: {state.floor._suppressed_events}")

    # 检查用户期望的三个条件
    lines.append("")
    lines.append("=== 轨迹复核 ===")

    # 重跑找关键 token
    state2 = make_initial_state()
    e611_at_81 = None
    hero_at_81 = None
    first_arrive_611 = None
    for idx, tok in enumerate(tokens):
        prev_x2, prev_y2 = state2.hero.x, state2.hero.y
        state2 = step(state2, tok)
        if idx == 81:
            e611_at_81 = state2.floor.entities[11][6]
            hero_at_81 = (state2.hero.x, state2.hero.y)
        if first_arrive_611 is None and state2.hero.x == 6 and state2.hero.y == 11:
            first_arrive_611 = idx
    lines.append(f"token[81] 时 e[11][6]={e611_at_81}，hero={hero_at_81}")
    lines.append(f"  (6,11) 被小偷挡住: {'是' if e611_at_81 == 123 else '否（thief=' + str(e611_at_81) + '）'}")
    lines.append(f"英雄首次抵达(6,11): token[{first_arrive_611}]")
    lines.append(f"期望: token[147] D 踏上(6,11) → 实际最后一步: token[{len(tokens)-1}]={tokens[-1]}, 终点=({state2.hero.x},{state2.hero.y})")
    lines.append(f"路线对齐: {'✓ 匹配' if state2.hero.x == 6 and state2.hero.y == 11 and first_arrive_611 == len(tokens)-1 else '✗ 不匹配'}")

    out_path = DATA / "mt10_exit_diag.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written: {out_path}")

    # 只打印关键摘要到 stdout
    for line in lines[-10:]:
        print(line)


if __name__ == "__main__":
    main()
