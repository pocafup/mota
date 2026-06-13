"""MVP A 段实验：MT8 段，入口 = 执行 tokens[:680] 后，出口格 = MT8(3,11)。

塔特有配置(MT8 / 680 / 出口格 / HP 基准 / route 真值)只在本脚本；
通用闭环逻辑在 seg_experiment.run_segment，solver/ 全程塔无关。
真值取自 route 全程重放(见 diag_mvp_segments.py)。
"""
from seg_experiment import run_segment

A_CFG = dict(
    name="MVP A 段（MT8 段）",
    entry_token=680,
    goal_cell=("MT8", 3, 11),
    baseline_hp=203,
    # route 真值取自 route 全程重放在 MT8(3,11) 最后一次停留(tok712，离开 MT8 前)。
    # keys=出口持有钥匙；map=离开 MT8 时地图上仍未拾取的资源(战略储备)。
    # route 段内吃 0 血瓶、留 3 redPotion 在地上——这两维是「253 不是严格更优」的关键。
    route_exit={
        "hp": 203, "atk": 26, "def": 24, "gold": 119, "kill": 44,
        "keys": {"yellowKey": 3},
        "map": {"yellowKey": 3, "redKey": 1, "bluePotion": 1,
                "redPotion": 3, "blueKey": 1},
    },
)

if __name__ == "__main__":
    run_segment(A_CFG)
