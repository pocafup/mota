"""MT7【绕过骷髅士兵·2黄门+3史莱姆】macro-edge 概念验证探针（一次性，不碰 quotient/beam）。

目的：在动主体代码前，验证 macro-edge 架构的地基假设 + f 原语正确性。只报三组数：
  ① 命门——该绕路段是否【静态·无拾取·无事件·无special】纯怪门段（逐格核实，藏拾取就立即报警）。
  ② f(atk,def) 分段表实际规模 + 预处理耗时（决定架构跑不跑得动）。
  ③ 引擎重放对拍——取几个具体 (atk,def)，f 表查得损血 vs 封板引擎【实走该段】真实损血，须一致。

铁律：段的格子/算子由引擎+静态地图算出，不手推路径；损血全用引擎 compute_combat / step，不手写公式。
塔无关性不适用（这是 extract/ 驱动层探针，可读塔特有 MT7 数据）；solver/ 一行不改。
"""
import heapq
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import (
    step, _copy_state, WALL_TILES, DOOR_KEY_MAP, _build_monster,
)
from sim.combat import PlayerState, compute_combat

_DIRS = [((0, -1), "U"), ((0, 1), "D"), ((-1, 0), "L"), ((1, 0), "R")]
BLOCK_BYPASS = {"skeletonSoldier"}   # 绕路【不走】这只——这正是"绕过它"的定义


# ─── 单元：格分类（引擎数据，不手推）────────────────────────────────────────────

def classify(floor, x, y):
    """返回 (kind, info)：wall / monster:mid / item:iid / door:keyname / stair:dest / npc / floor。"""
    rows, cols = len(floor.terrain), len(floor.terrain[0])
    if not (0 <= x < cols and 0 <= y < rows):
        return ("wall", None)
    e = floor.entities[y][x]
    mid = floor._tile_to_enemy.get(e)
    if mid is not None:
        return ("monster", mid)
    if e in floor._tile_to_item:
        return ("item", floor._tile_to_item[e])
    t = floor.terrain[y][x]
    if f"{x},{y}" in floor.change_floor:
        return ("stair", floor.change_floor[f"{x},{y}"].get("floorId"))
    if t in DOOR_KEY_MAP:
        return ("door", DOOR_KEY_MAP[t])
    if t in WALL_TILES:
        return ("wall", None)
    if e and e in getattr(floor, "_tile_to_entity", {}):
        return ("npc", e)
    return ("floor", None)


def replay_to_first(floor_id="MT7"):
    """重放封板存档 token 到首次踏入 floor_id，返回 (state, token_idx)。真实可玩态，非合成。"""
    state = build_initial_state()
    tokens = load_tokens()
    for i, tok in enumerate(tokens):
        state = step(state, tok)
        if state.current_floor == floor_id:
            return state, i
    raise RuntimeError(f"重放未抵达 {floor_id}")


def up_stair_cell(floor):
    """:next（上行/通往更高层）的楼梯格 (x,y)。"""
    for loc, cf in floor.change_floor.items():
        if isinstance(cf, dict) and cf.get("floorId") == ":next":
            x, y = map(int, loc.split(","))
            return (x, y)
    return None


def free_block(floor, sx, sy):
    """从 (sx,sy) 零代价(地板/道具/楼梯)可达的自由块。怪/门/墙/NPC 为边界。"""
    seen = {(sx, sy)}
    stack = [(sx, sy)]
    while stack:
        cx, cy = stack.pop()
        for (dx, dy), _ in _DIRS:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in seen:
                continue
            kind, _info = classify(floor, nx, ny)
            if kind in ("floor", "item", "stair"):
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def dijkstra_bypass(floor, src_cells, target, blocked_ids):
    """从 src_cells 任一格到 target 的最省【(杀怪数, 开门数, 步数)】路径，
    blocked_ids 里的怪当墙（=绕过它）。返回 cell 路径 [(x,y)...] 或 None。"""
    pq = []
    dist = {}
    for (sx, sy) in src_cells:
        dist[(sx, sy)] = (0, 0, 0)
        heapq.heappush(pq, (0, 0, 0, sx, sy, None))
    prev = {}
    while pq:
        k, d, st, x, y, par = heapq.heappop(pq)
        if (x, y) in prev:
            continue
        prev[(x, y)] = par
        if (x, y) == target:
            path = []
            cur = (x, y)
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            return path[::-1]
        for (dx, dy), _ in _DIRS:
            nx, ny = x + dx, y + dy
            kind, info = classify(floor, nx, ny)
            if kind == "wall" or kind == "npc":
                continue
            if kind == "monster" and info in blocked_ids:
                continue
            dk = 1 if kind == "monster" else 0
            dd = 1 if kind == "door" else 0
            nk, nd, ns = k + dk, d + dd, st + 1
            if (nx, ny) not in dist or (nk, nd, ns) < dist[(nx, ny)]:
                dist[(nx, ny)] = (nk, nd, ns)
                heapq.heappush(pq, (nk, nd, ns, nx, ny, (x, y)))
    return None


# ─── f 原语：单 slime 损血（引擎 compute_combat）+ 段分段表 ───────────────────────

def seg_blood(state, mids, atk, def_):
    """该段 mids 在 (atk,def) 下总损血（引擎算，逐怪 compute_combat 求和）。None=任一打不动。"""
    total, turns = 0, []
    for mid in mids:
        mon = _build_monster(state, mid)
        res = compute_combat(PlayerState(hp=10**7, atk=atk, def_=def_, mdef=0), mon)
        if res.damage is None:
            return None, None
        total += res.damage
        turns.append(res.turn)
    return total, turns


def atk_breakpoints(state, mid, atk_lo, atk_hi):
    """单怪在 [atk_lo,atk_hi] 上 turn 变化的 atk 临界点（√hp 量级）。"""
    bps = []
    last = None
    for a in range(atk_lo, atk_hi + 1):
        mon = _build_monster(state, mid)
        res = compute_combat(PlayerState(hp=10**7, atk=a, def_=0, mdef=0), mon)
        tn = res.turn if res.damage is not None else None
        if tn != last:
            bps.append((a, tn))
            last = tn
    return bps


def main():
    print("=" * 92)
    print("MT7【绕过骷髅士兵·2黄门+3史莱姆】macro-edge 概念验证探针")
    print("=" * 92)

    # ── ① 命门 a：整层事件/地形血审计（静态地图直读）────────────────────────────
    import json
    mt7 = json.loads((Path(__file__).parent.parent / "data/games51/floors/MT7.json")
                     .read_text(encoding="utf-8"))
    ev_fields = ["events", "firstArrive", "eachArrive", "afterGetItem",
                 "afterBattle", "afterOpenDoor", "cannotMove"]
    ev_empty = {k: (len(mt7.get(k) or []) == 0 if isinstance(mt7.get(k), list)
                    else len(mt7.get(k) or {}) == 0) for k in ev_fields}
    lava = mt7.get("_lava_tiles", [])
    print("① 整层静态审计：")
    for k in ev_fields:
        print(f"   {k:14s}: {'空 ✅' if ev_empty[k] else '⚠ 非空 ' + str(mt7.get(k))}")
    print(f"   {'_lava_tiles':14s}: {'空 ✅(无地形血)' if not lava else '⚠ ' + str(lava)}")
    floor_clean = all(ev_empty.values()) and not lava

    # ── ① 命门 b：全层怪 special 审计 ─────────────────────────────────────────
    mons = json.loads((Path(__file__).parent.parent / "data/games51/monsters.json")
                      .read_text(encoding="utf-8"))
    present = set()
    for name in mt7["_map_entities"]["monsters"]:
        present.add(name.split("(")[0])
    print("② 全层怪 special 审计：")
    all_plain = True
    for nm in sorted(present):
        sp = mons.get(nm, {}).get("special", [])
        ok = (sp == [])
        all_plain = all_plain and ok
        print(f"   {nm:18s}: special={sp} {'✅' if ok else '⚠ 有特殊'}")

    # ── 取真实 MT7 态 + 定位上行楼梯 + 绕路段 ─────────────────────────────────
    print("-" * 92)
    s, idx = replay_to_first("MT7")
    h = s.hero
    floor = s.floor
    print(f"真实 MT7 态（封板存档重放第 {idx} token 首入）: 英雄@({h.x},{h.y}) "
          f"HP={h.hp} ATK={h.atk} DEF={h.def_} keys={dict(h.keys)}")
    up = up_stair_cell(floor)
    print(f"上行楼梯(:next→更高层)格 = {up}")
    src = free_block(floor, h.x, h.y)
    print(f"英雄自由块大小 = {len(src)} 格")

    path = dijkstra_bypass(floor, src, up, BLOCK_BYPASS)
    if path is None:
        print("⚠ 绕路（避开 skeletonSoldier）不可达——需放开约束或换段，停。")
        return
    # 段算子序列 + 逐格审计
    kills, doors, items_on_path = [], [], []
    for (x, y) in path:
        kind, info = classify(floor, x, y)
        if kind == "monster":
            kills.append(((x, y), info))
        elif kind == "door":
            doors.append(((x, y), info))
        elif kind == "item":
            items_on_path.append(((x, y), info))
    print("-" * 92)
    print(f"③ 绕路段（自由块 → 上行楼梯，避开 {BLOCK_BYPASS}），共 {len(path)} 格：")
    print(f"   路径格: {path}")
    print(f"   杀怪算子({len(kills)}): " +
          ", ".join(f"{c}={m}" for c, m in kills))
    print(f"   开门算子({len(doors)}): " +
          ", ".join(f"{c}={k}" for c, k in doors))
    print(f"   ★命门★ 段内拾取格: " +
          (f"⚠⚠ 有 {items_on_path} → 该边不能整段收缩，须在拾取处切开！"
           if items_on_path else "无 ✅（纯怪门段，可整段收缩成一条 macro-edge）"))
    seg_mids = [m for _c, m in kills]
    print(f"   段=【{len(seg_mids)}怪 + {len(doors)}门】: 怪={seg_mids}  门={[k for _c,k in doors]}")

    geo_ok = floor_clean and all_plain and not items_on_path
    print(f"   ⇒ 地基假设（静态·无拾取·无事件·无special）: "
          f"{'成立 ✅✅✅' if geo_ok else '⚠ 不成立——见上'}")

    # ── ② f 分段表规模 + 预处理耗时 ───────────────────────────────────────────
    print("-" * 92)
    print("④ f(atk,def) 分段表规模 + 预处理耗时：")
    ATK_LO, ATK_HI = 3, 60
    DEF_LO, DEF_HI = 0, 60
    t0 = time.perf_counter()
    # atk 轴：逐怪 turn 临界（√hp）→ 段并集
    per_mon_bps = {}
    atk_break_set = {ATK_LO, ATK_HI + 1}
    for mid in set(seg_mids):
        bps = atk_breakpoints(s, mid, ATK_LO, ATK_HI)
        per_mon_bps[mid] = bps
        for (a, _tn) in bps:
            atk_break_set.add(a)
    atk_segments = sorted(atk_break_set)
    # 高效表示：1D over atk-段（def 用公式 (turn-1)*max(0,atk_mon-def) 现算）
    n_atk_seg = len(atk_segments) - 1
    # 朴素 2D：枚举 (atk,def) 全网格的 distinct 段（损血值变化即新格）
    cells_2d = 0
    for a in range(ATK_LO, ATK_HI + 1):
        last = object()
        for d in range(DEF_LO, DEF_HI + 1):
            b, _t = seg_blood(s, seg_mids, a, d)
            if b != last:
                cells_2d += 1
                last = b
    dt = time.perf_counter() - t0
    print(f"   atk 轴临界点（各怪 turn 变化点，√hp 量级）:")
    for mid, bps in per_mon_bps.items():
        print(f"     {mid:14s}: {len(bps)} 段  断点 atk={[a for a,_ in bps][:12]}"
              f"{'...' if len(bps)>12 else ''}")
    print(f"   段并集 atk-段数 = {n_atk_seg}（高效表示：1D over atk-段，def 用线性公式现算）")
    print(f"   朴素 2D 表 distinct 损血格数（atk∈[{ATK_LO},{ATK_HI}]×def∈[{DEF_LO},{DEF_HI}]）"
          f" = {cells_2d}")
    print(f"   预处理耗时 = {dt*1000:.1f} ms（含 2D 全枚举 {(ATK_HI-ATK_LO+1)*(DEF_HI-DEF_LO+1)} 点引擎战斗）")

    # ── ③ 引擎实走对拍 ───────────────────────────────────────────────────────
    print("-" * 92)
    print("⑤ 引擎重放对拍（f 表查值 vs 封板引擎【实走该段】）：")
    # 段【实走】token：从 path[0] 走到上行楼梯【前一格】（不踏楼梯免换层）。怪/门=同向按两下。
    walk_path = path[:-1] if classify(floor, *path[-1])[0] == "stair" else path[:]
    test_pts = [(22, 11), (10, 10), (25, 6), (30, 20), (24, 0)]
    print(f"   实走格序（止于楼梯前一格）: {walk_path}")
    print(f"   {'(atk,def)':12s} {'f表损血':>8s} {'引擎实走损血':>12s} {'门(钥匙)':>8s} {'对拍':>6s}")
    for (atk, def_) in test_pts:
        f_blood, f_turns = seg_blood(s, seg_mids, atk, def_)
        # 配置测试态：英雄置于段首格，设属性、海量血与黄钥匙，实走
        t = _copy_state(s)
        t.hero.x, t.hero.y = walk_path[0]
        t.hero.atk, t.hero.def_, t.hero.mdef = atk, def_, 0
        t.hero.hp = 10**7
        t.hero.keys = dict(t.hero.keys)
        t.hero.keys["yellowKey"] = 99
        hp0 = t.hero.hp
        ykey0 = t.hero.keys.get("yellowKey", 0)
        # 逐格走：朝下一格方向发 token；若下一格是怪/门，先打/开（不移入）再同向走入
        ok_walk = True
        for (cx, cy), (nx, ny) in zip(walk_path, walk_path[1:]):
            dx, dy = nx - cx, ny - cy
            mv = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}[(dx, dy)]
            kind, _info = classify(t.floor, nx, ny)
            # 引擎语义：怪=1下(打赢当场移入怪格,见 _fight_monster);门=2下(开门英雄停,再同向走入);地板=1下
            presses = 2 if kind == "door" else 1
            for _ in range(presses):
                t = step(t, mv)
                if t.dead:
                    ok_walk = False
                    break
            if not ok_walk:
                break
            if (t.hero.x, t.hero.y) != (nx, ny):
                # 没走到位（被打不动的怪挡住等）→ 标记
                ok_walk = False
                break
        eng_blood = hp0 - t.hero.hp if ok_walk else None
        eng_keys = ykey0 - t.hero.keys.get("yellowKey", 0) if ok_walk else None
        match = "✅一致" if (ok_walk and eng_blood == f_blood) else "⚠不一致"
        fb = "打不动" if f_blood is None else str(f_blood)
        eb = "走不通" if eng_blood is None else str(eng_blood)
        print(f"   ({atk:>3},{def_:>3})   {fb:>8s} {eb:>12s} {str(eng_keys):>8s}   {match}")

    print("=" * 92)
    print("结论速读：地基假设是否成立(③命门) / 分段表规模(④) / f vs 引擎是否一致(⑤) —— 三者决定要不要走第二步。")


if __name__ == "__main__":
    main()
