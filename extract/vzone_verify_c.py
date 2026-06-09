"""V_zone 验证 C【从 MT3 裸攻态真跑 beam，看谷底是否被砍】(extract/ 隔离，零碰 solver 核心)。

玩家拍板方案(a)：复用 build_start 噩梦后起点 + sim.step 真展开 + solver 展开原语
(_absorb/_boundary_ops/_expand_op/_qfp，皆公开可调) + beam.beam_select 真截断；自写 wave 循环，
唯一把 search_quotient 的【区势能 score】换成【V_zone score】——隔离 V_zone 这一个变量。

核心问题：beam 用 V_zone 评分，会不会自己搜出"绕去 MT5(11,11) 拿铁剑(atk10→20)再回来"，
还是中途把"去拿剑路上 atk 还=10、血却掉了、V_zone 还低"的谷底态砍掉(Q2)。

⚠ V_zone 口径(第一版固定 mon_cache，全怪都在算 D)：杀路上怪 → HP↓f 但 D 不降(cache 固定) →
  V_zone↓f，即【惩罚杀怪】。这是 admissible 下界的保守副作用，比玩家设计的 kill-neutral 口径
  【更严苛】(更不愿杀怪去 MT5)→ 若此口径下谷底仍不被砍，结论更强；若被砍，需辨是"杀怪惩罚"
  假阳性还是真问题(再上动态 cache)。配 _stairs_key 分坑保护(与 search_quotient beam_diversity 同口径)。
"""
import argparse
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start, _fidx
from sim.simulator import step
from solver.quotient import _free_cells, _boundary_ops, _expand_op, _absorb, _qfp, _stairs_key
from solver.beam import beam_select, value_vector
from vzone import build_zone, vzone
from seg_identify_zone1 import ZONE1

Pt = namedtuple("Pt", ["state", "actions"])
_ZONESET = set(ZONE1)


_D_CACHE = {}                              # (fid,x,y,atk,def,mdef) -> D=reach+boss（hp 外加，不入键）


def vzone_score(state, zone):
    """V_zone = HP − D(当前格→boss 最短损血路)。越高越好。出 ZONE1 / 无路 → 兜底。D 按属性+位置缓存。"""
    h = state.hero
    fid = state.current_floor
    if fid not in _ZONESET:
        return float(h.hp)                 # 出区(不该发生)：乐观兜底，不污染排序
    key = (fid, h.x, h.y, h.atk, h.def_, h.mdef)
    D = _D_CACHE.get(key)
    if D is None:
        v, reach, bf = vzone(zone, fid, h.x, h.y, h.hp, h.atk, h.def_, h.mdef)
        D = (reach + bf) if reach != float("inf") else float("inf")
        _D_CACHE[key] = D
    return float("-inf") if D == float("inf") else (h.hp - D)


def _has_iron(st):
    """是否已装备铁剑 sword1（玩家验证 C 的真目标：去 MT5(11,11) 拿铁剑 atk+10，非就近红宝石 atk+1）。"""
    return st.hero.flags.get("nowWeapon") == "sword1"


def expand(state, actions, step_fn):
    """展开一个态：先 _absorb 吸收块内道具(含铁剑→atk涨) → 逐边界算子 _expand_op 产 successor。"""
    s, mv0 = _absorb(state, step_fn)
    base_acts = actions + mv0
    free = _free_cells(s)
    ops = _boundary_ops(s, free, cross_floor=True)
    out = []
    for op in ops:
        r = _expand_op(s, free, op, step_fn)
        if r is None:
            continue
        ns, mv = r
        if ns.dead:
            continue
        out.append((ns, base_acts + mv))
    # _absorb 后若 atk 已涨(拿到铁剑)，把"吸收后态"也作为一个里程碑 successor 暴露(即便无边界算子)
    return out, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=50, help="beam 宽 K")
    ap.add_argument("--waves", type=int, default=40, help="最多跑几个 BFS wave")
    ap.add_argument("--no-diversity", action="store_true",
                    help="关掉 _stairs_key 分坑保护(裸看纯 V_zone 截断，更严苛)")
    args = ap.parse_args()

    zone = build_zone()
    start, nopen = build_start()
    h0 = start.hero
    div_fn = None if args.no_diversity else _stairs_key

    print("=" * 96)
    print("V_zone 验证 C：从 MT3 噩梦后裸攻态真跑 beam（V_zone 评分 + 真实展开/分坑保护）")
    print("=" * 96)
    print(f"起点: {start.current_floor}({h0.x},{h0.y}) HP={h0.hp} ATK={h0.atk} DEF={h0.def_}  "
          f"K={args.k}  分坑={'关(纯V_zone)' if args.no_diversity else '_stairs_key(保护climber)'}")
    print(f"目标观察: beam 能否搜到 MT5(11,11) 铁剑(atk→20)；去拿剑谷底态(atk=10/血降/朝MT4-5)是否被砍")
    v0 = vzone_score(start, zone)
    print(f"起点 V_zone = {v0}  (HP={h0.hp} − D)")
    print("-" * 96)

    frontier = [Pt(start, [])]
    visited = {}                            # qfp -> 见过的最高 V_zone（防环 + 允许严格更优重访）
    sword_wave = None                       # beam 首次出现 atk≥20(拿到铁剑) 的 wave
    best_floor_reached = "MT3"
    cut_valley_total = 0

    for wave in range(1, args.waves + 1):
        next_pts = []
        for (st, acts) in frontier:
            outs, absorbed = expand(st, acts, step)
            # 里程碑：吸收后属性涨了的态本身也进候选（防"拿到装备但无出边被忽略"）
            if absorbed.hero.atk > st.hero.atk or _has_iron(absorbed):
                outs = outs + [(absorbed, acts)]
            next_pts.extend(outs)

        if not next_pts:
            print(f"[wave {wave}] 前沿枯竭，停。")
            break

        # 指纹去重（同 _qfp 保留 V_zone 最高）+ 全局防环
        best = {}
        for (ns, a) in next_pts:
            free = _free_cells(ns)
            fp = _qfp(ns, free)
            v = vzone_score(ns, zone)
            if fp in visited and v <= visited[fp]:
                continue
            if fp not in best or v > best[fp][0]:
                best[fp] = (v, ns, a)
        dedup = [Pt(ns, a) for (v, ns, a) in best.values()]
        for fp, (v, ns, a) in best.items():
            visited[fp] = max(visited.get(fp, float("-inf")), v)

        if not dedup:
            print(f"[wave {wave}] 全被已访问支配，停。")
            break

        # beam 截断（唯一变量：score_fn=V_zone）
        pts = dedup
        kept, cut = beam_select(pts, args.k, score_fn=lambda s: vzone_score(s, zone),
                                value_vec_fn=value_vector, diversity_key_fn=div_fn)

        # 观察统计
        floors = {}
        max_atk = start.hero.atk
        deepest = "MT3"
        for p in kept:
            f = p.state.current_floor
            floors[f] = floors.get(f, 0) + 1
            max_atk = max(max_atk, p.state.hero.atk)
            if _fidx(f) > _fidx(deepest):
                deepest = f
            if _fidx(f) > _fidx(best_floor_reached):
                best_floor_reached = f
        # cut 里的"去拿剑谷底": 已推进到 MT4+(朝铁剑去)、却还没装铁剑 → 被砍
        valley_cut = [p for p in cut
                      if _fidx(p.state.current_floor) >= _fidx("MT4")
                      and not _has_iron(p.state)]
        cut_valley_total += len(valley_cut)

        got_iron = any(_has_iron(p.state) for p in kept)
        if got_iron and sword_wave is None:
            sword_wave = wave

        fl_str = " ".join(f"{k}:{v}" for k, v in sorted(floors.items(), key=lambda kv: _fidx(kv[0])))
        flag = "  ★装备铁剑(atk+10)" if got_iron else ""
        vbar = f"V[{min(vzone_score(p.state, zone) for p in kept):.0f}..{max(vzone_score(p.state, zone) for p in kept):.0f}]"
        print(f"[wave {wave:>2}] 候选{len(next_pts):>4}→去重{len(dedup):>3}→留{len(kept):>3} 砍{len(cut):>3}"
              f"  层[{fl_str}] 最深{deepest} maxATK={max_atk} {vbar}"
              f"  谷底被砍={len(valley_cut)}{flag}")

        frontier = kept
        if got_iron:
            champ = max((p for p in kept if _has_iron(p.state)),
                        key=lambda p: vzone_score(p.state, zone))
            ch = champ.state.hero
            print(f"         ↳ 铁剑态: {champ.state.current_floor}({ch.x},{ch.y}) "
                  f"HP={ch.hp} ATK={ch.atk} DEF={ch.def_}  V_zone={vzone_score(champ.state, zone):.0f}"
                  f"  (动作{len(champ.actions)}步)")
            break

    print("-" * 96)
    print("【验证 C 结论】")
    if sword_wave is not None:
        print(f"  ✅ beam 在第 {sword_wave} wave 自己搜到'去 MT5 装备铁剑'(atk+10)，谷底未被砍死 → "
              f"V_zone 诱导了延迟战斗(Q2 解)。")
    else:
        print(f"  ⚠ 跑满 {args.waves} wave 未装上铁剑，最远到 {best_floor_reached}，"
              f"累计砍掉去拿剑谷底态(MT4+未装铁剑) {cut_valley_total} 个 → 谷底疑似被砍，V_zone 单独不够，"
              f"需配'保护必经谷底'机制(加大 K / 动态 cache kill-neutral / 强制 climber 配额)。")
    print("=" * 96)


if __name__ == "__main__":
    main()
