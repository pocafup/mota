"""【方向2·核实】坐实玩家观察："k1600 反退 ATK24" 是否只是"没跑完(hit_cap)"的假象。

玩家核实点（可能推翻 §S40/§S44"加大预算没用"）：
  k1600 那次在 944 tok 停下、属性 733/24/22、还剩三黄钥匙、完全有能力往后；
  说 k800/k1600 路线基本相等、1600 只是没跑完才显得 ATK 低 24。

本脚本便宜坐实三件（只读 + 从一个态续跑·不加大预算重跑一整轮·不碰产品码）：
  Q1 = k1600 是 hit_cap(没跑完) 还是真收敛——已由日志 _dir2_beam_k800_1600.txt 答(见末尾打印)。
  Q2 = 把 944tok/733-24-22 那个 anchor 态当起点、单独跑"从它能不能到红钥"。
       真能到 = 玩家对(k1600 只是没跑完·在正确路上)；到不了 = 停哪都一样·非没跑完问题。
  Q3 = 对比 k800/k1600 两个 anchor 态：_qfp 指纹同不同 = 是不是同一进度态
       （位置/钥匙/已消除怪门一样），还是只属性碰巧相近其实不同进度。

跑法：python -u analysis/dir2_verify_k1600_notfinished.py [--budget 1200000] [--beam-k 1600]
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.extract_zone1_milestones import build_initial_state
from sim.simulator import step
from solver.quotient import search_quotient, _qfp, _free_cells
from extract.decode_route import parse_rle_route, decompress
from analysis.dir2_redkey_beam_probe import (
    v_boss_score, make_seg_step, fmt, REDKEY_CELL, REAL_LEG_FLOORS, BIG,
)

BK1600 = "dir2_redkey_halfway_bk1600.h5route"
BK800 = "dir2_redkey_halfway_bk800.h5route"


def decode_h5route(path):
    raw = Path(path).read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    route_raw = decompress(outer["route"])
    actions = parse_rle_route(route_raw)
    return actions, outer


def replay_actions(actions):
    s = build_initial_state()
    for t in actions:
        s = step(s, t)
        if s.dead:
            break
    return s


def qfp_signature(s):
    """返回 (current_floor, n_free_cells, frozenset_free, flags_tuple) + distinguish_doors=True 指纹。
    给玩家看的是 (层, 自由块大小, 指纹 hash)——同层+同自由块+同flag=同进度。"""
    free = _free_cells(s)
    fp = _qfp(s, free, True)
    return fp, len(free)


def show_state(tag, path):
    actions, _ = decode_h5route(path)
    s = replay_actions(actions)
    fp, nfree = qfp_signature(s)
    h = s.hero
    print(f"\n  [{tag}] {path}  ({len(actions)} token)")
    print(f"    重放终态: {fmt(s)}")
    print(f"    _qfp: 层={s.current_floor} 自由块={nfree}格 flags={dict(h.flags)} "
          f"指纹hash={hash(fp)}")
    return s, fp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=1_200_000,
                    help="Q2 续跑生成上限（原 k1600 在 800k hit_cap·给 1.5× 看能否破红钥/saturate）")
    ap.add_argument("--beam-k", type=int, default=1600, help="Q2 续跑 beam 宽（默认=原 k1600 同宽）")
    args = ap.parse_args()

    print("=" * 84)
    print("方向2 核实：k1600 是'没跑完(hit_cap)'还是'真收敛'？那个 anchor 态能不能往后破红钥？")
    print("=" * 84)

    # ── Q3：对比两 anchor 态是否同一进度（_qfp 指纹）─────────────────────────────────
    print("\n【Q3】k800 / k1600 两 anchor 态对比（玩家以为都是 733/24/22 同进度）：")
    s1600, fp1600 = show_state("k1600", BK1600)
    s800, fp800 = show_state("k800", BK800)
    same = (fp1600 == fp800)
    print(f"\n  ⟹ 两态 _qfp 指纹{'相同(同一进度)' if same else '不同(不同进度态)'}：", end="")
    if same:
        print("属性相近 = 真同进度。")
    else:
        d = []
        if s1600.current_floor != s800.current_floor:
            d.append(f"层 {s1600.current_floor}≠{s800.current_floor}")
        if (s1600.hero.x, s1600.hero.y) != (s800.hero.x, s800.hero.y):
            d.append(f"位置 ({s1600.hero.x},{s1600.hero.y})≠({s800.hero.x},{s800.hero.y})")
        k1 = {k: v for k, v in s1600.hero.keys.items() if v}
        k2 = {k: v for k, v in s800.hero.keys.items() if v}
        if k1 != k2:
            d.append(f"钥 {k1}≠{k2}")
        if s1600.hero.kill_count != s800.hero.kill_count:
            d.append(f"kills {s1600.hero.kill_count}≠{s800.hero.kill_count}")
        print("属性相近 ≠ 同进度，差异：" + "；".join(d))
    sys.stdout.flush()

    # ── Q2：从 k1600 anchor 态续跑、看能不能到红钥 ───────────────────────────────────
    print("\n" + "=" * 84)
    print(f"【Q2】从 k1600 anchor 态({fmt(s1600)}) 续跑搜红钥{REDKEY_CELL}")
    print(f"      beam_k={args.beam_k}  budget={args.budget}  （原 k1600 在 800k hit_cap·此处给更大预算）")
    print("=" * 84, flush=True)
    assert s1600._single_floor_copy is False, "anchor 起点 _single_floor_copy 须 False（跨层安全深拷）"

    best = defaultdict(lambda: {"atk": 0, "def": 0, "hp": 0, "V": BIG, "n": 0})

    def on_admit(child, _acts):
        h = child.hero
        b = best[child.current_floor]
        b["n"] += 1
        if h.atk > b["atk"]:
            b["atk"] = h.atk
        if h.def_ > b["def"]:
            b["def"] = h.def_
        if h.hp > b["hp"]:
            b["hp"] = h.hp
        v = v_boss_score(child)
        if v > b["V"]:
            b["V"] = v

    seg_step = make_seg_step(REAL_LEG_FLOORS)
    t0 = time.time()
    res = search_quotient(s1600, REDKEY_CELL, seg_step, max_states=args.budget,
                          cross_floor=True, beam_k=args.beam_k, distinguish_doors=True,
                          beam_score_fn=v_boss_score, beam_diversity="stairs",
                          on_admit=on_admit)
    secs = time.time() - t0

    print(f"\n  found={res.found}  耗时={secs:.1f}s  hit_cap={res.hit_cap}")
    print(f"  distinct_fp={res.distinct_fingerprints}  expanded={res.states_expanded} "
          f"generated={res.states_generated}  waves={res.n_waves}")
    print(f"  goal_hits={res.goal_hits}  前沿={len(res.goal_frontier)}")
    print(f"  fp_by_floor={dict(res.fp_by_floor)}")
    print("\n  ── 各层【到达过】最优属性（看续跑把队伍推到哪）──")
    for f in sorted(best, key=lambda x: int(x[2:])):
        b = best[f]
        print(f"    {f:>5}: n={b['n']:>6}  maxATK={b['atk']}  maxDEF={b['def']}  "
              f"maxHP={b['hp']}  bestV={b['V']:>8.0f}")

    print("\n" + "=" * 84)
    print("【结论判据】")
    if res.found:
        print(f"  ★ 从 anchor 续跑【走到了红钥】(出口HP={res.final_hp})")
        print("  ⟹ 玩家对：k1600 只是没跑完(hit_cap)、那个态在正路上、加大预算+跑完有戏。")
    elif res.hit_cap:
        print(f"  ✗ 从 anchor 续跑【没到红钥·又 hit_cap】(budget={args.budget} 也没跑完)")
        print("  ⟹ 不决定性：从 anchor 续跑也撞预算。须看 maxATK 有没有比 k1600 的 24 往上爬")
        print("     （爬=往正路走只是慢；不爬=卡同一墙·非没跑完）。")
    else:
        print(f"  ✗ 从 anchor 续跑【搜尽(saturate·hit_cap=False)也没到红钥】")
        print("  ⟹ 玩家过度解读：那个 anchor 态【续跑搜尽也到不了红钥】=停哪都一样、非没跑完。")
    print("=" * 84)

    # ── Q1：从日志直读（已知·此处复述给玩家对照）──────────────────────────────────
    print("\n【Q1】k1600 是 hit_cap 还是真收敛（直读日志 _dir2_beam_k800_1600.txt）：")
    print("  k800 : found=F hit_cap=False generated=632720<800000 waves=154 → saturate(真收敛·搜尽)")
    print("  k1600: found=F hit_cap=True  generated=800003≈800000 waves=83  → 撞预算上限·没跑完")
    print("  ⟹ Q1 玩家对：k1600 确实 hit_cap 没跑完(只83波·k800跑了154波)。")


if __name__ == "__main__":
    main()
