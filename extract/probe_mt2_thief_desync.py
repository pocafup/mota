"""诊断 β=0.5 路线网站回放"挂在 MT2 小偷"的 token 错位 bug（红线：读源码不猜）。

玩家报告：beta05_mt10_route.h5route 在网站回放卡在 MT2 小偷(3,7)，疑似小偷对话算一个 token
导致后续全错。已知事实：mt10_bosspass(前缀 tokens[:1169] 含整个开局+小偷) 网站回放正常，
故"开局用玩家 token 过小偷"没问题 → 嫌疑落在 β 段是否把英雄带回 MT2 踩/撞 (3,7)，且 sim 与
网站对"开局后小偷是否已消失"是否一致。

本探针只读不改：
  1) 解码 beta05_mt10_route.h5route → spliced tokens（前缀 82 + β 段）。
  2) sim 干净起点逐 token 重放，记录每步 (floor,x,y)。
  3) 报告 token 82 边界态；列出整条路线所有【踏入或试图踏入 MT2(3,7)】的时刻、属于前缀还是 β 段。
  4) 打印开局走完(token82)后 sim 里 MT2 层 (3,7) 的地形/实体——小偷消失了没有。
跑法：python extract/probe_mt2_thief_desync.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from lzstring import LZString
from extract.decode_route import parse_rle_route
from extract.export_mt10_boss_route import make_initial_state, load_tokens
from sim.simulator import step, _copy_state, load_floor

OPENING_PREFIX = 83   # 82→83：MT2(1,9)小偷 hide 抑制修法后进 MT3 前缀多一步
THIEF = (3, 7)
DIR = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}


def load_spliced():
    f = next(ROOT.glob("beta05_mt10_route.h5route"))
    outer = __import__("json").loads(LZString().decompressFromBase64(f.read_text(encoding="utf-8").strip()))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def expand(tok):
    """把 'U3' 之类拆成 3 个单步动作；非移动 token 原样返回单元素。"""
    if tok and tok[0] in DIR and (len(tok) == 1 or tok[1:].isdigit()):
        return [tok[0]] * (int(tok[1:]) if len(tok) > 1 else 1)
    return [tok]


def main():
    spliced = load_spliced()
    units = []
    for i, t in enumerate(spliced):
        for u in expand(t):
            units.append((i, t, u))   # (原token索引, 原token, 单步)

    s = make_initial_state()
    traj = []                         # (unit_idx, orig_tok_idx, tok, unit, floor, x, y) 走之前
    thief_hits = []
    for ui, (ti, tok, u) in enumerate(units):
        before = (s.current_floor, s.hero.x, s.hero.y)
        # 若是方向单步，算出目标格，看是不是冲着 MT2(3,7)
        if u in DIR and s.current_floor == "MT2":
            nx, ny = s.hero.x + DIR[u][0], s.hero.y + DIR[u][1]
            if (nx, ny) == THIEF:
                thief_hits.append((ui, ti, tok, before, "瞄准(3,7)"))
        s = step(s, u)
        after = (s.current_floor, s.hero.x, s.hero.y)
        if before[0] == "MT2" or after[0] == "MT2":
            traj.append((ui, ti, tok, u, before, after))
        if after == ("MT2",) + THIEF:
            thief_hits.append((ui, ti, tok, after, "踏入(3,7)"))

    print("=" * 92)
    print(f"β=0.5 路线总 token={len(spliced)}  展开单步={len(units)}  前缀 OPENING_PREFIX={OPENING_PREFIX}")
    print("=" * 92)

    # token 82 边界：重放 prefix 看落点
    sp = make_initial_state()
    for t in spliced[:OPENING_PREFIX]:
        sp = step(sp, t)
    print(f"前缀末(token[:{OPENING_PREFIX}])落点: {sp.current_floor}({sp.hero.x},{sp.hero.y}) "
          f"HP={sp.hero.hp} ATK={sp.hero.atk} DEF={sp.hero.def_}")

    # 开局后 MT2(3,7) 实体状态：从 sp（已走完开局）里取 MT2 层
    mt2 = sp.floors.get("MT2")
    if mt2 is None:                  # 还没加载过就直接读盘看原始
        mt2 = load_floor(ROOT / "data" / "games51" / "floors" / "MT2.json")
        src = "（开局未驻留 MT2 层对象，读原始盘）"
    else:
        src = "（取自走完开局的活 state）"
    tx, ty = THIEF
    print(f"\n开局后 MT2 层 {src}：")
    print(f"  terrain[{ty}][{tx}] = {mt2.terrain[ty][tx]}   entities[{ty}][{tx}] = {mt2.entities[ty][tx]}")
    print(f"  (3,7) 在 _tile_to_entity? {mt2.entities[ty][tx] in mt2._tile_to_entity}   "
          f"events 含'3,7'? {'3,7' in mt2.events}")
    ev37 = mt2.events.get("3,7")
    if isinstance(ev37, dict):
        print(f"  events['3,7'] enable={ev37.get('enable')}")
    elif isinstance(ev37, list):
        print(f"  events['3,7'] 仍是活动列表事件（小偷未被移除/禁用）")

    print(f"\nβ 段(token idx≥{OPENING_PREFIX})是否重访 MT2(3,7)：")
    beta_hits = [h for h in thief_hits if h[1] >= OPENING_PREFIX]
    pre_hits = [h for h in thief_hits if h[1] < OPENING_PREFIX]
    print(f"  前缀内 (3,7) 触碰 {len(pre_hits)} 次；β 段内 (3,7) 触碰 {len(beta_hits)} 次")
    for h in thief_hits:
        seg = "前缀" if h[1] < OPENING_PREFIX else "β段"
        print(f"    [{seg}] unit#{h[0]} origTok#{h[1]}={h[2]!r} @ {h[3]} {h[4]}")

    print(f"\nMT2 相关轨迹片段（前 60 条）：")
    for rec in traj[:60]:
        ui, ti, tok, u, bef, aft = rec
        mark = "  ← (3,7)!" if aft == ("MT2",) + THIEF or bef == ("MT2",) + THIEF else ""
        print(f"  unit#{ui:>4} tok#{ti:>4}={tok:>5} 步{u}: {bef} → {aft}{mark}")


if __name__ == "__main__":
    main()
