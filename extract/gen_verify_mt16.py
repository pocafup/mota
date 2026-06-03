"""
Generate data/games51/floors/MT16.json from mt16_raw_capture.json.
Cell-by-cell verification against the raw engine capture.
"""
import json
import re
from pathlib import Path

ROOT    = Path(__file__).parent.parent
DATA    = ROOT / "data" / "games51"
EXTRACT = ROOT / "extract"


def load_raw_capture(path):
    raw_text = path.read_text(encoding="utf-8").strip()
    if raw_text.startswith('"'):
        return json.loads(json.loads(raw_text))
    return json.loads(raw_text)


def build_entities_annotation(floor_map, tiles_db):
    enemy_map   = {int(k): v["id"] for k, v in tiles_db["enemys"].items()}
    item_map    = {int(k): v["id"] for k, v in tiles_db["items"].items()}
    npc_map     = {int(k): v["id"] for k, v in tiles_db["npcs"].items()}
    terrain_map = {int(k): v["id"] for k, v in tiles_db["terrains"].items()}
    animate_map = {int(k): v["id"] for k, v in tiles_db["animates"].items()}

    DOOR_IDS  = {"yellowDoor","blueDoor","redDoor","greenDoor","specialDoor","steelDoor"}
    STAIR_IDS = {"upFloor","downFloor"}

    monsters, items, doors, fakes, stairs, npcs = {}, {}, {}, {}, {}, {}

    for y, row in enumerate(floor_map):
        for x, cell in enumerate(row):
            if cell in (0, 1):
                continue
            pos = f"({x},{y})"
            if cell in enemy_map:
                key = f"{enemy_map[cell]}({cell})"
                monsters.setdefault(key, []).append(pos)
            elif cell in item_map:
                key = f"{item_map[cell]}({cell})"
                items.setdefault(key, []).append(pos)
            elif cell in npc_map:
                key = f"{npc_map[cell]}({cell})"
                npcs.setdefault(key, []).append(pos)
            elif cell in terrain_map:
                tid = terrain_map[cell]
                key = f"{tid}({cell})"
                if tid in STAIR_IDS:
                    stairs.setdefault(key, []).append(pos)
                else:
                    npcs.setdefault(f"terrain:{key}", []).append(pos)
            elif cell in animate_map:
                aid = animate_map[cell]
                key = f"{aid}({cell})"
                if aid in DOOR_IDS:
                    doors.setdefault(key, []).append(pos)
                else:
                    fakes.setdefault(key, []).append(pos)
            else:
                print(f"  ⚠ 未知 tile {cell} at ({x},{y}) — 需补充 tiles.json")

    out = {"_comment": ("从 map 数组推导的实体位置，便于阅读。"
                        "模拟器从 map + tiles.json 动态解析，不从此字段读取。")}
    if monsters: out["monsters"]       = monsters
    if items:    out["items"]          = items
    if doors:    out["doors"]          = doors
    if fakes:    out["fakes"]          = fakes
    if npcs:     out["npcs_terrain"]   = npcs
    if stairs:   out["stairs_terrain"] = stairs
    return out


def compact_rows(json_str):
    def _compact(m):
        inner = m.group(1)
        nums = re.split(r',\s*', inner.strip())
        if all(re.fullmatch(r'-?\d+', n.strip()) for n in nums if n.strip()):
            return '[' + ', '.join(n.strip() for n in nums if n.strip()) + ']'
        return m.group(0)
    return re.sub(r'\[\s*((?:-?\d+,?\s*)+)\]', _compact, json_str)


# ── Load ─────────────────────────────────────────────────────────────────────
raw      = load_raw_capture(EXTRACT / "mt16_raw_capture.json")
tiles_db = json.loads((DATA / "tiles.json").read_text(encoding="utf-8"))
entities = build_entities_annotation(raw["map"], tiles_db)

# ── Build output ──────────────────────────────────────────────────────────────
out = {
    "_comment":      "来源: core.floors['MT16'] (live engine, Playwright 提取)。events 存原始 h5mota 脚本。",
    "floorId":       raw["floorId"],
    "title":         raw["title"],
    "width":         raw["width"],
    "height":        raw["height"],
    "ratio":         raw["ratio"],
    "bgm":           raw["bgm"],
    "_landing_note": "downFloor/upFloor: fly魔杖/楼梯落点 [x,y]，来源: browser core.floors[id].downFloor/upFloor",
    "downFloor":     raw["downFloor"],
    "upFloor":       raw["upFloor"],
    "_map_note":     "map[y][x]，0=地板，1=墙。tile ID 含义见 tiles.json。",
    "map":           raw["map"],
    "_map_entities": entities,
    "changeFloor":   raw.get("changeFloor",   {}),
    "events":        raw.get("events",        {}),
    "firstArrive":   raw.get("firstArrive",   []),
    "eachArrive":    raw.get("eachArrive",    []),
    "afterGetItem":  raw.get("afterGetItem",  {}),
    "afterBattle":   raw.get("afterBattle",   {}),
    "autoEvent":     raw.get("autoEvent",     {}),
    "afterOpenDoor": raw.get("afterOpenDoor", {}),
    "cannotMove":    raw.get("cannotMove",    {}),
}

# ── Write ─────────────────────────────────────────────────────────────────────
out_path = DATA / "floors" / "MT16.json"
out_path.write_text(compact_rows(json.dumps(out, ensure_ascii=False, indent=2)),
                    encoding="utf-8")
print(f"写入: {out_path}")

# ── Cell-by-cell verification ─────────────────────────────────────────────────
src_map = raw["map"]
gen_map = json.loads(out_path.read_text(encoding="utf-8"))["map"]
H, W    = raw["height"], raw["width"]
errors  = []

for y in range(H):
    for x in range(W):
        sv, gv = src_map[y][x], gen_map[y][x]
        if sv != gv:
            errors.append(f"  ({x},{y}): 源码={sv}  JSON={gv}")

if errors:
    print(f"\n⚠ 逐格校验：{len(errors)} 处不一致")
    for e in errors:
        print(e)
else:
    print(f"\n✅ 逐格校验通过：{W}×{H}={W*H} 格全部与源码一致。")

# ── Summary ───────────────────────────────────────────────────────────────────
ents = {k: v for k, v in entities.items() if not k.startswith("_")}
print(f"\n=== MT16 内容摘要 ===")
print(f"  ratio={raw['ratio']}  size={W}×{H}  bgm={raw['bgm']}")
print(f"  downFloor={raw['downFloor']}  upFloor={raw['upFloor']}")
print(f"  changeFloor: {list(raw.get('changeFloor',{}).keys())}")
print(f"  events: {list(raw.get('events',{}).keys())}")
print(f"  autoEvent keys: {list(raw.get('autoEvent',{}).keys())}")
print(f"  afterBattle 条目数: {len(raw.get('afterBattle', {}))}")
for cat, tiles in ents.items():
    print(f"  {cat}: {list(tiles.keys())}")

lava_locs = [(x,y) for y,row in enumerate(raw['map']) for x,v in enumerate(row) if v==5]
print(f"\n  岩浆(tile 5): {'存在，位置: '+str(lava_locs) if lava_locs else '不存在'}")

for tid, tname in [(81,'yellowDoor'),(82,'blueDoor'),(83,'redDoor'),(84,'greenDoor')]:
    locs = [(x,y) for y,row in enumerate(raw['map']) for x,v in enumerate(row) if v==tid]
    if locs:
        print(f"  {tname}(tile {tid}): {locs}")
