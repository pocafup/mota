"""【§S52·血瓶增益项验证】测"位置感知的未来血瓶增益"能否把窄 beam 从 84 拨向 324。

诊断（project_s52_phi_validation）：我的廉价 Φ 只算损血、零血瓶增益、且位置盲 → score≈纯 hp=84。
最优路线终局 324>起点 248=靠银行血瓶（蓝瓶 MT10(11,11)+200 是主力）。本探针只测【血瓶增益项】：
  score = hp + gain(state)，对照纯 hp(84)/精确 V(324) 两锚点。

gain 三档（保真度/成本递增）：
  blind   = Σ 所有未收血瓶 HP（位置盲·最便宜·预测≈84 因绕路态/非绕路态同 gain）
  free    = Σ {未收血瓶: 其格 ∈ _free_cells(state)（英雄零代价自由块·清怪开门后扩大）}（位置感知·当前层）
  free_xf = free + Σ 其它层未收血瓶 HP（位置感知当前层 + 跨层 generous）

★红线：不用距离（玩家否决距离引导）；可达=清怪门控的 floodfill(_free_cells)·非距离。血瓶值读 items.json。
零产品码改动·纯 beam_score_fn 注入。
"""
import json
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

from analysis.seam_astar_smoke import first_enter_mt9, SEAM, seg_step  # noqa: E402
from sim.simulator import _load_floor_if_needed                       # noqa: E402
from solver.quotient import search_quotient, _free_cells              # noqa: E402
from solver.search import _gives_hp_on_pickup                         # noqa: E402

DISTINGUISH_DOORS = True
_DB = json.loads((ROOT / "data" / "games51" / "items.json").read_text(encoding="utf-8"))


def enumerate_potions(start, floors):
    """段内血瓶格全集：[(floor,x,y,hp)]。"""
    out = []
    for f in floors:
        if not _load_floor_if_needed(start, f):
            continue
        fl = start.floors[f]
        for y in range(len(fl.entities)):
            for x in range(len(fl.entities[y])):
                iid = fl._tile_to_item.get(fl.entities[y][x])
                if iid and _gives_hp_on_pickup(_DB.get(iid)):
                    eff = _DB[iid]["pickup"]
                    base = eff.get("base", eff.get("delta", 0))
                    hp = base * fl.ratio if eff.get("ratio_scaled") else base
                    out.append((f, x, y, hp))
    return out


def _uncollected(state, potions):
    """未收血瓶 [(floor,x,y,hp)]：该格 entities 仍是血瓶 tile（!=0）。未 load 层→当作还在。"""
    out = []
    for (f, x, y, hp) in potions:
        fl = state.floors.get(f)
        if fl is None or fl.entities[y][x] != 0:
            out.append((f, x, y, hp))
    return out


def make_scorers(potions):
    def blind(state):
        return float(state.hero.hp) + sum(hp for (_f, _x, _y, hp) in _uncollected(state, potions))

    def free(state):
        h = state.hero
        cur = h.current_floor if hasattr(h, "current_floor") else state.current_floor
        free_cells = _free_cells(state)
        g = 0.0
        for (f, x, y, hp) in _uncollected(state, potions):
            if f == state.current_floor and (x, y) in free_cells:
                g += hp
        return float(h.hp) + g

    def free_xf(state):
        free_cells = _free_cells(state)
        g = 0.0
        for (f, x, y, hp) in _uncollected(state, potions):
            if f == state.current_floor:
                if (x, y) in free_cells:
                    g += hp
            else:
                g += hp   # 跨层 generous
        return float(state.hero.hp) + g

    return [("hp+blind(位置盲)", blind),
            ("hp+free(自由可达·当层)", free),
            ("hp+free_xf(自由可达+跨层gen)", free_xf)]


def run(start, beam_k, score_fn, tag):
    t0 = time.time()
    res = search_quotient(start, SEAM, seg_step, max_states=600_000,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=DISTINGUISH_DOORS,
                          beam_score_fn=score_fn, beam_diversity="stairs")
    secs = time.time() - t0
    if not res.found:
        print(f"  k={beam_k:<3} {tag:<30} {secs:5.1f}s  ✗没搜通  cut={res.beam_cut_total}")
        return None
    fr = res.goal_frontier
    mh = max(v.get("hp", 0) for v in fr)
    ma = max(v.get("atk", 0) for v in fr)
    md = max(v.get("def", 0) for v in fr)
    print(f"  k={beam_k:<3} {tag:<30} {secs:5.1f}s  found cut={res.beam_cut_total:<5} "
          f"fp={res.distinct_fingerprints:<5} 前沿{len(fr):<3} maxHP={mh:<4} maxATK={ma} maxDEF={md}")
    return mh


def main():
    start, idx = first_enter_mt9()
    h0 = start.hero
    print("=" * 96)
    print(f"§S52 血瓶增益项验证 · 起点 MT9({h0.x},{h0.y}) HP={h0.hp} → seam{SEAM} "
          f"| 锚点 纯hp=84 精确V=324 @k8")
    print("=" * 96)
    potions = enumerate_potions(start, ["MT9", "MT10"])
    print(f"血瓶 {len(potions)} 瓶 总HP={sum(p[3] for p in potions):.0f}: "
          f"{[(f, x, y, int(hp)) for (f, x, y, hp) in potions]}")
    print(f"起点 gain 自检: blind={make_scorers(potions)[0][1](start)-h0.hp:.0f} "
          f"free={make_scorers(potions)[1][1](start)-h0.hp:.0f} "
          f"free_xf={make_scorers(potions)[2][1](start)-h0.hp:.0f}")

    scorers = make_scorers(potions)
    for bk in (8, 24, 64):
        print(f"\n── beam_k={bk} ──")
        run(start, bk, lambda s: float(s.hero.hp), "纯hp(锚)")
        for tag, fn in scorers:
            run(start, bk, fn, tag)

    print("\n" + "=" * 96)
    print("判读：free/free_xf 在 k=8 是否 >84（拨向 324）→ 位置感知血瓶增益有效、廉价档活；")
    print("      若三档都≈84 → 位置感知不够、须并入损血项或升档（如实报玩家）。")
    print("=" * 96)


if __name__ == "__main__":
    main()
