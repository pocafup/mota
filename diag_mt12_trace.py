"""
诊断：tok[1250..1320] 详细追踪
回答三个问题：
1. tok[1270] 的 ATK 是多少？
2. 横跳结束后英雄从哪步分叉（没走向祭坛或没上 MT14）？
3. 祭坛购买（MT12 (6,9)）在模拟器里实现了吗？
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA    = Path(__file__).parent / "data" / "games51"
FLOORS  = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path(__file__).parent.glob("51_*.h5route"))
raw = route_path.read_text(encoding="utf-8").strip()
outer = json.loads(decompress(raw))
all_tokens = parse_rle_route(decompress(outer["route"]))

print(f"总 token 数: {len(all_tokens)}")

hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
floor = load_floor(FLOORS / "MT1.json")
hero = HeroState(
    x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
    hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
    mdef=hero_init.get("mdef", 0), gold=hero_init.get("gold", 0),
    keys={}, items=dict(hero_init.get("items", {})),
    flags=dict(hero_init.get("flags", {})),
)
state = GameState(
    hero=hero, floors={"MT1": floor},
    current_floor="MT1", floor_ids=FLOOR_IDS,
    visited_floors={"MT1"}, pending_floor_change=None, _floors_dir=FLOORS,
)

TRACE_START = 1240
TRACE_END   = 1330

states = []
for i, tok in enumerate(all_tokens):
    state = step(state, tok)
    if TRACE_START <= i <= TRACE_END:
        states.append((i, tok, state.current_floor, state.hero.x, state.hero.y,
                       state.hero.hp, state.hero.atk, state.hero.def_, state.hero.gold))

print(f"\n{'idx':>5}  {'token':<14}  {'floor':<6}  {'pos':>7}  {'HP':>5}  {'ATK':>4}  {'DEF':>4}  {'gold':>5}")
print("-" * 68)

prev_floor = None
for idx, tok, floor_id, x, y, hp, atk, def_, gold in states:
    marker = ""
    if floor_id != prev_floor:
        marker = " ◀ 切层"
    prev_floor = floor_id
    print(f"[{idx:>4}]  {tok:<14}  {floor_id:<6}  ({x:>2},{y:>2})  {hp:>5}  {atk:>3}  {def_:>4}  {gold:>5}{marker}")

# 特别标出 tok[1270] 的 ATK
t1270 = next((s for s in states if s[0] == 1270), None)
if t1270:
    print(f"\n>>> tok[1270] ATK = {t1270[6]}  (真值应为 42)")

# 找第一个 ATK != 30 的时刻
print("\n--- ATK 首次变化 ---")
for idx, tok, floor_id, x, y, hp, atk, def_, gold in states:
    if atk != 30:
        print(f"  ATK 首次不等于 30：tok[{idx}] = {atk}  floor={floor_id} pos=({x},{y})")
        break
else:
    print("  ATK 在整段追踪中始终 = 30（祭坛购买未实现）")

# 找到祭坛格 (6,9) 是否被到达
print("\n--- 英雄是否到达 MT12(6,9) ---")
for idx, tok, floor_id, x, y, hp, atk, def_, gold in states:
    if floor_id == "MT12" and x == 6 and y == 9:
        print(f"  到达 MT12(6,9) at tok[{idx}]  ATK={atk}")
        break
else:
    print("  整段追踪中英雄从未到达 MT12(6,9)")

# 打印所有 CHOICE token
print("\n--- CHOICE token 列表 ---")
for idx, tok, floor_id, x, y, hp, atk, def_, gold in states:
    if tok.startswith("CHOICE"):
        print(f"  tok[{idx}] {tok}  floor={floor_id} pos=({x},{y})  ATK={atk}")
