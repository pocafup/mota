"""塔无关：段间 Pareto 前沿合并（全局残留态指纹 + 持有资源 Pareto）。

阶段一段间传递的不是单点而是【整条前沿】，每点携带「地图残留态」——全塔已加载层的
terrain/entities（活怪 / 地上资源 / 门墙开闭）、已触发 afterBattle、隐藏层揭示、英雄 flags、
访问层集，全随状态对象带走（h5mota 离层不重置：_load_floor_if_needed 复用持久层，killed
怪保持死、开过的门保持开）。

支配判定分两层（C 段「兑现时机」课的落地）：
  · 身份维 residual_fingerprint：影响未来可达性 / 代表残留机会的一切离散地图态。两点指纹不同
    = 处于状态空间不同位置，【不可比】，都保留——把跨段时机决策推迟到全局裁定，不在段内用标量
    好坏强行压缩（活怪 / 地上宝石 / 地上钥匙留着不是单调优点：得拿到、且看 coin×2 时机才兑现）。
  · 价值维 _value_map：hp/atk/def/mdef/gold/kill + 持有钥匙 / 道具，越多越好。仅在【同指纹】组
    内做 Pareto——组内残留地图全等，故 atk/def/kill/地图剩余血瓶多为恒量，真正权衡常是
    hp↔gold↔(持有 vs 回收的钥匙)。

为何不把活怪 / 地上资源塞进价值维：A 段实证「把未拾资源当越多越好」会让「少拿 / 不拿」退化点
全成非支配（前沿炸开、HP 极低点也入选）；C 段实证「段内 Pareto 判不了跨段兑现时机」。故残留
地图归【身份维】（不同则都留、留待全局裁定），只有真·持有资源归【价值维】。见 docs/solver-design.md。

塔无关：本文件无任何楼层编号 / 怪物 / 道具 / 阈值硬编码；指纹与价值都从注入的 state 通用字段读。
"""
from dataclasses import dataclass, field

from solver.search import _ge_all, _value_map

value_vector = _value_map  # 对外别名：段间价值维与段内 Pareto 同口径


def _floor_residual(f):
    """单层残留态 → 可哈希元组：地形 + 实体 + 已触发 afterBattle + 已封事件 + 隐藏层揭示 +
    拦截态。捕捉一切「离开该层后仍持久、且影响重访时可达性 / 残留机会」的地图状态。"""
    return (
        f.floor_id,
        tuple(map(tuple, f.terrain)),
        tuple(map(tuple, f.entities)),
        tuple(sorted(f._done_after_battle)),
        tuple(sorted(f._suppressed_events)),
        f.is_hide,
        f._event_intercepting,
    )


def residual_fingerprint(state):
    """全局残留态身份维（hashable）：英雄位 + 全已加载层残留 + flags + 访问层集 + 全局开关。

    同指纹 = 地图与门控态完全相同、仅持有资源可能不同 → 可在组内做价值 Pareto。
    指纹任一处不同 = 不同状态位置 → 段间都保留（不可比）。"""
    h = state.hero
    floors = tuple(sorted(
        (_floor_residual(f) for f in state.floors.values()),
        key=lambda t: t[0],
    ))
    flags = tuple(sorted(
        (k, v) for k, v in h.flags.items()
        if isinstance(v, (int, float, str, bool))
    ))
    enemy_ovr = tuple(sorted(
        (mid, tuple(sorted((k, tuple(v) if isinstance(v, list) else v)
                           for k, v in ov.items())))
        for mid, ov in state._enemy_overrides.items()
    ))
    pending = (None if not state.pending_floor_change else
               (state.pending_floor_change.get("floor_id"),
                state.pending_floor_change.get("x"),
                state.pending_floor_change.get("y")))
    return (
        state.current_floor, h.x, h.y,
        floors, flags,
        tuple(sorted(state.visited_floors)),
        state.auto_mode, state.dead, state.won,
        enemy_ovr, pending,
    )


@dataclass
class FrontierPoint:
    """段间前沿一点：携带完整残留态 state + 从全局起点的动作序列（供裁判重放 / 最终出路）。
    meta 透传任意附加信息（如来源父点、段内出口向量），不参与支配判定。"""
    state: object
    actions: tuple = ()
    meta: dict = field(default_factory=dict)


def merge_frontier(points):
    """把若干 FrontierPoint 合并为段间非支配前沿：按 residual_fingerprint 分组、组内对
    value_vector 做 Pareto 支配去重（被同指纹的某点各维 >= 则丢，含相等去重）。

    返回 (kept_points, stats)：
      kept_points  list[FrontierPoint]，段间传给下一段的前沿。
      stats        {raw_in, width, fingerprints, dropped, group_sizes}：膨胀曲线指标。
    """
    raw_in = len(points)
    groups: dict = {}
    for p in points:
        groups.setdefault(residual_fingerprint(p.state), []).append(p)

    kept: list = []
    for fp, members in groups.items():
        keep_vecs: list = []   # 该组当前非支配 (vec, point)
        for p in members:
            vec = value_vector(p.state)
            dominated = False
            for kv, _ in keep_vecs:
                if _ge_all(kv, vec):       # 已有点各维 >= vec（含相等）→ vec 无新价值
                    dominated = True
                    break
            if dominated:
                continue
            keep_vecs = [(kv, kp) for kv, kp in keep_vecs if not _ge_all(vec, kv)]
            keep_vecs.append((vec, p))
        kept.extend(kp for _, kp in keep_vecs)

    stats = {
        "raw_in": raw_in,
        "width": len(kept),
        "fingerprints": len(groups),
        "dropped": raw_in - len(kept),
        "group_sizes": sorted((len(m) for m in groups.values()), reverse=True),
    }
    return kept, stats
