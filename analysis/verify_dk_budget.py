"""丙 D_K 第1步【真实可达钥匙预算下重跑，看是否塌回 D_free】（只读探针，未接搜索）。

玩家 2026-06-10 指令第1步：上轮 D_K 塌回 D_free=1394 的真因 = 把【拿不到的钥匙当富余】
（56 黄全算可达 + 非停止 bug 让捡钥零代价循环→预算无界→门全免费→D_K=D_free）。
现在稀缺度算对了（真可达 黄53/蓝3/红1，MT2 三把黄(3,4)(4,4)(3,5) 一区 atk≤27 杀不动 def110
守门怪→拿不到，已排除）。本探针在【真实可达预算】下重跑，回答：D_K 还塌不塌回 D_free、钥匙边际价值还是不是 0。

口径（admissible + 有界，避开上轮非停止 bug）：
  · 核心诊断（§2）：D_free 最短【损血】路上各色门数 —— 若 ≤ 真可达钥数，预算【在这条路上】根本绑不住
    （钥匙稀缺是【全局】65门>56钥，但 boss-距离最短路只过少数门）。这是最干净的"有没有信号"判据。
  · D_K bracket（§3），全用【有界】keyed-Dijkstra（预算只减或【按色封顶】→状态有限→不爆内存）：
      (a) 预授全部真可达钥(53/3/1)、不模型捡钥  → D_K 最宽松下界（keys upfront 最乐观）
      (b) 0 钥、不捡（门全当墙）                → D_K 最悲观上界（钥匙效应上限）
      (c) 0 钥 + 沿路捡【真可达】钥(每色封顶反推非停止) → 介于 (a)(b) 间的现实乐观估
    真 D_K ∈ [(a)|(c), (b)]。(a)>D_free 或 (c)>D_free → 钥匙铁定有信号；(a)=(b)=D_free → 铁定无信号。
  · 损血全用引擎 _toll（强制可杀 ref_atk=max(atk,def+1)，vzone 既定启发）；门 0 损血、捡钥 0 损血、怪付 toll。
  · 塔无关性不适用(extract/ 驱动层探针，可读 MT1-10)；vzone / solver 一行不改（本地实现 keyed-Dijkstra）。
  · 引擎只当裁判，不进搜索循环；本步【不接搜索】。
"""
import sys
import heapq
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from probe_crossfloor import build_start
from sim.simulator import _KEY_ITEMS
from vzone import (build_zone, shortest_toll, _zone_key_geometry,
                   _passable, _enter_cost, _toll, _NB4,
                   BOSS_FLOOR, BOSS_CELL)

ARRIVAL = None                         # dst=None → 到 MT10 任意格(=入口落点)即停（埋伏前）
BOSS_DST = (BOSS_FLOOR, *BOSS_CELL)    # (MT10,6,4) 静态队长格

# 真可达供给（探针 probe_zone1_key_scarcity 实测 C 终态，落盘 zone1_key_scarcity.txt）：
REACHABLE = {"yellowKey": 53, "blueKey": 3, "redKey": 1}
# 一区 atk≤27 杀不动 def110 守门怪 → 拿不到的黄钥（从捡钥池排除）：
UNREACHABLE_KEY_CELLS = {("MT2", 3, 4), ("MT2", 4, 4), ("MT2", 3, 5)}


# ───────────────── 路径几何：各色门 / 打怪 / 损血 ─────────────────
def describe_path(zone, path, atk, def_, mdef):
    geom = _zone_key_geometry(zone)
    door_color = geom["door_color"]
    doors, mons, total = Counter(), [], 0
    floors_seq = []
    for node in path:
        fid = node[0]
        if not floors_seq or floors_seq[-1] != fid:
            floors_seq.append(fid)
        c = door_color.get(node)
        if c:
            doors[c] += 1
        m = zone["mon_cache"].get(node)
        if m:
            total += _toll(m, atk, def_, mdef)
            mons.append(node)
    return dict(doors=doors, n_doors=sum(doors.values()), n_mons=len(mons),
                total=total, floors_seq=floors_seq)


def _fmt(counter):
    if not counter:
        return "无"
    return " ".join(f"{c.replace('Key','')}×{n}" for c, n in sorted(counter.items()))


# ───────────────── 有界 keyed-Dijkstra（无非停止 bug） ─────────────────
def dk_bounded(zone, src, atk, def_, mdef, start_budget,
               pickup_cells=None, cap=None, dst=None, return_path=False):
    """门按色库存放行(过则 -1)；pickup_cells(cell→color) 过则该色 +1【按 cap 封顶】；怪付 toll。
       cap=None 且 pickup_cells=None → 预算只减 → 状态有限。
       pickup 时按 cap 封顶 → 预算 ∈ [0,cap] 有限 → 状态有限（避开零代价循环无界 bug）。
       返回 (D, n_states[, path])；无路→(inf, n_states[, None])。"""
    geom = _zone_key_geometry(zone)
    colors = geom["colors"]
    ci = {c: i for i, c in enumerate(colors)}
    door_color, links = geom["door_color"], zone["links"]
    pickup_cells = pickup_cells or {}
    capv = tuple((cap or {}).get(c, 10 ** 9) for c in colors)
    b0 = tuple(min(int(start_budget.get(c, 0)), capv[i]) for i, c in enumerate(colors))
    start = (src, b0)
    dist = {start: 0}
    prev = {}
    pq = [(0, src, b0)]
    n_states = 0
    while pq:
        d, node, bud = heapq.heappop(pq)
        if d > dist.get((node, bud), float("inf")):
            continue
        n_states += 1
        reached = (node == dst) if dst is not None else (node[0] == "MT10")
        if reached:
            if not return_path:
                return d, n_states
            path = []
            s = (node, bud)
            while s is not None:
                path.append(s[0])
                s = prev.get(s)
            path.reverse()
            return d, n_states, path
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in links:
            nbrs.append(links[node])
        for nb in nbrs:
            if not _passable(zone, nb):
                continue
            nbud = bud
            c = door_color.get(nb)
            if c is not None:                       # 门：要库存、消一把
                i = ci[c]
                if bud[i] <= 0:
                    continue
                nbud = nbud[:i] + (nbud[i] - 1,) + nbud[i + 1:]
            kc = pickup_cells.get(nb)
            if kc is not None:                      # 捡钥：该色 +1（按 cap 封顶）
                j = ci[kc]
                if nbud[j] < capv[j]:
                    nbud = nbud[:j] + (nbud[j] + 1,) + nbud[j + 1:]
            nd = d + _enter_cost(zone, nb, atk, def_, mdef)
            ns = (nb, nbud)
            if nd < dist.get(ns, float("inf")):
                dist[ns] = nd
                prev[ns] = (node, bud)
                heapq.heappush(pq, (nd, nb, nbud))
    return (float("inf"), n_states, None) if return_path else (float("inf"), n_states)


def main():
    L = []
    w = L.append

    real, nopen = build_start()
    rh = real.hero
    src = (real.current_floor, rh.x, rh.y)
    atk, def_, mdef = rh.atk, rh.def_, rh.mdef
    real_keys = {k: v for k, v in dict(rh.keys).items() if v and k in _KEY_ITEMS}

    zone = build_zone()
    geom = _zone_key_geometry(zone)
    colors = geom["colors"]
    # 真可达捡钥池 = 全部钥匙格 − 不可达的 MT2 三把黄
    pickup_reach = {cell: c for cell, c in geom["key_item"].items()
                    if cell not in UNREACHABLE_KEY_CELLS}
    pick_cnt = Counter(pickup_reach.values())

    w("=" * 100)
    w("丙 D_K 第1步 —— 真实可达钥匙预算下重跑（看是否塌回 D_free；只读，未接搜索）")
    w("=" * 100)
    w(f"真起点(穿 {nopen} token 开局噩梦后) = {src}  atk={atk} def={def_} mdef={mdef}")
    w(f"真起手钥匙 = {real_keys or '空(0 钥)'}")
    w(f"预算维(区内门色∪钥色) = {colors}")
    w(f"真可达供给(scarcity 实测 C 终态) = {REACHABLE}")
    w(f"捡钥池(真可达，排除 MT2 三把黄) 各色 = {dict(pick_cnt)}  （共 {len(pickup_reach)} 格）")
    w("-" * 100)

    for atk_probe in (atk, 27):
        tag = "真起手 atk" if atk_probe == atk else "一区能力上限 atk"
        w("")
        w("#" * 100)
        w(f"# atk={atk_probe}（{tag}），def={def_}")
        w("#" * 100)

        for label, dst in (("到 MT10 入口(埋伏前)", ARRIVAL), ("到静态 boss 格(6,4)", BOSS_DST)):
            w("")
            w(f"────── 目标：{label} ──────")
            df_d, df_path = shortest_toll(zone, src, atk_probe, def_, mdef,
                                          return_path=True, dst=dst)
            if df_path is None:
                w("  ⚠ D_free 无路（异常）")
                continue
            df = describe_path(zone, df_path, atk_probe, def_, mdef)
            w(f"  D_free(门全免费) 损血 = {df_d}")
            w(f"    路径经过层: {'→'.join(s[2:] for s in df['floors_seq'])}")
            w(f"    路上【各色门】= {_fmt(df['doors'])}   门总数={df['n_doors']}   打怪={df['n_mons']}")

            # §2 核心诊断：路上门数 vs 真可达钥
            w("  【诊断：这条最短血路上的门，真可达钥够不够开？】")
            binds = False
            for c in ("yellowKey", "blueKey", "redKey"):
                need = df["doors"].get(c, 0)
                have = REACHABLE.get(c, 0)
                if need == 0:
                    continue
                verdict = "够开(不绑)" if need <= have else "★不够→绑!"
                if need > have:
                    binds = True
                w(f"      {c.replace('Key','')}: 路上需开 {need} 扇，真可达钥 {have} 把 → {verdict}")
            if df["n_doors"] == 0:
                w("      （这条最短血路【一扇门都不过】→ 预算无论多紧都绑不住此路）")
            elif not binds:
                w("      ⇒ 全色 路上门数 ≤ 真可达钥 → 预算【在这条路上】绑不住 → 该路 D_K=D_free 可期")

            # §3 bracket
            ga, na = dk_bounded(zone, src, atk_probe, def_, mdef, REACHABLE, dst=dst)
            gb, nb = dk_bounded(zone, src, atk_probe, def_, mdef, {}, dst=dst)
            gc, nc = dk_bounded(zone, src, atk_probe, def_, mdef, real_keys,
                                pickup_cells=pickup_reach, cap=REACHABLE, dst=dst)
            w("  【D_K bracket（有界 keyed-Dijkstra）】")
            w(f"    (a) 预授全可达钥{REACHABLE} 不捡  D_K={ga}"
              f"   {'＝D_free' if ga == df_d else f'＞D_free +{ga-df_d}' if ga<float('inf') else '无路'}"
              f"   [展开{na}态]")
            w(f"    (b) 0 钥不捡(门全墙)          D_K={gb}"
              f"   {'＝D_free' if gb == df_d else f'＞D_free +{gb-df_d}' if gb<float('inf') else '无路(被门全封)'}"
              f"   [展开{nb}态]")
            w(f"    (c) 0 钥+沿路捡真可达钥(封顶)  D_K={gc}"
              f"   {'＝D_free' if gc == df_d else f'＞D_free +{gc-df_d}' if gc<float('inf') else '无路'}"
              f"   [展开{nc}态]")
            # 解读
            if ga > df_d and ga < float("inf"):
                w("    ⇒ 连【预授全可达钥】都 >D_free → 钥匙铁定有信号（最宽松都绑得住）")
            elif gc > df_d and gc < float("inf"):
                w("    ⇒ 现实捡钥模型 (c) >D_free → 钥匙有信号（时序：需在够到钥前先过门）")
            elif gb == df_d:
                w("    ⇒ 连 0 钥都 =D_free → 这条最短血路压根不过门 → 钥匙在此目标零信号")
            else:
                w(f"    ⇒ (a)=(c)=D_free 但 (b)>D_free：真 D_K∈[D_free,{gb}]，"
                  f"绑不绑取决于捡钥时序（(c) 乐观估为 =D_free → 此目标弱信号/无信号）")
        w("-" * 100)

    # ── §4 定位 (c)>D_free 是哪个色钥的【捡钥时序】驱动（按色逐一预授，比最优距离·不看会乱晃的路径） ──
    w("")
    w("#" * 100)
    w("# §4 信号是哪个色钥的【捡钥时序】驱动？逐色把该色钥【预授】(无需沿路捡)、其余仍 0 起手沿路捡，")
    w("#    看 boss-格 D_K 是否回落 D_free。某色一预授就回落 → 那色的捡钥时序是驱动。atk=10。")
    w("#    （注：(a)/(c) 的【路径】因门免费会反复穿门乱晃、不可作差集解读；只比最优【距离】可靠。）")
    w("#" * 100)
    df_boss = shortest_toll(zone, src, atk, def_, mdef, dst=BOSS_DST)
    dc_boss, _ = dk_bounded(zone, src, atk, def_, mdef, real_keys,
                            pickup_cells=pickup_reach, cap=REACHABLE, dst=BOSS_DST)
    w(f"  基线: D_free={df_boss}   (c)全色沿路捡 D_K={dc_boss}   时序信号合计=+{dc_boss - df_boss}")
    for c in ("yellowKey", "blueKey", "redKey"):
        gift = {c: REACHABLE[c]}                       # 只预授该色（其余 0、仍沿路捡）
        pick_rest = {cell: kc for cell, kc in pickup_reach.items() if kc != c}
        gd, _ = dk_bounded(zone, src, atk, def_, mdef, gift,
                           pickup_cells=pick_rest, cap=REACHABLE, dst=BOSS_DST)
        drop = dc_boss - gd
        tag = ("★该色时序是【主】驱动(预授即回落≈D_free)" if gd <= df_boss + 1
               else f"该色贡献 {drop} 血" if drop > 0 else "该色非驱动(预授无变化)")
        w(f"    预授 {c.replace('Key','')}={REACHABLE[c]}（其余沿路捡）→ D_K={gd}  ↓{drop}  {tag}")
    w("=" * 100)
    w("【第1步结论：钥匙边际价值有没有信号？——有，但不是全局稀缺，是【单把红钥的捡钥时序】】")
    w("  ① D_K【没】完全塌回 D_free：现实捡钥(0 起手沿路捡) 到 boss 格 = D_free+2292(atk10)/+316(atk27)。")
    w("     →【钥匙边际价值 ≠ 0】。但塌不塌、绑不绑，取决于【目标】与【是否模型捡钥时序】，不是全局钥匙数。")
    w("  ② 全局数稀缺(黄53<65门、蓝3<6门)【不绑】boss-距离最短血路：预授 53/3/1 即 =D_free（全部目标）；")
    w("     §4 逐色预授证实——预授【黄】↓0、预授【蓝】↓0，二者皆非驱动。boss 血路只过 18-20黄/2蓝门 ≪ 可达钥。")
    w("     →稀缺(黄缺9/蓝缺3)绑的是【收集全部宝箱门】，不是【到 boss】；对 D 启发零贡献。")
    w("  ③ 唯一驱动 = 那把【红钥】的【捡钥时序】(§4 预授红 ↓2292 独家回落 D_free)：唯一红门 MT10(6,9) 在")
    w("     【到队长的唯一近路上】(静态路:入(1,11)→…→(6,9)→(6,5)埋伏→(6,4))，唯一红钥远在 MT8(10,2)(守门怪后)")
    w("     → 0 起手到 boss 须先绕 MT8 取红钥(+10 怪@atk10=+2292 血)。注意红是【数够用】(1钥=1门)却仍出信号")
    w("     →【信号纯来自时序几何(钥-门相对位置)，与数稀缺正交】。")
    w("     ▸ 非静态假象坐实：MT10.json afterBattle[6,1] 有 setBlock(6,9)=0(杀队长清红门)，但那在【杀后】触发，")
    w("       而(6,9)在【approach 上、杀前必过】→ 清门来不及帮 approach → 红钥真需要。与玩家 77 步路线携 red=1 入 MT10 一致。")
    w("  ④ 到 MT10 入口 (c)=D_free（红门在入口之后；入口前的黄/蓝钥都早于其门可捡）→ 信号只在 MT10 内部段冒出。")
    w("  ⑤ admissible 链：真 D_K(每钥一次)≥(c)≥D_free（(c) 按色封顶可重捡=乐观下估）→ 真信号 ≥ 实测 +2292/+316。")
    w("  ⑥ atk↑信号缩(2292→316)：绕路代价随战力降；红钥取道的守门怪/沿途怪变便宜。")
    w("=" * 100)

    text = "\n".join(L)
    out = Path(__file__).parent / "dk_budget_verify.txt"
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[落盘] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
