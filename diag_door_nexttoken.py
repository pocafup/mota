"""
验证：route 里每次开门的下一个 token 是否是同方向
这是"开门不移动、下一步才进"的路由证据
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString

DATA = Path("data/games51")

def load_tokens():
    route_path = next(Path(".").glob("51_*.h5route"), None)
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))

# 已知开门 token 索引（来自 diag_doors_0_300.py 输出）
DOOR_TOKS = [15, 126, 132, 147, 172, 197, 239, 268, 297]

def main():
    tokens = load_tokens()
    print(f"{'tok':>6}  {'开门方向':<5}  {'下一tok':<5}  {'方向同？'}")
    print("-" * 40)
    for i in DOOR_TOKS:
        d = tokens[i]
        nxt = tokens[i+1] if i+1 < len(tokens) else "?"
        same = "✓ 同方向" if d == nxt else f"✗ 不同({nxt})"
        print(f"tok[{i:>3}]  {d:<5}  {nxt:<5}  {same}")

if __name__ == "__main__":
    main()
