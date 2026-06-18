"""【方向2·血饱和(HP 当约束)·§S44·2026-06-18】

诊断（玩家拍板·统一两病为一个根因）：fly 连边接上后视野确实开了(beam 够到 MT1 等远处)，
但出两个新问题，根因同一个——排序键 hp 线性全额无上限、血和属性/钥匙在【同一加性天平】自由权衡：
  问题二(fly 囤血不拿宝石): Φ_total 只依属性不依位置 + fly 不耗血/道具 → 飞回低层 hp 纯涨、
    Φ 不变、score 纯赚 → beam 用 fly 囤血(maxHP 802-834)、ATK 反退 24，不去拿属性。
  问题一(钥匙稀缺度开 fly 失效): 省蓝钥信号(mult=1 用两黄替一蓝净省≈+60HP)被囤血几百 HP 淹没
    → top-k 全囤血态、钥匙乱花(MT9 浪费蓝钥、MT8 真要蓝钥的门没保住)。
  → 同一个病：血当加分项、和属性/钥匙在同一天平权衡。fly 没害、是血把 fly 带歪了。

玩家策略(揭示结构性区别)：
  · 宝石(属性)=必拿目标(一区全拿·确定)、beam 只优化【顺序】；
  · 血=够用约束(够走过去就完全不拿·不够才拿最赚的·拿完宝石才屯)。
  而 beam 现在=血和属性都是加分项、谁当下加分多拿谁=错。

方案 A(血饱和·玩家拍板先做这个·别 A+B 一起·一个一个做好找问题)：
  把血从【加分项】降级为【够用约束】——score_fn 里 hp 改成 min(hp, HP_NEED)：
    score_fn(state) = min(hp, HP_NEED) − Φ_total(atk,def) + key_credit(持钥×HP当量×mult)
  · 血够用(HP_NEED)以上不再加分 → beam 不囤血 → 转去降 Φ(拿属性/宝石)；
  · Φ 不打折(属性越高越值钱·无饱和) → 属性永远值得拿；
  · 血不够时 hp 仍线性 → beam 去拿最赚的血；
  · ★连带验证：血不再淹没 key_credit → 钥匙稀缺度(问题一)大概率自动恢复=一石二鸟。

HP_NEED(够用血线·玩家拍板从段起点 Φ 自适应算·非魔法数)：
  HP_NEED = phi_total(段起点属性) × hp_safety
  Φ_total(段起点属性) = 以铁盾起点【最低】属性(ATK22/DEF20)打通段内剩余所有怪的总损血
    (打不动守卫用'刚好可打'损血当惩罚·见 _monster_loss) = 最悲观"够用"量。
  hp_safety 默认 1.0(最悲观 Φ 本身·不额外拍系数)。★第一版先用最悲观 Φ 看效果；
  若 HP_NEED 偏高(maxHP 还囤到 802-834·血没饱和) → 降 hp_safety(<1) 或改用目标属性算 Φ。

零产品码：只改探针 score_fn(血饱和)，复用 §S43 钥匙稀缺脚本的全部 building blocks(key_credit/
  audit/dump)+ §S42 的 Φ表/seg_step/search_quotient。solver/beam.py(47 守卫)+quotient.py
  封板【一字未动】→ beam 47 零回归自明。fly 保持开(enable_fly·验证修血判断后 fly 干正事=拿属性)。

验证读法(玩家睡醒一眼·四问)：
  ① 血囤不囤(maxHP 还 802-834 吗·< HP_NEED 说明饱和咬合生效)
  ② maxATK 破 25 没(血不囤了·资源去拿属性了吗)
  ③ MT9 改两黄没(钥匙稀缺自动恢复·问题一被 A 顺便修好没)
  ④ found 破红钥没(fly 配血饱和效果)
  ★三结局：血不囤+ATK上去+钥匙恢复=A 一石二鸟成功；血不囤但ATK上不去=A修了血、宝石必拿还需B；
         血还囤(maxHP≈834)=HP_NEED 偏高、降 --hp-safety 或改用目标属性算 Φ。

用法：python -u analysis/dir2_hpsat_beam.py [--beam-k 400] [--max-states 300000]
      [--mults 0,1] [--hp-safety 1.0] [--enable-fly] [--out FILE]
"""
import argparse
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

# §S42 path-loss building blocks（Φ表/seg_step/起点重放·零改动 import）
from analysis.dir2_redkey_pathloss_beam import (
    TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS,
    build_phi_table, phi_total, make_seg_step, replay_to_token, fmt,
)
# §S43 钥匙稀缺脚本辅助（钥匙信用 + 钥匙去向审计·零改动 import·保留 §S43 脚本不污染）
from analysis.dir2_keyscarcity_beam import (
    KEY_HP, FLY_ATTRS, key_credit, audit_keys, mt9_alt_verdict, dump_key_audit,
)
from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step
from extract.encode_route import write_h5route
from solver.quotient import search_quotient


def run_one(start, goal, allowed, beam_k, max_states, diversity, table, mult, hp_need,
            enable_fly=False):
    """跑一次 path-loss + 钥匙稀缺 + ★血饱和 引导段搜索。
    score_fn = min(hp, HP_NEED) − Φ(atk,def) + key_credit。
    ★A 唯一改动：hp → min(hp, hp_need)（血够用以上不加分 → beam 不囤血 → 转去降 Φ 拿属性）。"""
    seg_step = make_seg_step(allowed)

    def score_fn(state):
        h = state.hero
        hp_eff = min(h.hp, hp_need)              # ★方案A:血饱和=够用约束(够用以上不加分)
        return hp_eff - phi_total(h.atk, h.def_, table) + key_credit(h, mult)

    best = defaultdict(lambda: {"atk": 0, "def": 0, "hp": 0, "V": -10 ** 18, "n": 0})
    best_acts = {"key": (-1, -1), "acts": None, "snap": None}

    def on_admit(child, _acts):
        h = child.hero
        b = best[child.current_floor]
        b["n"] += 1
        b["atk"] = max(b["atk"], h.atk)
        b["def"] = max(b["def"], h.def_)
        b["hp"] = max(b["hp"], h.hp)
        v = score_fn(child)
        if v > b["V"]:
            b["V"] = v
        k = (h.atk, h.hp)                         # 最优态键=ATK 优先、同 ATK 取 HP 高（看属性上没上去）
        if k > best_acts["key"]:
            best_acts["key"] = k
            best_acts["acts"] = _acts
            best_acts["snap"] = (child.current_floor, h.x, h.y, h.atk, h.def_, h.hp,
                                 dict(h.keys))

    t0 = time.time()
    res = search_quotient(start, goal, seg_step, max_states=max_states,
                          cross_floor=True, beam_k=beam_k, distinguish_doors=True,
                          beam_score_fn=score_fn, beam_diversity=diversity,
                          on_admit=on_admit,
                          enable_fly=enable_fly, fly_attrs=FLY_ATTRS if enable_fly else None)
    res._secs = time.time() - t0
    res._best_by_floor = dict(best)
    res._best_acts = best_acts
    return res


def export_route_h5(best_acts, fname):
    """导 beam 最优态完整路线 h5route(前缀455 开局→铁盾 + beam 段) + sim 独立重放自检。
    复用 §S42/§S43 write_h5route/meta 口径。文件名由调用方给（带 hpsat/safety tag）。"""
    if not best_acts or best_acts.get("acts") is None:
        print("  ✗ 无 beam 动作串可导 h5route")
        return None
    tokens, outer = load_tokens()
    prefix = list(tokens[:TOK_SHIELD + 1])
    beam_acts = list(best_acts["acts"])
    full = prefix + beam_acts
    snap = best_acts["snap"]
    s = build_initial_state()
    for t in full:
        s = step(s, t)
        if s.dead:
            break
    ok = (s.current_floor == snap[0] and (s.hero.x, s.hero.y) == (snap[1], snap[2])
          and s.hero.atk == snap[3] and s.hero.def_ == snap[4]
          and s.hero.hp == snap[5] and not s.dead)
    meta = {"name": outer.get("name", "51"), "version": outer.get("version", "Ver 3.0"),
            "hard": outer.get("hard", ""), "seed": outer.get("seed")}
    out_path = ROOT / "route" / fname
    write_h5route(out_path, full, meta)
    flag = "✓" if ok else "⚠ 重放与锚点不符(别给玩家坏文件·排查)"
    print(f"  {flag} h5route 导出: route/{out_path.name}  "
          f"full={len(full)}tok(前缀{len(prefix)}+beam{len(beam_acts)})")
    print(f"     sim 独立重放终态: {fmt(s)}  seed={meta['seed']}")
    return out_path if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beam-k", type=int, default=400)
    ap.add_argument("--max-states", type=int, default=300_000)
    ap.add_argument("--mults", type=str, default="0,1")
    ap.add_argument("--hp-safety", type=float, default=1.0,
                    help="HP_NEED=phi_total(段起点属性)×安全系数。默认1.0(最悲观Φ本身·不额外拍系数)。"
                         "偏高(血还囤)→降<1。§S44 第一版玩家拍板用最悲观Φ看效果。")
    ap.add_argument("--allowed", type=str, default=",".join(REAL_LEG_FLOORS))
    ap.add_argument("--diversity", type=str, default="stairs",
                    choices=["none", "floor", "stairs"])
    ap.add_argument("--enable-fly", action="store_true",
                    help="开 fly 魔杖跨层边。§S44 玩家拍板保持开=验证修血判断后 fly 干正事(拿属性)。")
    ap.add_argument("--out", type=str, default="",
                    help="输出文件路径:给则 python 直接写此 utf-8 文件(行缓冲·实时)·供后台无人值守。")
    args = ap.parse_args()
    if args.out:
        sys.stdout = open(args.out, "w", encoding="utf-8", buffering=1)

    allowed = [f.strip() for f in args.allowed.split(",") if f.strip()]
    diversity = None if args.diversity == "none" else args.diversity
    mults = [float(x) for x in args.mults.split(",") if x.strip()]

    print("=" * 88)
    print("方向2 血饱和(血当约束·够用不加分) + path-loss + 钥匙稀缺 → 破 ATK25/拿红钥  [§S44·方案A]")
    print("=" * 88)

    start = replay_to_token(TOK_SHIELD)
    assert start._single_floor_copy is False, "起点 _single_floor_copy 须 False(跨层安全深拷)"
    print(f"段起点(铁盾 tok{TOK_SHIELD}): {fmt(start)}")
    print(f"目标红钥格={REDKEY_CELL}  段楼层({len(allowed)})={allowed}  分坑维={diversity}")

    t0 = time.time()
    table, roster, mons, mdef = build_phi_table(start, allowed)
    print(f"Φ表已建(剩余怪 {len(roster)} 只·mdef={mdef})  耗时 {time.time() - t0:.1f}s")

    # ★HP_NEED：从段起点(最悲观)属性 Φ 自适应算（玩家拍板·非魔法数·从游戏机制出）
    phi_start = phi_total(start.hero.atk, start.hero.def_, table)
    hp_need = phi_start * args.hp_safety
    print("\n" + "─" * 88)
    print(f"★血饱和线 HP_NEED = Φ(段起点 ATK{start.hero.atk},DEF{start.hero.def_})={phi_start:.0f} "
          f"× safety{args.hp_safety} = {hp_need:.0f}")
    print(f"  含义=以段起点最低属性打通段内剩余所有怪总损血(打不动守卫用'刚好可打'损血)=最悲观够用量")
    print(f"  参照: 段起点 hp={start.hero.hp} / §S42(无fly)maxHP≈658 / 本session(fly开)maxHP≈802-834")
    if hp_need >= 834:
        print(f"  ⚠ HP_NEED({hp_need:.0f}) ≥ 能囤的 maxHP(~834) → 血饱和【可能不咬合】(min(hp,HP_NEED)≈hp)")
        print(f"    → 若结果血还囤(maxHP 800+)=HP_NEED 偏高、下版降 --hp-safety 或改用目标属性算 Φ")
    else:
        print(f"  ✓ HP_NEED({hp_need:.0f}) < 能囤的 maxHP(~834) → 血饱和【会咬合】(beam 不再囤到 834)")
    print("─" * 88)
    print(f"排序键 = min(hp, HP_NEED) − Φ_total(atk,def) + key_credit(持钥×HP当量×mult)")
    print(f"钥匙 HP 当量: 黄={KEY_HP['yellowKey']} 蓝={KEY_HP['blueKey']} 红={KEY_HP['redKey']}(源码 shops.json)")
    print(f"fly 魔杖跨层边 = {'★开(验证修血后 fly 去拿属性)' if args.enable_fly else '关'}")
    print(f"参照基线: §S42(无血饱和)found=F/ATK25/maxHP658; 本session(fly+无饱和)ATK24/maxHP802-834")

    summary = []
    exported = []
    for mult in mults:
        print("\n" + "=" * 88)
        tag = "(纯血饱和·key_credit≡0·隔离'血饱和单独效果')" if mult == 0 else "(血饱和+钥匙稀缺)"
        print(f"■ mult={mult}{tag}  beam_k={args.beam_k} max_states={args.max_states}")
        print("=" * 88, flush=True)

        res = run_one(start, REDKEY_CELL, allowed, args.beam_k, args.max_states,
                      diversity, table, mult, hp_need, enable_fly=args.enable_fly)
        print(f"\n  found={res.found}  耗时={res._secs:.1f}s  hit_cap={res.hit_cap}  "
              f"distinct_fp={res.distinct_fingerprints}")
        print(f"  expanded={res.states_expanded} generated={res.states_generated} "
              f"waves={res.n_waves} goal_hits={res.goal_hits}")
        print("\n  ── 各层【到达过】最优属性(on_admit)──")
        for f in sorted(res._best_by_floor, key=lambda x: int(x[2:])):
            b = res._best_by_floor[f]
            print(f"    {f:>5}: n={b['n']:>7}  maxATK={b['atk']}  maxDEF={b['def']}  "
                  f"maxHP={b['hp']}  bestV={b['V']:>11.0f}")
        maxatk = max((b["atk"] for b in res._best_by_floor.values()), default=0)
        maxhp = max((b["hp"] for b in res._best_by_floor.values()), default=0)
        broke = maxatk > 25
        sat = maxhp < hp_need - 1                 # 饱和咬合=囤不到 HP_NEED（血被压住了）
        print(f"\n  ★maxATK(全段)={maxatk}  (基线25 → 破25: {'★破了' if broke else '没破'})")
        print(f"  ★maxHP(全段)={maxhp}  HP_NEED={hp_need:.0f} → "
              f"{'血已饱和不囤(咬合✓·对照fly+无饱和802-834)' if sat else '血未被压住(maxHP≈HP_NEED或HP_NEED太高没咬合)'}")

        ba = res._best_acts
        mt9_choice = "n/a"
        if ba["acts"] is not None:
            sn = ba["snap"]
            print(f"  beam 最优态(key=(atk,hp) 最大): {sn[0]}({sn[1]},{sn[2]}) "
                  f"ATK={sn[3]} DEF={sn[4]} HP={sn[5]} 钥={sn[6]}")
            print("  ── 钥匙去向审计(replay beam 最优态动作串)──")
            events, end_s = audit_keys(ba["acts"])
            dump_key_audit(events, end_s)
            mt9_choice = mt9_alt_verdict(events)
        else:
            print("  ⚠ 无 beam 动作串可审计(on_admit 未记到态)")

        if res.found:
            print(f"\n  ★★走到红钥! HP={res.final_hp} → 血饱和+钥匙稀缺=方向2路通!")
        print("\n  ── 导出该档路线 h5route ──")
        mtag = str(mult).replace(".", "p")
        stag = str(args.hp_safety).replace(".", "p")
        fname = f"dir2_hpsat_k{args.beam_k}_mult{mtag}_s{stag}.h5route"
        h5p = export_route_h5(res._best_acts, fname)
        if h5p:
            exported.append((mult, h5p))
        summary.append((mult, res.found, maxatk, maxhp, res.distinct_fingerprints, mt9_choice))

    # ── 总表（玩家睡醒一眼读）──
    print("\n" + "=" * 88)
    print("■ 总表(mult / found / maxATK / maxHP / distinct_fp / MT9开门用啥钥)")
    print("=" * 88)
    print(f"  HP_NEED={hp_need:.0f}(Φ段起点×safety{args.hp_safety})  fly={'开' if args.enable_fly else '关'}")
    print(f"  {'mult':>6} {'found':>7} {'maxATK':>7} {'maxHP':>7} {'distinct_fp':>12}  MT9抉择")
    for (mult, found, maxatk, maxhp, fp, mt9) in summary:
        flag = "★" if maxatk > 25 else " "
        print(f"  {mult:>6} {str(found):>7} {maxatk:>7}{flag} {maxhp:>7} {fp:>12}  {mt9}")
    print("\n读法(玩家睡醒·§S44 血饱和验证四问):")
    print("  ① 血囤不囤: maxHP 还 802-834 吗 → < HP_NEED 说明饱和咬合、beam 不囤血了")
    print("  ② ATK 破25没: 血不囤了资源去拿属性了吗(24→26→27)")
    print("  ③ 钥匙恢复没: MT9抉择='黄(省蓝✓)' → 血不淹没 key_credit、钥匙稀缺自动恢复(问题一被A顺修)")
    print("  ④ 破红钥没: found=True → fly+血饱和=方向2路通")
    print("  ★三结局: 血不囤+ATK上去+钥匙恢复=A一石二鸟成功; 血不囤但ATK上不去=A修了血、宝石必拿还需B;")
    print("           血还囤(maxHP≈834)=HP_NEED偏高、降 --hp-safety 或改用目标属性算 Φ。")
    print("=" * 88)
    print("\n■ 导出的 h5route(玩家网站回放看换血/换钥决策):")
    for (mult, h5p) in exported:
        print(f"    mult={mult}: route/{h5p.name}")


if __name__ == "__main__":
    main()
