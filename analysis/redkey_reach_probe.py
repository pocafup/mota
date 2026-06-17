"""【方向3·红钥段可达性廉价探针】段B 穷尽搜两个多层档都撞 300k cap → found=False 被预算掩盖，
不能判"红钥不可达"。本探针用两件廉价证据把它定死，不再烧 9 分钟穷尽：

  ① 真实路线这一腿（tok454 铁盾刚到手 → tok945 红钥到手）到底跨几层、回访多密？
     —— 直接量"交错回访"的真实跨度，是"线性段能不能咬下红钥"的事实依据。
  ② 从 tok454 真实态，navigate_to 贪心（全 zone、不限层）能不能走到红钥格 MT8(10,2)？
     —— reached=True ⟹ 红钥结构可达，穷尽搜只是太贵（预算/剪枝问题）。
        reached=False ⟹ 贪心被血/结构挡住，红钥很可能真需要先去别层攒属性/钥匙=线性段根本障碍。

只读：复用 extract_zone1_milestones 的明确指名加载、sim.step、ga_navigate.navigate_to、vzone.build_zone。
绝不改产品码。用法：python -u analysis/redkey_reach_probe.py [--max-pops 20000]
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step
from ga_navigate import navigate_to
from vzone import build_zone

REDKEY_CELL = ("MT8", 10, 2)   # 一区唯一红钥（tok945 到手）
TOK_SHIELD = 454               # 铁盾刚到手（MT9(9,7) DEF10→20）
TOK_REDKEY = 945               # 红钥到手


def fmt(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    items = {k: v for k, v in h.items.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 道具={items} kills={h.kill_count} dead={s.dead} won={s.won}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pops", type=int, default=20000, help="navigate_to 弹出护栏（够大=给贪心充分机会）")
    args = ap.parse_args()

    print("=" * 80)
    print("方向3 红钥段可达性探针：真实跨度 + navigate 贪心可达性")
    print("=" * 80)

    tokens, _ = load_tokens()
    print(f"新存档 token 数={len(tokens)}（应=1044）")

    # ── 重放并采集每一步的楼层，定位铁盾态、量真实红钥腿跨度 ──────────────────
    s = build_initial_state()
    floor_at = []  # floor_at[i] = 第 i 个 token 消耗后的 current_floor
    shield_state = None
    for i, tok in enumerate(tokens):
        s = step(s, tok)
        floor_at.append(s.current_floor)
        if i == TOK_SHIELD:
            shield_state = s
        if i == TOK_REDKEY:
            print(f"\n红钥到手态 tok{TOK_REDKEY}：{fmt(s)}")

    print(f"\n铁盾刚到手态 tok{TOK_SHIELD}：{fmt(shield_state)}")
    assert shield_state._single_floor_copy is False, "起点 _single_floor_copy 须 False（跨层安全深拷）"

    # ① 真实红钥腿跨度（tok454+1 .. tok945）：楼层序列 + 去重楼层 + 回访次数
    leg = floor_at[TOK_SHIELD + 1: TOK_REDKEY + 1]
    distinct = sorted(set(leg), key=lambda f: int(f[2:]))
    # 楼层切换次数（相邻不同即一次跨层）
    switches = sum(1 for a, b in zip(leg, leg[1:]) if a != b)
    # 每层被"进入"多少次（current_floor 从别层变成它）
    enters = {}
    prev = shield_state.current_floor
    for f in leg:
        if f != prev:
            enters[f] = enters.get(f, 0) + 1
        prev = f
    print("\n" + "-" * 80)
    print(f"① 真实红钥腿跨度 tok{TOK_SHIELD}→tok{TOK_REDKEY}（{len(leg)} 个 token）")
    print("-" * 80)
    print(f"  涉及楼层（去重）={distinct}  共 {len(distinct)} 层")
    print(f"  楼层切换总次数={switches}（线性单段=0；越大=交错回访越密）")
    print(f"  各层被重新进入次数={enters}")
    # 压缩楼层游程，直观看回访
    runs = []
    pf = None
    for f in [shield_state.current_floor] + leg:
        if f != pf:
            runs.append(f)
            pf = f
    print(f"  楼层游程序列={' → '.join(runs)}")

    # ② navigate 贪心可达性（全 zone、不限层、不缓存=干净对照）
    print("\n" + "-" * 80)
    print(f"② navigate_to 贪心 从铁盾态 → 红钥格 {REDKEY_CELL}（全 zone·max_pops={args.max_pops}）")
    print("-" * 80)
    t0 = time.time()
    zone = build_zone()
    print(f"  build_zone 就绪 {time.time()-t0:.1f}s", flush=True)
    tn = time.time()
    final, moves, reached = navigate_to(shield_state, REDKEY_CELL, zone, step,
                                        max_pops=args.max_pops, cache=None)
    print(f"  reached={reached}  耗时 {time.time()-tn:.1f}s  步数={len(moves)}")
    if reached:
        print(f"  ✓ 红钥结构可达：navigate 终态 {fmt(final)}")
        print("  ⟹ 红钥可达，穷尽搜 found=False 仅因 300k 预算/剪枝不足，非真不可达。")
    else:
        print(f"  ✗ navigate 贪心走不到红钥（max_pops 内）：返回态 {fmt(final)}")
        print("  ⟹ 贪心被血/结构挡住——红钥很可能真需先去别层攒属性/钥匙，线性单段难咬下。")

    print("\n" + "=" * 80)
    print("【结论判读】")
    print("=" * 80)
    print(f"  真实腿跨 {len(distinct)} 层、切换 {switches} 次 → 红钥获取本身就是多层交错回访。")
    print(f"  navigate 可达性={reached} → " +
          ("可达但穷尽太贵（探索预算/剪枝瓶颈）。" if reached
           else "贪心都够不到（结构/属性壁垒）。"))
    print("=" * 80)


if __name__ == "__main__":
    main()
