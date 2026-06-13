"""快速拓扑探针：从引擎数据读出 MT4..MT13 的楼梯(changeFloor)格、上/下落点、地上道具坐标。
仅用于确认向上远征的爬升路线由【数据】定，不在对话里手推。不进搜索、不改状态。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state
from sim.simulator import _load_floor_if_needed

s = build_initial_state()
print("floor_ids:", s.floor_ids)
print()

for fid in ["MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10", "MT11", "MT12", "MT13"]:
    if not _load_floor_if_needed(s, fid):
        print(f"{fid}: 未提取/加载失败")
        continue
    f = s.floors[fid]
    idx = s.floor_ids.index(fid)
    print(f"== {fid} (floor_ids[{idx}])  up_floor={f.up_floor} down_floor={f.down_floor}")
    # 楼梯
    for k, cf in sorted(f.change_floor.items()):
        tgt = cf.get("floorId")
        try:
            tgt_idx = s.floor_ids.index(tgt) if tgt in s.floor_ids else "?"
        except Exception:
            tgt_idx = "?"
        ev = f.events.get(k)
        enable = ev.get("enable") if isinstance(ev, dict) else None
        print(f"    楼梯@{k:>7} → {tgt}[{tgt_idx}] stair={cf.get('stair')}"
              + (f" enable={enable}" if enable is not None else ""))
    # 地上道具
    items = []
    for y, row in enumerate(f.entities):
        for x, tile in enumerate(row):
            iid = f._tile_to_item.get(tile)
            if iid is not None:
                items.append((x, y, iid))
    if items:
        print(f"    道具: " + "  ".join(f"({x},{y}){iid}" for x, y, iid in items))
    print()
