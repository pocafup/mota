"""MVP C 段实验：MT33 段（极限压测·损血精度试金石），入口 = 执行 tokens[:2894] 后(MT33(10,1) HP956)，
出口格 = MT33(10,1)（闭环段：route 绕一圈放血 956→6 换 +40 ATK 后回原格下楼去 MT32）。

主题：极限损血精度 + HP↔永久 ATK 阶梯取舍。段内 5 场硬仗连续放血 950(210+260+260+110+110)，
route 出口 HP=6(全程最低)，是引擎损血精度的试金石——搜索内 step 推进的放血必须与引擎独立重放
逐点吻合(差 1 点 HP=6 即错，甚至致死)。

闭环段(入口格==出口格==(10,1))非退化：route 用 950 HP 换 +40 永久 ATK(114→154)，故「原地不动
HP956/ATK114」与「走完 HP6/ATK154」互不支配——出口 Pareto 前沿会铺出完整 HP↔ATK 取舍曲线；HP
最大点(原地不动 956)是预期的「不投资」退化点，再证 HP 最大≠全局最优(同 A/B 段教训的极限版)。

塔特有配置(MT33 / 2894 / 出口格 / HP 基准 / route 真值)只在本脚本；通用闭环逻辑在
seg_experiment.run_segment，solver/ 全程塔无关。真值取自 route 全程重放(入口 tokens[:2894]、
出口 idx=2972，离开 MT33 前最后停 (10,1))。
"""
from seg_experiment import run_segment

C_CFG = dict(
    name="MVP C 段（MT33 段·极限压测/损血精度）",
    entry_token=2894,
    goal_cell=("MT33", 10, 1),
    baseline_hp=6,
    # route 真值取自 route 全程重放在 MT33(10,1) 离开前(idx2972)。
    # 出口持有道具全为常驻类(fly/I333/book/wand/cross，cls=constants)→比较时按 cls 投影掉(两边恒等)；
    # route 不持任何消耗品(cls=tools)道具，items 留空。
    # 出口 MT33 地图剩余 {yellowKey:1}——非 HP 消耗品(yellowKey 不给 HP)，_route_vec 经
    # _gives_hp_on_pickup 滤掉、不进比较(钥匙只计持有、不计地图剩余，见 docs/solver-design.md)；
    # 故 map 维实际为空，此处列出仅作记录。
    route_exit={
        "hp": 6, "atk": 154, "def": 70, "mdef": 0, "gold": 656, "kill": 181,
        "keys": {"yellowKey": 2},
        "items": {},
        "map": {"yellowKey": 1},
    },
)

if __name__ == "__main__":
    run_segment(C_CFG)
