"""一区(MT1-10) 门禁机制【只读核实】——每扇门到底靠什么开。回源码 floor json 的 map+事件脚本，不猜。

玩家纠正(2026-06-10)：MT2 那 6 扇"steelDoor"图块其实是【杀两个 def110 blueGuard 触发 afterBattle
openDoor】的机关门，不耗钢钥。门的开法不只"钥匙开"：还有 杀怪触发机关 / 踩格(事件)触发 /
specialDoor(本作无 specialKey、只能事件开) / 真封死(需本区没有的钥匙)。摸清开法，"真耗钥门数"才算得对。

判定(交叉 map 门 tile × events/afterBattle/firstArrive 里 openDoor 的目标 loc，全从源码读)：
  门 tile：81黄/82蓝/83红/84绿/86钢(DOOR_KEY_MAP) + 85 specialDoor(tiles.json：本作无 specialKey)。
  (a) 耗钥门：标准色门 tile 且 loc 【不】被任何 openDoor 事件覆盖 → 必须消耗对应颜色钥匙。
  (b) 杀怪机关门：loc 被 afterBattle[怪格] 的 openDoor 覆盖 → 杀那(些)怪自动开，不耗钥。
  (c) 事件门：loc 被 events[格]/firstArrive 的 openDoor 覆盖 → 踩格/到达触发开，不耗钥。
  (d) 真封死：85 specialDoor 且无 openDoor 覆盖(本作无 specialKey 又没事件开)；或 86 钢门无事件开(本区 0 钢钥)。
注：specialDoor(85) 本作无 specialKey → 必须事件开；同 loc 可被多源覆盖；closeDoor(关门，如埋伏) 单列。
塔无关性不适用(extract/ 驱动层、可读 MT1-10 源数据)。
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import FLOORS
from sim.simulator import load_floor, DOOR_KEY_MAP, SPECIAL_DOOR

ZONE1 = [f"MT{i}" for i in range(1, 11)]
DOOR_TILE = dict(DOOR_KEY_MAP)        # 81→yellowKey ... 86→steelKey
DOOR_TILE[SPECIAL_DOOR] = "specialKey"  # 85 specialDoor（本作无 specialKey）
KEY_TILES = {21: "yellowKey", 22: "blueKey", 23: "redKey",
             24: "greenKey", 25: "steelKey", 26: "bigKey"}  # tiles.json items
CN = {"yellowKey": "黄", "blueKey": "蓝", "redKey": "红", "greenKey": "绿",
      "steelKey": "钢", "specialKey": "机关85"}
_ORDER = ["yellowKey", "blueKey", "redKey", "greenKey", "steelKey", "specialKey"]


def _cn(c):
    return CN.get(c, c)


def collect_ops(node, out):
    """递归收集事件脚本里所有 openDoor/closeDoor 的目标 (type, (x,y)|None)（穿透 if/true/false 等嵌套）。
    无 loc 的 openDoor/closeDoor 记成 (type, None)——语义待确认，绝不猜它开哪扇门。"""
    if isinstance(node, dict):
        t = node.get("type")
        if t in ("openDoor", "closeDoor"):
            loc = node.get("loc")
            if isinstance(loc, list) and len(loc) == 2 and isinstance(loc[0], (int, float)):
                out.append((t, (int(loc[0]), int(loc[1]))))
            else:
                out.append((t, None))  # 无 loc/非常规 loc —— 待确认
        for v in node.values():
            collect_ops(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_ops(v, out)


def collect_getitem(node, out):
    """递归收集事件脚本里所有 getItem 给的道具 (id, num)（盗贼/宝箱/firstArrive 等给的钥匙也算）。"""
    if isinstance(node, dict):
        if node.get("type") == "getItem":
            iid = node.get("id")
            n = node.get("count", node.get("num", 1))
            try:
                n = int(n)
            except (TypeError, ValueError):
                n = 1
            if iid:
                out.append((iid, n))
        for v in node.values():
            collect_getitem(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_getitem(v, out)


def count_keys(fid):
    """一区钥匙普查：map tile 上的钥匙 + 事件 getItem 给的钥匙。返回 (tile计数, 事件计数)。"""
    data = json.loads((FLOORS / f"{fid}.json").read_text(encoding="utf-8"))
    m = data["map"]
    kt, ke = Counter(), Counter()
    for row in m:
        for tile in row:
            if tile in KEY_TILES:
                kt[KEY_TILES[tile]] += 1
    gi = []
    for sec in ("events", "afterBattle", "firstArrive", "autoEvent"):
        if data.get(sec):
            collect_getitem(data[sec], gi)
    for iid, n in gi:
        if iid in KEY_TILES.values():
            ke[iid] += n
    return kt, ke


def scan(fid):
    data = json.loads((FLOORS / f"{fid}.json").read_text(encoding="utf-8"))
    m = data["map"]
    fl = load_floor(FLOORS / f"{fid}.json")
    doors = {}
    for y in range(len(m)):
        for x in range(len(m[y])):
            if m[y][x] in DOOR_TILE:
                doors[(x, y)] = DOOR_TILE[m[y][x]]
    open_by, close_by, noloc = defaultdict(list), defaultdict(list), []
    for section in ("events", "afterBattle", "firstArrive", "autoEvent"):
        sec = data.get(section)
        if not sec:
            continue
        items = sec.items() if isinstance(sec, dict) else [("*", sec)]
        for trig, evs in items:
            ops = []
            collect_ops(evs, ops)
            for op_type, loc in ops:
                if loc is None:
                    noloc.append((section, trig, op_type))  # 无 loc，待确认
                    continue
                (open_by if op_type == "openDoor" else close_by)[loc].append((section, trig))
    return data, m, fl, doors, open_by, close_by, noloc


def trig_label(fl, m, section, trig):
    """把触发源翻成人读：杀怪标怪 id+def；踩格标坐标；到达层。"""
    if section == "afterBattle" and isinstance(trig, str) and "," in trig:
        x, y = (int(v) for v in trig.split(","))
        mid = fl._tile_to_enemy.get(m[y][x])
        if mid:
            md = fl._monsters_db.get(mid, {})
            return f"杀@({x},{y}){mid}(def{md.get('def')})"
        return f"杀@({x},{y})"
    if section == "events":
        return f"踩@{trig}"
    if section == "firstArrive":
        return "到达本层"
    return f"{section}@{trig}"


def main():
    out = []

    def w(s=""):
        out.append(s)

    w("=" * 100)
    w("一区(MT1-10) 门禁机制核实 —— 每扇门靠什么开(回源码 map + 事件脚本，不猜)")
    w("=" * 100)

    tot, pay, kill, evt, sealed = Counter(), Counter(), Counter(), Counter(), Counter()
    machine_list, sealed_list, close_list, nondoor_open, noloc_all = [], [], [], [], []
    per_floor = {}

    for fid in ZONE1:
        data, m, fl, doors, open_by, close_by, noloc = scan(fid)
        for section, trig, op_type in noloc:
            noloc_all.append((fid, section, trig, op_type))
        f_tot = Counter()
        for (x, y), color in sorted(doors.items()):
            tot[color] += 1
            f_tot[color] += 1
            srcs = open_by.get((x, y), [])
            secs = {s for s, _ in srcs}
            labels = sorted({trig_label(fl, m, s, t) for s, t in srcs})
            if srcs:
                if "afterBattle" in secs:
                    kill[color] += 1
                    cat = "杀怪机关门"
                else:
                    evt[color] += 1
                    cat = "事件门"
                machine_list.append((fid, (x, y), color, labels, cat))
            else:
                if color == "specialKey":
                    sealed[color] += 1
                    sealed_list.append((fid, (x, y), color, "special门-无事件开(本作无 specialKey)"))
                else:
                    pay[color] += 1
        per_floor[fid] = f_tot
        for loc, srcs in close_by.items():
            close_list.append((fid, loc, sorted({trig_label(fl, m, s, t) for s, t in srcs})))
        for loc, srcs in open_by.items():
            if loc not in doors:
                t = m[loc[1]][loc[0]] if 0 <= loc[1] < len(m) and 0 <= loc[0] < len(m[loc[1]]) else None
                nondoor_open.append((fid, loc, t, sorted({trig_label(fl, m, s, tt) for s, tt in srcs})))

    # 钥匙普查（map tile + 事件 getItem）
    key_tile, key_evt = Counter(), Counter()
    key_per_floor = {}
    for fid in ZONE1:
        kt, ke = count_keys(fid)
        key_tile += kt
        key_evt += ke
        key_per_floor[fid] = (kt, ke)

    # ── §1 各层门 tile 普查 ──
    w("-" * 100)
    w("【§1 各层门 tile 普查(map 初始 terrain，含 85 specialDoor)】")
    for fid in ZONE1:
        ft = per_floor[fid]
        cells = "  ".join(f"{_cn(c)}={ft[c]}" for c in _ORDER if ft.get(c))
        w(f"  {fid:<5}{cells or '(无门)'}")
    w(f"  合计  " + "  ".join(f"{_cn(c)}={tot[c]}" for c in _ORDER if tot.get(c)))

    # ── §2 开法分类汇总 ──
    w("-" * 100)
    w("【§2 全区门按开法分类(交叉事件 openDoor 目标)】")
    w(f"  {'色':<8}{'总门':<6}{'(a)真耗钥':<10}{'(b)杀怪机关':<12}{'(c)事件门':<10}{'(d)死门special':<14}")
    for c in _ORDER:
        if not tot.get(c):
            continue
        w(f"  {_cn(c):<8}{tot[c]:<6}{pay.get(c,0):<10}{kill.get(c,0):<12}"
          f"{evt.get(c,0):<10}{sealed.get(c,0):<14}")
    w("  ▸ (a) 才是真正消耗该色钥匙的门；(b)(c) 杀怪/踩格自动开，不耗钥；(d) 本作开不了。")

    # ── §3 机关门 / 事件门清单（重点：MT2 验证） ──
    w("-" * 100)
    w("【§3 机关门(杀怪开) / 事件门(踩格开) 清单——这些不耗钥，上轮被我误当耗钥门/封死】")
    by_floor_machine = defaultdict(list)
    for fid, loc, color, labels, cat in machine_list:
        by_floor_machine[fid].append((loc, color, labels, cat))
    for fid in ZONE1:
        items = by_floor_machine.get(fid)
        if not items:
            continue
        w(f"  {fid}:")
        for loc, color, labels, cat in sorted(items):
            w(f"     ({loc[0]},{loc[1]}) {_cn(color):<6}[{cat}] ← {' / '.join(labels)}")

    # ── §4 真封死 / 需外区钥匙 ──
    w("-" * 100)
    w("【§4 真封死(本作开不了) / 真耗钥但本区无钥(需外区带回)】")
    if sealed_list:
        w("  ① specialDoor(85) 无事件开 = 本作 specialKey 不存在 → 永久开不了：")
        for fid, loc, color, note in sorted(sealed_list):
            w(f"     {fid}({loc[0]},{loc[1]}) {note}")
    else:
        w("  ① specialDoor 无事件开者：无（一区的 special 门若有，均由事件开）")
    pay_steel = pay.get("steelKey", 0)
    w(f"  ② 真耗钢钥门(无事件覆盖、必须 steelKey)：{pay_steel} 扇"
      f"（一区 0 钢钥 → 这些才是真‘需外区钥匙’；MT2 那 6 扇钢门图块不在此列，是机关门）")

    # ── §5 closeDoor / openDoor 开非门 ──
    w("-" * 100)
    w("【§5 其它门类机制(机制完整性)】")
    w(f"  closeDoor(关门，如埋伏触发) {len(close_list)} 处：")
    for fid, loc, labels in sorted(close_list)[:20]:
        w(f"     {fid}({loc[0]},{loc[1]}) ← {' / '.join(labels)}")
    w(f"  openDoor 目标【非门 tile】(撞墙开路/开 specialDoor 等) {len(nondoor_open)} 处：")
    for fid, loc, t, labels in sorted(nondoor_open)[:20]:
        w(f"     {fid}({loc[0]},{loc[1]}) tile={t} ← {' / '.join(labels)}")
    w(f"  ⚠ 无 loc 的 openDoor/closeDoor(语义待确认，不猜其开哪扇门) {len(noloc_all)} 处：")
    for fid, section, trig, op_type in sorted(noloc_all):
        w(f"     {fid} {op_type}@{section}[{trig}] —— 无 loc 字段，引擎语义待玩家确认")

    # ── §6 真耗钥门 vs 可达钥匙 对账 ──
    real_keys = ["yellowKey", "blueKey", "redKey", "greenKey", "steelKey"]
    w("-" * 100)
    w("【§6 稀缺度对账：真耗钥门(a) vs 地图钥匙(tile+事件 getItem)】")
    w(f"  {'色':<6}{'门tile总':<9}{'真耗钥门(a)':<12}{'钥匙(tile)':<11}{'钥匙(事件)':<11}{'钥合计':<8}{'静态缺口':<10}")
    for c in real_keys:
        td = tot.get(c, 0)
        a = pay.get(c, 0)
        ks_t = key_tile.get(c, 0)
        ks_e = key_evt.get(c, 0)
        ks = ks_t + ks_e
        if td == 0 and ks == 0:
            continue
        gap = a - ks  # >0 = 门比钥多 = 至少这么多扇开不了；<0 = 钥有余
        if gap > 0:
            note = f"缺{gap}(≥{gap}扇开不了)"
        elif gap == 0:
            note = "平"
        else:
            note = f"余{-gap}"
        w(f"  {_cn(c):<6}{td:<9}{a:<12}{ks_t:<11}{ks_e:<11}{ks:<8}{note:<10}")
    w("  ▸ 缺口=真耗钥门(a)−钥匙合计；>0 ⇒ 必抉择开哪些门(airtight，与可达性无关)。")
    w("  ▸ 注：钥匙合计=【地图静态总数】≠【当前阶段可用数】。可达性进一步收紧见 probe_zone1_key_scarcity.py(C 上界)。")

    # ── 结论 ──
    w("=" * 100)
    w("【结论：一区门的真实开法】")
    w(f"  · 各色【真耗钥门(a)】：" + "  ".join(f"{_cn(c)}={pay.get(c,0)}" for c in _ORDER if tot.get(c)))
    w(f"  · 各色门总数(含机关/事件/死门)：" + "  ".join(f"{_cn(c)}={tot[c]}" for c in _ORDER if tot.get(c)))
    w("  · ∴ 上轮直接拿‘门 tile 总数’当‘耗钥门数’是错的——机关门(杀怪)/事件门(踩格)不耗钥。")
    w("  · 重算真实稀缺度须用【真耗钥门(a)】对账可达钥匙；机关门的代价=杀触发怪(见各门触发源的 def)。")
    w("=" * 100)

    text = "\n".join(out)
    p = Path(__file__).parent / "zone1_door_mechanisms.txt"
    p.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[落盘] {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
