"""扩层第二批 MT21-MT28（楼梯路过层）提取+逐格校验+连通报告。

用法：
    python gen_verify_mt2x.py 21 22 23 24 25 26 27 28
    python gen_verify_mt2x.py 21          # 只处理 MT21

数据源：extract/mt21_28_raw_combined.json（live engine 一次性 dump，double-encoded）。
本脚本把每层拆成 extract/mtNN_raw_capture.json（沿用既有约定），再生成
data/games51/floors/MTNN.json，并对 map 逐格比对 raw。任一层 >0 不一致或出现未知 tile
即 STOP，不再处理后续层（呼应"0处才继续下一层"）。
"""
import sys, json, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
EXTRACT = ROOT / "extract"
COMBINED = EXTRACT / "mt21_28_raw_combined.json"

tiles_db = json.loads((DATA / "tiles.json").read_text(encoding="utf-8"))
floor_ids = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

DOOR_IDS  = {"yellowDoor","blueDoor","redDoor","greenDoor","specialDoor","steelDoor"}
STAIR_IDS = {"upFloor","downFloor"}


def load_combined():
    t = COMBINED.read_text(encoding="utf-8").strip()
    return json.loads(json.loads(t)) if t.startswith('"') else json.loads(t)


def build_entities(floor_map):
    enemy_map   = {int(k): v["id"] for k, v in tiles_db["enemys"].items()}
    item_map    = {int(k): v["id"] for k, v in tiles_db["items"].items()}
    npc_map     = {int(k): v["id"] for k, v in tiles_db["npcs"].items()}
    terrain_map = {int(k): v["id"] for k, v in tiles_db["terrains"].items()}
    animate_map = {int(k): v["id"] for k, v in tiles_db["animates"].items()}
    monsters, items, doors, fakes, stairs, npcs = {}, {}, {}, {}, {}, {}
    unknown = []
    for y, row in enumerate(floor_map):
        for x, cell in enumerate(row):
            if cell in (0, 1): continue
            pos = f"({x},{y})"
            if   cell in enemy_map:   monsters.setdefault(f"{enemy_map[cell]}({cell})", []).append(pos)
            elif cell in item_map:    items.setdefault(f"{item_map[cell]}({cell})", []).append(pos)
            elif cell in npc_map:     npcs.setdefault(f"{npc_map[cell]}({cell})", []).append(pos)
            elif cell in terrain_map:
                tid = terrain_map[cell]
                (stairs if tid in STAIR_IDS else npcs).setdefault(f"{tid}({cell})", []).append(pos)
            elif cell in animate_map:
                aid = animate_map[cell]
                (doors if aid in DOOR_IDS else fakes).setdefault(f"{aid}({cell})", []).append(pos)
            else:
                unknown.append((x, y, cell))
    out = {"_comment": "从 map 推导的实体位置，模拟器从 map+tiles.json 动态解析。"}
    if monsters: out["monsters"] = monsters
    if items:    out["items"]    = items
    if doors:    out["doors"]    = doors
    if fakes:    out["fakes"]    = fakes
    if npcs:     out["npcs_terrain"] = npcs
    if stairs:   out["stairs_terrain"] = stairs
    return out, unknown


def compact(s):
    def _c(m):
        nums = re.split(r',\s*', m.group(1).strip())
        return ('['+', '.join(n.strip() for n in nums if n.strip())+']'
                if all(re.fullmatch(r'-?\d+', n.strip()) for n in nums if n.strip())
                else m.group(0))
    return re.sub(r'\[\s*((?:-?\d+,?\s*)+)\]', _c, s)


def resolve_floor(cur_id, expr):
    if not expr.startswith(":"):
        return expr
    idx = floor_ids.index(cur_id)
    if expr == ":next":  return floor_ids[idx + 1]
    if expr == ":before": return floor_ids[idx - 1]
    return expr


def landing_coord(target_id, stair, all_raw):
    """目标层落点坐标：踩楼梯后落到 target 的 downFloor/upFloor。"""
    src = all_raw.get(target_id)
    if src is None:
        p = FLOORS / f"{target_id}.json"
        if p.exists():
            src = json.loads(p.read_text(encoding="utf-8"))
        else:
            return None
    return src.get("downFloor") if stair == "downFloor" else src.get("upFloor")


def gen_one(fid, raw, all_raw):
    # 1) 写 per-floor raw_capture（沿用约定，faithful dump）
    (EXTRACT / f"{fid.lower()}_raw_capture.json").write_text(
        json.dumps(json.dumps(raw, ensure_ascii=False), ensure_ascii=False), encoding="utf-8")

    entities, unknown = build_entities(raw["map"])
    out = {
        "_comment": f"来源: core.floors['{fid}'] (live engine, Playwright 提取)。events 存原始 h5mota 脚本。",
        "floorId": raw["floorId"], "title": raw["title"],
        "width": raw["width"], "height": raw["height"],
        "ratio": raw["ratio"], "bgm": raw["bgm"],
        "downFloor": raw["downFloor"], "upFloor": raw["upFloor"],
        "_map_note": "map[y][x]，0=地板，1=墙。tile ID 含义见 tiles.json。",
        "map": raw["map"], "_map_entities": entities,
        "changeFloor": raw.get("changeFloor", {}), "events": raw.get("events", {}),
        "firstArrive": raw.get("firstArrive", []), "eachArrive": raw.get("eachArrive", []),
        "afterGetItem": raw.get("afterGetItem", {}), "afterBattle": raw.get("afterBattle", {}),
        "autoEvent": raw.get("autoEvent", {}), "afterOpenDoor": raw.get("afterOpenDoor", {}),
        "cannotMove": raw.get("cannotMove", {}),
    }
    out_path = FLOORS / f"{fid}.json"
    out_path.write_text(compact(json.dumps(out, ensure_ascii=False, indent=2)), encoding="utf-8")

    # 2) 逐格校验：raw["map"] vs 写盘后 MTNN.json 的 map
    gen = json.loads(out_path.read_text(encoding="utf-8"))["map"]
    src = raw["map"]
    H, W = raw["height"], raw["width"]
    errs = [(x, y, src[y][x], gen[y][x])
            for y in range(H) for x in range(W) if src[y][x] != gen[y][x]]
    return errs, unknown, entities, out_path


def report(fid, raw, errs, unknown, entities, all_raw):
    print(f"\n{'='*64}\n  {fid}  «{raw['title']}»  ratio={raw['ratio']}  bgm={raw['bgm']}")
    print(f"  canFlyTo={raw.get('canFlyTo')}  canFlyFrom={raw.get('canFlyFrom')}")
    print(f"  逐格校验: {'✅ 0 处不一致' if not errs else f'⚠ {len(errs)} 处不一致'}")
    for x, y, s, g in errs: print(f"      ({x},{y}): 源={s} gen={g}")
    if unknown:
        print(f"  ⚠⚠ 未知 tile {len(unknown)} 处（停下待确认）:")
        for x, y, c in unknown: print(f"      ({x},{y}) = tile {c}")

    print(f"  —— 楼梯连通 ——")
    print(f"  downFloor(落点字段)={raw['downFloor']}  upFloor(落点字段)={raw['upFloor']}")
    for k, cf in raw.get("changeFloor", {}).items():
        tgt = resolve_floor(fid, cf["floorId"])
        land = landing_coord(tgt, cf["stair"], all_raw)
        land_s = f"{tgt}{land}" if land else f"{tgt}(未提取,落点未知)"
        print(f"    踩({k}) [{cf['floorId']}→{tgt}] stair={cf['stair']:9} → 落到 {land_s}")
    st = entities.get("stairs_terrain", {})
    if st: print(f"    楼梯图块: {st}")

    print(f"  —— NPC / 实体 ——")
    npcs = entities.get("npcs_terrain", {})
    interest = {k: v for k, v in npcs.items()
                if any(t in k for t in ("oldman", "trader", "blueShop"))}
    print(f"    老人/商人/祭坛: {interest if interest else '无'}")
    other_npc = {k: v for k, v in npcs.items() if k not in interest}
    if other_npc: print(f"    其他NPC地形: {other_npc}")
    print(f"    怪物: {entities.get('monsters', {}) or '无'}")
    print(f"    道具: {entities.get('items', {}) or '无'}")
    print(f"    门: {entities.get('doors', {}) or '无'}")
    if entities.get("fakes"): print(f"    假墙/其他animate: {entities['fakes']}")
    lava = [(x, y) for y, r in enumerate(raw["map"]) for x, v in enumerate(r) if v == 5]
    print(f"    岩浆: {('有: ' + str(lava)) if lava else '无'}")

    print(f"  —— 事件 ——")
    for fld in ("events", "afterBattle", "autoEvent", "afterGetItem", "afterOpenDoor"):
        d = raw.get(fld, {})
        if d: print(f"    {fld}: keys={list(d.keys())}")
    for fld in ("firstArrive", "eachArrive"):
        lst = raw.get(fld, [])
        if lst: print(f"    {fld}: {lst}")
    if not any(raw.get(f) for f in
               ("events","afterBattle","autoEvent","afterGetItem","afterOpenDoor","firstArrive","eachArrive")):
        print(f"    （全空，纯路过层）")


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python gen_verify_mt2x.py 21 [22 ...]"); return
    all_raw = load_combined()
    for a in args:
        fid = f"MT{a}"
        if fid not in all_raw:
            print(f"⚠ {fid} 不在 combined dump 中，跳过"); continue
        raw = all_raw[fid]
        errs, unknown, entities, out_path = gen_one(fid, raw, all_raw)
        report(fid, raw, errs, unknown, entities, all_raw)
        print(f"  写入: {out_path}")
        if errs or unknown:
            print(f"\n🛑 {fid} 校验未过（{len(errs)}处不一致 / {len(unknown)}未知tile），STOP，不再处理后续层。")
            sys.exit(1)
    print(f"\n✅ 全部完成：{', '.join('MT'+a for a in args)} 均 0 处不一致、无未知 tile。")


if __name__ == "__main__":
    main()
