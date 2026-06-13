"""只读诊断：定位 B 段 MT17 的 route 真值（入口核对 + 出口完整向量）。

重放全程 route，切出 MT17 连续停留段，打印每段轨迹；并在 route 离开 MT17 前
最后一次停 (2,11) 处输出完整出口向量(hp/atk/def/gold/kill/持有钥匙/地图剩余道具)，
供写入 mvp_b.py 的 route_exit（口径同 mvp_a.py）。

地图剩余道具如实全列（钥匙/宝石/血瓶都数），并标注哪些是「给 HP 的消耗品」(血瓶类，
经 _gives_hp_on_pickup 判定)——只有血瓶维会进 _route_vec 的比较。

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
    rem = remaining_all(s) if s.current_floor == "MT17" else (None, None)
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

    # 切 MT17 连续段（hist idx 口径：hist[k] = tokens[:k] 之后）
    segs = []
    start = None
    for k in range(len(hist)):
        if hist[k]["floor"] == "MT17":
            if start is None:
                start = k
        elif start is not None:
            segs.append((start, k - 1))
            start = None
    if start is not None:
        segs.append((start, len(hist) - 1))

    print(f"\nMT17 连续停留段（共 {len(segs)} 段）:")
    for (a, b) in segs:
        print(f"  idx[{a:>4}..{b:>4}] len={b - a:>3}  "
              f"入口({hist[a]['x']},{hist[a]['y']}) 出口({hist[b]['x']},{hist[b]['y']})")

    # 入口核对：用户给 tokens[:1462] → MT17(5,11) HP655/A44/D32
    print("\n入口核对 hist[1462]（= tokens[:1462] 之后）:")
    e = hist[1462]
    print(f"  {e['floor']}({e['x']},{e['y']}) HP={e['hp']} ATK={e['atk']} "
          f"DEF={e['def_']} 金={e['gold']} kill={e['kc']} keys={e['keys']}")

    # 逐段打印轨迹（聚焦含 1462 / 1499 的段）
    for (a, b) in segs:
        print(f"\n=== MT17 段 idx[{a}..{b}] 全轨迹 ===")
        for k in range(a, b + 1):
            r = hist[k]
            mark = ""
            if r["rem_potion"]:
                mark = "  地图剩血瓶=" + " ".join(
                    f"{kk}={vv}" for kk, vv in sorted(r["rem_potion"].items()))
            star = " <==(2,11)" if (r["x"], r["y"]) == (2, 11) else ""
            print(f"  idx={r['idx']:>4} ({r['x']:>2},{r['y']:>2}) "
                  f"HP={r['hp']:>5} ATK={r['atk']:>3} DEF={r['def_']:>3} "
                  f"金={r['gold']:>5} kill={r['kc']:>2} keys={r['keys']}"
                  f"{mark}{star}")

    # 出口真值：route 离开 MT17 前最后一次停 (2,11)
    print("\n" + "=" * 60)
    print("候选出口（每个 MT17 段最后一格 + 该段内最后一次 (2,11)）:")
    for (a, b) in segs:
        # 段内最后一次出现 (2,11)
        last_211 = None
        for k in range(a, b + 1):
            if (hist[k]["x"], hist[k]["y"]) == (2, 11):
                last_211 = k
        tail = hist[b]
        print(f"  段[{a}..{b}] 末格 idx={tail['idx']} ({tail['x']},{tail['y']}) "
              f"HP={tail['hp']} ATK={tail['atk']} DEF={tail['def_']}")
        if last_211 is not None:
            r = hist[last_211]
            print(f"      段内最后 (2,11): idx={r['idx']} HP={r['hp']} "
                  f"ATK={r['atk']} DEF={r['def_']} mdef={r['mdef']} "
                  f"金={r['gold']} kill={r['kc']} "
                  f"keys={r['keys']} items={r['items']} "
                  f"地图剩(全)={r['rem_all']} 血瓶={r['rem_potion']}")


if __name__ == "__main__":
    main()
