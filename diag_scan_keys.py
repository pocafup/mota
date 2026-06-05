"""扫描 route 内全部 KEY: token（引擎 key:<keyCode> 快捷键），报告各自全局 token 下标。
只读诊断，不改任何文件。"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString

rp = next(Path('.').glob('51_*.h5route'), None)
raw = rp.read_text(encoding='utf-8').strip()
outer = json.loads(LZString().decompressFromBase64(raw))
tokens = parse_rle_route(LZString().decompressFromBase64(outer['route']))

print(f'route 总 token 数: {len(tokens)}')

key_idx = [(i, t) for i, t in enumerate(tokens) if t.startswith('KEY:')]
print(f'\nKEY: token 共 {len(key_idx)} 个：')
for i, t in key_idx:
    kc = t.split(':', 1)[1]
    ch = chr(int(kc)) if kc.isdigit() else '?'
    print(f"  tok[{i}] {t}  (keyCode {kc} = 键 '{ch}')")

print(f"\n按 keyCode 计数: {dict(Counter(t for _, t in key_idx).most_common())}")

# 残留 UNKNOWN（确认没有 UNKNOWN:K 漏网）
unk = [(i, t) for i, t in enumerate(tokens) if t.startswith('UNKNOWN')]
print(f'\nUNKNOWN: token 共 {len(unk)} 个：')
for i, t in unk:
    print(f"  tok[{i}] {t}")
