"""探针：tok4085 ITEM:50(centerFly) 为什么没瞬移。
重放到 tok4084（ITEM:50 之前），打印判定链路每一步，再实跑 tok4085 看结果。
只读探针，不改产品代码。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from extract.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step, _center_fly_can_land

tokens = load_tokens()
state = build_initial_state()

# 重放 tokens[0..4084]（含 4084），停在 ITEM:50 之前
for idx in range(4085):
    state = step(state, tokens[idx])

h = state.hero
floor = state.floor
print("=" * 64)
print(f"重放到 tok4084 后的状态（ITEM:50 之前）")
print(f"  当前楼层 = {state.current_floor}")
print(f"  英雄坐标 = ({h.x},{h.y})")
print(f"  hero.items = {h.items}")
print(f"  centerFly 计数 = {h.items.get('centerFly', 0)}")

print(f"\n  tok4085 实际 token = {tokens[4085]!r}")
tile = 50
item_id = floor._tile_to_item.get(tile)
print(f"  floor._tile_to_item.get(50) = {item_id!r}   ← 须为 'centerFly' 才会走瞬移分支")

rows = len(floor.terrain)
cols = len(floor.terrain[0]) if rows else 0
tx, ty = cols - 1 - h.x, rows - 1 - h.y
print(f"\n  地图尺寸 cols={cols} rows={rows}")
print(f"  中心对称落点 (tx,ty) = ({tx},{ty})   ← 玩家实测应落 (2,1)")

if 0 <= tx < cols and 0 <= ty < rows:
    ent = floor.entities[ty][tx]
    ter = floor.terrain[ty][tx]
    ent_id = floor._tile_to_id.get(ent) if ent else None
    ter_id = floor._tile_to_id.get(ter) if ter else None
    print(f"\n  落点 ({tx},{ty}) sim 数据：")
    print(f"    entities[{ty}][{tx}] = {ent}  (id={ent_id!r})   ← ≠0 则判定直接 False")
    print(f"    terrain [{ty}][{tx}] = {ter}  (id={ter_id!r})")
    print(f"    getBlockId 语义：entity≠0→entity_id；否则 terrain≠0→terrain_id；都为0→null")
    canland = _center_fly_can_land(floor, tx, ty)
    print(f"    _center_fly_can_land({tx},{ty}) = {canland}   ← 须 True 才会瞬移")
    print(f"    （口径：getBlockId ∈ {{null,'none','airwall'}} 才可落）")
else:
    print(f"  落点越界！")

print("\n" + "=" * 64)
print("实跑 tok4085 = ITEM:50：")
before = (h.x, h.y, h.items.get('centerFly', 0))
state = step(state, tokens[4085])
h2 = state.hero
print(f"  前: 坐标=({before[0]},{before[1]}) centerFly={before[2]}")
print(f"  后: 坐标=({h2.x},{h2.y}) centerFly={h2.items.get('centerFly', 0)}")
print(f"  楼层={state.current_floor}")
if (h2.x, h2.y) == (2, 1):
    print("  ✅ 瞬移到 (2,1) 成功")
else:
    print(f"  🛑 未瞬移：坐标仍为 ({h2.x},{h2.y})，玩家实测应为 (2,1)")
print("=" * 64)
