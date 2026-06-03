"""打印 token[200..299] 原始内容，检查是否有 CHOICE/ITEM/FLOOR 类型。"""
import json
from pathlib import Path
from extract.decode_route import parse_rle_route
from lzstring import LZString

DATA = Path('data/games51')
route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw))
tokens = parse_rle_route(LZString().decompressFromBase64(outer['route']))

print(f"Total tokens: {len(tokens)}")
print()
special = [t for t in tokens[200:300] if t not in ('U','D','L','R')]
print(f"Special tokens in [200..299]: {special}")
print()
print("All tokens[200..299]:")
for i in range(200, 300):
    t = tokens[i]
    marker = " <<<" if t not in ('U','D','L','R') else ""
    print(f"  [{i}] {t!r}{marker}")
