"""门开启·吸收 实测分析（钥匙价值阶段1 验收，遵铁律：重放真引擎、不靠观察/推断）。

对每个 crossbeam_floorbest_*.jsonl：把每条 Pareto 态的 actions 丢回 step() 独立重放到终态，
检查【门后奖励表 R(门)】里每扇门在该终态是否【已开】(terrain 不再是门 tile) + 其 pocket 是否【已吸】
(宝石/血 entities==0)。跨该 run 全部 Pareto 态取并集 → 报告"这套打分下，搜索的存活前沿里到底开过哪些门、
吸过哪些 pocket"。多 run 并排（基线 γ=0 vs γ>0）→ 看 door_pull 有没有让更多【有价值的门】被开。

用法：python analyze_door_open.py <floorbest1.jsonl> [floorbest2.jsonl ...]
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
from vzone import build_zone
from big_item_pull import detect_big_items
from door_value import build_door_reward
from probe_crossfloor import build_start, _fidx

OUT = Path(__file__).parent


def _door_open(state, dcell):
    """该终态里门 dcell 是否已开：门所在层已加载 且 该 tile 不再是门(DOOR_KEY_MAP 不认)。
    未加载层=没去过=没开。"""
    fid, x, y = dcell
    fl = state.floors.get(fid)
    if fl is None:
        return None                       # 该层未访问 → 无从谈开/未开
    return DOOR_KEY_MAP.get(fl.terrain[y][x]) is None


def _pocket_absorbed(state, info):
    """该门 pocket 的【宝石+血】是否全部吸走(entities==0)；任一未加载层的格算未吸。"""
    cells = [c for c, _ in info["gems"]] + [c for c, _ in info["blood"]]
    if not cells:
        return None
    for (fid, x, y) in cells:
        fl = state.floors.get(fid)
        if fl is None or fl.entities[y][x] != 0:
            return False
    return True


def analyze(path, reward, start):
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    opened = set()            # 该 run 任一 Pareto 态里【开过】的门
    absorbed = set()          # pocket 被【吸过】的门
    reached = set()
    for r in rows:
        final = replay(start, r["actions"], step, _copy_state)
        reached.add(final.current_floor)
        for dcell, info in reward.items():
            if _door_open(final, dcell):
                opened.add(dcell)
            if _pocket_absorbed(final, info):
                absorbed.add(dcell)
    return rows, opened, absorbed, reached


def main():
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        files = sorted(OUT.glob("crossbeam_floorbest_K*_lam0.0_none.jsonl"))
    start, _ = build_start()
    roster = build_future_roster(start)
    zone = build_zone()
    big_cells, _tau, ranked = detect_big_items(zone, roster, start)
    reward = build_door_reward(zone, roster, start, big_cells, ranked, include_win=False)

    # idea3 的 6 扇被 Pareto 淘汰门（纯 key 轴）——是否在奖励表(有 pocket)、是否被开
    idea3 = [("MT8", 3, 1), ("MT8", 4, 1), ("MT9", 9, 4),
             ("MT7", 3, 5), ("MT8", 1, 9), ("MT8", 10, 7)]

    print("=" * 100)
    print(f"门后奖励表：{len(reward)} 扇有 pocket 价值的门。idea3 的 6 扇『纯 key 轴 Pareto 淘汰』门核对：")
    for d in idea3:
        info = reward.get(d)
        if info:
            print(f"    {d[0]}({d[1]},{d[2]})  ✅在奖励表  R={info['R']:,.0f}  "
                  f"pocket={len(info['pocket'])} 宝石{len(info['gems'])} 血{len(info['blood'])}")
        else:
            print(f"    {d[0]}({d[1]},{d[2]})  ✖ 不在奖励表（pocket 空=可绕过/无门后价值→开它纯亏钥匙，算法本就不该引导）")
    print("=" * 100)

    results = {}
    for f in files:
        if not f.exists():
            print(f"⚠ 缺文件：{f}")
            continue
        rows, opened, absorbed, reached = analyze(f, reward, start)
        results[f.name] = (opened, absorbed, reached)
        tag = f.name.replace("crossbeam_floorbest_", "").replace("_lam0.0_none.jsonl", "")
        print(f"\n── {tag}  （{len(rows)} 条 Pareto 态，到达层={sorted(reached, key=_fidx)}）")
        print(f"   开过的门({len(opened)})：" +
              ("、".join(f"{d[0]}({d[1]},{d[2]})" for d in sorted(opened, key=lambda d: (_fidx(d[0]), d)))
               or "无"))
        print(f"   吸过 pocket 的门({len(absorbed)})：" +
              ("、".join(f"{d[0]}({d[1]},{d[2]})R{reward[d]['R']:,.0f}"
                        for d in sorted(absorbed, key=lambda d: -reward[d]['R']))
               or "无"))
        # 只算【够得到的】门（pocket 价值格所在层被到达过）里开了几扇
        reachable_doors = {d for d, info in reward.items()
                           if all(c[0] in reached for c, _ in info["gems"] + info["blood"])}
        print(f"   够得到的有价值门 {len(reachable_doors)} 扇中，开了 {len(opened & reachable_doors)} 扇、"
              f"吸了 {len(absorbed & reachable_doors)} 扇 pocket")

    # 并排对比：每扇门 在各 run 是否被吸（pocket 真兑现）
    if len(results) > 1:
        print("\n" + "=" * 100)
        print("并排：各 run【吸过 pocket】的门对比（✓=该 run 在某存活态里把该门后价值吸到手）")
        names = list(results)
        alld = set()
        for _, ab, _ in results.values():
            alld |= ab
        hdr = "  ".join(n.replace("crossbeam_floorbest_K50", "").replace("_lam0.0_none.jsonl", "") or "base"
                        for n in names)
        print(f"{'门':>14} {'R':>10}   {hdr}")
        for d in sorted(alld, key=lambda d: -reward[d]['R']):
            marks = "  ".join(" ✓ " if d in results[n][1] else " · " for n in names)
            print(f"{d[0]+str((d[1],d[2])):>14} {reward[d]['R']:>10,.0f}   {marks}")
    print("=" * 100)


if __name__ == "__main__":
    main()
