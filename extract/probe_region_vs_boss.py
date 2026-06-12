"""只读探针（不碰产品码）：在真实决策态量一颗 +1atk 宝石的三个数，对照
   (a) boss 单怪减伤            —— 现 pull 的 value 口径（vzone.boss_toll，vzone.py:601）
   (b) 对本区剩余存活怪累计减伤 —— 区势能口径（复用 solver/beam.py:287 _future_potential）
   (c) 拿到后 base=HP−D_free 跃升 —— vzone.v_zone_score(κ=0)（vzone.py:512）

回答四问：①(b) 比 (a) 大几倍（区势能值不值得做）；②兑现侧 (c) 能否撑住路径A 的红线B
（守着引导分 > 拿到兑现分 → κ=1 复发？核心张力，量化 (b)/(c)、β_crit）；③据此选路径A/B
（本探针给数，选路在报告里）。④路径B 中层饿死另跑 probe_crossfloor_beam --score region --lam>0
--diversity stairs，非本探针。

决策态来源：重放已验证 k200_mt10_route.json（replay_ok=true，起点同 build_start 的开局噩梦后 MT3）
到目标步/层（probe_pull_flyaware.replay_snapshots 模板）。roster 从 build_start() 起点构（带
_floors_dir/floor_ids），复用于所有决策态；_future_potential 读决策态 live state.floors 算存活
残留（不依赖决策态自身 _floors_dir，第0步打印核实）。不改 sim/solver/vzone/beam。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from solver.beam import (build_future_roster, FutureCfg, _future_potential,
                         _region_bounds, _alive_mids_on, _future_toll)
from probe_crossfloor import build_start, _fidx
from vzone import build_zone, boss_toll, v_zone_score

ROUTE = Path(__file__).parent / "k200_mt10_route.json"


def replay_trace():
    """重放 k200 路线，返回 [(step_idx, state)]（step_idx=-1 是开局噩梦后的起点态）+ 动作数。"""
    state = build_start()[0]
    actions = json.loads(ROUTE.read_text(encoding="utf-8"))["actions"]
    trace = [(-1, state)]
    for i, a in enumerate(actions):
        state = step(state, a)
        trace.append((i, state))
    return trace, len(actions)


def _bump_atk(state, d):
    s = _copy_state(state)
    s.hero.atk += d
    return s


def region_breakdown(state, roster):
    """区内各层（非当前层）存活怪数 + Σtoll（当前 state.hero 属性算）。返回 {fid: (n_alive, Σtoll)}。
    复用 beam._alive_mids_on（存活残留）+ _future_toll（强制可杀参照 toll）。"""
    cur_idx = roster["idx_of"].get(state.current_floor)
    out = {}
    if cur_idx is None:
        return out
    lo, hi = _region_bounds(roster, cur_idx)
    for idx in range(lo, hi + 1):
        if idx == cur_idx:
            continue
        mids = _alive_mids_on(state, roster, idx)
        if not mids:
            continue
        sigma = sum(_future_toll(state, mid) for mid in mids)
        out[roster["floor_ids"][idx]] = (len(mids), sigma)
    return out


def measure(zone, roster, state):
    """三个数 (a),(b),(c) + 当前区势能/base 参照。+1atk 宝石（da=1,dd=0）。"""
    h = state.hero
    A = h.atk
    a = boss_toll(zone, A, h.def_, h.mdef) - boss_toll(zone, A + 1, h.def_, h.mdef)

    fut = FutureCfg(roster, 1)
    fp_A = _future_potential(state, fut)
    fp_A1 = _future_potential(_bump_atk(state, 1), fut)
    b = fp_A - fp_A1

    base_A = v_zone_score(zone, state, 0.0)[0]
    base_A1 = v_zone_score(zone, _bump_atk(state, 1), 0.0)[0]
    c = base_A1 - base_A
    return a, b, c, fp_A, base_A


def report_state(zone, roster, state, tag):
    h = state.hero
    print("=" * 104)
    print(f"【{tag}】floor={state.current_floor} ({h.x},{h.y}) HP={h.hp} "
          f"ATK={h.atk} DEF={h.def_} mdef={h.mdef} gold={h.gold}")
    a, b, c, fp_A, base_A = measure(zone, roster, state)
    print(f"  参照: 当前区势能 Σ_区(λ=1,存活)={fp_A:,.0f}   当前 base=HP−D_free={base_A:,.0f}")
    print(f"  +1atk 宝石三个数：")
    print(f"    (a) boss 单怪减伤          = {a:>12,.0f}   [现 pull 的 value 口径]")
    print(f"    (b) 区势能·剩余存活累计减伤 = {b:>12,.0f}   [beam._future_potential 差分]")
    print(f"    (c) 兑现基分 HP−D_free 跃升 = {c:>12,.0f}   [v_zone_score(κ=0) 差分]")
    print(f"  比值：", end="")
    print(f"(b)/(a)={b/a:.1f}×  " if a > 0 else "(b)/(a)=∞[(a)=0]  ", end="")
    if c > 0:
        beta_crit = c / b if b > 0 else float("inf")
        print(f"(b)/(c)={b/c:.1f}×  (a)/(c)={a/c:.2f}×  "
              f"β_crit≈(c)/(b)={beta_crit:.3f}（β 超此值则『相邻守着引导分>拿到兑现分』=κ=1复发）")
    else:
        print(f"(c)={c:,.0f}（≤0，+1atk 未降 D_free）")

    bd0 = region_breakdown(state, roster)
    bd1 = region_breakdown(_bump_atk(state, 1), roster)
    print(f"  区势能减伤的层间分布（+1atk 对各层存活怪 Σtoll 的降幅）：")
    for fid in sorted(set(bd0) | set(bd1), key=_fidx):
        n0, s0 = bd0.get(fid, (0, 0))
        _n1, s1 = bd1.get(fid, (0, 0))
        mark = "  ←当前层下方(回收)" if _fidx(fid) < _fidx(state.current_floor) else ""
        print(f"    {fid:>5}: 存活{n0:>2}怪  Σtoll {s0:>11,.0f} → {s1:>11,.0f}  "
              f"降{s0 - s1:>9,.0f}{mark}")


def main():
    trace, n = replay_trace()
    zone = build_zone()
    start = trace[0][1]
    roster = build_future_roster(start)

    # 第0步：核实重放态是否带 build_future_roster 所需属性（handoff 待确认项，勿静默假设）
    mid = trace[len(trace) // 2][1]
    print("=" * 104)
    print("第0步·重放决策态属性核实（勿静默假设）：")
    print(f"  重放态 _floors_dir={hasattr(mid, '_floors_dir')}  "
          f"floor_ids={hasattr(mid, 'floor_ids')}  "
          f"floor._tile_to_enemy={hasattr(mid.floor, '_tile_to_enemy')}  "
          f"floors={type(mid.floors).__name__}")
    print(f"  → roster 从起点(build_start，确有 _floors_dir)构；_future_potential 读决策态 live "
          f"state.floors 算存活残留，安全。")
    print(f"  区边界(boss 层)={[roster['floor_ids'][b] for b in roster['boss_idxs']]}  "
          f"route 动作数={n}")

    # 路线落点速览（核对 handoff 标的 step≈位置）
    def floor_at(idx):
        s = trace[idx + 1][1] if 0 <= idx + 1 < len(trace) else None
        return s.current_floor if s else "—"
    print(f"  落点速览: step239={floor_at(239)} step366={floor_at(366)} "
          f"step506={floor_at(506)}（handoff 标 MT5剑后~239 / 就近打 366·506）")

    # 决策态①：MT5 刚拿铁剑（首个在 MT5 atk 跳 ≥10 的步）
    sword = None
    for k in range(1, len(trace)):
        i, s = trace[k]
        ps = trace[k - 1][1]
        if s.current_floor == "MT5" and s.hero.atk - ps.hero.atk >= 10:
            sword = (i, s)
            break

    # 决策态②③：就近打点 step366 / step506（直接索引）
    def at(idx):
        k = idx + 1
        return trace[k][1] if 0 <= k < len(trace) else None

    # 决策态④：首入 MT9
    mt9 = next(((i, s) for i, s in trace if s.current_floor == "MT9"), None)

    if sword:
        report_state(zone, roster, sword[1], f"MT5 刚拿铁剑 (step {sword[0]})")
    else:
        print("⚠ 未在 MT5 检测到 atk 跳 ≥10（铁剑）——k200 路线可能未在 MT5 拿剑。")

    for idx in (366, 506):
        s = at(idx)
        if s:
            report_state(zone, roster, s, f"就近打点 step {idx}")
        else:
            print(f"⚠ step {idx} 超出路线长度 {n}。")

    if mt9:
        report_state(zone, roster, mt9[1], f"首入 MT9 (step {mt9[0]})")
    else:
        print("⚠ k200 路线未经过 MT9（可能卡更早层）。")

    print("=" * 104)


if __name__ == "__main__":
    main()
