"""只读诊断：tok6340 圣水(ITEM:56=superPotion) 为何没生效。
回放到 tok6340，打印：当前层、hero.items(看 superPotion 是否入包)、
state.floor._tile_to_item.get(56)(看按层映射能否解析出 superPotion)、
全局 tiles.json items[56]、以及若执行 _use_super_potion 的应得 HP。
不改任何产品代码/真值/断言。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step

TARGET = 6340


def main():
    tokens = load_tokens()
    state = build_initial_state()
    for idx, tok in enumerate(tokens[:TARGET + 1]):
        prev_hp = state.hero.hp
        # 在执行 tok6340 之前先抓判定所需信息
        if idx == TARGET:
            h = state.hero
            print(f"=== 执行 tok[{idx}]={tok} 之前 ===")
            print(f"楼层={state.current_floor}  英雄({h.x},{h.y})  HP={h.hp} ATK={h.atk} DEF={h.def_}")
            print(f"hero.items = {h.items}")
            print(f"  superPotion 持有量 = {h.items.get('superPotion', 0)}")
            tti = state.floor._tile_to_item
            print(f"state.floor._tile_to_item.get(56) = {tti.get(56)!r}")
            print(f"  (该层 _tile_to_item 含 56? {56 in tti})  全表大小={len(tti)}")
            # 全局 tiles
            tj = json.load(open('data/games51/tiles.json', encoding='utf-8'))
            print(f"全局 tiles.json items[56] = {tj['items'].get('56')}")
            # 应得 HP
            import math
            gain = math.floor(0.74 * (h.atk + h.def_) + 0.5) * 10
            print(f"圣水应加 HP = round(0.74*({h.atk}+{h.def_}))*10 = {gain}")
        state = step(state, tok)
        if idx == TARGET:
            print(f"\n=== 执行 tok[{idx}] 之后 ===")
            print(f"HP {prev_hp} → {state.hero.hp}  (Δ={state.hero.hp - prev_hp:+d})")
            print(f"superPotion 持有量 = {state.hero.items.get('superPotion', 0)}")


if __name__ == '__main__':
    main()
