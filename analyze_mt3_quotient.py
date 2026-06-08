"""评估用一次性脚本（不改引擎/求解器）：算 MT3 在 seg4 入口态下的【缩点商图】真实规模。

回答玩家「MT3 缩点后有几个块、几条付代价的边」——拿真实数据对比朴素 BFS 的 2M 爆炸。

缩点口径（复刻 sim._auto_floodfill_pass 的可达语义，但只分区、不改状态）：
  · 「自由透明格」= 可零代价移入：地形可通行(非墙/noPass/特殊门/钥匙门/自开门) + 非大怪footprint
    + 实体为【空 / 道具 / 零伤可秒杀怪(_auto_combat_result 非 None)】。道具与零伤怪 = 块内吸收，
    顺序无关，不进搜索分支（玩家方案 4c 的「自动吸」）。
  · 块 = 自由透明格的 4-邻接连通分量（并查集）。块内坐标不进状态。
  · 「付代价边/节点」= 分隔块、需付代价或属独立节点者：耗血可杀怪(damage>0)、钥匙门、自开门、
    特殊门、可破墙(canBreak)、挂事件格/怪(MT33 硬约束：独立节点)、楼梯(免费层间边)。
零伤判定用【当前 atk】实算 compute_combat（玩家方案 4a：随属性动态）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import (step, _auto_combat_result, _build_monster,
                           _in_alive_monster_footprint, _enemy_special_set,
                           WALL_TILES, SPECIAL_DOOR, AUTO_OPEN_TILES, DOOR_KEY_MAP)
from sim.combat import PlayerState, compute_combat

MT3_ENTRY_TOKEN = 82   # analyze: seg3 forced D@81 ⟶换层；tokens[:82] 执行完即在 MT3 入口


def reach_mt3_entry():
    tokens = load_tokens()
    state = build_initial_state()
    for tok in tokens[:MT3_ENTRY_TOKEN]:
        state = step(state, tok)
    return state


class DSU:
    def __init__(self):
        self.p = {}
    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _killable_now(state, mid):
    """返回 (killable, damage)：damage=None 表打不动(硬墙)。"""
    h = state.hero
    mon = _build_monster(state, mid)
    ps = PlayerState(hp=h.hp, atk=h.atk, def_=h.def_, mdef=h.mdef)
    res = compute_combat(ps, mon, has_cross=h.items.get("cross", 0) > 0,
                         has_knife=h.items.get("knife", 0) > 0)
    if res is None or res.damage is None:
        return False, None
    return True, res.damage


def classify(state):
    f = state.floor
    rows, cols = len(f.terrain), len(f.terrain[0])
    cats = {"transparent": set(), "zero_monster": [], "costly_monster": [],
            "unkillable_monster": [], "event_monster": [], "item": [],
            "key_door": [], "auto_open": [], "special_door": [], "nopass": [],
            "wall": [], "npc_event": [], "empty": 0}
    for y in range(rows):
        for x in range(cols):
            t = f.terrain[y][x]
            e = f.entities[y][x]
            loc = f"{x},{y}"
            has_event = (loc in f.events or loc in f.after_battle
                         or loc in f.before_battle)
            # 地形阻挡分类
            if t in WALL_TILES:
                cats["wall"].append((x, y)); continue
            if t in f._no_pass_tiles:
                cats["nopass"].append((x, y)); continue
            if t == SPECIAL_DOOR:
                cats["special_door"].append((x, y)); continue
            if t in DOOR_KEY_MAP:
                cats["key_door"].append((x, y, DOOR_KEY_MAP[t])); continue
            if t in AUTO_OPEN_TILES:
                cats["auto_open"].append((x, y)); continue
            if _in_alive_monster_footprint(f, x, y):
                cats["wall"].append((x, y)); continue
            # 实体分类
            if e:
                if e in f._tile_to_enemy:
                    mid = f._tile_to_enemy[e]
                    if has_event:
                        cats["event_monster"].append((x, y, mid)); continue
                    if _auto_combat_result(state, x, y) is not None:
                        cats["zero_monster"].append((x, y, mid))
                        cats["transparent"].add((x, y)); continue   # 吸收=透明
                    killable, dmg = _killable_now(state, mid)
                    if killable:
                        cats["costly_monster"].append((x, y, mid, dmg))
                    else:
                        cats["unkillable_monster"].append((x, y, mid))
                    continue
                if e in f._tile_to_item:
                    cats["item"].append((x, y, f._tile_to_item[e]))
                    cats["transparent"].add((x, y)); continue   # 拾取=透明
                # NPC/商人/老人/祭坛等
                cats["npc_event"].append((x, y)); continue
            # 空地（无实体、地形可通行）
            if has_event:
                cats["npc_event"].append((x, y)); continue   # 踩格机关=独立节点
            cats["transparent"].add((x, y))
            cats["empty"] += 1
    return cats, rows, cols


def count_blocks(transparent, rows, cols):
    dsu = DSU()
    for (x, y) in transparent:
        dsu.find((x, y))
        for dx, dy in ((1, 0), (0, 1)):
            nb = (x + dx, y + dy)
            if nb in transparent:
                dsu.union((x, y), nb)
    roots = {dsu.find(c) for c in transparent}
    sizes = {}
    for c in transparent:
        r = dsu.find(c)
        sizes[r] = sizes.get(r, 0) + 1
    return len(roots), sorted(sizes.values(), reverse=True), dsu


def main():
    state = reach_mt3_entry()
    h = state.hero
    print("=" * 78)
    print(f"MT3 seg4 入口态：floor={state.current_floor} pos=({h.x},{h.y}) "
          f"HP={h.hp} ATK={h.atk} DEF={h.def_} keys={h.keys}")
    print("=" * 78)
    assert state.current_floor == "MT3", f"期望 MT3，实到 {state.current_floor}"

    cats, rows, cols = classify(state)
    nblocks, sizes, dsu = count_blocks(cats["transparent"], rows, cols)
    hero_block = dsu.find((h.x, h.y)) if (h.x, h.y) in cats["transparent"] else None
    hero_block_size = sum(1 for c in cats["transparent"] if dsu.find(c) == hero_block) if hero_block else 0

    npass = len(cats["transparent"])
    print(f"\n地图 {cols}×{rows} = {rows * cols} 格")
    print(f"  自由透明格(可零代价通行/吸收) = {npass}  其中纯空地={cats['empty']}")
    print(f"  → 缩点后【连通块数】= {nblocks}   块大小分布(前10)={sizes[:10]}")
    print(f"  英雄所在块大小 = {hero_block_size}（块内任意格免费可达，坐标不进状态）")

    zm, cm, um, em = (cats["zero_monster"], cats["costly_monster"],
                      cats["unkillable_monster"], cats["event_monster"])
    print(f"\n怪物分类（按当前 ATK={h.atk} 动态）：")
    print(f"  零伤可秒杀(块内吸收，非分支) = {len(zm)}  {[m[2] for m in zm]}")
    print(f"  耗血可杀(付代价合并，搜索分支)= {len(cm)}  "
          f"{[(m[2], f'-{m[3]}hp') for m in cm]}")
    print(f"  当前打不动(硬墙，atk涨后或可杀)= {len(um)}  {[m[2] for m in um]}")
    print(f"  挂事件的怪(独立节点，MT33约束) = {len(em)}  {[m[2] for m in em]}")

    print(f"\n门 / 墙 / 楼梯 / 事件格：")
    print(f"  钥匙门(付钥匙的边) = {len(cats['key_door'])}  {cats['key_door']}")
    print(f"  自开假墙           = {len(cats['auto_open'])}")
    print(f"  特殊门(85)         = {len(cats['special_door'])}")
    print(f"  踩格机关/NPC/祭坛(独立节点) = {len(cats['npc_event'])}  {cats['npc_event']}")
    print(f"  地上道具(块内吸收) = {len(cats['item'])}  {[m[2] for m in cats['item']]}")

    # —— 搜索空间量级对比 —— 朴素 BFS 指纹 ≈ 可达格 × 2^(可消耗实体改指纹)；缩点 ≈ 块 × 2^(付代价合并)
    naive_toggles = len(zm) + len(cm) + len(cats["item"]) + len(cats["key_door"]) + len(cats["auto_open"])
    quot_toggles = len(cm) + len(cats["key_door"]) + len(cats["auto_open"])
    print("\n" + "-" * 78)
    print("搜索空间量级（粗估，仅 MT3 单层、不含跨层）：")
    print(f"  朴素 BFS 指纹上界 ≈ 可达格{npass} × 2^(零伤{len(zm)}+耗血{len(cm)}+道具{len(cats['item'])}"
          f"+门{len(cats['key_door'])+len(cats['auto_open'])}) = {npass} × 2^{naive_toggles} "
          f"≈ {npass * (2 ** naive_toggles):,}")
    print(f"  缩点商图状态   ≈ 块{nblocks} × 2^(耗血{len(cm)}+门{len(cats['key_door'])+len(cats['auto_open'])})"
          f" = {nblocks} × 2^{quot_toggles} ≈ {nblocks * (2 ** quot_toggles):,}")
    if naive_toggles >= quot_toggles and quot_toggles >= 0:
        ratio = (npass * 2 ** naive_toggles) / max(1, nblocks * 2 ** quot_toggles)
        print(f"  → 理论压缩 ≈ {ratio:,.0f}×（位置塌缩 {npass}->{nblocks}，可消耗维 2^{naive_toggles}->2^{quot_toggles}）")
    print(f"  实测：朴素搜索本段撞 2,000,000 cap（gen=2,000,003，未跑完）。")


if __name__ == "__main__":
    main()
