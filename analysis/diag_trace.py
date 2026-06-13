"""
逐 token 轨迹追踪，标签与 pytest test_checkpoints.py 对齐：
  tok[i] = 执行完 tokens[:i] 之后的状态（即 pytest checkpoint i 检查的状态）
  每行打印：执行前的状态 + 即将执行的 token + 执行后的变化

用法：
  python diag_trace.py <START> <END>
  例：python diag_trace.py 480 502
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step, _copy_state

DATA = Path("data/games51")
FLOORS = DATA / "floors"

START = int(sys.argv[1]) if len(sys.argv) > 1 else 190
END   = int(sys.argv[2]) if len(sys.argv) > 2 else 210


def build_initial_state():
    floor_ids = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
        hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0), gold=hero_init.get("gold", 0),
        keys={}, items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero, floors={"MT1": floor}, current_floor="MT1",
        floor_ids=floor_ids, visited_floors={"MT1"},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def load_tokens():
    route_path = next(Path(".").glob("51_*.h5route"), None)
    if route_path is None:
        print("错误：找不到 51_*.h5route"); sys.exit(1)
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def main():
    tokens = load_tokens()
    state = build_initial_state()

    # 快进到 START（state 此时 = tokens[:START] 之后的状态 = pytest tok[START]）
    for i in range(START):
        state = step(state, tokens[i])

    print(f"# tok[i] = tokens[:i] 之后的状态（与 pytest checkpoint 口径一致）")
    print(f"{'tok':>6}  {'next_tok':<6} {'floor':<5} {'pos':>7}  {'HP':>5} {'ATK':>3} {'DEF':>3} {'yk':>3} {'bk':>3}  变化")
    print("-" * 85)

    for i in range(START, min(END + 1, len(tokens))):
        h = state.hero
        yk = h.keys.get("yellowKey", 0)
        bk = h.keys.get("blueKey", 0)

        # 即将执行的 token
        tok = tokens[i] if i < len(tokens) else "—"

        # 执行 token，记录变化
        if i < len(tokens):
            prev = _copy_state(state)
            state = step(state, tok)
            ph = prev.hero
            pyk = ph.keys.get("yellowKey", 0)
            pbk = ph.keys.get("blueKey", 0)
            nh = state.hero
            nyk = nh.keys.get("yellowKey", 0)
            nbk = nh.keys.get("blueKey", 0)

            notes = []
            floor_same = prev.current_floor == state.current_floor
            pos_same   = ph.x == nh.x and ph.y == nh.y

            if tok in ("U", "D", "L", "R"):
                if floor_same and pos_same:
                    notes.append("→BLOCKED")
                elif not floor_same:
                    notes.append(f"→{state.current_floor}")

            if nh.hp  != ph.hp:   notes.append(f"HP Δ{nh.hp - ph.hp:+d}")
            if nh.atk != ph.atk:  notes.append(f"ATK Δ{nh.atk - ph.atk:+d}")
            if nh.def_!= ph.def_: notes.append(f"DEF Δ{nh.def_ - ph.def_:+d}")
            if nyk != pyk: notes.append(f"yk {pyk}→{nyk}")
            if nbk != pbk: notes.append(f"bk {pbk}→{nbk}")
            change = "  ".join(notes)
        else:
            change = "(end)"

        print(f"tok[{i:>3}]  {tok:<6} {prev.current_floor:<5} ({h.x:2},{h.y:2})  {h.hp:>5} {h.atk:>3} {h.def_:>3} {yk:>3} {bk:>3}  {change}")


if __name__ == "__main__":
    main()
