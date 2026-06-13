"""把组合扫描里【真过 boss】那条 Pareto 态导出 .h5route（玩家 h5mota 网站看引擎回放·终审）。

照 gen_beta_h5route 模板，但源改取 floorbest jsonl，并【自动挑选】：
  优先=置位 BOSS_FLAG「10f战胜骷髅队长」且 HP>0 的态里 HP 最高那条（真杀队长）；
  若无过 boss 态=最深到达层里 HP 最高那条（展示卡在哪）。
流程：拼前缀 tokens[:OPENING_PREFIX]（开局噩梦→MT3 入口）+ 解算动作串（纯 RULD，踏楼梯 sim 自动换层、
不插 FMT，见 gen_beta_h5route 注释）→ 封板 sim 预检对账终态 → write_h5route。网站回放才是终审。

跑法：python extract/gen_bosspass_h5route.py <floorbest.jsonl>
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

from sim.simulator import step, _copy_state
from solver.verify import replay
from probe_crossfloor import build_start, OPENING_PREFIX, _fidx
from export_mt10_boss_route import load_tokens
from gen_h5routes import replay_all
from encode_route import write_h5route, DEFAULT_META
from vzone import BOSS_FLAG


def pick_row(rows, start):
    """重放每条 → 优先真过 boss(flag+HP>0) 里 HP 最高；否则最深层 HP 最高。返回 (row, final, passed)。"""
    passers, all_eval = [], []
    for r in rows:
        fin = replay(start, r["actions"], step, _copy_state)
        h = fin.hero
        passed = bool(h.flags.get(BOSS_FLAG)) and h.hp > 0
        all_eval.append((r, fin, passed))
        if passed:
            passers.append((r, fin, passed))
    if passers:
        return max(passers, key=lambda t: t[1].hero.hp)
    return max(all_eval, key=lambda t: (_fidx(t[1].current_floor), t[1].hero.hp))


def main():
    if len(sys.argv) < 2:
        sys.exit("跑法：python gen_bosspass_h5route.py <floorbest.jsonl>")
    fb = Path(sys.argv[1])
    if not fb.is_absolute():
        fb = ROOT / "extract" / fb.name
    rows = [json.loads(ln) for ln in fb.read_text(encoding="utf-8").splitlines() if ln.strip()]
    start, _ = build_start()
    row, fin, passed = pick_row(rows, start)
    actions = list(row["actions"])

    tokens = load_tokens()
    prefix = tokens[:OPENING_PREFIX]
    spliced = prefix + actions

    pre = replay_all(prefix)
    assert pre.current_floor == "MT3" and pre.hero.hp == 400, \
        f"前缀终态不符: {pre.current_floor} ({pre.hero.x},{pre.hero.y}) HP{pre.hero.hp}"
    chk = replay_all(spliced)
    h = chk.hero
    assert (chk.current_floor == row["floor"] and h.hp == row["hp"]
            and h.atk == row["atk"] and h.def_ == row["def"]), \
        (f"整串终态不符: {chk.current_floor} HP{h.hp} ATK{h.atk} DEF{h.def_} "
         f"vs floorbest {row['floor']} HP{row['hp']} ATK{row['atk']} DEF{row['def']}")

    tag = fb.name.replace("crossbeam_floorbest_", "").replace(".jsonl", "")
    kind = "BOSSPASS" if passed else "deepest"
    out_path = ROOT / f"{kind}_{tag}.h5route"
    write_h5route(out_path, spliced, DEFAULT_META)

    held = {k: v for k, v in h.keys.items() if v}
    boss_flag = bool(h.flags.get(BOSS_FLAG))
    print("=" * 88)
    print(f"源 {fb.name}")
    print(f"挑中：{'★★★真过boss' if passed else '✖未过boss·最深态'}  "
          f"终态 {chk.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_}")
    print(f"  BOSS_FLAG「{BOSS_FLAG}」={boss_flag}  持钥={held}  红钥={h.keys.get('redKey', 0)}")
    print(f"前缀 tokens[:{len(prefix)}] + 解算 {len(actions)} 步 = 共 {len(spliced)} token  ✅封板对账一致")
    print(f"文件 → {out_path}")
    print("=" * 88)


if __name__ == "__main__":
    main()
