"""Generate data/games51/floors/MT20.json from mt20_raw_capture.json."""
import json, re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"
EXTRACT = ROOT / "extract"

def load_raw(path):
    t = path.read_text(encoding="utf-8").strip()
    return json.loads(json.loads(t)) if t.startswith('"') else json.loads(t)

def build_entities(floor_map, tiles_db):
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
            else: print(f"  ⚠ 未知 tile {cell} at ({x},{y})")
    out = {"_comment": "从 map 推导的实体位置，模拟器从 map+tiles.json 动态解析。"}
    if monsters: out["monsters"] = monsters
    if items:    out["items"]    = items
    if doors:    out["doors"]    = doors
    if fakes:    out["fakes"]    = fakes
    if npcs:     out["npcs_terrain"] = npcs
    if stairs:   out["stairs_terrain"] = stairs
    return out

def compact(s):
    def _c(m):
        nums = re.split(r',\s*', m.group(1).strip())
        return ('['+', '.join(n.strip() for n in nums if n.strip())+']'
                if all(re.fullmatch(r'-?\d+', n.strip()) for n in nums if n.strip())
                else m.group(0))
    return re.sub(r'\[\s*((?:-?\d+,?\s*)+)\]', _c, s)

raw      = load_raw(EXTRACT / "mt20_raw_capture.json")
tiles_db = json.loads((DATA / "tiles.json").read_text(encoding="utf-8"))
entities = build_entities(raw["map"], tiles_db)

out = {
    "_comment": "来源: core.floors['MT20'] (live engine, Playwright 提取)。",
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
out_path = DATA / "floors" / "MT20.json"
out_path.write_text(compact(json.dumps(out, ensure_ascii=False, indent=2)), encoding="utf-8")
print(f"写入: {out_path}")

src, gen = raw["map"], json.loads(out_path.read_text(encoding="utf-8"))["map"]
H, W = raw["height"], raw["width"]
errs = [f"  ({x},{y}): 源={src[y][x]} gen={gen[y][x]}"
        for y in range(H) for x in range(W) if src[y][x] != gen[y][x]]
print(f"⚠ {len(errs)} 处不一致:" if errs else f"✅ 逐格校验通过：{W}×{H} 格全部一致。")
for e in errs: print(e)

ents = {k:v for k,v in entities.items() if not k.startswith("_")}
print(f"\n=== MT20 ===  ratio={raw['ratio']}  downFloor={raw['downFloor']}  upFloor={raw['upFloor']}")
print(f"  changeFloor: {list(raw.get('changeFloor',{}).keys())}")
print(f"  events keys: {list(raw.get('events',{}).keys())}")
print(f"  firstArrive: {raw.get('firstArrive',[])}")
print(f"  afterBattle keys: {list(raw.get('afterBattle',{}).keys())}")
for cat, tiles in ents.items(): print(f"  {cat}: {list(tiles.keys())}")
lava = [(x,y) for y,r in enumerate(raw['map']) for x,v in enumerate(r) if v==5]
print(f"  岩浆: {'有: '+str(lava) if lava else '无'}")
for tid,nm in [(81,'yellowDoor'),(82,'blueDoor'),(83,'redDoor'),(85,'specialDoor')]:
    locs = [(x,y) for y,r in enumerate(raw['map']) for x,v in enumerate(r) if v==tid]
    if locs: print(f"  {nm}({tid}): {locs}")

print("\n  afterBattle['6,6'] 要点:")
ab66 = raw.get('afterBattle',{}).get('6,6',[])
for i in ab66:
    if isinstance(i, dict): print(f"    {i.get('type')}: {i.get('loc') or i.get('name') or i.get('number','')}")
    elif isinstance(i, str): print(f"    [dialog]")
