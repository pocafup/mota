"""
全6360トークンから FLOOR: トークンを全部抽出し、fly ルートを把握。
また CHOICE トークンも表示（どのイベントに対応するかの手がかり）。
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString

DATA   = Path(__file__).parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))

def decode_all():
    lz = LZString()
    route_path = next(Path(__file__).parent.glob("51_*.h5route"))
    outer = json.loads(lz.decompressFromBase64(route_path.read_text(encoding="utf-8").strip()))
    return parse_rle_route(lz.decompressFromBase64(outer["route"]))

def main():
    tokens = decode_all()
    print(f"全トークン数: {len(tokens)}")
    print()

    floor_tokens = [(i, t) for i, t in enumerate(tokens) if t.startswith("FLOOR:")]
    choice_tokens = [(i, t) for i, t in enumerate(tokens) if t.startswith("CHOICE")]

    print(f"=== FLOOR: トークン ({len(floor_tokens)}個) ===")
    for i, t in floor_tokens:
        ctx_before = tokens[max(0,i-3):i]
        ctx_after = tokens[i+1:i+4]
        print(f"  [{i:4d}] {t}  前={ctx_before}  後={ctx_after}")

    print()
    print(f"=== CHOICE トークン ({len(choice_tokens)}個) ===")
    for i, t in choice_tokens[:40]:
        ctx_before = tokens[max(0,i-2):i]
        ctx_after = tokens[i+1:i+3]
        print(f"  [{i:4d}] {t}  前={ctx_before}  後={ctx_after}")
    if len(choice_tokens) > 40:
        print(f"  ... {len(choice_tokens)-40} 件省略 ...")
        for i, t in choice_tokens[-5:]:
            ctx_before = tokens[max(0,i-2):i]
            ctx_after = tokens[i+1:i+3]
            print(f"  [{i:4d}] {t}  前={ctx_before}  後={ctx_after}")

if __name__ == "__main__":
    main()
