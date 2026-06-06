"""段实验通用驱动（塔无关框架；塔特有参数由 cfg 注入）。

闭环：重放建入口 state → 通用搜索(solver.search) → 引擎裁判独立重放(solver.verify)
→ 验收三条 + 出口 Pareto 前沿 + 严格更优查询 + 性能报告(cProfile)。

定位：本文件是【实验驱动】，不是引擎/求解器——可 import sim 与数据路径。
但段的塔特有参数(层/token/出口格/基准/route真值)全部由 cfg 注入，driver 不写死
任何塔信息；solver/ 仍全程塔无关。
"""
import cProfile
import io
import json
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step, _copy_state
from solver.search import search_segment, _gives_hp_on_pickup
from solver.verify import replay, diff_states

DATA = Path(__file__).parent / "data/games51"
FLOORS = DATA / "floors"


def build_initial_state():
    floor_ids = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    kb_raw = json.loads((DATA / "replay_keybindings.json").read_text(encoding="utf-8"))
    key_bindings = {int(k): v for k, v in kb_raw.get("bindings", {}).items()}
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
        floor_ids=floor_ids, visited_floors={"MT1"},
        pending_floor_change=None, _floors_dir=FLOORS,
        _key_bindings=key_bindings,
    )


def load_tokens():
    route_path = next(Path(".").glob("51_*.h5route"), None)
    if route_path is None:
        route_path = next((Path(__file__).parent).glob("51_*.h5route"), None)
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def _fmt_vec(v):
    keys = " ".join(f"{k.split(':', 1)[1]}={v[k]}"
                    for k in sorted(v) if k.startswith("key:") and v[k])
    mp = " ".join(f"{k.split(':', 1)[1]}={v[k]}"
                  for k in sorted(v) if k.startswith("map:") and v[k])
    return (f"HP={v['hp']:>5} ATK={v['atk']:>3} DEF={v['def']:>3} "
            f"金={v['gold']:>5} kill={v['kill']:>3}"
            + (f"  钥匙[{keys}]" if keys else "")
            + (f"  地图剩[{mp}]" if mp else ""))


def _route_vec(route_exit, items_db):
    """把 cfg 里的 route 真值展开成完整 Pareto 向量（持有属性 + 持有钥匙 + 持有道具 + 地图剩余 HP 消耗品）。
    keys/items/map 为 cfg 可选项（塔特有真值）。**map 必须投影到与搜索前沿同口径**——只保留 HP
    消耗品(经 _gives_hp_on_pickup 数据驱动判定)；宝石/钥匙等非消耗品的地图剩余不计(它们拿到
    才兑现，留在地上不是 Pareto 优点，见 docs/solver-design.md 的建模粒度裁定)。否则 route_vec
    会比前沿多出「map:钥匙」这类无人能及的维度→route 虚假非支配(A 段历史误判正源于此)。

    持有维须与 _value_map 同口径：含 mdef(缺省 0)与 item:*(背包道具)。item:* 是否参与比较交给
    _project_for_compare 按 cls 数据驱动裁剪——本函数如实展开，不在此处过滤。"""
    rv = {"hp": route_exit["hp"], "atk": route_exit["atk"],
          "def": route_exit["def"], "mdef": route_exit.get("mdef", 0),
          "gold": route_exit["gold"], "kill": route_exit["kill"]}
    for k, val in route_exit.get("keys", {}).items():
        rv["key:" + k] = val
    for k, val in route_exit.get("items", {}).items():
        rv["item:" + k] = val
    for k, val in route_exit.get("map", {}).items():
        if _gives_hp_on_pickup(items_db.get(k)):
            rv["map:" + k] = val
    return rv


def _project_for_compare(vec, items_db):
    """把 Pareto 向量投影到「可比口径」后再做支配判定——只裁剪 item:* 维，其余维原样保留。

    item:* 维只保留【消耗品道具】(cls=='tools'，会随使用减少→余量是真价值维，如 centerFly/bomb/
    earthquake 剩几个，段间传前沿时关键)；【常驻能力道具】(cls=='constants' 及其它不消耗类，如
    fly/wand/book/I333)一律投影掉——它们段内既不获取也不消耗、两边永远相同，只会制造假胜负。

    B 段历史误判正源于此：某前沿点与 route 各属性全等，仅因前沿向量带 item:fly=1 而 route_vec
    缺该维(当 0)→虚假「严格支配」route。cls 按 items.json 数据驱动读(items_db)，绝不写死 id，塔无关。"""
    out = {}
    for k, v in vec.items():
        if k.startswith("item:"):
            iid = k.split(":", 1)[1]
            if (items_db.get(iid) or {}).get("cls") != "tools":
                continue  # 常驻/不消耗道具：两边恒等，投影掉
        out[k] = v
    return out


def _dominates(a, b):
    """a 在所有维 >= b（缺失维当 0）且至少一维严格 > b。"""
    allk = set(a) | set(b)
    ge = all(a.get(k, 0) >= b.get(k, 0) for k in allk)
    gt = any(a.get(k, 0) > b.get(k, 0) for k in allk)
    return ge and gt


def run_segment(cfg):
    """cfg: name / entry_token / goal_cell / baseline_hp / route_exit(dict hp,atk,def,gold,kill)。"""
    name = cfg["name"]
    entry_token = cfg["entry_token"]
    goal_cell = cfg["goal_cell"]
    baseline_hp = cfg["baseline_hp"]
    route_exit = cfg["route_exit"]
    search_kwargs = cfg.get("search_kwargs", {})

    print("=" * 72)
    print(f"{name}：搜索 → 引擎裁判 → 验收 + 出口 Pareto 前沿 + 性能")
    print("=" * 72)

    tokens = load_tokens()
    state = build_initial_state()
    for tok in tokens[:entry_token]:
        state = step(state, tok)
    entry = state
    h = entry.hero
    print(f"\n入口(tokens[:{entry_token}]): {entry.current_floor}({h.x},{h.y}) "
          f"HP={h.hp} ATK={h.atk} DEF={h.def_} 金={h.gold} "
          f"kill={h.kill_count} keys={dict(h.keys)}")
    print(f"目标格: {goal_cell}   基准 HP(route 出口): {baseline_hp}")

    # —— 搜索（profile + 计时）——
    # 单层段拷贝优化：搜索入口用一份副本并置 _single_floor_copy=True（只深拷当前层、其余层共享引用）。
    # 段搜索只发 U/D/L/R、切层子态被裁剪、切层路径从不就地改非当前层→共享安全。裁判(下方)仍用
    # 未置位的 entry 全量深拷独立重放：既保持最大独立性，又顺带校验本优化(单层段两种拷贝必须等价)。
    search_entry = _copy_state(entry)
    search_entry._single_floor_copy = True
    pr = cProfile.Profile()
    t0 = time.perf_counter()
    pr.enable()
    res = search_segment(search_entry, goal_cell, step, **search_kwargs)
    pr.disable()
    elapsed = time.perf_counter() - t0

    # —— 裁判：从干净入口独立重放，逐项核对 ——
    replayed = replay(entry, res.actions, step, _copy_state) if res.found else None
    diffs = diff_states(res.claimed_state, replayed) if res.found else []

    # —— 验收三条 ——
    print("\n" + "-" * 72 + "\n验收\n" + "-" * 72)
    a_ok = res.found
    print(f"  a. 找到合法路线到 {goal_cell}: {'是' if a_ok else '否'}"
          + (f"（{len(res.actions)} 步）" if a_ok else ""))
    b_ok = a_ok and not diffs
    print(f"  b. 引擎裁判一致(搜索宣称终态 == 独立重放终态): {'是' if b_ok else '否'}")
    for f, cv, rv in diffs:
        print(f"       不一致 {f}: 搜索={cv}  重放={rv}")
    replay_hp = replayed.hero.hp if replayed is not None else None
    c_ok = a_ok and replay_hp is not None and replay_hp >= baseline_hp
    print(f"  c. 终态 HP >= {baseline_hp}: {'是' if c_ok else '否'}"
          + (f"（搜索={res.final_hp} / 重放={replay_hp} / 基准={baseline_hp}）"
             if a_ok else ""))
    print(f"\n  >>> {'回路打通(三条全过)' if (a_ok and b_ok and c_ok) else '未通过'}")

    # —— 出口属性对比真值（HP 最大点）——
    if replayed is not None:
        print("\n出口属性对比(HP 最大点 vs route 真值):")
        rv = dict(hp=replayed.hero.hp, atk=replayed.hero.atk,
                  def_=replayed.hero.def_, gold=replayed.hero.gold,
                  kill=replayed.hero.kill_count)
        for field, rk in (("hp", "hp"), ("atk", "atk"), ("def_", "def"),
                          ("gold", "gold"), ("kill", "kill")):
            d = rv[field] - route_exit[rk]
            mark = "" if d == 0 else f"  (d{d:+d})"
            print(f"    {field:>5}: 搜索={rv[field]:>5}  route={route_exit[rk]:>5}{mark}")

    # —— 出口 Pareto 前沿（不只 HP 最大点）——
    fr = res.goal_frontier or []
    print(f"\n出口 Pareto 前沿（{len(fr)} 个非支配点 / goal_hits={res.goal_hits}）:")
    for v in sorted(fr, key=lambda v: (-v["hp"], -v["atk"], -v["def"])):
        print(f"    {_fmt_vec(v)}")

    # —— 严格更优查询（完整向量：HP/ATK/DEF + 持有钥匙 + 地图剩余资源）——
    # 修正历史误判：旧查询只比 ATK/DEF/HP，漏了钥匙(硬通货)与地图剩余资源(战略储备)，
    # 会把「吃掉储备血瓶 + 少持钥匙」的高 HP 出口误判为严格更优。见 docs/solver-design.md。
    items_db = entry.floors[entry.current_floor]._items_db
    route_vec = _route_vec(route_exit, items_db)
    has_keys = any(k.startswith("key:") for k in route_vec)
    has_map = any(k.startswith("map:") for k in route_vec)
    print(f"\nPareto 严格更优查询（完整向量支配 route 出口"
          f"{'；含钥匙' if has_keys else '；⚠cfg未给route钥匙真值'}"
          f"{'；含地图剩余资源' if has_map else '；⚠cfg未给route地图剩余真值'}）:")
    print(f"  route 完整向量: {_fmt_vec(route_vec)}")
    # 两边同口径投影后再判支配：常驻道具(cls!=tools)两边恒等、投影掉，避免假胜负(见 _project_for_compare)。
    route_cmp = _project_for_compare(route_vec, items_db)
    dom_idx = [i for i, v in enumerate(fr)
               if _dominates(_project_for_compare(v, items_db), route_cmp)]
    strictly_better = [fr[i] for i in dom_idx]
    if strictly_better:
        print(f"  [是] 找到 {len(strictly_better)} 个【完整向量】严格支配 route 的出口:")
        for v in strictly_better:
            print(f"      {_fmt_vec(v)}")
    else:
        print(f"  [否] 前沿中无任一点在完整向量上严格支配 route")
        print(f"       → route 出口是该段 Pareto 前沿上的非支配点（要 HP 更高，必须"
              f"放弃钥匙 / 提前清掉地图储备，不存在「白赚」的严格更优点）。")

    # —— 裁判独立重放严格支配点：确认引擎合法 + 完整动作序列 + 逐维对比表 ——
    # 严格支配 route 的出口不能只停留在「搜索宣称」——必须丢回引擎独立重放确认真走得通，再把完整
    # 动作序列 + 逐维对比表打出来供玩家在真实游戏核对。引擎只当裁判：重放终态须与搜索宣称逐项吻合。
    acts = res.goal_frontier_actions or []
    if dom_idx and acts:
        gf, gx, gy = goal_cell
        print("\n" + "=" * 72)
        print("[严格支配 route 的出口] 裁判独立重放确认 + 动作序列（请玩家丢回真实游戏核对）：")
        print("=" * 72)
        for rank, i in enumerate(sorted(dom_idx, key=lambda j: -fr[j]["hp"])):
            v = fr[i]
            actions = acts[i]
            rep = replay(entry, actions, step, _copy_state)
            ok = (rep.current_floor == gf and rep.hero.x == gx and rep.hero.y == gy
                  and rep.hero.hp == v["hp"] and rep.hero.atk == v["atk"]
                  and rep.hero.def_ == v["def"] and rep.hero.kill_count == v["kill"])
            repkeys = {k: vv for k, vv in rep.hero.keys.items() if vv}
            print(f"\n  支配点#{rank + 1}（{len(actions)} 步）: {_fmt_vec(v)}")
            print(f"    引擎裁判重放终态: @{rep.current_floor}({rep.hero.x},{rep.hero.y}) "
                  f"HP={rep.hero.hp} ATK={rep.hero.atk} DEF={rep.hero.def_} "
                  f"金={rep.hero.gold} kill={rep.hero.kill_count} keys={repkeys}  "
                  f"{'[OK] 与搜索宣称一致' if ok else '[X] 与搜索宣称不符!'}")
            print("    逐维 vs route(真值):")
            for nm, sv, rvv in (("HP", rep.hero.hp, route_exit["hp"]),
                                ("ATK", rep.hero.atk, route_exit["atk"]),
                                ("DEF", rep.hero.def_, route_exit["def"]),
                                ("金", rep.hero.gold, route_exit["gold"]),
                                ("kill", rep.hero.kill_count, route_exit["kill"])):
                d = sv - rvv
                mark = "" if d == 0 else f"  (d{d:+d})"
                print(f"        {nm:>4}: 重放={sv:>5}  route={rvv:>5}{mark}")
            seq = "".join(actions)
            print("    动作序列:")
            for j in range(0, len(seq), 60):
                print("      " + seq[j:j + 60])

    # —— 性能 ——
    print("\n" + "-" * 72 + "\n性能\n" + "-" * 72)
    print(f"  展开 expanded={res.states_expanded:,}  "
          f"生成 generated={res.states_generated:,} (≈搜索内 step 调用数)")
    print(f"  入队 admitted={res.states_admitted:,}  "
          f"去重指纹 fingerprints={res.distinct_fingerprints:,}")
    print(f"  队列峰值 frontier={res.frontier_peak:,}  "
          f"goal_hits={res.goal_hits:,}  hit_cap={res.hit_cap}")
    print(f"  搜索耗时 {elapsed*1000:.1f} ms")
    if res.states_generated:
        print(f"  每 step 均耗时(搜索内) {elapsed/res.states_generated*1e6:.1f} μs")
    print("\n  瓶颈分布(cProfile cumtime top 12):")
    sbuf = io.StringIO()
    pstats.Stats(pr, stream=sbuf).sort_stats("cumulative").print_stats(12)
    for line in sbuf.getvalue().splitlines():
        if line.strip():
            print("    " + line)

    # —— 超基准：完整动作序列供玩家核真实游戏 ——
    if res.found and replay_hp is not None and replay_hp > baseline_hp:
        print("\n" + "=" * 72)
        print(f"[更优路线] 搜索 HP={replay_hp} > 基准 {baseline_hp}（HP 最大点）。")
        print("  完整动作序列（请玩家丢回真实游戏核对是否真走得通）：")
        print("=" * 72)
        seq = "".join(res.actions)
        for i in range(0, len(seq), 60):
            print("    " + seq[i:i + 60])
        print(f"  共 {len(res.actions)} 步")

    return res
