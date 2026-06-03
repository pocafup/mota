"""
验收脚本：验证 NPC 可通行性修复后，重放路线能正确走到 MT3(5,9) 伏击格。

检查点：
  1. decoded[7]  R from MT1(6,10) → 落点应为 (7,10)（踩上作者NPC）
  2. decoded[69] 后，英雄应在 MT3(5,9) 触发伏击，HP=400 ATK=10 DEF=10，传送 MT2(3,8)
  3. 完整轨迹写 data/games51/verify_npc_trace.txt
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

    VERIFY_UP_TO = 80  # 前80个 token 全量打印
    rows = []
    passes = []
    fails = []

    for idx, tok in enumerate(tokens[:80]):
        fl_before = state.current_floor
        pos_before = (state.hero.x, state.hero.y)
        hp_before = state.hero.hp
        atk_before = state.hero.atk
        def_before = state.hero.def_

        state = step(state, tok)

        fl_after = state.current_floor
        pos_after = (state.hero.x, state.hero.y)
        moved = pos_before != pos_after or fl_before != fl_after
        label = "MOVE" if (pos_before != pos_after) else ("FLY/STAIR" if fl_before != fl_after else "WALL/NPC")

        rows.append({
            "idx": idx, "tok": tok,
            "floor": fl_after, "pos_before": pos_before, "pos_after": pos_after,
            "hp": state.hero.hp, "atk": state.hero.atk, "def_": state.hero.def_,
            "keys": dict(state.hero.keys),
            "label": label,
        })

    # ── 检查点 1：decoded[7] 落点 ──────────────────────────────────────────────
    r7 = rows[7]
    expected_pos7 = (7, 10)
    if r7["pos_after"] == expected_pos7 and r7["floor"] == "MT1":
        passes.append(f"[PASS] decoded[7]: {r7['tok']} MT1{r7['pos_before']}→{r7['pos_after']} (踩入作者NPC)")
    else:
        fails.append(f"[FAIL] decoded[7]: 期望 MT1(7,10)，实际 {r7['floor']}{r7['pos_after']}")

    # ── 继续跑到 decoded[69] ───────────────────────────────────────────────────
    for idx, tok in enumerate(tokens[80:], start=80):
        if idx > 75:
            pass
        fl_before = state.current_floor
        pos_before = (state.hero.x, state.hero.y)

        state = step(state, tok)

        fl_after = state.current_floor
        pos_after = (state.hero.x, state.hero.y)
        moved = pos_before != pos_after or fl_before != fl_after
        label = "MOVE" if (pos_before != pos_after) else ("FLY/STAIR" if fl_before != fl_after else "WALL/NPC")
        rows.append({
            "idx": idx, "tok": tok,
            "floor": fl_after, "pos_before": pos_before, "pos_after": pos_after,
            "hp": state.hero.hp, "atk": state.hero.atk, "def_": state.hero.def_,
            "keys": dict(state.hero.keys),
            "label": label,
        })

        if idx >= 75:
            break

    # ── 检查点 2：decoded[69] 后伏击状态 ─────────────────────────────────────
    r69 = rows[69]
    # 伏击在 MT3(5,9) 触发后立即传送，所以 decoded[69] 后英雄应在 MT2(3,8)
    ambush_hp = 400
    ambush_atk = 10
    ambush_def = 10
    ambush_floor = "MT2"
    ambush_pos = (3, 8)

    if r69["hp"] == ambush_hp:
        passes.append(f"[PASS] decoded[69] 后 HP={r69['hp']} (期望{ambush_hp})")
    else:
        fails.append(f"[FAIL] decoded[69] 后 HP={r69['hp']}，期望{ambush_hp}")

    if r69["atk"] == ambush_atk:
        passes.append(f"[PASS] decoded[69] 后 ATK={r69['atk']} (期望{ambush_atk})")
    else:
        fails.append(f"[FAIL] decoded[69] 后 ATK={r69['atk']}，期望{ambush_atk}")

    if r69["def_"] == ambush_def:
        passes.append(f"[PASS] decoded[69] 后 DEF={r69['def_']} (期望{ambush_def})")
    else:
        fails.append(f"[FAIL] decoded[69] 后 DEF={r69['def_']}，期望{ambush_def}")

    if r69["floor"] == ambush_floor and r69["pos_after"] == ambush_pos:
        passes.append(f"[PASS] decoded[69] 后在 {r69['floor']}{r69['pos_after']} (伏击传送正确)")
    else:
        fails.append(f"[FAIL] decoded[69] 后在 {r69['floor']}{r69['pos_after']}，期望 MT2(3,8)")

    # ── 打印结果摘要 ───────────────────────────────────────────────────────────
    print("=" * 60)
    print("验收摘要")
    print("=" * 60)
    for p in passes:
        print(p)
    for f in fails:
        print(f)
    print()
    print(f"通过 {len(passes)}，失败 {len(fails)}")

    # ── 写全量轨迹 ──────────────────────────────────────────────────────────────
    out_path = DATA / "verify_npc_trace.txt"
    lines = [
        "# NPC修复验收轨迹（decoded[0..75]）",
        f"{'idx':>4}  {'tok':<10}  {'floor':<6}  {'before':>8}  {'after':>8}  "
        f"{'hp':>5}  {'atk':>4}  {'def':>4}  {'keys':<28}  label",
        "-" * 110,
    ]
    for r in rows:
        lines.append(
            f"{r['idx']:>4}  {r['tok']:<10}  {r['floor']:<6}  "
            f"({r['pos_before'][0]},{r['pos_before'][1]})  "
            f"({r['pos_after'][0]},{r['pos_after'][1]})  "
            f"{r['hp']:>5}  {r['atk']:>4}  {r['def_']:>4}  "
            f"{str(r['keys']):<28}  {r['label']}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n完整轨迹写入: {out_path}")


if __name__ == "__main__":
    main()
