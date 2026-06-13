"""带 provenance 的重解析：记录每个展开 action 来自原始 RLE 串的哪段字符。
打印 tok4705..4730 的 (展开token, 原始来源子串, 原始char偏移)。
目的：确认 sim 喂入的 tok4719=L/4720=R/4721=L 是否忠实于原始路线串，
还是 RLE 解析 bug（如 R 计数错、L/R 混淆、漏token）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lzstring import LZString

route_path = next(Path('.').glob('51_*.h5route'))
raw_bytes = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw_bytes))
raw = LZString().decompressFromBase64(outer['route'])

# 复制 parse_rle_route 逻辑，但每个 action 记录来源 (raw_start, raw_end, raw_substr)
prov = []  # (action, raw_start, raw_end)
i = 0
n = len(raw)
while i < n:
    c = raw[i]
    start = i
    if raw[i:i+3] == 'FMT':
        j = i + 3
        while j < n and raw[j].isdigit():
            j += 1
        fn = raw[i+3:j]
        if j < n and raw[j] == ':':
            j += 1
        prov.append((f'FLOOR:MT{fn}', start, j))
        i = j
    elif c in 'UDLR':
        i += 1
        j = i
        while j < n and raw[j].isdigit():
            j += 1
        count = int(raw[i:j]) if j > i else 1
        i = j
        for _ in range(count):
            prov.append((c, start, j))
    elif c == 'C':
        i += 1
        j = i
        while j < n and raw[j].isdigit():
            j += 1
        cn = int(raw[i:j]) if j > i else 0
        i = j
        prov.append((f'CHOICE:{cn}', start, j))
    elif c == 'I':
        i += 1
        j = i
        while j < n and raw[j].isdigit():
            j += 1
        it = raw[i:j]
        if j < n and raw[j] == ':':
            j += 1
        prov.append((f'ITEM:{it}', start, j))
        i = j
    elif c == 'K':
        i += 1
        j = i
        while j < n and raw[j].isdigit():
            j += 1
        kc = raw[i:j]
        prov.append((f'KEY:{kc}', start, j))
        i = j
    elif c == 'M':
        i += 1
        j = i
        while j < n and raw[j].isdigit():
            j += 1
        x = raw[i:j]
        if j < n and raw[j] == ':':
            j += 1
        k = j
        while k < n and raw[k].isdigit():
            k += 1
        y = raw[j:k]
        prov.append((f'MOVE:{x}:{y}', start, k))
        i = k
    elif c.isalpha():
        j = i + 1
        while j < n and raw[j].isdigit():
            j += 1
        suf = raw[i+1:j]
        if j < n and raw[j] == ':':
            j += 1
            prov.append((f'UNKNOWN:{c}{suf}:', start, j))
        else:
            prov.append((f'UNKNOWN:{c}{suf}', start, j))
        i = j
    else:
        i += 1

print(f"展开 action 总数={len(prov)}")
print("tok4705..4730： 展开token | 原始来源子串 | char偏移")
seen_spans = set()
for idx in range(4705, 4731):
    act, s, e = prov[idx]
    span = (s, e)
    substr = raw[s:e]
    marker = ''
    if span not in seen_spans:
        seen_spans.add(span)
        marker = '  <<原始token起'
    print(f"  tok[{idx}] {act:10} 来源='{substr}' [{s}:{e}]{marker}")

# 额外：打印这一段原始串的连续上下文，肉眼看有无异常
s0 = prov[4715][1]
s1 = prov[4725][2]
print(f"\n原始RLE子串 [tok4715起..tok4725止] 字符[{s0}:{s1}] = '{raw[s0:s1]}'")
print(f"更宽上下文 raw[{s0-20}:{s1+20}] = '{raw[max(0,s0-20):s1+20]}'")
