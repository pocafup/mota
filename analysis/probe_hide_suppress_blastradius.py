"""hide 抑制修法的两个防误伤前置探针（全塔 51 层 + common_events.json 静态扫描）。

拟议修法：hide 执行时把被隐藏格登记进 _suppressed_events（当前只在 remove 时登记），
匹配网站"hide 移除触发块、再踏不触发"。最窄实现 = 只改"无 loc 的 hide"（隐藏自己的
触发格，即 (3,7) 那种）。本探针圈死它的影响面。

前置1：扫 events/outEvents 里所有【无 loc】hide（=隐藏自己触发格），按 remove 分组。
  无 remove 的那些 = 最窄修法新增抑制的对象。逐条列出楼层/格/对话/指令类型，
  好判断有没有哪个 hide 自己后还指望【再踏重触发】（若有→全局放宽会误封）。
前置2：扫 show 目标格 ∩ hide 目标格 = "先 hide 后被 show 复活"的候选。
  若某格被 hide(将被抑制)后又被 show 复活且需重触发，修法要配套让 show 解除抑制。

只静态读数据、不改任何代码。跑法：python extract/probe_hide_suppress_blastradius.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"

REFIRE = ["events", "outEvents"]          # 踏格可重触发面
OTHER = ["afterBattle", "beforeBattle", "afterOpenDoor", "afterGetItem",
         "autoEvent", "changeFloor", "firstArrive"]


def walk(obj):
    """递归 yield 所有 type 为 hide/show 的 dict（覆盖 if/choices/while 等任意嵌套分支）。"""
    if isinstance(obj, dict):
        if obj.get("type") in ("hide", "show"):
            yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def loc_cells(loc):
    """规整 loc → [(x,y)...]；含表达式(flag:/status:)则该项记 ('EXPR',原文)。"""
    if not loc:
        return []
    pairs = loc if isinstance(loc[0], (list, tuple)) else [loc]
    out = []
    for p in pairs:
        if isinstance(p[0], int) and isinstance(p[1], int):
            out.append((p[0], p[1]))
        else:
            out.append(("EXPR", str(p)))
    return out


def body_of(ev):
    return ev.get("data", []) if isinstance(ev, dict) else ev


def first_text(body):
    for it in (body or []):
        if isinstance(it, str):
            return it.strip()[:30]
    return ""


def types_in(body):
    ts = []
    for it in (body or []):
        if isinstance(it, dict) and it.get("type"):
            ts.append(it["type"])
    return ts


def main():
    floor_files = sorted(FLOORS.glob("MT*.json"),
                         key=lambda p: int(p.stem[2:]) if p.stem[2:].isdigit() else 999)

    noloc_refire = []      # (floor, cell, container, remove, dialogue, types)
    noloc_other = []       # 同上，OTHER 容器
    hide_targets = set()   # (floor, x, y) 会被隐藏的格（int loc）
    hide_dynamic = []      # (floor, ctx, 表达式) 动态 loc 的 hide
    show_targets = {}      # (floor, x, y) -> [来源描述...]

    def scan_event(fid, container, key, ev):
        body = body_of(ev)
        # 该事件的触发格（events/outEvents/afterBattle 等键即坐标）
        tx = ty = None
        if key and "," in str(key):
            try:
                tx, ty = (int(v) for v in str(key).split(","))
            except ValueError:
                pass
        for h in walk(ev):
            tfid = h.get("floorId") or fid
            if h["type"] == "show":
                for c in loc_cells(h.get("loc")):
                    if isinstance(c[0], int):
                        show_targets.setdefault((tfid, c[0], c[1]), []).append(
                            f"{fid}/{container}/{key}")
                continue
            # hide
            rm = bool(h.get("remove"))
            cells = loc_cells(h.get("loc"))
            if not cells:                       # 无 loc → 隐藏触发格自己
                if tx is not None:
                    hide_targets.add((tfid, tx, ty))
                    rec = (fid, f"{tx},{ty}", container, rm, first_text(body), types_in(body))
                    (noloc_refire if container in REFIRE else noloc_other).append(rec)
                else:
                    hide_dynamic.append((fid, f"{container}/{key}", "无loc且触发格非坐标(公共事件?)"))
            else:
                for c in cells:
                    if isinstance(c[0], int):
                        hide_targets.add((tfid, c[0], c[1]))
                    else:
                        hide_dynamic.append((fid, f"{container}/{key}", c[1]))

    for fp in floor_files:
        d = json.loads(fp.read_text(encoding="utf-8"))
        fid = d["floorId"]
        for container in REFIRE + OTHER:
            cont = d.get(container)
            if isinstance(cont, dict):
                for key, ev in cont.items():
                    scan_event(fid, container, key, ev)
            elif isinstance(cont, list):        # firstArrive
                scan_event(fid, container, None, cont)

    # 公共事件（无坐标，loc 多为表达式）
    ce_path = DATA / "common_events.json"
    if ce_path.exists():
        ces = json.loads(ce_path.read_text(encoding="utf-8"))
        for name, body in ces.items():
            for h in walk(body):
                if h["type"] == "show":
                    for c in loc_cells(h.get("loc")):
                        if isinstance(c[0], int):
                            show_targets.setdefault(("?", c[0], c[1]), []).append(f"common/{name}")
                else:
                    cells = loc_cells(h.get("loc"))
                    if not cells:
                        hide_dynamic.append(("common", name, "无loc(隐藏调用者格,运行时定)"))
                    else:
                        for c in cells:
                            if c[0] == "EXPR":
                                hide_dynamic.append(("common", name, c[1]))

    # ── 前置1 ────────────────────────────────────────────────────────────────
    print("=" * 78)
    print("前置1：events/outEvents 里【无 loc】hide（隐藏自己触发格）——最窄修法影响面")
    print("=" * 78)
    no_rm = [r for r in noloc_refire if not r[3]]
    with_rm = [r for r in noloc_refire if r[3]]
    print(f"\n无 remove（修法【新增】抑制这些，共 {len(no_rm)} 处）：")
    print("楼层  触发格   容器       对话/指令类型")
    print("-" * 74)
    for fid, cell, cont, rm, txt, types in no_rm:
        print(f"{fid:<5} {cell:<7} {cont:<9}  「{txt}」 {types}")
    print(f"\n已带 remove（当前已抑制，修法对其无变化，共 {len(with_rm)} 处）：")
    for fid, cell, cont, rm, txt, types in with_rm:
        print(f"{fid:<5} {cell:<7} {cont:<9}  「{txt}」 {types}")
    if noloc_other:
        print(f"\n（参考）OTHER 容器(afterBattle/autoEvent 等，按死亡/flag 触发、不靠重踏)"
              f"的无 loc hide 共 {len(noloc_other)} 处：")
        for fid, cell, cont, rm, txt, types in noloc_other:
            print(f"{fid:<5} {cell:<7} {cont:<11} remove={rm}  「{txt}」 {types}")

    # ── 前置2 ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("前置2：show 目标格 ∩ hide 目标格 = 先 hide 后被 show 复活的候选")
    print("=" * 78)
    inter = []
    for cell, srcs in show_targets.items():
        fid, x, y = cell
        cand = (fid, x, y) in hide_targets or ("?", x, y) in hide_targets or any(
            (hf, x, y) in hide_targets for hf in {fid})
        # 同层精确匹配
        if (fid, x, y) in hide_targets:
            inter.append((cell, srcs))
    if inter:
        print("⚠ 同时是 hide 目标与 show 目标的格（修法加抑制后，show 复活需配套解抑制）：")
        for (fid, x, y), srcs in inter:
            print(f"  {fid}({x},{y})  show来源={srcs}")
    else:
        print("无：没有任何格【既被 hide 又被 show】。show 复活与 hide 抑制面不相交。")

    print(f"\n全塔 show 目标格共 {len(show_targets)} 个：")
    for (fid, x, y), srcs in sorted(show_targets.items(), key=lambda kv: str(kv[0])):
        tag = "  ← 也是hide目标!" if (fid, x, y) in hide_targets else ""
        print(f"  {fid}({x},{y})  来源={srcs}{tag}")

    if hide_dynamic:
        print(f"\n（参考）动态 loc / 公共事件 hide 共 {len(hide_dynamic)} 处（loc 运行时定，静态无法判定格）：")
        for fid, ctx, expr in hide_dynamic:
            print(f"  {fid:<7} {ctx:<16} {expr}")


if __name__ == "__main__":
    main()
