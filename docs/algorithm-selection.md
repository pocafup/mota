# 算法选型调研报告（§S30 探针定生死之后·2026-06-16）

> 本文是一次性的**重大算法选型决策**的完整归档（对比表 / 六算法族评估 / 出处 / 推荐 + 玩家拍板）。
> 决策的**运行记录**（含分阶段路线、状态爆炸风险、下个 session 第一步）见 `docs/handoff.md` §S31。
> 触发背景：§S30 定生死探针坐实——旧方案"GA 选块 + 贪心 navigate 外包路径"撞到 **navigate 天花板**（贪心、血够永不绕路、不省钥匙、撞门就开 → 路径决策锁死在寻路器内、上层 GA 控制不了）。要换成"**让搜索把细粒度路径决策本身纳入**"的新算法。

## 本问题 5 决定性特征（驱动选型）
1. **确定性 + 完全可观测 + 单人**：无随机、无隐藏信息、无对手。
2. **稀疏奖励 + 超长视野**：过 boss 才有终局奖励，中间几百步只有资源损耗。
3. **状态可精确模拟 + 可回退**：完整确定性 `step(state, action) → state'`，前向展开/反向枚举都可行。
4. **已有精确 V_boss**：boss 段穷尽搜出的终局价值表 = 从目标反向一段的**真值已知**（部分价值函数）。
5. **有人类示范（1 条）**：14382 通关存档，可行非最优。

## 硬过滤（事实约束·非印象）
本机 **无 GPU、单实例（N=1）**。这两条直接排除三个候选：
- **AlphaZero / MuZero / RL** 全部**强制要训练神经网络 + GPU** → 无 GPU = 物理上做不了。
- 自对弈/RL 的价值在于**跨大量实例摊销训练**（AET 论文实测 break-even ≈ 1.58×10⁵ 实例才回本）；这里只有一座塔一个起点，无可摊销。
- MuZero 卖点是"**没有模拟器也能 planning**"——这里**已有精确模拟器**，学隐式模型纯属重复造轮子 + 引入近似误差。

→ 剩下 **① rollout-free MCTS / ④ 经典启发搜索 A\*族·HTN / ⑥ 反向归纳·retrograde·反向 DP** 三个都**不需要 NN/GPU**，在它们之间选。

## ★候选对比表

| 候选 | 适配度 | 成功先例（查证） | 工程量（NN/GPU） | 能用 V_boss | 能解路径决策 | 裁决 |
|---|---|---|---|---|---|---|
| **①rollout-free MCTS**（价值叶替 rollout） | 中（可用非最优） | SP-MCTS/SameGame (Schadd&Winands 2008/2011)；Sokoban 上 SP-MCTS **不如** best-first (ESA 2021)；PHS/LevinTS 用学习策略引导 best-first (AAAI'21/NeurIPS'18) | 中·**无 NN 无 GPU**（V_boss 当叶值） | 能（叶节点评估，正好治深谷 rollout 病） | 能（树边=动作，细粒度） | **Plan B** |
| **②AlphaZero/AlphaGo**（自对弈） | 低 | 棋类对抗；单人对口先例 DeepCubeA 其实用价值网+weighted-A\*、**非**自对弈 | 高·**须 NN+GPU**·单实例无法摊销 | 勉强 | 能但代价极高 | **出局** |
| **③MuZero**（学模型） | 低（冗余） | Atari/棋类；**无"已有完美模拟器还上 MuZero"的合理先例** | 高·**须 NN+GPU**+学模型 | 勉强 | 能但冗余 | **出局** |
| **④经典启发搜索 A\*族/HTN** | **高**（吃满资产） | Sokoban+PDB (Pereira&Ritt, AIJ 2015)；钥匙门/塞尔达类（启发搜索是主力解法）；ERCA\*（资源约束最短路 RCSPP）；DeepCubeA=价值+weighted-A\* (Nature MI 2019) | 中·**无 NN 无 GPU**（要状态抽象/PDB + 分段 HTN 控爆炸） | **能·最契合**（直接当一致尾启发，A\* 最优高效） | **能**（动作级搜索，绕路/省钥/开门都是搜索决策） | **★主推 A** |
| **⑤RL(DQN/PPO)+课程+示范** | 低 | 单示范 Montezuma (Salimans 2018)=128 GPU×2 周×50B 帧，且核心 trick(reset 到示范态)**本质是 planning** | 高·**须 NN+GPU**+海量交互；1 示范太少 | 勉强（reward shaping） | 能但样本代价极高、无最优保证 | **出局** |
| **⑥反向归纳/retrograde/反向 DP** | **高**（比残局库更有利） | Chinook 西洋跳棋残局库 444B 局面、Awari 完全解、中国象棋残局库、Bellman 1965、DAG 最长路=逆拓扑 DP (MIT 6.006) | 中·**无 NN 无 GPU**（纯查表 DP，瓶颈=状态数×内存） | **能·完美契合**（V_boss=种子/最后一片已解 slice；search_quotient=天然分段 DP 单元） | **能·从根上解**（每步=一条边、绕路/省钥=边权后果、最优由 DP 选出） | **★主推 B** |

## 留下三个的取舍（①④⑥）

**④ 与 ⑥ 是一体两面**——都是"用 V_boss + 确定性 + 可模拟"做**精确搜索**，都不需 NN/GPU，都把路径决策纳入搜索（正中旧方案死穴）：
- **④前向 A\*/IDA\***：从起点按需展开，**内存友好**，产出**单条最优路径**；V_boss 当**尾段启发**，中段启发须自己设计（主要工程量）。
- **⑥反向 DP/retrograde**：产出**每个可达态的精确最优值**（更强、可复用），但要枚举整段可达态、**吃内存**。

**★⑥ 的关键查证（"从谷底反向扩展"的正确形态）**：纯反向枚举前驱**不可行**——属性单调累积，反推前驱要"减血/退攻防/塞回钥匙/复活怪"，前驱集合爆炸且大量是游戏里走不到的**幻影态**。**成立的是混合形态**（文献直接支持）：
1. 按**不可逆事件分段**（过 boss / 永久开门 / 跨层）；
2. **段内正向 BFS 枚举真可达态**（避开幻影）；
3. 段内近无环 → **逆拓扑一遍 DP**（有小环时 fixpoint）；
4. 段间用**后段入口价值**往前接，**V_boss 就是最后一片已解 slice**。

→ 这正是现有 `search_quotient`（穷尽搜出 V_boss 那套）的**自然外扩**：把它当"分段 DP 求解单元"往前再解一两段 = 把 V_boss 往起点方向推。

**①MCTS-价值叶 = Plan B**：文献明确，确定性单人最优路径上 **best-first 搜索 ≥ MCTS**（Sokoban 上 SP-MCTS 实测不如 best-first）。仅在"前向分支爆炸、A\* 启发剪不动"时退守。

## 顾问推荐
**首选：④⑥ 合体的「分段精确搜索」框架，骨架复用现有 `search_quotient`，V_boss 当种子/启发——无 NN、无 GPU。**

理由：①唯一**吃满全部已有资产**（V_boss + 模拟器 + search_quotient + 示范当下界）；②**从根上解路径决策**（动作级搜索，不再外包贪心 navigate）；③**零新基础设施**（不碰 GPU、不训练）；④与"穷尽搜 boss 段得 V_boss"**同源**，是外扩不是另起炉灶；⑤前向(④)/反向(⑥)可**互为验证**。唯一真风险=**单段可达态数（内存）**，对策成熟（属性支配剪枝 / 分片 / 外存，Chinook 同款）。

## ★玩家拍板（2026-06-16）
采纳**纯搜索方案**：**【逆向价值传播（retrograde / 价值迭代）+ 带 V_boss 的 A\* move 级搜索】，先不上神经网络**。神经网络（AlphaZero/DQN）= 杀鸡用牛刀，**留作最后手段（阶段 4）**——仅当抽象后仍状态爆炸 + 精确价值迭代和 MCTS 都失败 + 要泛化到任意塔时才考虑。分阶段路线 / 状态爆炸风险 / 下个 session 第一步见 `docs/handoff.md` §S31。

## 出处（网络查证·非印象）
- Schadd & Winands, *Single-Player Monte-Carlo Tree Search*（SameGame, 2008/2011）
- Sokoban 上 best-first 优于 SP-MCTS 的分析（ESA 2021）
- PHS（Policy-guided Heuristic Search, AAAI 2021）、LevinTS（NeurIPS 2018）
- DeepCubeA, *Solving the Rubik's Cube with Deep RL and Search*（Nature Machine Intelligence 2019）— 价值网 + weighted-A\*，非自对弈
- AET（Amortized 分析）arXiv 2605.14624 — 自对弈摊销 break-even ≈ 1.58×10⁵ 实例
- Pereira & Ritt 等，Sokoban + PDB（Artificial Intelligence 2015）
- Zelda 类游戏 NP-hard（arXiv 2203.17167）；inventory-aware pathfinding；ERCA\*（资源约束最短路 RCSPP）
- Salimans & Chen, *Learning Montezuma's Revenge from a Single Demonstration*（2018）— 128 GPU×2 周×50B 帧；reset-to-demo 本质是 planning
- model-based vs model-free 综述（arXiv 2006.16712）；Sutton, *The Bitter Lesson*
- Endgame tablebase（Wikipedia）；Retrograde Analysis（Chessprogramming wiki）
- Chinook 残局库 444B 局面（U. Alberta）；Building the Checkers 10-Piece Endgame DBs
- External-Memory Retrograde Analysis（Springer）；Solving Large Retrograde Problems on NoW（U. Alberta）
- 中国象棋残局库 by Retrograde Analysis；Bellman 1965（DP 解残局）
- Shortest Paths in DAGs（MIT 6.006）；Backward Approximate DP（Princeton RLSO Ch.15）
