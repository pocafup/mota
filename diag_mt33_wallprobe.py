"""只读探针：route 全程定位 MT33 (8,10)/(9,10) 占用与穿越方向 + 局部地形/可通行 + token 构成。

回答（全部由运行代码判定，不靠猜测）：
  U1 route 是否曾站上 (8,10)？—— 解 tiles.json flower noPass:true(live抓) vs false(我们订正) 矛盾。
  U2 route 穿越方向 —— 钉「防回头墙」触发几何。
  G  (8,10) 邻格 (8,9)/(8,11)/(7,10)/(9,10) 是否可通行 —— 决定「停在(8,10)」是不是可被 solver
     利用的幻影分支（若邻格全墙→省去 moveHero 自动前进、只做封墙即安全）。
  T  route 在 idx≈2940 前后的原始 token —— 看是否含「被迫 moveHero」token（决定能否实现自动前进而不破坏重放）。

不改产品代码、不进搜索循环——纯分析。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from diag_mvp_segments import build_initial_state, load_tokens
from sim.simulator import step, WALL_TILES, SPECIAL_DOOR

TARGETS = {(8, 10), (9, 10)}


def passable(floor, x, y):
    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    if not (0 <= y < rows and 0 <= x < cols):
        return "界外"
    t = floor.terrain[y][x]
    e = floor.entities[y][x]
    if t in WALL_TILES or t in floor._no_pass_tiles or t == SPECIAL_DOOR:
        return f"墙/noPass(t={t})"
    if e in floor._tile_to_enemy:
        return f"怪(e={e})"
    if e in floor._tile_to_entity:
        return f"NPC/实体(e={e})"
    return f"可走(t={t},e={e})"


def main():
    tokens = load_tokens()
    state = build_initial_state()
    path = [(0, state.current_floor, state.hero.x, state.hero.y)]
    for i, tok in enumerate(tokens):
        state = step(state, tok)
        path.append((i + 1, state.current_floor, state.hero.x, state.hero.y))
    n = len(path)

    def fmt(p):
        return f"{p[1]}({p[2]},{p[3]})" if p else "—"

    print("=== route 落在 MT33 (8,10)/(9,10) 的全部帧（含前后邻帧） ===")
    hits = [k for k in range(n)
            if path[k][1] == "MT33" and (path[k][2], path[k][3]) in TARGETS]
    for k in hits:
        prev = path[k - 1] if k > 0 else None
        nxt = path[k + 1] if k + 1 < n else None
        print(f"  idx={path[k][0]:>4}  {fmt(prev)} -> [{fmt(path[k])}] -> {fmt(nxt)}")

    # T —— idx≈2940 前后原始 token
    print("\n=== T: route 原始 token[2936:2945]（含执行后落点） ===")
    for i in range(2936, 2945):
        if 0 <= i < len(tokens):
            after = path[i + 1]
            print(f"  token[{i}]={tokens[i]!r:>10}  →执行后 {fmt(after)}")

    # G —— 把 route 重放到刚到 (7,10)（idx2939）那一刻，看局部地形可通行
    print("\n=== G: 重放到 idx2939（hero 在 (7,10)，临穿 (8,10) 前）看局部可通行 ===")
    s2 = build_initial_state()
    for i in range(2939):
        s2 = step(s2, tokens[i])
    print(f"  此刻 hero @ {s2.current_floor}({s2.hero.x},{s2.hero.y})")
    f = s2.floors["MT33"]
    for (x, y, label) in [(7, 10, "左(7,10)"), (8, 10, "本(8,10)flower"),
                          (9, 10, "右(9,10)"), (8, 9, "上(8,9)"),
                          (8, 11, "下(8,11)"), (10, 10, "(10,10)sword")]:
        print(f"  {label:<16} -> {passable(f, x, y)}")


if __name__ == "__main__":
    main()
