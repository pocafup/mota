"""追踪 tok[1265..1295]：打印每步之后 floor/pos/ATK/HP，以及商店触发状态"""
import json, sys
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

TRACE_START = 1265
TRACE_END   = 1295

for i, tok in enumerate(all_tokens):
    state = step(state, tok)
    if TRACE_START <= i <= TRACE_END:
        fl = state.floors.get(state.current_floor)
        intercepting = fl._event_intercepting if fl else "?"
        print(f"[{i:4}] {tok:<14}  {state.current_floor:<5}  "
              f"({state.hero.x:>2},{state.hero.y:>2})  "
              f"HP={state.hero.hp:>4}  ATK={state.hero.atk:>3}  "
              f"intercept={'Y' if intercepting else 'N'}")
