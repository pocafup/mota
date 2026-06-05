"""只读诊断：定位 route 里所有 (xxx) 自定义 token，并用『修正版』解析器
(正确处理 (...) 为单 token，对照引擎 decodeOne) 打印 help 区段与锚点邻域的原始 token 流。
目的：判定自动模式的效果是否已『烘焙』进 route（显式 move token），还是需运行时展开。
不改任何产品代码/真值/断言。"""
import json
import re
from pathlib import Path
from lzstring import LZString

ROUTE = next(Path('.').glob('51_*.h5route'))
raw_file = ROUTE.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw_file))
route_raw = LZString().decompressFromBase64(outer['route'])
print(f"# 原始 route 串长度: {len(route_raw)} chars")

# 1. 所有 (...) 自定义 token 在原始串里的位置与内容
parens = [(m.start(), m.group(1)) for m in re.finditer(r'\(([^)]*)\)', route_raw)]
print(f"# (...) 自定义 token 共 {len(parens)} 处:")
from collections import Counter
print(f"#   内容计数: {dict(Counter(c for _, c in parens))}")
for pos, content in parens[:8]:
    print(f"#   raw@{pos}: ({content})  上下文: ...{route_raw[max(0,pos-12):pos+len(content)+3]}...")


def parse_corrected(raw):
    """修正版解析器：与引擎 _decodeRoute_decodeOne 对齐，(...) 作单 token。"""
    acts = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == '(':
            idx = raw.find(')', i + 1)
            acts.append(raw[i+1:idx])      # 整串作单 token，如 'help'
            i = idx + 1
        elif raw[i:i+3] == 'FMT':
            j = i + 3
            while j < n and raw[j].isdigit():
                j += 1
            fl = raw[i+3:j]
            if j < n and raw[j] == ':':
                j += 1
            acts.append(f'FLOOR:MT{fl}')
            i = j
        elif c in 'UDLR':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            cnt = int(raw[i:j]) if j > i else 1
            i = j
            acts.extend([c] * cnt)
        elif c == 'C':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            acts.append(f'CHOICE:{int(raw[i:j]) if j>i else 0}')
            i = j
        elif c == 'I':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            it = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1
            acts.append(f'ITEM:{it}')
            i = j
        elif c == 'K':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            acts.append(f'KEY:{raw[i:j]}')
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
            acts.append(f'MOVE:{x}:{raw[j:k]}')
            i = k
        elif c.isalpha():
            j = i + 1
            while j < n and raw[j].isdigit():
                j += 1
            suf = raw[i+1:j]
            if j < n and raw[j] == ':':
                j += 1
                acts.append(f'UNKNOWN:{c}{suf}:')
            else:
                acts.append(f'UNKNOWN:{c}{suf}')
            i = j
        else:
            i += 1
    return acts


acts = parse_corrected(route_raw)
print(f"\n# 修正版解析 token 总数: {len(acts)}")
print(f"# token 类型计数: {dict(Counter(a.split(':')[0] if ':' in a else a for a in acts).most_common())}")

# 找到第一个 help token 的修正版索引
help_idx = [i for i, a in enumerate(acts) if a == 'help']
print(f"# 'help' token 修正版索引: {help_idx}")

# 打印 help 区段邻域（首个 help 前后）
if help_idx:
    lo = max(0, help_idx[0] - 5)
    hi = min(len(acts), help_idx[-1] + 60)
    print(f"\n# === 修正版 token[{lo}..{hi}] (help 区段及其后 60 token) ===")
    for i in range(lo, hi):
        print(f"  [{i}] {acts[i]}")
