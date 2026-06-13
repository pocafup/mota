"""一区(MT1-MT10) 属性源【只读清点】—— 列全 G 候选(攻/防/魔防/血/装备/祭坛/商人)，供玩家核对边界。

这【不是】 verify_drel 探针、【不碰】 vzone/solver，纯读各层【初始】地图 entities + 事件脚本(setBlock/
giveItem)，落盘 inventory_zone1_attr_sources.txt。

为什么要双扫(静态格 + 事件放置)：D_rel 的 admissible 命门 = G 必须覆盖"打 boss 前一切可得的属性源"，
漏一个 → 真实路线用了它 → 真实 boss 更便宜 → D_rel 高估 → 错杀最优。故宁可多列(标注待玩家核)不可漏。
本脚本只负责"列全 + 标出处(静态/哪个事件放的)"，**不判可达/不算到手血/不算钥代价**(那是探针的事，且
铁律禁手推路径)。"打 boss 前可不可得"的边界由玩家用游戏知识核对(静态 entities 列得到≠该格此阶段可达)。

一区全层 ratio=1，故 ratio_scaled 道具 gain=base。Δ 直接由 items.json pickup 效果算，不写死。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state
from sim.simulator import load_floor

ZONE1 = [f"MT{i}" for i in range(1, 11)]
DATA = Path(__file__).parent.parent / "data" / "games51"

items_def = json.loads((DATA / "items.json").read_text(encoding="utf-8"))
tiles_def = json.loads((DATA / "tiles.json").read_text(encoding="utf-8"))
shops_def = json.loads((DATA / "shops.json").read_text(encoding="utf-8"))

TILE_ITEM = {int(t): v["_item"] for t, v in tiles_def["items"].items()}
ATTR = ("atk", "def", "mdef", "hp")   # 属性源判定维(hp=血，玩家明确要列)；gold 另算(喂祭坛)


def item_delta(iid, ratio=1):
    """从 items.json pickup 效果算 ratio 下的 {stat:增量}。非 pickup 属性源→{}。"""
    d = items_def.get(iid)
    if not d:
        return {}
    pu = d.get("pickup")
    if not pu:
        return {}
    out = defaultdict(int)
    if pu["type"] == "stat":
        if "base" in pu:
            out[pu["stat"]] += pu["base"] * (ratio if pu.get("ratio_scaled") else 1)
        else:
            out[pu["stat"]] += pu.get("delta", 0)
    elif pu["type"] == "multi":
        for op in pu["ops"]:
            out[op["stat"]] += op["delta"]
    return {k: v for k, v in out.items() if k in ATTR or k == "gold"}


def is_attr_source(iid):
    dd = item_delta(iid)
    return any(dd.get(s) for s in ATTR)


def fmt_delta(dd):
    parts = []
    for s in ("atk", "def", "mdef", "hp", "gold"):
        if dd.get(s):
            parts.append(f"{s}+{dd[s]}")
    return " ".join(parts) if parts else "(无属性增量)"


def walk_events(node, hits):
    """递归找事件 op 里放置(setBlock number)/给予(item/id)属性源道具。hits:[(type,iid,delta)]。"""
    if isinstance(node, dict):
        t = node.get("type")
        num = node.get("number")
        iid = None
        if isinstance(num, int) and num in TILE_ITEM:
            iid = TILE_ITEM[num]
        elif isinstance(num, str):
            if num.isdigit() and int(num) in TILE_ITEM:
                iid = TILE_ITEM[int(num)]   # setBlock 用字符串图块号("27"=redGem)
            elif num in items_def:
                iid = num
        if iid and is_attr_source(iid):
            hits.append((t or "setBlock", iid, item_delta(iid)))
        give = node.get("item")
        if give is None:
            cand = node.get("id")
            give = cand if isinstance(cand, str) else None
        if isinstance(give, str) and give in items_def and is_attr_source(give):
            hits.append((t or "give", give, item_delta(give)))
        for v in node.values():
            walk_events(v, hits)
    elif isinstance(node, list):
        for v in node:
            walk_events(v, hits)


EVENT_SECTIONS = ["events", "after_battle", "before_battle", "after_open_door",
                  "auto_event", "after_get_item", "out_events"]


def scan_floor(base, fid):
    floor = load_floor(base._floors_dir / f"{fid}.json")
    base.floors[fid] = floor
    static, altars, merchants, evplaced = [], [], [], []

    # 静态 entities 扫：道具(属性源) + 祭坛(131,'商店') + 商人(122,'trader')
    for y, row in enumerate(floor.entities):
        for x, e in enumerate(row):
            if not e:
                continue
            iid = floor._tile_to_item.get(e)
            if iid and is_attr_source(iid):
                static.append((x, y, iid, item_delta(iid)))
                continue
            if floor._tile_to_common_event.get(e) == "商店":
                altars.append((x, y))
            elif floor._tile_to_trigger.get(e) == "trader":
                merchants.append((x, y))

    # 事件放置扫：各事件 section 里的 setBlock/give 属性源
    for sec in EVENT_SECTIONS:
        d = getattr(floor, sec, None)
        if isinstance(d, dict):
            for key, ops in d.items():
                hits = []
                walk_events(ops, hits)
                for (t, iid, dd) in hits:
                    evplaced.append((f"{sec}[{key}]", t, iid, dd))
        elif isinstance(d, list):
            hits = []
            walk_events(d, hits)
            for (t, iid, dd) in hits:
                evplaced.append((sec, t, iid, dd))
    # first_arrive 是 list
    hits = []
    walk_events(getattr(floor, "first_arrive", []), hits)
    for (t, iid, dd) in hits:
        evplaced.append(("first_arrive", t, iid, dd))

    return floor, static, altars, merchants, evplaced


def main():
    base = build_initial_state()
    L = []

    def w(s=""):
        L.append(s)

    w("=" * 96)
    w("一区(MT1-MT10) 属性源清点 —— G 候选全列(供玩家核对'打boss前可得'边界)")
    w("只读各层初始地图 + 事件脚本；不判可达/不算到手血/不算钥代价。一区全 ratio=1。")
    w("=" * 96)

    grand = defaultdict(lambda: defaultdict(int))   # cat -> stat -> 总增量(全拿上限,不管钥够不够)
    count = defaultdict(int)

    for fid in ZONE1:
        floor, static, altars, merchants, evplaced = scan_floor(base, fid)
        w("")
        w(f"── {fid}  (ratio={floor.ratio})  静态属性源 {len(static)} · 祭坛 {len(altars)} · "
          f"商人 {len(merchants)} · 事件放置候选 {len(evplaced)} ──")

        if static:
            w("  [静态格 · 地上直接可拾]")
            for (x, y, iid, dd) in sorted(static, key=lambda r: (r[1], r[0])):
                nm = items_def[iid]["name"]
                w(f"     ({x:>2},{y:>2})  {iid:<11s}{nm:<5s}  {fmt_delta(dd)}")
                count[iid] += 1
                for s, v in dd.items():
                    grand["static"][s] += v

        for (x, y) in altars:
            a = next((a for a in shops_def["altars"] if a["floor"] == fid), None)
            extra = (f"  每次买 atk+{a['atk_per_purchase']}/def+{a['def_per_purchase']}"
                     f"  (花金币, times1 全局涨价 {shops_def['_altar_system']['cost_sequence'][:5]}...)") if a else ""
            w(f"  [祭坛] ({x},{y}){extra}")

        for (x, y) in merchants:
            m = next((m for m in shops_def["merchants"]["items"]
                      if m.get("floor") == fid and m.get("pos") == f"{x},{y}"), None)
            extra = f"  花{m['price']}金 → {m['give']}" if m else ""
            w(f"  [商人] ({x},{y}){extra}  (卖钥匙=间接属性源:钥→开门→门后宝石)")

        if evplaced:
            w("  [事件放置候选 · 需玩家核对该事件何时触发/是否打boss前]")
            for (where, t, iid, dd) in evplaced:
                nm = items_def[iid]["name"]
                w(f"     {where:<22s} {t:<10s} {iid:<11s}{nm:<5s} {fmt_delta(dd)}")

    # ── 全拿上限(忽略钥/可达) ──
    w("")
    w("=" * 96)
    w("【静态属性源·全拿上限】(仅地上静态格求和；忽略钥够不够/可不可达——给规模感，非真实可得)")
    tot = defaultdict(int)
    for s, v in grand["static"].items():
        tot[s] += v
    w("  ΣΔ(全拿静态) = " + fmt_delta(tot))
    w("  分项计数: " + ", ".join(f"{items_def[i]['name']}×{c}" for i, c in
                              sorted(count.items(), key=lambda kv: -kv[1])))
    w("")
    w("  注：祭坛(MT4)= 花金币买 atk/def，量由金币预算定，不计入上面'全拿'；商人(MT6/MT7)= 卖钥匙，")
    w("      间接属性源(钥→门→门后宝石)。两者要不要进 G 见报告讨论。")
    w("  注：事件放置候选含 boss/打怪掉落——MT10 afterBattle[6,1] 的奖励是【打完一区boss才掉】= 不该进 G。")
    w("=" * 96)

    report = "\n".join(L)
    out = Path(__file__).parent / "inventory_zone1_attr_sources.txt"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[落盘] {out}")


if __name__ == "__main__":
    main()
