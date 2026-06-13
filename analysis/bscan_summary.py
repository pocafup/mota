"""【只读·只分析】β 扫汇总：逐 β 读 cut 文件，按玩家五问输出（全部代码算，绝不手推）。

固定配置：--score vzone --beam 50 --diversity stairs（κ=0 能到 MT10 那套），只变 β。
五问：
  Q1 到顶层 + 全局 maxATK/maxDEF（β 增大有没有爬更高、攻防齐涨）；
  Q2 拿铁剑(MT5,+ATK)/铁盾(MT9,+DEF)了吗、第几步拿（封板 replay best-MT10 路线追踪宝石格）；
  Q3 复发刷分否（看到 MT10 vs 卡低层、攻防是否真涨——对照 κ=0 到 MT10/26/25，κ=1 退回 MT9）；
  Q4 血够否（best-MT10 入层 HP；boss 战 toll vs HP 余量，标注为上界=未扣走到 boss 格路费）；
  Q5 真过 boss 否（队长可杀阈值 atk>boss.def + HP 余量 > boss_toll；甜区再做封板打到胜利终审）。

铁律：动作串=cut 落盘 RULD 原样照走；宝石/boss 归因到 data 真读格(_zone_attr_gems/boss_mon)。
跑法：python -u extract/bscan_summary.py
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
from solver.verify import replay
from vzone import build_zone, boss_toll, _zone_attr_gems
from probe_crossfloor import build_start

HERE = Path(__file__).parent
BETAS = [0, 0.5, 1, 2, 4, 8]


def fk(fid):
    try:
        return int(fid[2:])
    except Exception:
        return -1


def cut_path(beta):
    tag = f"_b{beta:g}" if beta else ""
    return HERE / f"crossbeam_cut_K50_vzone{tag}_lam0.0_stairs.jsonl"


def load_rows(fn):
    rows = []
    with open(fn, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue                 # 跳过流式写入中的残行（后台正在跑的 cut 文件尾行）
    return rows


def taken_attr_gems(start, actions, gems):
    """封板 replay best-MT10 动作串，追踪【踏上且属性真涨】的攻防宝石格。返回 {cell:(da,dd,step_i)}。"""
    s = _copy_state(start)
    prev_atk, prev_def = s.hero.atk, s.hero.def_
    taken = {}
    for i, a in enumerate(actions, 1):
        s = step(s, a)
        cell = (s.current_floor, s.hero.x, s.hero.y)
        if cell in gems and (s.hero.atk > prev_atk or s.hero.def_ > prev_def):
            da, dd = gems[cell]
            taken[cell] = (da, dd, i)
        prev_atk, prev_def = s.hero.atk, s.hero.def_
    return taken, s


def analyze(beta, zone, start, gems, boss):
    fn = cut_path(beta)
    if not fn.exists():
        return None
    rows = load_rows(fn)
    if not rows:
        return dict(beta=beta, empty=True)
    top_floor = max(rows, key=lambda r: fk(r["floor"]))["floor"]
    gmax_atk = max(r["atk"] for r in rows)
    gmax_def = max(r["def"] for r in rows)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    out = dict(beta=beta, n_rows=len(rows), top_floor=top_floor,
               gmax_atk=gmax_atk, gmax_def=gmax_def, reached_mt10=bool(mt10))
    if not mt10:
        return out
    # 玩家口径 best-MT10：(def↓, atk↓, hp↓)
    best = max(mt10, key=lambda r: (r["def"], r["atk"], r["hp"]))
    out["best"] = dict(hp=best["hp"], atk=best["atk"], def_=best["def"],
                       mdef=best.get("mdef", 0), steps=len(best["actions"]))
    # 封板 replay 对账 + 宝石追踪
    actions = list(best["actions"])
    taken, term = taken_attr_gems(start, actions, gems)
    rs = replay(start, actions, step, _copy_state)
    out["fidelity_ok"] = (rs.current_floor == best["floor"] and rs.hero.hp == best["hp"]
                          and rs.hero.atk == best["atk"] and rs.hero.def_ == best["def"])
    iron_sword = [(c, v) for c, v in taken.items() if c[0] == "MT5" and v[0] >= 10]
    iron_shield = [(c, v) for c, v in taken.items() if c[0] == "MT9" and v[1] >= 10]
    out["iron_sword"] = iron_sword[0] if iron_sword else None
    out["iron_shield"] = iron_shield[0] if iron_shield else None
    out["n_gems"] = len(taken)
    out["gem_datk"] = sum(v[0] for v in taken.values())
    out["gem_ddef"] = sum(v[1] for v in taken.values())
    # boss：队长可杀阈值 + toll vs HP 余量（余量为上界：未扣 best-MT10 入层格→boss 格的路费）
    bdef = boss.def_ if boss is not None else None
    toll = boss_toll(zone, best["atk"], best["def"], best.get("mdef", 0))
    out["boss_def"] = bdef
    out["boss_killable"] = (bdef is not None and best["atk"] > bdef)
    out["boss_toll"] = toll
    out["boss_margin"] = best["hp"] - toll
    return out


def fmt(o):
    if o is None:
        return None
    b = o["beta"]
    if o.get("empty"):
        return f"β={b:<4g} cut 文件空"
    L = [f"β={b:<4g} 行数={o['n_rows']:,}  到顶层={o['top_floor']}  "
         f"全局 maxATK={o['gmax_atk']} maxDEF={o['gmax_def']}  到MT10={'是' if o['reached_mt10'] else '否'}"]
    if not o["reached_mt10"]:
        L.append("    └ 未到 boss 层 MT10")
        return "\n".join(L)
    be = o["best"]
    L.append(f"    best-MT10: HP={be['hp']} ATK={be['atk']} DEF={be['def_']} mdef={be['mdef']} "
             f"({be['steps']}步)  封板对账={'✅一致' if o['fidelity_ok'] else '❌偏离'}")
    isw = o["iron_sword"]; ish = o["iron_shield"]
    L.append(f"    铁剑(MT5+ATK)={'第%d步@%s拿(+%dATK)' % (isw[1][2], isw[0][1:], isw[1][0]) if isw else '未拿'}  "
             f"铁盾(MT9+DEF)={'第%d步@%s拿(+%dDEF)' % (ish[1][2], ish[0][1:], ish[1][1]) if ish else '未拿'}")
    L.append(f"    拿到攻防宝石共 {o['n_gems']} 个（Δatk+{o['gem_datk']} / Δdef+{o['gem_ddef']}）")
    L.append(f"    boss队长 def={o['boss_def']} 可杀={'是(atk>def)' if o['boss_killable'] else '否(打不动)'}  "
             f"boss战toll={o['boss_toll']}  HP余量(上界)={o['boss_margin']}"
             f"  → {'有望过(余量>0,待封板打到胜利终审)' if o['boss_killable'] and o['boss_margin'] > 0 else '过不了(余量≤0或打不动)'}")
    return "\n".join(L)


def main():
    zone = build_zone()
    start, _ = build_start()
    gems = _zone_attr_gems(zone)
    boss = zone["boss_mon"]
    print("=" * 96)
    print(f"β 扫汇总（固定 --score vzone --beam 50 --diversity stairs，只变 β）  "
          f"boss队长 hp={boss.hp}/atk={boss.atk}/def={boss.def_}" if boss else "β 扫汇总")
    print("=" * 96)
    results = []
    for b in BETAS:
        o = analyze(b, zone, start, gems, boss)
        results.append(o)
        s = fmt(o)
        if s is None:
            print(f"β={b:<4g} （cut 文件不存在，未跑）")
        else:
            print(s)
        print("-" * 96)
    # 紧凑对照表
    print("对照表（β ↑ 是否爬更高/攻防齐涨/拿剑盾/过boss）：")
    print(f"{'β':>5} {'顶层':>5} {'maxATK':>7} {'maxDEF':>7} {'best-MT10 hp/atk/def':>22} "
          f"{'铁剑':>4} {'铁盾':>4} {'boss余量':>9}")
    for o in results:
        if o is None or o.get("empty") or not o.get("reached_mt10"):
            tf = o["top_floor"] if (o and not o.get("empty")) else "—"
            ma = o["gmax_atk"] if (o and not o.get("empty")) else "—"
            md = o["gmax_def"] if (o and not o.get("empty")) else "—"
            print(f"{o['beta'] if o else '—':>5} {tf:>5} {ma:>7} {md:>7} {'(未到MT10)':>22}")
            continue
        be = o["best"]
        triple = f"{be['hp']}/{be['atk']}/{be['def_']}"
        print(f"{o['beta']:>5g} {o['top_floor']:>5} {o['gmax_atk']:>7} {o['gmax_def']:>7} "
              f"{triple:>22} "
              f"{'✓' if o['iron_sword'] else '✗':>4} {'✓' if o['iron_shield'] else '✗':>4} "
              f"{o['boss_margin']:>9}")


if __name__ == "__main__":
    main()
