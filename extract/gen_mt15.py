"""
Generate data/games51/floors/MT15.json from extract/mt15_raw_capture.json.
Same pipeline as gen_floors.py but for single-floor raw capture files.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"
EXTRACT = ROOT / "extract"

tiles_db = json.loads((DATA / "tiles.json").read_text(encoding="utf-8"))


def build_reverse_maps(tiles_db):
    enemy_map   = {int(k): v["id"] for k, v in tiles_db["enemys"].items()}
    item_map    = {int(k): v["id"] for k, v in tiles_db["items"].items()}
    door_map    = {int(k): v["id"] for k, v in tiles_db["animates"].items()
                   if v["id"] in ("yellowDoor","blueDoor","redDoor","greenDoor","specialDoor","steelDoor")}
    terrain_map = {int(k): v["id"] for k, v in tiles_db["terrains"].items()}
    npc_map     = {int(k): v["id"] for k, v in tiles_db["npcs"].items()}
    wall_map    = {int(k): v["id"] for k, v in tiles_db["animates"].items()
                   if v.get("noPass") and v["id"] not in ("yellowDoor","blueDoor","redDoor","greenDoor","specialDoor","steelDoor")}
    return enemy_map, item_map, door_map, terrain_map, npc_map, wall_map


def compute_map_entities(floor_map, enemy_map, item_map, door_map, terrain_map, npc_map, wall_map):
    monsters = {}
    items    = {}
    doors    = {}
    terrains = {}
    npcs     = {}
    unknowns = {}

    known_passable = {0, 1, 4, 5}  # floor, wall, airwall, lava — handled by simulator

    for y, row in enumerate(floor_map):
        for x, cell in enumerate(row):
            if cell in (0, 1, 4, 5):
                continue
            pos = f"({x},{y})"
            if cell in enemy_map:
                mid = f"{enemy_map[cell]}({cell})"
                monsters.setdefault(mid, []).append(pos)
            elif cell in item_map:
                iid = f"{item_map[cell]}({cell})"
                items.setdefault(iid, []).append(pos)
            elif cell in door_map:
                did = f"{door_map[cell]}({cell})"
                doors.setdefault(did, []).append(pos)
            elif cell in terrain_map:
                tid = f"{terrain_map[cell]}({cell})"
                terrains.setdefault(tid, []).append(pos)
            elif cell in npc_map:
                nid = f"{npc_map[cell]}({cell})"
                npcs.setdefault(nid, []).append(pos)
            elif cell in wall_map:
                wid = f"{wall_map[cell]}({cell})"
                doors.setdefault(wid, []).append(pos)
            else:
                unknowns.setdefault(str(cell), []).append(pos)

    result = {}
    if monsters: result["monsters"] = monsters
    if items:    result["items"]    = items
    if doors:    result["doors"]    = doors
    if terrains: result["terrains"] = terrains
    if npcs:     result["npcs"]     = npcs
    if unknowns:
        result["_unknown_tiles"] = unknowns
        print(f"  WARNING: unknown tile IDs: {list(unknowns.keys())}")
    return result


def build_floor_json(floor_id, raw):
    maps = build_reverse_maps(tiles_db)
    enemy_map, item_map, door_map, terrain_map, npc_map, wall_map = maps
    entities = compute_map_entities(
        raw["map"], enemy_map, item_map, door_map, terrain_map, npc_map, wall_map
    )

    lava_tiles = []
    for y, row in enumerate(raw["map"]):
        for x, cell in enumerate(row):
            if cell == 5:
                lava_tiles.append([x, y])

    out = {
        "_comment": (
            f"来源: core.floors['{floor_id}'] (live engine, Playwright capture)。"
            "events/afterBattle 等字段存原始 h5mota 脚本，不翻译。"
        ),
        "floorId":  raw["floorId"],
        "title":    raw["title"],
        "width":    raw["width"],
        "height":   raw["height"],
        "ratio":    raw["ratio"],
        "bgm":      raw["bgm"],
        "_map_note": "map[y][x]，0=地板，1=墙。tile ID 含义见 tiles.json。",
        "map":      raw["map"],
    }
    if entities:
        out["_map_entities"] = {
            "_comment": "从 map 数组推导的实体位置，便于阅读。模拟器从 map + tiles.json 动态解析，不从此字段读取。",
            **entities,
        }
    else:
        out["_map_entities"] = {"_comment": "无实体（全为地板/墙）"}

    out["changeFloor"]   = raw.get("changeFloor", {})
    out["events"]        = raw.get("events", {})
    out["firstArrive"]   = raw.get("firstArrive", [])
    out["eachArrive"]    = raw.get("eachArrive", [])
    out["parallelDo"]    = raw.get("parallelDo", "")
    out["afterGetItem"]  = raw.get("afterGetItem", {})
    out["afterBattle"]   = raw.get("afterBattle", {})
    out["afterOpenDoor"] = raw.get("afterOpenDoor", {})
    out["cannotMove"]    = raw.get("cannotMove", {})

    if lava_tiles:
        out["_lava_tiles"] = lava_tiles
        out["_lava_note"]  = f"{floor_id} 有 {len(lava_tiles)} 格血网地形（tile 5）"
    else:
        out["_lava_tiles"] = []
        out["_lava_note"]  = f"{floor_id} 无血网地形（tile 5）"

    return out


def load_raw(path):
    raw_text = path.read_text(encoding="utf-8").strip()
    if raw_text.startswith('"'):
        return json.loads(json.loads(raw_text))
    return json.loads(raw_text)


def compact_numeric_arrays(json_str):
    def compact(m):
        inner = m.group(1)
        nums = re.split(r',\s*', inner.strip())
        if all(re.fullmatch(r'-?\d+', n.strip()) for n in nums if n.strip()):
            return '[' + ', '.join(n.strip() for n in nums if n.strip()) + ']'
        return m.group(0)
    return re.sub(r'\[\s*((?:-?\d+,?\s*)+)\]', compact, json_str)


floors_dir = DATA / "floors"
floors_dir.mkdir(parents=True, exist_ok=True)

raw = load_raw(EXTRACT / "mt15_raw_capture.json")
floor_id = raw["floorId"]  # "MT15"

floor_json = build_floor_json(floor_id, raw)
out_path = floors_dir / f"{floor_id}.json"

raw_str = json.dumps(floor_json, ensure_ascii=False, indent=2)
raw_str = compact_numeric_arrays(raw_str)

with open(out_path, "w", encoding="utf-8") as f:
    f.write(raw_str)

entities = floor_json.get("_map_entities", {})
monsters = entities.get("monsters", {})
items    = entities.get("items", {})
doors    = entities.get("doors", {})
print(f"  {floor_id}: wrote {out_path}")
print(f"  monsters: {list(monsters.keys())}")
print(f"  items:    {list(items.keys())}")
print(f"  doors:    {list(doors.keys())}")
print("Done.")
