"""塔无关：把搜索输出的动作序列丢回 step() 独立重放，逐项核对终态。

这是「引擎只当裁判」的落地——搜索内部的去重 / Pareto / 任何剪枝优化
都【不】参与这次重放：从干净的入口 state 副本出发，只一步步跑 step。
若搜索宣称的终态与独立重放的终态有任何一项不符，说明搜索的优化引入了
bug（指纹碰撞、路径记录与扩展不符等），diff 会把它暴露出来。
"""

# 勇者标量字段（注意防御字段名是 def_）
_HERO_SCALARS = ("x", "y", "hp", "atk", "def_", "mdef", "gold", "kill_count")
_HERO_DICTS = ("keys", "items", "flags")
_STATE_FLAGS = ("current_floor", "dead", "won")


def replay(entry_state, actions, step_fn, copy_fn):
    """从 entry_state 的副本出发，依次 step(actions)，返回重放终态。
    copy_fn 注入（引擎的 _copy_state），避免污染调用方持有的入口 state。"""
    state = copy_fn(entry_state)
    for a in actions:
        state = step_fn(state, a)
    return state


def diff_states(claimed, replayed):
    """逐项比较两个终态，返回不一致项 [(field, claimed_val, replayed_val), ...]。
    返回空列表 = 完全一致（裁判通过）。"""
    diffs = []
    for f in _HERO_SCALARS:
        cv, rv = getattr(claimed.hero, f), getattr(replayed.hero, f)
        if cv != rv:
            diffs.append((f, cv, rv))
    for f in _HERO_DICTS:
        cv, rv = dict(getattr(claimed.hero, f)), dict(getattr(replayed.hero, f))
        if cv != rv:
            diffs.append((f, cv, rv))
    for f in _STATE_FLAGS:
        cv, rv = getattr(claimed, f), getattr(replayed, f)
        if cv != rv:
            diffs.append((f, cv, rv))
    return diffs
