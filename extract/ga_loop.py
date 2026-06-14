"""【GA 主循环·最小可跑版】run_ga —— ga_design.md 钉死点4「进化引擎」的第一棒：只证范式能爬坡。

本棒【只做最小 GA】（玩家 2026-06-13 拍板的分步纪律）：固定小种群 + 变异(swap/insert/delete)
+ 锦标赛选择(k≈3) + 精英保留(top1~2) + 迭代几代。**绝不写交叉(OX/PMX)**（顺序语义易错、留第二棒）、
不调参、不追最优解。验证门 = **爬坡**：末代最优 fitness > 初代最优（证真在进化、选择压力方向对），
**不是**「搜出 ≥0.7 骨架」（终极目标、太难当第一棒门）。同 navigate_to 先证「走得到」再谈「走得快」。

═══ 架构：纯 GA 循环 + eval 注入（与四封板零件干净隔离）═══
run_ga 只认一个 **eval_fn(gene)->fitness**，对基因层做进化——它【不知道】decode/navigate_to/fitness 存在。
真实评估由 make_decode_fitness_eval 把【封板四零件】包成 eval_fn：基因→decode(串 navigate_to)→终态→fitness。
好处：① run_ga 是纯进化机器、可用假 eval_fn 快速单测(选择压力/变异有效性/精英/可复现，不跑 26s 盾)；
② 四零件【一字不改】、只被 eval_fn 调用；③ beam 零影响（本文件全新增、不碰任何现有文件）。

基因 = 目标池里目标 cell=(fid,x,y) 的【变长有序无重复子集】（detect_big_items ∪ detect_key_targets 涌现）。
变异全在【目标层】→ 后代必是 pool 子集 → decode 必能解码（够不到的目标 decode 内部跳过、不产非法路线）。
fitness 缓存按【基因元组】去重（decode 贵 + 基因→终态确定性 → 同基因必同分）。固定随机种子可复现。

红线（ga_design 三红线 + κ=1 对偶）：run_ga 不读 navigate_to/decode 任何中途态、不反馈 fitness 给推进；
fitness 只对 decode 跑完的终态评一次。基因目标层保证可解码。塔无关（pool 由调用方涌现注入、run_ga 不认塔）。
"""
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # solver / sim
sys.path.insert(0, str(Path(__file__).resolve().parent))           # ga_decode / vzone 同目录

from ga_decode import decode                       # noqa: E402
from ga_navigate import navigate_to                # noqa: E402（规整层复刻 decode 的目标串需直接调）
from solver.fitness import fitness                 # noqa: E402


# ─── 进化算子（全在目标层，保证后代仍是 pool 的无重复有序子集 → 必可解码）────────────────────

def _random_individual(pool, rng):
    """随机基因 = pool 的【随机长度随机顺序无重复子集】（长度 1..len(pool)）。
    全长度谱采样 → 初代里既有短基因（缺剑/盾→低分）又有长基因但乱序（先打钥匙怪费血→次优）→ 给爬坡留头寸。"""
    k = rng.randint(1, len(pool))
    return rng.sample(pool, k)


def _mutate(ind, pool, rng):
    """目标层单点变异（三选一·最笨版本、不组合）。返回新基因（不改入参）：
      swap   : 交换两目标顺序（调「先去哪后去哪」——689 式先盾后钥匙就是顺序）；
      insert : 插入一个当前不在基因里的 pool 目标（调「多去拿一个」）；
      delete : 删除一个目标（调「少去拿一个」）。
    可行算子按当前基因长度/是否还有可插目标动态决定 → 永远返回合法子集（不会插重、不会空到无法操作）。"""
    ind = list(ind)
    missing = [g for g in pool if g not in ind]
    ops = []
    if len(ind) >= 2:
        ops += ["swap", "delete"]
    if missing:
        ops.append("insert")
    if not ops:                                     # 极端：基因==整个pool且len<2（pool只1个）→ 无可变，原样
        return ind
    op = rng.choice(ops)
    if op == "swap":
        i, j = rng.sample(range(len(ind)), 2)
        ind[i], ind[j] = ind[j], ind[i]
    elif op == "insert":
        ind.insert(rng.randint(0, len(ind)), rng.choice(missing))
    else:                                           # delete
        del ind[rng.randrange(len(ind))]
    return ind


def _tournament(pop_scored, k, rng):
    """锦标赛选择：随机抽 k 个个体、返回 fitness 最高者的基因副本。pop_scored=[(fit, ind), ...]。
    k 越大选择压力越强；k≈3 是温和压力（保多样性、不过早收敛）。"""
    cands = rng.sample(pop_scored, min(k, len(pop_scored)))
    return list(max(cands, key=lambda fs: fs[0])[1])


def _crossover(p1, p2, pool, rng):
    """OX 顺序交叉的【变长无重复子集】适配变体（标准 OX/PMX 是给等长同元素全排列设计的，
    这里两父代是 pool 的不同子集、元素集可能不同 → 套 PMX 位置映射会语义崩坏：引入重复或退化）。
      ① 从 p1 取一段连续子序列 seg（继承 p1 相对顺序、len≥1）；
      ② 从 p2 按序取出所有不在 seg 里的目标 rest（继承 p2 相对顺序、与 seg 必不重）；
      ③ 后代 = rest[:k] + seg + rest[k:]（seg 回到它在 p1 的相对位置 k=min(i,len(rest))）。
    后代元素 ⊆ pool、无重复、长度自然变化、seg 保 p1 序 / rest 保 p2 序 → 必合法子集、必可解码。
    不改入参（p1 拷贝、p2 只读、返回全新 list）。"""
    p1 = list(p1)
    i = rng.randrange(len(p1))
    j = rng.randint(i + 1, len(p1))
    seg = p1[i:j]
    seg_set = set(seg)
    rest = [g for g in p2 if g not in seg_set]
    k = min(i, len(rest))
    return rest[:k] + seg + rest[k:]


# ─── GA 主循环 ────────────────────────────────────────────────────────────────────

@dataclass
class GAResult:
    gen_best_fitness: list          # 每代最优 fitness（★爬坡曲线·核心产物）
    best_individual: list           # 全程最优基因（精英保留 → 即末代最优）
    best_fitness: float             # 全程最优 fitness
    n_unique_evals: int             # 去重后真正 decode+评分的基因数（缓存效果）
    gen_history: list = field(default_factory=list)   # 每代 [(fit, gene), ...] 排序快照（诊断用）


@dataclass
class GenLog:
    """每代进度快照（run_ga 每代把它传给 log 回调）。run_ga 塔无关、只把 best_individual 原样交出——
    认不认得「盾/剑」是【调用方】的事：诊断侧据此自渲染「含盾」标记，引擎侧绝不内嵌塔知识。"""
    gen: int                        # 代号（0..generations-1）
    best_individual: list           # 该代最优基因（副本）
    best_fitness: float             # 该代最优 fitness
    n_unique_evals: int             # 累计真 decode+评分去重数（缓存命中观察）
    spread_lo: float                # 该代种群最差 fitness（多样性下沿）
    spread_hi: float                # 该代种群最优 fitness（=best_fitness）


def run_ga(pool, eval_fn, *, population=12, generations=6, tournament_k=3,
           elite=2, crossover_rate=0.0, inject=None, seed=20260613, log=None):
    """最小 GA 主循环（见模块头）。pool=目标 cell 列表；eval_fn(gene)->fitness。返回 GAResult。
    fitness 缓存按基因元组去重（同基因不重复评估·decode 贵）。固定 seed 可复现。
    crossover_rate: 0=纯变异(默认·字节级零回归——>0 判定短路、不消耗 rng)；>0 则每个后代以此概率两父 OX 交叉。
    inject: 可选 [基因,...] 注入初始种群（须是 pool 非空无重复子集、数≤population），其余随机填充。
    log: 可选 callable(GenLog)，每代回调一次进度（GenLog 带 gen/best_individual/best_fitness/…）；
         run_ga 塔无关、不认盾/剑 → 「含盾」等标记由调用方在回调里自加。"""
    if not pool:
        raise ValueError("pool 不能为空")
    rng = random.Random(seed)
    fit_cache = {}

    def ev(ind):
        key = tuple(ind)
        if key not in fit_cache:
            fit_cache[key] = eval_fn(ind)
        return fit_cache[key]

    pool_set = set(pool)
    seeded = []
    for ind in (inject or []):
        assert ind and len(ind) == len(set(ind)) and all(g in pool_set for g in ind), \
            f"注入个体须是 pool 的非空无重复子集，违例: {ind}"
        seeded.append(list(ind))
    assert len(seeded) <= population, f"注入个体数 {len(seeded)} > 种群 {population}"
    pop = seeded + [_random_individual(pool, rng) for _ in range(population - len(seeded))]
    gen_best = []
    history = []
    best = (float("-inf"), None)

    for g in range(generations):
        scored = sorted(((ev(ind), ind) for ind in pop), key=lambda fs: -fs[0])
        history.append([(f, list(ind)) for f, ind in scored])
        gbest_fit, gbest_ind = scored[0]
        gen_best.append(gbest_fit)
        if gbest_fit > best[0]:
            best = (gbest_fit, list(gbest_ind))
        if log:
            log(GenLog(g, list(gbest_ind), gbest_fit, len(fit_cache),
                       scored[-1][0], scored[0][0]))
        if g == generations - 1:
            break
        # 下一代：精英原样保留 + 锦标赛选父→(按 crossover_rate 两父交叉)→单点变异
        nxt = [list(scored[i][1]) for i in range(min(elite, len(scored)))]
        while len(nxt) < population:
            if crossover_rate > 0 and rng.random() < crossover_rate:
                child = _crossover(_tournament(scored, tournament_k, rng),
                                   _tournament(scored, tournament_k, rng), pool, rng)
            else:
                child = _tournament(scored, tournament_k, rng)
            nxt.append(_mutate(child, pool, rng))
        pop = nxt

    return GAResult(gen_best, best[1], best[0], len(fit_cache), history)


# ─── 解码后规整（§S12 自欺序列真解·必做层）──────────────────────────────────────────
# 病：navigate_to 走向某目标会【顺路吸】路径上的别的目标（剑/顺路宝石）——GA 以为在搜「剑排第几」，
#   实际剑总被顺路吸、排第几 decode 终态都一样＝自欺序列（§S11）。但「剑早拿」在【无盾解】里有真实价值
#   （Δ+16826，§S12 铁证）＝不能剔剑。真解＝解码后【规整】：把基因目标按【真正进包的全局先后序】排成
#   normalized_order，等价基因（同进包序→同终态）共享 fitness 缓存去重——含盾 [盾,剑]≡[剑,盾] 折叠、
#   无盾 [剑,5钥]≠[5钥,剑] 不折叠。规整【不改 fitness 值】（终态本就同→分本就等）、只省重复评估。
# 红线：封板件（decode/navigate_to/fitness/detect_*）一字不改；规整只在此 eval 层复刻 decode 的目标串、
#   旁加进包追踪；不剔目标、不写死顺序；beam 零影响（本文件 GA 专用、beam 不 import）。

def _taken(state, cell):
    """目标格是否已空（道具被拿走＝已进包）。复刻 analysis/ga_sword_order_fitness_check.py 的同名判定：
    entities[y][x]==0 ＝ 该格无实体 ＝ 道具已被吸。"""
    fid, x, y = cell
    fl = state.floors.get(fid)
    return fl is not None and fl.entities[y][x] == 0


def _decode_with_order(chromosome, start_state, zone, step_fn, cache, *, max_pops=8000):
    """复刻封板 decode 的逐目标 navigate_to 串（decode 一字不改），额外产 normalized_order ＝ 基因目标
    【真正进包的全局先后序】。终态【必与 decode(...) 逐字段一致】（tests/test_ga_normalize_guard 钉死）。
      进包判定（复刻验证脚本的腿级 _taken）：一腿 navigate_to 前后，某基因目标格由「有」变「空」＝这一腿进包。
      腿内序：顺路吸的（非本腿 goal）排前、本腿 goal 排后——顺路道具物理上必在走到 goal【之前】被踩，
        进包时序「顺路 < goal」是硬事实（非脆弱 tiebreak）；多个顺路按 cell 排序（确定性、保去重稳定）。
    返回 (tokens, final_state, normalized_order: tuple[cell])。"""
    targets = list(chromosome)                      # 基因目标（钉死点 1：本就无重复有序）
    state = start_state
    tokens = []
    taken = {t: _taken(state, t) for t in targets}  # 已进包的目标（起点一般全 False）
    normalized = []
    for goal in chromosome:
        if state.dead or state.won:                 # 与 decode 同：死亡/通关冻结即停
            break
        final, moves, reached = navigate_to(
            state, goal, zone, step_fn, max_pops=max_pops, cache=cache)
        if reached:                                 # 与 decode 同：够不到则原子失败、state 不变、跳过
            state = final
            tokens.extend(moves)
        newly = [t for t in targets if not taken[t] and _taken(state, t)]   # 这一腿新进包（含顺路吸）
        for t in newly:
            taken[t] = True
        side = sorted(t for t in newly if t != goal)   # 顺路吸（非本腿目标）→ 排在 goal 之前·确定性定序
        normalized.extend(side)
        if goal in newly:                              # 本腿目标这一步真拿到 → 排在顺路之后
            normalized.append(goal)
    return tokens, state, tuple(normalized)


# ─── eval 注入：把封板四零件包成 eval_fn（基因→decode→终态→fitness）────────────────────────

def make_decode_fitness_eval(start, zone, step_fn, roster, big, zone_fids, *,
                             w_potion=1.5, w_key=39.0, decode_cache=None,
                             normalize=True, stats=None):
    """构造 eval_fn(gene)->fitness：复刻 decode（_decode_with_order 串 navigate_to）跑全程 → fitness 终评。
    decode_cache：navigate_to 缓存（GA 内反复导航同几个目标[尤其 26s 盾] → 命中近免费）。
      不传则本函数自建一个、整个 GA 共享 → 同(中途态,目标)只冷算一次。返回 (eval_fn, decode_cache)。
    规整（§S12 必做层）：以 normalized_order（真正进包先后序）为 fitness 缓存键 → 等价基因（同进包序→
      同终态）只评一次。【不改 fitness 值】：等价基因终态全同→分本就相等，缓存命中返回的就是应得值。
    normalize=False：旁路 norm_cache（规整【关】·对照诊断用）→ 每个不同基因元组都评 fitness（run_ga 的
      基因元组缓存仍去重）；默认 True 与现状逻辑等价。stats：可选 dict，旁路计真实 fitness() 冷算次数
      （stats['fitness_calls']·规整开/关省多少评估的诊断键），默认 None 零开销。两参数仅诊断、不入产品路径。"""
    if decode_cache is None:
        decode_cache = {}
    norm_cache = {}     # normalized_order -> fitness：等价基因评估去重（§S12 必做层）

    def eval_fn(gene):
        _tokens, final, normalized = _decode_with_order(
            gene, start, zone, step_fn, decode_cache)
        if normalize and normalized in norm_cache:  # 等价基因（同进包序）→ 复用、不重算 fitness
            return norm_cache[normalized]
        if stats is not None:                       # 诊断计数：真实 fitness() 冷算次数（默认 None 零开销）
            stats["fitness_calls"] = stats.get("fitness_calls", 0) + 1
        f = fitness(final, roster, big, zone_fids, w_potion=w_potion, w_key=w_key)
        if normalize:
            norm_cache[normalized] = f
        return f

    return eval_fn, decode_cache


# ─── 最小目标池 + 电池组（__main__ / 集成测试用；重 import 全在函数内 → import ga_loop 保持轻量）─────

MIN_GEMS = [("MT1", 7, 3), ("MT1", 7, 4), ("MT4", 7, 10)]   # 攻/防/攻·均 nav≈0s 顺路·决策价值挑(MT1 off-core 绕路对 + MT4 核心层交错)
EXCLUDE_DEEP_KEY = ("MT4", 9, 2)   # 实测 navigate_to 18.2s 冷算·本最小棒排除以降总耗时（非"它不是目标"，下棒可放回）


def build_min_pool(big_cells, ranked, cands):
    """从【封板涌现器输出】裁出最小目标池（玩家 2026-06-13 拍板·10 目标），每个目标 assert 回溯到
    detect_big_items / detect_key_targets 真涌现 cell —— 绝不手写裸坐标（塔无关红线 + 不擅自造目标）：
      · 剑/盾   : detect_big_items.big_cells 里 da>0 / dd>0 的大件（689 轴心·盾深 26s）。
      · MT4 钥  : detect_key_targets ② 候选里的 MT4 六钥【排除深 (9,2)】= 5 把（从 cands 直接筛 → 必是子集）。
      · 小宝石  : ranked 里 MIN_GEMS 三个顺路攻防宝石（assert ∈ ranked 且 ∉ big_cells → 真小宝石）。
    返回 (pool, meta)；meta 标注每目标来源供 dump。"""
    ranked_cells = {c for (_drp, c, _da, _dd) in ranked}
    sword = next((c for (_drp, c, da, _dd) in ranked if c in big_cells and da > 0), None)
    shield = next((c for (_drp, c, _da, dd) in ranked if c in big_cells and dd > 0), None)
    assert sword is not None and shield is not None, f"big_cells 缺剑/盾: {sorted(big_cells)}"

    mt4_keys = sorted(c for c in cands if c[0] == "MT4")
    assert len(mt4_keys) == 6, f"detect_key_targets 的 MT4 候选钥应为 6（§S9），实得 {len(mt4_keys)}: {mt4_keys}"
    assert EXCLUDE_DEEP_KEY in mt4_keys, f"待排除深钥 {EXCLUDE_DEEP_KEY} 不在候选 → 坐标失效，请重核"
    keys = [c for c in mt4_keys if c != EXCLUDE_DEEP_KEY]
    assert len(keys) == 5

    for g in MIN_GEMS:
        assert g in ranked_cells, f"宝石 {g} 不在 detect_big_items 涌现池 → 坐标失效"
        assert g not in big_cells, f"宝石 {g} 落进 big_cells（应是小宝石非大件）"
    gems = list(MIN_GEMS)

    pool = [sword, shield] + keys + gems
    assert len(pool) == len(set(pool)) == 10, f"池应为 10 个不重 cell，实得 {pool}"
    meta = {"sword": sword, "shield": shield, "keys": keys, "gems": gems}
    return pool, meta


def build_harness(*, persistent=False):
    """组装 GA 电池组：decode 起点（build_start MT3 自由态·detectors 同源 ref）+ fitness 标尺
    （复刻 tests/test_fitness 的 roster/big/zone_fids → GA 最优分与 fitness(689) 同尺直接可比）+ 最小目标池。
    重 import / route 回放全在此函数内（import ga_loop 不触发 build_start 重放，保单测轻量）。
    persistent：False（默认）→ navigate_to 用自建内存 dict（与现状字节一致·零回归）；True → 注入
      PersistentNavCache（跨 run 落盘·深目标全局只冷算一次·§S13 拆成本墙）。开/关只改耗时不改结果。"""
    import json

    from probe_crossfloor import build_start
    from vzone import build_zone
    from key_targets import detect_key_targets
    from big_item_pull import detect_big_items
    from solver.beam import build_future_roster
    from solver.fitness import build_zone1_roster, calibrate_big
    from export_mt10_boss_route import make_initial_state
    from decode_route import parse_rle_route, decompress
    from sim.simulator import step

    root = Path(__file__).resolve().parent.parent
    R718 = root / "route" / "deepest_K500_bb25_gd1w_cap480k_lam0.2_stairs.h5route"
    R689 = root / "route" / "deepest_K500_bb25_gd1w_ab0.7_cap480k_lam0.2_stairs.h5route"

    def _replay(route_file):
        outer = json.loads(decompress(route_file.read_text(encoding="utf-8").strip()))
        actions = parse_rle_route(decompress(outer["route"]))
        s = make_initial_state()
        for a in actions:
            s = step(s, a)
            if s.dead:
                break
        return s

    start, _ = build_start()
    zone = build_zone()

    # fitness 标尺：复刻 test_fitness（roster/big/zone_fids）→ GA 分与 fitness(689) 同尺
    s718, s689 = _replay(R718), _replay(R689)
    roster_fit, zone_fids, _all = build_zone1_roster(s718)
    big = calibrate_big([s718, s689, make_initial_state()], roster_fit)
    # zone_fids 结构性（boss 定·与态无关）：交叉核对 detectors 验证路径（build_start ref）同口径
    _rk, zone_fids_k, _ak = build_zone1_roster(start)
    assert zone_fids == zone_fids_k, (zone_fids, zone_fids_k)

    # 目标池涌现（detect_big_items 用 build_future_roster；detect_key_targets 用 zone_fids·ref=start）
    roster_big = build_future_roster(start)
    big_cells, _tau, ranked = detect_big_items(zone, roster_big, start)
    cands, info_key = detect_key_targets(start, zone_fids)
    pool, meta = build_min_pool(big_cells, ranked, cands)

    decode_cache_in = None
    if persistent:
        from nav_cache import PersistentNavCache
        decode_cache_in = PersistentNavCache()
    eval_fn, decode_cache = make_decode_fitness_eval(
        start, zone, step, roster_fit, big, zone_fids, decode_cache=decode_cache_in)

    return dict(start=start, zone=zone, step=step, pool=pool, meta=meta, ranked=ranked,
                big_cells=big_cells, cands=cands, info_key=info_key,
                roster_fit=roster_fit, big=big, zone_fids=zone_fids,
                eval_fn=eval_fn, decode_cache=decode_cache, s689=s689, s718=s718)


def main():
    import time
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    persistent = "--persistent" in sys.argv
    print(f"组装 GA 电池组（build_start 重放开局 + 标尺 route 回放 + 目标池涌现 · persistent={persistent}）…")
    t0 = time.time()
    H = build_harness(persistent=persistent)
    print(f"  电池组就绪 {time.time() - t0:.1f}s")

    pool, meta = H["pool"], H["meta"]
    print("\n" + "=" * 74)
    print("① 最终最小目标池（10 目标·每个回溯 detect_big_items / detect_key_targets 涌现 cell）")
    print("=" * 74)
    print(f"  剑(da>0·大件)              = {meta['sword']}")
    print(f"  盾(dd>0·大件·689 轴心·深26s) = {meta['shield']}")
    print(f"  MT4 候选钥 ×5(排除深 {EXCLUDE_DEEP_KEY}) = {meta['keys']}")
    print(f"  小宝石 ×3(顺路·决策价值)    = {meta['gems']}")
    print(f"  pool({len(pool)}) = {pool}")

    f689 = fitness(H["s689"], H["roster_fit"], H["big"], H["zone_fids"], w_potion=1.5, w_key=39.0)
    f718 = fitness(H["s718"], H["roster_fit"], H["big"], H["zone_fids"], w_potion=1.5, w_key=39.0)
    print(f"\n  标尺(同 fitness 尺): fitness(689)={f689:.1f}  fitness(718)={f718:.1f}")

    print("\n" + "=" * 74)
    print("② GA 爬坡曲线（pop12 × gen6 · 锦标赛 k3 · 精英 2 · 无交叉 · seed=20260613）")
    print("=" * 74)
    t1 = time.time()
    res = run_ga(pool, H["eval_fn"], population=12, generations=6,
                 tournament_k=3, elite=2, seed=20260613,
                 log=lambda gl: print(
                     f"  gen {gl.gen}: best={gl.best_fitness:>12.1f}  len={len(gl.best_individual):2d}  "
                     f"uniq_evals={gl.n_unique_evals:3d}  "
                     f"pop_spread=[{gl.spread_lo:.0f}..{gl.spread_hi:.0f}]"))
    dt = time.time() - t1
    print(f"\n  ▸ 每代最优 gen_best = {[round(x, 1) for x in res.gen_best_fitness]}")
    climb = res.gen_best_fitness[-1] - res.gen_best_fitness[0]
    print(f"  ▸ 末代最优 − 初代最优 = {climb:.1f}  →  {'✅ 在爬坡(>0)' if climb > 0 else '❌ 没爬(≤0)'}")
    print(f"  ▸ 真 decode+评估去重数 = {res.n_unique_evals}（fitness 缓存省算）  GA 净耗时 {dt:.1f}s")

    print("\n" + "=" * 74)
    print("③ 全程最优个体 → 解码路线 → 终态（对照 689 骨架）")
    print("=" * 74)
    best = res.best_individual
    print(f"  最优基因（{len(best)} 目标·按执行序）=")
    for g in best:
        tag = ("剑" if g == meta["sword"] else "盾" if g == meta["shield"]
               else "钥" if g in meta["keys"] else "宝石" if g in meta["gems"] else "?")
        print(f"      {g}  [{tag}]")
    tokens, final = decode(best, H["start"], H["zone"], H["step"], cache=H["decode_cache"])
    fh = final.hero
    print(f"\n  解码终态: {final.current_floor}({fh.x},{fh.y}) HP={fh.hp} ATK={fh.atk} "
          f"DEF={fh.def_} keys={dict(fh.keys)}  tokens={len(tokens)}")
    print(f"  最优 fitness = {res.best_fitness:.1f}   (对照 fitness(689)={f689:.1f})")

    dc = H["decode_cache"]
    if hasattr(dc, "stats"):
        print(f"\n  navigate_to 持久化缓存: 桶={dc.version_tag}  {dc.stats}")


if __name__ == "__main__":
    main()
