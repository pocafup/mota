"""临时诊断：dump tok4505..4535，看 KEY:50(tok4524) 时英雄在哪层/坐标，
据此判定 KEY:50 应绑 upFly(升1层) 还是 downFly(降1层) 才能进 MT44。
KEY:50 当前仍 no-op（未绑定），所以这是"未用飞翼"的轨迹。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.verify_all_checkpoints import build_initial_state, load_tokens, full_snap, diff_deltas
from sim.simulator import step

LO, HI = 4505, 4535
tokens = load_tokens()
state = build_initial_state()
prev = full_snap(state)
for idx, tok in enumerate(tokens[:HI + 1]):
    state = step(state, tok)
    cur = full_snap(state)
    if LO <= idx <= HI:
        d = diff_deltas(prev, cur)
        mark = '   <<<<<< KEY:50' if tok.startswith('KEY:') else ''
        dstr = ('  Δ ' + ', '.join(d)) if d else ''
        print(f"tok[{idx}] {tok:<10} | {cur['floor']}({cur['x']},{cur['y']}) "
              f"HP={cur['hp']} DEF={cur['df']} 黄{cur['yk']}/蓝{cur['bk']}/红{cur['rk']}"
              f"{dstr}{mark}")
    prev = cur
