"""守卫单测（命门）：钉死目标导向 pull 的三层分离，防 κ=1 反向病在 beam 截断层复发。

玩家 2026-06-10 拍板的两条命门（必须先过，才允许开 β 一次一变量扫）：
  命门①  加 pull 后 value_vector(state) 逐字节不变 —— pull / 排序基分绝不污染【无损剪枝界】。
  命门②  κ=0 / β=0 字节零回归 —— beam_rank_score(β=0) 严格 == v_zone_score(κ=0)[0]，
          且整条 search_quotient 行为逐字段不变（在 κ=1 真正作恶的 beam 截断层等价）。

三层分离（Check① 已查清剪枝口径）：
  剪枝界  value_vector（solver/search._value_map，纯持有资源多维 Pareto）            ⊥
  排序基分 v_zone_score(κ=0)[0] = HP − D_free（当前属性算 = 已兑现，拿到才降）        ⊥
  pull    引导项（朝可达高区势能下降道具，只进 beam score_override，绝不进 D/value）。

电池组用【真引擎重放 route token 到多检查点】取态（遵铁律：绝不手造态 / 手算属性），
覆盖 MT3/5/7/8/9、atk10→25、def10→23、pull 0.6→100，含区内带宝石(pull>0)与换属性后多样态。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest

import vzone as VZ
from probe_crossfloor import build_start
from seg_experiment import load_tokens
from sim.simulator import step, _copy_state
from solver.search import _value_map
from solver.quotient import value_vector, search_quotient

# 纯资源剪枝维白名单：标量键 + 这些前缀。出现任何别的键 = base/pull/κ/D/savings 泄漏进剪枝界。
_SCALAR_KEYS = {"hp", "atk", "def", "mdef", "gold", "kill"}
_ALLOWED_PREFIXES = ("key:", "item:")


def _is_resource_key(k):
    return k in _SCALAR_KEYS or any(k.startswith(p) for p in _ALLOWED_PREFIXES)


@pytest.fixture(scope="module")
def zone():
    return VZ.build_zone()


@pytest.fixture(scope="module")
def battery():
    """真引擎重放 route 到多 token 检查点的态电池组（全 engine-true，绝不手造态/手改属性）。"""
    start, nopen = build_start()
    toks = load_tokens()
    ckpts = [82, 120, 160, 220, 300, 400, 520, 680]
    snaps = [_copy_state(start)]            # 检查点 82 = 噩梦后起点本身
    s = start
    for i in range(nopen, max(ckpts)):
        if i >= len(toks):
            break
        s = step(s, toks[i])
        if (i + 1) in ckpts:
            snaps.append(_copy_state(s))
    assert len(snaps) >= 6, f"电池组态过少({len(snaps)})，重放检查点失败"
    return snaps


# ───────────────────────── 命门①：value_vector 纯净 + pull/rank 不改态 ─────────────────────────

def test_value_vector_is_pruning_key_identity():
    """剪枝键就是 _value_map 本体（结构证明 pull 没被接进无损剪枝维）。"""
    assert value_vector is _value_map


def test_value_vector_only_resources(battery):
    """每个电池态：value_vector 只含纯资源键，无 base/pull/κ/D/savings 泄漏。"""
    for s in battery:
        vv = value_vector(s)
        leaked = [k for k in vv if not _is_resource_key(k)]
        assert not leaked, f"剪枝维泄漏非资源键 {leaked}（floor={s.current_floor}）"


def test_pull_and_rank_do_not_mutate_state(zone, battery):
    """调 pull / beam_rank_score(β>0) 绝不改 value_vector 或任何 hero 字段（引导项纯只读）。"""
    hero_scalars = ("hp", "atk", "def_", "mdef", "gold", "x", "y", "kill_count")
    for s in battery:
        before_vv = dict(value_vector(s))
        before_scalars = {a: getattr(s.hero, a) for a in hero_scalars}
        before_keys = dict(s.hero.keys)
        before_items = dict(s.hero.items)
        before_flags = dict(s.hero.flags)

        VZ.pull(zone, s)
        VZ.beam_rank_score(zone, s, beta=5.0)

        assert dict(value_vector(s)) == before_vv, f"pull/rank 改了 value_vector(floor={s.current_floor})"
        assert {a: getattr(s.hero, a) for a in hero_scalars} == before_scalars, "pull/rank 改了 hero 标量"
        assert dict(s.hero.keys) == before_keys, "pull/rank 改了 hero.keys"
        assert dict(s.hero.items) == before_items, "pull/rank 改了 hero.items"
        assert dict(s.hero.flags) == before_flags, "pull/rank 改了 hero.flags"


# ───────────────────────── 命门②：β=0 / κ=0 字节零回归 ─────────────────────────

def test_beta0_byte_identical_to_kappa0_scalar(zone, battery):
    """beam_rank_score(β=0) 必须逐态字节 == v_zone_score(κ=0)[0]（含 -inf 不可达态）。"""
    for s in battery:
        base = VZ.v_zone_score(zone, s, kappa=0.0)[0]
        rank0 = VZ.beam_rank_score(zone, s, beta=0.0)
        assert rank0 == base or (base == float("-inf") and rank0 == float("-inf")), \
            f"β=0 非零回归：base={base!r} rank0={rank0!r}(floor={s.current_floor})"


def test_pull_layers_additively(zone, battery):
    """层分离正确性：β>0 时 rank == base + β·pull 精确（pull 只叠加、不渗进 base）；
       base=-inf 不可达态任何 β 仍 -inf（pull 不得把不可达态抬过可达态）。"""
    beta = 3.0
    for s in battery:
        base = VZ.v_zone_score(zone, s, kappa=0.0)[0]
        pl = VZ.pull(zone, s)
        rank = VZ.beam_rank_score(zone, s, beta=beta)
        if base == float("-inf"):
            assert rank == float("-inf")
        else:
            assert rank == base + beta * pl, f"层未严格相加(floor={s.current_floor})"


def test_pull_nonneg_and_gated(zone, battery):
    """pull 契约：恒 ≥ 0；区外 / 已胜 boss → 严格 0（可达性 + 拾取兑现门控）。"""
    for s in battery:
        pl = VZ.pull(zone, s)
        assert pl >= 0.0, f"pull 出负值 {pl}(floor={s.current_floor})"
        out_zone = s.current_floor not in zone["floors"]
        won = bool(s.hero.flags.get(VZ.BOSS_FLAG))
        if out_zone or won:
            assert pl == 0.0, f"区外/已胜 boss 仍 pull={pl}(floor={s.current_floor})"


@pytest.mark.slow
def test_search_byte_identical_kappa0_vs_beta0():
    """最强命门：在 κ=1 真正作恶的 beam 截断层，旧打分(v_zone_score κ=0) 与
       新打分(beam_rank_score β=0) 跑 search_quotient 必须逐字段同结果。
       小 cap+小 beam、目标格设不可达 → 强制穷尽探索撞 cap、覆盖大量截断决策。"""
    z = VZ.build_zone()
    cap, beam = 4000, 16
    goal = ("MT0", 1, 1)            # 楼梯不可达 → 纯探索撞 cap，最大化截断决策覆盖

    def run(score_fn):
        start, _ = build_start()
        memo = {}

        def fn(s):                  # 按对象 memo（同 probe 驱动：beam_select 每点多次调 score_fn）
            hit = memo.get(id(s))
            if hit is not None and hit[0] is s:
                return hit[1]
            v = score_fn(z, s)
            memo[id(s)] = (s, v)
            return v

        return search_quotient(start, goal, step, max_states=cap, cross_floor=True,
                               beam_k=beam, beam_score_fn=fn)

    old = run(lambda z, s: VZ.v_zone_score(z, s, kappa=0.0)[0])
    new = run(lambda z, s: VZ.beam_rank_score(z, s, beta=0.0))

    for f in ("found", "states_expanded", "states_generated", "states_admitted",
              "frontier_peak", "distinct_fingerprints", "goal_hits", "hit_cap"):
        assert getattr(old, f) == getattr(new, f), \
            f"β=0 搜索行为偏离 κ=0：{f} old={getattr(old, f)} new={getattr(new, f)}"
