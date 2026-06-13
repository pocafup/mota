"""只读诊断：定位 C 段 MT33 的 route 真值（入口核对 + 闭环出口完整向量 + 放血溯源）。

重放全程 route，切出 MT33 连续停留段，定位含「全程最低 HP=6 极限态」的那一段（闭环段：
入口格==出口格==(10,1)，route 绕一圈放血 956→6 换 +40 ATK 后回原格下楼去 MT32）。打印该段
轨迹、5 场关键放血(单步损血≥30)、并在 route 离开 MT33 前最后停 (10,1) 处输出完整出口向量
(hp/atk/def/mdef/gold/kill/持有钥匙/持有道具/地图剩余)，供写入 mvp_c.py 的 route_exit
(口径同 mvp_a.py / mvp_b.py)。

地图剩余道具如实全列，并标注哪些是「给 HP 的消耗品」(血瓶类，经 _gives_hp_on_pickup 判定)
——只有血瓶维会进 _route_vec 的比较；本段出口地图只剩 yellowKey(非 HP 消耗品)，故 map 维空。

不改产品代码、不进搜索循环——纯分析。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from diag_mvp_segments import build_initial_state, load_tokens
from sim.simulator import step
from solver.search import _gives_hp_on_pickup

ENTRY_TOKEN = 2894   # 入口：tokens[:2894] 后 MT33(10,1) HP956
EXIT_IDX = 2972      # 出口：离开 MT33 前最后停 (10,1)，HP6


def remaining_all(state):
    """当前层地图上尚未拾取的全部道具计数 + 标注血瓶类。"""
    f = state.floors[state.current_floor]
    t2i = f._tile_to_item
    db = f._items_db
    out = {}
    for row in f.entities:
        for tile in row:
            if tile:
                iid = t2i.get(tile)
                if iid is not None:
                    out[iid] = out.get(iid, 0) + 1
    potion = {k: v for k, v in out.items() if _gives_hp_on_pickup(db.get(k))}
    return out, potion


def snap(idx, s):
    h = s.hero
    rem = remaining_all(s) if s.current_floor == "MT33" else (None, None)
    return dict(idx=idx, floor=s.current_floor, x=h.x, y=h.y, hp=h.hp,
                atk=h.atk, def_=h.def_, mdef=h.mdef, gold=h.gold,
                kc=h.kill_count,
                keys={k: v for k, v in h.keys.items() if v},
                items={k: v for k, v in h.items.items() if v},
                rem_all=rem[0], rem_potion=rem[1])


def main():
    tokens = load_tokens()
    state = build_initial_state()
    hist = [snap(0, state)]  # hist[k] = 执行完 tokens[:k] 后（k 个 token）
    for i, tok in enumerate(tokens):
        state = step(state, tok)
        hist.append(snap(i + 1, state))
    print(f"总 token={len(tokens)}  终态 won={state.won} HP={state.hero.hp}")

    # 切 MT33 连续段（hist idx 口径：hist[k] = tokens[:k] 之后）
    segs = []
    start = None
    for k in range(len(hist)):
        if hist[k]["floor"] == "MT33":
            if start is None:
                start = k
        elif start is not None:
            segs.append((start, k - 1))
            start = None
    if start is not None:
        segs.append((start, len(hist) - 1))

    print(f"\nMT33 连续停留段（共 {len(segs)} 段）:")
    for (a, b) in segs:
        hps = [hist[k]["hp"] for k in range(a, b + 1)]
        print(f"  idx[{a:>4}..{b:>4}] len={b - a:>3}  "
              f"入口({hist[a]['x']},{hist[a]['y']})HP{hist[a]['hp']} "
              f"出口({hist[b]['x']},{hist[b]['y']})HP{hist[b]['hp']}  "
              f"段内 HP min={min(hps)} max={max(hps)}")

    # 入口核对：tokens[:2894] → MT33(10,1) HP956/A114/D70
    print(f"\n入口核对 hist[{ENTRY_TOKEN}]（= tokens[:{ENTRY_TOKEN}] 之后）:")
    e = hist[ENTRY_TOKEN]
    print(f"  {e['floor']}({e['x']},{e['y']}) HP={e['hp']} ATK={e['atk']} "
          f"DEF={e['def_']} 金={e['gold']} kill={e['kc']} keys={e['keys']} "
          f"items={e['items']}")

    # 极限段 = 含 EXIT_IDX 的那段（闭环 idx[2894..2972]）
    seg = next(((a, b) for (a, b) in segs if a <= EXIT_IDX <= b), None)
    if seg is None:
        print(f"\n⚠ 未找到含 idx={EXIT_IDX} 的 MT33 段")
        return
    a, b = seg
    print(f"\n=== MT33 极限段 idx[{a}..{b}] 全轨迹 + 放血溯源 ===")
    prev = None
    for k in range(a, b + 1):
        r = hist[k]
        drop = ""
        if prev is not None and prev["hp"] - r["hp"] >= 30:
            drop = f"  <==放血 {prev['hp']}->{r['hp']} 损{prev['hp'] - r['hp']}"
        star = " <==(10,1)" if (r["x"], r["y"]) == (10, 1) else ""
        low = " <==HP极限" if r["hp"] <= 6 else ""
        print(f"  idx={r['idx']:>4} ({r['x']:>2},{r['y']:>2}) "
              f"HP={r['hp']:>5} ATK={r['atk']:>3} DEF={r['def_']:>3} "
              f"金={r['gold']:>5} kill={r['kc']:>3}{drop}{star}{low}")
        prev = r

    # 出口真值：route 离开 MT33 前最后停 (10,1)（= idx EXIT_IDX）
    print("\n" + "=" * 60)
    print(f"出口真值 hist[{EXIT_IDX}]（写入 mvp_c.py 的 route_exit）:")
    r = hist[EXIT_IDX]
    print(f"  {r['floor']}({r['x']},{r['y']}) HP={r['hp']} ATK={r['atk']} "
          f"DEF={r['def_']} mdef={r['mdef']} 金={r['gold']} kill={r['kc']}")
    print(f"  keys={r['keys']}  items={r['items']}")
    print(f"  地图剩(全)={r['rem_all']}  其中血瓶(进比较)={r['rem_potion']}")
    print("  注：持有 items 全为 constants(fly/I333/book/wand/cross)→按 cls 投影掉；"
          "地图剩 yellowKey 非血瓶→map 维空。")


if __name__ == "__main__":
    main()
