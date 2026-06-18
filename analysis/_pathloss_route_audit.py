"""【临时只读核查·非封板】审计 k400 path-loss halfway 路线。
目的：
  ① 三重核验导出的 h5route：解码往返 / 确定性复现 / 独立重放终态=锚点。
  ② 逐 token 追踪 蓝/黄/红钥 的消耗(开门)-获取事件，dump 蓝钥去向——
     验证玩家猜测：beam 是否在 MT9 用稀缺蓝钥开蓝门(该门本可两黄从旁替代)
     → 浪费蓝钥 → MT8 一攻一防(蓝门)开不了 → 卡 ATK25(=钥匙稀缺·非"属性天花板")。
只读 decode/encode/step/build_initial_state，绝不改产品码。跑完即弃（数据放 h5route 旁给玩家网站回放参考·以回放为准）。
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from analysis.extract_zone1_milestones import build_initial_state
from analysis.dir2_redkey_pathloss_beam import fmt
from sim.simulator import step
from extract.decode_route import parse_rle_route, decompress
from extract.encode_route import make_h5route

H5 = ROOT / "dir2_redkey_pathloss_halfway_bk400.h5route"
ANCHOR = ("MT9", 9, 9, 25, 25, 584)   # 锚点态 floor,x,y,ATK,DEF,HP（k400 on_admit 输出）
TOK_SHIELD = 454                      # 前缀(开局→铁盾)末 token idx；i<=454=前缀, i>=455=beam 段
COLORS = ["yellowKey", "blueKey", "redKey"]


def decode_file(path):
    raw = path.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    route_raw = decompress(outer["route"])
    actions = parse_rle_route(route_raw)
    return actions, outer, route_raw


def replay(acts):
    s = build_initial_state()
    for t in acts:
        s = step(s, t)
        if s.dead:
            break
    return s


def sig(s):
    h = s.hero
    return (s.current_floor, h.x, h.y, h.hp, h.atk, h.def_,
            tuple(sorted(h.keys.items())), s.dead)


def main():
    print("=" * 78)
    print("k400 path-loss halfway 路线审计 — 三重核验 + 蓝钥去向追踪")
    print("=" * 78)
    if not H5.exists():
        sys.exit(f"✗ 找不到 {H5}")
    actions, outer, route_raw = decode_file(H5)
    meta = {k: v for k, v in outer.items() if k != "route"}
    print(f"\n[解码] {H5.name}: {len(actions)} 动作  meta={meta}")

    # ── 三重核验 ───────────────────────────────────────────────
    # ① 解码往返：actions → make_h5route → decode 回来，route 串 + 动作逐项一致
    re_text = make_h5route(actions, meta)
    re_outer = json.loads(decompress(re_text))
    re_route_raw = decompress(re_outer["route"])
    re_actions = parse_rle_route(re_route_raw)
    rt_ok = (re_route_raw == route_raw and re_actions == actions)

    # ② 确定性复现：同一动作串重放两次，终态逐字段一致
    s1, s2 = replay(actions), replay(actions)
    det_ok = (sig(s1) == sig(s2))

    # ③ 独立重放终态 = 锚点
    h = s1.hero
    anchor_ok = (s1.current_floor == ANCHOR[0] and h.x == ANCHOR[1] and h.y == ANCHOR[2]
                 and h.atk == ANCHOR[3] and h.def_ == ANCHOR[4] and h.hp == ANCHOR[5]
                 and not s1.dead)
    print("\n── 三重核验 ──")
    print(f"  ① 解码往返(route 串+动作逐项一致): {'OK ✅' if rt_ok else 'FAIL ❌'}")
    print(f"  ② 确定性复现(重放两次终态一致):   {'OK ✅' if det_ok else 'FAIL ❌'}")
    print(f"  ③ 独立重放终态=锚点{ANCHOR}: {'OK ✅' if anchor_ok else 'FAIL ❌'}")
    print(f"     实际终态: {fmt(s1)}")
    all_ok = rt_ok and det_ok and anchor_ok
    print(f"  => 三重核验: {'全过 ✅ 路线可信、可交玩家网站回放' if all_ok else '有失败 ❌ 须排查、别给坏文件'}")

    # ── 钥匙 消耗(开门)-获取 事件逐 token 追踪 ──────────────────
    print("\n" + "=" * 78)
    print("钥匙 消耗(开门)-获取 事件逐 token 追踪")
    print("=" * 78)
    s = build_initial_state()
    start_keys = {k: v for k, v in s.hero.keys.items()}
    print(f"开局钥匙: {start_keys}")
    prev = dict(s.hero.keys)
    events = []
    for i, t in enumerate(actions):
        s = step(s, t)
        if s.dead:
            break
        cur = s.hero.keys
        for c in COLORS:
            d = cur.get(c, 0) - prev.get(c, 0)
            if d != 0:
                seg = "前缀" if i <= TOK_SHIELD else "beam"
                events.append((i, seg, t, s.current_floor, s.hero.x, s.hero.y, c, d, cur.get(c, 0)))
        prev = dict(cur)

    for (i, seg, t, fl, x, y, c, d, rem) in events:
        kind = "开门消耗" if d < 0 else "获取    "
        print(f"  tok#{i:>4}[{seg}] {kind} {c:>9} {d:+d}→剩{rem}  @ {fl}({x},{y}) act={t}")

    # ── 蓝钥小结(玩家猜测核心) ─────────────────────────────────
    print("\n" + "=" * 78)
    print("★ 蓝钥去向小结(验证 'MT9 蓝门浪费蓝钥' 猜测)")
    print("=" * 78)
    blue_ev = [e for e in events if e[6] == "blueKey"]
    spends = [e for e in blue_ev if e[7] < 0]
    gains = [e for e in blue_ev if e[7] > 0]
    print(f"  开局蓝钥 = {start_keys.get('blueKey', 0)} 把   终态蓝钥 = {s.hero.keys.get('blueKey', 0)} 把")
    print(f"  蓝钥获取点 [(段,层,x,y)]: {[(e[1], e[3], e[4], e[5]) for e in gains] or '无'}")
    if spends:
        for e in spends:
            print(f"  蓝钥消耗(开蓝门): [{e[1]}] {e[3]}({e[4]},{e[5]}) tok#{e[0]} → 消耗1蓝钥")
    else:
        print("  蓝钥消耗: 无(全程没开过蓝门)")
    print(f"  黄钥: 开局{start_keys.get('yellowKey', 0)} → 终态{s.hero.keys.get('yellowKey', 0)}")
    print(f"  红钥: 开局{start_keys.get('redKey', 0)} → 终态{s.hero.keys.get('redKey', 0)}")
    # 各层是否到访(看路线有没有去 MT8)
    s = build_initial_state()
    floors_seen = []
    for t in actions:
        s = step(s, t)
        if s.dead:
            break
        if not floors_seen or floors_seen[-1] != s.current_floor:
            floors_seen.append(s.current_floor)
    print(f"\n  楼层到访序列(去重相邻): {floors_seen}")
    print("\n  ★读法(给玩家参考·以 h5mota 回放为准):")
    print("    · 蓝钥消耗点若落在 MT9 → 印证玩家猜测(蓝钥浪费在 MT9·该门本可两黄替代)，")
    print("      则卡 ATK25 是钥匙稀缺(蓝钥被 MT9 吃光、MT8 一攻一防开不了)而非段内属性天花板。")
    print("    · 此时下一步应是钥匙稀缺(蓝钥别浪费 MT9)，而非甲/乙两核查。")


if __name__ == "__main__":
    main()
