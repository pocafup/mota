"""扫描 route 的 ITEM/KEY token，坐实圣水(superPotion=ITEM:56)与破墙镐(pickaxe=KEY:49/ITEM:47)
的使用位置；并打印 token 类型计数。临时诊断脚本（工作流：交玩家裁定用）。"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString

route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw))
tokens = parse_rle_route(LZString().decompressFromBase64(outer['route']))

print(f"route 文件: {route_path.name}")
print(f"总 token 数: {len(tokens)}")

print("\n=== 所有 ITEM / KEY token (index, token) ===")
for i, tok in enumerate(tokens):
    if tok.startswith('ITEM:') or tok.startswith('KEY:'):
        print(f"  tok[{i}] = {tok}")

print("\n=== token 类型计数 ===")
ctr = Counter()
for t in tokens:
    head = t.split(':', 1)[0]
    ctr[head] += 1
for k, v in sorted(ctr.items(), key=lambda kv: -kv[1]):
    print(f"  {k}: {v}")

# 终局段附近上下文（验证 tok5391 KEY:49 / tok4925 区域）
print("\n=== tok[4900..4930] 上下文 ===")
for i in range(4900, min(4931, len(tokens))):
    print(f"  tok[{i}] = {tokens[i]}")
