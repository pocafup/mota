"""
诊断脚本：输出 MT10 Visit 4 逐 token 轨迹，标注 changeFloor 冻结点。
基于含拦截型事件机制的当前实现（intercepting events + keep fix + changeFloor freeze）。
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

    trajectory = []

    for idx, tok in enumerate(tokens):
        prev_x, prev_y = state.hero.x, state.hero.y
        prev_e611 = state.floor.entities[11][6]
        state = step(state, tok)
        after_x, after_y = state.hero.x, state.hero.y

        moved = (prev_x != after_x or prev_y != after_y)
        trajectory.append({
            "idx": idx,
            "token": tok,
            "from": (prev_x, prev_y),
            "to": (after_x, after_y),
            "moved": moved,
            "exited": state.floor._exited,
            "entities_611": state.floor.entities[11][6],
            "terrain_611": state.floor.terrain[11][6],
        })

    freeze_at = next((r["idx"] for r in trajectory if r["exited"]), None)

    # ── 写全量轨迹到文件 ──────────────────────────────────────────────────────
    out_path = DATA / "mt10_trajectory_diag.txt"
    lines = []
    lines.append("# 基于含拦截型事件机制的当前实现（intercepting events + keep fix + changeFloor freeze）")
    lines.append(f"Total tokens: {len(tokens)}")
    lines.append(f"freeze_at (token idx): {freeze_at}")
    lines.append("")
    lines.append(f"{'idx':>4}  {'tok':<12}  {'from':>8}  {'to':>8}  {'moved':>5}  {'e[11][6]':>8}  {'t[11][6]':>8}  {'frozen':>6}")
    lines.append("-" * 80)
    for r in trajectory:
        lines.append(
            f"{r['idx']:>4}  {r['token']:<12}  "
            f"({r['from'][0]},{r['from'][1]})"
            f"  ({r['to'][0]},{r['to'][1]})"
            f"  {'Y' if r['moved'] else '-':>5}"
            f"  {r['entities_611']:>8}"
            f"  {r['terrain_611']:>8}"
            f"  {'FROZEN' if r['exited'] else '':>6}"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Trajectory written to: {out_path}")

    # ── 关键摘要输出到 stdout ──────────────────────────────────────────────────
    print(f"\n=== KEY FINDINGS ===")
    print(f"total tokens: {len(tokens)}")
    print(f"freeze_at token[{freeze_at}]  tok={tokens[freeze_at] if freeze_at is not None else 'N/A'}")

    if freeze_at is not None:
        r = trajectory[freeze_at]
        print(f"  hero moved: {r['from']} → {r['to']}")
        print(f"  entities[11][6] AT freeze: {r['entities_611']}")
        print(f"  terrain[11][6]  AT freeze: {r['terrain_611']}")

    # entities[11][6] の変化を記録
    print("\nentities[11][6] changes:")
    prev_val = None
    for r in trajectory:
        if r["entities_611"] != prev_val:
            print(f"  token[{r['idx']:3d}] {r['token']:<12} → entities[11][6] = {r['entities_611']}")
            prev_val = r["entities_611"]

    # token[79:85] の詳細
    print("\nTokens [75..90] detail:")
    for r in trajectory[75:91]:
        print(
            f"  [{r['idx']:3d}] {r['token']:<12}  "
            f"{r['from']} → {r['to']}"
            f"  e[11][6]={r['entities_611']}"
            f"  {'FROZEN' if r['exited'] else ''}"
        )

    # 最後10個のtoken
    print(f"\nLast 10 tokens (around real exit at token[147]):")
    for r in trajectory[-10:]:
        print(
            f"  [{r['idx']:3d}] {r['token']:<12}  "
            f"{r['from']} → {r['to']}"
            f"  {'FROZEN' if r['exited'] else ''}"
        )


if __name__ == "__main__":
    main()
