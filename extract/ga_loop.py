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

from ga_decode import decode, goal_to_cell, forbidden_after   # noqa: E402（goal_to_cell：块 id→代表 cell；forbidden_after：§S15 禁区集）
from ga_navigate import navigate_to                # noqa: E402（规整层复刻 decode 的目标串需直接调）
from solver.fitness import fitness, INVALID_BASE, _depth_of   # noqa: E402（§S15 无效态地板 + 推进度梯度）


def _dedup(seq):
    """保序去重（块折叠后多 cell 落同块 → 块 id 列表去重·保执行序）。"""
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


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
    n_invalid: int = 0              # 该代序列无效个体数（§S15 INVALID_BASE 带）·爬坡健康度：初代高→末代降=进度分把 GA 往有效序拽（'先短后拼长'）


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
            n_inv = sum(1 for f, _ in scored if f < INVALID_BASE + 1e6)   # §S15 无效带个体（爬坡健康度·诊断用·只在 log 路径算）
            log(GenLog(g, list(gbest_ind), gbest_fit, len(fit_cache),
                       scored[-1][0], scored[0][0], n_inv))
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


# ─── _decode_with_order：复刻封板 decode 的目标串 + 进包追踪（产 normalized_order·诊断用）──────────
# navigate_to 走向某目标会【顺路吸】路径上的别的目标（剑/顺路宝石）。_decode_with_order 复刻封板 decode
#   的逐目标 navigate_to 串、逐腿追踪真实进包、产 normalized_order（基因目标真正进包的全局先后序）。
# ★序列有效性两半已根治：块为目标灭块内假序（§S20）、禁区把跨块顺路吸判无效（§S21）→【解码后规整去重已退役】
#   （§S21：原规整去重折叠的等价基因不再产生；去重交回 run_ga 基因元组缓存）。normalized_order 仍照产、
#   现仅供 dump 脚本显示「真实进包序」（玩家用游戏眼睛判 GA 解：剑第几进包 / 盾排哪 / 顺不顺）。
# 进包追踪的 taken 仍被禁区 forbidden_after 共用（知道哪些后续块已进包）→ 保留、非规整专属。
# 红线：封板件（decode/navigate_to/fitness/detect_*）一字不改；不剔目标、不写死顺序；beam 零影响（beam 不 import）。

def _taken(state, cell):
    """目标格是否已空（道具被拿走＝已进包）。复刻 analysis/ga_sword_order_fitness_check.py 的同名判定：
    entities[y][x]==0 ＝ 该格无实体 ＝ 道具已被吸。"""
    fid, x, y = cell
    fl = state.floors.get(fid)
    return fl is not None and fl.entities[y][x] == 0


def _goal_markers(goal, block_markers):
    """目标的"进包判据 cell 集"：
      · 块模式（block_markers 给且含 goal）→ 该块折进的全部 pool 物品 cell（detect 吐的真道具格·非空地
        代表 cell）。块"进包"＝这些 cell 全部被吸（all _taken）——代表 cell 可能是空地、不能拿它判进包。
      · cell 模式（block_markers=None 或 goal 不在表）→ (goal,)：目标自身一个 cell（封板单物品口径）。"""
    if block_markers is not None and goal in block_markers:
        return block_markers[goal]
    return (goal,)


def _decode_with_order(chromosome, start_state, zone, step_fn, cache, *, max_pops=8000,
                       block_markers=None, block_cells=None):
    """复刻封板 decode 的逐目标 navigate_to 串（decode 一字不改），额外产 normalized_order ＝ 基因目标
    【真正进包的全局先后序】。终态【必与 decode(...) 逐字段一致】（复刻封板 decode·禁区关时字节回封板）。
      进包判定（复刻验证脚本的腿级 _taken）：一腿 navigate_to 前后，某目标的【判据 cell 全部】由「有」变
        「空」＝这一腿进包。cell 模式判据 = 目标自身；块模式判据 = 该块折进的全部 pool 物品 cell（_goal_markers）。
      腿内序：顺路吸的（非本腿 goal）排前、本腿 goal 排后——顺路道具物理上必在走到 goal【之前】被踩，
        进包时序「顺路 < goal」是硬事实（非脆弱 tiebreak）；多个顺路按 cell/块 id 排序（确定性、保去重稳定）。
    block_markers（块为目标）：{块 id: frozenset(pool 物品 cell)}。给则按块判进包、normalized 为块 id 序；
      不给（None）→ cell 模式、与封板单物品口径【字节一致】（targets/normalized 皆为 cell）。
    block_cells（§S15 禁区·块为目标）：{块 id: frozenset((fid,x,y),...)}。给则每腿禁「排其后未进包块」的全
      cell（forbidden_after）→ navigate_to 绕禁区走（治跨块顺路吸）；带禁区够不到时【不带禁区重跑一次】区分：
      情况1 不带也够不到（无钥/真不可达）→ 同封板跳过、不淘汰；情况2 不带能到（唯一通路须踏入后续块）→ 此
      排序物理不可实现 → 标 invalid、整条作废（§S15 绝不换序）。None → 禁区关、navigate_to 字节回封板。
    返回 (tokens, final_state, normalized_order: tuple[目标], verdict)；verdict={"invalid":bool,
      "navigated":已导航腿数, "depth":最深层下标}——invalid 时供 eval 层算 INVALID_BASE+进度分
      （κ=1：verdict 是 decode 的结构产物、不调 fitness、不反馈任何中途推进）。"""
    targets = list(chromosome)                      # 基因目标（钉死点 1：本就无重复有序）；cell 或块 id
    markers = {g: _goal_markers(g, block_markers) for g in targets}

    def _is_taken(g, st):
        return all(_taken(st, c) for c in markers[g])   # 块模式=整块物品全吸；cell 模式=该 cell 已空

    state = start_state
    tokens = []
    taken = {g: _is_taken(g, state) for g in targets}   # 已进包的目标（起点一般全 False）
    normalized = []
    navigated = 0                                       # 成功导航到的腿数（进度分·区分无效序列优劣）
    invalid = False
    for i, goal in enumerate(chromosome):
        if state.dead or state.won:                 # 与 decode 同：死亡/通关冻结即停
            break
        forbidden = forbidden_after(                # §S15：排本目标之后、未进包块的全 cell（块模式才非空）
            targets, i, block_cells, taken=frozenset(g for g in targets if taken[g]))
        final, moves, reached = navigate_to(        # 块 id→代表 cell 归一（封板件 navigate_to 不动）
            state, goal_to_cell(goal), zone, step_fn, max_pops=max_pops, cache=cache,
            forbidden=forbidden)
        if not reached and forbidden:               # §S15 判无效：带禁区够不到 → 不带禁区重跑一次区分情况
            _f2, _m2, reached_free = navigate_to(   # 缓存键含 forbidden → 空禁区那次是独立条目（命中近免费）
                state, goal_to_cell(goal), zone, step_fn, max_pops=max_pops, cache=cache)
            if reached_free:                        # 情况2：唯一通路须踏入后续块 → 排序不可实现 → 整条无效
                invalid = True
                break
            # 情况1：不带禁区也够不到（无钥/打不过/真不可达）→ 与封板 decode 同·跳过本目标、继续下一个
        if reached:                                 # 与 decode 同：够不到则原子失败、state 不变、跳过
            state = final
            tokens.extend(moves)
            navigated += 1
        newly = [g for g in targets if not taken[g] and _is_taken(g, state)]   # 这一腿新进包（含顺路吸）
        for g in newly:
            taken[g] = True
        side = sorted(g for g in newly if g != goal)   # 顺路吸（非本腿目标）→ 排在 goal 之前·确定性定序
        normalized.extend(side)
        if goal in newly:                              # 本腿目标这一步真拿到 → 排在顺路之后
            normalized.append(goal)
    verdict = {"invalid": invalid, "navigated": navigated, "depth": _depth_of(state)}
    return tokens, state, tuple(normalized), verdict


# ─── eval 注入：把封板四零件包成 eval_fn（基因→decode→终态→fitness）────────────────────────

def _invalid_score(verdict):
    """§S15 序列无效态评分：恒 ≪ 死亡带的 INVALID_BASE + 进度分（已导航腿数·最深层）。进度分量级 ≤
    1000×7+10×50≈7050，远小于无效带与死亡带间距 1e9 → 无效序列彼此有梯度（导航越多/越深越高·GA 朝可实现
    排序爬），整段恒压在死亡态之下。绝不调 fitness()（κ=1：fitness 只评可实现终态）。"""
    return INVALID_BASE + 1000.0 * verdict["navigated"] + 10.0 * verdict["depth"]


def make_decode_fitness_eval(start, zone, step_fn, roster, big, zone_fids, *,
                             w_potion=1.5, w_key=39.0, decode_cache=None,
                             block_markers=None, block_cells=None):
    """构造 eval_fn(gene)->fitness：复刻 decode（_decode_with_order 串 navigate_to）跑全程 → fitness 终评。
    decode_cache：navigate_to 缓存（GA 内反复导航同几个目标[尤其 26s 盾] → 命中近免费）。
      不传则本函数自建一个、整个 GA 共享 → 同(中途态,目标)只冷算一次。返回 (eval_fn, decode_cache)。
    block_cells（§S15 禁区）：给则 _decode_with_order 每腿带禁区导航；某腿判无效 → eval 直接返 _invalid_score
      （INVALID_BASE+进度分），不调 fitness（run_ga 基因元组缓存已对同基因去重）。None → 禁区关。
    去重：靠 run_ga 的基因元组缓存（fit_cache）→ 同基因不重复评估。解码后规整去重已退役（§S21：块为目标灭
      块内假序、禁区把跨块顺路吸判无效 → 不再产生需折叠的等价基因）；_decode_with_order 仍产 normalized_order、
      仅供 dump 诊断显示真实进包序。"""
    if decode_cache is None:
        decode_cache = {}

    def eval_fn(gene):
        _tokens, final, _normalized, verdict = _decode_with_order(
            gene, start, zone, step_fn, decode_cache,
            block_markers=block_markers, block_cells=block_cells)
        if verdict["invalid"]:                       # §S15 序列结构无效 → 整条作废、给可区分差分（不评 fitness）
            return _invalid_score(verdict)
        return fitness(final, roster, big, zone_fids, w_potion=w_potion, w_key=w_key)

    return eval_fn, decode_cache


# ─── 最小目标池 + 电池组（__main__ / 集成测试用；重 import 全在函数内 → import ga_loop 保持轻量）─────

MIN_GEMS = [("MT1", 7, 3), ("MT1", 7, 4), ("MT4", 7, 10)]   # 攻/防/攻·均 nav≈0s 顺路·决策价值挑(MT1 off-core 绕路对 + MT4 核心层交错)
EXCLUDE_DEEP_KEY = ("MT4", 9, 2)   # 实测 navigate_to 18.2s 冷算·本最小棒排除以降总耗时（非"它不是目标"，下棒可放回）


def build_min_pool(big_cells, ranked, cands, block_index):
    """从【封板涌现器输出】裁出最小目标池（玩家 2026-06-13 拍板·10 物品 cell），每个 cell assert 回溯到
    detect_big_items / detect_key_targets 真涌现 cell —— 绝不手写裸坐标（塔无关红线 + 不擅自造目标）：
      · 剑/盾   : detect_big_items.big_cells 里 da>0 / dd>0 的大件（689 轴心·盾深 26s）。
      · MT4 钥  : detect_key_targets ② 候选里的 MT4 六钥【排除深 (9,2)】= 5 把（从 cands 直接筛 → 必是子集）。
      · 小宝石  : ranked 里 MIN_GEMS 三个顺路攻防宝石（assert ∈ ranked 且 ∉ big_cells → 真小宝石）。
    ★块为目标（§S18 步②）：detect 吐的 cell 口径【一字不改】（守 beam 零影响——detect 函数体不动），算出 10
      个 cell 后经 block_index 折成所属【初始块 id】、保序去重 → pool = 块 id 列表（同块 cell 合并·五钥归并）。
    返回 (pool, meta, block_markers)：
      · pool         : 块 id 有序去重列表（GA 基因元素）；
      · meta         : 角色→块 id（sword/shield/keys/gems）+ cells（原 cell 来源）+ block_roles/rep/cells（dump 用）；
      · block_markers: {块 id: frozenset(该块折进的 pool 物品 cell)} —— 规整进包判据（块"进包"＝整块物品全吸）。"""
    ranked_cells = {c for (_drp, c, _da, _dd) in ranked}
    sword_c = next((c for (_drp, c, da, _dd) in ranked if c in big_cells and da > 0), None)
    shield_c = next((c for (_drp, c, _da, dd) in ranked if c in big_cells and dd > 0), None)
    assert sword_c is not None and shield_c is not None, f"big_cells 缺剑/盾: {sorted(big_cells)}"

    mt4_keys = sorted(c for c in cands if c[0] == "MT4")
    assert len(mt4_keys) == 6, f"detect_key_targets 的 MT4 候选钥应为 6（§S9），实得 {len(mt4_keys)}: {mt4_keys}"
    assert EXCLUDE_DEEP_KEY in mt4_keys, f"待排除深钥 {EXCLUDE_DEEP_KEY} 不在候选 → 坐标失效，请重核"
    keys_c = [c for c in mt4_keys if c != EXCLUDE_DEEP_KEY]
    assert len(keys_c) == 5

    for g in MIN_GEMS:
        assert g in ranked_cells, f"宝石 {g} 不在 detect_big_items 涌现池 → 坐标失效"
        assert g not in big_cells, f"宝石 {g} 落进 big_cells（应是小宝石非大件）"
    gems_c = list(MIN_GEMS)

    cell_pool = [sword_c, shield_c] + keys_c + gems_c
    assert len(cell_pool) == len(set(cell_pool)) == 10, f"cell 池应为 10 个不重 cell，实得 {cell_pool}"

    # ── 折叠：每 detect cell → 所属初始块 id（detect 不变·块层只叠在其输出之上）──
    c2b = block_index["cell_to_block"]
    missing = [c for c in cell_pool if c not in c2b]
    assert not missing, (f"目标 cell {missing} 不在任何初始块（非自由格？被守怪/门/墙挡）——"
                         f"须人工核对，绝不静默丢（CLAUDE.md 不猜）")

    def bid(c):
        return c2b[c]

    sword, shield = bid(sword_c), bid(shield_c)
    keys = _dedup([bid(c) for c in keys_c])     # 五钥可能归并同块 → 去重
    gems = _dedup([bid(c) for c in gems_c])
    pool = _dedup([sword, shield] + keys + gems)
    assert pool and len(pool) == len(set(pool)), f"块 id 池应非空无重复，实得 {pool}"

    # block_markers（规整进包判据）+ 来源标注（dump 用）：每块折进了哪些 pool 物品 cell
    block_markers, block_roles = {}, {}
    for c, role in ([(sword_c, "剑"), (shield_c, "盾")]
                    + [(c, "钥") for c in keys_c] + [(c, "宝石") for c in gems_c]):
        b = bid(c)
        block_markers.setdefault(b, set()).add(c)
        block_roles.setdefault(b, []).append((role, c))
    block_markers = {b: frozenset(cs) for b, cs in block_markers.items()}

    meta = {
        "sword": sword, "shield": shield, "keys": keys, "gems": gems,
        "cells": {"sword": sword_c, "shield": shield_c, "keys": keys_c, "gems": gems_c},
        "block_roles": block_roles,
        "block_rep": {b: block_index["block_rep"][b] for b in pool},
        "block_cells": {b: block_index["block_cells"][b] for b in pool},
    }
    return pool, meta, block_markers


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
    from block_targets import build_block_index
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
    # 块涌现层：覆盖 zone 层 ∪ 所有 detect cell 所在层 → 静态算初始块集（detect 不变·块层叠其上·beam 零影响）
    index_fids = (set(zone_fids) | {c[0] for c in big_cells}
                  | {c[0] for c in cands} | {t[1][0] for t in ranked})
    block_index = build_block_index(sorted(index_fids))
    pool, meta, block_markers = build_min_pool(big_cells, ranked, cands, block_index)

    decode_cache_in = None
    if persistent:
        from nav_cache import PersistentNavCache
        decode_cache_in = PersistentNavCache()
    eval_fn, decode_cache = make_decode_fitness_eval(
        start, zone, step, roster_fit, big, zone_fids, decode_cache=decode_cache_in,
        block_markers=block_markers, block_cells=meta["block_cells"])   # §S15 禁区开

    return dict(start=start, zone=zone, step=step, pool=pool, meta=meta, ranked=ranked,
                big_cells=big_cells, cands=cands, info_key=info_key,
                roster_fit=roster_fit, big=big, zone_fids=zone_fids,
                block_index=block_index, block_markers=block_markers,
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
    cells = meta["cells"]
    print("\n" + "=" * 74)
    print("① 最终最小目标池（10 物品 cell → 折成初始块 id·detect 涌现 cell 不变）")
    print("=" * 74)
    print(f"  剑(da>0·大件)   cell={cells['sword']} → 块 {meta['sword']}")
    print(f"  盾(dd>0·深26s)  cell={cells['shield']} → 块 {meta['shield']}")
    print(f"  MT4 钥 ×5(排除深 {EXCLUDE_DEEP_KEY}) cells={cells['keys']}")
    print(f"      → 块(去重 {len(meta['keys'])}) {meta['keys']}")
    print(f"  小宝石 ×3       cells={cells['gems']} → 块 {meta['gems']}")
    print(f"  cell 池(10) 折成 pool({len(pool)} 块) = {pool}")

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
    tokens, final, _norm, verdict = _decode_with_order(   # §S15 禁区下导出·与 eval 同口径（非封板 decode）
        best, H["start"], H["zone"], H["step"], H["decode_cache"],
        block_markers=H["block_markers"], block_cells=meta["block_cells"])
    fh = final.hero
    if verdict["invalid"]:
        print("  ⚠ 最优个体被判序列无效（§S15）——全种群均无可实现排序，宜扩 pop/gen 或复核目标池")
    print(f"\n  解码终态: {final.current_floor}({fh.x},{fh.y}) HP={fh.hp} ATK={fh.atk} "
          f"DEF={fh.def_} keys={dict(fh.keys)}  tokens={len(tokens)}")
    print(f"  最优 fitness = {res.best_fitness:.1f}   (对照 fitness(689)={f689:.1f})")

    dc = H["decode_cache"]
    if hasattr(dc, "stats"):
        print(f"\n  navigate_to 持久化缓存: 桶={dc.version_tag}  {dc.stats}")


if __name__ == "__main__":
    main()
