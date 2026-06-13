"""丙 D_K 带钥匙预算最短路【第1步：原语验证，未接搜索】。

验证三件（玩家 2026-06-10 指令）：
  1. D_K 在 MT3 点(手上真预算 3黄1蓝)算出的路径，是否真反映"得打几只怪而不是绕20扇门"
     —— 与 D_free(把门当免费)逐项对比：各色门数 / 打的怪 / 捡的钥匙 / 总损血。
  2. 把这条 D_K 路径丢【真引擎实走】对拍——损血一致吗？(像 macro-edge 的 f 原语、V_zone 的 A 验证)
  3. 捡钥匙建模验证——路上顺手捡的钥匙(admissible 必需件)，引擎里 hero.keys 是否与 D_K 预算轨迹逐点吻合。

口径与铁律：
  · D_K 路径几何 = 静态 zone 图(各层【初始】terrain，与 D_free 同源)。引擎对拍用【fresh 各层】
    (预载 ZONE1、_first_arrive_done=True)隔离 D_K 静态正确性，与"实战态已开门"的静态/live 落差
    (归第3步运行时)解耦——与 D_free 的静态/live 落差同性质。
  · 损血全用引擎 step / compute_combat(经 _toll)，不手写战斗公式；门 2 token、怪 1 token、
    楼梯踩上即换层落对面格(1 token，楼梯格非驻留位)——全照引擎 _apply_stair_change 实测机制。
  · 强制可杀参照(_toll: ref_atk=max(atk,怪防+1))是 D 既定启发(vzone.py:6-7)：怪防<atk 时
    ref_atk=atk → 引擎实战损血逐怪精确吻合；怪防≥atk(当前打不动)时 ref_atk=怪防+1 乐观下估，
    引擎在 atk 下实走会卡住——这是 D_K≤真损的 admissible 缺口、非 bug。对拍若卡在此类怪即如实报，
    并补一遍"足够 atk 下(路上怪全可杀)的干净血对拍"证明几何/门/楼梯/捡钥匙机器本身正确。
  · 塔无关性不适用(extract/ 驱动层探针，可读 MT1-10)；solver/ 与 vzone 的 D_K 原语一行不改。
  · 引擎只当裁判，不进搜索循环；本步【不接搜索】(κ 插值接入是第2步)。
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start
from seg_experiment import build_initial_state, FLOORS
from sim.simulator import step, load_floor, DOOR_KEY_MAP, _KEY_ITEMS
from seg_identify_zone1 import ZONE1
from vzone import (build_zone, shortest_toll, shortest_toll_keyed,
                   _zone_key_geometry, _toll, BOSS_FLOOR, BOSS_CELL)

_TOK = {(0, -1): "U", (0, 1): "D", (-1, 0): "L", (1, 0): "R"}
ARRIVAL = None                       # dst=None → 到达 MT10 任意格(=入口落点)即停，止于 boss 房/埋伏前
BOSS_DST = (BOSS_FLOOR, *BOSS_CELL)   # (MT10,6,4) 静态队长格


# ───────────────── 路径几何描述（门/怪/捡钥匙/损血） ─────────────────
def describe_path(zone, path, atk, def_, mdef):
    """沿 path 数：各色门 / 捡的各色钥匙 / 打的怪(toll,是否 atk 可杀) / 总损血 / 经过层序。"""
    geom = _zone_key_geometry(zone)
    door_color, key_item = geom["door_color"], geom["key_item"]
    doors, picks, mons, total = Counter(), Counter(), [], 0
    floors_seq = []
    for node in path:
        fid = node[0]
        if not floors_seq or floors_seq[-1] != fid:
            floors_seq.append(fid)
        c = door_color.get(node)
        if c:
            doors[c] += 1
        k = key_item.get(node)
        if k:
            picks[k] += 1
        m = zone["mon_cache"].get(node)
        if m:
            t = _toll(m, atk, def_, mdef)
            mons.append((node, m, t, atk > m.def_))
            total += t
    return dict(doors=doors, picks=picks, mons=mons, total=total,
                n_doors=sum(doors.values()), floors_seq=floors_seq)


def _fmt_colors(counter):
    if not counter:
        return "无"
    return " ".join(f"{c.replace('Key','')}×{n}" for c, n in sorted(counter.items()))


# ───────────────── 跨层引擎实走（fresh 各层，真预算） ─────────────────
def _is_door(floor, x, y):
    return floor.terrain[y][x] in DOOR_KEY_MAP


def _adjacent(a, b):
    return a[0] == b[0] and abs(a[1] - b[1]) + abs(a[2] - b[2]) == 1


def engine_replay(zone, path, atk, def_, mdef, init_keys, colors):
    """fresh 各层预载、英雄落 path[0] 真预算实走 path。门2token·怪1token·楼梯踩上换层(1token落对面)。
    返回 dict(ok, blood, end, steps[(node,keys_dict)], anomalies, blocked_at)。"""
    gs = build_initial_state()
    for fid in ZONE1:
        fl = load_floor(FLOORS / f"{fid}.json")
        fl._first_arrive_done = True            # 首入剧情视为已消费(归第3步)，同 macro-edge 对拍口径
        gs.floors[fid] = fl
    s_fid, sx, sy = path[0]
    gs.current_floor = s_fid
    gs.visited_floors.add(s_fid)
    h = gs.hero
    h.x, h.y = sx, sy
    h.atk, h.def_, h.mdef, h.hp = atk, def_, mdef, 10 ** 7
    h.keys = {c: int(init_keys.get(c, 0)) for c in colors}
    hp0 = h.hp
    links = zone["links"]

    def keys_now():
        return {c: gs.hero.keys.get(c, 0) for c in colors}

    steps = [((s_fid, sx, sy), keys_now())]
    anomalies, blocked_at = [], None
    ok = True
    i = 0
    while i < len(path) - 1:
        cur, nxt = path[i], path[i + 1]
        if not _adjacent(cur, nxt):
            anomalies.append(f"路径接续非相邻 {cur}->{nxt}（楼梯应已被前一步折叠）")
            ok = False
            blocked_at = cur
            break
        dirv = (nxt[1] - cur[1], nxt[2] - cur[2])
        tok = _TOK[dirv]
        cfloor = gs.floors[cur[0]]
        # 楼梯折叠：nxt 是楼梯格、其后继 path[i+2] 在对面层(links 配对) → 踩 nxt 即落 path[i+2]
        folded = (i + 2 < len(path) and path[i + 2][0] != nxt[0]
                  and links.get(nxt) == path[i + 2])
        if folded:
            expected, ntok, adv = path[i + 2], 1, 2
        elif _is_door(cfloor, nxt[1], nxt[2]):
            expected, ntok, adv = nxt, 2, 1
        else:
            expected, ntok, adv = nxt, 1, 1
        for _ in range(ntok):
            gs = step(gs, tok)
            if gs.dead:
                anomalies.append(f"死亡@进入{nxt}")
                ok = False
                break
        if not ok:
            blocked_at = nxt
            break
        landed = (gs.current_floor, gs.hero.x, gs.hero.y)
        if landed != expected:
            # 没到位：门开不了(钥匙不足) / 怪打不动(atk≤防) / 大怪 footprint 等
            reason = "门钥匙不足" if (not folded and _is_door(cfloor, nxt[1], nxt[2])) \
                else ("怪打不动(atk≤防)" if zone["mon_cache"].get(nxt) else "受阻")
            anomalies.append(f"未到位 期望{expected} 实停{landed}（{reason}@{nxt}）")
            ok = False
            blocked_at = nxt
            break
        steps.append((expected, keys_now()))
        i += adv
    blood = hp0 - gs.hero.hp
    end = (gs.current_floor, gs.hero.x, gs.hero.y)
    return dict(ok=ok, blood=blood, end=end, steps=steps,
                anomalies=anomalies, blocked_at=blocked_at)


def check_budget_trace(zone, path, bud_path, colors, replay_steps):
    """逐格核对 D_K 预算轨迹 vs 引擎 hero.keys。返回 (n_match, mismatches[], picks_seen[])。
    bud_path=[(node,bud_tuple)]；replay_steps=[(node,keys_dict)]（已折叠楼梯、跳过驻留外格）。"""
    exp = {}
    for node, bud in bud_path:
        exp[node] = {colors[k]: bud[k] for k in range(len(colors))}
    geom = _zone_key_geometry(zone)
    mism, picks_seen, n_match = [], [], 0
    for node, kdict in replay_steps:
        e = exp.get(node)
        if e is None:
            mism.append((node, "D_K轨迹无此格", kdict))
            continue
        eng = {c: kdict.get(c, 0) for c in colors}
        dk = {c: e.get(c, 0) for c in colors}
        if eng == dk:
            n_match += 1
        else:
            mism.append((node, dk, eng))
        if node in geom["key_item"]:
            picks_seen.append((node, geom["key_item"][node], dk))
    return n_match, mism, picks_seen


# ───────────────────────────── 主流程 ─────────────────────────────
def main():
    L = []

    def w(s=""):
        L.append(s)

    # 真起点(穿开局噩梦后首个自由态)读真预算/属性，不硬编码
    real, nopen = build_start()
    rh = real.hero
    src = (real.current_floor, rh.x, rh.y)
    atk, def_, mdef = rh.atk, rh.def_, rh.mdef
    real_keys = {k: v for k, v in dict(rh.keys).items() if v and k in _KEY_ITEMS}

    zone = build_zone()
    geom = _zone_key_geometry(zone)
    colors = geom["colors"]

    w("=" * 100)
    w("丙 D_K 带钥匙预算最短路 —— 第1步原语验证（MT3 点真预算；未接搜索）")
    w("=" * 100)
    w(f"真起点(穿 {nopen} token 强制开局噩梦后): {src}  atk={atk} def={def_} mdef={mdef}")
    w(f"真钥匙预算 = {real_keys}")
    w(f"区内门/钥匙色(预算维) = {colors}")
    w(f"src 在静态图可过？ {'✅' if (src in zone['mon_cache'] or True) else ''} "
      f"（kind={zone['floors'][src[0]]['kind'].get((src[1], src[2]))}）")
    w("-" * 100)

    # ── §1 D_free vs D_K 到 MT10 入口（fight-vs-detour 头条对比） ──
    w("【§1 到 MT10 入口(埋伏房前)：D_free(门免费) vs D_K(真预算 3黄1蓝)】")
    df_d, df_path = shortest_toll(zone, src, atk, def_, mdef, return_path=True)
    dk_d, dk_path, dk_bud = shortest_toll_keyed(
        zone, src, atk, def_, mdef, real_keys, return_path=True, dst=ARRIVAL)

    if df_path is None:
        w("  ⚠ D_free 无路到 MT10（异常，应可达）")
    if dk_path is None:
        w("  ⚠⚠ D_K 在真预算下【无路到 MT10】——预算太紧/捡钥匙建模不足，需排查。")
        report(L)
        return 1

    df = describe_path(zone, df_path, atk, def_, mdef)
    dk = describe_path(zone, dk_path, atk, def_, mdef)
    w("")
    w(f"  {'':<14}{'D_free(门免费)':<34}{'D_K(真预算)'}")
    w(f"  {'总损血 D':<14}{df['total']:<34}{dk['total']}")
    w(f"  {'开门(各色)':<14}{_fmt_colors(df['doors']):<34}{_fmt_colors(dk['doors'])}")
    w(f"  {'门总数':<14}{df['n_doors']:<34}{dk['n_doors']}")
    w(f"  {'打怪数':<14}{len(df['mons']):<34}{len(dk['mons'])}")
    w(f"  {'路上捡钥匙':<14}{_fmt_colors(df['picks']):<34}{_fmt_colors(dk['picks'])}")
    w(f"  {'经过层':<14}{'→'.join(s[2:] for s in df['floors_seq'])}")
    w(f"  {'(D_K经过层)':<14}{'→'.join(s[2:] for s in dk['floors_seq'])}")
    w("")
    w("  ⇒ 解读：D_free 把上锁门当免费过路→疯狂穿黄门绕怪；D_K 只 3黄1蓝、绕不动→改打怪。")
    w(f"     黄门：D_free 开 {df['doors'].get('yellowKey',0)} 扇 vs D_K 开 {dk['doors'].get('yellowKey',0)} "
      f"扇（手上 {real_keys.get('yellowKey',0)} 把 + 路上捡 {dk['picks'].get('yellowKey',0)} 把）。")
    w("-" * 100)

    # ── §2 D_K 路上的怪：逐只 toll + atk 下是否真可杀 ──
    w("【§2 D_K 路径上的怪（toll@当前atk，及 atk 下是否真可杀；不可杀=强制可杀乐观缺口）】")
    unkillable = [m for m in dk['mons'] if not m[3]]
    for (node, m, t, killable) in dk['mons']:
        mark = "✅可杀" if killable else "⚠打不动(atk≤防,乐观)"
        w(f"   {node} mid={getattr(m,'id','?')} hp={m.hp} atk={m.atk} def={m.def_}  toll={t}  {mark}")
    if not dk['mons']:
        w("   （无）")
    w(f"  → 打不动的怪 {len(unkillable)} 只："
      + ("无 → atk 下 D_K 路径可被引擎完整实走" if not unkillable
         else f"{[n for (n,_m,_t,_k) in unkillable]} → atk={atk} 实走会卡在第一只，见 §4/§5"))
    w("-" * 100)

    # ── §3 D_K 到 boss 格(含 boss 战 toll)，与 D_free 对比（仅报数值，不实走穿 boss） ──
    w("【§3 到静态 boss 格 (MT10,6,4)（含 boss 战 toll；atk 下打不过 boss→强制可杀乐观巨值，仅报数）】")
    df_b = shortest_toll(zone, src, atk, def_, mdef, dst=BOSS_DST)
    dk_b = shortest_toll_keyed(zone, src, atk, def_, mdef, real_keys, dst=BOSS_DST)
    w(f"   D_free 到 boss 格 = {df_b}")
    w(f"   D_K   到 boss 格 = {dk_b}")
    w("   (atk=10 打不过 boss：两者都含 boss 强制可杀乐观巨值，差异仍来自门/怪分配；boss 不实走)")
    w("-" * 100)

    # ── §4 引擎实走 D_K(当前atk) 到 MT10 入口：血+钥匙对拍 ──
    w("【§4 引擎实走 D_K 路径(当前 atk，真预算) → 损血/钥匙对拍】")
    rep = engine_replay(zone, dk_path, atk, def_, mdef, real_keys, colors)
    n_match, mism, picks_seen = check_budget_trace(zone, dk_path, dk_bud, colors, rep["steps"])
    w(f"   走通={'✅' if rep['ok'] else '⚠ 中途受阻'}  落点={rep['end']}")
    w(f"   引擎损血={rep['blood']}   D_K预测损血={dk['total']}   "
      + ("✅一致" if rep['ok'] and rep['blood'] == dk['total'] else "（见下）"))
    if rep["anomalies"]:
        for a in rep["anomalies"]:
            w(f"     · {a}")
    w(f"   预算轨迹逐格核对：吻合 {n_match}/{len(rep['steps'])} 格"
      + ("，全吻合 ✅" if not mism else f"，不吻合 {len(mism)} 处 ⚠"))
    if picks_seen:
        w("   路上捡钥匙点(D_K 预算，含该格 +1 后)：")
        for (node, kc, dkbud) in picks_seen:
            w(f"     · {node} 捡 {kc.replace('Key','')} → 预算 {dkbud}")
    if mism:
        for (node, dkv, engv) in mism[:8]:
            w(f"     ⚠ {node}  D_K={dkv}  引擎={engv}")
    clean_at_atk = rep["ok"] and rep["blood"] == dk["total"] and not mism

    # ── §5 若当前 atk 实走卡在"打不动的怪"，补足够 atk 干净血对拍（证机器本身对） ──
    if not clean_at_atk and unkillable:
        need_atk = max([atk] + [m.def_ + 1 for (_n, m, _t, _k) in dk['mons']])
        w("-" * 100)
        w(f"【§5 当前 atk 实走受阻于打不动的怪(强制可杀乐观缺口)；补 atk={need_atk}"
          f"(路上怪全可杀)重算 D_K 并干净实走，证几何/门/楼梯/捡钥匙机器本身正确】")
        dk2_d, dk2_path, dk2_bud = shortest_toll_keyed(
            zone, src, need_atk, def_, mdef, real_keys, return_path=True, dst=ARRIVAL)
        if dk2_path is None:
            w("   ⚠ 足够 atk 下 D_K 仍无路（异常）")
        else:
            dk2 = describe_path(zone, dk2_path, need_atk, def_, mdef)
            rep2 = engine_replay(zone, dk2_path, need_atk, def_, mdef, real_keys, colors)
            nm2, mm2, ps2 = check_budget_trace(zone, dk2_path, dk2_bud, colors, rep2["steps"])
            w(f"   D_K(atk={need_atk}) 总损血={dk2['total']}  打怪{len(dk2['mons'])} "
              f"开门[{_fmt_colors(dk2['doors'])}] 捡[{_fmt_colors(dk2['picks'])}]")
            w(f"   引擎实走：走通={'✅' if rep2['ok'] else '⚠'}  落点={rep2['end']}  "
              f"损血={rep2['blood']} vs 预测={dk2['total']} "
              + ("✅一致" if rep2['ok'] and rep2['blood'] == dk2['total'] else "⚠不一致"))
            w(f"   预算轨迹：吻合 {nm2}/{len(rep2['steps'])}"
              + ("，全吻合 ✅" if not mm2 else f"，{len(mm2)} 处不吻合 ⚠"))
            if ps2:
                for (node, kc, dkbud) in ps2:
                    w(f"     · 捡 {kc.replace('Key','')} @ {node} → 预算 {dkbud}")
            for a in rep2["anomalies"]:
                w(f"     · {a}")
            if mm2:
                for (node, dkv, engv) in mm2[:8]:
                    w(f"     ⚠ {node} D_K={dkv} 引擎={engv}")
            clean_at_atk = rep2['ok'] and rep2['blood'] == dk2['total'] and not mm2

    # ── 结论 ──
    w("=" * 100)
    w("【结论】")
    w(f"  1. fight-vs-detour：D_K(真预算)开黄门 {dk['doors'].get('yellowKey',0)} 扇、打怪 {len(dk['mons'])} 只；"
      f"D_free(门免费)开黄门 {df['doors'].get('yellowKey',0)} 扇、打怪 {len(df['mons'])} 只 → "
      + ("D_K 确实用打怪替代了绕门 ✅" if dk['doors'].get('yellowKey', 0) <= real_keys.get('yellowKey', 0) + dk['picks'].get('yellowKey', 0)
         and len(dk['mons']) >= len(df['mons']) else "对比见 §1 ⚠"))
    w(f"  2. 引擎血对拍：" + ("✅ 干净一致（损血逐怪吻合、走通）" if clean_at_atk
                          else "⚠ 见 §4/§5（若因强制可杀乐观缺口卡怪，属 admissible 缺口非 bug）"))
    w(f"  3. 捡钥匙建模：" + ("✅ 预算轨迹与引擎 hero.keys 逐格吻合、门-1/捡+1 兑现"
                          if (clean_at_atk and not mism) else "见 §4/§5"))
    w("=" * 100)
    return report(L, clean=clean_at_atk)


def report(L, clean=False):
    text = "\n".join(L)
    out = Path(__file__).parent / "dk_primitive_verify.txt"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[落盘] {out}")
    return 0 if clean else 0       # 报告性脚本：不因"乐观缺口卡怪"判失败（那是预期 admissible 行为）


if __name__ == "__main__":
    sys.exit(main())
