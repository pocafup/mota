"""
诊断脚本：显示 RLE 原始 token 与 decoded 展开后的对应关系，
前80个 RLE token，确认 rle[55]、rle[69] 对应的 decoded 索引。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from lzstring import LZString


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def parse_rle_with_index(raw: str, max_rle: int = 90):
    """逐个 RLE token 解析，返回 (rle_idx, rle_raw, decoded_list, decoded_start)"""
    result = []
    decoded_offset = 0
    i = 0
    n = len(raw)
    rle_idx = 0

    while i < n and rle_idx < max_rle:
        c = raw[i]

        # Floor transition: FMT<digits>:
        if raw[i:i+3] == 'FMT':
            j = i + 3
            while j < n and raw[j].isdigit():
                j += 1
            floor_num = raw[i+3:j]
            if j < n and raw[j] == ':':
                j += 1
            rle_raw = raw[i:j]
            decoded = [f'FLOOR:MT{floor_num}']
            result.append((rle_idx, rle_raw, decoded, decoded_offset))
            decoded_offset += len(decoded)
            rle_idx += 1
            i = j

        # Movement: U/D/L/R + optional count
        elif c in 'UDLR':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            count = int(raw[i:j]) if j > i else 1
            rle_raw = raw[i-1:j]
            i = j
            decoded = [c] * count
            result.append((rle_idx, rle_raw, decoded, decoded_offset))
            decoded_offset += len(decoded)
            rle_idx += 1

        # Dialog choice: C + digit(s)
        elif c == 'C':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            choice_n = int(raw[i:j]) if j > i else 0
            rle_raw = raw[i-1:j]
            i = j
            decoded = [f'CHOICE:{choice_n}']
            result.append((rle_idx, rle_raw, decoded, decoded_offset))
            decoded_offset += len(decoded)
            rle_idx += 1

        # Item use: I<mapID>:
        elif c == 'I':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            item_id = raw[i:j]
            rle_raw = raw[i-1:j+1]  # include trailing ':'
            if j < n and raw[j] == ':':
                j += 1
            decoded = [f'ITEM:{item_id}']
            result.append((rle_idx, rle_raw, decoded, decoded_offset))
            decoded_offset += len(decoded)
            rle_idx += 1
            i = j

        # Unknown alphabetic token + optional digits + optional colon
        elif c.isalpha():
            j = i + 1
            while j < n and raw[j].isdigit():
                j += 1
            suffix = raw[i+1:j]
            if j < n and raw[j] == ':':
                j += 1
                rle_raw = raw[i:j]
                decoded = [f'UNKNOWN:{c}{suffix}:']
            else:
                rle_raw = raw[i:j]
                decoded = [f'UNKNOWN:{c}{suffix}']
            result.append((rle_idx, rle_raw, decoded, decoded_offset))
            decoded_offset += len(decoded)
            rle_idx += 1
            i = j

        else:
            i += 1

    return result


def main():
    route_path = next(ROOT.glob("51_*.h5route"))
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    route_raw = decompress(outer["route"])

    print(f"Raw RLE route (first 300 chars):\n{route_raw[:300]}\n")

    entries = parse_rle_with_index(route_raw, max_rle=90)

    print(f"{'rle':>4}  {'rle_tok':<12}  {'decoded_start':>12}  {'count':>5}  decoded_tokens")
    print("-" * 75)
    for rle_idx, rle_raw, decoded, d_start in entries:
        dec_str = ", ".join(decoded[:5])
        if len(decoded) > 5:
            dec_str += f" ... (+{len(decoded)-5} more)"
        print(f"{rle_idx:>4}  {rle_raw!r:<12}  d[{d_start:>4}..{d_start+len(decoded)-1:<4}]  {len(decoded):>5}  {dec_str}")

    # 找 rle[55] 和 rle[69] 的 decoded 索引
    print("\n=== 关键 RLE 索引 ===")
    for rle_idx, rle_raw, decoded, d_start in entries:
        if rle_idx in (55, 69):
            print(f"rle[{rle_idx}] = {rle_raw!r}  →  decoded[{d_start}..{d_start+len(decoded)-1}]  = {decoded[:3]}")


if __name__ == "__main__":
    main()
