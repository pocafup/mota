"""【方向2·path-loss beam 探针·§S41】把 beam 排序键从 V_boss(hp+delta·只算 boss 段损血)
换成 path-loss(hp − Φ_total·算【剩余 9 层全怪】损血上界)，跑 beam 看能否破红钥 basin。

三文件分工（互不破坏·全零产品码）：
  · dir2_redkey_beam_probe.py    = §S40 V_boss(hp+delta) 基线（对照·不动）
  · dir2_redkey_pathloss_probe.py= §S41 可行性评估脚本（产出 gΦ=612/204·只读诊断·不动）
  · dir2_redkey_pathloss_beam.py = 本文件：把评估坐实的 path-loss 当 beam 排序键正式跑 k400

§S40 病根（玩家纠正）= delta 只算 boss 段（+1 属性≈+60），漏算路上损血 → 排序里
  "一瓶血 +400 碾压属性 +60" → beam 拿有代价的血而非先攒属性、锁在 ~9000 态 basin。
  path-loss 让属性值回它真实的"全段省血"价值（评估实测 +1ATK 省血 584~612 >> 血瓶400）
  → beam 才肯先攒属性走出 basin。

口径（§S41·方案 A 替换 delta）：
  Φ_total(a,d) = 铁盾态(tok454)后【9 层剩余怪】每只 compute_combat 损血加总（引擎实算·上界）。
  · 剩余怪 = 各层现存 entities（已打的怪 replay 时已从 entities 移除）→ 天然 = 剩余路径怪集（探查=85只）。
    ★不用 afford 可达过滤（那会引入路线/可达依赖·违反 §S41 "Φ 须无路线依赖无惰性"）→ 取所有现存怪。
  · 本段全怪【无 special】（探查坐实）→ Φ 与 HP_in 无关、无位置依赖 = 干净纯 (a,d) 表（比 delta 还干净）。
  · 损血用 compute_combat（与 solver/beam._combat_damage 在无 special 段完全等价·口径一致）。
  · 打不动怪（hero_atk≤mon_def·本段仅 MT8 两 yellowGuard def22=红钥门守卫）：用"刚好可打
    (atk=mon_def+1)"的损血当惩罚（纯怪属性算出·无魔法数）→ 把"破红钥先攒 ATK 过 22"编进排序键。
  · 排序键 = hp − Φ_total(atk,def)。高 = 高血 + 全段损血少 = 过 boss + 拿红钥潜力大。
  · 上界（全怪=必打集上界·实打打折）→ 只用其【梯度方向】（属性↑→Φ↓恒成立）引导攒属性，不追最优。
  · 步长 1 密网格直查（每点 compute_combat 极便宜）→ 精确捕捉 yellowGuard 等强台阶，胜稀疏网格插值。

甲'三护栏（同 §S40 beam_probe）：① 排序键挂【现成 beam_score_fn 钩子】= 零产品码改动
  （search_quotient/beam.py 一字未动 → beam 47 守卫零回归【自明】）；② beam_diversity="stairs"
  分坑保 climber；③ goal_cell + ALLOWED 参数化。

只读：复用 build_initial_state/load_tokens/step/_load_floor_if_needed/_build_monster/compute_combat/
  search_quotient，绝不改产品码。
用法：python -u analysis/dir2_redkey_pathloss_beam.py [--beam-k 400] [--max-states 300000]
      [--allowed MT1,...] [--diversity stairs] [--phi-only]（仅 dump Φ 自检不跑 beam）
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step, _load_floor_if_needed, _build_monster
from sim.combat import compute_combat, PlayerState
from solver.quotient import search_quotient
from solver.search import _gives_hp_on_pickup
from extract.encode_route import write_h5route

_ITEM_DB = json.loads((ROOT / "data" / "games51" / "items.json").read_text(encoding="utf-8"))

TOK_SHIELD = 454               # 铁盾刚到手 MT9(9,7) HP166 ATK22 DEF20 钥黄2蓝1（§S36 坐实）
REDKEY_CELL = ("MT8", 10, 2)   # 一区唯一红钥（tok945 到手）= 本段 goal
REAL_LEG_FLOORS = ["MT1", "MT3", "MT4", "MT5", "MT6", "MT7", "MT8", "MT9", "MT10"]  # §S36 真实腿 9 层

# ── Φ_total 密网格范围（铁盾 ATK22/DEF20 起步·上界宽到远超红钥所需）──
A_LO, A_HI = 15, 45
D_LO, D_HI = 10, 45
_BIG_HP = 10 ** 7              # 算 Φ 用大 HP（本段无吸血怪→损血与 HP 无关；纯保险）


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _monster_loss(hero_atk, hero_def, mon, mdef):
    """单怪 compute_combat 损血。打不动(hero_atk≤mon_def)→用刚好可打(atk=mon_def+1)的损血当惩罚
    （纯怪属性算出·无魔法数·平滑衔接台阶·把'破门先攒 ATK 过守卫 def'编进排序）。"""
    r = compute_combat(PlayerState(hp=_BIG_HP, atk=hero_atk, def_=hero_def, mdef=mdef), mon)
    if r.damage is not None:
        return r.damage
    r2 = compute_combat(PlayerState(hp=_BIG_HP, atk=mon.def_ + 1, def_=hero_def, mdef=mdef), mon)
    return r2.damage if r2.damage is not None else mon.hp


def enumerate_roster(start, floors):
    """枚举 start(铁盾态)后 floors 各层现存怪（已打的已移除）= 剩余路径怪集。返回 [(floor, mid)]。
    取所有现存 entities 怪·不按可达过滤（§S41：Φ 须无路线/可达依赖）。"""
    roster = []
    for f in floors:
        if not _load_floor_if_needed(start, f):
            print(f"  ⚠ {f} 加载失败(文件缺)")
            continue
        fl = start.floors[f]
        ent = fl.entities
        for y in range(len(ent)):
            for x in range(len(ent[y])):
                mid = fl._tile_to_enemy.get(ent[y][x])
                if mid:
                    roster.append((f, mid))
    return roster


def build_phi_table(start, floors):
    """预存 Φ_total(a,d) 密网格：剩余怪集每只 compute_combat 损血加总。返回 (table, roster, mons, mdef)。"""
    roster = enumerate_roster(start, floors)
    mons = [_build_monster(start, mid) for _, mid in roster]
    mdef = start.hero.mdef
    table = {}
    for a in range(A_LO, A_HI + 1):
        for d in range(D_LO, D_HI + 1):
            table[(a, d)] = sum(_monster_loss(a, d, m, mdef) for m in mons)
    return table, roster, mons, mdef


def phi_total(atk, def_, table):
    return table[(_clamp(atk, A_LO, A_HI), _clamp(def_, D_LO, D_HI))]


def enumerate_potions(start, floors):
    """段内血瓶格全集：[(floor,x,y,hp)]。HP 当量引擎实算·读 items.json·零魔法数
    （pickup 给 hp 的道具=红/蓝瓶·_gives_hp_on_pickup 数据驱动判定·ratio 缩放跟 floor.ratio）。"""
    out = []
    for f in floors:
        if not _load_floor_if_needed(start, f):
            continue
        fl = start.floors[f]
        for y in range(len(fl.entities)):
            for x in range(len(fl.entities[y])):
                iid = fl._tile_to_item.get(fl.entities[y][x])
                if iid and _gives_hp_on_pickup(_ITEM_DB.get(iid)):
                    eff = _ITEM_DB[iid]["pickup"]
                    base = eff.get("base", eff.get("delta", 0))
                    hp = base * fl.ratio if eff.get("ratio_scaled") else base
                    out.append((f, x, y, hp))
    return out


def potion_bank(state, potions):
    """位置盲血瓶银行项：Σ【未收】血瓶 HP（该格 entities 仍是瓶 tile != 0；未 load 层=当作还在）。
    §S52 诊断坐实 equiv_hp/path-loss Φ 对【地图银行着的血瓶 HP】盲 → 加此项让 beam 看到未收瓶。
    位置盲（非距离·非可达·只数瓶值）= 守红线（玩家否决距离引导）·O(#瓶) 极便宜。
    ⚠数学性质：hp+bank 在拿瓶时不变（拿瓶 hp+=v、bank-=v）→ =起点hp+总瓶−已损 = 按【最小化总损血】排序。"""
    g = 0.0
    for (f, x, y, hp) in potions:
        fl = state.floors.get(f)
        if fl is None or fl.entities[y][x] != 0:
            g += hp
    return g


def make_seg_step(allowed):
    """把搜索框在 allowed 楼层集：踏出本段的子态置 dead 裁掉（同 seg_chain_verify）。"""
    aset = set(allowed)

    def seg_step(state, action):
        ns = step(state, action)
        if ns.current_floor not in aset:
            ns.dead = True
        return ns
    return seg_step


def fmt(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    items = {k: v for k, v in h.items.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 道具={items} kills={h.kill_count} dead={s.dead} won={s.won}")


def replay_to_token(tok_idx):
    s = build_initial_state()
    tokens, _ = load_tokens()
    for t in tokens[:tok_idx + 1]:
        s = step(s, t)
    return s


def export_h5route(res, tag):
    """found=True 时：拼 tokens[:455] 前缀（开局→铁盾）+ beam RULD → 完整 .h5route + sim 独立重放自检。"""
    tokens, outer = load_tokens()
    prefix = list(tokens[:TOK_SHIELD + 1])
    beam_acts = list(res.actions)
    full = prefix + beam_acts
    print(f"\n  ── 导出 h5route + sim 独立重放自检 ──")
    print(f"  full = 前缀{len(prefix)}(开局→铁盾) + beam{len(beam_acts)}(铁盾→红钥) = {len(full)} token")
    s = build_initial_state()
    for t in full:
        s = step(s, t)
        if s.dead:
            break
    gf, gx, gy = REDKEY_CELL
    reached = (s.current_floor == gf and (s.hero.x, s.hero.y) == (gx, gy) and not s.dead)
    print(f"  重放终态: {fmt(s)}")
    if not reached:
        print(f"  ✗ 重放未停在红钥格 {REDKEY_CELL} → 不导出（链路须排查·别给玩家坏文件）")
        return None
    meta = {"name": outer.get("name", "51"), "version": outer.get("version", "Ver 3.0"),
            "hard": outer.get("hard", ""), "seed": outer.get("seed")}
    out_path = ROOT / f"dir2_redkey_pathloss_fromstart_{tag}.h5route"
    write_h5route(out_path, full, meta)
    print(f"  ✓ sim 重放走到红钥格 → 已导出 {out_path.name}")
    return out_path


def export_halfway_h5route(best_acts, tag):
    """found=False 时：导【半截】= beam 跑到的"最接近破门"grind 态 + sim 独立重放自检。"""
    if not best_acts or best_acts.get("acts") is None:
        print("\n  ✗ 无 beam 动作串可导半截（on_admit 未记到态）")
        return None
    tokens, outer = load_tokens()
    prefix = list(tokens[:TOK_SHIELD + 1])
    beam_acts = list(best_acts["acts"])
    full = prefix + beam_acts
    snap = best_acts["snap"]
    print(f"\n  ── 导出【半截】h5route(beam 最接近破门态)+ sim 独立重放自检 ──")
    print(f"  锚点态(on_admit) = {snap[0]}({snap[1]},{snap[2]}) ATK={snap[3]} DEF={snap[4]} HP={snap[5]}")
    print(f"  full = 前缀{len(prefix)} + beam{len(beam_acts)} = {len(full)} token")
    s = build_initial_state()
    for t in full:
        s = step(s, t)
        if s.dead:
            break
    print(f"  重放终态: {fmt(s)}")
    ok = (s.current_floor == snap[0] and (s.hero.x, s.hero.y) == (snap[1], snap[2])
          and s.hero.atk == snap[3] and s.hero.def_ == snap[4]
          and s.hero.hp == snap[5] and not s.dead)
    meta = {"name": outer.get("name", "51"), "version": outer.get("version", "Ver 3.0"),
            "hard": outer.get("hard", ""), "seed": outer.get("seed")}
    out_path = ROOT / f"dir2_redkey_pathloss_halfway_{tag}.h5route"
    write_h5route(out_path, full, meta)
    flag = "✓" if ok else "⚠ 重放与锚点不符"
    print(f"  {flag} 已导出半截 {out_path.name}（seed={meta['seed']}）")
    print(f"    ⚠ 半截：beam 卡在 ATK{snap[3]}/DEF{snap[4]}、没破红钥门 → 回放走到 grind 态停、非通关")
    return out_path


def run_one(start, goal, allowed, beam_k, max_states, diversity, table, potions=None):
    """跑一次 path-loss 引导段搜索 + 各层进度统计。返回 res。
    potions=None → §S42 基线 hp−Φ（字节级不变·零回归）；
    potions=[...] → hp + 银行项 − Φ（让 beam 看到地图未收血瓶 HP）。"""
    seg_step = make_seg_step(allowed)

    if potions is None:
        def score_fn(state):
            h = state.hero
            return h.hp - phi_total(h.atk, h.def_, table)
    else:
        def score_fn(state):
            h = state.hero
            return h.hp + potion_bank(state, potions) - phi_total(h.atk, h.def_, table)

    best = defaultdict(lambda: {"atk": 0, "def": 0, "hp": 0, "V": -10**18, "n": 0})
    best_acts = {"key": (-1, -1), "acts": None, "snap": None}

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
        v = score_fn(child)
        if v > b["V"]:
            b["V"] = v
        k = (h.atk, h.hp)
        if k > best_acts["key"]:
            best_acts["key"] = k
            best_acts["acts"] = _acts
            best_acts["snap"] = (child.current_floor, h.x, h.y, h.atk, h.def_, h.hp)

    t0 = time.time()
    res = search_quotient(start, goal, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=True,
                          beam_score_fn=score_fn, beam_diversity=diversity,
                          on_admit=on_admit)
    res._secs = time.time() - t0
    res._best_by_floor = dict(best)
    res._best_acts = best_acts
    return res


def dump_phi_selfcheck(table, roster, mons, mdef):
    """Φ 自检：怪集统计 + 几档 Φ + 单调性 + ΔΦ 校验（复现探查 §S41：85 怪/ΔΦ(+1ATK@25,24)=584）。"""
    per_floor = defaultdict(Counter)
    for f, mid in roster:
        per_floor[f][mid] += 1
    print(f"\n Φ_total 自检：剩余怪集 = {len(roster)} 只  mdef={mdef}")
    for f in REAL_LEG_FLOORS:
        if per_floor[f]:
            print(f"   {f:>5}: {dict(per_floor[f])}")
    specials = {m.id: m.special for m in mons if m.special}
    print(f"   带 special 的怪种: {specials if specials else '无（Φ 与 HP 无关·纯(a,d)表）'}")
    print("\n Φ_total(a,d) 几档（看 Φ 主导的属性偏好）：")
    for a in (18, 22, 24, 25, 26, 27, 30, 33):
        row = "  ".join(f"d{d}:{phi_total(a, d, table):>6}" for d in (15, 20, 24, 27))
        print(f"   ATK{a:>2}:  {row}")
    da = phi_total(25, 24, table) - phi_total(26, 24, table)
    dd = phi_total(25, 24, table) - phi_total(25, 25, table)
    print(f"\n ΔΦ(+1ATK @ATK25→26,DEF24) = {da}（探查=584·>血瓶400 → 攒属性压过拿血）")
    print(f" ΔΦ(+1DEF @DEF24→25,ATK25) = {dd}（探查=186）")


def report_res(res, bk, tag, export_tag):
    """打印一组 beam 结果 + 各层进度 + 导 h5route。tag=对照标签·export_tag=文件名后缀。"""
    print(f"\n  ── [{tag}] ──")
    print(f"  found={res.found}  耗时={res._secs:.1f}s  hit_cap={res.hit_cap}")
    print(f"  distinct_fp={res.distinct_fingerprints}  expanded={res.states_expanded} "
          f"generated={res.states_generated}  waves={res.n_waves}")
    print(f"  goal_hits={res.goal_hits}  前沿={len(res.goal_frontier)}  "
          f"beam_cut_total={res.beam_cut_total}  overflow_waves={res.beam_overflow_waves}")
    print(f"  fp_by_floor={dict(res.fp_by_floor)}")
    print("\n  ── 各层【到达过】最优属性（on_admit·看 beam 把队伍推到哪）──")
    for f in sorted(res._best_by_floor, key=lambda x: int(x[2:])):
        b = res._best_by_floor[f]
        print(f"    {f:>5}: n={b['n']:>6}  maxATK={b['atk']}  maxDEF={b['def']}  "
              f"maxHP={b['hp']}  bestV={b['V']:>10.0f}")
    if res.found:
        print(f"\n  ★ 走到红钥！max-HP 出口 HP={res.final_hp}")
        print("  ⟹ path-loss 引导让 9 层中段【可处理】→ 方向2 路通（量损待对照）。")
        export_h5route(res, export_tag)
    else:
        mt8 = res._best_by_floor.get("MT8")
        reach8 = f"到过 MT8(maxATK{mt8['atk']}/DEF{mt8['def']}/HP{mt8['hp']})" if mt8 else "没到过 MT8"
        print(f"\n  ✗ 没走到红钥（{reach8}）。hit_cap={res.hit_cap}")
        print("  ⟹ 看各层 maxATK 有没有从 §S40 卡的 24-25 往上攒（思路扭过来的直接信号）。")
        export_halfway_h5route(res._best_acts, export_tag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beam-k", type=str, default="400", help="beam 上限（逗号分隔=扫多个）")
    ap.add_argument("--max-states", type=int, default=300_000,
                    help="生成上限（§S36 穷尽撞 300k cap·同预算对照）")
    ap.add_argument("--allowed", type=str, default=",".join(REAL_LEG_FLOORS),
                    help="段楼层集（默认=§S36 真实腿 9 层）")
    ap.add_argument("--diversity", type=str, default="stairs",
                    choices=["none", "floor", "stairs"], help="beam 分坑保护维")
    ap.add_argument("--phi-only", action="store_true", help="仅 dump Φ 自检不跑 beam")
    ap.add_argument("--potion-bank", action="store_true",
                    help="§S52：每 beam_k 多跑一组 hp+地图血瓶银行项−Φ（对照基线·让 beam 看到未收瓶 HP）")
    args = ap.parse_args()

    allowed = [f.strip() for f in args.allowed.split(",") if f.strip()]
    diversity = None if args.diversity == "none" else args.diversity
    beam_ks = [int(x) for x in args.beam_k.split(",") if x.strip()]

    print("=" * 84)
    print("方向2 path-loss：hp − Φ_total(全段9层怪损血上界) 引导 beam → 铁盾态穿 9 层拿红钥")
    print("=" * 84)

    start = replay_to_token(TOK_SHIELD)
    assert start._single_floor_copy is False, "起点 _single_floor_copy 须 False（跨层安全深拷）"
    print(f"铁盾起点 tok{TOK_SHIELD}：{fmt(start)}")
    print(f"目标红钥格 = {REDKEY_CELL}   段楼层({len(allowed)}) = {allowed}")
    print(f"排序键 = path-loss(§S41) = hp − Φ_total(atk,def)   分坑维 = {diversity}")

    t0 = time.time()
    table, roster, mons, mdef = build_phi_table(start, allowed)
    print(f"\n Φ_total 密网格已建：ATK[{A_LO},{A_HI}]×DEF[{D_LO},{D_HI}]  "
          f"({(A_HI-A_LO+1)*(D_HI-D_LO+1)} 点)  耗时 {time.time()-t0:.1f}s")
    dump_phi_selfcheck(table, roster, mons, mdef)

    if args.phi_only:
        print("\n--phi-only：仅 dump Φ 自检，不跑 beam。")
        return

    potions = enumerate_potions(start, allowed) if args.potion_bank else None
    if potions is not None:
        tot = sum(p[3] for p in potions)
        print(f"\n 血瓶银行项 ON（§S52）：段内未收血瓶 {len(potions)} 瓶 总HP当量={tot:.0f}"
              f"（位置盲·引擎实算·读 items.json）")
        print("   ⚠ hp+bank=按【最小化总损血】排序（与烧血换属性方向相反）→ 重点看：")
        print("     问题A(银行项解决):maxHP↑了吗?   问题B(真核心·不解决):maxATK 是否仍卡26/破红钥?")
        print("   每 beam_k 跑两组对照：基线(hp−Φ) vs 银行(hp+bank−Φ)")

    for bk in beam_ks:
        print("\n" + "=" * 84)
        print(f"■ beam_k={bk}  max_states={args.max_states}  diversity={diversity}")
        print("=" * 84, flush=True)
        if potions is None:
            res = run_one(start, REDKEY_CELL, allowed, bk, args.max_states, diversity, table)
            report_res(res, bk, "基线 hp−Φ", f"bk{bk}")
        else:
            res0 = run_one(start, REDKEY_CELL, allowed, bk, args.max_states, diversity, table,
                           potions=None)
            report_res(res0, bk, "基线 hp−Φ", f"base_bk{bk}")
            res1 = run_one(start, REDKEY_CELL, allowed, bk, args.max_states, diversity, table,
                           potions=potions)
            report_res(res1, bk, "银行 hp+bank−Φ", f"bank_bk{bk}")


if __name__ == "__main__":
    main()
