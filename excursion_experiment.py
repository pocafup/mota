"""【已作废 DEPRECATED 2026-06-08】——勿再运行/扩展，仅留作记录。

作废理由：本脚本是「缩点搜索缺跨层边」的症状，不是解法。它用导航脚本盲试四方向把勇者开到
楼梯邻格（每方向一次满 K 的 _run_block），抽象层级写错了，且实测 35 分钟卡死。正确做法是让
楼梯/飞行成为缩点边、上层块靠「付代价合并」自然进入搜索（见 docs/solver-design.md 第一性原理 +
data/games51/floor_graph.md 跨层边源码事实）。降 beam K 不是修法。
================================================================================================

向上远征验证实验（玩家 2026-06-08 批准的 B 第3点·最小验证实验）。

假设（玩家提出，让代码验证）：route 层序骨架近视——大额永久回报(shield 类防御)在骨架够不到的
上层；正确路线应含一段【向上远征】：从弹跳层(MT4/MT5)用【楼梯】爬几层、拿到上面的永久属性再
回来，其「防御提升带来的全程砍损血」可能抵得过远征路上的血亏+钥匙代价。

本实验做什么（全部由代码+引擎算，不在对话里手推）：
  1. 跑 phase1 前 LAUNCH 段拿到弹跳层(MT5)的发射前沿（=骨架内 A 的局部最优批）。
  2. 在发射前沿上【插入向上远征】：自动发现各层上行楼梯(读 change_floor，不写死方向/格)，逐层
     run-block 导航到楼梯邻格 + forced 踏上楼梯切层（楼梯已被引擎完整建模；fly 因 sim 过宽不可用，
     见铁律），一路 beam 控宽。爬到自然封顶层（探针证实 MT10→MT11 楼梯 enable=False），途中在
     顶层导航拿【永久属性道具】(读 items.json pickup.stat∈{atk,def,mdef} 识别，不写死"shield")。
  3. 再用下行楼梯原路下来归位 MT5。
  4. 全程用【跨区怪集】(MT4..MT9 全体怪，固定标尺)度量 Σ损血：远征前 vs 远征后属性 → 看 DEF/ATK
     涨了没、对全程怪的 Σ损血降了多少。这正是检验 A 的 Δ形式 V「跨区」那层够不够的关键。
  5. 引擎独立重放裁判远征终态（零差异才算数）。
  6. 报告：远征路线、与 route 逐项对比(DEF/HP/钥匙)、跨区 Σ损血升降、是否构成"支配 route"前置
     条件(永久属性更高+HP不亏)、耗时。若真支配则完整动作序列另行打出供玩家终审。

去哪层/拿什么/值不值 = V(Δ形式)+引擎损血算；本驱动只提供「可达性扩展(楼梯爬升)」与「度量」，
不预设"去 MT9 拿盾"为目标——MT9/shield 是数据里恰好够得着的最近大回报，是否值由度量说话。
塔特有信息(楼梯/层/道具)只在本驱动层读，sim/solver 一行未改。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state
from sim.simulator import (_DIR, _build_monster, _copy_state,
                           _load_floor_if_needed, _resolve_floor_id, step)
from solver.beam import _combat_damage, score_points
from solver.frontier import value_vector
from solver.verify import replay
import phase1

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "games51"
OUT = ROOT / "extract"
ITEMS = json.loads((DATA / "items.json").read_text(encoding="utf-8"))

LAUNCH = 6          # 跑前 6 段 → 首次进入 MT5（弹跳层），发射前沿在此
BEAM_K = 50
ZONE = ["MT4", "MT5", "MT6", "MT7", "MT8", "MT9"]   # 跨区 Σ损血标尺范围（弹跳+爬升区）


# ─── 永久属性道具识别（数据驱动，不写死 id）─────────────────────────────────────

def is_perm_attr_item(iid):
    """该道具 pickup 是否永久加 atk/def/mdef（gem/sword/shield 等）。读 items.json，不写死。"""
    eff = ITEMS.get(iid, {}).get("pickup")
    if not isinstance(eff, dict):
        return False
    if eff.get("type") == "stat" and eff.get("stat") in ("atk", "def", "mdef") \
            and (eff.get("delta") or eff.get("base")):
        return True
    if eff.get("type") == "multi":
        return any(o.get("stat") in ("atk", "def", "mdef") for o in eff.get("ops", []))
    return False


# ─── 楼梯自动发现（读 change_floor，不写死格/方向）─────────────────────────────

def _stairs(state):
    """返回 (up_stair, down_stair)：各为 (cell, target_floor) 或 (None,None)。
    up=目标层 floor_ids 序更大者；down=更小者。:next/:before 由引擎 _resolve_floor_id 解析。"""
    cur = state.floor_ids.index(state.current_floor)
    up = down = (None, None)
    for k, cf in state.floor.change_floor.items():
        ev = state.floor.events.get(k)
        if isinstance(ev, dict) and ev.get("enable") is False:
            continue                       # 未激活的楼梯（如 MT10→MT11）跳过
        tgt = _resolve_floor_id(state, cf["floorId"])
        if tgt not in state.floor_ids:
            continue
        cell = tuple(int(v) for v in k.split(","))
        if state.floor_ids.index(tgt) > cur:
            up = (cell, tgt)
        elif state.floor_ids.index(tgt) < cur:
            down = (cell, tgt)
    return up, down


def _approach_and_step(frontier, stair_cell, beam_k, tag):
    """把前沿导航到楼梯某【可达邻格】，再 forced 踏上楼梯格→切层。返回切层后前沿(空=失败)。
    四方向都试，取首个「导航非空且确实切层」者。N=楼梯格−_DIR[M]，从 N 朝 M 一步即踏上楼梯。"""
    floor = frontier[0].state.current_floor
    sx, sy = stair_cell
    best = []
    for M, (dx, dy) in _DIR.items():
        nx, ny = sx - dx, sy - dy
        nav, _ = phase1._run_block(frontier, floor, (nx, ny), None, None, beam_k,
                                   f"{tag}_nav{M}")
        if not nav:
            continue
        stepped, _ = phase1._forced_block(nav, M, None, beam_k, f"{tag}_step{M}")
        if stepped and stepped[0].state.current_floor != floor:
            if len(stepped) > len(best):
                best = stepped
    return best


def _grab_perm_items(frontier, beam_k, tag):
    """在当前层导航拿【永久属性道具】(数据识别)。每件作一条 run 分支 + 不拿分支一起 merge，
    交给 beam/V 决定值不值（不强制；但实验要测量，故保留拿到的分支）。返回 merge 后前沿。"""
    st0 = frontier[0].state
    floor = st0.current_floor
    targets = []
    for y, row in enumerate(st0.floor.entities):
        for x, tile in enumerate(row):
            iid = st0.floor._tile_to_item.get(tile)
            if iid is not None and is_perm_attr_item(iid):
                targets.append((x, y, iid))
    if not targets:
        return frontier, []
    pool = list(frontier)                  # 不拿分支
    for (x, y, iid) in targets:
        nav, _ = phase1._run_block(frontier, floor, (x, y), None, None, beam_k,
                                   f"{tag}_get_{iid}")
        pool.extend(nav)
    merged, _ = phase1.merge_frontier(pool)
    merged, _ = phase1._truncate(merged, None, beam_k, f"{tag}_grabmerge")
    return merged, targets


# ─── 跨区 Σ损血度量（固定标尺：ZONE 全体怪，kill-中性）──────────────────────────

def _zone_roster():
    """ZONE 各层【全体怪】(floor,x,y)->mid 并集，从干净初态读(全活=固定标尺)。
    度量「全程砍损血」用全集而非存活集——与 Δ形式 kill-中性同精神。"""
    s = build_initial_state()
    by_floor = {}
    for fid in ZONE:
        if not _load_floor_if_needed(s, fid):
            continue
        f = s.floors[fid]
        lst = []
        for y, row in enumerate(f.entities):
            for x, tile in enumerate(row):
                mid = f._tile_to_enemy.get(tile)
                if mid is not None:
                    lst.append((x, y, mid))
        by_floor[fid] = lst
    return by_floor


def _meas_state():
    s = build_initial_state()
    for fid in ZONE:
        _load_floor_if_needed(s, fid)
    return s


def _sigma_damage(meas, hero, roster_by_floor, big):
    """以 hero 的属性，对固定标尺 roster 算 Σ损血：可杀(损血<HP)→损血；打不动/会死→BIG。
    返回 (Σ, 打不动数, 总怪数, 可杀数)。meas.floor 切到怪所在层以正确 _build_monster。"""
    meas.hero = hero
    total = unkill = killable = 0
    n = 0
    for fid, lst in roster_by_floor.items():
        meas.current_floor = fid          # floor 属性随 current_floor 自动解析（只读）
        for (x, y, mid) in lst:
            n += 1
            d = _combat_damage(meas, mid)
            if d is not None and d < hero.hp:
                total += d
                killable += 1
            else:
                total += big
                unkill += 1
    return total, unkill, n, killable


def _zone_big(meas, hero, roster_by_floor):
    """BIG = 该 hero 属性下 ZONE 全标尺里最大可杀单怪损血（固定常量，跨态比较同标尺）。"""
    meas.hero = hero
    big = 0
    for fid, lst in roster_by_floor.items():
        meas.current_floor = fid          # floor 属性随 current_floor 自动解析（只读）
        for (x, y, mid) in lst:
            d = _combat_damage(meas, mid)
            if d is not None and d < hero.hp and d > big:
                big = d
    return big


# ─── 主流程 ────────────────────────────────────────────────────────────────────

def _best(frontier):
    """前沿里 Δ形式 V 最高点（本批 R/BIG），破平 HP、钥匙总数。"""
    roster, big, scores = score_points(frontier)
    return max(frontier, key=lambda p: (scores[id(p.state)],
                                        value_vector(p.state)["hp"],
                                        sum(p.state.hero.keys.values())))


def _hero_line(h):
    keys = " ".join(f"{k}={v}" for k, v in sorted(h.keys.items()) if v)
    items = " ".join(f"{k}={v}" for k, v in sorted(h.items.items()) if v)
    return (f"floor=? @({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} MDEF={h.mdef} "
            f"金={h.gold} kill={h.kill_count} 钥匙[{keys}] 道具[{items}]")


def main():
    t0 = time.perf_counter()
    print("=" * 92)
    print(f"向上远征验证实验：phase1 前 {LAUNCH} 段发射(MT5) → 楼梯爬升拿永久属性 → 归位；"
          f"beam K={BEAM_K}")
    print("=" * 92)

    # —— 1. 发射前沿 ——
    _, launch = phase1.run_phase1(num_segments=LAUNCH, beam_k=BEAM_K)
    if not launch:
        print("[终止] 发射前沿空")
        return
    lf = launch[0].state
    print(f"\n[发射] 前沿 {len(launch)} 点，位于 {lf.current_floor}@({lf.hero.x},{lf.hero.y})")

    # 跨区标尺（固定）+ BIG（以发射最优点属性定，跨态同标尺）
    roster_by_floor = _zone_roster()
    n_total = sum(len(v) for v in roster_by_floor.values())
    meas = _meas_state()
    base_pt = _best(launch)
    base_hero = _copy_state(base_pt.state).hero
    big = _zone_big(meas, base_hero, roster_by_floor)
    print(f"[跨区标尺] ZONE={ZONE} 共 {n_total} 怪；BIG(打不动代价)={big}（发射属性下最大可杀损血）")

    depth_log = []   # (label, floor, hero) 各深度最优点，统一标尺度量

    def log_depth(label, frontier):
        pt = _best(frontier)
        h = _copy_state(pt.state).hero
        sg, un, n, kl = _sigma_damage(meas, h, roster_by_floor, big)
        depth_log.append((label, pt.state.current_floor, h, sg, un, kl, n, pt))
        print(f"  [{label:<10}] {pt.state.current_floor}@({h.x},{h.y}) "
              f"HP={h.hp} ATK={h.atk} DEF={h.def_} MDEF={h.mdef} "
              f"钥匙Σ={sum(h.keys.values())} | 跨区Σ损血={sg} 打不动={un}/{n}")

    print("\n── 远征逐层（向上）─────────────────────────────────────────────────")
    log_depth("发射MT5", launch)
    frontier = launch

    # —— 2. 向上爬升（楼梯自动发现，爬到无上行楼梯为止）——
    visited_floors = [frontier[0].state.current_floor]
    for _ in range(8):    # 安全上限
        st = frontier[0].state
        (up_cell, up_tgt), _ = _stairs(st)
        if up_cell is None:
            print(f"  {st.current_floor} 无可用上行楼梯 → 爬升封顶")
            break
        nxt = _approach_and_step(frontier, up_cell, BEAM_K, f"up_{st.current_floor}")
        if not nxt:
            print(f"  {st.current_floor} 上行楼梯 {up_cell} 不可达 → 停")
            break
        frontier = nxt
        cur = frontier[0].state.current_floor
        visited_floors.append(cur)
        # 到达新层：导航拿永久属性道具
        frontier, tg = _grab_perm_items(frontier, BEAM_K, f"grab_{cur}")
        perm = [iid for (_, _, iid) in tg]
        log_depth(f"到{cur}", frontier)
        if perm:
            print(f"      {cur} 永久属性道具: {perm}")

    top_floor = frontier[0].state.current_floor
    print(f"\n[爬升封顶] {top_floor}；路线 {' → '.join(visited_floors)}")

    # —— 3. 向下归位回 MT5 ——
    print("\n── 远征逐层（向下归位）─────────────────────────────────────────────")
    for _ in range(8):
        st = frontier[0].state
        if st.current_floor == "MT5":
            break
        _, (dn_cell, dn_tgt) = _stairs(st)
        if dn_cell is None:
            print(f"  {st.current_floor} 无下行楼梯 → 停")
            break
        nxt = _approach_and_step(frontier, dn_cell, BEAM_K, f"dn_{st.current_floor}")
        if not nxt:
            print(f"  {st.current_floor} 下行楼梯 {dn_cell} 不可达 → 停")
            break
        frontier = nxt
        log_depth(f"回{frontier[0].state.current_floor}", frontier)

    # —— 4. 终态度量 + 引擎裁判 ——
    ret_pt = _best(frontier)
    ret_hero = _copy_state(ret_pt.state).hero
    rep = replay(build_initial_state(), ret_pt.actions, step, _copy_state)
    ok = (rep.current_floor == ret_pt.state.current_floor
          and (rep.hero.x, rep.hero.y) == (ret_pt.state.hero.x, ret_pt.state.hero.y)
          and rep.hero.hp == ret_hero.hp and rep.hero.atk == ret_hero.atk
          and rep.hero.def_ == ret_hero.def_ and rep.hero.kill_count == ret_hero.kill_count)

    bs, bu, bn, bk = _sigma_damage(meas, base_hero, roster_by_floor, big)
    rs, ru, rn, rk = _sigma_damage(meas, ret_hero, roster_by_floor, big)

    print("\n" + "=" * 92)
    print("远征 vs 发射基线（同一跨区标尺度量「全程砍损血」）")
    print("=" * 92)
    print(f"发射基线: {base_pt.state.current_floor}@({base_hero.x},{base_hero.y}) "
          f"HP={base_hero.hp} ATK={base_hero.atk} DEF={base_hero.def_} MDEF={base_hero.mdef} "
          f"钥匙Σ={sum(base_hero.keys.values())} tok={len(base_pt.actions)}")
    print(f"远征终态: {ret_pt.state.current_floor}@({ret_hero.x},{ret_hero.y}) "
          f"HP={ret_hero.hp} ATK={ret_hero.atk} DEF={ret_hero.def_} MDEF={ret_hero.mdef} "
          f"钥匙Σ={sum(ret_hero.keys.values())} tok={len(ret_pt.actions)}")
    print(f"Δ: HP {ret_hero.hp - base_hero.hp:+d}  ATK {ret_hero.atk - base_hero.atk:+d}  "
          f"DEF {ret_hero.def_ - base_hero.def_:+d}  MDEF {ret_hero.mdef - base_hero.mdef:+d}  "
          f"钥匙Σ {sum(ret_hero.keys.values()) - sum(base_hero.keys.values()):+d}  "
          f"tok {len(ret_pt.actions) - len(base_pt.actions):+d}")
    print(f"跨区 Σ损血: 发射={bs} (打不动{bu}/{bn}) → 远征={rs} (打不动{ru}/{rn})  "
          f"省血={bs - rs:+d}  可杀怪 {bk}→{rk}")
    dom = (ret_hero.def_ >= base_hero.def_ and ret_hero.atk >= base_hero.atk
           and (ret_hero.def_ > base_hero.def_ or ret_hero.atk > base_hero.atk)
           and ret_hero.hp >= base_hero.hp)
    print(f"\n引擎重放裁判: {'✅ 零差异' if ok else '❌ 不一致'}")
    print(f"支配前置(永久属性更高 且 HP不亏): {'✅ 成立' if dom else '✗ 不成立'}"
          f"（HP {ret_hero.hp - base_hero.hp:+d}；远征有血亏属正常代价，看跨区省血{bs - rs:+d}抵不抵）")

    OUT.mkdir(exist_ok=True)
    (OUT / "excursion_path.json").write_text(json.dumps({
        "launch_floor": lf.current_floor, "route_up": visited_floors,
        "base": {"hp": base_hero.hp, "atk": base_hero.atk, "def": base_hero.def_,
                 "mdef": base_hero.mdef, "keys": dict(base_hero.keys), "tok": len(base_pt.actions)},
        "ret": {"hp": ret_hero.hp, "atk": ret_hero.atk, "def": ret_hero.def_,
                "mdef": ret_hero.mdef, "keys": dict(ret_hero.keys), "tok": len(ret_pt.actions),
                "floor": ret_pt.state.current_floor},
        "sigma_base": bs, "sigma_ret": rs, "saved": bs - rs, "big": big,
        "zone": ZONE, "n_monsters": n_total, "engine_ok": ok,
        "actions": list(ret_pt.actions),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[落盘] extract/excursion_path.json  总耗时 {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
