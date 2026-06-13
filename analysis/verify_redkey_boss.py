"""红钥过 boss 组合验证（Stage-2，遵铁律：重放真引擎、不靠观察/推断）。

对每个 floorbest jsonl：把每条 Pareto 态 actions 丢回 step() 独立重放到终态，验 door_pull+β_big
组合能否引导玩家真实打法「爬到 boss 区→拿盾→凑属性→属性齐了打守门怪拿红钥→开 boss 门→真杀队长」：
  #1 真过 boss：有无态置位 BOSS_FLAG「10f战胜骷髅队长」且 HP>0（区分『到 MT10 门口』vs『真杀队长』；
     注意 state.won 是通关 MT50、非一区 boss，故用 flag 判一区过关）。
  #2 红钥时机：对最好/最深态步进重放，找红钥 acquire/use 时刻 + 当时 HP/ATK/DEF + 当时是否已够过 boss
     （HP≥boss_toll(atk,def)），判『属性齐才拿』vs『过早白拿』（命门：door_pull 软梯度会不会过早拿红钥）。
  #3 钥匙经济：终态红钥持有/红门开启/钥匙总留存（囤不囤）。
  #4 崩爬：最深到达层 + 该处 HP（有没有低层 farm 门袋不爬）。

用法：python verify_redkey_boss.py <floorbest1.jsonl> [floorbest2.jsonl ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, DOOR_KEY_MAP
from solver.verify import replay
from solver.beam import build_future_roster
from probe_crossfloor import build_start, _fidx
from vzone import build_zone, boss_toll, BOSS_FLAG, BOSS_FLOOR
from big_item_pull import detect_big_items
from door_value import build_door_reward

OUT = Path(__file__).parent


def _door_open(state, cell):
    """门 cell 在该终态是否已开（该层已加载且 tile 不再是门）。"""
    fid, x, y = cell
    fl = state.floors.get(fid)
    if fl is None:
        return False
    return DOOR_KEY_MAP.get(fl.terrain[y][x]) is None


def _nkeys(keys):
    return sum(v for v in keys.values() if v)


def trace_redkey(start, actions, zone, boss_color):
    """步进重放，找红钥 acquire/use 时刻 + 当时属性 + 当时是否已够过 boss(HP≥boss_toll)。"""
    s = _copy_state(start)
    prev = 0
    events = []
    for i, a in enumerate(actions):
        s = step(s, a)
        cur = s.hero.keys.get(boss_color, 0)
        if cur != prev:
            h = s.hero
            bt = boss_toll(zone, h.atk, h.def_, h.mdef)
            events.append({"act": "拿" if cur > prev else "用", "step": i,
                           "hp": h.hp, "atk": h.atk, "def": h.def_,
                           "boss_toll": bt, "够过boss": h.hp >= bt and bt > 0})
            prev = cur
    return events


def analyze_file(path, start, zone, boss_door, boss_color):
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    reached = {}
    n_pass = 0
    best_pass = None      # dict: hp/atk/def/steps/actions/keys
    best_mt10 = None      # 最深 MT10 未过态（hp 最高）
    deepest = None        # (fid, hp, atk, def, steps)
    red_picked = red_held_end = door_opened_cnt = 0

    for r in rows:
        final = replay(start, r["actions"], step, _copy_state)
        fid = final.current_floor
        reached[fid] = reached.get(fid, 0) + 1
        h = final.hero
        passed = bool(h.flags.get(BOSS_FLAG)) and h.hp > 0
        opened = _door_open(final, boss_door)
        held_red = h.keys.get(boss_color, 0)
        if opened:
            door_opened_cnt += 1
        if held_red > 0:
            red_held_end += 1
        if held_red > 0 or opened:
            red_picked += 1

        rec = {"hp": h.hp, "atk": h.atk, "def": h.def_, "steps": r["n_steps"],
               "actions": r["actions"], "keys": dict(h.keys), "opened": opened,
               "held_red": held_red, "floor": fid}
        if passed:
            n_pass += 1
            if best_pass is None or h.hp > best_pass["hp"]:
                best_pass = rec
        if fid == BOSS_FLOOR and not passed:
            if best_mt10 is None or h.hp > best_mt10["hp"]:
                best_mt10 = rec
        fi = _fidx(fid)
        if deepest is None or fi > _fidx(deepest[0]) or (fi == _fidx(deepest[0]) and h.hp > deepest[1]):
            deepest = (fid, h.hp, h.atk, h.def_, r["n_steps"])

    return {"rows": rows, "reached": reached, "n_pass": n_pass, "best_pass": best_pass,
            "best_mt10": best_mt10, "deepest": deepest, "red_picked": red_picked,
            "red_held_end": red_held_end, "door_opened_cnt": door_opened_cnt}


def main():
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        print("用法：python verify_redkey_boss.py <floorbest1.jsonl> [...]")
        return
    start, _ = build_start()
    roster = build_future_roster(start)
    zone = build_zone()
    big_cells, _tau, ranked = detect_big_items(zone, roster, start)
    reward = build_door_reward(zone, roster, start, big_cells, ranked, include_win=True)
    boss_doors = [(d, info) for d, info in reward.items() if info.get("win")]
    if not boss_doors:
        print("⚠ 奖励表里没有 win>0 的 boss 门（include_win 没生效？）")
        return
    boss_door, bd_info = max(boss_doors, key=lambda t: t[1]["win"])
    boss_color = bd_info["color"]
    print("=" * 100)
    print(f"boss 门 = {boss_door[0]}({boss_door[1]},{boss_door[2]})  色={boss_color}  "
          f"R/win={bd_info['win']:,.0f}  （过此门=进队长竖井；BOSS_FLAG={BOSS_FLAG!r}）")
    print(f"参照态 boss_toll(atk26,def25)={boss_toll(zone, 26, 25, 0):,.0f}（HP 须 ≥ 此值才扛得过队长）")
    print("=" * 100)

    for f in files:
        if not f.exists():
            print(f"\n⚠ 缺文件：{f}")
            continue
        tag = f.name.replace("crossbeam_floorbest_", "").replace("_lam0.2_stairs.jsonl", "")
        a = analyze_file(f, start, zone, boss_door, boss_color)
        print(f"\n── {tag}  （{len(a['rows'])} 条 Pareto 态，到达层="
              f"{sorted(a['reached'], key=_fidx)}）")

        # #1 真过 boss
        if a["n_pass"] > 0:
            bp = a["best_pass"]
            print(f"   #1 真过boss：★★★ {a['n_pass']} 个态杀队长(flag+HP>0)  最好：终floor={bp['floor']} "
                  f"HP={bp['hp']} ATK={bp['atk']} DEF={bp['def']} ({bp['steps']}步)  钥匙={bp['keys']}")
        else:
            bm = a["best_mt10"]
            if bm:
                print(f"   #1 真过boss：✖ 无态杀队长。最深到 MT10 未过态：HP={bm['hp']} ATK={bm['atk']} "
                      f"DEF={bm['def']} ({bm['steps']}步) 开红门={bm['opened']} 持红钥={bm['held_red']}")
            else:
                print(f"   #1 真过boss：✖ 无态杀队长，且无态到 MT10（爬升没到 boss 层）")

        # #2 红钥时机（对最好过 boss 态、否则最深 MT10 态步进）
        trace_src = a["best_pass"] or a["best_mt10"]
        if trace_src:
            ev = trace_redkey(start, trace_src["actions"], zone, boss_color)
            if ev:
                desc = "  ".join(f"[{e['act']}红钥@{e['step']}步 HP{e['hp']}/{e['atk']}/{e['def']} "
                                 f"boss_toll={e['boss_toll']:,} {'够过' if e['够过boss'] else '✖不够'}]"
                                 for e in ev)
                print(f"   #2 红钥时机：{desc}")
                acq = next((e for e in ev if e["act"] == "拿"), None)
                if acq:
                    print(f"        → 拿红钥时{'已' if acq['够过boss'] else '尚未'}够过 boss"
                          f"（{'属性齐才拿=对' if acq['够过boss'] else '过早拿=白拿风险'}）")
            else:
                print(f"   #2 红钥时机：该态全程未碰红钥（{boss_color}）")
        else:
            print(f"   #2 红钥时机：无 MT10 态可查")

        # #3 钥匙经济
        print(f"   #3 钥匙经济：触及红钥态={a['red_picked']}  终态持红钥={a['red_held_end']}  "
              f"开红门态={a['door_opened_cnt']}")

        # #4 崩爬
        d = a["deepest"]
        print(f"   #4 崩爬：最深到达={d[0]} HP={d[1]} ATK={d[2]} DEF={d[3]} ({d[4]}步)")

    print("\n" + "=" * 100)


if __name__ == "__main__":
    main()
