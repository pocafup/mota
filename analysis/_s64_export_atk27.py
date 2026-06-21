# -*- coding: utf-8 -*-
"""§S64 导出 ATK27 半截 h5route（玩家要看网站回放）

§S62 全跑 maxATK=27(到达过)·但 res 没存盘·ATK27 态的动作串只活在当时内存
res._best_acts(=按(atk,hp)选的锚点=ATK27态·smart_phi_s53_beam:338)。
本脚本【确定性重跑】§S62 full_run(同 L/max_states/score_fn → 必复现同一 ATK27 态)·
跑完用 export_halfway_h5route 导出 _best_acts(ATK27)成 .h5route + sim 独立重放自检。

⚠这是【半截】路线：走到 ATK27 但【没破红钥门】(found=False·墙2)·非通关。
   交付玩家时务必标注：网站回放看到的是 grind 到 ATK27 那一刻、不是通关。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis._s62_lookahead_full import (                                  # noqa: E402
    setup, make_score_fn, REDKEY_CELL, BEAM_K, MULT, _fmt,
)
from analysis.smart_phi_s53_beam import run_full                            # noqa: E402
from analysis.dir2_redkey_pathloss_beam import (                            # noqa: E402
    export_halfway_h5route, make_seg_step, REAL_LEG_FLOORS,
)

L = 8
MAX_STATES = 1_800_000        # 同 §S62 全跑·保证复现 ATK27（§S63 的 400k 只到 ATK26）


def main():
    t0 = time.time()
    start, phi_loss, diag = setup()
    seg = make_seg_step(REAL_LEG_FLOORS)
    score_fn = make_score_fn(phi_loss, seg, L, MULT)
    print(f"setup 就绪 {time.time()-t0:.1f}s · 起点 {_fmt(start)} · L={L} max_states={MAX_STATES}", flush=True)

    res = run_full(start, REDKEY_CELL, REAL_LEG_FLOORS, BEAM_K, MAX_STATES, score_fn, diag,
                   enable_fly=True)
    maxatk = max((b["atk"] for b in res._best_by_floor.values()), default=0)
    print(f"\n跑完 found={res.found} 耗时={res._secs:.1f}s ({res._secs/3600:.2f}h) "
          f"maxATK={maxatk} hit_cap={res.hit_cap}", flush=True)

    snap = res._best_acts.get("snap")
    print(f"_best_acts 锚点(按 max(atk,hp) 选) snap = {snap}", flush=True)
    if not snap or snap[3] < 27:
        print(f"⚠ 锚点 ATK={snap[3] if snap else '?'} <27 → 没到 ATK27·不导出（须排查·别给坏文件）")
        return

    print(f"\n✓ 锚点 ATK={snap[3]}≥27 → 导出 ATK27 半截 h5route + sim 重放自检：")
    out = export_halfway_h5route(res._best_acts, "s62_atk27_L8")
    print(f"\n导出文件: {out}")
    print("⚠ 半截路线：网站回放看到 grind 到 ATK27、没破红钥门、非通关。")


if __name__ == "__main__":
    main()
