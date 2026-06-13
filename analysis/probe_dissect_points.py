"""【只读·决策点解剖·第一步：定位】重放 beta_big25_lam0.2 best-MT10 路线，定位玩家点名的四个决策点
   (tok550/710/737/1011)，核对每点是不是【打骷髅士兵 / 开门不进 / MT9史莱姆 / MT4红史莱姆】，
   并厘清 tok 是【spliced(含83前缀)】还是【region 段】索引。纯诊断、不改产品码、不调参。

跑法：python -u extract/probe_dissect_points.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, DOOR_KEY_MAP, _build_monster
from vzone import build_zone
from probe_crossfloor import build_start, OPENING_PREFIX
from export_bscan_routes import load_rows, pick_best_mt10
from export_mt10_boss_route import load_tokens

HERE = Path(__file__).parent
SRC = HERE / "crossbeam_floorbest_K200_bb25_lam0.2_stairs.jsonl"
POINTS = [550, 710, 737, 1011]


def load_region_actions():
    start = build_start()[0]
    zone = build_zone()
    rows = load_rows(SRC)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    best_row, _s, _vz, _D = pick_best_mt10(zone, start, mt10)
    return start, list(best_row["actions"]), best_row


def cell_desc(state, x, y):
    """目标格 (x,y) 是什么：怪 mid / 道具 / 门(色) / 楼梯 / 空。"""
    fl = state.floor
    rows, cols = len(fl.terrain), len(fl.terrain[0])
    if not (0 <= x < cols and 0 <= y < rows):
        return "界外"
    e = fl.entities[y][x]
    mid = fl._tile_to_enemy.get(e)
    if mid is not None:
        return f"怪:{mid}"
    item = fl._tile_to_item.get(e)
    if item is not None:
        return f"道具:{item}"
    t = fl.terrain[y][x]
    if t in DOOR_KEY_MAP:
        return f"门:{DOOR_KEY_MAP[t]}"
    if f"{x},{y}" in fl.change_floor:
        return f"楼梯→{fl.change_floor[f'{x},{y}']}"
    return "空"


_DIR = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}


def _nkeys(h):
    return sum(v for k, v in h.keys.items() if v)


def replay_trace(start, actions):
    """逐步重放，返回每步 dict：i(1基), action, pre/post pos, hp/atk/def 及增量, 目标格描述, 钥匙增量。"""
    s = _copy_state(start)
    trace = []
    for i, a in enumerate(actions, 1):
        h0 = s.hero
        pre = (s.current_floor, h0.x, h0.y, h0.hp, h0.atk, h0.def_)
        nk0 = _nkeys(h0)
        tgt = None
        if a in _DIR:
            dx, dy = _DIR[a]
            tgt = cell_desc(s, h0.x + dx, h0.y + dy)
        s = step(s, a)
        h1 = s.hero
        trace.append(dict(i=i, a=a, floor=pre[0], x=pre[1], y=pre[2],
                          hp=pre[3], atk=pre[4], df=pre[5],
                          dhp=h1.hp - pre[3], datk=h1.atk - pre[4], ddef=h1.def_ - pre[5],
                          dkey=_nkeys(h1) - nk0,
                          post_floor=s.current_floor, post_x=h1.x, post_y=h1.y, tgt=tgt))
    return trace


def event_scan(trace):
    """全局事件扫描：列出所有战斗(目标=怪)、开门(钥匙减)、上下楼，供精确定位四病征。"""
    print("\n" + "=" * 100)
    print("全局事件扫描（region 步号）：所有战斗 / 开门 / 换层")
    print("=" * 100)
    print("【所有战斗（目标格=怪）】")
    print(f"{'region步':>8} {'层':>5} {'坐标':>9} {'怪':>20} {'ΔHP':>6} {'打完HP':>7}")
    for t in trace:
        if t["tgt"] and str(t["tgt"]).startswith("怪:"):
            print(f"{t['i']:>8} {t['floor']:>5} ({t['x']:>2},{t['y']:>2}) "
                  f"{t['tgt'][2:]:>20} {t['dhp']:>+6} {t['hp'] + t['dhp']:>7}")
    print("\n【所有开门（钥匙减少）】")
    print(f"{'region步':>8} {'层':>5} {'坐标':>9} {'目标门':>16} {'Δ钥匙':>6}")
    for t in trace:
        if t["dkey"] < 0:
            print(f"{t['i']:>8} {t['floor']:>5} ({t['x']:>2},{t['y']:>2}) "
                  f"{str(t['tgt']):>16} {t['dkey']:>+6}")


def window(trace, lo, hi, tag=""):
    print(f"\n── {tag} 窗口 region[{lo}..{hi}] ──")
    print(f"{'步':>5} {'层':>5} {'坐标':>9} {'动作':>4} {'目标格':>18} "
          f"{'HP':>5} {'ΔHP':>5} {'ATK':>4} {'DEF':>4} {'Δa/d':>7} {'Δ钥':>4}")
    for t in trace:
        if lo <= t["i"] <= hi:
            dd = f"{t['datk']:+d}/{t['ddef']:+d}" if (t["datk"] or t["ddef"]) else ""
            dk = f"{t['dkey']:+d}" if t["dkey"] else ""
            print(f"{t['i']:>5} {t['floor']:>5} ({t['x']:>2},{t['y']:>2}) {t['a']:>4} "
                  f"{str(t['tgt']):>18} {t['hp']:>5} {t['dhp']:>+5} {t['atk']:>4} {t['df']:>4} "
                  f"{dd:>7} {dk:>4}")


def main():
    start, region_actions, best_row = load_region_actions()
    n_region = len(region_actions)
    prefix = load_tokens()[:OPENING_PREFIX]
    print("=" * 100)
    print(f"beta_big25 best-MT10 路线：region 段 {n_region} 步；spliced = 前缀 {len(prefix)} + region "
          f"= {len(prefix) + n_region} token")
    print(f"末态(源行)：{best_row['floor']} HP={best_row['hp']} ATK={best_row['atk']} DEF={best_row['def']}")
    print("=" * 100)

    trace = replay_trace(start, region_actions)
    # 末态核对
    last = trace[-1]
    print(f"重放末态：{last['post_floor']}({last['post_x']},{last['post_y']}) "
          f"HP={last['hp'] + last['dhp']} （应 = 源行 HP={best_row['hp']}）")

    # 已确认 tok = spliced 索引（含 83 前缀）→ region 步号 = tok − 83。四点各开宽窗口看决策上下文。
    off = len(prefix)
    for tk in POINTS:
        reg = tk - off
        print("\n" + "#" * 100)
        print(f"# tok={tk}（spliced）→ region 步 {reg}")
        print("#" * 100)
        window(trace, reg - 8, reg + 10, tag=f"tok={tk}=region步{reg}")

    event_scan(trace)


if __name__ == "__main__":
    main()
