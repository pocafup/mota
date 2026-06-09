#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全塔楼梯/飞行边审计（只读数据，不改引擎）。

目的：在把楼梯建成跨层缩点边之前，先从源码核清楚——
  (1) 哪些楼梯是【单向】的（目标层没有反向格回来）；
  (2) 哪些楼梯【带门禁】（changeFloor 格在 events 里 enable:false，或被脚本条件控制）；
  (3) 事件脚本里【内嵌的 changeFloor 传送】（隐藏层/传送门，不是普通楼梯格）；
  (4) 飞行相关字段（canFlyTo/canFlyFrom/cannotMoveDirectly 等）。

输出供玩家拍板门禁口径，再决定跨层缩点边怎么建。
"""
import json
import os
import re
import glob

FLOOR_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "games51", "floors")


def floor_index(fid):
    m = re.match(r"MT(\d+)$", fid)
    return int(m.group(1)) if m else None


HIDDEN_IDX = set()  # 隐藏层(isHide=true)的楼层序号；引擎解析 :next/:before 时跳过


def resolve_target(fid, raw):
    """把 :next/:before 解析成真实 floorId（与引擎一致：跳过隐藏层）。"""
    idx = floor_index(fid)
    if idx is None:
        return raw
    if raw == ":next":
        j = idx + 1
        while j in HIDDEN_IDX:
            j += 1
        return f"MT{j}"
    if raw == ":before":
        j = idx - 1
        while j in HIDDEN_IDX:
            j -= 1
        return f"MT{j}"
    return raw


def walk_actions(node, found):
    """递归扫描事件脚本里的 {type:changeFloor} 动作。"""
    if isinstance(node, dict):
        if node.get("type") == "changeFloor":
            found.append(node)
        for v in node.values():
            walk_actions(v, found)
    elif isinstance(node, list):
        for v in node:
            walk_actions(v, found)


def main():
    files = sorted(glob.glob(os.path.join(FLOOR_DIR, "MT*.json")),
                   key=lambda p: floor_index(os.path.splitext(os.path.basename(p))[0]) or -1)

    floors = {}
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        floors[data["floorId"]] = data

    # 先标定隐藏层（引擎解析 :next/:before 会跳过它们）
    for fid, data in floors.items():
        if data.get("isHide"):
            idx = floor_index(fid)
            if idx is not None:
                HIDDEN_IDX.add(idx)

    # ---- 收集普通楼梯格 ----
    # edges[(F, cell)] = {target, stair, enable(None/True/False), gated_reason}
    stair_edges = {}
    for fid, data in floors.items():
        cf = data.get("changeFloor", {})
        events = data.get("events", {})
        for cell, info in cf.items():
            target = resolve_target(fid, info.get("floorId", ""))
            ev = events.get(cell)
            enable = None
            gated = ""
            if isinstance(ev, dict):
                if ev.get("enable") is False:
                    enable = False
                    gated = "events.enable=false"
                elif ev.get("enable") is True:
                    enable = True
                if ev.get("trigger"):
                    gated = (gated + "; " if gated else "") + f"trigger={ev.get('trigger')}"
            elif isinstance(ev, list) and ev:
                gated = "events[cell]=脚本(可能条件控制)"
            stair_edges[(fid, cell)] = {
                "target": target,
                "stair": info.get("stair"),
                "enable": enable,
                "gated": gated,
            }

    # ---- 收集事件内嵌 changeFloor 传送 ----
    portal_edges = []  # (F, where, target, loc)
    # 扫整张层 JSON 的所有区块（map 等数组里没有 type:changeFloor，顶层 changeFloor 楼梯项也没有 "type"，都不会误命中）
    for fid, data in floors.items():
        for section, sec in data.items():
            if section == "changeFloor" or not isinstance(sec, (dict, list)):
                continue
            found = []
            walk_actions(sec, found)
            for act in found:
                portal_edges.append((fid, section, resolve_target(fid, act.get("floorId", "")), act.get("loc")))

    # ---- 楼梯互通性（按层对） ----
    # pair_dirs[(A,B)] = set of source floors that have an edge A->B
    pair_has_edge = set()  # (src, dst)
    for (fid, cell), e in stair_edges.items():
        pair_has_edge.add((fid, e["target"]))
    for fid, sec, target, loc in portal_edges:
        if target:
            pair_has_edge.add((fid, target))

    # ---- 报告 ----
    print("=" * 92)
    print("全塔楼梯/飞行边审计")
    print("=" * 92)

    print("\n【1】普通楼梯格（changeFloor）逐条：")
    print("-" * 92)
    print(f"{'源层':>6} {'格子':>7}  {'→目标':>6}  {'落点stair':>10}  门禁")
    print("-" * 92)
    one_way = []
    gated_list = []
    for (fid, cell), e in sorted(stair_edges.items(),
                                 key=lambda kv: (floor_index(kv[0][0]) or -1, kv[0][1])):
        target = e["target"]
        reciprocal = (target, fid) in pair_has_edge
        mark = "" if reciprocal else "  ★单向(目标层无回程格)"
        gate = e["gated"] or ("enable=False" if e["enable"] is False else "")
        if not reciprocal:
            one_way.append((fid, cell, target))
        if gate:
            gated_list.append((fid, cell, target, gate))
        print(f"{fid:>6} {cell:>7}  {target:>6}  {str(e['stair']):>10}  {gate}{mark}")

    print("\n【2】事件内嵌 changeFloor 传送（隐藏层/传送门，非普通楼梯）：")
    print("-" * 92)
    if portal_edges:
        for fid, sec, target, loc in sorted(portal_edges, key=lambda t: (floor_index(t[0]) or -1, t[1])):
            recip = (target, fid) in pair_has_edge if target else False
            mark = "" if recip else "  ★无反向"
            print(f"{fid:>6}  in {sec:<12} → {str(target):>6}  loc={loc}{mark}")
    else:
        print("  （无）")

    print("\n【3】单向楼梯汇总（目标层没有任何回到源层的格/传送）：")
    print("-" * 92)
    if one_way:
        for fid, cell, target in one_way:
            print(f"  {fid} {cell} → {target}")
    else:
        print("  （无——所有普通楼梯都有层对级反向边）")

    print("\n【4】带门禁的楼梯（enable:false 或脚本条件）：")
    print("-" * 92)
    if gated_list:
        for fid, cell, target, gate in gated_list:
            print(f"  {fid} {cell} → {target}   [{gate}]")
    else:
        print("  （无）")

    print("\n【5】飞行/移动相关字段（逐层）：")
    print("-" * 92)
    fly_keys = ("canFlyTo", "canFlyFrom", "cannotMoveDirectly", "flyFromList", "canFly")
    any_fly = False
    for fid in sorted(floors, key=lambda f: floor_index(f) or -1):
        data = floors[fid]
        present = {k: data.get(k) for k in fly_keys if k in data}
        if present:
            any_fly = True
            print(f"  {fid}: {present}")
    if not any_fly:
        print("  （楼层 JSON 无 canFly*/cannotMove* 字段——飞行可能是全局道具/技能，需另查 data/items 或全局规则）")

    print("\n【6】隐藏层 & 仅飞行可入的楼层（楼梯图之外）：")
    print("-" * 92)
    stair_targets = {e["target"] for e in stair_edges.values()}
    stair_targets |= {t for _, _, t, _ in portal_edges if t}
    for fid in sorted(floors, key=lambda f: floor_index(f) or -1):
        data = floors[fid]
        hide = data.get("isHide")
        no_in = fid not in stair_targets
        flyto = data.get("canFlyTo")
        flyfrom = data.get("canFlyFrom")
        if hide or no_in or flyto is not None or flyfrom is not None:
            tags = []
            if hide:
                tags.append("isHide=true")
            if no_in:
                tags.append("无楼梯指向本层(仅飞行/事件可入)")
            if flyto is not None:
                tags.append(f"canFlyTo={flyto}")
            if flyfrom is not None:
                tags.append(f"canFlyFrom={flyfrom}")
            print(f"  {fid}: {', '.join(tags)}")

    print("\n【7】各层 up/down 落点（downFloor=下楼梯落点, upFloor=上楼梯落点）：")
    print("-" * 92)
    for fid in sorted(floors, key=lambda f: floor_index(f) or -1):
        data = floors[fid]
        print(f"  {fid}: downFloor={data.get('downFloor')}  upFloor={data.get('upFloor')}")


if __name__ == "__main__":
    main()
