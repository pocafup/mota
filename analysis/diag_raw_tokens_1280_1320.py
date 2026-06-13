"""
直接打印 raw token[1270..1330]，不经模拟器
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path(__file__).parent.glob("51_*.h5route"))
raw = route_path.read_text(encoding="utf-8").strip()
outer = json.loads(decompress(raw))
all_tokens = parse_rle_route(decompress(outer["route"]))

for i in range(1270, 1330):
    print(f"[{i}] {all_tokens[i]}")
