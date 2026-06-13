"""把指定 crossbeam_floorbest jsonl 的 best-MT10 路线导出成 .h5route（网站引擎回放）。
口径镜像 region_route_disease_audit.gen_region_h5route：floor==MT10 按真实 V=HP−D 取顶(pick_best_mt10)，
拼开局噩梦前缀(tokens[:OPENING_PREFIX]→MT3 入口)，纯 RULD 踏楼梯 sim 自动换层(无 FMT)，引擎封板逐字段断言。

用法：python export_alpha_best.py <floorbest.jsonl> <out_name.h5route>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from vzone import build_zone
from probe_crossfloor import build_start, OPENING_PREFIX
from export_bscan_routes import load_rows, pick_best_mt10
from export_mt10_boss_route import load_tokens
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META


def main():
    if len(sys.argv) < 3:
        sys.exit("用法：python export_alpha_best.py <floorbest.jsonl> <out_name.h5route>")
    src = Path(sys.argv[1])
    if not src.is_absolute():
        src = Path(__file__).parent / src.name
    out_name = sys.argv[2]

    start = build_start()[0]
    zone = build_zone()
    rows = load_rows(src)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        sys.exit(f"源 {src.name} 无 MT10 行，无法导出")
    best_row, sfin, vz, D = pick_best_mt10(zone, start, mt10)
    region_actions = list(best_row["actions"])

    tokens = load_tokens()
    prefix = tokens[:OPENING_PREFIX]               # 开局噩梦 → MT3 入口
    spliced = prefix + region_actions              # 纯 RULD，踏楼梯 sim 自动换层（不插 FMT）

    pre = replay_all(prefix)
    assert pre.current_floor == "MT3" and pre.hero.hp == 400, \
        f"前缀终态不符: {pre.current_floor}({pre.hero.x},{pre.hero.y}) HP{pre.hero.hp}"
    fin = replay_all(spliced)
    h = fin.hero
    assert (fin.current_floor == best_row["floor"] and h.hp == best_row["hp"]
            and h.atk == best_row["atk"] and h.def_ == best_row["def"]), \
        (f"整串终态不符: {fin.current_floor} HP{h.hp} ATK{h.atk} DEF{h.def_} "
         f"vs {best_row['floor']} HP{best_row['hp']} ATK{best_row['atk']} DEF{best_row['def']}")

    out_path = Path(__file__).resolve().parent.parent / out_name
    write_h5route(out_path, spliced, DEFAULT_META)
    held = {k: v for k, v in h.keys.items() if v}
    print(f"✅ 导出 {out_path.name}")
    print(f"   源 {src.name}  best-MT10 V=HP−D={vz:,.0f}（D={D:,.0f}）")
    print(f"   前缀 {len(prefix)} token + region 段 {len(region_actions)} 步 = 共 {len(spliced)} token（纯 RULD 无 FMT）")
    print(f"   封板终态：{fin.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
          f"持钥={held} 红钥={h.keys.get('redKey', 0)} ✅逐字段对账一致")
    print(f"   ⚠ 到 MT10 仍无红钥匙(老问题)→ 网站回放走到 MT10 入口即止、不撞红门。")


if __name__ == "__main__":
    main()
