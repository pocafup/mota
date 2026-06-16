"""【§S33 口径核实·只读·完整版】重建两个 seam 态、摆全状态(含地上剩余)、做支配判定。

核实玩家的质疑："穷尽 HP324 带盾 > navigate HP292 没盾 → 穷尽优" 是不是同口径比较。
本脚本只重建态 + 摆数据 + 跑 Pareto 支配判定；不重跑验证逻辑、不碰产品码、不动 navigate/GA。

口径复刻 seam_astar_smoke：起点=真实存档首次进 MT9(token493)；seam=MT10(1,10)(真落点)；
  穷尽 = search_quotient(cross_floor 限{MT9,MT10}, beam_k=None, distinguish_doors=True)；
  navigate = navigate_to 贪心 GBFS。两者都搜/走到 seam，比较出口态。

产出（回答玩家三问）：
  ① 两个 seam 态的【完整持有态】：HP/ATK/DEF/mdef/金/各色钥匙/道具/位置。
  ② 两个 seam 态的【地上剩余】：MT9(已离开层) + MT10(当前层) 各还剩哪些血瓶/宝石/钥匙/道具(没拿)。
     —— 数据驱动分类(按 items.json pickup 结构)，不写死 id。
  ③ Pareto 支配判定：穷尽的 32 点出口前沿里，有没有任何一点【各维≥】navigate 态(=真支配)？
     若无 → "324>292" 不是支配、是取舍轴 → 穷尽优【未】证成(持钥/地上潜力被换走)。

用法：python -u analysis/seam_caliber_check.py [--max-states 600000] [--nav-maxpops 8000]
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

from analysis.verify_all_checkpoints import build_initial_state, load_tokens   # noqa: E402
from sim.simulator import step, _copy_state                                    # noqa: E402
from solver.quotient import search_quotient, count_floor_blocks, _free_cells   # noqa: E402
from solver.search import _value_map, _ge_all                                  # noqa: E402
from solver.verify import replay                                               # noqa: E402
from ga_navigate import navigate_to                                            # noqa: E402
from vzone import build_zone                                                   # noqa: E402

SEAM = ("MT10", 1, 10)        # §S32 数据真相修正后的真落点（非换层格 1,11）
ALLOWED = {"MT9", "MT10"}     # MT9→seam 段；离段裁掉


def seg_step(state, action):
    ns = step(state, action)
    if ns.current_floor not in ALLOWED:
        ns.dead = True
    return ns


def first_enter_mt9():
    s = build_initial_state()
    tokens = load_tokens()
    for i, tok in enumerate(tokens):
        s = step(s, tok)
        if s.current_floor == "MT9":
            return s, i
    return None, None


def full_state(tag, s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    items = {k: v for k, v in h.items.items() if v}
    print(f"  【{tag}】{s.current_floor}({h.x},{h.y})")
    print(f"     HP={h.hp}  ATK={h.atk}  DEF={h.def_}  MDEF={h.mdef}  金={h.gold}  击杀={h.kill_count}")
    print(f"     钥匙={keys}")
    print(f"     道具={items}")
    print(f"     _single_floor_copy={s._single_floor_copy}（须 False）")


def _classify(idata):
    """数据驱动分类：按 items.json pickup 结构判类型，不写死 id。"""
    if not idata:
        return "其他"
    if idata.get("cls") == "tools" and idata.get("pickup") is None:
        return "钥匙/工具"
    p = idata.get("pickup")
    if not isinstance(p, dict):
        return "其他"
    t = p.get("type")
    if t == "stat" and p.get("stat") == "hp":
        return "血瓶(纯HP)"
    if t == "multi" and any(o.get("stat") == "hp" for o in p.get("ops", ())):
        return "宝石(HP+永久属性)"
    return "其他"


def scan_ground(s, floor_name):
    """扫某层地上【尚未拾取】的道具(按 entities 实时)，分类计数。返回 {类型: {iid: cnt}}。"""
    f = s.floors[floor_name]
    t2i = f._tile_to_item
    db = f._items_db
    out = {}
    for row in f.entities:
        for tile in row:
            if not tile:
                continue
            iid = t2i.get(tile)
            if iid is None:
                continue
            cls = _classify(db.get(iid))
            out.setdefault(cls, {})
            out[cls][iid] = out[cls].get(iid, 0) + 1
    return out


def print_ground(tag, s):
    print(f"  【{tag}】地上剩余（未拾取，按层）：")
    for fl in ("MT9", "MT10"):
        g = scan_ground(s, fl)
        note = "（已离开·但真实路线 seam 后还回 MT9 三次=可后取潜力）" if fl == "MT9" else "（当前所在层·boss 段可取潜力）"
        if not g:
            print(f"     {fl}{note}：无")
            continue
        print(f"     {fl}{note}：")
        for cls in ("血瓶(纯HP)", "宝石(HP+永久属性)", "钥匙/工具", "其他"):
            if cls in g:
                db = s.floors[fl]._items_db
                parts = [f"{iid}×{n}（{db.get(iid,{}).get('name','?')}）" for iid, n in g[cls].items()]
                print(f"        {cls}: {', '.join(parts)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-states", type=int, default=600_000)
    ap.add_argument("--nav-maxpops", type=int, default=8000)
    args = ap.parse_args()

    print("=" * 78)
    print("§S33 口径核实：MT9→seam 两个 seam 态完整状态 + 地上剩余 + Pareto 支配判定")
    print("=" * 78)

    t0 = time.time()
    zone = build_zone()
    print(f"build_zone 就绪 {time.time()-t0:.1f}s", flush=True)

    mt9, idx = first_enter_mt9()
    print(f"\n起点 = 真实存档首次进 MT9：token[{idx}]")
    full_state("MT9 起点", mt9)
    nblk, nfree = count_floor_blocks(mt9)
    print(f"  MT9 缩点：自由块={nblk} 自由格={nfree} 英雄块={len(_free_cells(mt9))}", flush=True)

    # ── ① navigate 贪心 → seam ────────────────────────────────────────────────
    print("\n" + "-" * 78)
    print("① navigate 贪心 GBFS → seam", flush=True)
    tn = time.time()
    seam_nav, moves_nav, reached_nav = navigate_to(mt9, SEAM, zone, step,
                                                   max_pops=args.nav_maxpops, cache=None)
    print(f"  reached={reached_nav} 耗时{time.time()-tn:.1f}s 步数={len(moves_nav)}", flush=True)

    # ── ② 穷尽 search_quotient → seam（取 max-HP 出口，replay 重建全态）──────────
    print("\n" + "-" * 78)
    print("② 穷尽 search_quotient → seam（max-HP 出口 replay 重建）", flush=True)
    tq = time.time()
    res = search_quotient(mt9, SEAM, seg_step, max_states=args.max_states,
                          cross_floor=True, beam_k=None, distinguish_doors=True)
    print(f"  found={res.found} 耗时{time.time()-tq:.1f}s 出口前沿={len(res.goal_frontier)} "
          f"max-HP出口hp={res.final_hp}", flush=True)
    seam_exh = replay(mt9, res.actions, step, _copy_state)
    assert seam_exh.hero.hp == res.final_hp, f"replay hp {seam_exh.hero.hp} != res.final_hp {res.final_hp}"
    print(f"  replay 校验：seam_exh.hp={seam_exh.hero.hp} == res.final_hp ✓", flush=True)

    # ── 完整状态 + 地上剩余 ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("【完整持有态】")
    print("=" * 78)
    if reached_nav:
        full_state("navigate seam", seam_nav)
    print()
    full_state("穷尽 max-HP seam", seam_exh)

    print("\n" + "=" * 78)
    print("【地上剩余（含可后取潜力）】")
    print("=" * 78)
    if reached_nav:
        print_ground("navigate seam", seam_nav)
        print()
    print_ground("穷尽 max-HP seam", seam_exh)

    # ── Pareto 支配判定 ───────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("【Pareto 支配判定：穷尽前沿能不能【真支配】navigate？（含各色钥匙维）】")
    print("=" * 78)
    if reached_nav and res.found:
        nav_vec = _value_map(seam_nav)
        # 穷尽前沿任一点是否各维 >= navigate（=真支配 navigate）
        dominators = [v for v in res.goal_frontier if _ge_all(v, nav_vec)]
        print(f"  navigate 持有向量 = {{k:v for k,v in nav_vec.items() if v}}")
        print(f"  穷尽前沿点数={len(res.goal_frontier)}，其中【各维≥navigate】(真支配)的点数 = {len(dominators)}")
        if not dominators:
            print("  ⟹ 穷尽前沿【没有一点】在所有维度上≥navigate（navigate 的 yellowKey/地上潜力换不回）")
            print("     ⟹ 'HP324>292' 不是支配、是取舍轴 → 穷尽【未】严格优于 navigate")
            # 逐维差：穷尽 max-HP 出口 vs navigate
            exh_vec = _value_map(seam_exh)
            allk = sorted(set(nav_vec) | set(exh_vec))
            print("\n  ── 穷尽 max-HP 出口  减  navigate（正=穷尽多，负=navigate多）──")
            for k in allk:
                d = exh_vec.get(k, 0) - nav_vec.get(k, 0)
                if d:
                    print(f"     {k:18} 穷尽={exh_vec.get(k,0):>5}  nav={nav_vec.get(k,0):>5}  差={d:+}")
        else:
            print("  ⟹ 穷尽前沿存在真支配点 → 穷尽在所有维度≥navigate → 穷尽优(持有维)成立")
            for v in dominators[:3]:
                print(f"     支配点: {{k:val for k,val in v.items() if val}}")

    print("\n" + "=" * 78)
    print("（地上剩余 + 支配判定交叉读：navigate 若 yellowKey/地上血瓶更多 = 携带更多后取潜力，")
    print(" 而真实路线 seam 后回 MT9 三次 → 该潜力可兑现 → 当前 HP 低≠更差）")
    print("=" * 78)


if __name__ == "__main__":
    main()
