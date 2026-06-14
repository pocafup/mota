"""【fitness 标定·数据摸底探针】回放两条现成 route 到终态，打印 fitness 各项的真实尺度。

不是 fitness 实现，只是摸底：让我据【真实终态数据】（HP/atk/def/访问层/一区 roster 大小/地上
血瓶回血量/余钥匙）设计 fitness 各项权重，而不是凭空标。回放工具与 tests/test_ga_navigate 同源
（make_initial_state + decode_route）。一区 roster 用 build_future_roster 的 mon_cells 按 boss_idxs 切。
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step
from solver.beam import build_future_roster, equiv_hp_over_roster, _combat_damage
from solver.search import _gives_hp_on_pickup
from decode_route import parse_rle_route, decompress
from export_mt10_boss_route import make_initial_state
from probe_crossfloor import build_start


def replay(route_file):
    outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
    actions = parse_rle_route(decompress(outer["route"]))
    s = make_initial_state()
    for a in actions:
        s = step(s, a)
        if s.dead:
            break
    return s, len(actions)


def _hp_gain(idata):
    """血瓶名义回血量（数据驱动，items.json pickup）。stat 类取 base(ratio_scaled名义) 或 delta；
    multi 类取 ops 里 hp 的 delta。注：ratio_scaled=true 实际 gain=base×楼层ratio，这里用 base 名义值。"""
    if not idata:
        return 0
    e = idata.get("pickup")
    if not isinstance(e, dict):
        return 0
    if e.get("type") == "stat" and e.get("stat") == "hp":
        return e.get("base", e.get("delta", 0))
    if e.get("type") == "multi":
        return sum(op.get("delta", 0) for op in e.get("ops", ()) if op.get("stat") == "hp")
    return 0


def zone_potions(st, fr, boss0, fallback_dir):
    """一区各层地上剩余血瓶（已访问层读 entities 反映已捡；未访问层读 JSON 全剩）。
    返回 (总回血量, 总个数, {fid: (gain, cnt)})。"""
    floors_dir = getattr(st, "_floors_dir", None) or fallback_dir
    tte_item = st.floor._tile_to_item
    db = st.floor._items_db
    total_gain = total_cnt = 0
    detail = {}
    for idx in range(0, boss0 + 1):
        fid = fr["floor_ids"][idx]
        gain = cnt = 0
        fl = st.floors.get(fid)
        if fl is not None:                       # 已访问：读残留实体
            for row in fl.entities:
                for tile in row:
                    if tile:
                        iid = fl._tile_to_item.get(tile)
                        if iid and _gives_hp_on_pickup(fl._items_db.get(iid)):
                            gain += _hp_gain(fl._items_db.get(iid))
                            cnt += 1
        else:                                    # 未访问：读静态 JSON 全剩
            path = floors_dir / f"{fid}.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                for row in data.get("map", []):
                    for tile in row:
                        iid = tte_item.get(tile)
                        if iid and _gives_hp_on_pickup(db.get(iid)):
                            gain += _hp_gain(db.get(iid))
                            cnt += 1
        if cnt:
            detail[fid] = (gain, cnt)
        total_gain += gain
        total_cnt += cnt
    return total_gain, total_cnt, detail


def main():
    routes = {
        "120k_ab1(HP571)": ROOT / "route" / "alphabig1_route.h5route",
        "120k_ab07(HP583)": ROOT / "route" / "alphabig07_route.h5route",
        "480k_ab1(718耗尽)": ROOT / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route",
        "480k_ab07(689高潜力)": ROOT / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route",
    }

    # 一区 roster：用 build_start 态构造（mon_cells 静态、boss_idxs 结构性，与评谁无关）
    s0, _ = build_start()
    fr = build_future_roster(s0)
    fallback_dir = s0._floors_dir
    boss0 = fr["boss_idxs"][0] if fr["boss_idxs"] else fr["max_idx"]
    print("floor_ids:", fr["floor_ids"])
    print(f"boss_idxs={fr['boss_idxs']}  一区=idx[0..{boss0}] = "
          f"{fr['floor_ids'][0]}..{fr['floor_ids'][boss0]}")

    zone1_roster = {}
    for idx in range(0, boss0 + 1):
        for (x, y, mid) in fr["mon_cells"].get(idx, []):
            zone1_roster[(idx, x, y)] = mid
    full_roster = {}
    for idx, cells in fr["mon_cells"].items():
        for (x, y, mid) in cells:
            full_roster[(idx, x, y)] = mid
    print(f"一区静态怪数={len(zone1_roster)}  全塔静态怪数={len(full_roster)}")
    from collections import Counter
    print(f"一区怪 mid 分布={dict(Counter(zone1_roster.values()))}")

    # 回放两条 route
    finals = {}
    for name, rf in routes.items():
        s, n = replay(rf)
        finals[name] = s
        h = s.hero
        print(f"\n=== {name} ===  ({n} actions)")
        print(f" floor={s.current_floor} dead={s.dead} won={s.won}")
        print(f" HP={h.hp} ATK={h.atk} DEF={h.def_} MDEF={h.mdef} "
              f"gold={h.gold} kill={h.kill_count}")
        print(f" keys={dict(h.keys)} items={dict(h.items)}")
        print(f" visited_floors={sorted(s.visited_floors)}")
        print(f" has _floors_dir={hasattr(s, '_floors_dir')}")

    # big 标定：两终态（+起点）对一区 roster 的最大可杀损血
    def calc_big(states, roster):
        big = 0
        for st in states:
            hp = st.hero.hp
            for mid in roster.values():
                d = _combat_damage(st, mid)
                if d is not None and d < hp and d > big:
                    big = d
        return big

    big_finals = calc_big(list(finals.values()), zone1_roster)
    big_all = calc_big(list(finals.values()) + [s0], zone1_roster)
    print(f"\nbig(两终态/一区roster)={big_finals}  big(含起点)={big_all}")

    print("\n— 主干 equiv_hp_over_roster（一区roster, future=None）—")
    for big in sorted({big_finals, big_all}):
        for name, s in finals.items():
            v = equiv_hp_over_roster(s, zone1_roster, big)
            print(f" big={big:>5}  equiv_hp[{name}] = {v}")

    print("\n— 一区地上剩余血瓶（潜力项原料）—")
    for name, s in finals.items():
        gain, cnt, detail = zone_potions(s, fr, boss0, fallback_dir)
        print(f" [{name}] 总回血={gain} 个数={cnt} 分层={detail}")

    print("\n— 余钥匙（第一版=计数×小权重）—")
    for name, s in finals.items():
        keys = {k: v for k, v in s.hero.keys.items() if isinstance(v, (int, float))}
        print(f" [{name}] keys={keys} 总数={sum(keys.values())}")


if __name__ == "__main__":
    main()
