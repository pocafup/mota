"""生成 β best-MT10 路线的 .h5route（玩家在 h5mota 网站看【游戏自己引擎】回放）。

照编码器标准流程（handoff A.5 / gen_h5routes 模板）：
  1) 取解算动作串：β cut 文件里 floor==MT10 按真实 V=HP−D 取顶那条（与 export_bscan_routes 同口径）。
  2) 拼前缀 tokens[:83]（玩家存档开局噩梦→MT3 入口，OPENING_PREFIX；82→83 见 MT2(1,9)小偷修法）。
  3) 封板 sim 预检：replay 整串，断言终态 == cut 行 (floor/hp/atk/def)。
  4) write_h5route。

⚠ 【不插 FMT 标记】：β 是纯 RULD 解算串，踏楼梯那步 sim 已自动换层。实测 insert_floor_markers
   会把英雄重定位到该层【固定入口格】——玩家录像每次走标准楼梯(落点==入口、幂等无害)，但 β 路线
   走非标准楼梯(落点≠固定入口) → FMT 重定位打乱轨迹(终态从 HP553 崩成 HP44)。故本路线只用纯 RULD，
   sim 预检确认终态精确等于 cut 行。网站回放才是终审：若回放在某楼梯处不自动换层而卡住，告诉我换 FMT 策略。

⚠ β=0.5 best-MT10 路线终态在 MT10 入口落点 (1,10)、0 红钥匙——回放到 MT10 入口即结束，
   并不会真去撞红门(6,9)。它证明的是：β=0.5 自夸的 +172 余量是 D 幻觉（连红钥匙都没拿到、
   根本到不了 boss 房）。网站回放才是终审，sim 预检只排除拼接/编码错。

跑法：python extract/gen_beta_h5route.py [beta]   # beta 默认 0.5
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from vzone import build_zone
from probe_crossfloor import build_start, OPENING_PREFIX
from export_bscan_routes import cut_path, load_rows, pick_best_mt10
from export_mt10_boss_route import load_tokens
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META


def gen(beta):
    zone = build_zone()
    start, _ = build_start()                       # MT3 入口 (2,11) HP400，_single_floor_copy=False
    rows = load_rows(cut_path(beta))
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        sys.exit(f"β={beta}: cut 文件无 MT10 态，无法生成")
    best_row, _s, _vz, D = pick_best_mt10(zone, start, mt10)
    beta_actions = list(best_row["actions"])

    tokens = load_tokens()
    prefix = tokens[:OPENING_PREFIX]               # 开局噩梦 → MT3 入口
    spliced = prefix + beta_actions                # 纯 RULD，踏楼梯步 sim 自动换层（不插 FMT，见模块注释）

    # ── 封板 sim 预检：前缀到 MT3 入口；整串到 cut 行终态 ──
    pre = replay_all(prefix)
    assert pre.current_floor == "MT3" and pre.hero.hp == 400, \
        f"前缀终态不符: {pre.current_floor} ({pre.hero.x},{pre.hero.y}) HP{pre.hero.hp}"
    fin = replay_all(spliced)
    h = fin.hero
    assert (fin.current_floor == best_row["floor"] and h.hp == best_row["hp"]
            and h.atk == best_row["atk"] and h.def_ == best_row["def"]), \
        (f"整串终态不符: {fin.current_floor} HP{h.hp} ATK{h.atk} DEF{h.def_} "
         f"vs cut {best_row['floor']} HP{best_row['hp']} ATK{best_row['atk']} DEF{best_row['def']}")

    tag = f"{beta:g}".replace(".", "")
    out_path = ROOT / f"beta{tag}_mt10_route.h5route"
    write_h5route(out_path, spliced, DEFAULT_META)
    red = h.keys.get("redKey", 0)
    held = {k: v for k, v in h.keys.items() if v}
    return dict(path=out_path, prefix_len=len(prefix), beta_steps=len(beta_actions),
                total=len(spliced),
                floor=fin.current_floor, x=h.x, y=h.y, hp=h.hp, atk=h.atk, def_=h.def_,
                keys=held, red=red, margin_seen=h.hp - D, D=D)


def main():
    beta = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    info = gen(beta)
    print("=" * 84)
    print(f"β={beta:g} best-MT10 路线 → {info['path'].name}")
    print("=" * 84)
    print(f"前缀 tokens[:{info['prefix_len']}]（开局噩梦→MT3 入口）"
          f" + β 段 {info['beta_steps']} 步（纯 RULD，无 FMT）"
          f" = 共 {info['total']} token")
    print(f"封板 sim 预检终态: {info['floor']}({info['x']},{info['y']}) "
          f"HP={info['hp']} ATK={info['atk']} DEF={info['def_']} "
          f"持钥={info['keys']}  红钥匙={info['red']}  ✅对账一致")
    print(f"搜索看到 HP−D = {info['margin_seen']}（D：红门免费 + 埋伏漏算，是上界幻觉）")
    print(f"文件: {info['path']}")
    print(f"→ 网站回放预计：走到 MT10 入口 ({info['x']},{info['y']}) HP={info['hp']}、"
          f"红钥匙={info['red']}，路线到此结束（不会撞红门 6,9）。")


if __name__ == "__main__":
    main()
