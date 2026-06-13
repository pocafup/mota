"""route 到底在哪一步、什么属性下杀掉 MT10 队长（flag:10f战胜骷髅队长）？
查清"队长是一区首过必杀闸门、还是后期高属性回头清"——直接关系 V_zone 把队长当区边界对不对。仅诊断。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import step

FLAG = "10f战胜骷髅队长"

state = build_initial_state()
tokens = load_tokens()
n = len(tokens)
print(f"route 总 token 数 = {n}")

prev_flag = bool(state.hero.flags.get(FLAG))
first_mt10_idx = None
flag_flip_idx = None
# 记录每次进入/离开 MT10 的属性轨迹（看首过 vs 回访）
mt10_visits = []
prev_floor = state.current_floor

for i, tok in enumerate(tokens):
    state = step(state, tok)
    h = state.hero
    fl = state.current_floor
    if fl == "MT10" and prev_floor != "MT10":
        mt10_visits.append(("进", i, h.hp, h.atk, h.def_))
        if first_mt10_idx is None:
            first_mt10_idx = i
    if fl != "MT10" and prev_floor == "MT10":
        mt10_visits.append(("出", i, h.hp, h.atk, h.def_))
    now_flag = bool(h.flags.get(FLAG))
    if now_flag and not prev_flag:
        flag_flip_idx = i
        print("=" * 80)
        print(f"★ 队长被杀（flag『{FLAG}』翻 True）在 token[{i}]（进度 {i / n * 100:.1f}%）")
        print(f"   此刻: 层={fl} ({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_}")
        print("=" * 80)
    prev_flag = now_flag
    prev_floor = fl

print(f"\nMT10 首次进入 token[{first_mt10_idx}]（进度 {first_mt10_idx / n * 100:.1f}%）")
print(f"队长清除 token[{flag_flip_idx}]（进度 {flag_flip_idx / n * 100:.1f}%）" if flag_flip_idx
      else "全程未见队长 flag 翻 True（？）")
if first_mt10_idx is not None and flag_flip_idx is not None:
    gap = flag_flip_idx - first_mt10_idx
    print(f"首过 MT10 → 清队长 相隔 {gap} 步"
          f"  ⇒ {'首过即清（同次访问）' if gap < 50 else '⚠ 隔很久，后期回头清（非一区首过闸门）'}")

print(f"\nMT10 进/出轨迹（前 12 次）:")
for tag, i, hp, atk, df in mt10_visits[:12]:
    print(f"   [{tag}] token[{i:>4}] HP={hp:>5} ATK={atk:>3} DEF={df:>3}")
