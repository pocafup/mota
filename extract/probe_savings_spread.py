"""【只读诊断】实测 savings(κ折价项) 在 frontier 上的分布 + 盾的钥匙可达性。

回答玩家三问之 #13/#12 收尾：
  · savings 是否"对同期态几乎一样大、不重排序"？(我此前的诊断,需实测坐实/证伪)
  · 在手的任何态,MT9 铁盾格 (9,7) 是否在 _drel_reachable(只用手上钥匙) 里？
    —— 若全 False ⟹ savings 永远算不进盾的折价 ⟹ κ 对"拿盾"天然失灵(根因坐实)。

做法：把 κ=1 跑出的 cut 态(动作串)用引擎 replay 重放回真实 state,逐个算
v_zone_score(κ=1) 的 savings 项 + 查盾格可达性。不改任何求解逻辑,纯测量。
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from solver.verify import replay
from vzone import build_zone, v_zone_score, _drel_reachable, _zone_attr_gems
from probe_crossfloor import build_start

CUT = Path(__file__).parent / "crossbeam_cut_K50_vzone_k1_lam0.0_none.jsonl"
SHIELD = ("MT9", 9, 7)


def load_cuts(fn):
    rows = []
    with open(fn, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def main():
    start = build_start()[0]
    zone = build_zone()                  # 无参：内部建草稿态，绝不污染搜索起点 start
    gems = _zone_attr_gems(zone)
    print("=" * 92)
    print(f"盾格 {SHIELD} 在属性宝石表? {SHIELD in gems}  Δ={gems.get(SHIELD)}")
    print(f"一区攻防宝石共 {len(gems)} 处")
    rows = load_cuts(CUT)
    print(f"载入 κ=1 cut 态 {len(rows)} 条，逐个重放算 savings + 盾可达性…")
    print("=" * 92)

    # 采样：每层都要有代表；按 wave 桶聚合测"同期离散度"
    by_wave = defaultdict(list)          # wave -> [savings,...]
    shield_reach_cnt = 0
    pos_savings = []                     # 所有 savings>0
    leaders = []                         # (floor_idx, ykeys, savings, shield_ok, atk, def, info)
    n_done = 0

    def fk(s):
        try:
            return int(s[2:])
        except Exception:
            return -1

    # 全量重放(纯 RULD 动作串)；逐条对账日志值，保真才采信
    mismatch = 0
    for r in rows:
        acts = list(r["actions"])
        st = replay(start, acts, step, _copy_state)
        if (st.current_floor != r["floor"] or st.hero.atk != r["atk"]
                or st.hero.def_ != r["def"] or st.hero.hp != r["hp"]):
            mismatch += 1
            continue                      # 重放对不上日志→不采信此态
        score, D, savings, info = v_zone_score(zone, st, 1.0)
        reached = _drel_reachable(zone, st, st.hero.keys)
        shield_ok = SHIELD in reached
        by_wave[r["wave"]].append(savings)
        if savings > 0:
            pos_savings.append(savings)
        if shield_ok:
            shield_reach_cnt += 1
        yk = st.hero.keys.get("yellowKey", 0)
        leaders.append((fk(st.current_floor), yk, savings, shield_ok,
                        st.hero.atk, st.hero.def_, st.current_floor))
        n_done += 1

    print(f"\n重放完成 {n_done} 态（对账保真，重放≠日志而弃用 {mismatch} 条）。")
    print("─" * 92)
    print(f"【盾可达性】MT9 盾格在 _drel_reachable(只用手上钥匙) 里的态数: "
          f"{shield_reach_cnt} / {n_done}")
    if shield_reach_cnt == 0:
        print("  ⟹ 没有任何在手态够得到盾(钥匙意义) ⟹ savings 永远不含盾折价 ⟹ κ 对'拿盾'天然失灵。")
    print("─" * 92)
    print(f"【savings 全局】>0 的态: {len(pos_savings)} / {n_done}"
          f"   {'(全为 0!)' if not pos_savings else ''}")
    if pos_savings:
        pos_savings.sort()
        import statistics
        print(f"  savings>0 分布: min={min(pos_savings)} "
              f"中位={statistics.median(pos_savings):.0f} max={max(pos_savings)} "
              f"均值={statistics.mean(pos_savings):.0f}")
    print("─" * 92)
    print("【同期(同 wave)离散度】抽几个 frontier 快照看 savings 在同期态里是否近似常数:")
    print("  wave | #态 | savings: min  max  spread  | 唯一值数")
    waves_sorted = sorted(by_wave, key=lambda w: -len(by_wave[w]))[:12]
    for w in sorted(waves_sorted):
        sv = by_wave[w]
        uniq = len(set(sv))
        print(f"  {w:>4} | {len(sv):>4} | {min(sv):>6} {max(sv):>6} {max(sv)-min(sv):>7}  | {uniq}")
    print("─" * 92)
    print("【最有希望拿盾的态】按(楼层↓, 黄钥↓)排，看顶尖候选 savings + 盾可达 + 可达到哪些宝石:")
    leaders.sort(key=lambda t: (-t[0], -t[1]))
    for fl_i, yk, sav, sok, atk, df, fl in leaders[:12]:
        print(f"  {fl}(idx{fl_i}) 黄钥={yk} atk={atk} def={df} | savings={sav} 盾可达={sok}")
    print("=" * 92)


if __name__ == "__main__":
    main()
