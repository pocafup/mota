"""打印原始路由字符串，找 token[190..215] 对应的片段，确认 token[202] 真实值。"""
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

tokens = parse_rle_route(route_raw)

# 重新实现带位置信息的解析，记录每个 token 在原始字符串的起始字符位置
def parse_with_positions(raw):
    """返回 (token, start_pos, end_pos) 列表"""
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
            choice_n = int(raw[i:j]) if j > i else 0
            i = j
            result.append((f'CHOICE:{choice_n}', start, i))
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

print("=== token[185..215] 的原始字符串位置 ===")
for idx in range(185, 216):
    tok, s, e = parsed[idx]
    # 显示该 token 在原始字符串里的实际字符（可能是多个 token 共享一个 RLE 段）
    segment = route_raw[s:e]
    print(f"  [{idx:3d}] tok={tok:<15}  raw[{s}:{e}]='{segment}'")

# 找 token[190..215] 的前后各5字符上下文
s_start = parsed[185][1]
e_end = parsed[215][2]
print(f"\n=== 原始字符串 raw[{s_start-5}:{e_end+5}] ===")
print(repr(route_raw[max(0,s_start-5):e_end+5]))
