"""route 首次通过 vs 后期回访 属性审计（玩家 2026-06-08 纠基准）。

背景：之前「搜索 vs route」对照里，route 那列用的是【该层全程峰值属性】(max over 所有访问)。
但 route 是整条 50 层通关存档——大后期会回头反复经过低层(找商人刷 3% 属性、收尾)。所以「MT2 峰
26391/507/373」是【后期回访】态，不是一区首次通过的水平。把后期高属性当该层同期基准 → 参照系错乱。

本脚本沿 route 逐 token 重放，把每层切成【访问段】(maximal 连续同层 run)，分别打印：
  首次进入 / 首次离开 该层时的 (HP/ATK/DEF)  vs  该层全程峰值 + 峰值出现的 token 位置(暴露是不是大后期)。
口径与 route_profile 一致：只记开局噩梦之后 (token≥OPENING_PREFIX) 的轨迹。
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import step
from probe_crossfloor import _fidx, OPENING_PREFIX


def main():
    state = build_initial_state()
    tokens = load_tokens()

    # 逐 token 重放，记录开局噩梦之后的 (floor, hp, atk, def) 轨迹
    traj = []
    for i, tok in enumerate(tokens):
        state = step(state, tok)
        if i >= OPENING_PREFIX - 1:
            h = state.hero
            traj.append((state.current_floor, h.hp, h.atk, h.def_))
    n = len(traj)

    # 切访问段：current_floor 连续相同为一段
    visits = []   # (floor, entry(hp,atk,def), exit(hp,atk,def), start_idx, end_idx)
    cur = None
    seg_start = 0
    for idx, (fl, hp, atk, df) in enumerate(traj):
        if fl != cur:
            if cur is not None:
                pe = traj[idx - 1]
                visits.append((cur, tuple(traj[seg_start][1:]),
                               (pe[1], pe[2], pe[3]), seg_start, idx - 1))
            cur = fl
            seg_start = idx
    pe = traj[-1]
    visits.append((cur, tuple(traj[seg_start][1:]),
                   (pe[1], pe[2], pe[3]), seg_start, n - 1))

    # 每层聚合：访问次数 / 首次进入 / 首次离开 / 全程峰(含峰值 token 位置)
    pf = {}
    for (fl, ent, ext, s, e) in visits:
        d = pf.setdefault(fl, {"visits": 0, "first_entry": None, "first_exit": None,
                               "peak_hp": (-1, -1), "peak_atk": (-1, -1), "peak_def": (-1, -1)})
        d["visits"] += 1
        if d["first_entry"] is None:
            d["first_entry"] = ent
            d["first_exit"] = ext
    for idx, (fl, hp, atk, df) in enumerate(traj):
        d = pf[fl]
        if hp > d["peak_hp"][0]:
            d["peak_hp"] = (hp, idx)
        if atk > d["peak_atk"][0]:
            d["peak_atk"] = (atk, idx)
        if df > d["peak_def"][0]:
            d["peak_def"] = (df, idx)

    floors = sorted(pf, key=_fidx)
    print("=" * 108)
    print(f"route 首次通过 vs 后期回访 属性审计（噩梦后轨迹 {n} 个记录态；token 位置 i/{n} 越靠后=越大后期）")
    print("=" * 108)
    print(f"{'层':>5} {'访问':>4} {'首入(hp/atk/def)':>20} {'首离(hp/atk/def)':>20} "
          f"{'全程峰hp@tok':>16} {'峰atk@tok':>14} {'峰def@tok':>14}")
    print("-" * 108)
    for fl in floors:
        d = pf[fl]
        fe = d["first_entry"]
        fx = d["first_exit"]
        ph, phi = d["peak_hp"]
        pa, pai = d["peak_atk"]
        pd, pdi = d["peak_def"]
        zone = "★一区" if 1 <= _fidx(fl) <= 10 else ""
        print(f"{fl:>5} {d['visits']:>4} "
              f"{fe[0]:>6}/{fe[1]:>3}/{fe[2]:>3}   "
              f"{fx[0]:>6}/{fx[1]:>3}/{fx[2]:>3}   "
              f"{ph:>6}@{phi:<6} {pa:>4}@{pai:<6} {pd:>4}@{pdi:<6} {zone}")
    print("-" * 108)

    # 一区(MT1-10)首次通过真实属性曲线 + 关键判定：首离 ATK 是否 < 50
    z1 = [fl for fl in floors if 1 <= _fidx(fl) <= 10]
    print("一区(MT1-10) 首次离开该层时的 ATK（玩家实测：一区结束攻击不到 50）：")
    for fl in z1:
        fx = pf[fl]["first_exit"]
        pa, pai = pf[fl]["peak_atk"]
        late = "  ← 峰值在大后期回访" if pai > 0.7 * n else ""
        print(f"  {fl}: 首离 ATK={fx[1]:>3}  DEF={fx[2]:>3}  HP={fx[0]:>6}   "
              f"| 全程峰 ATK={pa}@tok{pai}{late}")
    if z1:
        max_first_atk = max(pf[fl]["first_exit"][1] for fl in z1)
        print(f"→ 一区首次通过 ATK 上界 = {max_first_atk}（首离口径）  "
              f"{'✅ <50，与玩家实测吻合' if max_first_atk < 50 else '❌ ≥50，与玩家实测矛盾，需排查'}")


if __name__ == "__main__":
    main()
