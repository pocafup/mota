"""V_zone 验证 D【MT10 埋伏硬必杀段·纯 V_zone 连杀压力测试】(extract/ 隔离，零碰 solver 核心)。

玩家拍板 2：全量接入前，拿【现成的硬必杀段】MT10 埋伏单测纯 V_zone（固定 mon_cache 惩罚杀怪口径），
看「跑得通(愿意连杀 6 骷髅+2 士兵那一串、不卡死)」还是「卡死(惩罚口径让它不敢连杀、瘫在埋伏前)」。
  · 跑得通 → caveat 排除，动态 kill-neutral cache 不用做，全量直接上。
  · 卡死  → 证明需要动态 cache，那时再做。

⚠ MT10 埋伏的运行时特殊性（玩家点名、必须正确建测）：踩 (6,5) 才放出 6+2 怪、boss 从 (6,4)
  move 到 (6,1)、真战斗与开闸都在 afterBattle(6,1)——固定收缩图看不到放怪。故本测【用真实 step
  重放到"真踩埋伏触发后"的态】再跑 beam（不用静态收缩图，预演全量接入时埋伏/boss 搬家怎么处理）。

读源码（绝不手推）得到、本测要【实测裏取】的两条结构事实：
  ① V_zone 在 boss 层退化：shortest_toll(src=MT10 格, dst=None) 因 src 本身就在 MT10 层 → 立即
     reach=0 → D=boss_toll=常量 → 【MT10 上 V_zone=HP−常量】。即 boss 层无推进梯度、纯 HP 最大化，
     每个强制 kill 都是【纯掉 V_zone、零进度信用】＝惩罚杀怪口径的最坏情形。本测 D0 实测裏取。
  ② 隊長结构性不可杀：_killable(quotient.py:199) 排除 afterBattle/before_battle/arrive-event 怪 →
     MT10 隊長(6,1) 挂 afterBattle → 不生成 kill 算子。且 _boundary_ops 只产【自由块边界】算子、块内
     移动内部化 → 封在埋伏室里的英雄，边界算子=8 个 kill（无非杀逃逸选项）。本测 D1 实测裏取。

控制变量（透明披露）：真实到场 atk=100→对全 MT10 怪 0 伤害（test_combat_zero_damage 已证）→ 无惩罚、
  连杀免费、测不出怯战。故【覆盖 hero 属性】为可杀但要付血的中等值（默认 atk=20 铁剑/def=10/hp 充足
  保不致死），让每杀真掉血、真触发惩罚口径——这是本测唯一人为干预，余皆真实 step 产物。
"""
import argparse
import json
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from lzstring import LZString
from decode_route import parse_rle_route
from sim.simulator import GameState, HeroState, step, load_floor
from solver.quotient import (_free_cells, _boundary_ops, _expand_op, _absorb,
                             _qfp, _stairs_key, _killable)
from solver.beam import beam_select, value_vector
from vzone import build_zone, vzone
from seg_identify_zone1 import ZONE1
from probe_crossfloor import _fidx

Pt = namedtuple("Pt", ["state", "actions"])
DATA = Path(__file__).parent.parent / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
AMBUSH_POS = [(5, 4), (6, 4), (7, 4), (5, 5), (7, 5), (5, 6), (6, 6), (7, 6)]
CAPTAIN = (6, 1)
_ZONESET = set(ZONE1)
_D_CACHE = {}


# ────────────────────────── 种子：真实重放到埋伏触发后 ──────────────────────────

def load_tokens():
    route_path = next((Path(__file__).parent.parent).glob("51_*.h5route"), None)
    if route_path is None:
        raise SystemExit("存档 51_*.h5route 未找到")
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def make_initial_state():
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
        hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0), gold=hero_init.get("gold", 0),
        keys={}, items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero, floors={"MT1": floor}, current_floor="MT1",
        floor_ids=FLOOR_IDS, visited_floors={"MT1"},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def run_until(tokens, state, predicate, max_tokens=1400):
    for idx, tok in enumerate(tokens[:max_tokens]):
        state = step(state, tok)
        if predicate(state):
            return state, idx
    return state, -1


def seed_post_trigger():
    """真实重放到【踩 (6,5) 触发埋伏后】的 MT10 态：8 怪已放、隊長已 move 到 (6,1)、(6,3) 封 (tile85)。"""
    tokens = load_tokens()
    state, idx = run_until(
        tokens, make_initial_state(),
        predicate=lambda s: (s.current_floor == "MT10" and s.hero.x == 6 and s.hero.y == 5
                             and s.floors["MT10"].map[3][6] == 85))
    if idx == -1:
        raise SystemExit("未重放到 MT10(6,5) 埋伏触发态")
    return state, idx


# ────────────────────────── V_zone 评分（与验证 C 同口径）──────────────────────────

def vzone_score(state, zone):
    h = state.hero
    fid = state.current_floor
    if fid not in _ZONESET:
        return float(h.hp)
    key = (fid, h.x, h.y, h.atk, h.def_, h.mdef)
    D = _D_CACHE.get(key)
    if D is None:
        v, reach, bf = vzone(zone, fid, h.x, h.y, h.hp, h.atk, h.def_, h.mdef)
        D = (reach + bf) if reach != float("inf") else float("inf")
        _D_CACHE[key] = D
    return float("-inf") if D == float("inf") else (h.hp - D)


def _cleared(st):
    fl = st.floors["MT10"]
    return sum(1 for (x, y) in AMBUSH_POS if fl.entities[y][x] == 0)


def _captain_alive(st):
    fl = st.floors["MT10"]
    return fl._tile_to_enemy.get(fl.entities[CAPTAIN[1]][CAPTAIN[0]]) is not None


def expand(state, actions, step_fn):
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
    return out, s, ops


# ────────────────────────────── 诊断 D0 / D1 ──────────────────────────────

def diag_degeneracy(zone, seed):
    """D0：实测裏取『MT10 上 reach=0 → V_zone=HP−常量』退化。"""
    print("-" * 96)
    print("【D0 实测】boss 层 V_zone 退化：shortest_toll 从 MT10 任意格 reach 是否恒 0、D 是否恒 boss_toll？")
    h = seed.hero
    probes = [(seed.current_floor, h.x, h.y), ("MT10", 6, 4), ("MT10", 1, 11), ("MT10", 6, 8)]
    for (fid, x, y) in probes:
        v, reach, bf = vzone(zone, fid, x, y, h.hp, h.atk, h.def_, h.mdef)
        print(f"   {fid}({x:>2},{y:>2}): reach={reach:>3}  boss_toll={bf:>5}  D={reach + bf:>5}  "
              f"V_zone(HP={h.hp})={v:>6.0f}")
    print("   ⇒ reach 恒 0 ⇒ MT10 上 V_zone=HP−boss_toll(常量) ⇒ 每杀仅掉 HP、零进度信用（惩罚口径最坏情形）")


def diag_boundary_ops(seed):
    """D1：实测裏取『封在埋伏室的英雄边界算子=8 个 kill、隊長无 kill 算子』。"""
    print("-" * 96)
    print("【D1 实测】埋伏触发后种子态的边界算子：是否只有 8 个 kill（无非杀逃逸）、隊長(6,1)有无 kill 算子？")
    free = _free_cells(seed)
    ops = _boundary_ops(seed, free, cross_floor=True)
    kinds = {}
    kill_cells = []
    for op in ops:
        kinds[op[0]] = kinds.get(op[0], 0) + 1
        if op[0] == "kill":
            kill_cells.append((op[1], op[2]))
    print(f"   自由块格数={len(free)}  边界算子分类={kinds}")
    print(f"   kill 算子格={sorted(kill_cells)}")
    amb_killable = [c for c in kill_cells if c in AMBUSH_POS]
    cap_killable = CAPTAIN in kill_cells
    cap_state = "活" if _captain_alive(seed) else "已清"
    print(f"   其中埋伏怪 kill={sorted(amb_killable)}（命中 {len(amb_killable)}/8）")
    print(f"   隊長(6,1)[{cap_state}] 是否生成 kill 算子: {cap_killable}  "
          f"（_killable 判定={_killable(seed, *CAPTAIN)}，afterBattle 挂钩 → 预期 False）")
    nonkill_escape = [k for k in kinds if k != "kill"]
    print(f"   非 kill 的逃逸算子种类={nonkill_escape or '无'}  "
          f"⇒ {'封死、唯一推进=连杀（怯战无可逃逸、量子抽象上不可表达）' if not nonkill_escape else '存在非杀算子，需看 beam 是否偏好它（怯战可能）'}")


# ────────────────────────────── 主 beam 循环 ──────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=50, help="beam 宽 K")
    ap.add_argument("--waves", type=int, default=30)
    ap.add_argument("--atk", type=int, default=20, help="覆盖 hero atk（默认 20=铁剑，可杀但付血）")
    ap.add_argument("--def", dest="def_", type=int, default=10, help="覆盖 hero def")
    ap.add_argument("--hp", type=int, default=4000, help="覆盖 hero hp（取充足值避免被打死混淆怯战）")
    ap.add_argument("--no-diversity", action="store_true", default=True,
                    help="纯 V_zone（默认关分坑，与验证 C 隔离同口径）")
    ap.add_argument("--diversity", dest="no_diversity", action="store_false",
                    help="开 _stairs_key 分坑对照")
    args = ap.parse_args()

    zone = build_zone()
    seed, tok_idx = seed_post_trigger()

    print("=" * 96)
    print("V_zone 验证 D：MT10 埋伏硬必杀段·纯 V_zone 连杀压力测试（真实 step 触发埋伏后跑 beam）")
    print("=" * 96)
    h = seed.hero
    print(f"种子(真实重放 tok[0..{tok_idx}] 踩 (6,5) 触发埋伏后): {seed.current_floor}({h.x},{h.y})")
    print(f"  真实属性: HP={h.hp} ATK={h.atk} DEF={h.def_} keys={dict(h.keys)} "
          f"items={ {k: v for k, v in h.items.items() if v} }")
    print(f"  埋伏现状: 8 怪已清 {_cleared(seed)}/8  隊長(6,1)={'活' if _captain_alive(seed) else '已清'}  "
          f"(6,3)tile={seed.floors['MT10'].map[3][6]}(85=封)")

    # ── 覆盖属性（唯一人为干预，透明披露）──
    h.atk, h.def_, h.hp = args.atk, args.def_, args.hp
    _D_CACHE.clear()
    print(f"  ⚙ 覆盖属性(控制变量): ATK={h.atk} DEF={h.def_} HP={h.hp}  "
          f"（真到场 atk=100→0 伤害测不出怯战，覆盖为可杀付血值）")

    diag_degeneracy(zone, seed)
    diag_boundary_ops(seed)

    print("-" * 96)
    div_fn = None if args.no_diversity else _stairs_key
    print(f"跑 beam：K={args.k}  分坑={'关(纯V_zone)' if args.no_diversity else '_stairs_key'}  "
          f"观察：连杀 8 怪？卡在第几只？停因=结构(隊長不可杀)还是怯战(还有 kill 算子却不杀)？")
    v0 = vzone_score(seed, zone)
    print(f"种子 V_zone={v0:.0f}（覆盖属性后）")
    print("-" * 96)

    frontier = [Pt(seed, [])]
    visited = {}
    max_cleared = _cleared(seed)
    stall_reason = None

    for wave in range(1, args.waves + 1):
        next_pts = []
        wave_ops_kinds = {}
        for (st, acts) in frontier:
            outs, _absorbed, ops = expand(st, acts, step)
            for op in ops:
                wave_ops_kinds[op[0]] = wave_ops_kinds.get(op[0], 0) + 1
            next_pts.extend(outs)

        if not next_pts:
            # 前沿枯竭：分辨结构停 vs 怯战
            still_kill = wave_ops_kinds.get("kill", 0)
            stall_reason = ("frontier_empty", still_kill, dict(wave_ops_kinds))
            print(f"[wave {wave:>2}] 前沿枯竭。本轮可用算子={dict(wave_ops_kinds)}")
            break

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
            stall_reason = ("all_dominated", wave_ops_kinds.get("kill", 0), dict(wave_ops_kinds))
            print(f"[wave {wave:>2}] 全被已访问支配，停。本轮算子={dict(wave_ops_kinds)}")
            break

        kept, cut = beam_select(dedup, args.k, score_fn=lambda s: vzone_score(s, zone),
                                value_vec_fn=value_vector, diversity_key_fn=div_fn)

        cleared_kept = [_cleared(p.state) for p in kept]
        wave_max_clear = max(cleared_kept)
        max_cleared = max(max_cleared, wave_max_clear)
        cap_dead_any = any(not _captain_alive(p.state) for p in kept)
        vs = [vzone_score(p.state, zone) for p in kept]
        hps = [p.state.hero.hp for p in kept]
        print(f"[wave {wave:>2}] 候选{len(next_pts):>3}→去重{len(dedup):>3}→留{len(kept):>3} 砍{len(cut):>3}"
              f"  算子{dict(wave_ops_kinds)}  清怪[{min(cleared_kept)}..{wave_max_clear}]/8"
              f"  HP[{min(hps)}..{max(hps)}]  V[{min(vs):.0f}..{max(vs):.0f}]"
              f"  隊長已清={cap_dead_any}")

        frontier = kept
        if wave_max_clear >= 8:
            # 8 怪清完，再看隊長/出口：预期结构性停（隊長 afterBattle 不可杀）
            champ = max(kept, key=lambda p: _cleared(p.state))
            cs = champ.state
            free = _free_cells(cs)
            ops = _boundary_ops(cs, free, cross_floor=True)
            kk = sum(1 for op in ops if op[0] == "kill")
            cap_op = any((op[0] == "kill" and (op[1], op[2]) == CAPTAIN) for op in ops)
            print("-" * 96)
            print(f"  ★ 8 怪连杀完成！champ: MT10({cs.hero.x},{cs.hero.y}) HP={cs.hero.hp} "
                  f"(6,3)tile={cs.floors['MT10'].map[3][6]}  隊長={'活' if _captain_alive(cs) else '已清'}")
            print(f"    清完后边界算子={ {op[0]: 1 for op in ops} or '无'}  kill算子数={kk}  "
                  f"隊長生成kill算子={cap_op}")
            stall_reason = ("threaded_all_8", kk, cap_op)
            break

    # ────────────────────────── 结论 ──────────────────────────
    print("=" * 96)
    print("【验证 D 结论】")
    if stall_reason and stall_reason[0] == "threaded_all_8":
        kk, cap_op = stall_reason[1], stall_reason[2]
        print(f"  ✅ 连杀：纯 V_zone【愿意连杀全部 8 只埋伏怪】、未怯战瘫痪、未卡在埋伏前 → "
              f"惩罚口径在硬必杀段【不致瘫痪】。")
        print(f"     机理(D1 实测)：封在埋伏室时边界算子只有 kill（无非杀逃逸）→ 量子抽象下怯战不可表达、")
        print(f"     连杀是唯一推进 → 惩罚掉 V_zone 但无更高 V_zone 替代可逃 → 必然连杀。")
        if not cap_op:
            print(f"  ⚠ 但清完 8 只后【结构性停在隊長】：隊長(6,1)挂 afterBattle、_killable 排除 → 展开原语"
                  f"不生成 kill 算子(kill={kk}, 隊長算子={cap_op}) → beam 过不了 boss。")
            print(f"     这【与 V_zone/cache 口径无关】，是展开原语结构性不打挂事件怪——正是你点名的"
                  f"『埋伏/boss 搬家这类运行时机制怎么在 beam 里处理』开放问题，需独立于动态 cache 解决。")
    elif stall_reason and stall_reason[0] in ("frontier_empty", "all_dominated"):
        kk = stall_reason[1]
        print(f"  跑到第 stall：清怪上限={max_cleared}/8，停因={stall_reason[0]}，停时可用 kill 算子={kk}")
        if max_cleared < 8 and kk > 0:
            print(f"  ⚠⚠ 怯战嫌疑：还有 kill 算子可推进({kk}个)、却未清完 8 只就停 → 惩罚口径疑似让 beam 不敢连杀。"
                  f"需上动态 kill-neutral cache 复测。")
        elif max_cleared < 8:
            print(f"  停时已无 kill 算子但未清完 8——非怯战(可能被打死/几何)，查上面 wave 日志。")
    else:
        print(f"  跑满 {args.waves} wave 未达终止判定：清怪上限={max_cleared}/8（查 wave 日志）。")
    print("=" * 96)


if __name__ == "__main__":
    main()
