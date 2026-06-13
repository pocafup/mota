"""【只读·逐里程碑标注】把 4 条 α 路线(bb25_gd1w, α∈{1,0.7,0.5,0.3})各自的 best-MT10 区段
重放真引擎，逐步 diff 出里程碑：换层 / 拿装备 / 拿宝石 / 拿血瓶 / 拿钥匙 / 拿道具 / 开门 / 打怪，
每条标 region步(0基) + 网站tok(=83+region步) + 层 + 坐标 + 动作 + HP/ATK/DEF + 持钥。
专项：①剑(MT5,11,11)/盾(MT9,9,7) 各第几步拿、剑盾之间小宝石；②MT8 门后物品拿没拿(对照α)；
③MT7 所有开门(找"三史莱姆门、盾已拿、不增通路"那个无理由开门)；④HP 烧在哪(战斗/地形损血明细)。
不改产品码、不调参、不喂走法。每条写出 route_milestones_a{α}.md 全量里程碑；控制台打横向对比。

跑法：python -u extract/route_milestones.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, DOOR_KEY_MAP, load_floor
from probe_crossfloor import build_start, OPENING_PREFIX
from export_bscan_routes import load_rows, pick_best_mt10
from vzone import build_zone

HERE = Path(__file__).parent
FLOORS_DIR = HERE.parent / "data" / "games51" / "floors"

ROUTES = [
    ("1",   "crossbeam_floorbest_K200_bb25_gd1w_lam0.2_stairs.jsonl"),
    ("0.7", "crossbeam_floorbest_K200_bb25_gd1w_a0.7_lam0.2_stairs.jsonl"),
    ("0.5", "crossbeam_floorbest_K200_bb25_gd1w_a0.5_lam0.2_stairs.jsonl"),
    ("0.3", "crossbeam_floorbest_K200_bb25_gd1w_a0.3_lam0.2_stairs.jsonl"),
]

DOOR_CN = {81: "黄门", 82: "蓝门", 83: "红门", 84: "绿门", 85: "特殊门", 86: "铁门"}
KEY_CN = {"yellowKey": "黄", "blueKey": "蓝", "redKey": "红",
          "greenKey": "绿", "steelKey": "铁", "bigKey": "魔法"}
SWORD_CELL = ("MT5", 11, 11)
SHIELD_CELL = ("MT9", 9, 7)


def item_cat(iid):
    if iid.endswith("Key"):
        return "钥匙"
    if iid.endswith("Gem"):
        return "宝石"
    if iid.endswith("Potion"):
        return "血瓶"
    if iid.startswith("sword"):
        return "剑"
    if iid.startswith("shield"):
        return "盾"
    return "道具"


def held_keys(h):
    parts = [f"{KEY_CN.get(k, k)}{v}" for k, v in h.keys.items() if v]
    return "".join(parts) if parts else "—"


def load_fresh(fid):
    return load_floor(FLOORS_DIR / f"{fid}.json")


def dump_floor(fid):
    fl = load_fresh(fid)
    print(f"\n=== {fid} 原始内容 ===")
    mons, items, doors = [], [], []
    for y, row in enumerate(fl.entities):
        for x, t in enumerate(row):
            mid = fl._tile_to_enemy.get(t)
            if mid is not None:
                mons.append((x, y, fl._monsters_db.get(mid, {}).get("name", mid)))
            iid = fl._tile_to_item.get(t)
            if iid is not None:
                items.append((x, y, iid, fl._items_db.get(iid, {}).get("name", iid)))
    for y, row in enumerate(fl.terrain):
        for x, t in enumerate(row):
            if t in DOOR_CN:
                doors.append((x, y, DOOR_CN[t]))
    print("  怪：" + ("  ".join(f"({x},{y}){n}" for x, y, n in mons) if mons else "无"))
    print("  道具：" + ("  ".join(f"({x},{y}){n}[{item_cat(i)}]" for x, y, i, n in items) if items else "无"))
    print("  门：" + ("  ".join(f"({x},{y}){d}" for x, y, d in doors) if doors else "无"))
    return fl


def best_region_actions(zone, start, src):
    rows = load_rows(src)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        return None, None
    best_row, _sfin, _vz, _D = pick_best_mt10(zone, start, mt10)
    return list(best_row["actions"]), best_row


def replay_milestones(start, actions):
    """逐步 diff，返回 (milestones, final_state, hp_stats)。"""
    s = _copy_state(start)
    ms = []
    combat_loss = terrain_loss = heal_gain = 0
    fights = []          # (step, floor, x, y, name, dmg)
    floor_seq = [s.current_floor]
    for i, a in enumerate(actions):  # 0-based region step
        before = s
        bf = before.current_floor
        bh = before.hero
        bhp = bh.hp
        s = step(before, a)
        af = s.current_floor
        ah = s.hero
        recs = []
        if af != bf:
            recs.append(("换层", f"{bf}→{af}", ah.x, ah.y, None))
            if not floor_seq or floor_seq[-1] != af:
                floor_seq.append(af)
        else:
            bfl = before.floors[bf]
            afl = s.floors[bf]
            for y in range(len(bfl.entities)):
                brow, arow = bfl.entities[y], afl.entities[y]
                for x in range(len(brow)):
                    if brow[x] and not arow[x]:
                        tile = brow[x]
                        mid = bfl._tile_to_enemy.get(tile)
                        if mid is not None:
                            recs.append(("打怪", bfl._monsters_db.get(mid, {}).get("name", mid), x, y, None))
                        else:
                            iid = bfl._tile_to_item.get(tile, str(tile))
                            recs.append((item_cat(iid), bfl._items_db.get(iid, {}).get("name", iid), x, y, iid))
            for y in range(len(bfl.terrain)):
                brow, arow = bfl.terrain[y], afl.terrain[y]
                for x in range(len(brow)):
                    if brow[x] != arow[x] and brow[x] in DOOR_CN and arow[x] == 0:
                        recs.append(("开门", DOOR_CN[brow[x]], x, y, None))
        step_dhp = ah.hp - bhp
        is_fight = any(r[0] == "打怪" for r in recs)
        if is_fight and step_dhp < 0:
            combat_loss += -step_dhp
            for r in recs:
                if r[0] == "打怪":
                    fights.append((i, bf, r[2], r[3], r[1], -step_dhp))
        elif step_dhp < 0:
            terrain_loss += -step_dhp
        elif step_dhp > 0:
            heal_gain += step_dhp
        for (typ, label, x, y, iid) in recs:
            ms.append(dict(step=i, tok=OPENING_PREFIX + i, floor=bf, x=x, y=y,
                           typ=typ, label=label, iid=iid, hp=ah.hp, atk=ah.atk,
                           df=ah.def_, dhp=step_dhp, keys=held_keys(ah), act=a))
    return ms, s, dict(combat=combat_loss, terrain=terrain_loss, heal=heal_gain,
                       fights=fights, floor_seq=floor_seq)


def write_md(alpha, src_name, region_n, best_row, ms, hp):
    out = HERE.parent / f"route_milestones_a{alpha}.md"
    L = []
    L.append(f"# α={alpha} 逐里程碑（源 {src_name}）\n")
    L.append(f"- best-MT10 末态：{best_row['floor']} HP={best_row['hp']} ATK={best_row['atk']} "
             f"DEF={best_row['def']}；region 段 {region_n} 步（网站 spliced = 前缀83 + region步）")
    L.append(f"- HP 账：战斗损血 {hp['combat']}  地形/区域损血 {hp['terrain']}  回血 {hp['heal']}")
    L.append(f"- 层序：{' → '.join(hp['floor_seq'])}\n")
    L.append("| region步 | 网站tok | 层 | 坐标 | 类型 | 内容 | 动作 | HP | ATK | DEF | ΔHP | 持钥 |")
    L.append("|---:|---:|:--|:--|:--|:--|:--:|---:|---:|---:|---:|:--|")
    for m in ms:
        L.append(f"| {m['step']} | {m['tok']} | {m['floor']} | ({m['x']},{m['y']}) | {m['typ']} | "
                 f"{m['label']} | {m['act']} | {m['hp']} | {m['atk']} | {m['df']} | "
                 f"{m['dhp']:+d} | {m['keys']} |")
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def main():
    start = build_start()[0]
    zone = build_zone()

    print("=" * 96)
    print("参考：相关楼层原始内容（剑MT5 / 盾MT9 / 门后谷MT8 / 无理由开门MT7）")
    print("=" * 96)
    for fid in ("MT5", "MT7", "MT8", "MT9"):
        dump_floor(fid)

    # MT8 门后物品原始清单（用于"拿没拿"对照）
    mt8 = load_fresh("MT8")
    mt8_items = []
    for y, row in enumerate(mt8.entities):
        for x, t in enumerate(row):
            iid = mt8._tile_to_item.get(t)
            if iid is not None:
                mt8_items.append((x, y, iid, mt8._items_db.get(iid, {}).get("name", iid)))

    results = {}
    for alpha, name in ROUTES:
        src = HERE / name
        actions, best_row = best_region_actions(zone, start, src)
        if actions is None:
            print(f"\n⚠ α={alpha} 源 {name} 无 MT10 行，跳过")
            continue
        ms, final, hp = replay_milestones(start, actions)
        md = write_md(alpha, name, len(actions), best_row, ms, hp)
        # 专项标记
        sword_step = next((m["step"] for m in ms if m["floor"] == SWORD_CELL[0]
                           and (m["x"], m["y"]) == SWORD_CELL[1:] and m["typ"] == "剑"), None)
        shield_step = next((m["step"] for m in ms if m["floor"] == SHIELD_CELL[0]
                            and (m["x"], m["y"]) == SHIELD_CELL[1:] and m["typ"] == "盾"), None)
        between = []
        if sword_step is not None and shield_step is not None and shield_step > sword_step:
            between = [m for m in ms if m["typ"] == "宝石" and sword_step < m["step"] < shield_step]
        mt7_doors = [m for m in ms if m["floor"] == "MT7" and m["typ"] == "开门"]
        mt8_events = [m for m in ms if m["floor"] == "MT8"]
        # MT8 门后物品拿没拿：对照原始清单与终态 entities
        mt8_final = final.floors.get("MT8")
        mt8_taken = []
        for x, y, iid, nm in mt8_items:
            taken = mt8_final is not None and mt8_final.entities[y][x] == 0
            mt8_taken.append((x, y, nm, item_cat(iid), taken))
        results[alpha] = dict(md=md, ms=ms, hp=hp, sword=sword_step, shield=shield_step,
                              between=between, mt7=mt7_doors, mt8=mt8_events, mt8_taken=mt8_taken,
                              best=best_row, n=len(actions), final=final)

    # ── 横向对比 ──
    print("\n" + "=" * 96)
    print("【横向对比】剑/盾/剑盾间宝石")
    print("=" * 96)
    for alpha, _ in ROUTES:
        r = results.get(alpha)
        if not r:
            continue
        bn = "、".join(f"{m['floor']}({m['x']},{m['y']}){m['label']}@step{m['step']}" for m in r["between"]) or "无"
        print(f"\nα={alpha}: 剑@step{r['sword']}  盾@step{r['shield']}  "
              f"剑盾间宝石{len(r['between'])}个 → {bn}")

    print("\n" + "=" * 96)
    print("【横向对比】MT8 门后物品 拿没拿（原始清单逐件对照终态）")
    print("=" * 96)
    for alpha, _ in ROUTES:
        r = results.get(alpha)
        if not r:
            continue
        cells = "  ".join(f"({x},{y}){nm}[{cat}]:{'拿✓' if tk else '弃✗'}"
                          for x, y, nm, cat, tk in r["mt8_taken"])
        print(f"α={alpha}: {cells}")
        if r["mt8"]:
            print("    MT8 里程碑：" + "  ".join(
                f"step{m['step']}({m['x']},{m['y']}){m['typ']}{m['label']}" for m in r["mt8"]))
        else:
            print("    MT8 里程碑：无（这条没在 MT8 拿/开任何东西）")

    print("\n" + "=" * 96)
    print("【横向对比】MT7 开门（找无理由开门：三史莱姆门、盾已拿、不增通路）")
    print("=" * 96)
    for alpha, _ in ROUTES:
        r = results.get(alpha)
        if not r:
            continue
        if r["mt7"]:
            for m in r["mt7"]:
                print(f"α={alpha}: MT7开门 step{m['step']}(网站tok{m['tok']}) ({m['x']},{m['y']}){m['label']} "
                      f"动作{m['act']} HP={m['hp']} 持钥{m['keys']}")
        else:
            print(f"α={alpha}: MT7 无开门")

    print("\n" + "=" * 96)
    print("【横向对比】HP 烧在哪（爬到 MT10 末态 + 战斗/地形损血 + 最大几次战斗）")
    print("=" * 96)
    print(f"{'α':>5} {'末态HP':>7} {'战斗损血':>9} {'地形损血':>9} {'回血':>7} {'region步':>9} {'换层数':>7}")
    for alpha, _ in ROUTES:
        r = results.get(alpha)
        if not r:
            continue
        b = r["best"]
        print(f"{alpha:>5} {b['hp']:>7} {r['hp']['combat']:>9} {r['hp']['terrain']:>9} "
              f"{r['hp']['heal']:>7} {r['n']:>9} {len(r['hp']['floor_seq'])-1:>7}")
    for alpha, _ in ROUTES:
        r = results.get(alpha)
        if not r:
            continue
        top = sorted(r["hp"]["fights"], key=lambda f: -f[5])[:6]
        tt = "  ".join(f"{fl}({x},{y}){nm}:-{d}" for (_st, fl, x, y, nm, d) in top)
        print(f"\nα={alpha} 最烧血的几场：{tt}")
        print(f"  层序：{' → '.join(r['hp']['floor_seq'])}")

    print("\n" + "=" * 96)
    print("已写出 4 条全量里程碑 .md：")
    for alpha, _ in ROUTES:
        r = results.get(alpha)
        if r:
            print(f"  {r['md'].name}（{len(r['ms'])} 条里程碑）")


if __name__ == "__main__":
    main()
