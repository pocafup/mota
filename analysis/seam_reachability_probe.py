"""【§S32 定生死·只读快探】seam=MT10(1,11) 到底可不可达 + 弱起点 vs 强起点。

§S32 smoke 发现：从【第一次进 MT9 的弱态】(HP248/ATK21/DEF10/无盾) 出发，navigate 与
穷尽 search_quotient 都到不了 seam(found=False·goal_hits=0·状态没爆)。要分清这是
①配置假信号(seam 格不可达=楼梯格判据问题) 还是 ②弱起点真到不了(资源门槛)。

本脚本【不跑 search_quotient·秒级】，只用真实存档重放 + floodfill 出三件铁证：
  ① 真实通关存档【到底有没有】踩过 MT10(1,11)？踩过=seam 构造真实、是真路线必经；
     没踩过=真路线走的是别的楼梯(seam 是 vzone 配对构造)→ 报玩家。
  ② 真实存档每一次站上 MT9 的属性进度(找出"弱首入" vs "强回访"两类 MT9 态)。
  ③ 对【弱首入 MT9】和【最强 MT9 回访】两个态分别 floodfill：
     seam 楼梯 MT9(1,11)、普通楼梯 MT9(1,10)、盾 MT9(9,7) 在不在零损血自由块里。
     (零损血够不到 ≠ 真到不了：还能靠杀怪/开门，但能看出门槛在哪。)

只读·不碰封板件。用法：python -u analysis/seam_reachability_probe.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.verify_all_checkpoints import build_initial_state, load_tokens  # noqa: E402
from sim.simulator import step                                                # noqa: E402
from solver.quotient import _free_cells                                       # noqa: E402

SEAM_CELL = (1, 11)       # MT10 上的 seam 格
STAIR_NORMAL = (1, 10)    # MT9 upFloor(普通 MT9→MT10 楼梯)
STAIR_SEAM = (1, 11)      # MT9 changeFloor(seam 楼梯)
SHIELD_MT9 = (9, 7)       # MT9 铁盾


def hero_t(h):
    keys = {k: v for k, v in h.keys.items() if v}
    return f"HP={h.hp} ATK={h.atk} DEF={h.def_} 钥={keys}"


def main():
    print("=" * 78)
    print("§S32 定生死·只读快探：seam=MT10(1,11) 可达性 + 弱/强 MT9 起点")
    print("=" * 78)

    s = build_initial_state()
    tokens = load_tokens()
    print(f"存档 token 数={len(tokens)}\n")

    mt9_visits = []   # (i, x, y, hp, atk, def_, state_copy_ref)
    mt10_visits = []  # (i, x, y, hp, atk, def_)
    mt10_at_seam = []
    first_mt9_state = None
    mt9_states = {}   # i -> state(浅引用·只读用)

    for i, tok in enumerate(tokens):
        s = step(s, tok)
        cf = s.current_floor
        h = s.hero
        if cf == "MT9":
            mt9_visits.append((i, h.x, h.y, h.hp, h.atk, h.def_))
            mt9_states[i] = s
            if first_mt9_state is None:
                first_mt9_state = s
        elif cf == "MT10":
            mt10_visits.append((i, h.x, h.y, h.hp, h.atk, h.def_))
            if (h.x, h.y) == SEAM_CELL:
                mt10_at_seam.append((i, h.hp, h.atk, h.def_))

    # ── 铁证① 真路线踩没踩过 seam 格 ──
    print("-" * 78)
    print("① 真实通关存档有没有踩过 MT10(1,11)=seam 格？")
    print("-" * 78)
    print(f"  MT10 总访问帧={len(mt10_visits)}  其中站在 (1,11)=seam 的帧={len(mt10_at_seam)}")
    if mt10_at_seam:
        print("  ★踩过！seam=MT10(1,11) 是真实路线必经楼梯落点。各次：")
        for (i, hp, atk, df) in mt10_at_seam[:8]:
            print(f"     token[{i}]  HP={hp} ATK={atk} DEF={df}")
    else:
        print("  ⚠ 真路线【从没站上 MT10(1,11)】→ seam 是 vzone 楼梯配对的构造点，")
        print("    真路线走的是别的 MT9↔MT10 楼梯。下面看 MT10 落点都在哪：")
    # MT10 落点分布(去重计数)
    from collections import Counter
    cells = Counter((x, y) for (_i, x, y, _h, _a, _d) in mt10_visits)
    print(f"  MT10 各落点帧数(top)：{dict(sorted(cells.items(), key=lambda kv:-kv[1])[:10])}")

    # ── 铁证② MT9 属性进度 ──
    print("\n" + "-" * 78)
    print("② 真实存档每次站上 MT9 的属性进度(找弱首入 vs 强回访)")
    print("-" * 78)
    print(f"  MT9 总访问帧={len(mt9_visits)}")
    if mt9_visits:
        first = mt9_visits[0]
        strongest = max(mt9_visits, key=lambda r: (r[5], r[4], r[3]))  # def,atk,hp
        print(f"  首入 MT9：token[{first[0]}] ({first[1]},{first[2]}) "
              f"HP={first[3]} ATK={first[4]} DEF={first[5]}")
        print(f"  最强 MT9：token[{strongest[0]}] ({strongest[1]},{strongest[2]}) "
              f"HP={strongest[3]} ATK={strongest[4]} DEF={strongest[5]}")
        # 是否有"拿了盾(DEF>10)的 MT9 态"
        shielded = [r for r in mt9_visits if r[5] > 10]
        print(f"  DEF>10(已拿盾) 的 MT9 帧数={len(shielded)}"
              + (f"  首个：token[{shielded[0][0]}] DEF={shielded[0][5]}" if shielded else ""))

    # ── 铁证③ floodfill 零损血可达 ──
    print("\n" + "-" * 78)
    print("③ 对弱首入 / 最强 MT9 态 floodfill：seam楼梯(1,11)/普通楼梯(1,10)/盾(9,7) 够不够得到")
    print("-" * 78)

    def check(state, tag):
        free = _free_cells(state)
        h = state.hero
        print(f"  [{tag}] 英雄@({h.x},{h.y})  {hero_t(h)}")
        print(f"     零损血自由块大小={len(free)}")
        for label, cell in (("seam楼梯(1,11)", STAIR_SEAM),
                            ("普通楼梯(1,10)", STAIR_NORMAL),
                            ("盾(9,7)", SHIELD_MT9)):
            inblk = cell in free
            print(f"     {label:14}: {'✓在自由块(零损血够得到)' if inblk else '✗不在自由块(须杀怪/开门或真到不了)'}")

    if first_mt9_state is not None:
        check(first_mt9_state, "弱首入 MT9")
    if mt9_visits:
        strongest_i = max(mt9_visits, key=lambda r: (r[5], r[4], r[3]))[0]
        if strongest_i in mt9_states and mt9_states[strongest_i] is not first_mt9_state:
            check(mt9_states[strongest_i], "最强回访 MT9")

    print("\n" + "=" * 78)
    print("【解读】seam 楼梯格(1,11)在 quotient 里被判【非自由】(换层格)，只能靠")
    print("『站上 MT9(1,11) 踩楼梯落到 MT10(1,11)』触达；故 seam 可达 ⟺ 能走到 MT9(1,11)。")
    print("=" * 78)


if __name__ == "__main__":
    main()
