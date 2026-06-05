"""只读诊断：定位 route 中 MT16(11,11) 老人(发圣水)交互的 token 序列。
打印所有 floor==MT16 且 (英雄在 (10,11)/(11,10)/(11,11) 附近 或 token 是 CHOICE) 的 token，
看是否存在 撞(11,11)→撞(11,11)→CHOICE:0 的二段交互。不改产品代码/真值/断言。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step

NEAR = {(10, 11), (11, 10), (11, 11), (11, 12), (12, 11)}


def main():
    tokens = load_tokens()
    state = build_initial_state()
    for idx, tok in enumerate(tokens):
        prev = (state.current_floor, state.hero.x, state.hero.y)
        state = step(state, tok)
        h = state.hero
        on16 = state.current_floor == "MT16"
        near = (h.x, h.y) in NEAR
        is_choice = tok.startswith("CHOICE")
        # 也抓“从 MT16 邻格撞 (11,11)”：撞墙/NPC 不移动，prev 在邻格
        if on16 and (near or (is_choice and prev[0] == "MT16")):
            sw = h.flags.get("switch:A", "<未设>")
            sp = h.items.get("superPotion", 0)
            print(f"tok[{idx}] {tok:<10} MT16({h.x},{h.y})  switch:A={sw}  superPotion={sp}")


if __name__ == '__main__':
    main()
