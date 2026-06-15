"""【GA decoder · 最小闭环】decode —— ga_design.md 钉死点 2.1 契约的落地。

本棒【只做闭环】：基因目标序列 → 依次 navigate_to 串成完整路线 → 返回 (动作串, 终态)。
绝不写种群随机化/选择/交叉/变异/迭代——那是验证完「基因→腿→指南针→分数」数据链转得对【之后】才
加的进化动力（与 navigate_to 先证对才进 GA、fitness 先证对才标定的同一分步纪律）。

契约（ga_design 钉死点 2.1 / 2.2 / 2.3）：
    decode(chromosome, start_state, zone, step_fn) -> (action_tokens, final_state)
  · 对基因每个目标 goal，从当前态【定向导航】navigate_to(state, goal) → 够到则推进态、串入动作；
  · 够不到（navigate_to reached=False·原子失败返回入口态本体、零副作用）→ 跳过该目标、继续下一个
    （钉死点 2.3：基因是"愿望清单"，做不到就略过 → 任何基因永远可解码成合法路线、不整条作废）；
  · 中途死亡 / 通关（step 的 dead/won 冻结）→ 立即停。
  保证：全程经真 step 推进 → action_tokens 必然【引擎可重放的合法路线】（撞墙/无钥/打不过的动作
  要么不生成、要么 no-op），可直接丢回真引擎 / .h5route 让玩家网站回放。

红线（与 fitness 隔离，ga_design 钉死点 3 的对偶形态）：decode【绝不读 fitness/终评】。它只把英雄
  合法推向基因目标序列；这条路线好坏（潜力/HP/家底）由 fitness 在 decode【之外】对终态评一次——
  fitness 不反馈给 decode 的任何中途推进（守 κ=1）。导航复用现成腿 navigate_to，不重写导航。

基因表示（本棒 = 钉死点 1 的 pickup 子集）：chromosome = [goal_cell, ...]，goal_cell=(fid,x,y) 由
  detect_big_items 数据涌现（大件=big_cells / 小宝石=ranked 非 big 项）、不手写裸坐标 → 塔无关。
  商人 trade（买/不买决策位）是钉死点 1 的一等目标，但本棒【留空接口】不含——见 decode 内注释。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # solver / sim
sys.path.insert(0, str(Path(__file__).resolve().parent))           # ga_navigate / vzone（同目录）

from ga_navigate import navigate_to

_DEFAULT_CACHE = object()   # sentinel：decode 不传 cache → 透传给 navigate_to 用其模块级默认共享缓存


def goal_to_cell(goal):
    """【块为目标·decode 改的唯一一处】把基因元素归一成 navigate_to 吃的 cell=(fid,x,y)：
      · 块 id (fid,(mx,my))（2 元·第二元是 (mx,my) 元组）→ 代表 cell (fid,mx,my)（=块内 min·初始态几何
        锚）。进块即 _absorb 吸光整块（ga_navigate.py:209），代表 cell 是道具格或空地都成立。
      · cell (fid,x,y)（3 元）→ 原样返回（兼容封板单物品目标，test_ga_decode 仍走此路）。
    判别按长度：块 id 2 元、cell 3 元——两者不混淆（封板件 navigate_to 一字不动）。"""
    if len(goal) == 2:
        fid, (mx, my) = goal
        return (fid, mx, my)
    return goal


def forbidden_after(targets, idx, block_cells, taken=None):
    """§S15 禁区集：导航 targets[idx] 这一腿时【不得踏入】的 cell 集——排在它【之后】、且【尚未进包】的
    块的初始 block_cells 并集。治【跨块顺路吸】（去盾顺路把还没轮到的剑块吸进包＝剑早进＝谎报）。
    纯结构函数（无副作用、不读 fitness）：targets=基因目标序、idx=当前腿下标、block_cells={块 id: frozenset
      ((fid,x,y),...)}、taken=已进包目标集合（None＝都没进包）。
    · block_cells 为空/None（cell 模式）→ 返回空集 → navigate_to 字节回到封板（零回归）。
    · 排除自身（不禁当前目标）+ 排除已进包后续块（taken 命中——禁其已空 cell 只会无谓挡路）。
      注：禁区一旦从首腿生效，后续块在轮到自己前【绝不会被提前吸】（每条更早的腿都禁着它）→ taken 过滤
      实际只挡「起点态就已被收掉的块」这一边角，但保留它＝严格按"未进包"口径、不做隐含假设。
    · 后续目标若非块 id（混合/cell 模式）→ 不在 block_cells、自然跳过。"""
    if not block_cells:
        return frozenset()
    cur = targets[idx]
    taken = taken or frozenset()
    later = [g for g in targets[idx + 1:]
             if g != cur and g not in taken and g in block_cells]
    if not later:
        return frozenset()
    return frozenset().union(*(block_cells[g] for g in later))


def decode(chromosome, start_state, zone, step_fn, *, cache=_DEFAULT_CACHE, max_pops=8000):
    """见模块头契约。返回 (action_tokens: list, final_state)。
    cache：navigate_to 缓存外壳的 cache 形参（GA 内循环反复导航同几个目标 → 命中省算）。
      不传 → navigate_to 用其模块级默认 _NAV_CACHE；传 dict → 专用缓存；传 None → 禁用（对照/调试）。
    max_pops：透传给 navigate_to 的前沿弹出护栏。"""
    kw = {} if cache is _DEFAULT_CACHE else {"cache": cache}
    state = start_state
    tokens = []
    for goal in chromosome:
        if state.dead or state.won:
            break
        # 商人 trade 目标【留空接口】（钉死点 1）：将来 goal 形如带 type==trade + buy 位的对象时，此处
        # 先 navigate_to 到商人格、再按 buy 发 step(CHOICE:0=买 / CHOICE:1=不买，_resolve_choices 同口径)。
        # 本棒 goal 全是 pickup 的 (fid,x,y) cell → 直接定向导航、无决策位。
        # 块为目标：goal 可能是块 id (fid,(mx,my)) → goal_to_cell 归一成代表 cell 再导航（封板件不动）。
        final, moves, reached = navigate_to(
            state, goal_to_cell(goal), zone, step_fn, max_pops=max_pops, **kw)
        if reached:
            state = final
            tokens.extend(moves)
        # reached=False → 原子失败、state 不变（navigate_to 返回入口态本体）→ 跳过、继续下一目标
    return tokens, state
