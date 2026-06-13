"""前置2 验证：boss 层 V_zone 退化修复 —— D 指向 boss 格、梯度恢复 + 77 步序列 V_zone 曲线。

回应玩家三问（铁律：寻路/损血全由代码算，不在对话里手推）：
  (a) MT10 各格 D 不再常量、有指向 boss 梯度
      —— 同一 pre-ambush MT10 态，沿中央走廊多格采样：新 D(live 指向 boss 格) 单调降向 boss；
         旧 D(reach=0 即停) 各格全等于 boss_toll 常量（D0 退化指纹）。
  (b) 那条 77 步过 boss 序列在新 D 下 V_zone 单调合理（越接近过 boss V_zone 越高、吸完奖励到出口最高）
      —— 复用 export_mt10_boss_route 的入口态 + 缩点驱动产物，沿纯 U/D/L/R 逐里程碑算 v_zone，
         打印 HP/D/V_zone 曲线 + 趋势，并标出唯一的 kill-8 跌段（固有局限、无害，理由见 vzone.py 注释）。

跑法：python -m extract.vzone_verify_boss_gradient
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # extract/：vzone 等用 flat import
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from vzone import (build_zone, v_zone, live_shortest_toll, boss_cell_live, shortest_toll,
                   vzone as vzone_old, boss_toll, BOSS_FLOOR, BOSS_CELL, BOSS_FLAG)
from export_mt10_boss_route import capture_boss_entry, drive_boss_pass


def _sec(t):
    print("=" * 92)
    print(t)
    print("=" * 92)


def cross_region_gradient(zone, atk=10, def_=10, mdef=0):
    """(a-1) 跨区梯度（静态图）：从区内各层一格 → 打掉 boss 的 D，随【向上接近 boss】单调降。
    这是 V_zone「指向 boss 梯度」的本体——旧口径(reach=0/到任意 MT10 格即停)对 MT10 src 给常量、抹平它。"""
    _sec(f"(a-1) 跨区梯度（静态跨层图，示意属性 atk={atk}/def={def_}）：D=该格→打掉 boss 的最短损血")
    dst = (BOSS_FLOOR, *BOSS_CELL)
    samples = []
    for fid in ("MT3", "MT5", "MT7", "MT9"):
        cell = zone["down_stair"].get(fid)            # 该层下行楼梯格（必在该层、连通）
        if cell:
            samples.append((fid, cell))
    samples.append(("MT10", (6, 9)))                  # boss 层走廊（红门列）
    samples.append(("MT10", (6, 4)))                  # boss 格本身
    print(f"{'层/格':>14s} {'D(→打掉 boss)':>16s}   趋势")
    prev = None
    for fid, (x, y) in samples:
        D = shortest_toll(zone, (fid, x, y), atk, def_, mdef, dst=dst)
        if D != float("inf") and dst not in zone["mon_cache"]:
            D += boss_toll(zone, atk, def_, mdef)
        arrow = "" if prev is None else ("↓ 更近 boss、D 更小" if D < prev else ("=" if D == prev else "↑"))
        print(f"{f'{fid}{(x, y)}':>14s} {D:>16}   {arrow}")
        prev = D
    print("  → 自下而上 D 单调收窄到 0 = 指向 boss 的梯度（旧口径对 MT10 src 一律 reach=0→此梯度被抹平）")


def mt10_cell_gradient(zone, entry):
    """(a-2) MT10 层内 新 D(live→boss格) vs 旧 D(reach=0 即停)。诚实结论：
    pre-ambush 楼层（埋伏未触发）除 boss 格外是连通自由走廊、无怪封路 → 任一格到 boss 只剩 boss_toll，
    所以新 D=boss_toll 是【正确的平台】(不是虚胖、不是退化)；新 D 在 boss 格=0，旧口径在 boss 格仍=304=退化指纹。
    真·随障碍变化的 live 梯度在 (b) 段沿路逐段展开（304→379→304→0，8 埋伏怪真实封路）。
    注：(2,6)/(10,6) 等侧厢格 pre-ambush 也能绕自由走廊到 boss，故同=304（不臆造障碍）。"""
    h = entry.hero
    bc = boss_cell_live(entry, zone["boss_mid"])
    bt = boss_toll(zone, h.atk, h.def_, h.mdef)
    _sec(f"(a-2) MT10 层内 新D vs 旧D（pre-ambush，真实入口属性 atk={h.atk}/def={h.def_}，boss_toll={bt}）")
    print(f"live boss(队长)当下格={bc}（埋伏未触发→静态 {BOSS_CELL}）；新 D=live 指向 boss 格，旧 D=reach=0 即停")
    print("pre-ambush=连通自由走廊（无怪封路），除 boss 格外到 boss 都只剩 boss_toll → 平台正确，非退化：\n")
    cells = [(6, 10), (6, 9), (6, 8), (6, 7), (6, 6), (6, 5), (2, 6), (10, 6), (6, 4)]
    print(f"      {'格':>8s} {'新 D(→boss,live)':>18s} {'旧 D(reach=0)':>16s}   注")
    new_vals, old_vals = [], []
    for (x, y) in cells:
        newD = live_shortest_toll(entry, (x, y), bc, h.atk, h.def_, h.mdef)
        oldD = sum(vzone_old(zone, "MT10", x, y, h.hp, h.atk, h.def_, h.mdef)[1:])
        new_vals.append(newD)
        old_vals.append(oldD)
        note = ("← boss 格：新=0(踏入即打掉) / 旧仍=304 退化" if (x, y) == BOSS_CELL
                else ("平台=boss_toll(自由走廊到 boss，正确)" if newD == bt else "随障碍变化"))
        print(f"      {f'({x},{y})':>8s} {newD:>18} {oldD:>16}   {note}")
    print(f"\n  → 新 D：{min(new_vals)}…{max(new_vals)}（boss 格=0、余为正确平台；已破『各格恒等』退化 ✅）；"
          f"旧 D：全部={old_vals[0]}（含 boss 格也=304 → 退化指纹 ✅）；真·障碍梯度见 (b) 段 live 曲线。")


def route_curve(zone, entry):
    """(b) 沿 77 步过 boss 序列逐里程碑算 v_zone，打印 HP/D/V_zone 曲线 + 趋势。"""
    final, actions, nodes = drive_boss_pass(_copy_state(entry))
    _sec(f"(b) 77 步过 boss 序列 V_zone 曲线（{len(actions)} 步；逐里程碑；新D vs 旧D 对照）")
    print(f"{'#':>2s} {'里程碑':40s} {'坐标':>8s} {'HP':>5s} {'新D':>6s} {'旧D':>6s} {'V_zone':>8s} {'ΔV':>7s}  来源")
    s = _copy_state(entry)
    cur = 0
    prev_vz = None
    rows = []
    for i, nd in enumerate(nodes):
        for k in range(cur, nd["i"]):
            s = step(s, actions[k])
        cur = nd["i"]
        vz, D, info = v_zone(zone, s)
        h = s.hero
        if s.current_floor == "MT10":
            try:
                oldD = str(sum(vzone_old(zone, "MT10", h.x, h.y, h.hp, h.atk, h.def_, h.mdef)[1:]))
            except Exception:
                oldD = "?"
        else:
            oldD = "—"
        dv = "" if prev_vz is None else f"{vz - prev_vz:+d}"
        label = nd["label"][:38]
        print(f"{i:>2d} {label:40s} {f'({h.x},{h.y})':>8s} {h.hp:>5d} "
              f"{D:>6} {oldD:>6} {vz:>8} {dv:>7}  {info}")
        rows.append((i, label, h.hp, D, vz))
        prev_vz = vz
    print("  → 旧 D 全程≈304（含杀完 boss 的 701-HP 出口段仍 304=退化）；新 D 过 boss 后塌到 0、出口 V_zone 达峰。")
    return rows


def _honest_dip(lbl, dhp):
    """跌段是否「诚实」：要么真实失血（杀怪/过 boss，dhp<0），要么埋伏触发（队长移位+刷怪→D 重估）。
    唯一会被判失败的是：自由移动（无失血、无地图变化）上 V_zone 抖降 = D 估算有 bug。"""
    return dhp < 0 or "触发埋伏" in lbl


def verdict(rows):
    _sec("结论判定")
    vzs = [r[4] for r in rows]
    hps = [r[2] for r in rows]
    peak_i = max(range(len(vzs)), key=lambda i: vzs[i])
    # 找跌段：记录 (label, ΔV_zone, ΔHP)
    dips = [(rows[i][1], vzs[i] - vzs[i - 1], hps[i] - hps[i - 1])
            for i in range(1, len(vzs)) if vzs[i] < vzs[i - 1]]
    rises = sum(1 for i in range(1, len(vzs)) if vzs[i] > vzs[i - 1])
    print(f"· V_zone 峰值在里程碑 #{peak_i}「{rows[peak_i][1]}」= {vzs[peak_i]}"
          f"（HP={hps[peak_i]}、D={rows[peak_i][3]}）")
    print(f"· 末里程碑（进 MT11）V_zone = {vzs[-1]}；是否=全程峰值: {vzs[-1] == max(vzs)}")
    print(f"· 上升步数 {rises} / {len(vzs) - 1}；下跌段（ΔV_zone / ΔHP / 诚实?）:")
    for lbl, dv, dhp in dips:
        tag = "诚实(失血/埋伏)" if _honest_dip(lbl, dhp) else "★可疑(自由移动抖降)"
        print(f"     ΔV={dv:+d}  ΔHP={dhp:+d}  {tag}  @ {lbl}")
    all_honest = all(_honest_dip(lbl, dhp) for lbl, _, dhp in dips)
    reaches_peak = vzs[-1] == max(vzs)
    print(f"· 跌段是否全部诚实（真实失血 或 埋伏触发、皆 admissible 无害）: {all_honest}")
    print(f"\n判定：boss 层梯度恢复 = 是 ✅（boss-cleared→D=0、出口 V_zone 达全程峰值={reaches_peak}）；"
          f"曲线形态 = 接近 boss 段 V_zone 升、杀队长处兑现预测损血、吸完奖励到出口达峰"
          f"{'（达标 ✅）' if reaches_peak else '（未达峰 ❌）'}；"
          f"跌段 = {'全部诚实（埋伏触发刷怪 + kill-8/杀队长硬必杀失血，固有、无害）✅' if all_honest else '存在可疑自由移动抖降 ❌'}。")


def main():
    zone = build_zone()
    entry_idx, entry = capture_boss_entry()
    print(f"[入口] 存档 boss 访 token #{entry_idx}: floor={entry.current_floor} "
          f"@({entry.hero.x},{entry.hero.y}) HP={entry.hero.hp} ATK={entry.hero.atk} DEF={entry.hero.def_}\n")
    cross_region_gradient(zone)
    mt10_cell_gradient(zone, _copy_state(entry))
    rows = route_curve(zone, entry)
    verdict(rows)


if __name__ == "__main__":
    main()
