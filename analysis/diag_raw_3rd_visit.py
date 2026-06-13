"""打印 token[248..285] 的原始字符串位置，并检查中左/中右区的路由编码。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(decompress(raw))
route_raw = decompress(outer['route'])

# 带位置信息的解析
def parse_with_positions(raw):
    result = []
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        start = i
        if raw[i:i+3] == 'FMT':
            j = i + 3
            while j < n and raw[j].isdigit():
                j += 1
            floor_num = raw[i+3:j]
            if j < n and raw[j] == ':':
                j += 1
            result.append((f'FLOOR:MT{floor_num}', start, j))
            i = j
        elif c in 'UDLR':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            count = int(raw[i:j]) if j > i else 1
            i = j
            for _ in range(count):
                result.append((c, start, i))
        elif c == 'C':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            i = j
            result.append((f'CHOICE', start, i))
        elif c.isalpha():
            j = i + 1
            while j < n and raw[j].isdigit():
                j += 1
            suffix = raw[i+1:j]
            if j < n and raw[j] == ':':
                j += 1
                result.append((f'UNKNOWN:{c}{suffix}:', start, j))
            else:
                result.append((f'UNKNOWN:{c}{suffix}', start, j))
            i = j
        else:
            i += 1
    return result

parsed = parse_with_positions(route_raw)

print("=== token[248..285] 原始字符串位置 ===")
for idx in range(248, 286):
    tok, s, e = parsed[idx]
    segment = route_raw[s:e]
    print(f"  [{idx:3d}] tok={tok:<15}  raw[{s}:{e}]='{segment}'")

# 显示整个第三次 MT4 造访的 raw 片段
s_start = parsed[256][1]
e_end = parsed[280][2]
print(f"\n=== 第三次 MT4 造访原始字符串 raw[{s_start}:{e_end}] ===")
print(repr(route_raw[s_start:e_end]))

# 解读：按 RLE 结构手动分析这段字符串
segment = route_raw[s_start:e_end]
print(f"\n手动解读：{segment}")
print("预期：FMT4:U2R5UR3D7LR2U2FMT5: (走中左区)")
print("正确：FMT4:U3R7D4LR3LU4FMT5: (走中右区)")
