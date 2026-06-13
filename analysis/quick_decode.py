import sys, json
from pathlib import Path
from lzstring import LZString

lz = LZString()
raw = Path(r"C:\Users\pocaf\Source\mota\51_20260529133740.h5route").read_text(encoding='utf-8').strip()

outer_json = lz.decompressFromBase64(raw)
print("OUTER JSON length:", len(outer_json))
outer = json.loads(outer_json)
print("Keys:", list(outer.keys()))
for k, v in outer.items():
    if k != 'route':
        print(f"  {k}: {repr(v)}")

route_raw = lz.decompressFromBase64(outer['route'])
print(f"\nRoute raw (first 300): {route_raw[:300]!r}")
print(f"Route total length: {len(route_raw)}")

# Write full route to file for inspection
Path(r"C:\Users\pocaf\Source\mota\extract\route_raw.txt").write_text(route_raw, encoding='utf-8')
print("\nFull route written to extract/route_raw.txt")
