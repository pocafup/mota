"""【方向2·path-loss + 钥匙稀缺·无人值守测试·§S43·2026-06-18】

诊断（玩家钉死·推翻 §S42 甲/乙"段内属性天花板"方向）：k400 path-loss 卡 ATK25 的
真因 = 蓝钥【资源分配】错误，不是段内属性供给天花板。蓝钥审计
（analysis/_pathloss_route_audit.py）证：beam 拿 2 把蓝钥、花在 MT9(tok469)+MT8(tok1322)。
这条路线【三处要蓝钥】：
  ① MT8 蓝门（一攻一防）                  —— 真要蓝钥
  ② MT9 蓝门（tok469·铁盾旁上楼必经）     —— ★可用【两把黄钥】替代（黄钥充裕·剩2）
  ③ MT9 上楼（绕怪·省 250+ 血和一黄）      —— 真要蓝钥
只 2 把蓝钥，但 ② 能用两黄替代 → 省下那把蓝钥够覆盖 ①③。beam 没做替代（把稀缺蓝钥
浪费在 ② 能用黄钥的门）→ 蓝钥不够 → ① 开不了 → 属性/血拿不全 → 卡 ATK25。
★这是资源分配【逻辑】问题、不是算力问题——加预算（§S40 k1600/3200k）没用：beam 排序键
不知道"蓝钥稀缺、该用黄钥替代"，更大搜索空间里还犯同样的错误分配。

解法：给 beam"蓝钥稀缺"认知 —— path-loss 排序键 score_fn 加【钥匙 HP 当量项】，蓝 > 黄。
  ★钥匙 HP 当量【源码坐实·非魔法数】（data/games51/shops.json 商人事件）：
    · MT45(9,3) 商店  1000 金 → hp+2000   ⇒ 1 金 = 2 血（HP 当量）
    · MT7 (6,1) 商店    50 金 → 5 黄钥      ⇒ 1 黄 = 10 金 = 20 血
    · MT6 (8,4) 商店    50 金 → 1 蓝钥      ⇒ 1 蓝 = 50 金 = 100 血  （∴ 1 蓝 ≈ 5 黄·与 §S41 一致）
  key_credit(state) = Σ_color 持有钥[color] × HP当量[color] × mult
    蓝(100) > 黄(20) → beam"心疼"蓝钥 → MT9 用两黄（净省 2×20=40）替蓝（省 100）、保住蓝钥
    → 留给 MT8 蓝门 → 拿一攻一防 → ATK 破 25 → 破红钥门。
  扫 mult ∈ {0, 1, 3, 10}（对照组 + 敏感度）：
    · mult=0  = §S42 基线复现（key_credit≡0·score_fn=hp−Φ·验脚本与 §S42 等价：found=F/ATK25/fp≈8313）
    · mult=1  = 纯源码 HP 当量基准（玩家要的 door_value 折 HP 当量起点）
    · mult=10 = 蓝钥"用 2 黄替 1 蓝"净省 = W_B·3/5 ≈ 600 ≈ ΔΦ(+1ATK)=584 → 钥信号 ≈ 属性梯度
    · mult=3  = 中间档
    源码当量绝对差小（净省 60），放大档用来区分"诊断错（放大也不改用黄钥）"vs"信号弱（放大就改）"。

零产品码：只改探针 score_fn（beam_score_fn override），复用 §S42 的 Φ表/seg_step/search_quotient，
  solver/beam.py（47 守卫）与 solver/quotient.py 封板【一字未动】→ beam 47 零回归自明。跑 k400（同 §S42 预算）。
每档跑完：replay beam 最优态（key=(atk,hp) 最大）的动作串，逐 token 追踪蓝/黄钥消耗-获取
  （集成 _pathloss_route_audit 逻辑）→ dump 蓝钥去向（MT9 开门用蓝还是黄）、各层 maxATK、found、distinct_fp。

用法：python -u analysis/dir2_keyscarcity_beam.py [--beam-k 400] [--max-states 300000]
      [--mults 0,1,3,10]  > analysis/_test_keyscarcity_k400.txt 2>&1
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

# 复用 §S42 path-loss 脚本的全部 building blocks（零改动·import 即用）
from analysis.dir2_redkey_pathloss_beam import (
    TOK_SHIELD, REDKEY_CELL, REAL_LEG_FLOORS,
    build_phi_table, phi_total, make_seg_step, replay_to_token, fmt,
)
from analysis.extract_zone1_milestones import build_initial_state, load_tokens
from sim.simulator import step
from solver.quotient import search_quotient
from extract.encode_route import write_h5route

# ── 钥匙 HP 当量（源码坐实·shops.json·见模块顶折算）──
KEY_HP = {"yellowKey": 20, "blueKey": 100, "redKey": 1600}
COLORS = ["yellowKey", "blueKey", "redKey"]

# fly 魔杖跨层属性（canFlyTo/canFlyFrom·排 MT0/MT44/MT50）·驱动层注入 search_quotient(enable_fly=True)
FLY_ATTRS = json.loads(
    (ROOT / "data" / "games51" / "fly_attrs.json").read_text(encoding="utf-8"))["floors"]

# ★玩家点名的可替代门：MT9(6,2)（mult=0 复现里 tok469 在此用蓝钥·玩家说可用两把黄钥从旁替代）。
#   注意 MT9 有多个蓝门（还有 (4,11) 等）→ 审计须【按门位置】区分，不能笼统统计"MT9 用蓝/黄"。
MT9_ALT_DOOR = ("MT9", 6, 2)


def key_credit(hero, mult):
    """持有钥匙的 HP 当量信用：Σ 持钥 × 源码 HP 当量 × mult。蓝(100)>黄(20) → beam 心疼蓝钥。"""
    if mult == 0:
        return 0
    return sum(hero.keys.get(c, 0) * KEY_HP[c] for c in KEY_HP) * mult


def run_one(start, goal, allowed, beam_k, max_states, diversity, table, mult, enable_fly=False):
    """跑一次 path-loss(+钥匙稀缺) 引导段搜索。mult=0 → key_credit≡0 = §S42 基线。
    enable_fly=True → 开 fly 魔杖跨层边（方案B保守子集·扩 beam 视野=飞回低层拿漏拿资源）。"""
    seg_step = make_seg_step(allowed)

    def score_fn(state):
        h = state.hero
        return h.hp - phi_total(h.atk, h.def_, table) + key_credit(h, mult)

    best = defaultdict(lambda: {"atk": 0, "def": 0, "hp": 0, "V": -10 ** 18, "n": 0})
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


def audit_keys(beam_acts):
    """replay 前缀(开局→铁盾) + beam 动作串，逐 token 追踪钥匙消耗(开门)/获取事件。
    复用 _pathloss_route_audit 逻辑。返回 (events, end_state)。"""
    tokens, _ = load_tokens()
    full = list(tokens[:TOK_SHIELD + 1]) + list(beam_acts)
    s = build_initial_state()
    prev = dict(s.hero.keys)
    events = []
    for i, t in enumerate(full):
        s = step(s, t)
        if s.dead:
            break
        cur = s.hero.keys
        for c in COLORS:
            d = cur.get(c, 0) - prev.get(c, 0)
            if d != 0:
                seg = "前缀" if i <= TOK_SHIELD else "beam"
                events.append(dict(i=i, seg=seg, color=c, d=d, rem=cur.get(c, 0),
                                   fl=s.current_floor, x=s.hero.x, y=s.hero.y))
        prev = dict(cur)
    return events, s


def mt9_alt_verdict(events):
    """beam 最优态在 MT9(6,2)（玩家点名 tok469 可两黄替代门）的开法：蓝/黄/绕过。给总表用。"""
    t62 = [e for e in events if e["seg"] == "beam" and e["d"] < 0
           and (e["fl"], e["x"], e["y"]) == MT9_ALT_DOOR]
    if any(e["color"] == "blueKey" for e in t62):
        return "蓝(浪费)"
    if any(e["color"] == "yellowKey" for e in t62):
        return "黄(省蓝✓)"
    return "(6,2)未开"


def dump_key_audit(events, end_state):
    """dump 钥匙去向，专门回答玩家 3 问：MT9(6,2) 可替代门用蓝还是黄、MT8 蓝门(①一攻一防)开没开、
    稀缺蓝钥全花哪。★按门位置区分（MT9 有多个蓝门），不笼统统计。"""
    beam_spends = [e for e in events if e["seg"] == "beam" and e["d"] < 0]
    blue_gain = [e for e in events if e["color"] == "blueKey" and e["d"] > 0]
    blue_spend = [e for e in events if e["color"] == "blueKey" and e["d"] < 0]

    seq = " ".join(f"{e['fl']}:{e['color'][0]}@({e['x']},{e['y']})" for e in beam_spends)
    print(f"    beam 段开门序列: {seq or '无'}")
    print(f"    蓝钥获取点: {[(e['seg'], e['fl'], e['x'], e['y']) for e in blue_gain] or '无'}")
    if blue_spend:
        print(f"    蓝钥全部消耗点(开蓝门):")
        for e in blue_spend:
            tgt = " ←★玩家点名的可两黄替代门" if (e["fl"], e["x"], e["y"]) == MT9_ALT_DOOR else ""
            print(f"      [{e['seg']}] tok#{e['i']} {e['fl']}({e['x']},{e['y']}) →剩{e['rem']}{tgt}")
    else:
        print(f"    蓝钥消耗: 无(全程没开蓝门)")

    # ★玩家点名门 MT9(6,2)：beam 最优态用蓝（浪费·病在）/用黄（认知生效）/绕过（=省下蓝钥）。
    v = mt9_alt_verdict(events)
    note = {"蓝(浪费)": "用蓝钥开 → 浪费稀缺蓝钥·诊断的病还在",
            "黄(省蓝✓)": "★改用黄钥开 → 蓝钥稀缺认知生效",
            "(6,2)未开": "未开 → 绕过/走两黄替代路（看上面开门序列确认）·=省下蓝钥"}[v]
    print(f"    ★MT9(6,2) tok469 可替代门: {note}")

    # MT8 蓝门（玩家说 ①一攻一防·真要蓝钥）：beam 最优态有没有把蓝钥用在这？
    mt8_blue = [(e["x"], e["y"]) for e in beam_spends if e["fl"] == "MT8" and e["color"] == "blueKey"]
    print(f"    MT8 蓝门(①一攻一防·真要蓝钥): "
          f"{'开了@' + str(mt8_blue) + '（蓝钥用对地方）' if mt8_blue else '没开（蓝钥没用在这）'}")

    h = end_state.hero
    print(f"    终态钥匙: 黄{h.keys.get('yellowKey', 0)} 蓝{h.keys.get('blueKey', 0)} "
          f"红{h.keys.get('redKey', 0)}")


def export_route_h5(best_acts, mult):
    """导该档 beam 最优态完整路线 h5route(前缀455 开局→铁盾 + beam 段) + sim 独立重放自检。
    复用 §S42 write_h5route/meta 口径。文件名 route/dir2_keyscarcity_k400_mult{m}.h5route。"""
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
    mtag = str(mult).replace(".", "p")
    out_path = ROOT / "route" / f"dir2_keyscarcity_k400_mult{mtag}.h5route"
    write_h5route(out_path, full, meta)
    flag = "✓" if ok else "⚠ 重放与锚点不符(别给玩家坏文件·排查)"
    print(f"  {flag} h5route 导出: route/{out_path.name}  full={len(full)}tok(前缀{len(prefix)}+beam{len(beam_acts)})")
    print(f"     sim 独立重放终态: {fmt(s)}  seed={meta['seed']}")
    return out_path if ok else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beam-k", type=int, default=400)
    ap.add_argument("--max-states", type=int, default=300_000)
    ap.add_argument("--mults", type=str, default="0,1,3,10")
    ap.add_argument("--ky", type=int, default=None,
                    help="黄钥 HP 当量覆盖(玩家指定·实战稀缺价·非源码商店价)")
    ap.add_argument("--kb", type=int, default=None,
                    help="蓝钥 HP 当量覆盖(玩家指定·实战稀缺价·非源码商店价)")
    ap.add_argument("--kr", type=int, default=None,
                    help="红钥 HP 当量覆盖(玩家指定·实战稀缺价·非源码商店价)")
    ap.add_argument("--allowed", type=str, default=",".join(REAL_LEG_FLOORS))
    ap.add_argument("--diversity", type=str, default="stairs",
                    choices=["none", "floor", "stairs"])
    ap.add_argument("--enable-fly", action="store_true",
                    help="开 fly 魔杖跨层边（方案B·扩视野飞回低层拿漏拿资源）；默认关=老路指纹不变")
    ap.add_argument("--out", type=str, default="",
                    help="输出文件路径：给则 python 直接写此 utf-8 文件（行缓冲·实时），"
                         "绕过 shell 重定向的中文编码坑·供 detached 后台无人值守用")
    args = ap.parse_args()
    key_src = "源码 shops.json(1金=2血 / 黄20 / 蓝100 → 1蓝≈5黄)"
    if any(v is not None for v in (args.ky, args.kb, args.kr)):
        if args.ky is not None:
            KEY_HP["yellowKey"] = args.ky
        if args.kb is not None:
            KEY_HP["blueKey"] = args.kb
        if args.kr is not None:
            KEY_HP["redKey"] = args.kr
        key_src = "★玩家指定【实战稀缺价】(非商店价·黄蓝比例已改)"
    if args.out:
        sys.stdout = open(args.out, "w", encoding="utf-8", buffering=1)

    allowed = [f.strip() for f in args.allowed.split(",") if f.strip()]
    diversity = None if args.diversity == "none" else args.diversity
    mults = [float(x) for x in args.mults.split(",") if x.strip()]

    print("=" * 88)
    print("方向2 path-loss + 钥匙稀缺(蓝钥 HP 当量 > 黄钥) → 破 ATK25 / 拿红钥  [无人值守·§S43]")
    print("=" * 88)
    print(f"钥匙 HP 当量: 黄={KEY_HP['yellowKey']} 蓝={KEY_HP['blueKey']} 红={KEY_HP['redKey']}  "
          f"来源={key_src}  黄:蓝={KEY_HP['blueKey'] / max(KEY_HP['yellowKey'], 1):.2f}")

    start = replay_to_token(TOK_SHIELD)
    assert start._single_floor_copy is False, "起点 _single_floor_copy 须 False（跨层安全深拷）"
    print(f"铁盾起点 tok{TOK_SHIELD}: {fmt(start)}")
    print(f"目标红钥格={REDKEY_CELL}  段楼层({len(allowed)})={allowed}  分坑维={diversity}")
    print(f"排序键 = hp − Φ_total(atk,def) + key_credit(持钥×HP当量×mult)")
    print(f"fly 魔杖跨层边(扩视野) = "
          f"{'★开(enable_fly·飞回低层拿漏拿资源)' if args.enable_fly else '关(老路)'}")

    t0 = time.time()
    table, roster, mons, mdef = build_phi_table(start, allowed)
    print(f"\nΦ表已建(剩余怪 {len(roster)} 只·mdef={mdef})  耗时 {time.time() - t0:.1f}s")
    print(f"§S42 对照基线(mult=0 应复现): found=False / 各层 maxATK=25 / distinct_fp≈8313 / HP 囤 658")

    summary = []
    exported = []
    for mult in mults:
        wy, wb = KEY_HP["yellowKey"] * mult, KEY_HP["blueKey"] * mult
        net_save = wb - 2 * wy
        print("\n" + "=" * 88)
        tag = "（§S42 基线·key_credit≡0）" if mult == 0 else ""
        print(f"■ mult={mult}{tag}  钥匙 HP 当量: 黄={wy:.0f} 蓝={wb:.0f}")
        print(f"  蓝钥'用 2 黄替 1 蓝'净省 = {net_save:.0f} HP（对照 ΔΦ(+1ATK)=584）  "
              f"beam_k={args.beam_k} max_states={args.max_states}")
        print("=" * 88, flush=True)

        res = run_one(start, REDKEY_CELL, allowed, args.beam_k, args.max_states,
                      diversity, table, mult, enable_fly=args.enable_fly)
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
        broke = maxatk > 25
        print(f"\n  ★maxATK(全段)={maxatk}  (§S42 基线=25 → 破 25 没: "
              f"{'★破了' if broke else '没破'})")

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
            print(f"\n  ★★走到红钥! HP={res.final_hp} → 钥匙稀缺是真因、解法成立!")
        print("\n  ── 导出该档路线 h5route(玩家网站回放看换血决策)──")
        h5p = export_route_h5(res._best_acts, mult)
        if h5p:
            exported.append((mult, h5p))
        summary.append((mult, res.found, maxatk, res.distinct_fingerprints, mt9_choice))

    # ── 总表（玩家睡醒一眼读）──
    print("\n" + "=" * 88)
    print("■ 总表（mult / found / maxATK / distinct_fp / MT9开门用啥钥）")
    print("=" * 88)
    print(f"  {'mult':>6} {'found':>7} {'maxATK':>7} {'distinct_fp':>12}  MT9抉择")
    for (mult, found, maxatk, fp, mt9) in summary:
        flag = "★" if maxatk > 25 else " "
        print(f"  {mult:>6} {str(found):>7} {maxatk:>7}{flag} {fp:>12}  {mt9}")
    print("\n读法（玩家睡醒）:")
    print("  ① beam 在 MT9 改用黄钥没（'MT9抉择'列）→ 改用=蓝钥稀缺认知生效、不浪费蓝钥")
    print("  ② maxATK 破 25 没 → 破=省下蓝钥拿到 MT8 一攻一防、证实蓝钥分配是真因")
    print("  ③ found 破红钥没 → 破=钥匙稀缺度是解、方向2 路通")
    print("  ★不浪费蓝钥(MT9改黄) + ATK 过 25 = 证实诊断（资源分配非算力）、钥匙稀缺度是解。")
    print("  mult=0 须复现 §S42(found=F/ATK25/fp≈8313)，否则脚本与基线不等价、上面结论不可信。")
    print("=" * 88)
    print("\n■ 导出的四条 h5route(玩家网站回放看换血/换钥决策):")
    for (mult, h5p) in exported:
        print(f"    mult={mult}: route/{h5p.name}")
    if len(exported) < len(mults):
        print(f"    ⚠ 仅 {len(exported)}/{len(mults)} 档导出成功(其余 on_admit 没记到态或自检失败)")


if __name__ == "__main__":
    main()
