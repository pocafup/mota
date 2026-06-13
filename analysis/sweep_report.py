"""【共享α 扫描·横向对比】只读·重放真引擎，把多条 α 的 crossbeam_floorbest jsonl 摆一起比三件事：
  ①爬升深度：最深到达层 + 该层 maxHP 态(hp/atk/def/步数)。
  ②剑盾顺序：sword_step / shield_step / 两件大件之间吃了几个小宝石（剑盾误判=盾被推到很后、中间扫一堆近宝石）。
  ③MT8门后谷：MT8 攻防宝石各是否在拾取线上（门后2攻防被抬起来没）。
不改产品码、不喂走法；行里已带 floor/hp/atk/def → 摘要无需重放，只重放【选中的最深那条】取拾取时序。

用法：python sweep_report.py <a1.jsonl> <a0.7.jsonl> ...   （文件名里的 _a{α} 自动当标签，无后缀=α1）
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from solver.beam import build_future_roster
from probe_crossfloor import build_start, _fidx
from vzone import build_zone
from vzone import _zone_attr_gems as _gems_of
from big_item_pull import detect_big_items
from export_beta_route_disease_audit import analyze, FAR
from export_k0stairs_mt10_route import fk
from region_route_disease_audit import dcounts, total_disease


def _alpha_of(name):
    m = re.search(r"_a([0-9.]+)", name)
    return m.group(1) if m else "1"


def pick_deepest_row(rows):
    """最深态：先最高层、再该层最高 HP（与 analyze_priorities.pick_deepest 同口径，但直读行不重放）。"""
    best = None
    for r in rows:
        key = (_fidx(r["floor"]), r["hp"])
        if best is None or key > best[0]:
            best = (key, r)
    return best[1]


def pickup_timeline(start, actions, watch):
    """步进重放，记录 watch 里每 cell 第一次 entities==0 的 step 与当时 HP/atk/def。"""
    s = _copy_state(start)
    taken = {}
    for i, a in enumerate(actions):
        s = step(s, a)
        for cell in watch:
            if cell in taken:
                continue
            fid, x, y = cell
            fl = s.floors.get(fid)
            if fl is not None and fl.entities[y][x] == 0:
                taken[cell] = (i, s.hero.hp, s.hero.atk, s.hero.def_)
    return taken


def main():
    files = [Path(a) for a in sys.argv[1:]]
    if not files:
        sys.exit("用法：python sweep_report.py <floorbest_a1.jsonl> <..a0.7..> ...")
    files = [f if f.is_absolute() else Path(__file__).parent / f.name for f in files]

    start, _ = build_start()
    roster = build_future_roster(start)
    zone = build_zone()
    big_cells, tau, ranked = detect_big_items(zone, roster, start)
    gems = _gems_of(zone)
    mt15_cells = frozenset(c for c in gems if fk(c[0]) in FAR)
    # 大件分剑/盾：atk 偏多=剑，def 偏多=盾
    bigs = sorted(big_cells, key=lambda c: -(gems[c][0] - gems[c][1]))
    sword = bigs[0] if bigs else None
    shield = bigs[-1] if len(bigs) > 1 else None
    mt8_gems = sorted(c for c in gems if c[0] == "MT8")

    print("=" * 100)
    print(f"大件 {len(big_cells)} 件 τ={tau:,.0f}   剑(atk重)={sword}+{gems[sword] if sword else '—'}   "
          f"盾(def重)={shield}+{gems[shield] if shield else '—'}")
    print(f"MT8 攻防宝石 {len(mt8_gems)} 件：" + "  ".join(f"{c}+atk{gems[c][0]}/def{gems[c][1]}" for c in mt8_gems))
    print("=" * 100)

    summary = []
    for f in files:
        a = _alpha_of(f.name)
        rows = [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        deepest_fidx = max(_fidx(r["floor"]) for r in rows)
        deepest_floor = next(r["floor"] for r in rows if _fidx(r["floor"]) == deepest_fidx)
        top = pick_deepest_row(rows)
        watch = [c for c in (sword, shield) if c] + mt8_gems
        taken = pickup_timeline(start, top["actions"], watch)

        sstep = taken.get(sword, [None])[0] if sword else None
        hstep = taken.get(shield, [None])[0] if shield else None
        # 剑盾之间吃的小宝石数（不含大件本身）
        between = 0
        if sstep is not None and hstep is not None and hstep > sstep:
            tt = pickup_timeline(start, top["actions"], list(gems.keys()))
            between = sum(1 for c, v in tt.items()
                          if c not in big_cells and sstep < v[0] < hstep)
        mt8_taken = [c for c in mt8_gems if c in taken]

        # ④规范四病审计（就近/剑后/早拿血/开门）——只对到 MT10 的路线（analyze 挑 best-MT10）
        o = analyze(a, zone, start, gems, mt15_cells, cut_fn=f)
        dc = dcounts(o)

        print(f"\n── α={a}  源 {f.name}")
        print(f"   ①爬升：最深层 {deepest_floor}  | 最深态 {top['floor']} "
              f"HP={top['hp']} ATK={top['atk']} DEF={top['def']} ({top['n_steps']}步)")
        print(f"   ②剑盾：剑@step{sstep}  盾@step{hstep}  中间小宝石={between}个"
              + ("  ⚠盾未拿" if hstep is None else "")
              + ("  ⚠剑未拿" if sstep is None else ""))
        print(f"   ③MT8门后：{len(mt8_taken)}/{len(mt8_gems)} 拿到 → "
              + ("  ".join(f"{c}@step{taken[c][0]}" for c in mt8_taken) if mt8_taken else "✗一件未拿(门后谷)"))
        if dc:
            print(f"   ④病合计={total_disease(dc)}（就近{dc['junk']}/剑后{dc['sword']}/早拿血{dc['heal']}/开门{dc['door']}）"
                  f"  best-MT10态 HP={dc['hp']}/{dc['atk']}/{dc['df']} 步{dc['steps']} 进MT9×{dc['n_mt9']}")
        else:
            print(f"   ④病合计=—（未到MT10，四病审计需 best-MT10 路线；看①②③代理指标）")
        summary.append((a, deepest_floor, top['hp'], top['atk'], top['def'],
                        sstep, hstep, between, len(mt8_taken), len(mt8_gems),
                        total_disease(dc) if dc else None))

    print("\n" + "=" * 100)
    print("【汇总表】")
    print(f"{'α':>5} {'最深层':>7} {'HP':>6} {'ATK':>5} {'DEF':>5} {'剑step':>7} {'盾step':>7} "
          f"{'中间宝石':>8} {'MT8门后':>8} {'病合计':>7}")
    for a, fl, hp, atk, df, ss, hs, bt, m8, m8t, dis in summary:
        print(f"{a:>5} {fl:>7} {hp:>6} {atk:>5} {df:>5} {str(ss):>7} {str(hs):>7} "
              f"{bt:>8} {f'{m8}/{m8t}':>8} {str(dis) if dis is not None else '—':>7}")
    print("=" * 100)


if __name__ == "__main__":
    main()
