"""只读爆炸半径扫描：找出全塔所有「同步 move(type==move,非async) 之后出现纯文字字符串」
的事件列表——即 _execute_event_list 中 had_sync_anim→拦截分支【会触发】的全部位置。

忠实复刻 had_sync_anim 传播：type=='move' 且非 async 置 True；if(true/false)/while(body)/
insert(公共事件) 继承当前 had；遇 choices 视为另一分支(提前返回，不计入字符串拦截)。
保守起见记录所有「had=True 时遇到的字符串」(真实代码只在首个停)，宁多报不漏报。
"""
import json
from pathlib import Path

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'
COMMON = json.loads((DATA / 'common_events.json').read_text(encoding='utf-8')) \
    if (DATA / 'common_events.json').exists() else {}

hits = []  # (source, had_set_by, text_snippet)


def walk(lst, had, source, depth=0):
    """处理一个指令列表；返回处理后 had 值。had=True 时遇字符串 → 记 HIT。"""
    if not isinstance(lst, list) or depth > 25:
        return had
    for instr in lst:
        if isinstance(instr, str):
            if had:
                hits.append((source, instr[:30]))
            continue
        if not isinstance(instr, dict):
            continue
        t = instr.get('type', '')
        if t == 'choices':
            # choices 是另一条拦截分支，提前返回（其后字符串本轮不可达）
            return had
        if t == 'move' and not instr.get('async', False):
            had = True
        elif t == 'if':
            h_t = walk(instr.get('true', []), had, source, depth + 1)
            h_f = walk(instr.get('false', []), had, source, depth + 1)
            had = had or h_t or h_f
        elif t == 'while':
            had = had or walk(instr.get('data', instr.get('true', [])), had, source, depth + 1)
        elif t == 'insert':
            name = instr.get('name')
            if name in COMMON:
                body = COMMON[name]
                body = body.get('data', body) if isinstance(body, dict) else body
                had = had or walk(body, had, f'{source}>insert:{name}', depth + 1)
    return had


def scan_eventlist(raw, source):
    if isinstance(raw, dict):
        raw = raw.get('data', [])
    walk(raw, False, source)


for fp in sorted(FLOORS.glob('MT*.json')):
    fl = json.loads(fp.read_text(encoding='utf-8'))
    fid = fp.stem
    for key, ev in (fl.get('events') or {}).items():
        scan_eventlist(ev, f'{fid}.events[{key}]')
    for key, ev in (fl.get('afterBattle') or {}).items():
        scan_eventlist(ev, f'{fid}.afterBattle[{key}]')
    fa = fl.get('firstArrive') or fl.get('firstarrive')
    if fa:
        scan_eventlist(fa, f'{fid}.firstArrive')
    ae = fl.get('autoEvent') or {}
    if isinstance(ae, dict):
        for key, entry in ae.items():
            scan_eventlist(entry, f'{fid}.autoEvent[{key}]')

print(f'=== had_sync_anim→拦截分支【会触发】的位置（共 {len(hits)} 处）===')
for src, txt in hits:
    print(f'  {src}\n      文字: {txt!r}')
if not hits:
    print('  （无）')
