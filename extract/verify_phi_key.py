"""D_rel 函数级自检 + 零回归断言（extract/ 驱动层，不跑搜索）。

跑大搜索(probe_crossfloor_beam --score vzone --kappa)前先抓函数级错，证三件事：
  (1) 零回归基线：v_zone_score(zone,s,κ=0)[0] 与 v_zone(zone,s)[0] 字节一致（所有采样态）；
  (2) admissible 单调：κ>0 时 boss_savings ≥ 0（D(κ)=D_free−κ·savings ≤ D_free，只会更松不会高估）；
  (3) κ>0 时 score = (HP−D_free) + κ·savings 精确成立（savings=boss_toll(当前)−boss_toll(当前+Δ可达)）。

Φ_key 项已废（钥匙价值从 D_rel 的 boss 折价自然落出，不再单列）。
采样态来自重放玩家 route【开局噩梦之后】的轨迹（与搜索起点同口径），覆盖 MT1-10 不同
位置/钥匙持有，是真实态而非构造态。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from probe_crossfloor import OPENING_PREFIX
from sim.simulator import step
from vzone import build_zone, v_zone, v_zone_score

ZONE_FLOORS = {f"MT{i}" for i in range(1, 11)}


def main():
    zone = build_zone()
    base = build_initial_state()
    tokens = load_tokens()

    # 沿 route 采样：开局噩梦后、且在一区(MT1-10)的态，每 ~20 步取一个
    samples = []
    s = base
    for i, tok in enumerate(tokens):
        s = step(s, tok)
        if i >= OPENING_PREFIX - 1 and s.current_floor in ZONE_FLOORS and i % 20 == 0:
            samples.append(s)
    print(f"采样一区态 {len(samples)} 个（route 重放、开局噩梦后、MT1-10）")
    print("=" * 96)

    # (1) 零回归：κ=0 字节一致
    n_mismatch = 0
    for s in samples:
        a = v_zone(zone, s)[0]
        b = v_zone_score(zone, s, 0.0)[0]
        if a != b and not (a != a and b != b):   # NaN 不会出现；-inf==-inf 为 True
            n_mismatch += 1
            print(f"  ✗ 零回归不符 {s.current_floor}({s.hero.x},{s.hero.y}): v_zone={a} score0={b}")
    print(f"(1) κ=0 字节一致：{len(samples)-n_mismatch}/{len(samples)} 通过"
          + ("  ✅" if n_mismatch == 0 else f"  ✗ {n_mismatch} 个不符"))

    # (2)(3) D_rel 折价：savings≥0(admissible) + κ>0 分解精确
    print("-" * 96)
    print("(2)(3) D_rel 明细（Δ可达攻防 / boss省）+ κ=1 分解（score = HP−D_free + κ·savings）：")
    KAP = 1.0
    n_save_neg = 0
    n_save_pos = 0
    n_decomp_ok = 0
    n_checked = 0
    for s in samples:
        vz, D, _ = v_zone(zone, s)
        score, D2, savings, info = v_zone_score(zone, s, KAP)
        if D == float("inf") or D == 0:
            continue          # 无路/已清态跳过（无 boss 可折价）
        n_checked += 1
        if savings < 0:
            n_save_neg += 1
            print(f"  ✗ savings<0 {s.current_floor}({s.hero.x},{s.hero.y}): {savings}")
        if abs(score - (vz + KAP * savings)) < 1e-6:
            n_decomp_ok += 1
        else:
            print(f"  ✗ 分解不符 {s.current_floor}({s.hero.x},{s.hero.y}): "
                  f"score={score} vz+κ·s={vz + KAP * savings}")
        if savings > 0:
            n_save_pos += 1
            keys = {k: v for k, v in s.hero.keys.items() if v}
            print(f"  {s.current_floor}({s.hero.x},{s.hero.y}) HP={s.hero.hp} "
                  f"atk={s.hero.atk} def={s.hero.def_} keys={keys}  {info}")
    print("-" * 96)
    print(f"(2) boss_savings ≥ 0（admissible 单调）：{n_checked-n_save_neg}/{n_checked}  "
          + ("✅" if n_save_neg == 0 else f"✗ {n_save_neg} 个为负"))
    print(f"(3) κ>0 分解 score==HP−D_free+κ·savings 精确：{n_decomp_ok}/{n_checked}  "
          + ("✅" if n_decomp_ok == n_checked else "✗"))
    print(f"    savings>0（Δ可达能让 boss 变便宜）的态 {n_save_pos} 个")
    print("=" * 96)


if __name__ == "__main__":
    main()
