"""
诊断：追踪完整重放 (1318 tokens) 中，英雄每次进入 MT3 的轨迹。
重点：
 1. 几次进入 MT3，每次来自哪层、落点在哪
 2. 每次在 MT3 的移动轨迹（是否经过 yellowDoor(9,11)、greenSlime(7,5)、ambush(5,9)）
 3. 切层事件（走楼梯/fly）的详情

结论写到对话（不写文件），力求定位"英雄为何从未踩到 (5,9)"的根因。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def load_tokens() -> list[str]:
    route_path = next(ROOT.glob("51_*.h5route"))
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    return parse_rle_route(decompress(outer["route"]))


def make_initial_state() -> GameState:
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"],
        y=hero_init["loc"]["y"],
        hp=hero_init["hp"],
        atk=hero_init["atk"],
        def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0),
        gold=hero_init.get("gold", 0),
        keys={},
        items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero,
        floors={"MT1": floor},
        current_floor="MT1",
        floor_ids=FLOOR_IDS,
        visited_floors={"MT1"},
        pending_floor_change=None,
        _floors_dir=FLOORS,
    )


def main():
    tokens = load_tokens()
    state = make_initial_state()

    print(f"总 token 数: {len(tokens)}")
    print()

    # 追踪每个 token 的前后状态
    mt3_visits = []      # 每段在 MT3 停留的记录
    current_mt3_segment = None
    all_floor_changes = []   # 所有切层事件

    for idx, tok in enumerate(tokens):
        fl_before = state.current_floor
        pos_before = (state.hero.x, state.hero.y)
        keys_before = dict(state.hero.keys)
        atk_before = state.hero.atk

        state = step(state, tok)

        fl_after = state.current_floor
        pos_after = (state.hero.x, state.hero.y)
        keys_after = dict(state.hero.keys)
        atk_after = state.hero.atk

        # 记录所有切层
        if fl_before != fl_after or tok.startswith("FLOOR:"):
            all_floor_changes.append({
                "idx": idx,
                "tok": tok,
                "from": fl_before,
                "to": fl_after,
                "pos_before": pos_before,
                "pos_after": pos_after,
                "keys": dict(keys_after),
                "atk": atk_after,
            })

        # 追踪 MT3 期间行为
        if fl_after == "MT3":
            if current_mt3_segment is None:
                current_mt3_segment = {
                    "entry_idx": idx,
                    "entry_tok": tok,
                    "entry_pos": pos_after,
                    "from_floor": fl_before,
                    "steps": [],
                    "visited": set(),
                    "reached_59": False,
                    "reached_7_5": False,
                    "opened_9_11": False,
                }
            current_mt3_segment["visited"].add(pos_after)
            if pos_after == (5, 9):
                current_mt3_segment["reached_59"] = True
            if pos_after == (7, 5):
                current_mt3_segment["reached_7_5"] = True
            # yellowDoor at (9,11) - check if it was opened (hero moved through it)
            if pos_before == (10, 11) and pos_after == (9, 11):
                current_mt3_segment["opened_9_11"] = True
            if pos_before == (8, 11) and pos_after == (9, 11):
                current_mt3_segment["opened_9_11"] = True
            if (pos_before[0] in (8, 10) and pos_after == (9, 11)):
                current_mt3_segment["opened_9_11"] = True

            current_mt3_segment["steps"].append({
                "idx": idx,
                "tok": tok,
                "pos_before": pos_before,
                "pos_after": pos_after,
                "keys": dict(keys_after),
                "atk": atk_after,
            })

        elif fl_before == "MT3" and fl_after != "MT3":
            # 离开 MT3
            if current_mt3_segment is not None:
                current_mt3_segment["exit_idx"] = idx
                current_mt3_segment["exit_tok"] = tok
                current_mt3_segment["exit_pos"] = pos_after
                current_mt3_segment["exit_floor"] = fl_after
                current_mt3_segment["exit_keys"] = dict(keys_after)
                mt3_visits.append(current_mt3_segment)
                current_mt3_segment = None

    # 结束时还在 MT3？
    if current_mt3_segment is not None:
        current_mt3_segment["exit_idx"] = len(tokens) - 1
        current_mt3_segment["exit_tok"] = "(end)"
        current_mt3_segment["exit_floor"] = state.current_floor
        current_mt3_segment["exit_pos"] = (state.hero.x, state.hero.y)
        current_mt3_segment["exit_keys"] = dict(state.hero.keys)
        mt3_visits.append(current_mt3_segment)

    # ── 输出切层摘要 ────────────────────────────────────────────────────────────
    print("=== 所有切层事件（含 FLOOR: tokens）===")
    for e in all_floor_changes:
        print(f"  [{e['idx']:>4}] {e['tok']:<12} {e['from']!r:>6} → {e['to']!r:<6}  "
              f"pos_after={e['pos_after']}  keys={e['keys']}  atk={e['atk']}")

    # ── 输出 MT3 各次停留 ───────────────────────────────────────────────────────
    print(f"\n=== MT3 共 {len(mt3_visits)} 次停留 ===")
    for i, seg in enumerate(mt3_visits):
        n = len(seg["steps"])
        print(f"\n--- MT3 第{i+1}次停留 ---")
        print(f"  进入: token[{seg['entry_idx']}] {seg['entry_tok']!r}  "
              f"来自={seg['from_floor']!r}  落点={seg['entry_pos']}")
        print(f"  离开: token[{seg['exit_idx']}] {seg['exit_tok']!r}  "
              f"去往={seg['exit_floor']!r}  落点={seg['exit_pos']}")
        print(f"  步数: {n}  到达(5,9): {seg['reached_59']}  "
              f"到达(7,5): {seg['reached_7_5']}  开(9,11)门: {seg['opened_9_11']}")
        print(f"  离开时钥匙: {seg['exit_keys']}")

        # 打印所有步骤
        print(f"  步骤（全量）:")
        for s in seg["steps"]:
            moved = s["pos_before"] != s["pos_after"]
            marker = ""
            if s["pos_after"] == (5, 9):
                marker = " ★ AMBUSH"
            elif s["pos_after"] == (7, 5):
                marker = " ← greenSlime"
            elif s["pos_after"] == (9, 11):
                marker = " ← yellowDoor opened"
            elif s["pos_before"] == (9, 11) and not moved:
                marker = " ← hit yellowDoor (blocked?)"
            label = "MOVE" if moved else "WALL/NPC"
            print(f"    [{s['idx']:>4}] {s['tok']:<6}  {s['pos_before']} → {s['pos_after']}  "
                  f"{label}  keys={s['keys']}{marker}")

    # ── 关键状态检查 ────────────────────────────────────────────────────────────
    print("\n=== 关键检查 ===")
    # 找英雄最后一次 ATK 变化
    state2 = make_initial_state()
    last_atk_change = None
    for idx, tok in enumerate(tokens):
        atk_before = state2.hero.atk
        state2 = step(state2, tok)
        if state2.hero.atk != atk_before:
            last_atk_change = (idx, tok, atk_before, state2.hero.atk, state2.current_floor, (state2.hero.x, state2.hero.y))
    if last_atk_change:
        print(f"  最后一次 ATK 变化: token[{last_atk_change[0]}] {last_atk_change[1]!r}  "
              f"{last_atk_change[2]} → {last_atk_change[3]}  "
              f"floor={last_atk_change[4]}  pos={last_atk_change[5]}")
    else:
        print("  ATK 全程未变化")

    print(f"\n  最终状态: floor={state.current_floor}  pos=({state.hero.x},{state.hero.y})  "
          f"hp={state.hero.hp}  atk={state.hero.atk}  def={state.hero.def_}")


if __name__ == "__main__":
    main()
