"""第1步（单上 P=购买能力）验证：两件事，一次跑完。
(1) 零回归硬底线：allow_purchase=False（默认）必须与【改动前老版 quotient.py】字节一致。
    做法：git show HEAD:solver/quotient.py 取出老版→importlib 当独立模块加载→与新版同输入对跑，
    比完整搜索签名（states_* / 指纹 / floors_seen / intercept_locs / wave_log / 目标前沿 / 动作串）。
    新版开关关 == 老版（老版无该参数，直接不传）→ 任一字段不符即 FAIL。
(2) 购买涌现：allow_purchase=True 跑同一配置，on_admit 捕获所有【动作串含 CHOICE】的入队态，
    按购买格归并，报：买了哪些格（商人钥匙/祭坛属性）、祭坛各买几次（看自收敛）、对比开关关的
    states_admitted/floors_seen/耗时膨胀。仅诊断，零碰核心；导出留给玩家终审。
"""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step
from solver.quotient import search_quotient as search_new
from probe_crossfloor import build_start
from vzone import build_zone, v_zone

# ── 配置：复用盲区探针同口径（cap6万/k50/V_zone），保证真撞到 choices 拦截路径 ──
CAP = 60000
K = 50
GOAL = ("MT0", 1, 1)


# 我这次 P 改动里【唯一影响搜索行为】的是 intercept 循环块（签名加参/helper/docstring 在旧循环下
# 全惰性）。baseline = 当前工作树把这块还原回【加 P 之前】的旧循环——只反向替换这一处，得到精确
# 「无 P」版本。NEW_LOOP/OLD_LOOP 逐字复刻自本次对 quotient.py 的编辑（任一不匹配即 assert 失败，
# 防转写漂移）。HEAD 不可用作 baseline：上个会话的 beam_score_fn 接入也是未提交改动，混在同一文件里。
NEW_LOOP = '''            for op in ops:
                res = _expand_op(state, free, op, step_fn)
                st.states_generated += 1
                if res is None:
                    continue
                child, op_moves = res
                if child.floor._event_intercepting:
                    intercept_locs.add((op[1], op[2]))   # choices 事件：陷拦截态（记录留痕）
                    if not allow_purchase:
                        continue                          # 老版口径：无 CHOICE→跳过（字节一致）
                    resolved = _resolve_choices(child, tuple(op_moves), step_fn)  # 解开买/不买/买N次
                else:
                    resolved = [(child, op_moves)]
                for rchild, rmoves in resolved:
                    if rchild.current_floor != state.current_floor:
                        # 离层子态：单层版一律裁掉；跨层版只放行楼梯边，事件传送(重置/结局/门禁传送)排除
                        if not cross_floor or op[0] != "stair":
                            continue
                    rchild, abs_moves = _absorb(rchild, step_fn)
                    if rchild.dead:
                        continue
                    child_free = _free_cells(rchild)
                    fp = _qfp(rchild, child_free)
                    cvec = value_vector(rchild)
                    cur = visited.get(fp)
                    if cur is not None and any(_ge_all(v, cvec) for v in cur):
                        continue
                    if cur is None:
                        visited[fp] = [cvec]
                    else:
                        visited[fp] = [v for v in cur if not _ge_all(cvec, v)] + [cvec]
                    st.states_admitted += 1
                    child_acts = acts + tuple(rmoves) + tuple(abs_moves)
                    if on_admit is not None:
                        on_admit(rchild, child_acts)
                    next_pts.append((rchild, child_acts))
                    if st.states_generated >= max_states:
                        st.hit_cap = True
                        break
                if st.hit_cap:
                    break
            if st.hit_cap:
                break'''

OLD_LOOP = '''            for op in ops:
                res = _expand_op(state, free, op, step_fn)
                st.states_generated += 1
                if res is None:
                    continue
                child, op_moves = res
                if child.floor._event_intercepting:
                    intercept_locs.add((op[1], op[2]))   # choices 事件：陷拦截态，无 CHOICE 口径→跳过+记录
                    continue
                if child.current_floor != state.current_floor:
                    # 离层子态：单层版一律裁掉；跨层版只放行楼梯边，事件传送(重置/结局/门禁传送)排除
                    if not cross_floor or op[0] != "stair":
                        continue
                child, abs_moves = _absorb(child, step_fn)
                if child.dead:
                    continue
                child_free = _free_cells(child)
                fp = _qfp(child, child_free)
                cvec = value_vector(child)
                cur = visited.get(fp)
                if cur is not None and any(_ge_all(v, cvec) for v in cur):
                    continue
                if cur is None:
                    visited[fp] = [cvec]
                else:
                    visited[fp] = [v for v in cur if not _ge_all(cvec, v)] + [cvec]
                st.states_admitted += 1
                child_acts = acts + tuple(op_moves) + tuple(abs_moves)
                if on_admit is not None:
                    on_admit(child, child_acts)
                next_pts.append((child, child_acts))
                if st.states_generated >= max_states:
                    st.hit_cap = True
                    break
            if st.hit_cap:
                break'''


def load_old_quotient():
    """baseline = 当前 solver/quotient.py 把 intercept 循环块还原回【加 P 之前】旧版，当独立模块加载。
    只反向替换这一处行为相关改动；其余加 P 的惰性改动（签名参/helper/docstring）保留无妨。"""
    cur = (ROOT / "solver" / "quotient.py").read_text(encoding="utf-8")
    assert NEW_LOOP in cur, "当前 quotient.py 找不到 NEW_LOOP（转写漂移？先核对编辑）"
    base = cur.replace(NEW_LOOP, OLD_LOOP, 1)
    assert base != cur and OLD_LOOP in base, "循环块反向替换未生效"
    tmp = ROOT / "solver" / "_quotient_baseline_tmp.py"
    tmp.write_text(base, encoding="utf-8")
    try:
        spec = importlib.util.spec_from_file_location("quotient_baseline_tmp", tmp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        tmp.unlink()   # 加载后即删，不留临时文件
    return mod.search_quotient


def make_score_fn():
    zone = build_zone()
    memo = {}

    def fn(s):
        hit = memo.get(id(s))
        if hit is not None and hit[0] is s:
            return hit[1]
        v = v_zone(zone, s)[0]
        memo[id(s)] = (s, v)
        return v
    return fn


def signature(res):
    """搜索结果的规范签名：覆盖全搜索轨迹。任一字段不一致 = 行为分叉。"""
    gf = sorted(tuple(sorted(v.items())) for v in (res.goal_frontier or []))
    return {
        "states_expanded": res.states_expanded,
        "states_generated": res.states_generated,
        "states_admitted": res.states_admitted,
        "distinct_fingerprints": res.distinct_fingerprints,
        "n_waves": res.n_waves,
        "frontier_peak": res.frontier_peak,
        "n_ops_total": res.n_ops_total,
        "n_blocks_peak": res.n_blocks_peak,
        "hit_cap": res.hit_cap,
        "floors_seen": list(res.floors_seen),
        "fp_by_floor": dict(sorted(res.fp_by_floor.items())),
        "intercept_locs": [list(t) for t in res.intercept_locs],
        "wave_log": [list(w) for w in res.wave_log],
        "found": res.found,
        "final_hp": res.final_hp,
        "actions": "".join(res.actions),
        "goal_frontier": gf,
    }


def run(search_fn, **kw):
    start, _ = build_start()
    t0 = time.perf_counter()
    res = search_fn(start, GOAL, step, max_states=CAP, cross_floor=True,
                    beam_k=K, beam_score_fn=make_score_fn(), **kw)
    return res, time.perf_counter() - t0


def part1_byte_identity():
    print("=" * 84)
    print("(1) 零回归：新版 allow_purchase=False  vs  老版(HEAD)  字节一致性")
    print("=" * 84)
    search_old = load_old_quotient()
    print(f"配置：cap={CAP} beam_k={K} score=V_zone cross_floor=True")
    res_old, dt_old = run(search_old)                          # 老版：无该参数
    res_new, dt_new = run(search_new, allow_purchase=False)    # 新版：开关关
    sig_old, sig_new = signature(res_old), signature(res_new)
    diffs = [k for k in sig_old if sig_old[k] != sig_new[k]]
    print(f"老版耗时 {dt_old:.1f}s  新版(关) 耗时 {dt_new:.1f}s")
    print(f"老版 floors_seen={sig_old['floors_seen']}  admitted={sig_old['states_admitted']} "
          f"指纹={sig_old['distinct_fingerprints']} intercept={sig_old['intercept_locs']}")
    if not diffs:
        print("✅ 字节一致：全部签名字段逐一相等（states_* / 指纹 / floors / intercept / "
              "wave_log / 目标前沿 / 动作串）。开关关 = 改动前老版，零回归成立。")
    else:
        print(f"❌ 不一致字段：{diffs}")
        for k in diffs:
            ov, nv = sig_old[k], sig_new[k]
            so, sn = str(ov), str(nv)
            print(f"   · {k}: 老={so[:120]}  新={sn[:120]}")
    return res_old, sig_old, dt_old, (not diffs)


def part2_purchase_emergence(sig_off, dt_off):
    print("\n" + "=" * 84)
    print("(2) 购买涌现：allow_purchase=True 同配置，看搜索自己买什么、祭坛买几次")
    print("=" * 84)
    buys = []   # (floor, x, y, n_choice, hp, atk, def_, gold, keys_tuple)

    def on_admit(stt, actions):
        if any(a.startswith("CHOICE:") for a in actions):
            h = stt.hero
            nch = sum(1 for a in actions if a.startswith("CHOICE:"))
            keys = tuple(sorted((k, v) for k, v in dict(h.keys).items() if v))
            buys.append((stt.current_floor, h.x, h.y, nch, h.hp, h.atk, h.def_, h.gold, keys))

    start, _ = build_start()
    t0 = time.perf_counter()
    res = search_new(start, GOAL, step, max_states=CAP, cross_floor=True,
                     beam_k=K, beam_score_fn=make_score_fn(),
                     allow_purchase=True, on_admit=on_admit)
    dt = time.perf_counter() - t0
    print(f"开关开 耗时 {dt:.1f}s  hit_cap={res.hit_cap}")
    print(f"floors_seen={list(res.floors_seen)}  admitted={res.states_admitted} "
          f"指纹={res.distinct_fingerprints}")
    print(f"对比开关关：admitted {sig_off['states_admitted']}→{res.states_admitted} "
          f"(Δ{res.states_admitted - sig_off['states_admitted']:+d})  "
          f"指纹 {sig_off['distinct_fingerprints']}→{res.distinct_fingerprints}  "
          f"耗时 {dt_off:.1f}s→{dt:.1f}s")
    print(f"intercept_locs(撞到的 choices 格)={[list(t) for t in res.intercept_locs]}")

    if not buys:
        print("\n⚠ 没有任何含 CHOICE 的入队态——本配置下搜索【没买】（可能金币不够/买了不划算被去重压掉/"
              "未到达可买格）。这本身是结论：买不买由价值决定，此跑判定不买。")
        return res

    print(f"\n含购买动作的入队态共 {len(buys)} 个。按【购买格归并】（看每格买了几次、属性/钥匙增量）：")
    from collections import defaultdict
    by_cell = defaultdict(list)
    for fl, x, y, nch, hp, atk, df, gold, keys in buys:
        by_cell[(fl, x, y)].append((nch, hp, atk, df, gold, keys))
    for (fl, x, y), lst in sorted(by_cell.items()):
        ncounts = sorted(set(n for n, *_ in lst))
        atks = sorted(set(a for _, _, a, _, _, _ in lst))
        defs = sorted(set(d for _, _, _, d, _, _ in lst))
        print(f"   {fl}({x},{y}) 停点态 {len(lst)} 个；CHOICE 次数集={ncounts}；"
              f"到此 ATK 取值={atks} DEF 取值={defs}")
    print("\n注：CHOICE 次数集 = 该停点经历的选择步数（祭坛连买会累加）；ATK/DEF 多取值 = 不同买次的"
          "并列态都被保留（Pareto），『买几次』由后续 beam/价值收敛，未写死。支配 route 的点待玩家终审导出。")
    return res


if __name__ == "__main__":
    res_old, sig_off, dt_off, ok = part1_byte_identity()
    part2_purchase_emergence(sig_off, dt_off)
    print("\n" + "=" * 84)
    print(f"第1步小结：零回归{'通过 ✅' if ok else '失败 ❌（先修字节一致再谈涌现）'}；"
          f"购买能力已接入（开关 allow_purchase，default False）。仅 solver/quotient.py 一处结构改动，"
          f"sim/ 零改。")
    print("=" * 84)
