"""对账：live 引擎 blocksInfo（ground truth） vs data/games51/tiles.json。
并统计每个有问题的编号实际出现在哪些已提取楼层（MTx.json），判断影响面。
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"

# 1) 引擎权威映射 {num(int): id}
t = (ROOT / "extract" / "blocksInfo_full.json").read_text(encoding="utf-8").strip()
eng_raw = json.loads(json.loads(t)) if t.startswith('"') else json.loads(t)
eng = {int(k): v["id"] for k, v in eng_raw.items()}
eng_cls = {int(k): v.get("cls") for k, v in eng_raw.items()}

# 2) tiles.json 扁平 {num(int): id}
tiles = json.loads((DATA / "tiles.json").read_text(encoding="utf-8"))
flat = {}
for cat in ("walls", "terrains", "animates", "items", "enemys", "npcs"):
    for k, v in tiles.get(cat, {}).items():
        flat[int(k)] = v["id"]

# 3) 每个编号出现在哪些已提取楼层
def floors_using(num):
    used = []
    for p in sorted(FLOORS.glob("MT*.json"), key=lambda x: int(x.stem[2:])):
        m = json.loads(p.read_text(encoding="utf-8")).get("map", [])
        if any(num in row for row in m):
            used.append(p.stem)
    return used

print("=== tiles.json 中与引擎不一致的编号（WRONG）===")
wrong = []
for num, tid in sorted(flat.items()):
    if num in eng and eng[num] != tid:
        wrong.append(num)
        print(f"  {num}: tiles.json='{tid}'  引擎='{eng[num]}'(cls={eng_cls[num]})  出现于: {floors_using(num) or '(未提取楼层引用)'}")
if not wrong:
    print("  （无）")

print("\n=== 所有已提取楼层用到、但 tiles.json 缺失的编号（MISSING）===")
all_nums = set()
for p in FLOORS.glob("MT*.json"):
    for row in json.loads(p.read_text(encoding="utf-8")).get("map", []):
        all_nums.update(v for v in row if v not in (0, 1))
missing = sorted(n for n in all_nums if n not in flat)
for num in missing:
    print(f"  {num}: 引擎='{eng.get(num,'NULL')}'(cls={eng_cls.get(num)})  出现于: {floors_using(num)}")
if not missing:
    print("  （无）")

print("\n=== 参考：引擎里 magicDragon / blackMagician / princess 的真实编号 ===")
for want in ("magicDragon", "blackMagician", "princess"):
    nums = [n for n, i in eng.items() if i == want]
    print(f"  {want}: {nums}")
