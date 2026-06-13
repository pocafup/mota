"""把【拿到 MT9 铁盾】PRIMARY 路线导出成【逐步可照走 + 关键标注】清单。

读 extract/shield_route_decision.json 的 primary.actions，引擎逐 token 重放，标注：
换层 / 属性增益(铁剑+10ATK·铁盾+10DEF·宝石+1) / 拿道具钥匙 / 杀怪累计；第835步拿铁盾高亮。
全部引擎算（铁律：不手推路径/属性）。落盘 extract/shield_walkthrough.txt。

玩家用途：照着方向走真实游戏，核对「第835步才拿盾、此前已杀39怪」是否亏路线。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from solver.verify import replay, diff_states
from probe_crossfloor import build_start

OUT = Path(__file__).parent
DATA = OUT / "shield_route_decision.json"
ARROW = {"U": "↑", "D": "↓", "L": "←", "R": "→"}


def snap(s):
    h = s.hero
    return {"floor": s.current_floor, "x": h.x, "y": h.y, "hp": h.hp,
            "atk": h.atk, "def": h.def_, "mdef": h.mdef, "kill": h.kill_count,
            "items": dict(h.items), "keys": dict(h.keys)}


def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    cfg = payload["config"]
    prim = payload["primary"]
    actions = prim["actions"]
    shield = prim.get("shield") or {}

    # ── 引擎逐 token 重放，记录每步事件（铁律：标注由引擎算，不手推）──
    s, _ = build_start()
    start = snap(s)
    prev = start
    rows = []                      # (步号, tok, [事件str], 当刻snap, 全局kill计数)
    for i, tok in enumerate(actions, 1):
        before = prev
        s = step(s, tok)
        after = snap(s)
        ev = []
        if before["floor"] != after["floor"]:
            ev.append(("FLOOR", "⟶换层 %s→%s" % (before["floor"], after["floor"])))
        for key, lab in (("atk", "ATK"), ("def", "DEF"), ("mdef", "MDEF")):
            if after[key] > before[key]:
                d = after[key] - before[key]
                tag = ""
                if key == "atk" and d >= 10:
                    tag = "  ◆铁剑"
                elif key == "def" and d >= 10:
                    tag = "  ★★★铁盾★★★"
                ev.append((key.upper(), "▲%s %d→%d(+%d)%s" % (lab, before[key], after[key], d, tag)))
        if after["kill"] > before["kill"]:
            ev.append(("KILL", "✗杀怪×%d(累计%d只)"
                       % (after["kill"] - before["kill"], after["kill"])))
        for name in ("items", "keys"):
            for k, v in after[name].items():
                pv = before[name].get(k, 0)
                if v > pv:
                    ev.append(("ITEM", "◆获得 %s×%d(持%d)" % (k, v - pv, v)))
        rows.append((i, tok, ev, after, after["kill"]))
        prev = after
    end = prev

    # ── 独立裁判：重放对拍（引擎只当裁判）──
    s2, _ = build_start()
    rep = replay(s2, list(actions), step, _copy_state)
    diffs = diff_states(s, rep)
    verdict = "✅ 零差异（可照走）" if not diffs else ("❌ 差异: %s" % diffs)

    n_floor = sum(1 for r in rows for e in r[2] if e[0] == "FLOOR")
    sword = next((r for r in rows
                  if any(e[0] == "ATK" and "铁剑" in e[1] for e in r[2])), None)
    shield_row = next((r for r in rows
                       if any(e[0] == "DEF" and "铁盾" in e[1] for e in r[2])), None)

    L = []
    def w(x=""):
        L.append(x)

    w("=" * 84)
    w("拿铁盾路线 · 逐步照走清单   PRIMARY=全局maxDEF, %d 步" % len(actions))
    w("=" * 84)
    w("来源 : shield_route_decision.json  (K=%s λ=%s 分坑=%s goal=%s 纯探索·未喂盾坐标)"
      % (cfg["beam_k"], cfg["lam"], cfg["diversity"], cfg["goal"]))
    w("起点 : %s(%d,%d)  HP%d ATK%d DEF%d   (越狱后首个自由态)"
      % (start["floor"], start["x"], start["y"], start["hp"], start["atk"], start["def"]))
    w("末态 : %s(%d,%d)  HP%d ATK%d DEF%d  kill=%d"
      % (end["floor"], end["x"], end["y"], end["hp"], end["atk"], end["def"], end["kill"]))
    w("裁判 : %s" % verdict)
    w("方向 : →右(R)  ←左(L)  ↑上(U)  ↓下(D)   换层=走到楼梯格自动触发，照方向走即可")
    w("")
    w("★关键速查★（步号=第几个动作，从第1个动作数起 1-based）")
    if shield and shield_row:
        gi, gk = shield_row[0], shield_row[4]
        full = shield.get("full_drop_if_at_start", 0)
        rem = shield.get("reduce_remaining", 0)
        pct = round(100 * rem / full) if full else 0
        w("  · 拿铁盾(+%dDEF): 第%d步 @%s ← 『亏点』：此前已杀%d只怪(全局·含序章%d)、HP掉到%d、ATK已%d、DEF仅%d"
          % (shield["delta"], gi, shield["cur_floor"],
             gk, start["kill"], shield["hp"], shield["atk"], shield["def_before"]))
        w("  · 盾对剩余未杀区怪减伤=%s；若开局即拿满额=%s；实得仅%d%%（约%s 价值因晚拿被浪费）"
          % ("{:,}".format(rem), "{:,}".format(full), pct, "{:,}".format(full - rem)))
    if sword:
        w("  · 拿铁剑(+10ATK): 第%d步 @%s" % (sword[0], sword[3]["floor"]))
    w("  · 全程: 换层 %d 次, 本路线杀怪 %d 只(起点已含序章 %d 只, 末态总 kill=%d)"
      % (n_floor, end["kill"] - start["kill"], start["kill"], end["kill"]))
    w("")

    # ── 一、里程碑总表（杀怪不进表，太多；在第二节逐步体现）──
    w("-" * 84)
    w("一、里程碑总表（换层 / 属性 / 拿盾 / 拿道具，按步号；纯移动+杀怪在第二节）")
    w("-" * 84)
    w("   步 |  层  | 事件 | 当刻 HP/ATK/DEF | 累计杀")
    for (i, tok, ev, after, k) in rows:
        for kind, txt in ev:
            if kind == "KILL":
                continue
            w(" %4d | %-4s | %s | %d/%d/%d | %d"
              % (i, after["floor"], txt, after["hp"], after["atk"], after["def"], k))
    w("")

    # ── 二、逐步动作序列（纯移动折叠，事件步单独高亮）──
    w("-" * 84)
    w("二、逐步动作序列（照走；事件步单独成行高亮，纯移动步折叠成方向串）")
    w("-" * 84)
    w("[起点] %s(%d,%d) HP%d/%d/%d"
      % (start["floor"], start["x"], start["y"], start["hp"], start["atk"], start["def"]))
    buf = []
    buf_start = [None]

    def flush():
        if not buf:
            return
        a = buf_start[0]
        b = a + len(buf) - 1
        rng = ("步%d" % a) if a == b else ("步%d–%d" % (a, b))
        w("  %-12s %s" % (rng + ":", " ".join(buf)))
        buf.clear()
        buf_start[0] = None

    for (i, tok, ev, after, k) in rows:
        if not ev:
            if buf_start[0] is None:
                buf_start[0] = i
            buf.append(ARROW.get(tok, tok))
            if len(buf) >= 30:
                flush()
            continue
        flush()
        detail = "   ".join(t for _, t in ev)
        w("  步%-5d %s   %s   [HP%d/%d/%d 杀%d]"
          % (i, ARROW.get(tok, tok), detail, after["hp"], after["atk"], after["def"], k))
    flush()
    w("[末态] %s(%d,%d) HP%d/%d/%d kill=%d"
      % (end["floor"], end["x"], end["y"], end["hp"], end["atk"], end["def"], end["kill"]))
    w("=" * 84)

    report = "\n".join(L)
    (OUT / "shield_walkthrough.txt").write_text(report, encoding="utf-8")
    print(report)
    print("\n[落盘] extract/shield_walkthrough.txt  (%d 步, %d 行)" % (len(actions), len(L)))


if __name__ == "__main__":
    main()
