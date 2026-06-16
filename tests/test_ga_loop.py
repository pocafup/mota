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
    _random_individual, _mutate, _tournament, _crossover, run_ga, GAResult,
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


# ════════════════════════════════════════════════════════════════════════════════
# 第二棒新增：OX 变体交叉 _crossover + run_ga 的 crossover_rate / inject 接口
# （仍全程假 eval_fn 秒级·证交叉算子合法性 + 注入接口 + 交叉下进化机器仍对 + 字节级零回归）
# ════════════════════════════════════════════════════════════════════════════════

def _is_subsequence(sub, seq):
    """sub 是否为 seq 的子序列（保相对顺序、可不连续）。"""
    it = iter(seq)
    return all(x in it for x in sub)


class _StubRng:
    """受控 rng：randrange→固定 i、randint→固定 j，用于手验 _crossover 确定输出。"""
    def __init__(self, i, j):
        self.i, self.j = i, j

    def randrange(self, n):
        return self.i

    def randint(self, a, b):
        return self.j


# ── _crossover：后代恒合法子集 + 顺序部分继承 ───────────────────────────────────
def test_crossover_always_valid_subset():
    rng = random.Random(10)
    for _ in range(500):
        p1 = _random_individual(POOL, rng)
        p2 = _random_individual(POOL, rng)
        child = _crossover(p1, p2, POOL, rng)
        assert _is_valid_subset(child, POOL)


def test_crossover_deterministic_example():
    """手验确定例：p1=[0,1,2,3] i=1 j=3→seg=[1,2]；p2=[2,4,0,5]→rest=[4,0,5]；k=1→child=[4,1,2,0,5]。"""
    child = _crossover([0, 1, 2, 3], [2, 4, 0, 5], POOL, _StubRng(1, 3))
    assert child == [4, 1, 2, 0, 5]
    assert child[1:3] == [1, 2]                                  # seg 原样连续(保 p1 序)
    assert [g for g in child if g not in (1, 2)] == [4, 0, 5]    # rest 保 p2 序


def test_crossover_inherits_parent_orders():
    """不相交父 → rest=全 p2(保序)、seg=p1 连续段(p1 子序列)：顺序部分继承的不变式。"""
    rng = random.Random(11)
    p1, p2 = [0, 1, 2], [3, 4, 5]
    for _ in range(200):
        child = _crossover(p1, p2, POOL, rng)
        assert _is_valid_subset(child, POOL)
        assert [g for g in child if g in (3, 4, 5)] == [3, 4, 5]     # rest=p2 全员保序
        seg = [g for g in child if g in (0, 1, 2)]
        assert _is_subsequence(seg, p1)                             # seg 是 p1 子序列(连续段)


def test_crossover_does_not_mutate_inputs():
    rng = random.Random(12)
    for _ in range(200):
        p1 = _random_individual(POOL, rng)
        p2 = _random_individual(POOL, rng)
        s1, s2 = list(p1), list(p2)
        _crossover(p1, p2, POOL, rng)
        assert p1 == s1 and p2 == s2                                # 入参原样


def test_crossover_identical_parents_same_set():
    """p1==p2 → 后代是同元素集的重排(seg∪rest=p)、合法、无重。"""
    rng = random.Random(13)
    for _ in range(200):
        p = _random_individual(POOL, rng)
        child = _crossover(p, list(p), POOL, rng)
        assert _is_valid_subset(child, POOL)
        assert set(child) == set(p)


# ── run_ga + crossover_rate：交叉下进化机器仍对 ─────────────────────────────────
def test_run_ga_crossover_climbs_and_monotonic():
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=20, generations=30, elite=2,
                 crossover_rate=0.7, seed=20260613)
    gb = res.gen_best_fitness
    assert all(gb[i + 1] >= gb[i] for i in range(len(gb) - 1)), gb   # 精英单调不降
    assert gb[-1] > gb[0], gb                                        # 真爬坡
    assert _is_valid_subset(res.best_individual, POOL)               # 交叉后代仍合法


def test_reproducible_with_crossover():
    ev = _ordered_target_eval(list(POOL))
    a = run_ga(POOL, ev, population=16, generations=15, crossover_rate=0.7, seed=77)
    b = run_ga(POOL, ev, population=16, generations=15, crossover_rate=0.7, seed=77)
    assert a.gen_best_fitness == b.gen_best_fitness
    assert a.best_individual == b.best_individual
    assert a.n_unique_evals == b.n_unique_evals


def test_crossover_rate_zero_byte_identical():
    """crossover_rate=0(默认) 字节级零回归：>0 判定短路、不消耗 rng → 与不传 crossover_rate 全同。"""
    ev = _ordered_target_eval(list(POOL))
    a = run_ga(POOL, ev, population=16, generations=15, seed=2024)
    b = run_ga(POOL, ev, population=16, generations=15, crossover_rate=0.0, seed=2024)
    assert a.gen_best_fitness == b.gen_best_fitness
    assert a.best_individual == b.best_individual
    assert a.n_unique_evals == b.n_unique_evals
    assert [g for _, g in a.gen_history[-1]] == [g for _, g in b.gen_history[-1]]


# ── inject：注入个体进初始种群 ───────────────────────────────────────────────────
def test_inject_present_in_initial_population():
    ev = _ordered_target_eval(list(POOL))
    seed_ind = [5, 3, 1]
    res = run_ga(POOL, ev, population=12, generations=1, inject=[seed_ind], seed=5)
    assert seed_ind in [g for _, g in res.gen_history[0]]            # 注入个体在初代种群


def test_inject_high_fitness_retained_by_elitism():
    """注入合成最优(target 全序) → 初代最优即它、精英保住 → 全程最优==它的分。"""
    target = list(POOL)
    ev = _ordered_target_eval(target)
    res = run_ga(POOL, ev, population=12, generations=10,
                 inject=[list(target)], elite=2, seed=9)
    assert res.gen_best_fitness[0] == ev(target)                    # 初代就含最优
    assert res.best_fitness == ev(target)                           # 精英保住、无更高


def test_inject_invalid_raises():
    ev = _ordered_target_eval(list(POOL))
    for bad in ([[0, 0, 1]], [[0, 1, 99]], [[]]):                   # 重复 / ∉pool / 空
        with pytest.raises(AssertionError):
            run_ga(POOL, ev, population=8, generations=2, inject=bad, seed=1)


def test_inject_exceeding_population_raises():
    ev = _ordered_target_eval(list(POOL))
    with pytest.raises(AssertionError):
        run_ga(POOL, ev, population=4, generations=2,
                inject=[[i] for i in range(5)], seed=1)             # 5 注入 > 4 种群


# ════════════════════════════════════════════════════════════════════════════════
# §S23 早熟三旋钮：max_len / mutations_per_child / random_immigrants
# （默认均=原版行为·字节级零回归；开启时行为正确·种群尺寸守恒·仍合法仍爬坡）
# ════════════════════════════════════════════════════════════════════════════════

def test_default_levers_byte_identical():
    """三旋钮默认值(None/1/0)与完全不传 → 逐字节零回归（gen_best/最优个体/去重数/末代种群全同）。"""
    ev = _ordered_target_eval(list(POOL))
    a = run_ga(POOL, ev, population=16, generations=15, crossover_rate=0.5, seed=2024)
    b = run_ga(POOL, ev, population=16, generations=15, crossover_rate=0.5, seed=2024,
               max_len=None, mutations_per_child=1, random_immigrants=0)
    assert a.gen_best_fitness == b.gen_best_fitness
    assert a.best_individual == b.best_individual
    assert a.n_unique_evals == b.n_unique_evals
    assert [g for _, g in a.gen_history[-1]] == [g for _, g in b.gen_history[-1]]


# ── max_len：长度上限 ─────────────────────────────────────────────────────────────
def test_max_len_caps_all_genes():
    """max_len=4 → 所有代、所有个体长度 ≤ 4（初代随机/变异 insert/交叉截长 全守上限）。"""
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=16, generations=20, crossover_rate=0.6,
                 max_len=4, seed=20260613)
    for gen in res.gen_history:
        for _f, g in gen:
            assert _is_valid_subset(g, POOL) and len(g) <= 4, g


def test_max_len_operator_mutate_blocks_insert_at_cap():
    """_mutate 在 len==max_len 时绝不 insert（只 swap/delete）→ 长度永不越上限。"""
    rng = random.Random(7)
    base = [0, 1, 2, 3]                                  # len4==cap
    for _ in range(500):
        child = _mutate(base, POOL, rng, max_len=4)
        assert _is_valid_subset(child, POOL) and len(child) <= 4


def test_max_len_crossover_truncates():
    """_crossover 后代超 max_len → 截短到 max_len、仍无重合法。"""
    rng = random.Random(8)
    for _ in range(300):
        p1 = _random_individual(POOL, rng)
        p2 = _random_individual(POOL, rng)
        child = _crossover(p1, p2, POOL, rng, max_len=3)
        assert _is_valid_subset(child, POOL) and len(child) <= 3


# ── mutations_per_child：复合变异步长 ─────────────────────────────────────────────
def test_mutations_per_child_climbs_and_valid():
    """每后代多次变异仍合法、仍爬坡（更大步长不破坏机器正确性）。"""
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=20, generations=30, elite=2,
                 mutations_per_child=3, seed=20260613)
    assert _is_valid_subset(res.best_individual, POOL)
    gb = res.gen_best_fitness
    assert all(gb[i + 1] >= gb[i] for i in range(len(gb) - 1)), gb     # 精英单调不降
    assert gb[-1] > gb[0], gb                                          # 真爬坡


# ── random_immigrants：每代注入新血抗塌缩 ────────────────────────────────────────
def test_random_immigrants_population_conserved():
    """注入随机移民后每代仍恰 population 个体（精英+移民被截顶、while 补满）。"""
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=12, generations=8, elite=2,
                 random_immigrants=4, seed=5)
    assert all(len(gen) == 12 for gen in res.gen_history)
    for gen in res.gen_history:
        for _f, g in gen:
            assert _is_valid_subset(g, POOL)


def test_random_immigrants_monotonic_elitism_holds():
    """移民引入下行扰动，但精英仍保最优 → 每代最优单调不降（抗早熟不破坏爬坡铁律）。"""
    ev = _ordered_target_eval(list(POOL))
    res = run_ga(POOL, ev, population=20, generations=25, elite=2,
                 random_immigrants=5, seed=20260613)
    gb = res.gen_best_fitness
    assert all(gb[i + 1] >= gb[i] for i in range(len(gb) - 1)), gb


def test_random_immigrants_adds_diversity():
    """移民>0 比移民=0 评估更多唯一基因（新血确实进了种群·非空操作）。"""
    ev = _ordered_target_eval(list(POOL))
    base = run_ga(POOL, ev, population=20, generations=20, seed=20260613)
    immi = run_ga(POOL, ev, population=20, generations=20,
                  random_immigrants=6, seed=20260613)
    assert immi.n_unique_evals > base.n_unique_evals


def test_levers_reproducible():
    """三旋钮全开下同 seed 仍可复现（随机源被 seed 钉死）。"""
    ev = _ordered_target_eval(list(POOL))
    kw = dict(population=18, generations=15, crossover_rate=0.6,
              max_len=5, mutations_per_child=2, random_immigrants=4, seed=4242)
    a = run_ga(POOL, ev, **kw)
    b = run_ga(POOL, ev, **kw)
    assert a.gen_best_fitness == b.gen_best_fitness
    assert a.best_individual == b.best_individual
    assert a.n_unique_evals == b.n_unique_evals


# ════════════════════════════════════════════════════════════════════════════════
# §S26 头部精英末腿钩子 elite_eval_fn/elite_k（塔无关·合成 eval 验机器；真红钥末腿契约见 @slow 测）
# 机器铁律：默认关=字节零回归；开启只对 top-elite_k 跑第二评估·跨代缓存·有效分流入 history/选择/log
# ════════════════════════════════════════════════════════════════════════════════

def test_elite_hook_default_off_byte_identical():
    """elite_eval_fn=None/elite_k=0 与完全不传 → 逐字节零回归（默认关）。"""
    ev = _ordered_target_eval(list(POOL))
    a = run_ga(POOL, ev, population=16, generations=15, crossover_rate=0.5, seed=2024)
    b = run_ga(POOL, ev, population=16, generations=15, crossover_rate=0.5, seed=2024,
               elite_eval_fn=None, elite_k=0)
    assert a.gen_best_fitness == b.gen_best_fitness
    assert a.best_individual == b.best_individual
    assert a.n_unique_evals == b.n_unique_evals
    assert [g for _, g in a.gen_history[-1]] == [g for _, g in b.gen_history[-1]]


def test_elite_hook_partial_config_is_off():
    """只给 elite_eval_fn 不给 elite_k（或反之）→ 仍关（两者都需 → 防误触发跑贵末腿）。"""
    ev = _ordered_target_eval(list(POOL))
    big = lambda g: ev(g) + 100000
    base = run_ga(POOL, ev, population=16, generations=12, seed=2024)
    only_fn = run_ga(POOL, ev, population=16, generations=12, seed=2024, elite_eval_fn=big)
    only_k = run_ga(POOL, ev, population=16, generations=12, seed=2024, elite_k=3)
    for r in (only_fn, only_k):
        assert r.gen_best_fitness == base.gen_best_fitness
        assert r.best_individual == base.best_individual
        assert r.n_unique_evals == base.n_unique_evals


def test_elite_hook_miss_is_noop_on_trajectory():
    """elite_eval_fn 原样返回 base（miss·原子空操作类比）→ 选择轨迹与关闭时逐字节同。
    坐实：末腿 miss 不改种群演化，只有 reach（带 B）才扰动。"""
    ev = _ordered_target_eval(list(POOL))
    base = run_ga(POOL, ev, population=20, generations=12, elite=2, seed=20260613)
    miss = run_ga(POOL, ev, population=20, generations=12, elite=2, seed=20260613,
                  elite_eval_fn=lambda g: ev(g), elite_k=3)
    assert miss.gen_best_fitness == base.gen_best_fitness
    assert miss.best_individual == base.best_individual
    assert miss.n_unique_evals == base.n_unique_evals
    assert [g for _, g in miss.gen_history[-1]] == [g for _, g in base.gen_history[-1]]


def test_elite_hook_bonus_promotes_and_flows():
    """头部「reach」基因（合成命门=头位命中 target[0]·正是高 base 那批）带 +B → 霸占最优、有效分入 history。
    base fit_cache 不计末腿评估（n_unique_evals 仍只数 base）。"""
    target = list(POOL)
    ev = _ordered_target_eval(target)
    B = 100000
    def elite_ev(g):                                 # reach = 头位命中 target[0]（高 base 基因特征）
        return ev(g) + B if (g and g[0] == target[0]) else ev(g)
    res = run_ga(POOL, ev, population=20, generations=20, elite=2,
                 elite_eval_fn=elite_ev, elite_k=3, seed=20260613)
    assert res.gen_best_fitness[-1] >= B             # 末代最优带 B → 确反映末腿奖励
    assert res.best_individual[0] == target[0]       # 最优个体确是「reach」那类
    assert _is_valid_subset(res.best_individual, POOL)
    gb = res.gen_best_fitness
    assert all(gb[i + 1] >= gb[i] for i in range(len(gb) - 1)), gb  # 精英保留 → 单调不降


def test_elite_hook_evaluates_only_top_k():
    """末腿评估次数被 top-elite_k 框住 + 跨代缓存去重 → 远少于 pop·gens（贵末腿不全员烧）。"""
    target = list(POOL)
    ev = _ordered_target_eval(target)
    calls = {"n": 0}
    def elite_ev(g):
        calls["n"] += 1
        return ev(g)
    pop, gens, k = 20, 10, 3
    run_ga(POOL, ev, population=pop, generations=gens, elite=2,
           elite_eval_fn=elite_ev, elite_k=k, seed=20260613)
    assert calls["n"] <= k * gens                    # 每代至多 k 条冷算
    assert calls["n"] < pop * gens                   # 远少于全员评估
