"""临时导出：token[4417..4504] 逐 token 全状态清单（含两端 88 行），交玩家逐行裁定。
复用 verify_all_checkpoints 的 build_initial_state/full_snap/diff_deltas，保证 sim 口径一致。
KEY 按键 token 特别标注。只导出，不裁定。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import build_initial_state, load_tokens, full_snap, diff_deltas
from sim.simulator import step

LO, HI = 4417, 4504

tokens = load_tokens()
state = build_initial_state()
prev = full_snap(state)
rows = []
for idx, tok in enumerate(tokens[:HI + 1]):
    state = step(state, tok)
    cur = full_snap(state)
    d = diff_deltas(prev, cur)
    if LO <= idx <= HI:
        rows.append((idx, tok, cur, d))
    prev = cur

key_hits = [(i, t) for i, t, _, _ in rows if t.startswith('KEY:')]
print(f'# token[{LO}..{HI}]  共 {len(rows)} 行')
print(f'# 区间内 KEY 按键 token: {key_hits if key_hits else "无"}')
print('# 每行: tok[idx] 动作 | 楼层(x,y) HP/ATK/DEF 黄/蓝/红 金  Δ变化')
print()
for idx, tok, s, deltas in rows:
    base = (f"tok[{idx}] {tok:<10} | {s['floor']}({s['x']},{s['y']}) "
            f"HP={s['hp']} ATK={s['atk']} DEF={s['df']} "
            f"黄{s['yk']}/蓝{s['bk']}/红{s['rk']} 金={s['gold']}")
    dstr = ('  Δ ' + ', '.join(deltas)) if deltas else ''
    mark = '   <<<<<< KEY 按键（存档快捷键→道具）' if tok.startswith('KEY:') else ''
    print(base + dstr + mark)
