"""【只导出·只读】把 κ=0+stairs 搜索到 MT10 的"最好那条"(maxDEF=25/maxATK=26)逐里程碑导出。

铁律遵循：
  · 不改 sim/solver；纯 replay + data 取数。动作串=cut 文件里搜索落盘的 RULD，原样照走。
  · 每个事件归因到【data 真读的格子】：怪=mon_cache、攻防宝石/铁剑铁盾=_zone_attr_gems、
    钥匙/门=状态里钥匙增减(增=拿钥、减=开门)，绝不手推。
  · 引擎封板重放：把整串动作从干净起点 replay 一遍，终态逐字段对账 cut 日志行。

跑法：python -u extract/export_k0stairs_mt10_route.py
产物：extract/mt10_best_route_k0stairs.md
"""
import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, _DIR
from solver.verify import replay
from vzone import build_zone, boss_toll, _zone_attr_gems
from probe_crossfloor import build_start

CUT = Path(__file__).parent / "crossbeam_cut_K50_vzone_lam0.0_stairs.jsonl"
OUT = Path(__file__).parent / "mt10_best_route_k0stairs.md"


def fk(fid):
    try:
        return int(fid[2:])
    except Exception:
        return -1


def load_rows(fn):
    rows = []
    with open(fn, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def nz_keys(hero):
    return {k: v for k, v in hero.keys.items() if v}


def snap(s):
    h = s.hero
    return dict(floor=s.current_floor, x=h.x, y=h.y, hp=h.hp, atk=h.atk,
               def_=h.def_, mdef=h.mdef, gold=h.gold, keys=nz_keys(h))


def gem_label(da, dd):
    parts = []
    if da:
        parts.append("铁剑+%dATK" % da if da >= 10 else "攻击宝石+%dATK" % da)
    if dd:
        parts.append("铁盾+%dDEF" % dd if dd >= 10 else "防御宝石+%dDEF" % dd)
    return "/".join(parts)


def key_delta_label(before, after):
    """钥匙增减 → (拿钥串, 开门串)。"""
    got, spent = [], []
    allk = set(before) | set(after)
    for k in sorted(allk):
        d = after.get(k, 0) - before.get(k, 0)
        if d > 0:
            got.append(f"{k}×{d}")
        elif d < 0:
            spent.append(f"{k}×{-d}")
    return got, spent


def build_milestones(start, actions, zone, gems):
    """逐步 replay，归因事件。返回 (snaps_per_step, milestones, visited_cells, taken_gems)。"""
    s = _copy_state(start)
    cur = snap(s)
    milestones = [dict(i=0, label="起点（开局噩梦后首个自由态 MT3 入口）", **cur)]
    visited = {(cur["floor"], cur["x"], cur["y"])}
    taken_gems = {}                              # cell -> (da,dd)
    mon = zone["mon_cache"]
    for i, a in enumerate(actions, 1):
        before = cur
        # 战斗归因：本步动作指向的目标格若【当下还活着】怪 → 打的就是它
        # （用 live 楼层取数，排除走回已清空怪格被误标"损血0 打怪"的假事件）
        dx, dy = _DIR[a]
        bx, by = before["x"] + dx, before["y"] + dy
        tgt = (before["floor"], bx, by)
        pf = s.floor
        ent = getattr(pf, "entities", None)
        live_mon = (ent is not None and 0 <= by < len(ent) and 0 <= bx < len(ent[by])
                    and pf._tile_to_enemy.get(ent[by][bx]) is not None)
        s = step(s, a)
        cur = snap(s)
        cell = (cur["floor"], cur["x"], cur["y"])
        visited.add(cell)
        labels = []
        # 换层
        if cur["floor"] != before["floor"]:
            labels.append(f"换层 {before['floor']}→{cur['floor']}")
        # 打怪（目标格当下有活怪；损血=战斗扣血）
        if live_mon:
            tmon = mon.get(tgt)
            dmg = before["hp"] - cur["hp"]
            if tmon is not None:
                sp = f" special{tmon.special}" if tmon.special else ""
                labels.append(f"打怪 {tmon.name}(id{tmon.id} hp{tmon.hp}/atk{tmon.atk}/def{tmon.def_}{sp})"
                              f" 损血{dmg}")
            else:
                labels.append(f"打怪(损血{dmg})")
        # 拿攻防宝石/铁剑铁盾（踏上的格在宝石表 + 属性真涨）
        if cell in gems and (cur["atk"] > before["atk"] or cur["def_"] > before["def_"]):
            da, dd = gems[cell]
            taken_gems[cell] = (da, dd)
            labels.append("拿" + gem_label(da, dd) + f" @{cell[1:]} ")
        # 回血
        if cur["hp"] > before["hp"] and not live_mon:
            labels.append(f"回血+{cur['hp'] - before['hp']}")
        # 钥匙增减
        got, spent = key_delta_label(before["keys"], cur["keys"])
        if got:
            labels.append("拿钥匙 " + ",".join(got))
        if spent:
            labels.append("开门(耗" + ",".join(spent) + f") @{cell[1:]}")
        if labels:
            milestones.append(dict(i=i, label="；".join(labels), **cur))
    return milestones, visited, taken_gems, cur


def main():
    start = build_start()[0]
    zone = build_zone()
    gems = _zone_attr_gems(zone)
    rows = load_rows(CUT)

    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        sys.exit("cut 文件里没有 MT10 行")
    # "最好那条"：玩家口径 maxDEF=25/maxATK=26 → 按 (def↓, atk↓, hp↓)
    primary = max(mt10, key=lambda r: (r["def"], r["atk"], r["hp"]))
    # 另给 maxHP MT10（#3"差多少血"取最宽口径）
    hp_best = max(mt10, key=lambda r: (r["hp"], r["def"], r["atk"]))

    actions = list(primary["actions"])
    milestones, visited, taken_gems, term = build_milestones(start, actions, zone, gems)

    # ── 封板独立重放对账 ──
    rs = replay(start, actions, step, _copy_state)
    fidelity = dict(floor=(rs.current_floor, primary["floor"]),
                    hp=(rs.hero.hp, primary["hp"]),
                    atk=(rs.hero.atk, primary["atk"]),
                    def_=(rs.hero.def_, primary["def"]))
    fid_ok = all(a == b for a, b in fidelity.values())

    # ── 宝石账：本区(MT1-MT10)拿了/跳过/擦肩没拿 ──
    region_gems = {c: d for c, d in gems.items() if 1 <= fk(c[0]) <= 10}
    visited_by_floor = {}
    for (f, x, y) in visited:
        visited_by_floor.setdefault(f, set()).add((x, y))
    taken, skipped_adj, skipped_far, skipped_unvisited = [], [], [], []
    for c, d in sorted(region_gems.items(), key=lambda kv: (fk(kv[0][0]), kv[0][1], kv[0][2])):
        f, x, y = c
        if c in taken_gems:
            taken.append((c, d))
        elif f not in visited_by_floor:
            skipped_unvisited.append((c, d))
        else:
            vs = visited_by_floor[f]
            mind = min(abs(x - vx) + abs(y - vy) for vx, vy in vs)
            (skipped_adj if mind <= 1 else skipped_far).append((c, d, mind))

    # ── 钥匙花在哪：开门里程碑 + 起终持钥 ──
    door_events = [m for m in milestones if "开门" in m["label"]]
    key_events = [m for m in milestones if "拿钥匙" in m["label"]]
    start_keys = nz_keys(start.hero)

    # ── boss 缺口 ──
    bm = zone["boss_mon"]
    toll_primary = boss_toll(zone, term["atk"], term["def_"], term["mdef"])
    toll_hpbest = boss_toll(zone, hp_best["atk"], hp_best["def"], 0)

    write_report(primary, hp_best, milestones, term, fidelity, fid_ok,
                 taken, skipped_adj, skipped_far, skipped_unvisited,
                 door_events, key_events, start_keys, bm, toll_primary, toll_hpbest,
                 region_gems, len(actions))
    print(f"主态(导出对象): MT10 HP={primary['hp']} ATK={primary['atk']} DEF={primary['def']} "
          f"动作{len(actions)}步")
    print(f"封板重放对账: {'逐字段一致 ✅' if fid_ok else fidelity}")
    print(f"终态停在: {term['floor']}({term['x']},{term['y']}) HP={term['hp']} "
          f"ATK={term['atk']} DEF={term['def_']}")
    print(f"boss(队长 {bm.name if bm else None}) 打这一战模型损血={toll_primary} vs 终态 HP={term['hp']}")
    print(f"报告已写: {OUT}")


def write_report(primary, hp_best, milestones, term, fidelity, fid_ok,
                 taken, skipped_adj, skipped_far, skipped_unvisited,
                 door_events, key_events, start_keys, bm, toll_primary, toll_hpbest,
                 region_gems, nact):
    L = []
    L.append("# κ=0+stairs 搜索到 MT10 的「最好那条」路线导出（只读·引擎封板重放）\n")
    L.append("> 仅导出，不含策略分析。动作串=搜索 cut 文件原样落盘的方向键，已从干净起点引擎重放对账。")
    L.append(f"> 来源文件：`{CUT.name}` 中 `floor==MT10` 按 (DEF↓,ATK↓,HP↓) 取顶的那条。\n")

    # 4. 提到前面：来历 + 终态字段（玩家问 #4）
    L.append("## 0. 这条是引擎重放过的还是缩点算的（玩家问 #4）")
    L.append("- **产生**：κ=0+stairs 跨层 beam 搜索（缩点算子内部展开成方向键），cut 时把整串 RULD 落盘。")
    L.append("- **校验**：本脚本把这串方向键从【干净起点】(`build_start`，开局噩梦后 MT3 入口) 用封板引擎")
    L.append("  `sim.step` 经 `solver.verify.replay` 重放，与 cut 日志行【逐字段对账】：")
    fl = fidelity
    L.append(f"  - floor: 重放={fl['floor'][0]} / 日志={fl['floor'][1]}")
    L.append(f"  - HP: 重放={fl['hp'][0]} / 日志={fl['hp'][1]}　ATK: {fl['atk'][0]}/{fl['atk'][1]}"
             f"　DEF: {fl['def_'][0]}/{fl['def_'][1]}")
    L.append(f"  - **对账结果：{'逐字段一致 ✅（动作串真能引擎走到该终态，非仅缩点抽象层算过）' if fid_ok else '不一致 ❌ '+str(fl)}**")
    L.append("- ⚠ 动作串从【开局噩梦后首个自由态】起算：真实游戏照走前，需先走完强制开局噩梦"
             "（build_start 内施加存档前 82 token，无博弈自由度的过场）。\n")

    L.append("## 1. 入口 / 终态字段")
    L.append(f"- **导出主态**（玩家口径 maxDEF=25/maxATK=26）：MT10 "
             f"HP={primary['hp']} ATK={primary['atk']} DEF={primary['def']}，动作 {nact} 步。")
    L.append(f"- **终态停点**：{term['floor']}({term['x']},{term['y']}) "
             f"HP={term['hp']} ATK={term['atk']} DEF={term['def_']} mdef={term['mdef']} "
             f"gold={term['gold']} 持钥={term['keys']}")
    L.append(f"- 起点：MT3(2,11) HP=400 ATK=10 DEF=10 持钥={start_keys}")
    L.append(f"- 另存最宽口径 maxHP@MT10 兄弟态（非本条，仅 #3 参照）：HP={hp_best['hp']} "
             f"ATK={hp_best['atk']} DEF={hp_best['def']}\n")

    L.append("## 2. 逐里程碑（每个关键节点：换层/拿装备宝石/拿钥匙/开门/打怪 + 当刻坐标/属性/持钥）")
    L.append("| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |")
    L.append("|----|------|------|----|----|-----|---------|")
    for m in milestones:
        L.append(f"| {m['i']} | {m['label']} | ({m['x']},{m['y']})@{m['floor']} | "
                 f"{m['hp']} | {m['atk']} | {m['def_']} | {m['keys']} |")
    L.append("")

    L.append("## 3. 重点：拿了哪些 / 跳过哪些 / 守着没拿 / 钥匙花在哪（玩家问 #2）")
    L.append(f"### 攻防宝石+铁剑铁盾（本区 MT1-MT10 共 {len(region_gems)} 处）")
    L.append("**拿到的：**")
    if taken:
        for c, d in taken:
            L.append(f"- ✅ {c} {gem_label(*d)}")
    else:
        L.append("- （无）")
    L.append("**擦肩没拿（曼哈顿≤1，走到隔壁却没踏上）：**")
    if skipped_adj:
        for c, d, md in skipped_adj:
            L.append(f"- ⚠ 守着没拿 {c} {gem_label(*d)}（最近到 {md} 格）")
    else:
        L.append("- （无）")
    L.append("**到过该层但绕开了（曼哈顿>1）：**")
    if skipped_far:
        for c, d, md in skipped_far:
            L.append(f"- ○ {c} {gem_label(*d)}（最近 {md} 格）")
    else:
        L.append("- （无）")
    L.append("**整层没进、自然没拿：**")
    if skipped_unvisited:
        for c, d in skipped_unvisited:
            L.append(f"- · {c} {gem_label(*d)}")
    else:
        L.append("- （无）")
    L.append("")
    L.append("### 铁剑 / 铁盾 专项（+10 装备）")
    big = [(c, d) for c, d in region_gems.items() if max(d) >= 10]
    for c, d in sorted(big, key=lambda kv: (fk(kv[0][0]), kv[0][1])):
        tag = "✅拿到" if c in dict(taken) else "❌没拿"
        L.append(f"- {gem_label(*d)} @{c}：{tag}")
    L.append("")
    L.append("### 钥匙花在哪")
    L.append(f"- 起点持钥：{start_keys}　→　终态持钥：{term['keys']}")
    L.append("- **开门耗钥事件：**")
    if door_events:
        for m in door_events:
            L.append(f"  - 步#{m['i']} {m['label']} → 当刻持钥 {m['keys']}")
    else:
        L.append("  - （全程未开门）")
    L.append("- **沿途捡钥事件：**")
    if key_events:
        for m in key_events:
            L.append(f"  - 步#{m['i']} {m['label']} → 当刻持钥 {m['keys']}")
    else:
        L.append("  - （全程未捡到钥匙）")
    L.append("")

    L.append("## 4. 最后停在 MT10 哪、为什么过不了 boss（玩家问 #3）")
    if bm:
        L.append(f"- **boss（本层队长）**：{bm.name}(id{bm.id}) hp{bm.hp}/atk{bm.atk}/def{bm.def_} "
                 f"special{bm.special}")
    L.append(f"- **终态停点**：{term['floor']}({term['x']},{term['y']}) "
             f"HP={term['hp']} ATK={term['atk']} DEF={term['def_']}")
    L.append(f"- **打 boss 这一战的模型损血**（boss_toll，按终态 atk{term['atk']}/def{term['def_']}）"
             f"= **{toll_primary}**　vs 终态 HP=**{term['hp']}**")
    gap = toll_primary - term["hp"]
    if gap > 0:
        L.append(f"  - → 仅这一战就要掉 {toll_primary} 血，手里只有 {term['hp']}，**差 {gap} 血**（还没算到 boss 前路上损血）。")
    L.append(f"- 最宽口径兄弟态 maxHP@MT10：HP={hp_best['hp']} ATK={hp_best['atk']} DEF={hp_best['def']}"
             f" → 该属性下 boss_toll={toll_hpbest}，"
             + (f"仍差 {toll_hpbest - hp_best['hp']} 血。" if toll_hpbest > hp_best['hp'] else "理论上够。"))
    L.append("- 说明：cut 态是 beam 截断点，动作串止于该 MT10 格、并未实际推进 boss 埋伏序列；"
             "上面 boss_toll 是引擎战斗模型对【单挑队长那一战】的损血，仅供看「差多少」。\n")

    L.append("## 5. 完整动作序列（方向键，可照走；先走完强制开局噩梦再接此串）")
    L.append("```")
    L.append("".join(primary["actions"]))
    L.append("```")
    ud = Counter(primary["actions"])
    L.append(f"- 合计 {nact} 步：U×{ud.get('U',0)} D×{ud.get('D',0)} "
             f"L×{ud.get('L',0)} R×{ud.get('R',0)}")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
