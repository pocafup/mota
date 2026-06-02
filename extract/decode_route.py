"""
Decode a .h5route file and normalize route tokens to an action list.

Outer layer: lz-string Base64 -> JSON {name, version, hard, seed, route}
Inner route: lz-string Base64 -> RLE action string

Confirmed token formats (from source analysis):
  U[n] D[n] L[n] R[n]  -- move n steps (n omitted = 1)
  C[n]                  -- dialog choice, n is 0-indexed option index
  FMT<floor>:           -- floor-transition marker (player arrives at MT<floor>)
  I<mapID>:             -- use item with map tile ID <mapID>
  K<n>:                 -- QUESTION: meaning unknown (shop? key?)
  (help)                -- QUESTION: meaning unknown (appears as literal chars)
"""

import json
import sys
from collections import Counter
from pathlib import Path

try:
    from lzstring import LZString
except ImportError:
    print("ERROR: pip install lzstring")
    sys.exit(1)


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def parse_rle_route(raw: str) -> list[str]:
    """
    Parse RLE-encoded route string into normalized action list.
    Each element is one of:
      'U' 'D' 'L' 'R'       -- single step
      'CHOICE:n'             -- dialog choice n (0-indexed, pending confirmation)
      'FLOOR:MTn'            -- floor transition marker
      'ITEM:n'               -- use item (map tile ID n)
      'UNKNOWN:xxx'          -- unrecognized token, flagged for question list
    """
    actions = []
    i = 0
    n = len(raw)

    while i < n:
        c = raw[i]

        # Floor transition: FMT<digits>:
        if raw[i:i+3] == 'FMT':
            j = i + 3
            while j < n and raw[j].isdigit():
                j += 1
            floor_num = raw[i+3:j]
            if j < n and raw[j] == ':':
                j += 1
            actions.append(f'FLOOR:MT{floor_num}')
            i = j

        # Movement: U/D/L/R + optional count
        elif c in 'UDLR':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            count = int(raw[i:j]) if j > i else 1
            i = j
            actions.extend([c] * count)

        # Dialog choice: C + digit(s)
        elif c == 'C':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            choice_n = int(raw[i:j]) if j > i else 0
            i = j
            actions.append(f'CHOICE:{choice_n}')

        # Item use: I<mapID>:
        elif c == 'I':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            item_id = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1
            actions.append(f'ITEM:{item_id}')
            i = j

        # Direct coordinate jump: M<x>:<y>  →  MOVE:x:y
        elif c == 'M':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            x = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1          # skip ':'
            k = j
            while k < n and raw[k].isdigit():
                k += 1
            y = raw[j:k]
            actions.append(f'MOVE:{x}:{y}')
            i = k

        # Unknown alphabetic token + optional digits + optional colon
        elif c.isalpha():
            j = i + 1
            while j < n and raw[j].isdigit():
                j += 1
            suffix = raw[i+1:j]
            if j < n and raw[j] == ':':
                j += 1
                actions.append(f'UNKNOWN:{c}{suffix}:')
            else:
                actions.append(f'UNKNOWN:{c}{suffix}')
            i = j

        else:
            i += 1

    return actions


def decode_route_file(path: str) -> dict:
    raw_bytes = Path(path).read_text(encoding='utf-8').strip()

    outer_json = decompress(raw_bytes)
    if not outer_json:
        raise ValueError("Outer decompression failed")

    outer = json.loads(outer_json)
    meta = {k: v for k, v in outer.items() if k != 'route'}
    print("=== Outer JSON meta:")
    for k, v in meta.items():
        print(f"  {k}: {v!r}")

    route_raw = decompress(outer.get('route', ''))
    if not route_raw:
        raise ValueError("Inner route decompression failed")

    print(f"\n=== Raw route (first 200 chars):\n{route_raw[:200]}")
    print(f"    Total length: {len(route_raw)} chars")

    actions = parse_rle_route(route_raw)

    types = Counter(a.split(':')[0] if ':' in a else a for a in actions)
    print(f"\n=== Token type counts: {dict(types.most_common())}")
    print(f"\n=== First 50 actions:")
    for idx, a in enumerate(actions[:50]):
        print(f"  [{idx:3d}] {a}")

    return {
        'meta': meta,
        'route_raw': route_raw,
        'actions': actions,
    }


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        candidates = list(Path(__file__).parent.parent.glob('51_*.h5route'))
        if not candidates:
            print("No .h5route file found.")
            sys.exit(1)
        path = str(candidates[0])
        print(f"Using: {path}\n")

    decode_route_file(path)
