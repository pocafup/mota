"""【只导出 + 自验 · 不改任何逻辑 · 不 commit】把路线图② GA 最优解导成 .h5route 供玩家网站实地回放，
同时截断玩家存档到首进 MT10(tok789) 导出，与 689 三条并排对比打法。

红线：只读复用封板件(decode/navigate_to)+编码器(encode_route)+前缀(load_tokens)；不改产品码。
自验：① GA 基因 decode 终态必 == 报值(HP249/ATK23/DEF21·确定性证基因转录无误)；② 拼 83 步开局前缀后
  封板 sim replay(spliced) 终态必 == GA decode 终态(证拼接无误·引擎可重放)；③ tok789 截断 replay 终态
  必 == §S14 报值(MT10/HP265/ATK26/DEF24)。三关全过才写盘。

跑法：python -u analysis/ga_export_scaleup_route.py
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

from ga_loop import build_harness
from ga_decode import decode
from solver.fitness import fitness
from probe_crossfloor import OPENING_PREFIX
from export_mt10_boss_route import load_tokens, make_initial_state
from export_k0stairs_mt10_route import fk
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META, make_h5route
from decode_route import parse_rle_route, decompress

WP, WK = 1.5, 39.0

# 路线图② GA 最优基因(执行序·转录自 analysis/_ga_scaleup_out.txt ③；decode 后断言终态==报值证无误)
GA_GENE = [
    ("MT9", 9, 7),    # 盾
    ("MT4", 2, 1),    # 钥
    ("MT1", 7, 4),    # 宝石
    ("MT4", 7, 10),   # 宝石
    ("MT5", 11, 11),  # 剑
    ("MT1", 7, 3),    # 宝石
    ("MT4", 3, 2),    # 钥
    ("MT4", 5, 11),   # 钥
]
GA_EXP = dict(floor="MT4", x=5, y=11, hp=249, atk=23, def_=21)  # decode 终态报值(§ 报告④)
GA_FNAME = "ga_zone1_scaleup_best.h5route"

PLAYER_SAVE = ROOT / "51_20260529133740.h5route"
TOK_FNAME = "tok789_player_mt10.h5route"
TOK_EXP = dict(floor="MT10", x=1, y=10, hp=265, atk=26, def_=24)  # §S14 报值


def max_floor(actions, step):
    s = make_initial_state()
    mx = fk(s.current_floor)
    for a in actions:
        s = step(s, a)
        mx = max(mx, fk(s.current_floor))
        if s.dead or s.won:
            break
    return f"MT{mx}"


def assert_state(label, hero_floor, h, exp):
    got = (hero_floor, h.x, h.y, h.hp, h.atk, h.def_)
    want = (exp["floor"], exp["x"], exp["y"], exp["hp"], exp["atk"], exp["def_"])
    assert got == want, f"{label} 终态不符: got {got} != exp {want}"


def main():
    print("组装 GA 电池组(persistent=True 暖桶)…")
    H = build_harness(persistent=True)
    step = H["step"]

    # ── 前缀：开局噩梦 → MT3 入口(与 ga_export_h5routes 同口径) ──
    prefix = list(load_tokens()[:OPENING_PREFIX])
    pre = replay_all(prefix)
    assert pre.current_floor == "MT3" and pre.hero.hp == 400, \
        f"前缀终态不符: {pre.current_floor} HP{pre.hero.hp}"
    print(f"  前缀 {len(prefix)} 步预检 ✅ → MT3 入口 HP400")

    # ════ ① 导出 GA 最优解 ════
    assert all(c in H["pool"] for c in GA_GENE), "GA 基因有 cell 不在 pool → 转录错"
    tokens, final = decode(GA_GENE, H["start"], H["zone"], step, cache=H["decode_cache"])
    fh = final.hero
    f = fitness(final, H["roster_fit"], H["big"], H["zone_fids"], w_potion=WP, w_key=WK)
    # 自验①：decode 终态 == 报值(基因转录无误·确定性)
    assert_state("GA decode", final.current_floor, fh, GA_EXP)
    print(f"\n① GA decode 终态自验 ✅: {final.current_floor}({fh.x},{fh.y}) "
          f"HP{fh.hp}/A{fh.atk}/D{fh.def_} keys={dict((k,v) for k,v in fh.keys.items() if v)} fit={f:.1f}")

    spliced = prefix + list(tokens)
    rfin = replay_all(spliced)
    rh = rfin.hero
    # 自验②：拼前缀后封板 sim replay 终态 == decode 终态(引擎可重放)
    assert_state("GA replay(spliced)", rfin.current_floor, rh, GA_EXP)
    print(f"  拼前缀 sim replay 终态自验 ✅: {rfin.current_floor}({rh.x},{rh.y}) "
          f"HP{rh.hp}/A{rh.atk}/D{rh.def_}  == decode 终态(引擎可重放)")
    ga_path = ROOT / "route" / GA_FNAME
    write_h5route(ga_path, spliced, DEFAULT_META)
    ga_maxf = max_floor(spliced, step)
    print(f"  ✅ 写盘 route/{GA_FNAME}  (前缀{len(prefix)}+GA{len(tokens)}={len(spliced)} token·最深层 {ga_maxf})")

    # ════ ② 导出 tok789(截断玩家存档到首进 MT10) ════
    outer = json.loads(decompress(PLAYER_SAVE.read_text(encoding="utf-8").strip()))
    player_meta = {k: v for k, v in outer.items() if k != "route"}
    player_actions = parse_rle_route(decompress(outer["route"]))
    # 重放找首进 MT10 的截断点(复刻 §S14 replay_player_until_floor)
    s = make_initial_state()
    cut = len(player_actions)
    for i, a in enumerate(player_actions):
        s = step(s, a)
        if s.dead or s.current_floor == "MT10":
            cut = i + 1
            break
    tok_actions = player_actions[:cut]
    tfin = replay_all(tok_actions)
    th = tfin.hero
    # 自验③：截断 replay 终态 == §S14 报值
    assert_state(f"tok{cut} replay", tfin.current_floor, th, TOK_EXP)
    ftok = fitness(tfin, H["roster_fit"], H["big"], H["zone_fids"], w_potion=WP, w_key=WK)
    print(f"\n② tok{cut} 截断自验 ✅: {tfin.current_floor}({th.x},{th.y}) "
          f"HP{th.hp}/A{th.atk}/D{th.def_} keys={dict((k,v) for k,v in th.keys.items() if v)} fit={ftok:.1f}")
    tok_path = ROOT / "route" / TOK_FNAME
    # 用玩家存档原 meta(回放起点一致)，仅截断动作
    tok_path.write_text(make_h5route(tok_actions, player_meta), encoding="utf-8")
    print(f"  ✅ 写盘 route/{TOK_FNAME}  ({cut} token·截到首进 MT10)")

    # ════ 三条交付 + 打法标注 ════
    print("\n" + "=" * 78)
    print("三条 .h5route(拖进 h5mota 网站用游戏引擎实地回放)：")
    print("=" * 78)
    print(f"  【GA最优·不含红钥】  route/{GA_FNAME}")
    print(f"      打法=先抓剑(MT5)+深盾(MT9)两大件、再回头补 MT4/MT1 钥宝、停 MT4(5,11)·最深 {ga_maxf}")
    print(f"  【689·beam轴心】     route/deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route")
    print(f"      打法=先拿下面属性、推进到 MT10(HP689)·含红钥努力")
    print(f"  【tok789·玩家】      route/{TOK_FNAME}")
    print(f"      打法=先拿下面属性、推进到 MT10(HP265)·含红钥努力(玩家手玩·截到首进 MT10)")
    print(f"\n  (GA 是一区中间态非通关路线·网站回放到末目标即止；689/tok789 回放到 MT10。)")
    print(f"  (玩家全程存档原件在 ROOT/51_20260529133740.h5route·tok789 即其前 {cut} 步)")


if __name__ == "__main__":
    main()
