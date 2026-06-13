"""MVP B 段实验：MT17 段，入口 = 执行 tokens[:1462] 后(MT17(5,11))，出口格 = MT17(2,11)。

主题：装备阈值决策——段内有 sword2(+20 ATK，在 (2,2))，route 走法是「先打怪(ATK=44 损血多)
后取剑」；验证「拿装备时机改写后续损血」的阈值决策(攻/防跨过怪攻·连击·坚固阈值致损血突变)。
MT17 还有四象限机关门 + 出口时仍未拾的 redGem/blueGem 各 1。

塔特有配置(MT17 / 1462 / 出口格 / HP 基准 / route 真值)只在本脚本；
通用闭环逻辑在 seg_experiment.run_segment，solver/ 全程塔无关。
真值取自 route 全程重放(见 diag_mvp_b_truth.py)：出口 idx=1499，离开 MT17 前最后停 (2,11)。
"""
from seg_experiment import run_segment

B_CFG = dict(
    name="MVP B 段（MT17 段·装备阈值决策）",
    entry_token=1462,
    goal_cell=("MT17", 2, 11),
    baseline_hp=459,
    # route 真值取自 route 全程重放在 MT17(2,11) 离开前(idx1499)。
    # keys=出口持有钥匙；map=离开 MT17 时地图上仍未拾取的资源(完整记录；_route_vec 只取血瓶维比较)。
    # 注意：出口时 redGem/blueGem 各 1 仍在地上(route 未在本段拿)——宝石是永久增益，不计地图剩余维；
    # 搜索若在段内顺手拿了这两块宝石→出口 ATK/DEF 更高，可能严格支配 route。
    route_exit={
        "hp": 459, "atk": 64, "def": 32, "mdef": 0, "gold": 235, "kill": 89,
        "keys": {"yellowKey": 1},
        # 出口持有道具全为常驻类(fly/book/wand/I333，cls=constants)，比较时按 cls 投影掉
        # (两边恒等、只制造假胜负)；route 不持任何消耗品(cls=tools)道具，故 items 留空。
        "items": {},
        "map": {"redGem": 1, "blueGem": 1, "bluePotion": 1,
                "yellowKey": 2, "redPotion": 2},
    },
)

if __name__ == "__main__":
    run_segment(B_CFG)
