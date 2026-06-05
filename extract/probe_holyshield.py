"""坐实地形伤免疫：①blocksInfo 结构与血网/lava/shield5/amulet 定义；
②全塔 floors map 全部 tile 对照 tiles.json，找未定义 tile（潜在血网/未知机制）。"""
import json, glob, os, collections

EX = r'C:\Users\pocaf\Source\mota\extract\blocksInfo_full.json'
FL = r'C:\Users\pocaf\Source\mota\data\games51\floors'
TILES = r'C:\Users\pocaf\Source\mota\data\games51\tiles.json'

bi = json.load(open(EX, encoding='utf-8'))
print("blocksInfo type:", type(bi).__name__,
      "len:", len(bi) if hasattr(bi, '__len__') else '?')
if isinstance(bi, dict):
    ks = list(bi.keys())[:3]
    print("sample keys:", ks)
    if ks:
        print("sample value:", json.dumps(bi[ks[0]], ensure_ascii=False)[:400])
elif isinstance(bi, list) and bi:
    print("sample[0]:", json.dumps(bi[0], ensure_ascii=False)[:400])


def walk(b):
    if isinstance(b, dict):
        yield from b.items()
    else:
        yield from enumerate(b)


print("\n=== blocksInfo 搜 lava/血/Net/shield5/amulet/负面地形 ===")
hit = False
for k, v in walk(bi):
    s = json.dumps(v, ensure_ascii=False)
    if any(t in s for t in ['lava', '血', 'Net', 'shield5', 'amulet', '护符', '负面地形']):
        print(k, '->', s[:280])
        hit = True
if not hit:
    print("（blocksInfo 中无任何相关条目）")

# tiles.json 已定义的数字 tile
tj = json.load(open(TILES, encoding='utf-8'))
defined = {}
for cls, seg in tj.items():
    if isinstance(seg, dict):
        for tid, info in seg.items():
            if tid.isdigit():
                defined[int(tid)] = (cls, info.get('id') if isinstance(info, dict) else '')

print("\n=== 全塔 map tile 全集（tile ×次数 | tiles.json定义 | 出现楼层）===")
all_tiles = collections.Counter()
tile_floor = collections.defaultdict(set)
for fp in sorted(glob.glob(os.path.join(FL, '*.json'))):
    name = os.path.basename(fp).replace('.json', '')
    d = json.load(open(fp, encoding='utf-8'))
    m = d.get('map')
    if not m:
        continue
    for row in m:
        for t in row:
            all_tiles[t] += 1
            tile_floor[t].add(name)

undefined = []
for t in sorted(all_tiles):
    if t in defined:
        cls, iid = defined[t]
        mark = f"OK [{cls}/{iid}]"
    else:
        mark = "*** 未在 tiles.json 定义 ***"
        undefined.append(t)
    fls = sorted(tile_floor[t], key=lambda s: int(s[2:]) if s[2:].isdigit() else 0)
    print(f"tile {t:>3}: ×{all_tiles[t]:<4} {mark:<28} floors={fls}")

print("\n=== 结论 ===")
print("未定义 tile:", undefined if undefined else "无（全塔 map tile 全部已在 tiles.json 定义）")
