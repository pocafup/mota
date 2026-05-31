"""
Generate data/games51/floors/MT2-MT10.json from raw engine captures.
Also builds _map_entities annotation like MT1.json.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"
EXTRACT = ROOT / "extract"

# Load tile mappings (for _map_entities annotation)
tiles_db = json.loads((DATA / "tiles.json").read_text(encoding="utf-8"))

def build_reverse_maps(tiles_db):
    enemy_map   = {int(k): v["id"] for k, v in tiles_db["enemys"].items()}
    item_map    = {int(k): v["id"] for k, v in tiles_db["items"].items()}
    door_map    = {int(k): v["id"] for k, v in tiles_db["animates"].items()
                   if v["id"] in ("yellowDoor","blueDoor","redDoor","greenDoor","specialDoor","steelDoor")}
    terrain_map = {int(k): v["id"] for k, v in tiles_db["terrains"].items()}
    npc_map     = {int(k): v["id"] for k, v in tiles_db["npcs"].items()}
    return enemy_map, item_map, door_map, terrain_map, npc_map

def compute_map_entities(floor_map, enemy_map, item_map, door_map, terrain_map, npc_map):
    monsters  = {}
    items     = {}
    doors     = {}
    terrains  = {}
    npcs      = {}

    for y, row in enumerate(floor_map):
        for x, cell in enumerate(row):
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

    result = {}
    if monsters: result["monsters"] = monsters
    if items:    result["items"]    = items
    if doors:    result["doors"]    = doors
    if terrains: result["terrains"] = terrains
    if npcs:     result["npcs"]     = npcs
    return result

def build_floor_json(floor_id, raw):
    enemy_map, item_map, door_map, terrain_map, npc_map = build_reverse_maps(tiles_db)
    entities = compute_map_entities(raw["map"], enemy_map, item_map, door_map, terrain_map, npc_map)

    out = {
        "_comment": f"来源: core.floors['{floor_id}'] (live engine)。events/firstArrive/afterGetItem/afterBattle 存原始 h5mota 脚本，不翻译。",
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
            **entities
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
    out["_lava_tiles"]   = []
    out["_lava_note"]    = f"{floor_id} 无血网地形（tile 5）"
    return out

def process_file(raw_file):
    text = raw_file.read_text(encoding="utf-8").strip().strip('"')
    # The file contains a JSON string (double-escaped), unescape it
    data = json.loads(json.loads(f'"{text}"') if not text.startswith("{") else text)
    return data

# Parse raw files
def load_raw(path):
    raw_text = path.read_text(encoding="utf-8").strip()
    # Files contain a JSON string literal (quoted), parse accordingly
    if raw_text.startswith('"'):
        return json.loads(json.loads(raw_text))
    return json.loads(raw_text)

floors_dir = DATA / "floors"
floors_dir.mkdir(parents=True, exist_ok=True)

for raw_file, floor_range in [
    (EXTRACT / "mt2_5_raw.txt",  range(2, 6)),
    (EXTRACT / "mt6_10_raw.txt", range(6, 11)),
]:
    all_floors = load_raw(raw_file)
    for n in floor_range:
        fid = f"MT{n}"
        if fid not in all_floors or all_floors[fid] is None:
            print(f"WARNING: {fid} not found in {raw_file.name}")
            continue
        raw = all_floors[fid]
        floor_json = build_floor_json(fid, raw)
        out_path = floors_dir / f"{fid}.json"
        import re
        raw_str = json.dumps(floor_json, ensure_ascii=False, indent=2)
        # Compact numeric-only arrays (map rows) onto a single line
        def compact_numeric_array(m):
            inner = m.group(1)
            nums = re.split(r',\s*', inner.strip())
            if all(re.fullmatch(r'-?\d+', n.strip()) for n in nums if n.strip()):
                return '[' + ', '.join(n.strip() for n in nums if n.strip()) + ']'
            return m.group(0)
        raw_str = re.sub(r'\[\s*((?:-?\d+,?\s*)+)\]', compact_numeric_array, raw_str)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(raw_str)
        entities = floor_json.get("_map_entities", {})
        monsters = entities.get("monsters", {})
        print(f"  {fid}: wrote {out_path.name}  monsters={list(monsters.keys())}")

print("\nDone.")
