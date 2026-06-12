"""【只生成+标注·不改产品码】一次产出四条 β(0.25/0.5/0.75/1) best-MT10 路线的 .h5route
   （带 β 值命名，玩家在 h5mota 网站逐条看【游戏自己引擎】回放）+ 关键位置标注表。

玩家(2026-06-11)要：转四条 h5route + 标 MT9来回蹭/7处就近病/拿血处/卡点，对着网站回放逐条验。
  · 步号双口径：β段内步号(审计 md 同口径，从开局噩梦后 MT3 入口起算的第几个动作)
                / 网站绝对 token ≈ OPENING_PREFIX(83) + β段步号（h5route 前面拼了 83 步开局前缀）。
  · MT9 段：每次进 MT9 的步号 + 该段触达楼层串 + 段损血 + 自动判「深潜远货 / 近层往返蹭」。
  · 三病步号：就近病(可绕开损血战) / MT5剑后回MT1拿血 / 广义早拿血(700+)。

复用（不重写逻辑）：
  · gen_beta_h5route.gen(beta) —— 取 best_row.actions、拼前缀 tokens[:83]、封板 sim 预检、write_h5route。
  · export_beta_route_disease_audit.analyze(beta,...) —— 同一条 best_row.actions 的 MT9段表 segs + 三病步号 dis。
  两者同口径(pick_best_mt10)取同一条路线，故步号一致。

不改 sim/solver/vzone/quotient，不决定改方向A还是fly。
跑法：python -u extract/gen_beta_h5routes_all.py
产物：四个 beta{tag}_mt10_route.h5route + extract/beta_h5routes_annotated.md
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

from probe_crossfloor import build_start, OPENING_PREFIX
from vzone import build_zone, _zone_attr_gems
from export_k0stairs_mt10_route import fk
from gen_beta_h5route import gen
from export_beta_route_disease_audit import analyze, FAR, BETAS

OUT = Path(__file__).parent / "beta_h5routes_annotated.md"


def both(i):
    """步号双口径：β段内步号 / 网站绝对 token(≈OPENING_PREFIX+i)。"""
    return f"{i}(网站~{OPENING_PREFIX + i})"


def seg_kind(floors):
    """从该 MT9 段触达的楼层串自动判段性质。"""
    if not floors:
        return "原地"
    nums = [fk(f) for f in floors]
    lo = min(nums)
    if lo <= 5:
        return f"深潜远货→到MT{lo}再折返"
    if len(set(floors)) < len(floors) or len(floors) > 2:
        return "近层(MT6-9)往返蹭"
    return "近层直行"


def collect():
    zone = build_zone()
    start = build_start()[0]
    gems = _zone_attr_gems(zone)
    mt15 = frozenset(c for c in gems if fk(c[0]) in FAR)
    out = []
    for b in BETAS:
        info = gen(b)                              # 生成 .h5route + 封板 sim 预检 + 终态/卡点
        o = analyze(b, zone, start, gems, mt15)    # 同一条 actions 的 MT9段/三病步号
        out.append((b, info, o))
    return out


def write_report(rows):
    L = []
    L.append("# 四 β best-MT10 路线 · h5route（网站引擎回放）+ 关键位置标注\n")
    L.append("> 只生成+标注，未改任何产品码(sim/solver/vzone/quotient)，未决定改方向A还是fly。")
    L.append(f"> 每条 = 前缀 `tokens[:{OPENING_PREFIX}]`(开局噩梦→MT3 入口) + β 段纯 RULD 解算串，"
             "拼接后封板 sim 预检终态==cut 行才写盘。")
    L.append("> **步号双口径**：`β段步号`(从 MT3 入口起算的第几个动作，与审计 md 同口径) / "
             f"`网站~N`(网站回放绝对 token ≈ {OPENING_PREFIX}+β段步号，前面 {OPENING_PREFIX} 步是开局前缀)。")
    L.append("> 标注步号来自只读审计(反事实无战 BFS 判可绕、损血/省 boss 血归因 data 真读格)，对着回放逐条核。\n")

    # 总览
    L.append("## 总览\n")
    L.append("| β | 文件 | 前缀+β段=总token | 终态(MT10入口) | 红钥 | 进MT9 | 就近病 | 剑后拿血 | 早拿血 | 封板 |")
    L.append("|---|------|------------------|----------------|------|------|-------|---------|-------|------|")
    for b, info, o in rows:
        d = o["dis"]
        L.append(f"| {b:g} | `{info['path'].name}` | {info['prefix_len']}+{info['beta_steps']}={info['total']} | "
                 f"{info['floor']}({info['x']},{info['y']}) HP{info['hp']}/A{info['atk']}/D{info['def_']} | "
                 f"{info['red']} | {o['n_mt9']}次 | {len(d['junk_kill'])} | {len(d['hp_after_sword'])} | "
                 f"{len(d['early_heal'])} | {'✅' if o['fid_ok'] else '❌'} |")
    L.append("")
    L.append("> 四条终态都停在 **MT10 入口**、**红钥匙=0** → 网站回放走到 MT10 入口即结束，"
             "**不会撞红门(6,9)、到不了 boss 房**。这正是 β 自夸余量是 D 幻觉(连红钥匙都没拿到)的实证。\n")

    # 每条详情
    for b, info, o in rows:
        d = o["dis"]
        L.append(f"## β={b:g} → `{info['path'].name}`\n")
        L.append(f"- **文件**：前缀 {info['prefix_len']} 步(开局噩梦→MT3 入口) + β段 {info['beta_steps']} 步(纯 RULD，无 FMT) "
                 f"= 共 {info['total']} token。封板 sim 预检 {'✅一致' if info_ok(info, o) else '❌'}。")
        L.append(f"- **预计走到哪/卡哪**：网站回放到 **MT10 入口 ({info['x']},{info['y']}) HP={info['hp']} "
                 f"ATK={info['atk']} DEF={info['def_']}**，持钥={info['keys']}，**红钥匙={info['red']}**。"
                 f"{'红钥匙=0 → 到 MT10 入口即止，不会撞红门(6,9)、打不到 boss。' if info['red'] == 0 else '有红钥匙，可继续撞红门。'}")
        L.append(f"- **依赖旧假设会不会卡**：β段在 ZONE1(MT1-10) 内，前缀只到 MT3，整条不触及 MT40+("
                 "故与 handoff 那处 MT45 预存 regression 无关)；ZONE1 内 MT2 小偷(3,7)→(1,9) desync 已三段修法、"
                 "网站 1b 已坐实。封板 sim(修法后)重放==cut 行，预计忠实回放到 MT10 入口；若某楼梯不自动换层或撞墙 desync，记步号告诉我。\n")

        # MT9 段
        L.append(f"### 进 MT9 共 {o['n_mt9']} 次（来回蹭看这里）")
        L.append("| 第# | 进MT9@步(β段/网站) | 该段触达楼层 | 段损血 | 段性质(自动判) |")
        L.append("|----|--------------------|------------|-------|---------------|")
        for k, sg in enumerate(o["segs"], 1):
            fl_s = "→".join(sg["floors"]) or "—"
            L.append(f"| {k} | {both(sg['entry'])} | {fl_s} | {sg['dmg']} | {seg_kind(sg['floors'])} |")
        L.append("")

        # 就近病
        L.append(f"### 就近病(可绕开+非零伤+此刻还有远货)：{len(d['junk_kill'])} 处")
        if d["junk_kill"]:
            for (i, fl, dmg, dg, cnt, ha, fv) in d["junk_kill"]:
                L.append(f"- 步 **{both(i)}** @{fl}：损血{dmg}/金+{dg}，可绕开，此刻 MT1-5 剩 {cnt} 件远货"
                         f"{'(含红宝石+atk)' if ha else ''}(可省 boss {fv:.0f} 血) → 回放到这看是不是绕了冤枉路去打它")
        else:
            L.append("- （无）")
        L.append("")

        # MT5 剑后拿血 + 早拿血
        L.append(f"### MT5 拿剑后回 MT1 拿血(HP≥700)：{len(d['hp_after_sword'])} 处")
        if d["hp_after_sword"]:
            for (i, hpb, dh) in d["hp_after_sword"]:
                L.append(f"- 步 **{both(i)}**：此刻 HP={hpb}(已≥700)仍拿血 +{dh}")
        else:
            L.append("- （无）")
        L.append(f"### 广义早拿血(HP≥700 仍拿，非上面那处)：{len(d['early_heal'])} 处")
        if d["early_heal"]:
            for (i, fl, hpb, dh) in d["early_heal"]:
                L.append(f"- 步 **{both(i)}** @{fl}：此刻 HP={hpb}(已≥700)仍拿血 +{dh}")
        else:
            L.append("- （无）")
        L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


def info_ok(info, o):
    return o["fid_ok"]


def main():
    rows = collect()
    write_report(rows)
    print("=" * 92)
    print("四 β best-MT10 路线 → .h5route + 标注")
    print("=" * 92)
    for b, info, o in rows:
        d = o["dis"]
        print(f"β={b:<5g} {info['path'].name}  前缀{info['prefix_len']}+β段{info['beta_steps']}={info['total']}token  "
              f"终态 {info['floor']}({info['x']},{info['y']}) HP{info['hp']}/A{info['atk']}/D{info['def_']} "
              f"红钥{info['red']}  进MT9×{o['n_mt9']} 就近病{len(d['junk_kill'])} "
              f"剑后拿血{len(d['hp_after_sword'])} 早拿血{len(d['early_heal'])} 封板{'✅' if o['fid_ok'] else '❌'}")
    print("-" * 92)
    print(f"标注表已写：{OUT}")
    print(f"四个 .h5route 已写到仓库根目录 {ROOT}（带 β 值命名），可直接拖进 h5mota 看回放。")


if __name__ == "__main__":
    main()
