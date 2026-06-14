"""【只导出 + 局面表 · 不改任何逻辑 · 不 commit · 不碰成本优化】
把 GA 侦察三组(B/C/A)末代最优个体导成 .h5route 供玩家在 h5mota 网站【游戏自己引擎】实地回放，
并出 B 含盾解 vs 689 骨架并排局面表 + B「GA 自己进化出的执行序」逐目标到达步号（盾在第几步）。

红线：只读复用封板件(decode/navigate_to/fitness)+编码器(encode_route)+前缀(load_tokens)；不改产品码。
转录无误的证明：三基因转录自 route/ga_inject_recon_out.txt，每条 decode 后【断言 fitness/终态==recon 报值】
（基因→终态确定性 → 对上即证转录一字不差）；再拼 83 步开局前缀、封板 sim 预检 replay==GA 终态才写盘。

跑法：python -u extract/ga_export_h5routes.py   产物：route/ga_recon_{B,C,A}_*.h5route
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from ga_loop import build_harness                         # noqa: E402
from ga_decode import decode                              # noqa: E402
from ga_navigate import navigate_to                       # noqa: E402
from solver.fitness import fitness                        # noqa: E402
from probe_crossfloor import OPENING_PREFIX               # noqa: E402
from export_mt10_boss_route import load_tokens, make_initial_state   # noqa: E402
from export_k0stairs_mt10_route import fk                 # noqa: E402
from gen_h5routes import replay_all                       # noqa: E402
from encode_route import write_h5route, DEFAULT_META      # noqa: E402
from decode_route import parse_rle_route, decompress      # noqa: E402

WP, WK = 1.5, 39.0
R689 = ROOT / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route"

# ── 三组末代最优基因（转录自 route/ga_inject_recon_out.txt；decode 后断言 fitness/终态==recon 报值证无误）──
GROUPS = [
    ("B_shield", "B 注入含盾+交叉", "ga_recon_B_shield.h5route",
     [("MT4", 5, 10), ("MT4", 3, 11), ("MT9", 9, 7), ("MT1", 7, 4), ("MT4", 2, 1),
      ("MT4", 5, 11), ("MT5", 11, 11), ("MT1", 7, 3), ("MT4", 7, 10)],
     dict(fit=-1452.0, floor="MT4", x=7, y=10, hp=150, atk=23, def_=21)),
    ("C_mutation", "C 纯变异·基线", "ga_recon_C_mutation.h5route",
     [("MT5", 11, 11), ("MT4", 2, 1), ("MT4", 7, 10), ("MT1", 7, 4), ("MT4", 5, 11),
      ("MT4", 3, 11)],
     dict(fit=-3650.0, floor="MT4", x=3, y=11, hp=521, atk=22, def_=11)),
    ("A_crossover", "A 光交叉·不注入", "ga_recon_A_crossover.h5route",
     [("MT5", 11, 11), ("MT4", 7, 10), ("MT4", 3, 11), ("MT1", 7, 3), ("MT4", 2, 1),
      ("MT4", 3, 2), ("MT1", 7, 4)],
     dict(fit=-3647.0, floor="MT1", x=7, y=4, hp=524, atk=22, def_=11)),
]


def _tag(cell, meta):
    if cell == meta["sword"]:
        return "剑"
    if cell == meta["shield"]:
        return "★盾"
    if cell in meta["keys"]:
        return "钥"
    if cell in meta["gems"]:
        return "宝石"
    return "?"


def _load_actions(route_file):
    outer = json.loads(decompress(Path(route_file).read_text(encoding="utf-8").strip()))
    return parse_rle_route(decompress(outer["route"]))


def _max_floor(actions, step):
    """从游戏起点重放，记录轨迹触达的最深(最高号)楼层 → 'MT{n}'。"""
    s = make_initial_state()
    mx = fk(s.current_floor)
    for a in actions:
        s = step(s, a)
        mx = max(mx, fk(s.current_floor))
        if s.dead or s.won:
            break
    return f"MT{mx}"


def _milestones(gene, H):
    """复刻 decode 的循环、逐目标记录到达步号（只读用 navigate_to·不改 decode）：
    返回 [(序号, cell, reached, 段步数, 累计步数 cum)]，cum=该目标到达时从 MT3 入口起算的第几步。"""
    state, cum, out = H["start"], 0, []
    for k, goal in enumerate(gene, 1):
        if state.dead or state.won:
            out.append((k, goal, False, 0, cum))
            continue
        final, moves, reached = navigate_to(
            state, goal, H["zone"], H["step"], cache=H["decode_cache"])
        if reached:
            state, cum = final, cum + len(moves)
        out.append((k, goal, reached, len(moves), cum))
    return out


def main():
    print("组装 GA 电池组（build_start + 标尺 route + 目标池涌现）…")
    H = build_harness()
    meta, pool = H["meta"], H["pool"]
    step = H["step"]

    # 前缀：开局噩梦 → MT3 入口（与 gen_beta_h5route 同口径）
    prefix = list(load_tokens()[:OPENING_PREFIX])
    pre = replay_all(prefix)
    assert pre.current_floor == "MT3" and pre.hero.hp == 400, \
        f"前缀终态不符: {pre.current_floor} HP{pre.hero.hp}"
    print(f"  前缀 {len(prefix)} 步预检 ✅ → MT3 入口 HP400\n")

    results = {}
    for key, title, fname, gene, exp in GROUPS:
        assert all(c in pool for c in gene), f"{key}: 基因有 cell 不在 pool → 转录错"
        tokens, final = decode(gene, H["start"], H["zone"], step, cache=H["decode_cache"])
        f = fitness(final, H["roster_fit"], H["big"], H["zone_fids"], w_potion=WP, w_key=WK)
        fh = final.hero
        # ① 转录无误证明：decode 复算的 fitness/终态必须 == recon 报值（确定性）
        assert round(f, 1) == exp["fit"], f"{key}: fitness {f:.1f} ≠ recon {exp['fit']}"
        assert (final.current_floor, fh.x, fh.y, fh.hp, fh.atk, fh.def_) == \
            (exp["floor"], exp["x"], exp["y"], exp["hp"], exp["atk"], exp["def_"]), \
            f"{key}: 终态 {final.current_floor}({fh.x},{fh.y})HP{fh.hp}/A{fh.atk}/D{fh.def_} ≠ recon"

        # ② 拼前缀 + 封板 sim 预检：replay(spliced) 终态必须 == GA decode 终态
        spliced = prefix + list(tokens)
        rfin = replay_all(spliced)
        rh = rfin.hero
        assert (rfin.current_floor, rh.x, rh.y, rh.hp, rh.atk, rh.def_) == \
            (final.current_floor, fh.x, fh.y, fh.hp, fh.atk, fh.def_), \
            f"{key}: 拼接后 replay 终态 {rfin.current_floor}({rh.x},{rh.y})HP{rh.hp} ≠ GA 终态"

        out_path = ROOT / "route" / fname
        write_h5route(out_path, spliced, DEFAULT_META)
        mxf = _max_floor(spliced, step)
        held = {k2: v for k2, v in fh.keys.items() if v}
        results[key] = dict(title=title, path=out_path, gene=gene, final=final, fit=f,
                            tokens=len(tokens), total=len(spliced), maxf=mxf, keys=held)
        print(f"✅ {title}: {out_path.name}  (前缀{len(prefix)}+GA{len(tokens)}={len(spliced)} token) "
              f"终态 {final.current_floor}({fh.x},{fh.y}) HP{fh.hp}/A{fh.atk}/D{fh.def_} "
              f"含盾={meta['shield'] in gene} fit={f:.1f}  转录&拼接预检 ✅")

    # ── 689 骨架局面（同 fitness 尺）──
    s689 = H["s689"]
    h689 = s689.hero
    f689 = fitness(s689, H["roster_fit"], H["big"], H["zone_fids"], w_potion=WP, w_key=WK)
    act689 = _load_actions(R689)
    mxf689 = _max_floor(act689, step)
    held689 = {k2: v for k2, v in h689.keys.items() if v}

    # ── ② B vs 689 并排局面表 ──
    B = results["B_shield"]
    bh = B["final"].hero
    print("\n" + "=" * 78)
    print("② B 含盾解 vs 689 骨架 · 并排真实局面（同 fitness 尺）")
    print("=" * 78)
    print(f"  {'':<14}{'B 含盾解(GA进化)':<22}{'689 骨架(玩家轴心)'}")
    print(f"  {'fitness':<14}{B['fit']:<22.1f}{f689:.1f}")
    print(f"  {'HP':<14}{bh.hp:<22}{h689.hp}")
    print(f"  {'ATK':<14}{bh.atk:<22}{h689.atk}")
    print(f"  {'DEF':<14}{bh.def_:<22}{h689.def_}")
    print(f"  {'钥匙':<14}{str(B['keys']):<22}{held689}")
    print(f"  {'最深层':<14}{B['maxf']:<22}{mxf689}")
    print(f"  {'tokens':<14}{B['total']:<22}{len(act689)}")
    print(f"  {'终态位置':<14}{B['final'].current_floor+f'({bh.x},{bh.y})':<22}"
          f"{s689.current_floor}({h689.x},{h689.y})")

    # ── B 执行序：每个目标第几步到、盾在第几步 ──
    print("\n" + "=" * 78)
    print("  B「GA 自己进化出的执行序」逐目标到达步号（盾排第几、在第几步）")
    print("=" * 78)
    print(f"  {'序':<4}{'目标 cell':<18}{'类型':<6}{'到达?':<7}{'本段步':<8}"
          f"{'累计步(MT3起)':<14}{'网站绝对~':<10}")
    for k, cell, reached, seg, cum in _milestones(B["gene"], H):
        mark = "✅" if reached else "✗跳过"
        print(f"  {k:<4}{str(cell):<18}{_tag(cell, meta):<6}{mark:<7}{seg:<8}"
              f"{cum:<14}{OPENING_PREFIX + cum:<10}")
    sh_ord = next(k for k, c, *_ in _milestones(B["gene"], H) if c == meta["shield"])
    print(f"\n  → ★盾 = 执行序第 {sh_ord} 个目标（先拿 2 把钥匙再下深盾 MT9）。"
          f"对照注入时是「盾-first」→ GA 自己把盾后移、进化出 689 式「先攒后下深盾」雏形。")

    # ── A/C 只确认无盾（DEF 低）──
    print("\n" + "=" * 78)
    print("  A/C 确认（只看无盾·DEF 低，不细看）")
    print("=" * 78)
    for key in ("C_mutation", "A_crossover"):
        r = results[key]
        rh = r["final"].hero
        print(f"  {r['title']}: {r['path'].name}  含盾={meta['shield'] in r['gene']} "
              f"DEF={rh.def_}(不拿盾基线11) HP={rh.hp} fit={r['fit']:.1f}")

    print("\n" + "=" * 78)
    print("三条 .h5route 已写到 route/（可直接拖进 h5mota 看游戏引擎回放）：")
    for key, title, fname, *_ in GROUPS:
        print(f"  {title:<18} route/{fname}")
    print("（注：三条都是 GA 中间态、非通关路线，网站回放到各自末目标即止。）")


if __name__ == "__main__":
    main()
