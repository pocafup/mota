"""【§S26 红钥末腿契约·单测（@slow·真 decode+navigate）】钉死「头部精英末腿」两半行为，绝不让接线悄悄走样。

§S26 玩家用游戏知识定的命门：「ATK26 够不到红钥是基因不扎实(HP薄/位置差)非属性不够」——「够得到」看
【整个状态扎实度】不只看属性数字。本测用 build_harness 现成的【真实状态】坐实这条，覆盖末腿两段分支：
  ① miss 半（薄/弱态）：harness start（HP400/ATK10/DEF10·打不过 yellowGuard atk48）→ 红钥末腿够不到 →
     【原子空操作】（终态逐字段==入口·绝不判 invalid·早代弱基因留属性梯度防早熟塌缩）→ 不加 B。
  ② reach 半（689 式扎实态）：s689（HP689/ATK26/DEF25·过 boss 路线终态）→ 红钥末腿【真导航一腿】够到红钥 →
     reached_final=True、红钥进包 → eval 整体 +B（且恰好 B·北极星二段奖励·κ=1 在 wrapper 加非 fitness 本体）。
★同属性(26/25)不同扎实度(HP184 vs 689)够不到/够得到——本测的 start vs s689 正是这条命门的活体（数据驱动·非手写）。
封板件 fitness/decode/navigate_to/detect 一字不改：本测只调它们的现成组合（_decode_with_order / make_decode_fitness_eval）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest                                                          # noqa: E402

RED_CAP = 8000          # 末腿专用弹出护栏（与 launcher 默认 redcap 同·标定暂定值）
BONUS_B = 500.0         # 北极星二段奖励（与 launcher 默认 bonusb 同量级）


@pytest.fixture(scope="module")
def rl():
    """红钥末腿电池组（build_harness 一次·重 import 局部化不拖快测 collection·共享 decode_cache 暖桶）。"""
    from ga_loop import build_harness
    h = build_harness()
    assert h["red_block"] is not None and h["red_markers"], "红钥块未涌现 → 数据/detect 漂移，须核对"
    return h


def _redleg_decode(h, start_state):
    """从 start_state 跑【空基因 + 红钥末腿】→ 唯一一腿就是红钥末腿（隔离末腿契约·不掺主循环）。"""
    from ga_loop import _decode_with_order
    return _decode_with_order(
        [], start_state, h["zone"], h["step"], h["decode_cache"],
        block_markers=h["block_markers"], block_cells=h["meta"]["block_cells"],
        final_goal=h["red_block"], final_markers=h["red_markers"], final_max_pops=RED_CAP)


# ── ① miss 半：薄/弱态 → 原子空操作（终态不变·不判 invalid·不加 B）─────────────────────────────
@pytest.mark.slow
def test_redleg_miss_is_atomic_noop(rl):
    """harness start（HP400/ATK10/DEF10·薄）→ 红钥末腿够不到 → 终态逐字段==入口（原子空操作）·非 invalid。"""
    start = rl["start"]
    _t, final, _nz, v = _redleg_decode(rl, start)
    assert v["reached_final"] is False, f"薄态不该够到红钥，实得 {v}"
    assert v["invalid"] is False, "末腿 miss 必须是原子空操作·绝不判 invalid（否则早代弱基因全废→早熟塌缩）"
    # 终态==入口（state 原样·navigate_to 返回入口态本体）
    assert final.current_floor == start.current_floor
    assert (final.hero.x, final.hero.y) == (start.hero.x, start.hero.y)
    assert final.hero.hp == start.hero.hp
    assert final.hero.atk == start.hero.atk
    assert final.hero.def_ == start.hero.def_


# ── ② reach 半：689 式扎实态 → 真导航够到红钥（reached_final + 进包）──────────────────────────────
@pytest.mark.slow
def test_redleg_reach_from_solid_689(rl):
    """s689（HP689/ATK26/DEF25·扎实）→ 红钥末腿【真走一腿】够到红钥 → reached_final=True + 红钥进包(终态空)。"""
    from ga_loop import _taken
    s689 = rl["s689"]
    _t, final, _nz, v = _redleg_decode(rl, s689)
    assert v["invalid"] is False
    assert v["reached_final"] is True, f"689 式扎实态应够到红钥，实得 {v}"
    assert v["navigated"] >= 1, "应真导航一腿（非起点已在手）→ 坐实 navigate_to 自走去取红钥"
    assert all(_taken(final, c) for c in rl["red_markers"]), "红钥 cell 终态应已空（进包）"


# ── ② reach 的 B：reached 时 eval 整体 +B 且恰好 B（同 final_goal 下 B 版 − 0 版 == B）──────────────
@pytest.mark.slow
def test_redleg_bonus_b_added_exactly_on_reach(rl):
    """689 式扎实态 reach → make_decode_fitness_eval 的 wrapper 整体 +B：B 版与 B=0 版（同末腿·同终态）之差恰为 B。"""
    from ga_loop import make_decode_fitness_eval
    s689 = rl["s689"]
    common = dict(decode_cache=rl["decode_cache"], block_markers=rl["block_markers"],
                  block_cells=rl["meta"]["block_cells"], final_goal=rl["red_block"],
                  final_markers=rl["red_markers"], final_max_pops=RED_CAP)
    elite_B, _ = make_decode_fitness_eval(s689, rl["zone"], rl["step"], rl["roster_fit"],
                                          rl["big"], rl["zone_fids"], bonus_b=BONUS_B, **common)
    elite_0, _ = make_decode_fitness_eval(s689, rl["zone"], rl["step"], rl["roster_fit"],
                                          rl["big"], rl["zone_fids"], bonus_b=0.0, **common)
    assert elite_B([]) - elite_0([]) == pytest.approx(BONUS_B), "reach 段应整体 +B（恰好 B·不多不少）"


# ── ① miss 的无 B：miss 时不加 B（弱态 B 版 == 无末腿 base 版 == fitness(start)）─────────────────────
@pytest.mark.slow
def test_redleg_no_bonus_on_miss(rl):
    """薄态末腿 miss → 终态==start（原子空操作）→ 带末腿+B 的 eval == 不带末腿的 base eval（reached 段没触发·B 没加）。"""
    from ga_loop import make_decode_fitness_eval
    start = rl["start"]
    base_ev, _ = make_decode_fitness_eval(
        start, rl["zone"], rl["step"], rl["roster_fit"], rl["big"], rl["zone_fids"],
        decode_cache=rl["decode_cache"], block_markers=rl["block_markers"],
        block_cells=rl["meta"]["block_cells"])                       # 无 final_goal=纯 base
    elite_ev, _ = make_decode_fitness_eval(
        start, rl["zone"], rl["step"], rl["roster_fit"], rl["big"], rl["zone_fids"],
        decode_cache=rl["decode_cache"], block_markers=rl["block_markers"],
        block_cells=rl["meta"]["block_cells"], final_goal=rl["red_block"],
        final_markers=rl["red_markers"], final_max_pops=RED_CAP, bonus_b=BONUS_B)
    assert elite_ev([]) == base_ev([]), "miss 不加 B 且原子空操作不改终态 → 与纯 base 逐数一致"
