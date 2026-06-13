"""抽出 beam(K=50, 前9段) 的获胜路径（最优 HP=754 点），供玩家真实游戏终审。

全部从引擎重放算出，不在对话里推演：
  · 起点 / 终点节点（层+坐标+全属性+钥匙/道具）；
  · 引擎独立重放裁判（replay→diff_states 必须零差异）；
  · 逐层逐事件轨迹（进/出坐标、HP 变化、杀怪、拾取、开门、用道具）——引擎算；
  · 完整 token 序列（可回放）。
落盘 extract/winning_path_K50_n9.txt + .json。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state
from sim.simulator import step, _copy_state
from solver.verify import replay, diff_states
from solver.beam import equiv_hp_over_roster, score_points
from solver.frontier import value_vector
from phase1 import run_phase1

OUT = Path(__file__).parent / "extract"


def _snap(s):
    h = s.hero
    return {"floor": s.current_floor, "x": h.x, "y": h.y, "hp": h.hp, "atk": h.atk,
            "def": h.def_, "mdef": h.mdef, "gold": h.gold, "kill": h.kill_count,
            "keys": {k: v for k, v in h.keys.items() if v},
            "items": {k: v for k, v in h.items.items() if v}}


def _fmt_node(n):
    extra = ""
    if n["keys"]:
        extra += "  钥匙[" + " ".join(f"{k}={v}" for k, v in sorted(n["keys"].items())) + "]"
    if n["items"]:
        extra += "  道具[" + " ".join(f"{k}={v}" for k, v in sorted(n["items"].items())) + "]"
    return (f"{n['floor']} @({n['x']},{n['y']})  HP={n['hp']} ATK={n['atk']} "
            f"DEF={n['def']} MDEF={n['mdef']} 金={n['gold']} kill={n['kill']}" + extra)


def _events(before, after, tok):
    """两态差异 → 人话事件列表（引擎算出的真实变化）。"""
    ev = []
    if before["floor"] != after["floor"]:
        ev.append(f"换层 {before['floor']}→{after['floor']}")
    dhp = after["hp"] - before["hp"]
    if dhp < 0:
        tag = "杀怪" if after["kill"] > before["kill"] else "地形/受击"
        ev.append(f"HP {before['hp']}→{after['hp']} ({dhp}) [{tag}]")
    elif dhp > 0:
        ev.append(f"HP {before['hp']}→{after['hp']} (+{dhp}) [回血]")
    if after["atk"] != before["atk"]:
        ev.append(f"ATK {before['atk']}→{after['atk']} [宝石/装备]")
    if after["def"] != before["def"]:
        ev.append(f"DEF {before['def']}→{after['def']} [宝石/装备]")
    for k in set(before["keys"]) | set(after["keys"]):
        b, a = before["keys"].get(k, 0), after["keys"].get(k, 0)
        if a != b:
            ev.append(f"钥匙 {k} {b}→{a} ({'+' if a > b else ''}{a - b})")
    for k in set(before["items"]) | set(after["items"]):
        b, a = before["items"].get(k, 0), after["items"].get(k, 0)
        if a != b:
            ev.append(f"道具 {k} {b}→{a} ({'+' if a > b else ''}{a - b})")
    if tok.startswith("CHOICE") or tok.startswith("ITEM") or tok.startswith("KEY") \
            or tok in ("help",):
        ev.append(f"事件token={tok}")
    return ev


def main(num_segments=9, beam_k=50):
    print(f"重跑 beam K={beam_k} 前 {num_segments} 段以取获胜路径……")
    _, frontier = run_phase1(num_segments=num_segments, beam_k=beam_k)
    # 选最优点：按【双值 V（Δ形式 = HP − Σ固定参照怪集损血，对杀怪中性）】选段内最优点，
    # 依次 HP、钥匙总数 破平（确定性）。R/BIG 由末段前沿现算（旋钮①=段末前沿存活并集）。
    # 这是段内 V 最优，非通关赢家（攻防回报后段才兑现）。
    roster, big, scores = score_points(frontier)
    best = max(frontier, key=lambda p: (scores[id(p.state)],
                                        value_vector(p.state)["hp"],
                                        sum(v for k, v in p.state.hero.keys.items())))
    actions = list(best.actions)

    init = build_initial_state()
    start = _snap(init)
    # 引擎独立重放裁判
    rep = replay(init, actions, step, _copy_state)
    diffs = diff_states(best.state, rep)
    end = _snap(rep)

    # 逐 token 轨迹（快照原始值，免受 step 是否原地修改影响）
    s = build_initial_state()
    cur = _snap(s)
    lines, floor_runs = [], []
    run = {"floor": cur["floor"], "enter": (cur["x"], cur["y"]), "hp_in": cur["hp"],
           "atk_in": cur["atk"], "def_in": cur["def"], "kills": 0, "evts": []}
    for idx, tok in enumerate(actions):
        before = _snap(s)
        s = step(s, tok)
        after = _snap(s)
        evs = _events(before, after, tok)
        if before["floor"] != after["floor"]:
            run["exit"] = (before["x"], before["y"])
            run["hp_out"] = before["hp"]
            run["atk_out"], run["def_out"] = before["atk"], before["def"]
            floor_runs.append(run)
            run = {"floor": after["floor"], "enter": (after["x"], after["y"]),
                   "hp_in": after["hp"], "atk_in": after["atk"], "def_in": after["def"],
                   "kills": 0, "evts": []}
        if after["kill"] > before["kill"]:
            run["kills"] += after["kill"] - before["kill"]
        for e in evs:
            if not e.startswith("换层"):
                run["evts"].append(f"  ({after['x']},{after['y']}) {e}")
        if evs:
            lines.append(f"[{idx:>3}] {tok:<10} @({after['x']},{after['y']}) " + " ; ".join(evs))
    run["exit"] = (cur := _snap(s))["x"], cur["y"]
    run["hp_out"] = cur["hp"]
    run["atk_out"], run["def_out"] = cur["atk"], cur["def"]
    floor_runs.append(run)

    # —— 文本报告 ——
    out = []
    out.append("=" * 88)
    out.append(f"beam K={beam_k} 前 {num_segments} 段【段内双值V最优点】(非通关赢家;攻防回报后段才兑现)"
               f" — 玩家真实游戏终审")
    _v = equiv_hp_over_roster(rep, roster, big)
    out.append(f"双值：HP={end['hp']}  Σ参照怪集损血={end['hp'] - _v}  V=HP−Σ={_v}（Δ形式·对杀怪中性）")
    out.append("=" * 88)
    out.append(f"起点：{_fmt_node(start)}")
    out.append(f"终点：{_fmt_node(end)}")
    out.append(f"总 token 数：{len(actions)}")
    out.append(f"引擎独立重放裁判：{'✅ 零差异（搜索宣称终态 == 引擎重放终态）' if not diffs else '❌ 不一致 ' + str(diffs)}")
    out.append("")
    out.append("── 逐层小结（每次停留一层为一段；坐标=列,行）" + "─" * 40)
    out.append(f"{'#':>2} {'层':>5} {'进入':>9} {'离开':>9} {'HP进':>6} {'HP出':>6} "
               f"{'ATK进':>6} {'ATK出':>6} {'DEF进':>6} {'DEF出':>6} {'杀怪':>5}")
    for i, r in enumerate(floor_runs):
        out.append(f"{i:>2} {r['floor']:>5} {str(r['enter']):>9} {str(r['exit']):>9} "
                   f"{r['hp_in']:>6} {r['hp_out']:>6} "
                   f"{r.get('atk_in',0):>6} {r.get('atk_out',0):>6} "
                   f"{r.get('def_in',0):>6} {r.get('def_out',0):>6} {r['kills']:>5}")
    out.append("")
    out.append("── 逐事件明细（HP变化/杀怪/拾取/宝石/换层/事件token）" + "─" * 30)
    out.extend(lines)
    out.append("")
    out.append("── 完整 token 序列（可回放）" + "─" * 50)
    out.append(" ".join(actions))
    report = "\n".join(out)
    print("\n" + report)

    OUT.mkdir(exist_ok=True)
    (OUT / "winning_path_K50_n9.txt").write_text(report, encoding="utf-8")
    (OUT / "winning_path_K50_n9.json").write_text(json.dumps(
        {"start": start, "end": end, "diffs": diffs, "n_tokens": len(actions),
         "actions": actions, "floor_runs": floor_runs}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\n[落盘] extract/winning_path_K50_n9.txt + .json")


if __name__ == "__main__":
    main()
