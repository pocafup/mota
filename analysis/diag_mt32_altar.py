"""只读诊断：回放到 MT32 祭坛购买段，逐 token 打印 times1/ratio/money1/gold/atk，
核对 times1 是否从 MT4/MT12 跨层累计、成本档位是否对（第4次该=140）。不改产品代码。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(hero=hero, floors={'MT1': floor}, current_floor='MT1',
                     floor_ids=floor_ids, visited_floors={'MT1'},
                     pending_floor_change=None, _floors_dir=FLOORS)


def load_tokens():
    rp = next((Path(__file__).parent.parent).glob('51_*.h5route'), None)
    raw = rp.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def main():
    tokens = load_tokens()
    state = build_initial_state()
    # 记录 MT4/MT12 祭坛购买后的 times1
    milestones = {}
    for idx, tok in enumerate(tokens[:2497]):
        state = step(state, tok)
        h = state.hero
        if idx in (2400,):
            milestones[idx] = h.flags.get('times1', 0)
        if 2476 <= idx <= 2496:
            f = h.flags
            print(f"tok[{idx:4d}] {tok:10s} floor={state.current_floor:5s} "
                  f"({h.x},{h.y}) gold={h.gold:5d} atk={h.atk:3d} "
                  f"times1={f.get('times1',0)} ratio={f.get('ratio',0)} "
                  f"money1={f.get('money1','-')}")
    print(f"\ntimes1 @tok2400(入MT32前): {milestones.get(2400)}")
    print(f"最终 atk={state.hero.atk} gold={state.hero.gold} times1={state.hero.flags.get('times1',0)}")


if __name__ == '__main__':
    main()
