"""【课程学习·V_boss 弱格饱和度复核】只读脚本。

§S28 留的"诚实保留·未复核"：V_boss 价值表 @ HP_in=735 里的【弱格】(低战力但能生还的格，
如 (24,30)=94 / (24,33)=196 / (27,24)=142 / (30,24)=224)——它们的 delta-vs-HP 拐点是否 >735？

背景机制：较强格 @ (27,27) 拐点在 600→700，735 已稳在拐点上方平台(delta 恒=226)。但【弱格】
  回合数多、boss 战谷底更深，拐点【可能 >735】——意味着 735 处 delta 还没爬到该弱格平台值(仍在
  上升段)，于是 V_boss 表在 735 这层对弱格不准。本脚本对几个弱格各扫一串 HP_in，量 delta-vs-HP
  曲线，判断 735 是否已饱和(=平台)、还是仍在爬坡(拐点>735)。

口径与 curriculum_scan_vboss.py 完全一致(复用其 boss_entry_state/make_entry/scan_point/seg_step
写法)：起点=真实存档 tok1168(刚进 MT10 打 boss)，深拷只覆写 (ATK,DEF,HP)，其余(redKey=1/金/位置)
不动；每点跑 search_quotient(cross_floor=True 限{MT10,MT11}、beam_k=None 穷尽、distinguish_doors
=True)，取 res.final_hp，delta=final_hp-HP_in。

★成本警告：弱格战力低、但高 HP 时活得久→搜索空间也会涨(死亡剪枝放松)。每点设 max_states 安全网，
  hit_cap 即如实记"搜不动"(此时 final_hp 是【不完整】前沿的最大值，非真平台值)，不干等。

只读：复用产品码，绝不改。
用法：python analysis/curriculum_weakcell_saturation.py [--smoke] [--max-states 800000]
      [--cells 24:30,24:33,27:24,30:24] [--hp 735,900,1100,1300,1600,2000]
      [--smoke-cell 24:30] [--smoke-hp 900]
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# 复用 V_boss 主扫脚本的全部建起点/扫点写法，口径严格一致
from analysis.curriculum_scan_vboss import (
    boss_entry_state, make_entry, scan_point, seg_step,
    BOSS_ENTRY_TOK, GOAL, ALLOWED, REAL,
)

# 默认弱格(低战力·能生还)：来自 §S28 HP=735 矩阵的弱格
DEFAULT_CELLS = [(24, 30), (24, 33), (27, 24), (30, 24)]
# (24,27) 在 735 是"死"，可补它在更高 HP 是否复活
EXTRA_DEAD_CELLS = [(24, 27)]
DEFAULT_HPS = [735, 900, 1100, 1300, 1600, 2000]


def parse_cells(s):
    out = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        a, d = tok.split(":")
        out.append((int(a), int(d)))
    return out


def parse_ints(s):
    return [int(x) for x in s.split(",") if x.strip()]


def run_cell_hp(base, atk, def_, hp, max_states):
    """扫单个弱格的单个 HP 点。返回 (delta_or_None, info_dict)。
    hit_cap 时 final_hp 是【不完整前沿】的最大出口值——delta 仍记下但标 hit_cap，
    读表须知此值非真平台(搜索没穷尽，可能偏低也可能恰好已找到最优但没证完)。"""
    res, secs = scan_point(base, atk, def_, hp, max_states)
    delta = (res.final_hp - hp) if res.found else None
    info = {
        "found": res.found,
        "hit_cap": getattr(res, "hit_cap", False),
        "final_hp": res.final_hp,
        "delta": delta,
        "n_exits": len(res.goal_frontier),
        "fps": res.distinct_fingerprints,
        "gen": getattr(res, "states_generated", -1),
        "secs": secs,
    }
    return delta, info


def fmt_delta(info):
    if info["delta"] is None:
        return "死" if not info["hit_cap"] else "?cap"
    tag = "*" if info["hit_cap"] else ""   # * = hit_cap，值不完整
    return f"{info['delta']}{tag}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=str, default="",
                    help="弱格列表 ATK:DEF 逗号分隔；空=默认4弱格+(24,27)死格复活探测")
    ap.add_argument("--hp", type=str, default="",
                    help="HP_in 列表逗号分隔；空=735,900,1100,1300,1600,2000")
    ap.add_argument("--max-states", type=int, default=800_000,
                    help="单点搜索上限(安全网)；hit_cap 即记搜不动，不干等")
    ap.add_argument("--smoke", action="store_true",
                    help="冒烟：只跑一个最便宜的点(默认 (24,30)@HP=900)确认单点耗时与脚本可跑通")
    ap.add_argument("--smoke-cell", type=str, default="24:30")
    ap.add_argument("--smoke-hp", type=int, default=900)
    args = ap.parse_args()

    base = boss_entry_state()
    h = base.hero
    keys = {k: v for k, v in h.keys.items() if v}
    print("========== V_boss 弱格饱和度复核：起点 = 真实存档 tok1168 ==========")
    print(f" 基准起点 = MT10({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"钥={keys} 金={h.gold}")
    print(f" 目标 = {GOAL}  段楼层 = {sorted(ALLOWED)}  穷尽(beam_k=None) distinguish_doors=True")
    print(f" max_states 安全网 = {args.max_states}（hit_cap 标 '*'：值不完整=搜不动）")

    # ── 冒烟：先跑一个最便宜的点确认耗时 ───────────────────────────────────
    if args.smoke:
        a, d = parse_cells(args.smoke_cell)[0]
        hp = args.smoke_hp
        print(f"\n[冒烟] 单点 (ATK={a},DEF={d}) @ HP={hp} …")
        delta, info = run_cell_hp(base, a, d, hp, args.max_states)
        print(f"  found={info['found']} hit_cap={info['hit_cap']} "
              f"final_hp={info['final_hp']} delta={info['delta']} "
              f"出口={info['n_exits']} 指纹={info['fps']} gen={info['gen']} "
              f"耗时={info['secs']:.1f}s")
        print(f"  → 单点 {info['secs']:.1f}s；据此估算全表(cells×hps)耗时再决定放开范围。")
        return

    cells = parse_cells(args.cells) if args.cells else (DEFAULT_CELLS + EXTRA_DEAD_CELLS)
    hps = parse_ints(args.hp) if args.hp else DEFAULT_HPS

    # ── 主扫：每个弱格扫一串 HP，量 delta-vs-HP ──────────────────────────────
    results = {}   # (a,d) -> {hp: info}
    for (a, d) in cells:
        results[(a, d)] = {}
        print(f"\n\n========== 弱格 (ATK={a}, DEF={d}) delta-vs-HP ==========")
        print(f" {'HP_in':>6} | {'found':>5} {'cap':>3} {'final_hp':>9} {'delta':>7} "
              f"{'出口':>4} {'指纹':>7} {'gen':>9} {'秒':>7}")
        for hp in hps:
            delta, info = run_cell_hp(base, a, d, hp, args.max_states)
            results[(a, d)][hp] = info
            ds = f"{info['delta']:>7}" if info["delta"] is not None else f"{'--':>7}"
            print(f" {hp:>6} | {str(info['found']):>5} {str(info['hit_cap']):>3} "
                  f"{info['final_hp']:>9} {ds} {info['n_exits']:>4} {info['fps']:>7} "
                  f"{info['gen']:>9} {info['secs']:>7.1f}", flush=True)

    # ── 汇总矩阵：行=弱格 列=HP，单元=delta(hit_cap 标 *) ────────────────────
    print(f"\n\n========== 汇总 delta(弱格 × HP_in)  ['死'=没生还 / '*'=hit_cap值不完整] ==========")
    header = "  格(ATK,DEF) " + "".join(f"{hp:>9}" for hp in hps)
    print(header)
    for (a, d) in cells:
        row = []
        for hp in hps:
            row.append(f"{fmt_delta(results[(a, d)][hp]):>9}")
        print(f" ({a:>2},{d:>2})     " + "".join(row))

    # ── 拐点/饱和判定：找 delta 首次"基本不再涨"的 HP 档 ──────────────────────
    print(f"\n ── 拐点/饱和判定(只对 found 且非 hit_cap 的点；Δ相邻≤2 视为已平) ──")
    for (a, d) in cells:
        seq = [(hp, results[(a, d)][hp]) for hp in hps]
        # 取有效(found & 非cap)的 (hp, delta) 序列
        valid = [(hp, info["delta"]) for hp, info in seq
                 if info["found"] and not info["hit_cap"]]
        if not valid:
            capped = any(info["hit_cap"] for _, info in seq)
            note = "全 hit_cap 搜不动" if capped else "全程没生还(死)"
            print(f"  ({a},{d}): {note}")
            continue
        # 平台值 = 有效点里最大 delta；判 735 是否已达
        plateau = max(v for _, v in valid)
        d735 = results[(a, d)].get(735)
        # 找首个"之后不再显著上涨"的 HP(与平台差≤2)
        knee = None
        for hp, v in valid:
            if plateau - v <= 2:
                knee = hp
                break
        if d735 is not None and d735["found"] and not d735["hit_cap"]:
            sat = (plateau - d735["delta"]) <= 2
            s735 = f"735处 delta={d735['delta']}, {'已饱和' if sat else '未饱和(拐点>735)'}"
        elif d735 is not None and d735["hit_cap"]:
            s735 = "735处 hit_cap(搜不动)"
        else:
            s735 = "735处 死/无效"
        print(f"  ({a},{d}): 有效平台 delta≈{plateau}(出现于 HP≥{knee})；{s735}")

    print("\n ★ 含义：若某弱格 735 处 delta < 其高 HP 平台 → V_boss 表在 735 层对该弱格【低估】，")
    print("   严谨表须对此弱格按更高 HP 标定平台 delta；若 735 已= 平台 → 单 HP=735 层够用。")
    print("   带 '*'(hit_cap)的格搜索未穷尽，平台值不可信，须降属性/换更小 HP 或加 max_states 复核。")


if __name__ == "__main__":
    main()
