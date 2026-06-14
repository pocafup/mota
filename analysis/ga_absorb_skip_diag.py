"""【诊断·一次性】navigate_to 吸收语义改前改后对照（docs/handoff §S8 核心验证门）。

只读不改产品码：跑 navigate_to(start, 盾) 这条腿两遍——
  · 改后＝现产品行为（_absorb skip_potential=True，潜力标的血瓶/钥匙留地上）；
  · 改前＝mock 强制 skip_potential=False（贪婪吸光一切，复现 §S8 缺陷行为）。
对照：reached/步数、ATK/DEF/HP、手里 keys、全图地上钥匙（尤其 MT4 那 3 把在不在）。
判据（本棒成败）：改后【仍吸剑→ATK 仍被提】+【不吸 MT4 钥匙→keys 不增、MT4 钥匙留地上】。
cache=None 隔离（两种语义绝不共享缓存）。
"""
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

from probe_crossfloor import build_start
from sim.simulator import step, _KEY_ITEMS
from solver.beam import build_future_roster
from vzone import build_zone
from big_item_pull import detect_big_items
import ga_navigate
from ga_navigate import navigate_to
from solver.quotient import _absorb as real_absorb


def ground_keys(state):
    """各已载层地上仍在的钥匙 [(fid,x,y,iid)]（被吸/被用的置 0 自动剔）。"""
    t2i = state.floor._tile_to_item
    out = []
    for fid, fl in state.floors.items():
        for y, row in enumerate(fl.entities):
            for x, tile in enumerate(row):
                if tile and t2i.get(tile) in _KEY_ITEMS:
                    out.append((fid, x, y, t2i[tile]))
    return out


def report(label, s, final, moves, reached, shield):
    print(f"\n===== {label} =====")
    print(f"navigate_to(start, 盾{shield})   reached={reached}   步数={len(moves)}")
    print(f"  ATK {s.hero.atk}->{final.hero.atk}    DEF {s.hero.def_}->{final.hero.def_}"
          f"    HP {s.hero.hp}->{final.hero.hp}")
    print(f"  手里 keys {dict(s.hero.keys)} -> {dict(final.hero.keys)}")
    gk = ground_keys(final)
    print(f"  全图地上钥匙 {dict(Counter(i for *_, i in gk))}")
    print(f"  其中 MT4 地上钥匙 {[(x, y, i) for f, x, y, i in gk if f == 'MT4']}")


def absorb_block_compare():
    """开局自由块 _absorb 直接对照（绕开"门挡路"干扰，验【吸收语义机制本身】对不对）：
    同一开局块分别 skip=False(贪婪) / skip=True(留潜力)，看非潜力(攻防/宝石→ATK/DEF)吸没吸、
    潜力(钥匙→keys / 血瓶→HP)留没留。这一步不依赖开门，纯测 _absorb 过滤逻辑。"""
    from solver.quotient import _absorb
    s, _ = build_start()
    print("\n===== 开局自由块 _absorb 直接对照（验吸收语义机制本身，不受开门干扰）=====")
    print(f"起点 {s.current_floor}({s.hero.x},{s.hero.y})  ATK{s.hero.atk} DEF{s.hero.def_} "
          f"HP{s.hero.hp} keys{dict(s.hero.keys)}")
    sf, mf = _absorb(s, step, skip_potential=False)
    print(f"  skip=False(贪婪吸光): ATK{sf.hero.atk} DEF{sf.hero.def_} HP{sf.hero.hp} "
          f"keys{dict(sf.hero.keys)} items{dict(sf.hero.items)} 步{len(mf)}")
    st, mt = _absorb(s, step, skip_potential=True)
    print(f"  skip=True (留潜力)  : ATK{st.hero.atk} DEF{st.hero.def_} HP{st.hero.hp} "
          f"keys{dict(st.hero.keys)} items{dict(st.hero.items)} 步{len(mt)}")
    print("  判据：非潜力(ATK/DEF/宝石)两者都该吸；潜力(keys/HP血瓶)只 False 吸、True 留。")


def main():
    absorb_block_compare()   # 先验吸收语义机制本身（不受门挡路干扰）
    s, _ = build_start()
    zone = build_zone()
    roster = build_future_roster(s)
    big_cells, tau, ranked = detect_big_items(zone, roster, s)
    shield = next((c for (drp, c, da, dd) in ranked if c in big_cells and dd > 0), None)
    print(f"盾目标格 = {shield}    起点 keys = {dict(s.hero.keys)}")
    gk0 = ground_keys(s)
    print(f"起点已载层地上钥匙 {dict(Counter(i for *_, i in gk0))}  "
          f"MT4 {[(x, y, i) for f, x, y, i in gk0 if f == 'MT4']}")

    # 改后＝现产品行为（skip_potential=True 硬编码在 navigate_to）
    fa, ma, ra = navigate_to(s, shield, zone, step, cache=None)
    report("改后(skip_potential=True，留潜力)", s, fa, ma, ra, shield)

    # 改前＝mock 强制贪婪吸光（复现 §S8 缺陷）
    def forced(state, step_fn, skip_potential=True):
        return real_absorb(state, step_fn, skip_potential=False)
    with patch.object(ga_navigate, "_absorb", forced):
        fb, mb, rb = navigate_to(s, shield, zone, step, cache=None)
    report("改前(skip_potential=False，贪婪吸光)", s, fb, mb, rb, shield)


if __name__ == "__main__":
    main()
