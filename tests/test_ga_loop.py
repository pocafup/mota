"""【GA 主循环·进化机器 单元验证】钉死 run_ga 的范式正确性，全程用【假 eval_fn】——不跑 decode/
navigate_to（盾 26s），秒级。证的是【进化机器本身】对不对（玩家 2026-06-13 拍板：第一棒只证『真在进化』）：
  · 变异恒产合法子集（无重、∈pool）、三算子(swap/insert/delete)都可行；
  · 锦标赛选 fitness 高者；精英保留 → 每代最优单调不降；
  · fitness 缓存按基因元组去重（同基因不重复评估）；固定 seed 可复现；
  · 合成 fitness（有爬坡头寸·随机初值非最优）下末代最优 > 初代最优 = 真爬坡。

真·decode+fitness 的端到端最优解留 extract/ga_loop.py 的 __main__ 跑（耗时分钟级·不进单测）。
"""
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest

from ga_loop import (
    _random_individual, _mutate, _tournament, run_ga, GAResult,
)

POOL = list(range(8))   # 假 pool：8 个可哈希"目标"（int 当 cell 占位，机器不认 cell 语义）


def _is_valid_subset(ind, pool):
    return len(ind) == len(set(ind)) and all(g in pool for g in ind) and len(ind) >= 1


# ── 变异：恒产合法子集 + 三算子都可行 ─────────────────────────────────────────────
def test_random_individual_valid():
    rng = random.Random(1)
    for _ in range(200):
        ind = _random_individual(POOL, rng)
        assert _is_valid_subset(ind, POOL)


def test_mutate_always_valid_subset():
    rng = random.Random(2)
    for _ in range(500):
        base = _random_individual(POOL, rng)
        child = _mutate(base, POOL, rng)
        assert _is_valid_subset(child, POOL)
        assert child is not base                      # 不改入参（返回新基因）


def test_mutate_does_not_mutate_input():
    rng = random.Random(3)
    base = [0, 1, 2, 3]
    snapshot = list(base)
    for _ in range(50):
        _mutate(base, POOL, rng)
    assert base == snapshot                            # 入参原样


def test_mutate_operators_all_reachable():
    """500 次变异里 swap(同集换序)/insert(变长+1)/delete(变长−1) 三种结果都出现过。"""
    rng = random.Random(4)
    base = [0, 1, 2, 3]                                # len4·有缺失可插 → 三算子都可行
    saw_swap = saw_insert = saw_delete = False
    for _ in range(500):
        child = _mutate(base, POOL, rng)
        if len(child) == len(base) + 1:
            saw_insert = True
        elif len(child) == len(base) - 1:
            saw_delete = True
        elif set(child) == set(base) and child != base:
            saw_swap = True
    assert saw_swap and saw_insert and saw_delete


def test_mutate_full_pool_no_insert():
    """基因==整个 pool（无可插）→ 只 swap/delete，永不越界插重。"""
    rng = random.Random(5)
    full = list(POOL)
    for _ in range(200):
        child = _mutate(full, POOL, rng)
        assert _is_valid_subset(child, POOL)
        assert len(child) <= len(POOL)                 # 不会插重变长


def test_mutate_singleton_pool_returns_same():
    """pool 仅 1 个 + 基因==pool（len<2 且无可插）→ 无可行算子 → 原样返回。"""
    rng = random.Random(6)
    out = _mutate([42], [42], rng)
    assert out == [42]


# ── 锦标赛选择：选 fitness 高者 ───────────────────────────────────────────────────
def test_tournament_picks_highest_when_k_full():
    rng = random.Random(7)
    scored = [(10.0, [0]), (50.0, [1]), (30.0, [2]), (5.0, [3])]
    for _ in range(50):
        win = _tournament(scored, k=len(scored), rng=rng)
        assert win == [1]                              # k=全员 → 必选最高分


def test_tournament_returns_copy():
    rng = random.Random(8)
    gene = [1, 2, 3]
    scored = [(99.0, gene)]
    win = _tournament(scored, k=1, rng=rng)
    assert win == gene and win is not gene             # 副本（防后续变异污染种群）


# ── 精英 + 爬坡：每代最优单调不降；合成梯度下真爬坡 ───────────────────────────────
def _ordered_target_eval(target):
    """合成 fitness：基因越接近【target 全序】分越高（位置对 +10、在场 +1）。
    全序最优 = 10·len + len；随机初值几乎不可能命中 → 给爬坡留足头寸。可哈希、纯函数。"""
    def ev(gene):
        s = 0
        for i, g in enumerate(gene):
            if i < len(target) and g == target[i]:
                s += 10
            s += 1
        return s
    return ev


def test_elitism_monotonic_nondecreasing():
    """精英 top-k 原样进下一代 → 每代最优 fitness 单调不降（机器铁律·与具体 eval 无关）。"""
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=20, generations=25, elite=2, seed=123)
    gb = res.gen_best_fitness
    assert all(gb[i + 1] >= gb[i] for i in range(len(gb) - 1)), gb


def test_climbs_on_synthetic_gradient():
    """有爬坡头寸的合成梯度 → 末代最优【严格 >】初代最优 = 范式真在进化（核心验证门）。"""
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=20, generations=30, elite=2, seed=20260613)
    assert res.gen_best_fitness[-1] > res.gen_best_fitness[0], res.gen_best_fitness
    assert res.best_fitness == res.gen_best_fitness[-1]          # 全程最优==末代最优(精英)


def test_best_individual_matches_best_fitness():
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=16, generations=20, seed=7)
    assert ev(res.best_individual) == res.best_fitness


# ── fitness 缓存：同基因不重复评估 ───────────────────────────────────────────────
def test_fitness_cache_dedup():
    """eval_fn 调用次数 == 去重基因数（n_unique_evals）；且 < pop·gen（确有命中省算）。"""
    calls = {"n": 0}
    target = list(POOL)
    base_ev = _ordered_target_eval(target)

    def counting_ev(gene):
        calls["n"] += 1
        return base_ev(gene)

    pop, gens = 16, 12
    res = run_ga(POOL, counting_ev, population=pop, generations=gens, seed=99)
    assert calls["n"] == res.n_unique_evals            # 每个唯一基因只冷算一次
    assert res.n_unique_evals < pop * gens             # 精英+收敛 → 必有重复命中缓存


# ── 可复现：同 seed 同结果 ───────────────────────────────────────────────────────
def test_reproducible_same_seed():
    ev = _ordered_target_eval(list(POOL))
    a = run_ga(POOL, ev, population=16, generations=15, seed=2024)
    b = run_ga(POOL, ev, population=16, generations=15, seed=2024)
    assert a.gen_best_fitness == b.gen_best_fitness
    assert a.best_individual == b.best_individual
    assert a.n_unique_evals == b.n_unique_evals


def test_different_seed_may_differ():
    """不同 seed 至少在过程上不恒等（弱证随机源真生效·非死循环固定）。"""
    ev = _ordered_target_eval(list(POOL))
    a = run_ga(POOL, ev, population=12, generations=10, seed=1)
    b = run_ga(POOL, ev, population=12, generations=10, seed=2)
    # 末代最优都应到顶或接近，但中途曲线/去重数大概率不同
    assert (a.gen_best_fitness != b.gen_best_fitness) or (a.n_unique_evals != b.n_unique_evals)


# ── 边界：空 pool 报错 ───────────────────────────────────────────────────────────
def test_empty_pool_raises():
    with pytest.raises(ValueError):
        run_ga([], _ordered_target_eval([]), population=4, generations=2)


# ── GAResult 结构完整 ────────────────────────────────────────────────────────────
def test_result_shape():
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=10, generations=5, seed=11)
    assert isinstance(res, GAResult)
    assert len(res.gen_best_fitness) == 5
    assert len(res.gen_history) == 5
    assert all(len(gen) == 10 for gen in res.gen_history)       # 每代记录 population(=10) 个
