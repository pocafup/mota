"""【方向2·便宜诊断②】红钥腿 9 层 ATK/DEF 物量够不够攒到破门阈值 + 高宝石锁不锁红门后。

接诊断①（dir2_redkey_gate_threshold.py）：破门阈值 = 从 beam 攒到的 ATK25/DEF25/HP733
再要 +1ATK(→26) 或 +1DEF(→26) 或 +4HP(→737)。本脚本回答「加力能不能攒出这 1 点」：

  问题1：9 层 {MT1,3,4,5,6,7,8,9,10} 从 tok454 铁盾态还能 door-wise 拿到多少 ATK/DEF？
          （door-wise = 只看门墙拓扑、守怪可穿=乐观上界；够不够把 ATK 22→26 / DEF 20→26）
  问题2：★破门所需高宝石有没有锁在【红门(83)/铁门(86)/机关门(85)】后？
          红钥是【本段终点·破门前没红钥】→ 红门后宝石 = 破门前拿不到 = 结构性死结标志。
          铁钥一区拿不到 → 铁门后永久锁死。

afford 口径：
  · 破门前真实 afford = _afford_colors(tok454) = 起点手里持有色（黄/蓝·无红钥）→ 红门当墙。
  · 全门通(_FULL_AFFORD) = 假装所有门能开 → 对比看红/铁/机关门锁了多少 ATK/DEF。

只读：复用 solver.fitness._zone_floor_cells(afford 门控 is_wall) + extract.key_targets._floor_tile_at。
绝不改产品码。
"""
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step, _KEY_ITEMS, DOOR_KEY_MAP
from solver.fitness import _afford_colors, _zone_floor_cells
from extract.key_targets import _floor_tile_at, _FULL_AFFORD, _NB4

TOK_SHIELD = 454
REAL_LEG_FLOORS = ["MT1", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10"]

# tile id → (名称, ATK增量, DEF增量)。宝石/剑盾来源 items.json + tiles.json。
# redGem/blueGem 是 ratio_scaled（实际增量 = base×floor.ratio）→ 运行时乘 ratio。
RATIO_GEM = {27: ("redGem", "atk"), 28: ("blueGem", "def")}     # base=1，×ratio
YELLOW_GEM = 30                                                  # 固定 +6atk +6def +1000hp
# 剑盾 pickup delta（items.json·直接加 ATK/DEF；起点已有 sword1/shield1）
SWORD_ATK = {35: 10, 37: 20, 39: 40, 41: 50, 43: 100}           # sword1..5
SHIELD_DEF = {36: 10, 38: 20, 40: 40, 42: 50, 44: 100}          # shield1..5
DOOR_TILES = {81: "yellowDoor", 82: "blueDoor", 83: "redDoor",
              84: "greenDoor", 85: "specialDoor", 86: "steelDoor"}


def _floor_ratio(state, fid):
    fl = state.floors.get(fid)
    if fl is not None and getattr(fl, "ratio", None) is not None:
        return fl.ratio
    path = ROOT / "data/games51/floors" / f"{fid}.json"
    return json.loads(path.read_text(encoding="utf-8")).get("ratio", 1)


def _reach_cells(state, fid, afford):
    """door-wise floodfill（守怪可穿·只看门墙）。返回 (seen_set, h, w) 或 None。"""
    info = _zone_floor_cells(state, fid, afford)
    if info is None:
        return None
    h, w, is_wall, _mid, _keys, src_cells = info
    seen, dq = set(), deque()
    for s in src_cells:
        if not is_wall(*s):
            seen.add(s)
            dq.append(s)
    while dq:
        x, y = dq.popleft()
        for dx, dy in _NB4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and not is_wall(nx, ny):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return seen, h, w


def _scan_supply(state, fid, cells):
    """在 cells 集合里扫 ATK/DEF 物品，返回 (atk_gain, def_gain, item_list)。"""
    ratio = _floor_ratio(state, fid)
    atk = dfn = 0
    items = []
    for (x, y) in cells:
        t = _floor_tile_at(state, fid, x, y)
        if t in RATIO_GEM:
            name, stat = RATIO_GEM[t]
            g = 1 * ratio
            if stat == "atk":
                atk += g
            else:
                dfn += g
            items.append((x, y, f"{name}(+{g}{stat})"))
        elif t == YELLOW_GEM:
            atk += 6
            dfn += 6
            items.append((x, y, "yellowGem(+6atk+6def+1000hp)"))
        elif t in SWORD_ATK:
            atk += SWORD_ATK[t]
            items.append((x, y, f"sword(+{SWORD_ATK[t]}atk)"))
        elif t in SHIELD_DEF:
            dfn += SHIELD_DEF[t]
            items.append((x, y, f"shield(+{SHIELD_DEF[t]}def)"))
    return atk, dfn, items


def _all_doors(state, fid):
    """该层所有门位置 {(x,y): door_name}（读静态 json map，全门 present）。"""
    path = ROOT / "data/games51/floors" / f"{fid}.json"
    grid = json.loads(path.read_text(encoding="utf-8")).get("map", [])
    out = {}
    for y, row in enumerate(grid):
        for x, t in enumerate(row):
            if t in DOOR_TILES:
                out[(x, y)] = DOOR_TILES[t]
    return out


def main():
    s = build_initial_state()
    tokens, _ = load_tokens()
    for t in tokens[:TOK_SHIELD + 1]:
        s = step(s, t)
    h = s.hero
    afford_real = _afford_colors(s)
    print("=" * 88)
    print(f"起点 tok{TOK_SHIELD}：{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"钥={ {k: v for k, v in h.keys.items() if v} }")
    print(f"破门前真实 afford（手里持有色）= {afford_real}   ← 无红钥，红门当墙")
    print(f"破门阈值（诊断①）：ATK25/DEF25/HP733 再要 +1ATK 或 +1DEF 或 +4HP")
    print("=" * 88)

    tot_real_a = tot_real_d = 0
    tot_full_a = tot_full_d = 0
    locked_items = []   # 锁在红/铁/机关门后的 ATK/DEF 物品

    for fid in REAL_LEG_FLOORS:
        ratio = _floor_ratio(s, fid)
        r_real = _reach_cells(s, fid, afford_real)
        r_full = _reach_cells(s, fid, _FULL_AFFORD)
        if r_real is None or r_full is None:
            print(f"\n[{fid}] _zone_floor_cells 返回 None（_floors_dir 未设？）→ 跳过")
            continue
        cells_real, _, _ = r_real
        cells_full, _, _ = r_full
        a_real, d_real, items_real = _scan_supply(s, fid, cells_real)
        a_full, d_full, items_full = _scan_supply(s, fid, cells_full)
        tot_real_a += a_real
        tot_real_d += d_real
        tot_full_a += a_full
        tot_full_d += d_full
        # 锁住的 = full 可达但 real 不可达的格里的物品
        locked_cells = cells_full - cells_real
        a_lock, d_lock, items_lock = _scan_supply(s, fid, locked_cells)
        doors = _all_doors(s, fid)
        ndoor = {}
        for nm in DOOR_TILES.values():
            c = sum(1 for v in doors.values() if v == nm)
            if c:
                ndoor[nm] = c
        print(f"\n[{fid}] ratio={ratio}  门={ndoor}")
        print(f"   破门前可达(door-wise·黄蓝)：ATK+{a_real} DEF+{d_real}  物品={items_real}")
        if items_lock:
            print(f"   ★锁在红/铁/机关门后(全门通才可达)：ATK+{a_lock} DEF+{d_lock}  物品={items_lock}")
            locked_items.extend((fid,) + it for it in items_lock)

    print("\n" + "=" * 88)
    print("【汇总】")
    print("=" * 88)
    print(f"9 层破门前 door-wise 可达(黄蓝门)总物量：ATK+{tot_real_a}  DEF+{tot_real_d}")
    print(f"  → 起点 ATK22/DEF20 理论可达上界：ATK≤{22 + tot_real_a}  DEF≤{20 + tot_real_d}")
    print(f"9 层全门通(含红/铁/机关门后)总物量：ATK+{tot_full_a}  DEF+{tot_full_d}")
    print(f"  → 锁在红/铁/机关门后的物量：ATK+{tot_full_a - tot_real_a}  DEF+{tot_full_d - tot_real_d}")
    print(f"\nbeam 实际攒到 ATK25(+3)/DEF25(+5)。破门要 ATK26 或 DEF26。")
    print(f"破门前可达上界 ATK={22 + tot_real_a} / DEF={20 + tot_real_d}：")
    margin_a = (22 + tot_real_a) - 26
    margin_d = (20 + tot_real_d) - 26
    print(f"  ATK 余量(上界-26) = {margin_a:+d}   DEF 余量(上界-26) = {margin_d:+d}")
    if margin_a >= 0 or margin_d >= 0:
        print("  ⟹ 物量【够】破门（door-wise 上界过 26）→ beam 没攒够是搜索力/战力问题 → 加力可能破。")
    else:
        print("  ⟹ 物量【不够】破门（door-wise 上界都到不了 26）→ 结构性死结、加力也没用。")
    if locked_items:
        print(f"\n★被锁物品明细（红/铁/机关门后·破门前够不到）：")
        for it in locked_items:
            print(f"    {it}")


if __name__ == "__main__":
    main()
