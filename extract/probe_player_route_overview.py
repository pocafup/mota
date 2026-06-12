"""【想法3·前提·只读】解码玩家通关 h5route，从真起点(MT1)全程引擎重放，报告总步数/终态/是否真通关。
确认 51_20260529133740.h5route 是玩家完整通关串（vs 51_roundtrip_full.h5route 往返产物）。
口径同 tests/test_checkpoints.py：tokens[0]=CHOICE:1 初始化；逐 token step；金标准真值表对账。
跑法：python -u extract/probe_player_route_overview.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from lzstring import LZString
from decode_route import parse_rle_route
from sim.simulator import GameState, HeroState, load_floor, step

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data/games51"
FLOORS = DATA / "floors"

CANDIDATES = ["51_20260529133740.h5route", "51_roundtrip_full.h5route"]


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


def load_tokens(path):
    raw = path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def replay(path):
    tokens = load_tokens(path)
    s = build_initial_state()
    trace = []   # (i, floor, hp, atk, def, x, y)
    floors_seen = []
    err = None
    for i, tok in enumerate(tokens):
        try:
            s = step(s, tok)
        except Exception as e:
            err = f"步{i} tok={tok!r} 异常: {e}"
            break
        h = s.hero
        trace.append((i, s.current_floor, h.hp, h.atk, h.def_, h.x, h.y))
        if not floors_seen or floors_seen[-1] != s.current_floor:
            floors_seen.append(s.current_floor)
    return tokens, s, trace, floors_seen, err


def main():
    for name in CANDIDATES:
        path = ROOT / name
        print("=" * 92)
        print(f"文件：{name}")
        if not path.exists():
            print("  不存在，跳过")
            continue
        tokens, s, trace, floors_seen, err = replay(path)
        h = s.hero
        print(f"  解码 token 数：{len(tokens)}（tokens[0]={tokens[0]!r}）")
        if err:
            print(f"  ⚠ 重放中断：{err}")
        last = trace[-1] if trace else None
        if last:
            print(f"  终态：步{last[0]} {last[1]}({last[5]},{last[6]}) "
                  f"HP={last[2]} ATK={last[3]} DEF={last[4]}")
        print(f"  全程持钥：{ {k: v for k, v in h.keys.items() if v} }")
        print(f"  flags(victory/胜利标记相关)：{ {k: v for k, v in h.flags.items() if v and ('victory' in k.lower() or 'win' in k.lower() or 'clear' in k.lower() or 'boss' in k.lower())} }")
        # 楼层访问序列（去重相邻）
        print(f"  楼层访问序列（{len(floors_seen)} 段）：{' → '.join(floors_seen)}")
        # 每 100 步一个里程碑（对账 test_checkpoints 金标准）
        print("  里程碑（每 200 步）：")
        for i, fl, hp, atk, df, x, y in trace:
            if i % 200 == 0 and i > 0:
                print(f"    tok[{i}] {fl}({x},{y}) HP={hp} ATK={atk} DEF={df}")
    print("=" * 92)


if __name__ == "__main__":
    main()
