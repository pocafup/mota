"""【§S25 命门坐实·只读诊断】navigate_to 会不会自己绕去拿开门钥？

玩家机制事实（§S25·全舍纯钥块的地基）：
  navigate_to 不是"去一个目标点"，是【用最小代价去某点、路上自己决定去哪拿钥匙/血瓶再去目标】
  → 开门必需的钥 navigate_to 自己绕去拿、不需 GA 放钥块。

本脚本【实测别靠记忆】坐实这条：从 MT3/0 钥起点，让 navigate_to 去【需开门才能到、开门钥不在
直接路径、手里初始无钥】的深目标，重放它返回的动作串，看它是否【自己绕去拿钥→开门→到达】
（reached=True + 重放显示拿了起步没有的钥 + 开了门）还是【卡在没钥的门前到不了】（reached=False）。

测的目标（都从封板涌现器取真 cell·不手写坐标）：
  · 盾（detect_big_items dd>0 大件·MT9 深目标）：★最关键——盾是【非钥匙的属性目标】，它在多道
    钥匙门后。若 navigate_to 从 0 钥起点能到盾，证明【就算基因里没有任何钥块，navigate_to 也会自己
    把开门钥抓来去拿属性目标】——这正是"全舍纯钥块"成立的充要证据。
  · 剑（detect_big_items da>0·MT5·浅）：对照（浅目标·门少）。
  · 红钥 MT8(10,2)（§S25 判断3 目标）：测它够不够得到 + 终态攻击（坐实"25+攻击门槛"）。

只读：不改任何产品码/fitness/navigate_to；navigate_to 用独立 dict 缓存（不碰持久桶）。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from probe_crossfloor import build_start            # noqa: E402
from vzone import build_zone                         # noqa: E402
from big_item_pull import detect_big_items           # noqa: E402
from key_targets import detect_key_targets           # noqa: E402
from ga_navigate import navigate_to                  # noqa: E402
from solver.beam import build_future_roster, _combat_damage   # noqa: E402
from solver.fitness import build_zone1_roster        # noqa: E402
from sim.simulator import step, DOOR_KEY_MAP, _KEY_ITEMS       # noqa: E402

DOOR_TILES = set(DOOR_KEY_MAP)   # 81/82/83/84/85/86


def _keys_total(state):
    return sum(v for v in state.hero.keys.values() if isinstance(v, (int, float)))


def _door_cells(state):
    """全塔当前【还闭着的门】cell→门 tile（跨已访问层扫 entities）。开门后 tile→0 自动剔。"""
    out = {}
    for fid, fl in state.floors.items():
        for y, row in enumerate(fl.entities):
            for x, t in enumerate(row):
                if t in DOOR_TILES:
                    out[(fid, x, y)] = t
    return out


def _tile_color(t):
    return DOOR_KEY_MAP.get(t, f"tile{t}")


def replay_and_trace(start, goal_cell, zone, label, max_pops):
    """跑 navigate_to(start→goal)，重放动作串，逐步追踪【拿钥/开门/杀怪/跨层】。只读。"""
    print("\n" + "=" * 78)
    print(f"【{label}】navigate_to → goal={goal_cell}")
    print("=" * 78)
    h0 = start.hero
    print(f"  起点: {start.current_floor}({h0.x},{h0.y})  HP={h0.hp} ATK={h0.atk} DEF={h0.def_} "
          f"keys={dict(h0.keys)}  (手里钥匙总数={_keys_total(start)})")

    cache = {}   # 独立内存缓存（不碰持久桶）
    t0 = time.time()
    final, moves, reached = navigate_to(start, goal_cell, zone, step, max_pops=max_pops, cache=cache)
    dt = time.time() - t0
    print(f"  navigate_to 返回: reached={reached}  moves={len(moves)}  耗时{dt:.1f}s")

    if not reached:
        print(f"  ❌ 够不到——卡住（原子失败、入口态原样返回）。")
        print(f"     → 若目标在门后且起步无钥：说明 navigate_to 【没能】自己绕拿开门钥（命门有例外）。")
        return dict(label=label, reached=False, final=None, moves=moves)

    # 重放 moves，逐步追踪
    s = start
    keys_grabbed = []      # (step_i, color)  —— 拿到一把钥
    doors_opened = []      # (step_i, fid,x,y, color)  —— 一扇门由闭变开
    guards_killed = 0
    floor_seq = [s.current_floor]
    prev_keys = dict(s.hero.keys)
    prev_doors = _door_cells(s)
    prev_kill = s.hero.kill_count
    max_keys_held = _keys_total(s)

    for i, mv in enumerate(moves):
        s = step(s, mv)
        # 跨层
        if s.current_floor != floor_seq[-1]:
            floor_seq.append(s.current_floor)
        # 拿钥（某色 +1）
        cur_keys = dict(s.hero.keys)
        for color, cnt in cur_keys.items():
            if cnt > prev_keys.get(color, 0):
                keys_grabbed.append((i, color))
        # 开门（门 cell 由有变无）
        cur_doors = _door_cells(s)
        for cell, t in prev_doors.items():
            if cell not in cur_doors:
                doors_opened.append((i, cell, _tile_color(t)))
        # 杀怪
        if s.hero.kill_count > prev_kill:
            guards_killed += s.hero.kill_count - prev_kill
        prev_keys, prev_doors, prev_kill = cur_keys, cur_doors, s.hero.kill_count
        max_keys_held = max(max_keys_held, _keys_total(s))

    fh = s.hero
    print(f"  ✅ 到达: {s.current_floor}({fh.x},{fh.y})  HP={fh.hp} ATK={fh.atk} DEF={fh.def_} "
          f"keys={dict(fh.keys)}")
    print(f"     跨层序: {' → '.join(floor_seq)}")
    print(f"     ★起步手里钥匙=0 → 沿途【拿钥 {len(keys_grabbed)} 把】: "
          f"{[(i, c) for i, c in keys_grabbed]}")
    print(f"     ★沿途【开门 {len(doors_opened)} 扇】:")
    for i, cell, color in doors_opened:
        print(f"         step#{i:4d}  门 {cell}  [{color}]")
    print(f"     沿途杀怪 {guards_killed} 只；终态手里余钥匙={_keys_total(s)}")

    # 命门判定
    grabbed_then_opened = len(keys_grabbed) > 0 and any(
        c in {"yellowKey", "blueKey", "redKey", "greenKey", "steelKey"}
        for _, c in doors_opened
    )
    if grabbed_then_opened:
        print(f"  ▶▶ 命门成立：起步 0 钥 → navigate_to 自己绕去【拿了 {len(keys_grabbed)} 把钥】并"
              f"【开了门】到达目标 → 纯钥块可全舍（钥匙交 navigate_to 自理）。")
    elif len(doors_opened) > 0:
        print(f"  ▶▶ 部分成立：开了 {len(doors_opened)} 扇门但其中含非钥匙门（事件/特殊门）；"
              f"keyed 门开了 {sum(1 for _,_,c in doors_opened if c in _KEY_ITEMS)} 扇。")
    else:
        print(f"  ▶▶ 本目标路上没开任何门（目标本就在无门连通块内·非门后目标·换更深目标再验）。")
    return dict(label=label, reached=True, final=s, moves=moves,
                keys_grabbed=keys_grabbed, doors_opened=doors_opened)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("组装（build_start 噩梦后 MT3 入口 + build_zone + 涌现器）…")
    t0 = time.time()
    start, nopen = build_start()
    zone = build_zone()
    roster_big = build_future_roster(start)
    big_cells, tau, ranked = detect_big_items(zone, roster_big, start)
    _roster, zone_fids, _all = build_zone1_roster(start)
    cands, info_key = detect_key_targets(start, zone_fids)
    print(f"  就绪 {time.time() - t0:.1f}s  起点 keys={dict(start.hero.keys)}")

    # 从涌现器取真 cell（不手写坐标）
    sword_c = next(c for (_d, c, da, _dd) in ranked if c in big_cells and da > 0)
    shield_c = next(c for (_d, c, _da, dd) in ranked if c in big_cells and dd > 0)
    print(f"  剑 cell={sword_c}  盾 cell={shield_c}  big_cells={sorted(big_cells)}")

    # 红钥 cell：从全集里挑 redKey 色
    colors = info_key["colors"]
    red_cells = sorted(c for c, col in colors.items() if col == "redKey")
    print(f"  红钥 cell(detect 全集 redKey 色)={red_cells}  afford 闭包={sorted(info_key['afford'])}")
    print(f"  红钥在候选②? {[c in cands for c in red_cells]}  "
          f"在顺路①? {[c in info_key['cheap'] for c in red_cells]}  "
          f"在够不到③? {[c in info_key['unreachable'] for c in red_cells]}")

    # ── 测 1：剑（浅·对照）──
    replay_and_trace(start, sword_c, zone, "剑 MT5（浅·门少·对照）", max_pops=8000)

    # ── 测 2：盾（深·★最关键：非钥属性目标在多道钥匙门后）──
    replay_and_trace(start, shield_c, zone, "盾 MT9（深·非钥属性目标·命门正主）", max_pops=8000)

    # ── 测 3：红钥（§S25 判断3 目标）──
    for rc in red_cells:
        replay_and_trace(start, rc, zone, f"红钥 {rc}（§S25 判断3·测够不够得到+终态攻击）",
                         max_pops=30000)

    print("\n" + "=" * 78)
    print("命门坐实小结：见上每个目标的【▶▶】判定行。盾（非钥属性目标）从 0 钥起点能否到达，"
          "决定'全舍纯钥块'对不对。")
    print("=" * 78)


if __name__ == "__main__":
    main()
