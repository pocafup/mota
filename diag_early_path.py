"""
诊断脚本：逐格追踪 decoded[0..99]，找英雄在 MT1 早期走偏/卡死的分叉点。
输出全量轨迹到 data/games51/early_path_trace.txt，对话只报告关键转折点。

预期路径：MT1(6,11) → 捡钥匙(5,10) → 开门(6,9) → row8 → column11 → row1 → MT1(1,1)楼梯 → MT2 → MT3(5,9)伏击
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA   = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def load_all_tokens() -> list[str]:
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


def classify(tok, floor_before, pos_before, state_after, floor_after, pos_after) -> str:
    """返回这一步发生了什么的分类标签。"""
    if tok.startswith("FLOOR:"):
        return f"FLY→{tok[6:]}"
    if tok.startswith("CHOICE:"):
        return "CHOICE"
    if tok.startswith("ITEM:"):
        return "ITEM"
    if floor_before != floor_after:
        return f"STAIR→{floor_after}"
    if pos_before == pos_after:
        if floor_before == floor_after:
            return "WALL/NPC"
        return "NOOP"
    # 位置变化了
    h = state_after.hero
    return f"MOVE hp={h.hp} atk={h.atk} def={h.def_} keys={dict(h.keys)}"


def main():
    all_tokens = load_all_tokens()
    tokens = all_tokens[:100]  # 只看前100个

    state = make_initial_state()
    rows = []
    prev_floor = state.current_floor
    prev_pos = (state.hero.x, state.hero.y)
    prev_hp = state.hero.hp
    prev_keys = dict(state.hero.keys)

    for idx, tok in enumerate(tokens):
        fl_before = state.current_floor
        pos_before = (state.hero.x, state.hero.y)
        hp_before = state.hero.hp
        keys_before = dict(state.hero.keys)

        state = step(state, tok)

        fl_after = state.current_floor
        pos_after = (state.hero.x, state.hero.y)
        hp_after = state.hero.hp
        keys_after = dict(state.hero.keys)

        moved = pos_before != pos_after
        floor_changed = fl_before != fl_after
        hp_changed = hp_before != hp_after
        keys_changed = keys_before != keys_after

        label = classify(tok, fl_before, pos_before, state, fl_after, pos_after)

        rows.append({
            "idx": idx,
            "tok": tok,
            "floor": fl_after,
            "pos_before": pos_before,
            "pos_after": pos_after,
            "moved": moved,
            "floor_changed": floor_changed,
            "hp": hp_after,
            "atk": state.hero.atk,
            "def_": state.hero.def_,
            "keys": dict(keys_after),
            "label": label,
        })

    # ── 写全量轨迹 ──────────────────────────────────────────────────────────────
    out_path = DATA / "early_path_trace.txt"
    lines = ["# MT1 早期路径诊断（decoded[0..99]）",
             f"{'idx':>4}  {'tok':<14}  {'floor':<6}  {'before':>8}  {'after':>8}  {'hp':>5}  {'atk':>4}  {'def':>4}  {'keys':<30}  label",
             "-" * 120]
    for r in rows:
        lines.append(
            f"{r['idx']:>4}  {r['tok']:<14}  {r['floor']:<6}  "
            f"({r['pos_before'][0]},{r['pos_before'][1]})"
            f"  ({r['pos_after'][0]},{r['pos_after'][1]})"
            f"  {r['hp']:>5}  {r['atk']:>4}  {r['def_']:>4}  "
            f"{str(r['keys']):<30}  {r['label']}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] 全量轨迹写入: {out_path}")

    # ── 关键转折点摘要 ─────────────────────────────────────────────────────────
    print("\n=== 关键转折点（位置变化、楼层变化、HP变化、钥匙变化）===")
    prev_pos2 = (6, 11)
    prev_fl2 = "MT1"
    prev_keys2 = {}
    consec_walls = 0
    first_wall_run_start = None

    for r in rows:
        is_wall = r["label"] == "WALL/NPC" and r["tok"] in ("U", "D", "L", "R")
        if is_wall:
            if consec_walls == 0:
                first_wall_run_start = r["idx"]
            consec_walls += 1
        else:
            if consec_walls >= 3:
                print(f"  [卡住] token[{first_wall_run_start}..{r['idx']-1}] 连续{consec_walls}步撞墙，"
                      f"位置停在 {r['pos_before']}，楼层={r['floor']}")
            consec_walls = 0
            first_wall_run_start = None

        if r["floor_changed"]:
            print(f"  [切层] token[{r['idx']}] {r['tok']}  {prev_fl2} → {r['floor']}  "
                  f"落点={r['pos_after']}")
            prev_fl2 = r["floor"]
        elif r["moved"]:
            if r["pos_before"] != prev_pos2 or r["tok"].startswith("FLOOR:"):
                pass  # 只报关键节点
            prev_pos2 = r["pos_after"]

        if r["keys"] != prev_keys2:
            gained = {k: r["keys"].get(k, 0) - prev_keys2.get(k, 0)
                      for k in set(r["keys"]) | set(prev_keys2) if r["keys"].get(k, 0) != prev_keys2.get(k, 0)}
            print(f"  [钥匙] token[{r['idx']}] {r['tok']:<10}  {prev_keys2} → {r['keys']}  变化={gained}")
            prev_keys2 = dict(r["keys"])

        if r["floor_changed"] or r["label"].startswith("FLY"):
            prev_fl2 = r["floor"]

    # 末尾未结束的连续撞墙
    if consec_walls >= 3:
        print(f"  [卡住] token[{first_wall_run_start}..99] 连续{consec_walls}步撞墙，"
              f"位置停在 {rows[-1]['pos_after']}，楼层={rows[-1]['floor']}")

    print("\n=== 结束状态 ===")
    last = rows[-1]
    print(f"  token[99]={last['tok']}  floor={last['floor']}  pos={last['pos_after']}")
    print(f"  HP={last['hp']} ATK={last['atk']} DEF={last['def_']}  keys={last['keys']}")

    # ── 连续撞墙详情（逐步列出） ────────────────────────────────────────────────
    print("\n=== 所有 WALL/NPC 步骤位置 ===")
    for r in rows:
        if r["label"] == "WALL/NPC" and r["tok"] in ("U", "D", "L", "R"):
            print(f"  [{r['idx']:>3}] {r['tok']}  at {r['pos_before']} floor={r['floor']}")


if __name__ == "__main__":
    main()
