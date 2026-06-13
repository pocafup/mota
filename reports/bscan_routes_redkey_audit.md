# β 扫各路线导出 + 红钥匙核实 + 真实余量重估（只读·引擎封板重放）

> 不重跑搜索；动作串=各 β 的 cut 文件里 `floor==MT10` 按真实 V=HP−D 取顶的那条，从干净起点(开局噩梦后 MT3 入口)引擎封板重放对账。怪/宝石/钥匙归因到 data 真读格。

## 0. 源码核实：boss 房进入机制（红门必经 + D 漏了什么）

- **真地图 BFS（MT10 静态地图，引擎 terrain 数据）**：从 MT9 入口落点 (6, 10) 能否走到队长格 (6, 4)（=进 boss 房）——
  - **不持红钥匙**：可达=**否**（红门 6,9=tile83 当墙；黄/蓝/绿门放行、机关门/铁门当墙）
  - **持红钥匙**：可达=是
  - → **结论：红门(6,9)是进 boss 房的唯一通道，红钥匙必需。**侧袋被 330 硬墙 + 85 机关门封死，绕不过去。
- **埋伏满房**（来源 MT10.json events['6,5'] 生成列表 + autoEvent 8 格门控）：6×骷髅人(id209 hp50/atk42/def6) + 2×骷髅士兵(id210 hp55/atk52/def12) + 队长(id211 hp100/atk65/def15)，共 9 战。
- **D 两条固有局限**（vzone.py 注释明记，非 bug，是 admissible 上界的乐观）：
  - (a) 最短路只对【路径上】障碍记损血。到达态(埋伏触发前)从入口直上竖井到队长，路上**一只埋伏怪都不踩**(它们在侧格/上排)→ D 的 boss 段≈只算队长 1 战，**8 只埋伏怪全漏**。
  - (b) D 把上锁门当【免费过路】→ **红门零代价穿、根本不查有没有红钥匙**。
  - ⇒ 搜索看到的 `HP−D` 同时吃了这两个乐观红利，是**上界幻觉**，不是能不能过 boss 的真账。

## 1. 对照表：各 β best-MT10 路线（红钥匙 + 真实余量重估）

| β | 到MT10态 HP/ATK/DEF | 持红钥匙 | 拿钥第# | 杀MT8卫兵 | 队长可杀 | HP−D(搜索看到) | 满房真损血 | 重估余量(HP−满房) | MT10态有红钥比例 |
|---|--------------------|---------|--------|----------|---------|---------------|-----------|------------------|----------------|
| 0 | 92/25/25 | ❌无 | — | 0/2 | 是 | -289 | 780 | **-688** | 0/377 |
| 0.5 | 553/25/25 | ❌无 | — | 0/2 | 是 | 172 | 780 | **-227** | 0/361 |
| 1 | 606/24/24 | ❌无 | — | 0/2 | 是 | 131 | 891 | **-285** | 0/471 |
| 2 | 394/25/24 | ❌无 | — | 0/2 | 是 | 1 | 809 | **-415** | 0/486 |
| 4 | 68/23/21 | ❌无 | — | 0/2 | 是 | -493 | 1028 | **-960** | 0/19 |
| 8 | 318/25/24 | ❌无 | — | 0/2 | 是 | -75 | 809 | **-491** | 0/1129 |

> - **持红钥匙**：到达 MT10 的那一刻手里有没有红钥匙。❌无 → 即便“到了 MT10”也进不了 boss 房，右侧 `HP−D` 余量是假的。
> - **满房真损血**：6 骷髅人+2 骷髅士兵+队长，按到达态属性引擎现算（不含走位/夹击，是下界口径的满房直损）。**重估余量 = HP − 满房真损血**。
> - **MT10态有红钥比例**：该 β 所有到达 MT10 的 cut 态里，持≥1 红钥匙的占比（看“到 MT10”是否普遍不需要红钥匙）。

## 2. 各 β best-MT10 逐里程碑（换层/装备宝石/拿钥匙/开门/打怪 + 坐标/属性/持钥）

### β=0　到达 MT10 落点=(1, 10)　终态 MT10(2,6) HP=92 ATK=25 DEF=25 持钥={}　封板对账=✅一致
- 红钥匙：**全程未拿红钥匙**　|　MT8 def22 卫兵杀了 0/2　|　队长可杀(atk>15)=是
- 余量：搜索看到 HP−D=-289（D 含红门免费+埋伏漏算）　vs　满房重估 HP−780=**-688**

| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |
|----|------|------|----|----|-----|---------|
| 0 | 起点（开局噩梦后首个自由态 MT3 入口） | (2,11)@MT3 | 400 | 10 | 10 | {} |
| 11 | 拿钥匙 blueKey×1 | (5,3)@MT3 | 400 | 10 | 10 | {'blueKey': 1} |
| 12 | 拿钥匙 yellowKey×1 | (4,3)@MT3 | 400 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 13 | 回血+200 | (4,2)@MT3 | 600 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 14 | 拿钥匙 yellowKey×1 | (4,1)@MT3 | 600 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 15 | 回血+200 | (5,1)@MT3 | 800 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 16 | 拿钥匙 yellowKey×1 | (5,2)@MT3 | 800 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 17 | 回血+200 | (6,2)@MT3 | 1000 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 18 | 拿钥匙 yellowKey×1 | (6,1)@MT3 | 1000 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 20 | 拿钥匙 yellowKey×1 | (6,3)@MT3 | 1000 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 25 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血112 | (3,5)@MT3 | 888 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 28 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 888 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 30 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血384 | (1,7)@MT3 | 504 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 32 | 回血+50 | (1,9)@MT3 | 554 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 34 | 拿钥匙 yellowKey×1 | (2,8)@MT3 | 554 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 35 | 拿攻击宝石+1ATK @(2, 9)  | (2,9)@MT3 | 554 | 11 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 54 | 换层 MT3→MT2 | (1,10)@MT2 | 554 | 11 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 63 | 换层 MT2→MT1 | (2,1)@MT1 | 554 | 11 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 91 | 开门(耗yellowKey×1) @(5, 3) | (5,3)@MT1 | 554 | 11 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 95 | 回血+50 | (1,3)@MT1 | 604 | 11 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 110 | 开门(耗yellowKey×1) @(10, 8) | (10,8)@MT1 | 604 | 11 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 112 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血112 | (10,10)@MT1 | 492 | 11 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 113 | 回血+200 | (10,11)@MT1 | 692 | 11 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 134 | 换层 MT1→MT2 | (1,2)@MT2 | 692 | 11 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 143 | 换层 MT2→MT3 | (2,11)@MT3 | 692 | 11 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 154 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,5)@MT3 | 668 | 11 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 160 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血40 | (8,10)@MT3 | 628 | 11 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 162 | 开门(耗yellowKey×1) @(8, 11) | (8,11)@MT3 | 628 | 11 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 165 | 换层 MT3→MT4 | (11,10)@MT4 | 628 | 11 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 167 | 开门(耗yellowKey×1) @(11, 9) | (11,9)@MT4 | 628 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 177 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (3,7)@MT4 | 604 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 179 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血40 | (1,7)@MT4 | 564 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 193 | 换层 MT4→MT3 | (10,11)@MT3 | 564 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 214 | 换层 MT3→MT2 | (1,10)@MT2 | 564 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 223 | 换层 MT2→MT1 | (2,1)@MT1 | 564 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 244 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (9,11)@MT1 | 540 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 266 | 换层 MT1→MT2 | (1,2)@MT2 | 540 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 275 | 换层 MT2→MT3 | (2,11)@MT3 | 540 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 296 | 换层 MT3→MT4 | (11,10)@MT4 | 540 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 307 | 开门(耗yellowKey×1) @(4, 7) | (4,7)@MT4 | 540 | 11 | 10 | {'blueKey': 1} |
| 309 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血112 | (4,9)@MT4 | 428 | 11 | 10 | {'blueKey': 1} |
| 311 | 拿钥匙 yellowKey×1 | (5,10)@MT4 | 428 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 312 | 拿钥匙 yellowKey×1 | (5,11)@MT4 | 428 | 11 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 321 | 开门(耗yellowKey×1) @(1, 7) | (1,7)@MT4 | 428 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 325 | 换层 MT4→MT5 | (2,11)@MT5 | 428 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 332 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (6,8)@MT5 | 404 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 335 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,6)@MT5 | 380 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 340 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血40 | (11,7)@MT5 | 340 | 11 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 345 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT5 | 340 | 11 | 10 | {'blueKey': 1} |
| 352 | 拿铁剑+10ATK @(11, 11)  | (11,11)@MT5 | 340 | 21 | 10 | {'blueKey': 1} |
| 378 | 换层 MT5→MT4 | (1,10)@MT4 | 340 | 21 | 10 | {'blueKey': 1} |
| 388 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (3,10)@MT4 | 332 | 21 | 10 | {'blueKey': 1} |
| 389 | 拿钥匙 yellowKey×1 | (3,11)@MT4 | 332 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 399 | 开门(耗yellowKey×1) @(8, 7) | (8,7)@MT4 | 332 | 21 | 10 | {'blueKey': 1} |
| 401 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (8,9)@MT4 | 244 | 21 | 10 | {'blueKey': 1} |
| 403 | 拿攻击宝石+1ATK @(7, 10)  | (7,10)@MT4 | 244 | 22 | 10 | {'blueKey': 1} |
| 405 | 回血+50 | (9,10)@MT4 | 294 | 22 | 10 | {'blueKey': 1} |
| 420 | 换层 MT4→MT5 | (2,11)@MT5 | 294 | 22 | 10 | {'blueKey': 1} |
| 431 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (6,4)@MT5 | 266 | 22 | 10 | {'blueKey': 1} |
| 433 | 拿钥匙 yellowKey×1 | (6,2)@MT5 | 266 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 446 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,2)@MT5 | 246 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 448 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT5 | 246 | 22 | 10 | {'blueKey': 1} |
| 452 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (8,2)@MT5 | 238 | 22 | 10 | {'blueKey': 1} |
| 453 | 拿钥匙 yellowKey×1 | (8,3)@MT5 | 238 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 454 | 拿钥匙 yellowKey×1 | (8,4)@MT5 | 238 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 455 | 拿钥匙 yellowKey×1 | (9,4)@MT5 | 238 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 456 | 拿钥匙 yellowKey×1 | (9,3)@MT5 | 238 | 22 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 478 | 开门(耗yellowKey×1) @(6, 1) | (6,1)@MT5 | 238 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 480 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,1)@MT5 | 218 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 483 | 开门(耗yellowKey×1) @(4, 3) | (4,3)@MT5 | 218 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 484 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT5 | 190 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 485 | 开门(耗yellowKey×1) @(3, 3) | (3,3)@MT5 | 190 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 489 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,6)@MT5 | 162 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 492 | 拿钥匙 yellowKey×1 | (1,6)@MT5 | 162 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 493 | 拿钥匙 yellowKey×1 | (1,5)@MT5 | 162 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 505 | 换层 MT5→MT6 | (1,2)@MT6 | 162 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 508 | 开门(耗yellowKey×1) @(1, 4) | (1,4)@MT6 | 162 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 510 | 开门(耗yellowKey×1) @(2, 4) | (2,4)@MT6 | 162 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 513 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,3)@MT6 | 142 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 514 | 拿钥匙 yellowKey×1 | (4,2)@MT6 | 142 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 515 | 拿钥匙 yellowKey×1 | (4,1)@MT6 | 142 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 516 | 拿钥匙 yellowKey×1 | (3,1)@MT6 | 142 | 22 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 517 | 拿钥匙 yellowKey×1 | (3,2)@MT6 | 142 | 22 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 521 | 开门(耗yellowKey×1) @(4, 4) | (4,4)@MT6 | 142 | 22 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 525 | 拿钥匙 yellowKey×1 | (6,6)@MT6 | 142 | 22 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 528 | 开门(耗yellowKey×1) @(6, 8) | (6,8)@MT6 | 142 | 22 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 530 | 开门(耗yellowKey×1) @(7, 8) | (7,8)@MT6 | 142 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 533 | 开门(耗yellowKey×1) @(9, 8) | (9,8)@MT6 | 142 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 536 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,9)@MT6 | 122 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 540 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (9,9)@MT6 | 102 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 542 | 回血+50 | (9,11)@MT6 | 152 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 543 | 回血+50 | (8,11)@MT6 | 202 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 552 | 换层 MT6→MT7 | (11,10)@MT7 | 202 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 555 | 开门(耗yellowKey×1) @(11, 8) | (11,8)@MT7 | 202 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 564 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT7 | 114 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 566 | 开门(耗yellowKey×1) @(3, 6) | (3,6)@MT7 | 114 | 22 | 10 | {'blueKey': 1} |
| 569 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT7 | 86 | 22 | 10 | {'blueKey': 1} |
| 570 | 回血+50 | (3,2)@MT7 | 136 | 22 | 10 | {'blueKey': 1} |
| 571 | 拿攻击宝石+1ATK @(3, 1)  | (3,1)@MT7 | 136 | 23 | 10 | {'blueKey': 1} |
| 583 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血64 | (9,5)@MT7 | 72 | 23 | 10 | {'blueKey': 1} |
| 585 | 回血+50 | (9,3)@MT7 | 122 | 23 | 10 | {'blueKey': 1} |
| 586 | 拿钥匙 yellowKey×1 | (9,2)@MT7 | 122 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 587 | 拿钥匙 yellowKey×1 | (9,1)@MT7 | 122 | 23 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 595 | 开门(耗yellowKey×1) @(7, 6) | (7,6)@MT7 | 122 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 598 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (7,9)@MT7 | 102 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 599 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血66 | (7,10)@MT7 | 36 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 600 | 回血+200 | (7,11)@MT7 | 236 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 608 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血168 | (9,7)@MT7 | 68 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 610 | 回血+200 | (9,9)@MT7 | 268 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 611 | 拿钥匙 yellowKey×1 | (9,10)@MT7 | 268 | 23 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 612 | 拿钥匙 yellowKey×1 | (9,11)@MT7 | 268 | 23 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 624 | 换层 MT7→MT6 | (11,10)@MT6 | 268 | 23 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 644 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (3,6)@MT6 | 248 | 23 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 665 | 换层 MT6→MT7 | (11,10)@MT7 | 248 | 23 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 676 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT7 | 248 | 23 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 679 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (5,9)@MT7 | 220 | 23 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 680 | 拿钥匙 yellowKey×1 | (5,10)@MT7 | 220 | 23 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 681 | 拿钥匙 yellowKey×1 | (5,11)@MT7 | 220 | 23 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 689 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血168 | (2,6)@MT7 | 52 | 23 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 691 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 52 | 23 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 696 | 换层 MT7→MT8 | (1,2)@MT8 | 52 | 23 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 697 | 开门(耗yellowKey×1) @(1, 2) | (1,2)@MT8 | 52 | 23 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 700 | 回血+50 | (1,5)@MT8 | 102 | 23 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 706 | 开门(耗yellowKey×1) @(2, 1) | (2,1)@MT8 | 102 | 23 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 708 | 开门(耗yellowKey×1) @(3, 1) | (3,1)@MT8 | 102 | 23 | 10 | {'blueKey': 1} |
| 713 | 换层 MT8→MT9 | (6,2)@MT9 | 102 | 23 | 10 | {'blueKey': 1} |
| 714 | 开门(耗blueKey×1) @(6, 2) | (6,2)@MT9 | 102 | 23 | 10 | {} |
| 717 | 拿钥匙 yellowKey×1 | (7,4)@MT9 | 102 | 23 | 10 | {'yellowKey': 1} |
| 719 | 拿攻击宝石+1ATK @(6, 5)  | (6,5)@MT9 | 102 | 24 | 10 | {'yellowKey': 1} |
| 721 | 拿钥匙 yellowKey×1 | (5,4)@MT9 | 102 | 24 | 10 | {'yellowKey': 2} |
| 727 | 开门(耗yellowKey×1) @(7, 1) | (7,1)@MT9 | 102 | 24 | 10 | {'yellowKey': 1} |
| 729 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,1)@MT9 | 94 | 24 | 10 | {'yellowKey': 1} |
| 731 | 回血+50 | (11,1)@MT9 | 144 | 24 | 10 | {'yellowKey': 1} |
| 740 | 拿铁盾+10DEF @(9, 7)  | (9,7)@MT9 | 144 | 24 | 20 | {'yellowKey': 1} |
| 752 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,2)@MT9 | 144 | 24 | 20 | {'yellowKey': 1} |
| 761 | 换层 MT9→MT8 | (6,2)@MT8 | 144 | 24 | 20 | {'yellowKey': 1} |
| 762 | 开门(耗yellowKey×1) @(6, 2) | (6,2)@MT8 | 144 | 24 | 20 | {} |
| 765 | 拿钥匙 yellowKey×1 | (5,4)@MT8 | 144 | 24 | 20 | {'yellowKey': 1} |
| 766 | 拿钥匙 yellowKey×1 | (4,4)@MT8 | 144 | 24 | 20 | {'yellowKey': 2} |
| 767 | 拿钥匙 yellowKey×1 | (3,4)@MT8 | 144 | 24 | 20 | {'yellowKey': 3} |
| 773 | 换层 MT8→MT9 | (6,2)@MT9 | 144 | 24 | 20 | {'yellowKey': 3} |
| 778 | 开门(耗yellowKey×1) @(5, 5) | (5,5)@MT9 | 144 | 24 | 20 | {'yellowKey': 2} |
| 781 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,6)@MT9 | 144 | 24 | 20 | {'yellowKey': 2} |
| 786 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血18 | (3,5)@MT9 | 126 | 24 | 20 | {'yellowKey': 2} |
| 788 | 拿钥匙 yellowKey×1 | (2,4)@MT9 | 126 | 24 | 20 | {'yellowKey': 3} |
| 790 | 拿防御宝石+1DEF @(1, 5)  | (1,5)@MT9 | 126 | 24 | 21 | {'yellowKey': 3} |
| 801 | 换层 MT9→MT8 | (6,2)@MT8 | 126 | 24 | 21 | {'yellowKey': 3} |
| 802 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (7,2)@MT8 | 126 | 24 | 21 | {'yellowKey': 3} |
| 815 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,6)@MT8 | 126 | 24 | 21 | {'yellowKey': 3} |
| 816 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,6)@MT8 | 126 | 24 | 21 | {'yellowKey': 3} |
| 817 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (4,6)@MT8 | 126 | 24 | 21 | {'yellowKey': 3} |
| 825 | 换层 MT8→MT7 | (1,2)@MT7 | 126 | 24 | 21 | {'yellowKey': 3} |
| 844 | 换层 MT7→MT6 | (11,10)@MT6 | 126 | 24 | 21 | {'yellowKey': 3} |
| 863 | 换层 MT6→MT5 | (1,2)@MT5 | 126 | 24 | 21 | {'yellowKey': 3} |
| 873 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (2,7)@MT5 | 2 | 24 | 21 | {'yellowKey': 3} |
| 875 | 拿钥匙 yellowKey×1 | (2,9)@MT5 | 2 | 24 | 21 | {'yellowKey': 4} |
| 876 | 回血+50 | (3,9)@MT5 | 52 | 24 | 21 | {'yellowKey': 4} |
| 880 | 拿防御宝石+1DEF @(1, 9)  | (1,9)@MT5 | 52 | 24 | 22 | {'yellowKey': 4} |
| 913 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (9,2)@MT5 | 52 | 24 | 22 | {'yellowKey': 4} |
| 936 | 换层 MT5→MT4 | (1,10)@MT4 | 52 | 24 | 22 | {'yellowKey': 4} |
| 948 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (4,11)@MT4 | 52 | 24 | 22 | {'yellowKey': 4} |
| 962 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,11)@MT4 | 52 | 24 | 22 | {'yellowKey': 4} |
| 976 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (2,5)@MT4 | 22 | 24 | 22 | {'yellowKey': 4} |
| 977 | 开门(耗yellowKey×1) @(2, 5) | (2,5)@MT4 | 22 | 24 | 22 | {'yellowKey': 3} |
| 981 | 回血+50 | (1,2)@MT4 | 72 | 24 | 22 | {'yellowKey': 3} |
| 983 | 拿钥匙 blueKey×1 | (2,1)@MT4 | 72 | 24 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 985 | 拿钥匙 yellowKey×1 | (3,2)@MT4 | 72 | 24 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 996 | 换层 MT4→MT5 | (2,11)@MT5 | 72 | 24 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1019 | 换层 MT5→MT6 | (1,2)@MT6 | 72 | 24 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1038 | 换层 MT6→MT7 | (11,10)@MT7 | 72 | 24 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1057 | 换层 MT7→MT8 | (1,2)@MT8 | 72 | 24 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1063 | 换层 MT8→MT9 | (6,2)@MT9 | 72 | 24 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1072 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (7,10)@MT9 | 56 | 24 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1074 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 56 | 24 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1078 | 开门(耗blueKey×1) @(4, 11) | (4,11)@MT9 | 56 | 24 | 22 | {'yellowKey': 3} |
| 1081 | 回血+50 | (2,10)@MT9 | 106 | 24 | 22 | {'yellowKey': 3} |
| 1088 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 106 | 24 | 22 | {'yellowKey': 2} |
| 1090 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (9,11)@MT9 | 76 | 24 | 22 | {'yellowKey': 2} |
| 1092 | 回血+50 | (11,11)@MT9 | 126 | 24 | 22 | {'yellowKey': 2} |
| 1096 | 拿钥匙 yellowKey×1 | (9,9)@MT9 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1113 | 换层 MT9→MT8 | (6,2)@MT8 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1121 | 换层 MT8→MT7 | (1,2)@MT7 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1140 | 换层 MT7→MT6 | (11,10)@MT6 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1159 | 换层 MT6→MT5 | (1,2)@MT5 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1182 | 换层 MT5→MT4 | (1,10)@MT4 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1199 | 换层 MT4→MT3 | (10,11)@MT3 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1220 | 换层 MT3→MT2 | (1,10)@MT2 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1229 | 换层 MT2→MT1 | (2,1)@MT1 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1250 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,11)@MT1 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1272 | 换层 MT1→MT2 | (1,2)@MT2 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1281 | 换层 MT2→MT3 | (2,11)@MT3 | 126 | 24 | 22 | {'yellowKey': 3} |
| 1297 | 开门(耗yellowKey×1) @(8, 2) | (8,2)@MT3 | 126 | 24 | 22 | {'yellowKey': 2} |
| 1299 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (10,2)@MT3 | 110 | 24 | 22 | {'yellowKey': 2} |
| 1301 | 回血+50 | (11,1)@MT3 | 160 | 24 | 22 | {'yellowKey': 2} |
| 1316 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 160 | 24 | 22 | {'yellowKey': 1} |
| 1318 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (1,3)@MT3 | 130 | 24 | 22 | {'yellowKey': 1} |
| 1320 | 回血+50 | (2,2)@MT3 | 180 | 24 | 22 | {'yellowKey': 1} |
| 1321 | 拿防御宝石+1DEF @(2, 1)  | (2,1)@MT3 | 180 | 24 | 23 | {'yellowKey': 1} |
| 1322 | 拿钥匙 yellowKey×1 | (1,1)@MT3 | 180 | 24 | 23 | {'yellowKey': 2} |
| 1337 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT3 | 180 | 24 | 23 | {'yellowKey': 1} |
| 1339 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血27 | (10,8)@MT3 | 153 | 24 | 23 | {'yellowKey': 1} |
| 1340 | 拿钥匙 yellowKey×1 | (11,8)@MT3 | 153 | 24 | 23 | {'yellowKey': 2} |
| 1341 | 回血+50 | (11,7)@MT3 | 203 | 24 | 23 | {'yellowKey': 2} |
| 1361 | 换层 MT3→MT2 | (1,10)@MT2 | 203 | 24 | 23 | {'yellowKey': 2} |
| 1370 | 换层 MT2→MT1 | (2,1)@MT1 | 203 | 24 | 23 | {'yellowKey': 2} |
| 1401 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血38 | (2,4)@MT1 | 165 | 24 | 23 | {'yellowKey': 2} |
| 1402 | 开门(耗yellowKey×1) @(2, 4) | (2,4)@MT1 | 165 | 24 | 23 | {'yellowKey': 1} |
| 1405 | 拿钥匙 yellowKey×1 | (1,6)@MT1 | 165 | 24 | 23 | {'yellowKey': 2} |
| 1409 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血116 | (2,7)@MT1 | 49 | 24 | 23 | {'yellowKey': 2} |
| 1410 | 开门(耗yellowKey×1) @(2, 7) | (2,7)@MT1 | 49 | 24 | 23 | {'yellowKey': 1} |
| 1414 | 拿钥匙 yellowKey×1 | (3,10)@MT1 | 49 | 24 | 23 | {'yellowKey': 2} |
| 1415 | 拿钥匙 yellowKey×1 | (3,11)@MT1 | 49 | 24 | 23 | {'yellowKey': 3} |
| 1417 | 回血+50 | (1,11)@MT1 | 99 | 24 | 23 | {'yellowKey': 3} |
| 1418 | 回血+50 | (1,10)@MT1 | 149 | 24 | 23 | {'yellowKey': 3} |
| 1433 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT1 | 149 | 24 | 23 | {'yellowKey': 2} |
| 1435 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血15 | (7,6)@MT1 | 134 | 24 | 23 | {'yellowKey': 2} |
| 1436 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血27 | (8,6)@MT1 | 107 | 24 | 23 | {'yellowKey': 2} |
| 1437 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血15 | (9,6)@MT1 | 92 | 24 | 23 | {'yellowKey': 2} |
| 1438 | 开门(耗yellowKey×1) @(9, 6) | (9,6)@MT1 | 92 | 24 | 23 | {'yellowKey': 1} |
| 1442 | 拿钥匙 yellowKey×1 | (8,3)@MT1 | 92 | 24 | 23 | {'yellowKey': 2} |
| 1443 | 回血+50 | (8,4)@MT1 | 142 | 24 | 23 | {'yellowKey': 2} |
| 1444 | 拿防御宝石+1DEF @(7, 4)  | (7,4)@MT1 | 142 | 24 | 24 | {'yellowKey': 2} |
| 1445 | 拿攻击宝石+1ATK @(7, 3)  | (7,3)@MT1 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1479 | 换层 MT1→MT2 | (1,2)@MT2 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1488 | 换层 MT2→MT3 | (2,11)@MT3 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1509 | 换层 MT3→MT4 | (11,10)@MT4 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1526 | 换层 MT4→MT5 | (2,11)@MT5 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1549 | 换层 MT5→MT6 | (1,2)@MT6 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1568 | 换层 MT6→MT7 | (11,10)@MT7 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1587 | 换层 MT7→MT8 | (1,2)@MT8 | 142 | 25 | 24 | {'yellowKey': 2} |
| 1596 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT8 | 142 | 25 | 24 | {'yellowKey': 1} |
| 1599 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血14 | (4,8)@MT8 | 128 | 25 | 24 | {'yellowKey': 1} |
| 1616 | 换层 MT8→MT9 | (6,2)@MT9 | 128 | 25 | 24 | {'yellowKey': 1} |
| 1632 | 换层 MT9→MT10 | (1,10)@MT10 | 128 | 25 | 24 | {'yellowKey': 1} |
| 1633 | 开门(耗yellowKey×1) @(1, 10) | (1,10)@MT10 | 128 | 25 | 24 | {} |
| 1639 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (3,6)@MT10 | 92 | 25 | 24 | {} |
| 1640 | 拿防御宝石+1DEF @(2, 6)  | (2,6)@MT10 | 92 | 25 | 25 | {} |

### β=0.5　到达 MT10 落点=(1, 10)　终态 MT10(1,10) HP=553 ATK=25 DEF=25 持钥={}　封板对账=✅一致
- 红钥匙：**全程未拿红钥匙**　|　MT8 def22 卫兵杀了 0/2　|　队长可杀(atk>15)=是
- 余量：搜索看到 HP−D=172（D 含红门免费+埋伏漏算）　vs　满房重估 HP−780=**-227**

| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |
|----|------|------|----|----|-----|---------|
| 0 | 起点（开局噩梦后首个自由态 MT3 入口） | (2,11)@MT3 | 400 | 10 | 10 | {} |
| 11 | 拿钥匙 blueKey×1 | (5,3)@MT3 | 400 | 10 | 10 | {'blueKey': 1} |
| 12 | 拿钥匙 yellowKey×1 | (4,3)@MT3 | 400 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 13 | 回血+200 | (4,2)@MT3 | 600 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 14 | 拿钥匙 yellowKey×1 | (4,1)@MT3 | 600 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 15 | 回血+200 | (5,1)@MT3 | 800 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 16 | 拿钥匙 yellowKey×1 | (5,2)@MT3 | 800 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 17 | 回血+200 | (6,2)@MT3 | 1000 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 18 | 拿钥匙 yellowKey×1 | (6,1)@MT3 | 1000 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 20 | 拿钥匙 yellowKey×1 | (6,3)@MT3 | 1000 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 25 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,5)@MT3 | 976 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 31 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (8,10)@MT3 | 926 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 33 | 开门(耗yellowKey×1) @(8, 11) | (8,11)@MT3 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 36 | 换层 MT3→MT4 | (11,10)@MT4 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 38 | 开门(耗yellowKey×1) @(11, 9) | (11,9)@MT4 | 926 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 48 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (3,7)@MT4 | 902 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 50 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 51 | 开门(耗yellowKey×1) @(1, 7) | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 55 | 换层 MT4→MT5 | (2,11)@MT5 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 62 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (6,8)@MT5 | 828 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 65 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,6)@MT5 | 804 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 70 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (11,7)@MT5 | 754 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 75 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT5 | 754 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 82 | 拿铁剑+10ATK @(11, 11)  | (11,11)@MT5 | 754 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 97 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,2)@MT5 | 734 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 99 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT5 | 734 | 20 | 10 | {'blueKey': 1} |
| 102 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,2)@MT5 | 726 | 20 | 10 | {'blueKey': 1} |
| 103 | 拿钥匙 yellowKey×1 | (9,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 104 | 拿钥匙 yellowKey×1 | (8,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 105 | 拿钥匙 yellowKey×1 | (8,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 106 | 拿钥匙 yellowKey×1 | (9,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 131 | 换层 MT5→MT4 | (1,10)@MT4 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 142 | 开门(耗yellowKey×1) @(8, 7) | (8,7)@MT4 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 144 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (8,9)@MT4 | 638 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 146 | 拿攻击宝石+1ATK @(7, 10)  | (7,10)@MT4 | 638 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 148 | 回血+50 | (9,10)@MT4 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 159 | 换层 MT4→MT3 | (10,11)@MT3 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 180 | 换层 MT3→MT2 | (1,10)@MT2 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 189 | 换层 MT2→MT1 | (2,1)@MT1 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 217 | 开门(耗yellowKey×1) @(5, 3) | (5,3)@MT1 | 688 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 221 | 回血+50 | (1,3)@MT1 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 236 | 开门(耗yellowKey×1) @(10, 8) | (10,8)@MT1 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 238 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (10,10)@MT1 | 710 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 239 | 回血+200 | (10,11)@MT1 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 260 | 换层 MT1→MT2 | (1,2)@MT2 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 269 | 换层 MT2→MT3 | (2,11)@MT3 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 290 | 换层 MT3→MT4 | (11,10)@MT4 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 301 | 开门(耗yellowKey×1) @(4, 7) | (4,7)@MT4 | 910 | 21 | 10 | {'blueKey': 1} |
| 303 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,9)@MT4 | 882 | 21 | 10 | {'blueKey': 1} |
| 305 | 拿钥匙 yellowKey×1 | (5,10)@MT4 | 882 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 306 | 拿钥匙 yellowKey×1 | (5,11)@MT4 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 318 | 换层 MT4→MT5 | (2,11)@MT5 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 329 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (6,4)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 331 | 拿钥匙 yellowKey×1 | (6,2)@MT5 | 854 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 333 | 开门(耗yellowKey×1) @(6, 1) | (6,1)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 335 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,1)@MT5 | 834 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 338 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 339 | 开门(耗yellowKey×1) @(3, 3) | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 341 | 开门(耗yellowKey×1) @(4, 3) | (4,3)@MT5 | 806 | 21 | 10 | {'blueKey': 1} |
| 344 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,6)@MT5 | 778 | 21 | 10 | {'blueKey': 1} |
| 347 | 拿钥匙 yellowKey×1 | (1,6)@MT5 | 778 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 348 | 拿钥匙 yellowKey×1 | (1,5)@MT5 | 778 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 360 | 换层 MT5→MT6 | (1,2)@MT6 | 778 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 366 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (3,6)@MT6 | 758 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 367 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT6 | 670 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 369 | 拿钥匙 yellowKey×1 | (6,6)@MT6 | 670 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 372 | 开门(耗yellowKey×1) @(6, 8) | (6,8)@MT6 | 670 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 374 | 开门(耗yellowKey×1) @(7, 8) | (7,8)@MT6 | 670 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 377 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (9,9)@MT6 | 650 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 379 | 回血+50 | (9,11)@MT6 | 700 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 380 | 回血+50 | (8,11)@MT6 | 750 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 392 | 开门(耗yellowKey×1) @(6, 4) | (6,4)@MT6 | 750 | 21 | 10 | {'blueKey': 1} |
| 395 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,3)@MT6 | 730 | 21 | 10 | {'blueKey': 1} |
| 396 | 拿钥匙 yellowKey×1 | (4,2)@MT6 | 730 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 397 | 拿钥匙 yellowKey×1 | (4,1)@MT6 | 730 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 398 | 拿钥匙 yellowKey×1 | (3,1)@MT6 | 730 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 399 | 拿钥匙 yellowKey×1 | (3,2)@MT6 | 730 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 412 | 开门(耗yellowKey×1) @(9, 8) | (9,8)@MT6 | 730 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 415 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,9)@MT6 | 710 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 417 | 换层 MT6→MT7 | (11,10)@MT7 | 710 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 420 | 开门(耗yellowKey×1) @(11, 8) | (11,8)@MT7 | 710 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 429 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT7 | 622 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 431 | 开门(耗yellowKey×1) @(3, 6) | (3,6)@MT7 | 622 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 434 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT7 | 594 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 435 | 回血+50 | (3,2)@MT7 | 644 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 436 | 拿攻击宝石+1ATK @(3, 1)  | (3,1)@MT7 | 644 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 442 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血210 | (2,6)@MT7 | 434 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 444 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 434 | 22 | 10 | {'blueKey': 1} |
| 453 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血96 | (9,5)@MT7 | 338 | 22 | 10 | {'blueKey': 1} |
| 455 | 回血+50 | (9,3)@MT7 | 388 | 22 | 10 | {'blueKey': 1} |
| 456 | 拿钥匙 yellowKey×1 | (9,2)@MT7 | 388 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 457 | 拿钥匙 yellowKey×1 | (9,1)@MT7 | 388 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 475 | 换层 MT7→MT8 | (1,2)@MT8 | 388 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 478 | 开门(耗yellowKey×1) @(2, 1) | (2,1)@MT8 | 388 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 480 | 开门(耗yellowKey×1) @(3, 1) | (3,1)@MT8 | 388 | 22 | 10 | {'blueKey': 1} |
| 485 | 换层 MT8→MT9 | (6,2)@MT9 | 388 | 22 | 10 | {'blueKey': 1} |
| 486 | 开门(耗blueKey×1) @(6, 2) | (6,2)@MT9 | 388 | 22 | 10 | {} |
| 489 | 拿钥匙 yellowKey×1 | (7,4)@MT9 | 388 | 22 | 10 | {'yellowKey': 1} |
| 491 | 拿攻击宝石+1ATK @(6, 5)  | (6,5)@MT9 | 388 | 23 | 10 | {'yellowKey': 1} |
| 493 | 拿钥匙 yellowKey×1 | (5,4)@MT9 | 388 | 23 | 10 | {'yellowKey': 2} |
| 499 | 开门(耗yellowKey×1) @(7, 1) | (7,1)@MT9 | 388 | 23 | 10 | {'yellowKey': 1} |
| 501 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,1)@MT9 | 380 | 23 | 10 | {'yellowKey': 1} |
| 503 | 回血+50 | (11,1)@MT9 | 430 | 23 | 10 | {'yellowKey': 1} |
| 512 | 拿铁盾+10DEF @(9, 7)  | (9,7)@MT9 | 430 | 23 | 20 | {'yellowKey': 1} |
| 529 | 换层 MT9→MT8 | (6,2)@MT8 | 430 | 23 | 20 | {'yellowKey': 1} |
| 530 | 开门(耗yellowKey×1) @(6, 2) | (6,2)@MT8 | 430 | 23 | 20 | {} |
| 533 | 拿钥匙 yellowKey×1 | (5,4)@MT8 | 430 | 23 | 20 | {'yellowKey': 1} |
| 534 | 拿钥匙 yellowKey×1 | (4,4)@MT8 | 430 | 23 | 20 | {'yellowKey': 2} |
| 535 | 拿钥匙 yellowKey×1 | (3,4)@MT8 | 430 | 23 | 20 | {'yellowKey': 3} |
| 548 | 开门(耗yellowKey×1) @(1, 2) | (1,2)@MT8 | 430 | 23 | 20 | {'yellowKey': 2} |
| 551 | 回血+50 | (1,5)@MT8 | 480 | 23 | 20 | {'yellowKey': 2} |
| 562 | 换层 MT8→MT9 | (6,2)@MT9 | 480 | 23 | 20 | {'yellowKey': 2} |
| 568 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,2)@MT9 | 480 | 23 | 20 | {'yellowKey': 2} |
| 579 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,6)@MT9 | 480 | 23 | 20 | {'yellowKey': 2} |
| 587 | 换层 MT9→MT8 | (6,2)@MT8 | 480 | 23 | 20 | {'yellowKey': 2} |
| 588 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (7,2)@MT8 | 480 | 23 | 20 | {'yellowKey': 2} |
| 601 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,6)@MT8 | 480 | 23 | 20 | {'yellowKey': 2} |
| 607 | 换层 MT8→MT7 | (1,2)@MT7 | 480 | 23 | 20 | {'yellowKey': 2} |
| 612 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 480 | 23 | 20 | {'yellowKey': 1} |
| 616 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (1,10)@MT7 | 480 | 23 | 20 | {'yellowKey': 1} |
| 618 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,11)@MT7 | 480 | 23 | 20 | {'yellowKey': 1} |
| 620 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,10)@MT7 | 480 | 23 | 20 | {'yellowKey': 1} |
| 633 | 换层 MT7→MT8 | (1,2)@MT8 | 480 | 23 | 20 | {'yellowKey': 1} |
| 639 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,6)@MT8 | 480 | 23 | 20 | {'yellowKey': 1} |
| 640 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (4,6)@MT8 | 480 | 23 | 20 | {'yellowKey': 1} |
| 653 | 换层 MT8→MT9 | (6,2)@MT9 | 480 | 23 | 20 | {'yellowKey': 1} |
| 658 | 开门(耗yellowKey×1) @(5, 5) | (5,5)@MT9 | 480 | 23 | 20 | {} |
| 660 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血18 | (3,5)@MT9 | 462 | 23 | 20 | {} |
| 662 | 拿钥匙 yellowKey×1 | (2,4)@MT9 | 462 | 23 | 20 | {'yellowKey': 1} |
| 664 | 拿防御宝石+1DEF @(1, 5)  | (1,5)@MT9 | 462 | 23 | 21 | {'yellowKey': 1} |
| 675 | 换层 MT9→MT8 | (6,2)@MT8 | 462 | 23 | 21 | {'yellowKey': 1} |
| 683 | 换层 MT8→MT7 | (1,2)@MT7 | 462 | 23 | 21 | {'yellowKey': 1} |
| 694 | 开门(耗yellowKey×1) @(7, 6) | (7,6)@MT7 | 462 | 23 | 21 | {} |
| 697 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,9)@MT7 | 462 | 23 | 21 | {} |
| 698 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (7,10)@MT7 | 429 | 23 | 21 | {} |
| 699 | 回血+200 | (7,11)@MT7 | 629 | 23 | 21 | {} |
| 707 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (9,7)@MT7 | 505 | 23 | 21 | {} |
| 709 | 回血+200 | (9,9)@MT7 | 705 | 23 | 21 | {} |
| 710 | 拿钥匙 yellowKey×1 | (9,10)@MT7 | 705 | 23 | 21 | {'yellowKey': 1} |
| 711 | 拿钥匙 yellowKey×1 | (9,11)@MT7 | 705 | 23 | 21 | {'yellowKey': 2} |
| 719 | 开门(耗yellowKey×1) @(11, 6) | (11,6)@MT7 | 705 | 23 | 21 | {'yellowKey': 1} |
| 722 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,3)@MT7 | 705 | 23 | 21 | {'yellowKey': 1} |
| 723 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (11,2)@MT7 | 705 | 23 | 21 | {'yellowKey': 1} |
| 742 | 换层 MT7→MT8 | (1,2)@MT8 | 705 | 23 | 21 | {'yellowKey': 1} |
| 748 | 换层 MT8→MT9 | (6,2)@MT9 | 705 | 23 | 21 | {'yellowKey': 1} |
| 757 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (7,10)@MT9 | 688 | 23 | 21 | {'yellowKey': 1} |
| 759 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 688 | 23 | 21 | {} |
| 761 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (9,11)@MT9 | 655 | 23 | 21 | {} |
| 763 | 回血+50 | (11,11)@MT9 | 705 | 23 | 21 | {} |
| 767 | 拿钥匙 yellowKey×1 | (9,9)@MT9 | 705 | 23 | 21 | {'yellowKey': 1} |
| 784 | 换层 MT9→MT8 | (6,2)@MT8 | 705 | 23 | 21 | {'yellowKey': 1} |
| 792 | 换层 MT8→MT7 | (1,2)@MT7 | 705 | 23 | 21 | {'yellowKey': 1} |
| 811 | 换层 MT7→MT6 | (11,10)@MT6 | 705 | 23 | 21 | {'yellowKey': 1} |
| 830 | 换层 MT6→MT5 | (1,2)@MT5 | 705 | 23 | 21 | {'yellowKey': 1} |
| 840 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (2,7)@MT5 | 581 | 23 | 21 | {'yellowKey': 1} |
| 842 | 拿钥匙 yellowKey×1 | (2,9)@MT5 | 581 | 23 | 21 | {'yellowKey': 2} |
| 843 | 回血+50 | (3,9)@MT5 | 631 | 23 | 21 | {'yellowKey': 2} |
| 847 | 拿防御宝石+1DEF @(1, 9)  | (1,9)@MT5 | 631 | 23 | 22 | {'yellowKey': 2} |
| 875 | 换层 MT5→MT4 | (1,10)@MT4 | 631 | 23 | 22 | {'yellowKey': 2} |
| 885 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,10)@MT4 | 631 | 23 | 22 | {'yellowKey': 2} |
| 886 | 拿钥匙 yellowKey×1 | (3,11)@MT4 | 631 | 23 | 22 | {'yellowKey': 3} |
| 887 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (4,11)@MT4 | 631 | 23 | 22 | {'yellowKey': 3} |
| 897 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (2,5)@MT4 | 601 | 23 | 22 | {'yellowKey': 3} |
| 898 | 开门(耗yellowKey×1) @(2, 5) | (2,5)@MT4 | 601 | 23 | 22 | {'yellowKey': 2} |
| 902 | 回血+50 | (1,2)@MT4 | 651 | 23 | 22 | {'yellowKey': 2} |
| 904 | 拿钥匙 blueKey×1 | (2,1)@MT4 | 651 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 906 | 拿钥匙 yellowKey×1 | (3,2)@MT4 | 651 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 924 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,11)@MT4 | 651 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 935 | 换层 MT4→MT3 | (10,11)@MT3 | 651 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 948 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (3,5)@MT3 | 635 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 960 | 换层 MT3→MT2 | (1,10)@MT2 | 635 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 969 | 换层 MT2→MT1 | (2,1)@MT1 | 635 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 990 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (9,11)@MT1 | 635 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 992 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,11)@MT1 | 635 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1010 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血40 | (2,4)@MT1 | 595 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1011 | 开门(耗yellowKey×1) @(2, 4) | (2,4)@MT1 | 595 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1014 | 拿钥匙 yellowKey×1 | (1,6)@MT1 | 595 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1018 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血120 | (2,7)@MT1 | 475 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1019 | 开门(耗yellowKey×1) @(2, 7) | (2,7)@MT1 | 475 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1023 | 拿钥匙 yellowKey×1 | (3,10)@MT1 | 475 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1024 | 拿钥匙 yellowKey×1 | (3,11)@MT1 | 475 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1026 | 回血+50 | (1,11)@MT1 | 525 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1027 | 回血+50 | (1,10)@MT1 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1066 | 换层 MT1→MT2 | (1,2)@MT2 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1075 | 换层 MT2→MT3 | (2,11)@MT3 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1096 | 换层 MT3→MT4 | (11,10)@MT4 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1113 | 换层 MT4→MT5 | (2,11)@MT5 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1136 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,2)@MT5 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1164 | 换层 MT5→MT6 | (1,2)@MT6 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1183 | 换层 MT6→MT7 | (11,10)@MT7 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1192 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,1)@MT7 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1202 | 换层 MT7→MT6 | (11,10)@MT6 | 575 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1213 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血40 | (5,11)@MT6 | 535 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1221 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血40 | (8,6)@MT6 | 495 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1232 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (2,11)@MT6 | 495 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1247 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (7,1)@MT6 | 465 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1249 | 拿钥匙 yellowKey×1 | (9,1)@MT6 | 465 | 23 | 22 | {'yellowKey': 5, 'blueKey': 1} |
| 1250 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,1)@MT6 | 465 | 23 | 22 | {'yellowKey': 5, 'blueKey': 1} |
| 1269 | 换层 MT6→MT5 | (1,2)@MT5 | 465 | 23 | 22 | {'yellowKey': 5, 'blueKey': 1} |
| 1280 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (3,5)@MT5 | 435 | 23 | 22 | {'yellowKey': 5, 'blueKey': 1} |
| 1302 | 换层 MT5→MT4 | (1,10)@MT4 | 435 | 23 | 22 | {'yellowKey': 5, 'blueKey': 1} |
| 1310 | 开门(耗yellowKey×1) @(3, 5) | (3,5)@MT4 | 435 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1313 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (6,5)@MT4 | 435 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1330 | 换层 MT4→MT3 | (10,11)@MT3 | 435 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1351 | 换层 MT3→MT2 | (1,10)@MT2 | 435 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1360 | 换层 MT2→MT1 | (2,1)@MT1 | 435 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1385 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT1 | 435 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1387 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (7,6)@MT1 | 419 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1388 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (8,6)@MT1 | 389 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1389 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (9,6)@MT1 | 373 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1390 | 开门(耗yellowKey×1) @(9, 6) | (9,6)@MT1 | 373 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1394 | 拿钥匙 yellowKey×1 | (8,3)@MT1 | 373 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1395 | 回血+50 | (8,4)@MT1 | 423 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1396 | 拿防御宝石+1DEF @(7, 4)  | (7,4)@MT1 | 423 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1397 | 拿攻击宝石+1ATK @(7, 3)  | (7,3)@MT1 | 423 | 24 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1431 | 换层 MT1→MT2 | (1,2)@MT2 | 423 | 24 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1440 | 换层 MT2→MT3 | (2,11)@MT3 | 423 | 24 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1456 | 开门(耗yellowKey×1) @(8, 2) | (8,2)@MT3 | 423 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1458 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血15 | (10,2)@MT3 | 408 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1460 | 回血+50 | (11,1)@MT3 | 458 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1476 | 换层 MT3→MT4 | (11,10)@MT4 | 458 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1495 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血38 | (9,5)@MT4 | 420 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1497 | 开门(耗yellowKey×1) @(10, 5) | (10,5)@MT4 | 420 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1499 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血116 | (10,3)@MT4 | 304 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1501 | 拿钥匙 yellowKey×1 | (9,2)@MT4 | 304 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1503 | 回血+200 | (11,2)@MT4 | 504 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1522 | 换层 MT4→MT5 | (2,11)@MT5 | 504 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1545 | 换层 MT5→MT6 | (1,2)@MT6 | 504 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1565 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT6 | 504 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1568 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血15 | (11,4)@MT6 | 489 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1572 | 回血+50 | (8,3)@MT6 | 539 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1599 | 换层 MT6→MT7 | (11,10)@MT7 | 539 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1610 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT7 | 539 | 24 | 23 | {'blueKey': 1} |
| 1613 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血15 | (5,9)@MT7 | 524 | 24 | 23 | {'blueKey': 1} |
| 1614 | 拿钥匙 yellowKey×1 | (5,10)@MT7 | 524 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1615 | 拿钥匙 yellowKey×1 | (5,11)@MT7 | 524 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1629 | 换层 MT7→MT8 | (1,2)@MT8 | 524 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1635 | 换层 MT8→MT9 | (6,2)@MT9 | 524 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1646 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 524 | 24 | 23 | {'yellowKey': 1, 'blueKey': 1} |
| 1650 | 开门(耗blueKey×1) @(4, 11) | (4,11)@MT9 | 524 | 24 | 23 | {'yellowKey': 1} |
| 1653 | 回血+50 | (2,10)@MT9 | 574 | 24 | 23 | {'yellowKey': 1} |
| 1672 | 换层 MT9→MT8 | (6,2)@MT8 | 574 | 24 | 23 | {'yellowKey': 1} |
| 1680 | 换层 MT8→MT7 | (1,2)@MT7 | 574 | 24 | 23 | {'yellowKey': 1} |
| 1699 | 换层 MT7→MT6 | (11,10)@MT6 | 574 | 24 | 23 | {'yellowKey': 1} |
| 1718 | 换层 MT6→MT5 | (1,2)@MT5 | 574 | 24 | 23 | {'yellowKey': 1} |
| 1741 | 换层 MT5→MT4 | (1,10)@MT4 | 574 | 24 | 23 | {'yellowKey': 1} |
| 1758 | 换层 MT4→MT3 | (10,11)@MT3 | 574 | 24 | 23 | {'yellowKey': 1} |
| 1774 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 574 | 24 | 23 | {} |
| 1776 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血27 | (1,3)@MT3 | 547 | 24 | 23 | {} |
| 1778 | 回血+50 | (2,2)@MT3 | 597 | 24 | 23 | {} |
| 1779 | 拿防御宝石+1DEF @(2, 1)  | (2,1)@MT3 | 597 | 24 | 24 | {} |
| 1780 | 拿钥匙 yellowKey×1 | (1,1)@MT3 | 597 | 24 | 24 | {'yellowKey': 1} |
| 1785 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 597 | 24 | 24 | {} |
| 1787 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (1,7)@MT3 | 561 | 24 | 24 | {} |
| 1789 | 回血+50 | (1,9)@MT3 | 611 | 24 | 24 | {} |
| 1791 | 拿钥匙 yellowKey×1 | (2,8)@MT3 | 611 | 24 | 24 | {'yellowKey': 1} |
| 1792 | 拿攻击宝石+1ATK @(2, 9)  | (2,9)@MT3 | 611 | 25 | 24 | {'yellowKey': 1} |
| 1813 | 换层 MT3→MT4 | (11,10)@MT4 | 611 | 25 | 24 | {'yellowKey': 1} |
| 1830 | 换层 MT4→MT5 | (2,11)@MT5 | 611 | 25 | 24 | {'yellowKey': 1} |
| 1853 | 换层 MT5→MT6 | (1,2)@MT6 | 611 | 25 | 24 | {'yellowKey': 1} |
| 1873 | 开门(耗yellowKey×1) @(1, 11) | (1,11)@MT6 | 611 | 25 | 24 | {} |
| 1876 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血24 | (1,8)@MT6 | 587 | 25 | 24 | {} |
| 1880 | 拿防御宝石+1DEF @(4, 9)  | (4,9)@MT6 | 587 | 25 | 25 | {} |
| 1903 | 换层 MT6→MT7 | (11,10)@MT7 | 587 | 25 | 25 | {} |
| 1922 | 换层 MT7→MT8 | (1,2)@MT8 | 587 | 25 | 25 | {} |
| 1928 | 换层 MT8→MT9 | (6,2)@MT9 | 587 | 25 | 25 | {} |
| 1943 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血34 | (5,10)@MT9 | 553 | 25 | 25 | {} |
| 1948 | 换层 MT9→MT10 | (1,10)@MT10 | 553 | 25 | 25 | {} |

### β=1　到达 MT10 落点=(1, 10)　终态 MT10(1,6) HP=606 ATK=24 DEF=24 持钥={}　封板对账=✅一致
- 红钥匙：**全程未拿红钥匙**　|　MT8 def22 卫兵杀了 0/2　|　队长可杀(atk>15)=是
- 余量：搜索看到 HP−D=131（D 含红门免费+埋伏漏算）　vs　满房重估 HP−891=**-285**

| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |
|----|------|------|----|----|-----|---------|
| 0 | 起点（开局噩梦后首个自由态 MT3 入口） | (2,11)@MT3 | 400 | 10 | 10 | {} |
| 11 | 拿钥匙 blueKey×1 | (5,3)@MT3 | 400 | 10 | 10 | {'blueKey': 1} |
| 12 | 拿钥匙 yellowKey×1 | (4,3)@MT3 | 400 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 13 | 回血+200 | (4,2)@MT3 | 600 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 14 | 拿钥匙 yellowKey×1 | (4,1)@MT3 | 600 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 15 | 回血+200 | (5,1)@MT3 | 800 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 16 | 拿钥匙 yellowKey×1 | (5,2)@MT3 | 800 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 17 | 回血+200 | (6,2)@MT3 | 1000 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 18 | 拿钥匙 yellowKey×1 | (6,1)@MT3 | 1000 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 20 | 拿钥匙 yellowKey×1 | (6,3)@MT3 | 1000 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 25 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,5)@MT3 | 976 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 31 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (8,10)@MT3 | 926 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 33 | 开门(耗yellowKey×1) @(8, 11) | (8,11)@MT3 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 36 | 换层 MT3→MT4 | (11,10)@MT4 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 38 | 开门(耗yellowKey×1) @(11, 9) | (11,9)@MT4 | 926 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 48 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (3,7)@MT4 | 902 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 50 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 51 | 开门(耗yellowKey×1) @(1, 7) | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 55 | 换层 MT4→MT5 | (2,11)@MT5 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 62 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (6,8)@MT5 | 828 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 65 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,6)@MT5 | 804 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 70 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (11,7)@MT5 | 754 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 75 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT5 | 754 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 82 | 拿铁剑+10ATK @(11, 11)  | (11,11)@MT5 | 754 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 97 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,2)@MT5 | 734 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 99 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT5 | 734 | 20 | 10 | {'blueKey': 1} |
| 102 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,2)@MT5 | 726 | 20 | 10 | {'blueKey': 1} |
| 103 | 拿钥匙 yellowKey×1 | (9,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 104 | 拿钥匙 yellowKey×1 | (8,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 105 | 拿钥匙 yellowKey×1 | (8,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 106 | 拿钥匙 yellowKey×1 | (9,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 131 | 换层 MT5→MT4 | (1,10)@MT4 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 142 | 开门(耗yellowKey×1) @(8, 7) | (8,7)@MT4 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 144 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (8,9)@MT4 | 638 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 146 | 拿攻击宝石+1ATK @(7, 10)  | (7,10)@MT4 | 638 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 148 | 回血+50 | (9,10)@MT4 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 159 | 换层 MT4→MT3 | (10,11)@MT3 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 180 | 换层 MT3→MT2 | (1,10)@MT2 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 189 | 换层 MT2→MT1 | (2,1)@MT1 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 217 | 开门(耗yellowKey×1) @(5, 3) | (5,3)@MT1 | 688 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 221 | 回血+50 | (1,3)@MT1 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 236 | 开门(耗yellowKey×1) @(10, 8) | (10,8)@MT1 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 238 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (10,10)@MT1 | 710 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 239 | 回血+200 | (10,11)@MT1 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 260 | 换层 MT1→MT2 | (1,2)@MT2 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 269 | 换层 MT2→MT3 | (2,11)@MT3 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 290 | 换层 MT3→MT4 | (11,10)@MT4 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 301 | 开门(耗yellowKey×1) @(4, 7) | (4,7)@MT4 | 910 | 21 | 10 | {'blueKey': 1} |
| 303 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,9)@MT4 | 882 | 21 | 10 | {'blueKey': 1} |
| 305 | 拿钥匙 yellowKey×1 | (5,10)@MT4 | 882 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 306 | 拿钥匙 yellowKey×1 | (5,11)@MT4 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 318 | 换层 MT4→MT5 | (2,11)@MT5 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 329 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (6,4)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 331 | 拿钥匙 yellowKey×1 | (6,2)@MT5 | 854 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 333 | 开门(耗yellowKey×1) @(6, 1) | (6,1)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 335 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,1)@MT5 | 834 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 338 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 339 | 开门(耗yellowKey×1) @(3, 3) | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 341 | 开门(耗yellowKey×1) @(4, 3) | (4,3)@MT5 | 806 | 21 | 10 | {'blueKey': 1} |
| 344 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,6)@MT5 | 778 | 21 | 10 | {'blueKey': 1} |
| 347 | 拿钥匙 yellowKey×1 | (1,6)@MT5 | 778 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 348 | 拿钥匙 yellowKey×1 | (1,5)@MT5 | 778 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 360 | 换层 MT5→MT6 | (1,2)@MT6 | 778 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 366 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (3,6)@MT6 | 758 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 367 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT6 | 670 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 369 | 拿钥匙 yellowKey×1 | (6,6)@MT6 | 670 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 372 | 开门(耗yellowKey×1) @(6, 8) | (6,8)@MT6 | 670 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 374 | 开门(耗yellowKey×1) @(7, 8) | (7,8)@MT6 | 670 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 377 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (9,9)@MT6 | 650 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 379 | 回血+50 | (9,11)@MT6 | 700 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 380 | 回血+50 | (8,11)@MT6 | 750 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 392 | 开门(耗yellowKey×1) @(6, 4) | (6,4)@MT6 | 750 | 21 | 10 | {'blueKey': 1} |
| 395 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,3)@MT6 | 730 | 21 | 10 | {'blueKey': 1} |
| 396 | 拿钥匙 yellowKey×1 | (4,2)@MT6 | 730 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 397 | 拿钥匙 yellowKey×1 | (4,1)@MT6 | 730 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 398 | 拿钥匙 yellowKey×1 | (3,1)@MT6 | 730 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 399 | 拿钥匙 yellowKey×1 | (3,2)@MT6 | 730 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 412 | 开门(耗yellowKey×1) @(9, 8) | (9,8)@MT6 | 730 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 415 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,9)@MT6 | 710 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 417 | 换层 MT6→MT7 | (11,10)@MT7 | 710 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 420 | 开门(耗yellowKey×1) @(11, 8) | (11,8)@MT7 | 710 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 429 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT7 | 622 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 431 | 开门(耗yellowKey×1) @(3, 6) | (3,6)@MT7 | 622 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 434 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT7 | 594 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 435 | 回血+50 | (3,2)@MT7 | 644 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 436 | 拿攻击宝石+1ATK @(3, 1)  | (3,1)@MT7 | 644 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 444 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT7 | 644 | 22 | 10 | {'blueKey': 1} |
| 447 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (5,9)@MT7 | 616 | 22 | 10 | {'blueKey': 1} |
| 448 | 拿钥匙 yellowKey×1 | (5,10)@MT7 | 616 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 449 | 拿钥匙 yellowKey×1 | (5,11)@MT7 | 616 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 457 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血210 | (2,6)@MT7 | 406 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 459 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 406 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 468 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血96 | (9,5)@MT7 | 310 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 470 | 回血+50 | (9,3)@MT7 | 360 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 471 | 拿钥匙 yellowKey×1 | (9,2)@MT7 | 360 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 472 | 拿钥匙 yellowKey×1 | (9,1)@MT7 | 360 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 490 | 换层 MT7→MT8 | (1,2)@MT8 | 360 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 493 | 开门(耗yellowKey×1) @(2, 1) | (2,1)@MT8 | 360 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 495 | 开门(耗yellowKey×1) @(3, 1) | (3,1)@MT8 | 360 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 500 | 开门(耗yellowKey×1) @(6, 2) | (6,2)@MT8 | 360 | 22 | 10 | {'blueKey': 1} |
| 503 | 拿钥匙 yellowKey×1 | (5,4)@MT8 | 360 | 22 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 504 | 拿钥匙 yellowKey×1 | (4,4)@MT8 | 360 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 505 | 拿钥匙 yellowKey×1 | (3,4)@MT8 | 360 | 22 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 518 | 开门(耗yellowKey×1) @(1, 2) | (1,2)@MT8 | 360 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 521 | 回血+50 | (1,5)@MT8 | 410 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 532 | 换层 MT8→MT9 | (6,2)@MT9 | 410 | 22 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 533 | 开门(耗blueKey×1) @(6, 2) | (6,2)@MT9 | 410 | 22 | 10 | {'yellowKey': 2} |
| 536 | 拿钥匙 yellowKey×1 | (7,4)@MT9 | 410 | 22 | 10 | {'yellowKey': 3} |
| 538 | 拿攻击宝石+1ATK @(6, 5)  | (6,5)@MT9 | 410 | 23 | 10 | {'yellowKey': 3} |
| 540 | 拿钥匙 yellowKey×1 | (5,4)@MT9 | 410 | 23 | 10 | {'yellowKey': 4} |
| 543 | 开门(耗yellowKey×1) @(7, 4) | (7,4)@MT9 | 410 | 23 | 10 | {'yellowKey': 3} |
| 545 | 开门(耗yellowKey×1) @(8, 4) | (8,4)@MT9 | 410 | 23 | 10 | {'yellowKey': 2} |
| 551 | 回血+50 | (11,1)@MT9 | 460 | 23 | 10 | {'yellowKey': 2} |
| 560 | 拿铁盾+10DEF @(9, 7)  | (9,7)@MT9 | 460 | 23 | 20 | {'yellowKey': 2} |
| 573 | 开门(耗yellowKey×1) @(5, 1) | (5,1)@MT9 | 460 | 23 | 20 | {'yellowKey': 1} |
| 585 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,2)@MT9 | 460 | 23 | 20 | {'yellowKey': 1} |
| 587 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (9,1)@MT9 | 460 | 23 | 20 | {'yellowKey': 1} |
| 598 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,6)@MT9 | 460 | 23 | 20 | {'yellowKey': 1} |
| 606 | 换层 MT9→MT8 | (6,2)@MT8 | 460 | 23 | 20 | {'yellowKey': 1} |
| 607 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (7,2)@MT8 | 460 | 23 | 20 | {'yellowKey': 1} |
| 620 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,6)@MT8 | 460 | 23 | 20 | {'yellowKey': 1} |
| 621 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,6)@MT8 | 460 | 23 | 20 | {'yellowKey': 1} |
| 622 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (4,6)@MT8 | 460 | 23 | 20 | {'yellowKey': 1} |
| 635 | 换层 MT8→MT9 | (6,2)@MT9 | 460 | 23 | 20 | {'yellowKey': 1} |
| 640 | 开门(耗yellowKey×1) @(5, 5) | (5,5)@MT9 | 460 | 23 | 20 | {} |
| 642 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血18 | (3,5)@MT9 | 442 | 23 | 20 | {} |
| 644 | 拿钥匙 yellowKey×1 | (2,4)@MT9 | 442 | 23 | 20 | {'yellowKey': 1} |
| 646 | 拿防御宝石+1DEF @(1, 5)  | (1,5)@MT9 | 442 | 23 | 21 | {'yellowKey': 1} |
| 657 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (7,10)@MT9 | 425 | 23 | 21 | {'yellowKey': 1} |
| 659 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 425 | 23 | 21 | {} |
| 661 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (9,11)@MT9 | 392 | 23 | 21 | {} |
| 663 | 回血+50 | (11,11)@MT9 | 442 | 23 | 21 | {} |
| 667 | 拿钥匙 yellowKey×1 | (9,9)@MT9 | 442 | 23 | 21 | {'yellowKey': 1} |
| 684 | 换层 MT9→MT8 | (6,2)@MT8 | 442 | 23 | 21 | {'yellowKey': 1} |
| 692 | 换层 MT8→MT7 | (1,2)@MT7 | 442 | 23 | 21 | {'yellowKey': 1} |
| 703 | 开门(耗yellowKey×1) @(7, 6) | (7,6)@MT7 | 442 | 23 | 21 | {} |
| 706 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,9)@MT7 | 442 | 23 | 21 | {} |
| 707 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (7,10)@MT7 | 409 | 23 | 21 | {} |
| 708 | 回血+200 | (7,11)@MT7 | 609 | 23 | 21 | {} |
| 716 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (9,7)@MT7 | 485 | 23 | 21 | {} |
| 718 | 回血+200 | (9,9)@MT7 | 685 | 23 | 21 | {} |
| 719 | 拿钥匙 yellowKey×1 | (9,10)@MT7 | 685 | 23 | 21 | {'yellowKey': 1} |
| 720 | 拿钥匙 yellowKey×1 | (9,11)@MT7 | 685 | 23 | 21 | {'yellowKey': 2} |
| 734 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 685 | 23 | 21 | {'yellowKey': 1} |
| 738 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (1,10)@MT7 | 685 | 23 | 21 | {'yellowKey': 1} |
| 757 | 换层 MT7→MT6 | (11,10)@MT6 | 685 | 23 | 21 | {'yellowKey': 1} |
| 776 | 换层 MT6→MT5 | (1,2)@MT5 | 685 | 23 | 21 | {'yellowKey': 1} |
| 786 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (2,7)@MT5 | 561 | 23 | 21 | {'yellowKey': 1} |
| 788 | 拿钥匙 yellowKey×1 | (2,9)@MT5 | 561 | 23 | 21 | {'yellowKey': 2} |
| 789 | 回血+50 | (3,9)@MT5 | 611 | 23 | 21 | {'yellowKey': 2} |
| 793 | 拿防御宝石+1DEF @(1, 9)  | (1,9)@MT5 | 611 | 23 | 22 | {'yellowKey': 2} |
| 807 | 换层 MT5→MT6 | (1,2)@MT6 | 611 | 23 | 22 | {'yellowKey': 2} |
| 822 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (7,1)@MT6 | 581 | 23 | 22 | {'yellowKey': 2} |
| 824 | 拿钥匙 yellowKey×1 | (9,1)@MT6 | 581 | 23 | 22 | {'yellowKey': 3} |
| 825 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,1)@MT6 | 581 | 23 | 22 | {'yellowKey': 3} |
| 844 | 换层 MT6→MT5 | (1,2)@MT5 | 581 | 23 | 22 | {'yellowKey': 3} |
| 871 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,2)@MT5 | 581 | 23 | 22 | {'yellowKey': 3} |
| 895 | 换层 MT5→MT4 | (1,10)@MT4 | 581 | 23 | 22 | {'yellowKey': 3} |
| 905 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,10)@MT4 | 581 | 23 | 22 | {'yellowKey': 3} |
| 906 | 拿钥匙 yellowKey×1 | (3,11)@MT4 | 581 | 23 | 22 | {'yellowKey': 4} |
| 918 | 换层 MT4→MT5 | (2,11)@MT5 | 581 | 23 | 22 | {'yellowKey': 4} |
| 941 | 换层 MT5→MT6 | (1,2)@MT6 | 581 | 23 | 22 | {'yellowKey': 4} |
| 960 | 换层 MT6→MT7 | (11,10)@MT7 | 581 | 23 | 22 | {'yellowKey': 4} |
| 980 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,11)@MT7 | 581 | 23 | 22 | {'yellowKey': 4} |
| 982 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,10)@MT7 | 581 | 23 | 22 | {'yellowKey': 4} |
| 1005 | 换层 MT7→MT6 | (11,10)@MT6 | 581 | 23 | 22 | {'yellowKey': 4} |
| 1024 | 换层 MT6→MT5 | (1,2)@MT5 | 581 | 23 | 22 | {'yellowKey': 4} |
| 1047 | 换层 MT5→MT4 | (1,10)@MT4 | 581 | 23 | 22 | {'yellowKey': 4} |
| 1059 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (4,11)@MT4 | 581 | 23 | 22 | {'yellowKey': 4} |
| 1069 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (2,5)@MT4 | 551 | 23 | 22 | {'yellowKey': 4} |
| 1070 | 开门(耗yellowKey×1) @(2, 5) | (2,5)@MT4 | 551 | 23 | 22 | {'yellowKey': 3} |
| 1074 | 回血+50 | (1,2)@MT4 | 601 | 23 | 22 | {'yellowKey': 3} |
| 1076 | 拿钥匙 blueKey×1 | (2,1)@MT4 | 601 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1078 | 拿钥匙 yellowKey×1 | (3,2)@MT4 | 601 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1096 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,11)@MT4 | 601 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1107 | 换层 MT4→MT3 | (10,11)@MT3 | 601 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1120 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (3,5)@MT3 | 585 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1132 | 换层 MT3→MT2 | (1,10)@MT2 | 585 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1141 | 换层 MT2→MT1 | (2,1)@MT1 | 585 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1162 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (9,11)@MT1 | 585 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1184 | 换层 MT1→MT2 | (1,2)@MT2 | 585 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1193 | 换层 MT2→MT3 | (2,11)@MT3 | 585 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1209 | 开门(耗yellowKey×1) @(8, 2) | (8,2)@MT3 | 585 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1211 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (10,2)@MT3 | 569 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1213 | 回血+50 | (11,1)@MT3 | 619 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1224 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT3 | 619 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1226 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (10,8)@MT3 | 589 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1227 | 拿钥匙 yellowKey×1 | (11,8)@MT3 | 589 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1228 | 回血+50 | (11,7)@MT3 | 639 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1248 | 换层 MT3→MT2 | (1,10)@MT2 | 639 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1257 | 换层 MT2→MT1 | (2,1)@MT1 | 639 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1278 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,11)@MT1 | 639 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1300 | 换层 MT1→MT2 | (1,2)@MT2 | 639 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1309 | 换层 MT2→MT3 | (2,11)@MT3 | 639 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1323 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 639 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1325 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (1,3)@MT3 | 609 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1327 | 回血+50 | (2,2)@MT3 | 659 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1328 | 拿防御宝石+1DEF @(2, 1)  | (2,1)@MT3 | 659 | 23 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1329 | 拿钥匙 yellowKey×1 | (1,1)@MT3 | 659 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1349 | 换层 MT3→MT4 | (11,10)@MT4 | 659 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1366 | 换层 MT4→MT5 | (2,11)@MT5 | 659 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1389 | 换层 MT5→MT6 | (1,2)@MT6 | 659 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1408 | 换层 MT6→MT7 | (11,10)@MT7 | 659 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1427 | 换层 MT7→MT8 | (1,2)@MT8 | 659 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1433 | 换层 MT8→MT9 | (6,2)@MT9 | 659 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1444 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 659 | 23 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1448 | 开门(耗blueKey×1) @(4, 11) | (4,11)@MT9 | 659 | 23 | 23 | {'yellowKey': 2} |
| 1451 | 回血+50 | (2,10)@MT9 | 709 | 23 | 23 | {'yellowKey': 2} |
| 1470 | 换层 MT9→MT8 | (6,2)@MT8 | 709 | 23 | 23 | {'yellowKey': 2} |
| 1478 | 换层 MT8→MT7 | (1,2)@MT7 | 709 | 23 | 23 | {'yellowKey': 2} |
| 1493 | 开门(耗yellowKey×1) @(11, 6) | (11,6)@MT7 | 709 | 23 | 23 | {'yellowKey': 1} |
| 1496 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,3)@MT7 | 709 | 23 | 23 | {'yellowKey': 1} |
| 1497 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (11,2)@MT7 | 709 | 23 | 23 | {'yellowKey': 1} |
| 1506 | 换层 MT7→MT6 | (11,10)@MT6 | 709 | 23 | 23 | {'yellowKey': 1} |
| 1526 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT6 | 709 | 23 | 23 | {} |
| 1529 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血15 | (11,4)@MT6 | 694 | 23 | 23 | {} |
| 1533 | 回血+50 | (8,3)@MT6 | 744 | 23 | 23 | {} |
| 1560 | 换层 MT6→MT7 | (11,10)@MT7 | 744 | 23 | 23 | {} |
| 1579 | 换层 MT7→MT8 | (1,2)@MT8 | 744 | 23 | 23 | {} |
| 1585 | 换层 MT8→MT9 | (6,2)@MT9 | 744 | 23 | 23 | {} |
| 1589 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血38 | (3,1)@MT9 | 706 | 23 | 23 | {} |
| 1591 | 拿钥匙 yellowKey×1 | (2,2)@MT9 | 706 | 23 | 23 | {'yellowKey': 1} |
| 1596 | 换层 MT9→MT8 | (6,2)@MT8 | 706 | 23 | 23 | {'yellowKey': 1} |
| 1604 | 换层 MT8→MT7 | (1,2)@MT7 | 706 | 23 | 23 | {'yellowKey': 1} |
| 1623 | 换层 MT7→MT6 | (11,10)@MT6 | 706 | 23 | 23 | {'yellowKey': 1} |
| 1642 | 换层 MT6→MT5 | (1,2)@MT5 | 706 | 23 | 23 | {'yellowKey': 1} |
| 1665 | 换层 MT5→MT4 | (1,10)@MT4 | 706 | 23 | 23 | {'yellowKey': 1} |
| 1682 | 换层 MT4→MT3 | (10,11)@MT3 | 706 | 23 | 23 | {'yellowKey': 1} |
| 1698 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 706 | 23 | 23 | {} |
| 1700 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血38 | (1,7)@MT3 | 668 | 23 | 23 | {} |
| 1702 | 回血+50 | (1,9)@MT3 | 718 | 23 | 23 | {} |
| 1704 | 拿钥匙 yellowKey×1 | (2,8)@MT3 | 718 | 23 | 23 | {'yellowKey': 1} |
| 1705 | 拿攻击宝石+1ATK @(2, 9)  | (2,9)@MT3 | 718 | 24 | 23 | {'yellowKey': 1} |
| 1726 | 换层 MT3→MT4 | (11,10)@MT4 | 718 | 24 | 23 | {'yellowKey': 1} |
| 1743 | 换层 MT4→MT5 | (2,11)@MT5 | 718 | 24 | 23 | {'yellowKey': 1} |
| 1766 | 换层 MT5→MT6 | (1,2)@MT6 | 718 | 24 | 23 | {'yellowKey': 1} |
| 1785 | 换层 MT6→MT7 | (11,10)@MT7 | 718 | 24 | 23 | {'yellowKey': 1} |
| 1804 | 换层 MT7→MT8 | (1,2)@MT8 | 718 | 24 | 23 | {'yellowKey': 1} |
| 1810 | 换层 MT8→MT9 | (6,2)@MT9 | 718 | 24 | 23 | {'yellowKey': 1} |
| 1825 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血38 | (5,10)@MT9 | 680 | 24 | 23 | {'yellowKey': 1} |
| 1830 | 换层 MT9→MT10 | (1,10)@MT10 | 680 | 24 | 23 | {'yellowKey': 1} |
| 1831 | 开门(耗yellowKey×1) @(1, 10) | (1,10)@MT10 | 680 | 24 | 23 | {} |
| 1837 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血38 | (3,6)@MT10 | 642 | 24 | 23 | {} |
| 1838 | 拿防御宝石+1DEF @(2, 6)  | (2,6)@MT10 | 642 | 24 | 24 | {} |
| 1845 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (1,6)@MT10 | 606 | 24 | 24 | {} |

### β=2　到达 MT10 落点=(1, 10)　终态 MT10(1,10) HP=394 ATK=25 DEF=24 持钥={'yellowKey': 1}　封板对账=✅一致
- 红钥匙：**全程未拿红钥匙**　|　MT8 def22 卫兵杀了 0/2　|　队长可杀(atk>15)=是
- 余量：搜索看到 HP−D=1（D 含红门免费+埋伏漏算）　vs　满房重估 HP−809=**-415**

| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |
|----|------|------|----|----|-----|---------|
| 0 | 起点（开局噩梦后首个自由态 MT3 入口） | (2,11)@MT3 | 400 | 10 | 10 | {} |
| 11 | 拿钥匙 blueKey×1 | (5,3)@MT3 | 400 | 10 | 10 | {'blueKey': 1} |
| 12 | 拿钥匙 yellowKey×1 | (4,3)@MT3 | 400 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 13 | 回血+200 | (4,2)@MT3 | 600 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 14 | 拿钥匙 yellowKey×1 | (4,1)@MT3 | 600 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 15 | 回血+200 | (5,1)@MT3 | 800 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 16 | 拿钥匙 yellowKey×1 | (5,2)@MT3 | 800 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 17 | 回血+200 | (6,2)@MT3 | 1000 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 18 | 拿钥匙 yellowKey×1 | (6,1)@MT3 | 1000 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 20 | 拿钥匙 yellowKey×1 | (6,3)@MT3 | 1000 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 25 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,5)@MT3 | 976 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 31 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (8,10)@MT3 | 926 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 33 | 开门(耗yellowKey×1) @(8, 11) | (8,11)@MT3 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 36 | 换层 MT3→MT4 | (11,10)@MT4 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 38 | 开门(耗yellowKey×1) @(11, 9) | (11,9)@MT4 | 926 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 48 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (3,7)@MT4 | 902 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 50 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 51 | 开门(耗yellowKey×1) @(1, 7) | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 55 | 换层 MT4→MT5 | (2,11)@MT5 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 62 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (6,8)@MT5 | 828 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 65 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,6)@MT5 | 804 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 70 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (11,7)@MT5 | 754 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 75 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT5 | 754 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 82 | 拿铁剑+10ATK @(11, 11)  | (11,11)@MT5 | 754 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 97 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,2)@MT5 | 734 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 99 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT5 | 734 | 20 | 10 | {'blueKey': 1} |
| 102 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,2)@MT5 | 726 | 20 | 10 | {'blueKey': 1} |
| 103 | 拿钥匙 yellowKey×1 | (9,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 104 | 拿钥匙 yellowKey×1 | (8,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 105 | 拿钥匙 yellowKey×1 | (8,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 106 | 拿钥匙 yellowKey×1 | (9,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 131 | 换层 MT5→MT4 | (1,10)@MT4 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 142 | 开门(耗yellowKey×1) @(8, 7) | (8,7)@MT4 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 144 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (8,9)@MT4 | 638 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 146 | 拿攻击宝石+1ATK @(7, 10)  | (7,10)@MT4 | 638 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 148 | 回血+50 | (9,10)@MT4 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 159 | 换层 MT4→MT3 | (10,11)@MT3 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 180 | 换层 MT3→MT2 | (1,10)@MT2 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 189 | 换层 MT2→MT1 | (2,1)@MT1 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 217 | 开门(耗yellowKey×1) @(5, 3) | (5,3)@MT1 | 688 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 221 | 回血+50 | (1,3)@MT1 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 236 | 开门(耗yellowKey×1) @(10, 8) | (10,8)@MT1 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 238 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (10,10)@MT1 | 710 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 239 | 回血+200 | (10,11)@MT1 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 260 | 换层 MT1→MT2 | (1,2)@MT2 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 269 | 换层 MT2→MT3 | (2,11)@MT3 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 290 | 换层 MT3→MT4 | (11,10)@MT4 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 301 | 开门(耗yellowKey×1) @(4, 7) | (4,7)@MT4 | 910 | 21 | 10 | {'blueKey': 1} |
| 303 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,9)@MT4 | 882 | 21 | 10 | {'blueKey': 1} |
| 305 | 拿钥匙 yellowKey×1 | (5,10)@MT4 | 882 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 306 | 拿钥匙 yellowKey×1 | (5,11)@MT4 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 318 | 换层 MT4→MT5 | (2,11)@MT5 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 329 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (6,4)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 331 | 拿钥匙 yellowKey×1 | (6,2)@MT5 | 854 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 333 | 开门(耗yellowKey×1) @(6, 1) | (6,1)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 335 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,1)@MT5 | 834 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 338 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 339 | 开门(耗yellowKey×1) @(3, 3) | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 343 | 换层 MT5→MT6 | (1,2)@MT6 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 349 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (3,6)@MT6 | 786 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 350 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT6 | 698 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 352 | 拿钥匙 yellowKey×1 | (6,6)@MT6 | 698 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 355 | 开门(耗yellowKey×1) @(6, 4) | (6,4)@MT6 | 698 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 358 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,3)@MT6 | 678 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 359 | 拿钥匙 yellowKey×1 | (4,2)@MT6 | 678 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 360 | 拿钥匙 yellowKey×1 | (4,1)@MT6 | 678 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 361 | 拿钥匙 yellowKey×1 | (3,1)@MT6 | 678 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 362 | 拿钥匙 yellowKey×1 | (3,2)@MT6 | 678 | 21 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 372 | 开门(耗yellowKey×1) @(6, 8) | (6,8)@MT6 | 678 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 374 | 开门(耗yellowKey×1) @(7, 8) | (7,8)@MT6 | 678 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 377 | 开门(耗yellowKey×1) @(9, 8) | (9,8)@MT6 | 678 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 380 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,9)@MT6 | 658 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 384 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (9,9)@MT6 | 638 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 386 | 回血+50 | (9,11)@MT6 | 688 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 387 | 回血+50 | (8,11)@MT6 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 396 | 换层 MT6→MT7 | (11,10)@MT7 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 399 | 开门(耗yellowKey×1) @(11, 8) | (11,8)@MT7 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 408 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT7 | 650 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 410 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血252 | (2,6)@MT7 | 398 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 412 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 398 | 21 | 10 | {'blueKey': 1} |
| 421 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血96 | (9,5)@MT7 | 302 | 21 | 10 | {'blueKey': 1} |
| 423 | 回血+50 | (9,3)@MT7 | 352 | 21 | 10 | {'blueKey': 1} |
| 424 | 拿钥匙 yellowKey×1 | (9,2)@MT7 | 352 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 425 | 拿钥匙 yellowKey×1 | (9,1)@MT7 | 352 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 431 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血252 | (9,7)@MT7 | 100 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 433 | 回血+200 | (9,9)@MT7 | 300 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 434 | 拿钥匙 yellowKey×1 | (9,10)@MT7 | 300 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 435 | 拿钥匙 yellowKey×1 | (9,11)@MT7 | 300 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 449 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 300 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 453 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (1,10)@MT7 | 292 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 462 | 换层 MT7→MT8 | (1,2)@MT8 | 292 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 465 | 开门(耗yellowKey×1) @(2, 1) | (2,1)@MT8 | 292 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 467 | 开门(耗yellowKey×1) @(3, 1) | (3,1)@MT8 | 292 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 472 | 开门(耗yellowKey×1) @(6, 2) | (6,2)@MT8 | 292 | 21 | 10 | {'blueKey': 1} |
| 475 | 拿钥匙 yellowKey×1 | (5,4)@MT8 | 292 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 476 | 拿钥匙 yellowKey×1 | (4,4)@MT8 | 292 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 477 | 拿钥匙 yellowKey×1 | (3,4)@MT8 | 292 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 490 | 开门(耗yellowKey×1) @(1, 2) | (1,2)@MT8 | 292 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 493 | 回血+50 | (1,5)@MT8 | 342 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 504 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (7,2)@MT8 | 334 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 508 | 换层 MT8→MT9 | (6,2)@MT9 | 334 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 511 | 开门(耗yellowKey×1) @(7, 1) | (7,1)@MT9 | 334 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 513 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,1)@MT9 | 326 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 515 | 回血+50 | (11,1)@MT9 | 376 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 517 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (10,2)@MT9 | 368 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 526 | 拿铁盾+10DEF @(9, 7)  | (9,7)@MT9 | 368 | 21 | 20 | {'yellowKey': 1, 'blueKey': 1} |
| 543 | 换层 MT9→MT8 | (6,2)@MT8 | 368 | 21 | 20 | {'yellowKey': 1, 'blueKey': 1} |
| 551 | 换层 MT8→MT7 | (1,2)@MT7 | 368 | 21 | 20 | {'yellowKey': 1, 'blueKey': 1} |
| 558 | 开门(耗yellowKey×1) @(3, 6) | (3,6)@MT7 | 368 | 21 | 20 | {'blueKey': 1} |
| 566 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,11)@MT7 | 368 | 21 | 20 | {'blueKey': 1} |
| 568 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,10)@MT7 | 368 | 21 | 20 | {'blueKey': 1} |
| 581 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血18 | (3,3)@MT7 | 350 | 21 | 20 | {'blueKey': 1} |
| 582 | 回血+50 | (3,2)@MT7 | 400 | 21 | 20 | {'blueKey': 1} |
| 583 | 拿攻击宝石+1ATK @(3, 1)  | (3,1)@MT7 | 400 | 22 | 20 | {'blueKey': 1} |
| 595 | 换层 MT7→MT8 | (1,2)@MT8 | 400 | 22 | 20 | {'blueKey': 1} |
| 600 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,6)@MT8 | 400 | 22 | 20 | {'blueKey': 1} |
| 601 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,6)@MT8 | 400 | 22 | 20 | {'blueKey': 1} |
| 602 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (4,6)@MT8 | 400 | 22 | 20 | {'blueKey': 1} |
| 615 | 换层 MT8→MT9 | (6,2)@MT9 | 400 | 22 | 20 | {'blueKey': 1} |
| 616 | 开门(耗blueKey×1) @(6, 2) | (6,2)@MT9 | 400 | 22 | 20 | {} |
| 619 | 拿钥匙 yellowKey×1 | (5,4)@MT9 | 400 | 22 | 20 | {'yellowKey': 1} |
| 621 | 拿钥匙 yellowKey×1 | (7,4)@MT9 | 400 | 22 | 20 | {'yellowKey': 2} |
| 623 | 拿攻击宝石+1ATK @(6, 5)  | (6,5)@MT9 | 400 | 23 | 20 | {'yellowKey': 2} |
| 629 | 开门(耗yellowKey×1) @(5, 1) | (5,1)@MT9 | 400 | 23 | 20 | {'yellowKey': 1} |
| 636 | 开门(耗yellowKey×1) @(5, 5) | (5,5)@MT9 | 400 | 23 | 20 | {} |
| 639 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,6)@MT9 | 400 | 23 | 20 | {} |
| 644 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血18 | (3,5)@MT9 | 382 | 23 | 20 | {} |
| 646 | 拿钥匙 yellowKey×1 | (2,4)@MT9 | 382 | 23 | 20 | {'yellowKey': 1} |
| 648 | 拿防御宝石+1DEF @(1, 5)  | (1,5)@MT9 | 382 | 23 | 21 | {'yellowKey': 1} |
| 659 | 换层 MT9→MT8 | (6,2)@MT8 | 382 | 23 | 21 | {'yellowKey': 1} |
| 667 | 换层 MT8→MT7 | (1,2)@MT7 | 382 | 23 | 21 | {'yellowKey': 1} |
| 678 | 开门(耗yellowKey×1) @(7, 6) | (7,6)@MT7 | 382 | 23 | 21 | {} |
| 681 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,9)@MT7 | 382 | 23 | 21 | {} |
| 682 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (7,10)@MT7 | 349 | 23 | 21 | {} |
| 683 | 回血+200 | (7,11)@MT7 | 549 | 23 | 21 | {} |
| 697 | 换层 MT7→MT6 | (11,10)@MT6 | 549 | 23 | 21 | {} |
| 716 | 换层 MT6→MT5 | (1,2)@MT5 | 549 | 23 | 21 | {} |
| 739 | 换层 MT5→MT4 | (1,10)@MT4 | 549 | 23 | 21 | {} |
| 749 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,10)@MT4 | 549 | 23 | 21 | {} |
| 750 | 拿钥匙 yellowKey×1 | (3,11)@MT4 | 549 | 23 | 21 | {'yellowKey': 1} |
| 751 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (4,11)@MT4 | 549 | 23 | 21 | {'yellowKey': 1} |
| 762 | 换层 MT4→MT5 | (2,11)@MT5 | 549 | 23 | 21 | {'yellowKey': 1} |
| 785 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,2)@MT5 | 549 | 23 | 21 | {'yellowKey': 1} |
| 813 | 换层 MT5→MT6 | (1,2)@MT6 | 549 | 23 | 21 | {'yellowKey': 1} |
| 832 | 换层 MT6→MT7 | (11,10)@MT7 | 549 | 23 | 21 | {'yellowKey': 1} |
| 851 | 换层 MT7→MT8 | (1,2)@MT8 | 549 | 23 | 21 | {'yellowKey': 1} |
| 857 | 换层 MT8→MT9 | (6,2)@MT9 | 549 | 23 | 21 | {'yellowKey': 1} |
| 866 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (7,10)@MT9 | 532 | 23 | 21 | {'yellowKey': 1} |
| 868 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 532 | 23 | 21 | {} |
| 870 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (9,11)@MT9 | 499 | 23 | 21 | {} |
| 872 | 回血+50 | (11,11)@MT9 | 549 | 23 | 21 | {} |
| 876 | 拿钥匙 yellowKey×1 | (9,9)@MT9 | 549 | 23 | 21 | {'yellowKey': 1} |
| 893 | 换层 MT9→MT8 | (6,2)@MT8 | 549 | 23 | 21 | {'yellowKey': 1} |
| 901 | 换层 MT8→MT7 | (1,2)@MT7 | 549 | 23 | 21 | {'yellowKey': 1} |
| 920 | 换层 MT7→MT6 | (11,10)@MT6 | 549 | 23 | 21 | {'yellowKey': 1} |
| 939 | 换层 MT6→MT5 | (1,2)@MT5 | 549 | 23 | 21 | {'yellowKey': 1} |
| 962 | 换层 MT5→MT4 | (1,10)@MT4 | 549 | 23 | 21 | {'yellowKey': 1} |
| 979 | 换层 MT4→MT3 | (10,11)@MT3 | 549 | 23 | 21 | {'yellowKey': 1} |
| 991 | 开门(耗yellowKey×1) @(8, 2) | (8,2)@MT3 | 549 | 23 | 21 | {} |
| 993 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (10,2)@MT3 | 532 | 23 | 21 | {} |
| 995 | 回血+50 | (11,1)@MT3 | 582 | 23 | 21 | {} |
| 1015 | 换层 MT3→MT2 | (1,10)@MT2 | 582 | 23 | 21 | {} |
| 1024 | 换层 MT2→MT1 | (2,1)@MT1 | 582 | 23 | 21 | {} |
| 1045 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (9,11)@MT1 | 582 | 23 | 21 | {} |
| 1047 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,11)@MT1 | 582 | 23 | 21 | {} |
| 1069 | 换层 MT1→MT2 | (1,2)@MT2 | 582 | 23 | 21 | {} |
| 1078 | 换层 MT2→MT3 | (2,11)@MT3 | 582 | 23 | 21 | {} |
| 1099 | 换层 MT3→MT4 | (11,10)@MT4 | 582 | 23 | 21 | {} |
| 1116 | 换层 MT4→MT5 | (2,11)@MT5 | 582 | 23 | 21 | {} |
| 1139 | 换层 MT5→MT6 | (1,2)@MT6 | 582 | 23 | 21 | {} |
| 1158 | 换层 MT6→MT7 | (11,10)@MT7 | 582 | 23 | 21 | {} |
| 1177 | 换层 MT7→MT8 | (1,2)@MT8 | 582 | 23 | 21 | {} |
| 1183 | 换层 MT8→MT9 | (6,2)@MT9 | 582 | 23 | 21 | {} |
| 1187 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血42 | (3,1)@MT9 | 540 | 23 | 21 | {} |
| 1189 | 拿钥匙 yellowKey×1 | (2,2)@MT9 | 540 | 23 | 21 | {'yellowKey': 1} |
| 1194 | 换层 MT9→MT8 | (6,2)@MT8 | 540 | 23 | 21 | {'yellowKey': 1} |
| 1202 | 换层 MT8→MT7 | (1,2)@MT7 | 540 | 23 | 21 | {'yellowKey': 1} |
| 1211 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT7 | 540 | 23 | 21 | {} |
| 1214 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (5,9)@MT7 | 523 | 23 | 21 | {} |
| 1215 | 拿钥匙 yellowKey×1 | (5,10)@MT7 | 523 | 23 | 21 | {'yellowKey': 1} |
| 1216 | 拿钥匙 yellowKey×1 | (5,11)@MT7 | 523 | 23 | 21 | {'yellowKey': 2} |
| 1228 | 开门(耗yellowKey×1) @(11, 6) | (11,6)@MT7 | 523 | 23 | 21 | {'yellowKey': 1} |
| 1231 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,3)@MT7 | 523 | 23 | 21 | {'yellowKey': 1} |
| 1232 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (11,2)@MT7 | 523 | 23 | 21 | {'yellowKey': 1} |
| 1233 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,1)@MT7 | 523 | 23 | 21 | {'yellowKey': 1} |
| 1253 | 换层 MT7→MT8 | (1,2)@MT8 | 523 | 23 | 21 | {'yellowKey': 1} |
| 1264 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (7,5)@MT8 | 490 | 23 | 21 | {'yellowKey': 1} |
| 1276 | 换层 MT8→MT7 | (1,2)@MT7 | 490 | 23 | 21 | {'yellowKey': 1} |
| 1295 | 换层 MT7→MT6 | (11,10)@MT6 | 490 | 23 | 21 | {'yellowKey': 1} |
| 1314 | 换层 MT6→MT5 | (1,2)@MT5 | 490 | 23 | 21 | {'yellowKey': 1} |
| 1319 | 开门(耗yellowKey×1) @(4, 3) | (4,3)@MT5 | 490 | 23 | 21 | {} |
| 1322 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (4,6)@MT5 | 473 | 23 | 21 | {} |
| 1325 | 拿钥匙 yellowKey×1 | (1,6)@MT5 | 473 | 23 | 21 | {'yellowKey': 1} |
| 1326 | 拿钥匙 yellowKey×1 | (1,5)@MT5 | 473 | 23 | 21 | {'yellowKey': 2} |
| 1329 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (2,7)@MT5 | 349 | 23 | 21 | {'yellowKey': 2} |
| 1331 | 拿钥匙 yellowKey×1 | (2,9)@MT5 | 349 | 23 | 21 | {'yellowKey': 3} |
| 1332 | 回血+50 | (3,9)@MT5 | 399 | 23 | 21 | {'yellowKey': 3} |
| 1336 | 拿防御宝石+1DEF @(1, 9)  | (1,9)@MT5 | 399 | 23 | 22 | {'yellowKey': 3} |
| 1350 | 换层 MT5→MT6 | (1,2)@MT6 | 399 | 23 | 22 | {'yellowKey': 3} |
| 1365 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (7,1)@MT6 | 369 | 23 | 22 | {'yellowKey': 3} |
| 1367 | 拿钥匙 yellowKey×1 | (9,1)@MT6 | 369 | 23 | 22 | {'yellowKey': 4} |
| 1368 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,1)@MT6 | 369 | 23 | 22 | {'yellowKey': 4} |
| 1387 | 换层 MT6→MT5 | (1,2)@MT5 | 369 | 23 | 22 | {'yellowKey': 4} |
| 1410 | 换层 MT5→MT4 | (1,10)@MT4 | 369 | 23 | 22 | {'yellowKey': 4} |
| 1416 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (2,5)@MT4 | 339 | 23 | 22 | {'yellowKey': 4} |
| 1417 | 开门(耗yellowKey×1) @(2, 5) | (2,5)@MT4 | 339 | 23 | 22 | {'yellowKey': 3} |
| 1421 | 回血+50 | (1,2)@MT4 | 389 | 23 | 22 | {'yellowKey': 3} |
| 1423 | 拿钥匙 blueKey×1 | (2,1)@MT4 | 389 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1425 | 拿钥匙 yellowKey×1 | (3,2)@MT4 | 389 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1444 | 换层 MT4→MT3 | (10,11)@MT3 | 389 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1457 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (3,5)@MT3 | 373 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1466 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT3 | 373 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1468 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (10,8)@MT3 | 343 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1469 | 拿钥匙 yellowKey×1 | (11,8)@MT3 | 343 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1470 | 回血+50 | (11,7)@MT3 | 393 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1480 | 换层 MT3→MT4 | (11,10)@MT4 | 393 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1492 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,11)@MT4 | 393 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1507 | 换层 MT4→MT5 | (2,11)@MT5 | 393 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1532 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (3,5)@MT5 | 363 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1554 | 换层 MT5→MT4 | (1,10)@MT4 | 363 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1562 | 开门(耗yellowKey×1) @(3, 5) | (3,5)@MT4 | 363 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1565 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (6,5)@MT4 | 363 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1582 | 换层 MT4→MT3 | (10,11)@MT3 | 363 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1603 | 换层 MT3→MT2 | (1,10)@MT2 | 363 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1612 | 换层 MT2→MT1 | (2,1)@MT1 | 363 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1643 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血40 | (2,4)@MT1 | 323 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1644 | 开门(耗yellowKey×1) @(2, 4) | (2,4)@MT1 | 323 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1647 | 拿钥匙 yellowKey×1 | (1,6)@MT1 | 323 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1651 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血120 | (2,7)@MT1 | 203 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1652 | 开门(耗yellowKey×1) @(2, 7) | (2,7)@MT1 | 203 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1656 | 拿钥匙 yellowKey×1 | (3,10)@MT1 | 203 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1657 | 拿钥匙 yellowKey×1 | (3,11)@MT1 | 203 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1659 | 回血+50 | (1,11)@MT1 | 253 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1660 | 回血+50 | (1,10)@MT1 | 303 | 23 | 22 | {'yellowKey': 4, 'blueKey': 1} |
| 1675 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT1 | 303 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1677 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (7,6)@MT1 | 287 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1678 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (8,6)@MT1 | 257 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1679 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血16 | (9,6)@MT1 | 241 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1680 | 开门(耗yellowKey×1) @(9, 6) | (9,6)@MT1 | 241 | 23 | 22 | {'yellowKey': 2, 'blueKey': 1} |
| 1684 | 拿钥匙 yellowKey×1 | (8,3)@MT1 | 241 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1685 | 回血+50 | (8,4)@MT1 | 291 | 23 | 22 | {'yellowKey': 3, 'blueKey': 1} |
| 1686 | 拿防御宝石+1DEF @(7, 4)  | (7,4)@MT1 | 291 | 23 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1687 | 拿攻击宝石+1ATK @(7, 3)  | (7,3)@MT1 | 291 | 24 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1721 | 换层 MT1→MT2 | (1,2)@MT2 | 291 | 24 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1730 | 换层 MT2→MT3 | (2,11)@MT3 | 291 | 24 | 23 | {'yellowKey': 3, 'blueKey': 1} |
| 1744 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 291 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1746 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血27 | (1,3)@MT3 | 264 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1748 | 回血+50 | (2,2)@MT3 | 314 | 24 | 23 | {'yellowKey': 2, 'blueKey': 1} |
| 1749 | 拿防御宝石+1DEF @(2, 1)  | (2,1)@MT3 | 314 | 24 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1750 | 拿钥匙 yellowKey×1 | (1,1)@MT3 | 314 | 24 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1770 | 换层 MT3→MT4 | (11,10)@MT4 | 314 | 24 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1789 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (9,5)@MT4 | 278 | 24 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1791 | 开门(耗yellowKey×1) @(10, 5) | (10,5)@MT4 | 278 | 24 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1793 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血112 | (10,3)@MT4 | 166 | 24 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1795 | 拿钥匙 yellowKey×1 | (9,2)@MT4 | 166 | 24 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1797 | 回血+200 | (11,2)@MT4 | 366 | 24 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1822 | 换层 MT4→MT3 | (10,11)@MT3 | 366 | 24 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1838 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 366 | 24 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1840 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (1,7)@MT3 | 330 | 24 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1842 | 回血+50 | (1,9)@MT3 | 380 | 24 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1844 | 拿钥匙 yellowKey×1 | (2,8)@MT3 | 380 | 24 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1845 | 拿攻击宝石+1ATK @(2, 9)  | (2,9)@MT3 | 380 | 25 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1866 | 换层 MT3→MT4 | (11,10)@MT4 | 380 | 25 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1883 | 换层 MT4→MT5 | (2,11)@MT5 | 380 | 25 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1906 | 换层 MT5→MT6 | (1,2)@MT6 | 380 | 25 | 24 | {'yellowKey': 3, 'blueKey': 1} |
| 1926 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT6 | 380 | 25 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1929 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血14 | (11,4)@MT6 | 366 | 25 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1933 | 回血+50 | (8,3)@MT6 | 416 | 25 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1956 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (5,11)@MT6 | 380 | 25 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1968 | 换层 MT6→MT7 | (11,10)@MT7 | 380 | 25 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1987 | 换层 MT7→MT8 | (1,2)@MT8 | 380 | 25 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 1993 | 换层 MT8→MT9 | (6,2)@MT9 | 380 | 25 | 24 | {'yellowKey': 2, 'blueKey': 1} |
| 2004 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 380 | 25 | 24 | {'yellowKey': 1, 'blueKey': 1} |
| 2008 | 开门(耗blueKey×1) @(4, 11) | (4,11)@MT9 | 380 | 25 | 24 | {'yellowKey': 1} |
| 2011 | 回血+50 | (2,10)@MT9 | 430 | 25 | 24 | {'yellowKey': 1} |
| 2016 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (5,10)@MT9 | 394 | 25 | 24 | {'yellowKey': 1} |
| 2021 | 换层 MT9→MT10 | (1,10)@MT10 | 394 | 25 | 24 | {'yellowKey': 1} |

### β=4　到达 MT10 落点=(1, 10)　终态 MT10(1,10) HP=68 ATK=23 DEF=21 持钥={}　封板对账=✅一致
- 红钥匙：**全程未拿红钥匙**　|　MT8 def22 卫兵杀了 0/2　|　队长可杀(atk>15)=是
- 余量：搜索看到 HP−D=-493（D 含红门免费+埋伏漏算）　vs　满房重估 HP−1028=**-960**

| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |
|----|------|------|----|----|-----|---------|
| 0 | 起点（开局噩梦后首个自由态 MT3 入口） | (2,11)@MT3 | 400 | 10 | 10 | {} |
| 11 | 拿钥匙 blueKey×1 | (5,3)@MT3 | 400 | 10 | 10 | {'blueKey': 1} |
| 12 | 拿钥匙 yellowKey×1 | (4,3)@MT3 | 400 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 13 | 回血+200 | (4,2)@MT3 | 600 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 14 | 拿钥匙 yellowKey×1 | (4,1)@MT3 | 600 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 15 | 回血+200 | (5,1)@MT3 | 800 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 16 | 拿钥匙 yellowKey×1 | (5,2)@MT3 | 800 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 17 | 回血+200 | (6,2)@MT3 | 1000 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 18 | 拿钥匙 yellowKey×1 | (6,1)@MT3 | 1000 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 20 | 拿钥匙 yellowKey×1 | (6,3)@MT3 | 1000 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 25 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,5)@MT3 | 976 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 31 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (8,10)@MT3 | 926 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 33 | 开门(耗yellowKey×1) @(8, 11) | (8,11)@MT3 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 36 | 换层 MT3→MT4 | (11,10)@MT4 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 38 | 开门(耗yellowKey×1) @(11, 9) | (11,9)@MT4 | 926 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 48 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (3,7)@MT4 | 902 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 50 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 51 | 开门(耗yellowKey×1) @(1, 7) | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 55 | 换层 MT4→MT5 | (2,11)@MT5 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 62 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (6,8)@MT5 | 828 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 65 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,6)@MT5 | 804 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 70 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (11,7)@MT5 | 754 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 75 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT5 | 754 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 82 | 拿铁剑+10ATK @(11, 11)  | (11,11)@MT5 | 754 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 97 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,2)@MT5 | 734 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 99 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT5 | 734 | 20 | 10 | {'blueKey': 1} |
| 102 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,2)@MT5 | 726 | 20 | 10 | {'blueKey': 1} |
| 103 | 拿钥匙 yellowKey×1 | (9,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 104 | 拿钥匙 yellowKey×1 | (8,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 105 | 拿钥匙 yellowKey×1 | (8,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 106 | 拿钥匙 yellowKey×1 | (9,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 131 | 换层 MT5→MT4 | (1,10)@MT4 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 142 | 开门(耗yellowKey×1) @(8, 7) | (8,7)@MT4 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 144 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (8,9)@MT4 | 638 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 146 | 拿攻击宝石+1ATK @(7, 10)  | (7,10)@MT4 | 638 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 148 | 回血+50 | (9,10)@MT4 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 159 | 换层 MT4→MT3 | (10,11)@MT3 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 180 | 换层 MT3→MT2 | (1,10)@MT2 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 189 | 换层 MT2→MT1 | (2,1)@MT1 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 217 | 开门(耗yellowKey×1) @(5, 3) | (5,3)@MT1 | 688 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 221 | 回血+50 | (1,3)@MT1 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 236 | 开门(耗yellowKey×1) @(10, 8) | (10,8)@MT1 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 238 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (10,10)@MT1 | 710 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 239 | 回血+200 | (10,11)@MT1 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 260 | 换层 MT1→MT2 | (1,2)@MT2 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 269 | 换层 MT2→MT3 | (2,11)@MT3 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 290 | 换层 MT3→MT4 | (11,10)@MT4 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 301 | 开门(耗yellowKey×1) @(4, 7) | (4,7)@MT4 | 910 | 21 | 10 | {'blueKey': 1} |
| 303 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,9)@MT4 | 882 | 21 | 10 | {'blueKey': 1} |
| 305 | 拿钥匙 yellowKey×1 | (5,10)@MT4 | 882 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 306 | 拿钥匙 yellowKey×1 | (5,11)@MT4 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 318 | 换层 MT4→MT5 | (2,11)@MT5 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 329 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (6,4)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 331 | 拿钥匙 yellowKey×1 | (6,2)@MT5 | 854 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 333 | 开门(耗yellowKey×1) @(6, 1) | (6,1)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 335 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,1)@MT5 | 834 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 338 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 339 | 开门(耗yellowKey×1) @(3, 3) | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 343 | 换层 MT5→MT6 | (1,2)@MT6 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 349 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (3,6)@MT6 | 786 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 350 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT6 | 698 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 352 | 拿钥匙 yellowKey×1 | (6,6)@MT6 | 698 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 355 | 开门(耗yellowKey×1) @(6, 4) | (6,4)@MT6 | 698 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 358 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,3)@MT6 | 678 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 359 | 拿钥匙 yellowKey×1 | (4,2)@MT6 | 678 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 360 | 拿钥匙 yellowKey×1 | (4,1)@MT6 | 678 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 361 | 拿钥匙 yellowKey×1 | (3,1)@MT6 | 678 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 362 | 拿钥匙 yellowKey×1 | (3,2)@MT6 | 678 | 21 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 372 | 开门(耗yellowKey×1) @(6, 8) | (6,8)@MT6 | 678 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 374 | 开门(耗yellowKey×1) @(7, 8) | (7,8)@MT6 | 678 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 377 | 开门(耗yellowKey×1) @(9, 8) | (9,8)@MT6 | 678 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 380 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,9)@MT6 | 658 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 384 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (9,9)@MT6 | 638 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 386 | 回血+50 | (9,11)@MT6 | 688 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 387 | 回血+50 | (8,11)@MT6 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 396 | 换层 MT6→MT7 | (11,10)@MT7 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 399 | 开门(耗yellowKey×1) @(11, 8) | (11,8)@MT7 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 404 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血96 | (9,5)@MT7 | 642 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 406 | 回血+50 | (9,3)@MT7 | 692 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 407 | 拿钥匙 yellowKey×1 | (9,2)@MT7 | 692 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 408 | 拿钥匙 yellowKey×1 | (9,1)@MT7 | 692 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 414 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血252 | (9,7)@MT7 | 440 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 416 | 回血+200 | (9,9)@MT7 | 640 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 417 | 拿钥匙 yellowKey×1 | (9,10)@MT7 | 640 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 418 | 拿钥匙 yellowKey×1 | (9,11)@MT7 | 640 | 21 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 428 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (4,6)@MT7 | 552 | 21 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 430 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血252 | (2,6)@MT7 | 300 | 21 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 432 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 300 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 437 | 换层 MT7→MT8 | (1,2)@MT8 | 300 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 440 | 开门(耗yellowKey×1) @(2, 1) | (2,1)@MT8 | 300 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 442 | 开门(耗yellowKey×1) @(3, 1) | (3,1)@MT8 | 300 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 447 | 开门(耗yellowKey×1) @(6, 2) | (6,2)@MT8 | 300 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 450 | 拿钥匙 yellowKey×1 | (5,4)@MT8 | 300 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 451 | 拿钥匙 yellowKey×1 | (4,4)@MT8 | 300 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 452 | 拿钥匙 yellowKey×1 | (3,4)@MT8 | 300 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 458 | 换层 MT8→MT9 | (6,2)@MT9 | 300 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 459 | 开门(耗blueKey×1) @(6, 2) | (6,2)@MT9 | 300 | 21 | 10 | {'yellowKey': 4} |
| 462 | 拿钥匙 yellowKey×1 | (7,4)@MT9 | 300 | 21 | 10 | {'yellowKey': 5} |
| 464 | 拿攻击宝石+1ATK @(6, 5)  | (6,5)@MT9 | 300 | 22 | 10 | {'yellowKey': 5} |
| 466 | 拿钥匙 yellowKey×1 | (5,4)@MT9 | 300 | 22 | 10 | {'yellowKey': 6} |
| 470 | 换层 MT9→MT8 | (6,2)@MT8 | 300 | 22 | 10 | {'yellowKey': 6} |
| 471 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (7,2)@MT8 | 292 | 22 | 10 | {'yellowKey': 6} |
| 480 | 换层 MT8→MT7 | (1,2)@MT7 | 292 | 22 | 10 | {'yellowKey': 6} |
| 499 | 换层 MT7→MT6 | (11,10)@MT6 | 292 | 22 | 10 | {'yellowKey': 6} |
| 518 | 换层 MT6→MT5 | (1,2)@MT5 | 292 | 22 | 10 | {'yellowKey': 6} |
| 541 | 换层 MT5→MT4 | (1,10)@MT4 | 292 | 22 | 10 | {'yellowKey': 6} |
| 551 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (3,10)@MT4 | 284 | 22 | 10 | {'yellowKey': 6} |
| 552 | 拿钥匙 yellowKey×1 | (3,11)@MT4 | 284 | 22 | 10 | {'yellowKey': 7} |
| 553 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (4,11)@MT4 | 276 | 22 | 10 | {'yellowKey': 7} |
| 563 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (2,5)@MT4 | 188 | 22 | 10 | {'yellowKey': 7} |
| 564 | 开门(耗yellowKey×1) @(2, 5) | (2,5)@MT4 | 188 | 22 | 10 | {'yellowKey': 6} |
| 568 | 回血+50 | (1,2)@MT4 | 238 | 22 | 10 | {'yellowKey': 6} |
| 570 | 拿钥匙 blueKey×1 | (2,1)@MT4 | 238 | 22 | 10 | {'yellowKey': 6, 'blueKey': 1} |
| 572 | 拿钥匙 yellowKey×1 | (3,2)@MT4 | 238 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 590 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (8,11)@MT4 | 230 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 605 | 换层 MT4→MT5 | (2,11)@MT5 | 230 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 628 | 换层 MT5→MT6 | (1,2)@MT6 | 230 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 647 | 换层 MT6→MT7 | (11,10)@MT7 | 230 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 666 | 换层 MT7→MT8 | (1,2)@MT8 | 230 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 677 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (7,5)@MT8 | 142 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 682 | 换层 MT8→MT9 | (6,2)@MT9 | 142 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 687 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (7,6)@MT9 | 122 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 691 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (7,10)@MT9 | 94 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 699 | 开门(耗yellowKey×1) @(5, 5) | (5,5)@MT9 | 94 | 22 | 10 | {'yellowKey': 6, 'blueKey': 1} |
| 701 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,5)@MT9 | 66 | 22 | 10 | {'yellowKey': 6, 'blueKey': 1} |
| 703 | 拿钥匙 yellowKey×1 | (2,4)@MT9 | 66 | 22 | 10 | {'yellowKey': 7, 'blueKey': 1} |
| 705 | 拿防御宝石+1DEF @(1, 5)  | (1,5)@MT9 | 66 | 22 | 11 | {'yellowKey': 7, 'blueKey': 1} |
| 716 | 开门(耗yellowKey×1) @(7, 1) | (7,1)@MT9 | 66 | 22 | 11 | {'yellowKey': 6, 'blueKey': 1} |
| 718 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (9,1)@MT9 | 59 | 22 | 11 | {'yellowKey': 6, 'blueKey': 1} |
| 720 | 回血+50 | (11,1)@MT9 | 109 | 22 | 11 | {'yellowKey': 6, 'blueKey': 1} |
| 724 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (10,2)@MT9 | 102 | 22 | 11 | {'yellowKey': 6, 'blueKey': 1} |
| 733 | 拿铁盾+10DEF @(9, 7)  | (9,7)@MT9 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 750 | 换层 MT9→MT8 | (6,2)@MT8 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 758 | 换层 MT8→MT7 | (1,2)@MT7 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 777 | 换层 MT7→MT6 | (11,10)@MT6 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 796 | 换层 MT6→MT5 | (1,2)@MT5 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 819 | 换层 MT5→MT4 | (1,10)@MT4 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 836 | 换层 MT4→MT3 | (10,11)@MT3 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 857 | 换层 MT3→MT2 | (1,10)@MT2 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 866 | 换层 MT2→MT1 | (2,1)@MT1 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 887 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (9,11)@MT1 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 889 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,11)@MT1 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 911 | 换层 MT1→MT2 | (1,2)@MT2 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 920 | 换层 MT2→MT3 | (2,11)@MT3 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 941 | 换层 MT3→MT4 | (11,10)@MT4 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 958 | 换层 MT4→MT5 | (2,11)@MT5 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 981 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (8,2)@MT5 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1009 | 换层 MT5→MT6 | (1,2)@MT6 | 102 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1024 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血63 | (5,11)@MT6 | 39 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1036 | 换层 MT6→MT7 | (11,10)@MT7 | 39 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1055 | 换层 MT7→MT8 | (1,2)@MT8 | 39 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1068 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (7,7)@MT8 | 22 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1082 | 换层 MT8→MT7 | (1,2)@MT7 | 22 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1101 | 换层 MT7→MT6 | (11,10)@MT6 | 22 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1115 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (2,11)@MT6 | 22 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1130 | 换层 MT6→MT7 | (11,10)@MT7 | 22 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1149 | 换层 MT7→MT8 | (1,2)@MT8 | 22 | 22 | 21 | {'yellowKey': 6, 'blueKey': 1} |
| 1150 | 开门(耗yellowKey×1) @(1, 2) | (1,2)@MT8 | 22 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1153 | 回血+50 | (1,5)@MT8 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1155 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,6)@MT8 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1156 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,6)@MT8 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1157 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (4,6)@MT8 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1165 | 换层 MT8→MT7 | (1,2)@MT7 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1184 | 换层 MT7→MT6 | (11,10)@MT6 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1203 | 换层 MT6→MT5 | (1,2)@MT5 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1226 | 换层 MT5→MT4 | (1,10)@MT4 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1243 | 换层 MT4→MT3 | (10,11)@MT3 | 72 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1256 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (3,5)@MT3 | 55 | 22 | 21 | {'yellowKey': 5, 'blueKey': 1} |
| 1265 | 开门(耗yellowKey×1) @(8, 2) | (8,2)@MT3 | 55 | 22 | 21 | {'yellowKey': 4, 'blueKey': 1} |
| 1267 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (10,2)@MT3 | 38 | 22 | 21 | {'yellowKey': 4, 'blueKey': 1} |
| 1269 | 回血+50 | (11,1)@MT3 | 88 | 22 | 21 | {'yellowKey': 4, 'blueKey': 1} |
| 1285 | 换层 MT3→MT4 | (11,10)@MT4 | 88 | 22 | 21 | {'yellowKey': 4, 'blueKey': 1} |
| 1299 | 开门(耗yellowKey×1) @(3, 5) | (3,5)@MT4 | 88 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1302 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (6,5)@MT4 | 88 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1313 | 换层 MT4→MT5 | (2,11)@MT5 | 88 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1336 | 换层 MT5→MT6 | (1,2)@MT6 | 88 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1351 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血44 | (7,1)@MT6 | 44 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1353 | 拿钥匙 yellowKey×1 | (9,1)@MT6 | 44 | 22 | 21 | {'yellowKey': 4, 'blueKey': 1} |
| 1354 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,1)@MT6 | 44 | 22 | 21 | {'yellowKey': 4, 'blueKey': 1} |
| 1373 | 换层 MT6→MT7 | (11,10)@MT7 | 44 | 22 | 21 | {'yellowKey': 4, 'blueKey': 1} |
| 1388 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 44 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1392 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (1,10)@MT7 | 44 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1394 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,11)@MT7 | 44 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1396 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,10)@MT7 | 44 | 22 | 21 | {'yellowKey': 3, 'blueKey': 1} |
| 1407 | 开门(耗yellowKey×1) @(3, 6) | (3,6)@MT7 | 44 | 22 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1410 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (3,3)@MT7 | 27 | 22 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1411 | 回血+50 | (3,2)@MT7 | 77 | 22 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1412 | 拿攻击宝石+1ATK @(3, 1)  | (3,1)@MT7 | 77 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1424 | 换层 MT7→MT8 | (1,2)@MT8 | 77 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1439 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血42 | (6,8)@MT8 | 35 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1441 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (4,8)@MT8 | 18 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1454 | 换层 MT8→MT9 | (6,2)@MT9 | 18 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1465 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 18 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1469 | 开门(耗blueKey×1) @(4, 11) | (4,11)@MT9 | 18 | 23 | 21 | {'yellowKey': 1} |
| 1472 | 回血+50 | (2,10)@MT9 | 68 | 23 | 21 | {'yellowKey': 1} |
| 1474 | 换层 MT9→MT10 | (1,10)@MT10 | 68 | 23 | 21 | {'yellowKey': 1} |
| 1475 | 开门(耗yellowKey×1) @(1, 10) | (1,10)@MT10 | 68 | 23 | 21 | {} |

### β=8　到达 MT10 落点=(1, 10)　终态 MT10(1,10) HP=318 ATK=25 DEF=24 持钥={'yellowKey': 1}　封板对账=✅一致
- 红钥匙：**全程未拿红钥匙**　|　MT8 def22 卫兵杀了 0/2　|　队长可杀(atk>15)=是
- 余量：搜索看到 HP−D=-75（D 含红门免费+埋伏漏算）　vs　满房重估 HP−809=**-491**

| 步# | 事件 | 坐标 | HP | ATK | DEF | 持有钥匙 |
|----|------|------|----|----|-----|---------|
| 0 | 起点（开局噩梦后首个自由态 MT3 入口） | (2,11)@MT3 | 400 | 10 | 10 | {} |
| 11 | 拿钥匙 blueKey×1 | (5,3)@MT3 | 400 | 10 | 10 | {'blueKey': 1} |
| 12 | 拿钥匙 yellowKey×1 | (4,3)@MT3 | 400 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 13 | 回血+200 | (4,2)@MT3 | 600 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 14 | 拿钥匙 yellowKey×1 | (4,1)@MT3 | 600 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 15 | 回血+200 | (5,1)@MT3 | 800 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 16 | 拿钥匙 yellowKey×1 | (5,2)@MT3 | 800 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 17 | 回血+200 | (6,2)@MT3 | 1000 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 18 | 拿钥匙 yellowKey×1 | (6,1)@MT3 | 1000 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 20 | 拿钥匙 yellowKey×1 | (6,3)@MT3 | 1000 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 25 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,5)@MT3 | 976 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 31 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (8,10)@MT3 | 926 | 10 | 10 | {'yellowKey': 5, 'blueKey': 1} |
| 33 | 开门(耗yellowKey×1) @(8, 11) | (8,11)@MT3 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 36 | 换层 MT3→MT4 | (11,10)@MT4 | 926 | 10 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 38 | 开门(耗yellowKey×1) @(11, 9) | (11,9)@MT4 | 926 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 48 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (3,7)@MT4 | 902 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 50 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 51 | 开门(耗yellowKey×1) @(1, 7) | (1,7)@MT4 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 55 | 换层 MT4→MT5 | (2,11)@MT5 | 852 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 62 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (6,8)@MT5 | 828 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 65 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血24 | (7,6)@MT5 | 804 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 70 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血50 | (11,7)@MT5 | 754 | 10 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 75 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT5 | 754 | 10 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 82 | 拿铁剑+10ATK @(11, 11)  | (11,11)@MT5 | 754 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 97 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,2)@MT5 | 734 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 99 | 开门(耗yellowKey×1) @(11, 1) | (11,1)@MT5 | 734 | 20 | 10 | {'blueKey': 1} |
| 102 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血8 | (9,2)@MT5 | 726 | 20 | 10 | {'blueKey': 1} |
| 103 | 拿钥匙 yellowKey×1 | (9,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 104 | 拿钥匙 yellowKey×1 | (8,3)@MT5 | 726 | 20 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 105 | 拿钥匙 yellowKey×1 | (8,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 106 | 拿钥匙 yellowKey×1 | (9,4)@MT5 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 131 | 换层 MT5→MT4 | (1,10)@MT4 | 726 | 20 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 142 | 开门(耗yellowKey×1) @(8, 7) | (8,7)@MT4 | 726 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 144 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血88 | (8,9)@MT4 | 638 | 20 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 146 | 拿攻击宝石+1ATK @(7, 10)  | (7,10)@MT4 | 638 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 148 | 回血+50 | (9,10)@MT4 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 159 | 换层 MT4→MT3 | (10,11)@MT3 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 180 | 换层 MT3→MT2 | (1,10)@MT2 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 189 | 换层 MT2→MT1 | (2,1)@MT1 | 688 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 217 | 开门(耗yellowKey×1) @(5, 3) | (5,3)@MT1 | 688 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 221 | 回血+50 | (1,3)@MT1 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 236 | 开门(耗yellowKey×1) @(10, 8) | (10,8)@MT1 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 238 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (10,10)@MT1 | 710 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 239 | 回血+200 | (10,11)@MT1 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 260 | 换层 MT1→MT2 | (1,2)@MT2 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 269 | 换层 MT2→MT3 | (2,11)@MT3 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 290 | 换层 MT3→MT4 | (11,10)@MT4 | 910 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 301 | 开门(耗yellowKey×1) @(4, 7) | (4,7)@MT4 | 910 | 21 | 10 | {'blueKey': 1} |
| 303 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,9)@MT4 | 882 | 21 | 10 | {'blueKey': 1} |
| 305 | 拿钥匙 yellowKey×1 | (5,10)@MT4 | 882 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 306 | 拿钥匙 yellowKey×1 | (5,11)@MT4 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 318 | 换层 MT4→MT5 | (2,11)@MT5 | 882 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 329 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (6,4)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 331 | 拿钥匙 yellowKey×1 | (6,2)@MT5 | 854 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 333 | 开门(耗yellowKey×1) @(6, 1) | (6,1)@MT5 | 854 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 335 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,1)@MT5 | 834 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 338 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 339 | 开门(耗yellowKey×1) @(3, 3) | (3,3)@MT5 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 343 | 换层 MT5→MT6 | (1,2)@MT6 | 806 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 349 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (3,6)@MT6 | 786 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 356 | 换层 MT6→MT5 | (1,2)@MT5 | 786 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 361 | 开门(耗yellowKey×1) @(4, 3) | (4,3)@MT5 | 786 | 21 | 10 | {'blueKey': 1} |
| 364 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血28 | (4,6)@MT5 | 758 | 21 | 10 | {'blueKey': 1} |
| 367 | 拿钥匙 yellowKey×1 | (1,6)@MT5 | 758 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 368 | 拿钥匙 yellowKey×1 | (1,5)@MT5 | 758 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 380 | 换层 MT5→MT6 | (1,2)@MT6 | 758 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 383 | 开门(耗yellowKey×1) @(1, 4) | (1,4)@MT6 | 758 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 385 | 开门(耗yellowKey×1) @(2, 4) | (2,4)@MT6 | 758 | 21 | 10 | {'blueKey': 1} |
| 388 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (4,3)@MT6 | 738 | 21 | 10 | {'blueKey': 1} |
| 389 | 拿钥匙 yellowKey×1 | (4,2)@MT6 | 738 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 390 | 拿钥匙 yellowKey×1 | (4,1)@MT6 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 391 | 拿钥匙 yellowKey×1 | (3,1)@MT6 | 738 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 392 | 拿钥匙 yellowKey×1 | (3,2)@MT6 | 738 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 396 | 开门(耗yellowKey×1) @(4, 4) | (4,4)@MT6 | 738 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 400 | 拿钥匙 yellowKey×1 | (6,6)@MT6 | 738 | 21 | 10 | {'yellowKey': 4, 'blueKey': 1} |
| 403 | 开门(耗yellowKey×1) @(6, 8) | (6,8)@MT6 | 738 | 21 | 10 | {'yellowKey': 3, 'blueKey': 1} |
| 405 | 开门(耗yellowKey×1) @(7, 8) | (7,8)@MT6 | 738 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 408 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (9,9)@MT6 | 718 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 410 | 回血+50 | (9,11)@MT6 | 768 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 411 | 回血+50 | (8,11)@MT6 | 818 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 416 | 开门(耗yellowKey×1) @(9, 8) | (9,8)@MT6 | 818 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 419 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血20 | (11,9)@MT6 | 798 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 437 | 换层 MT6→MT5 | (1,2)@MT5 | 798 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 447 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血252 | (2,7)@MT5 | 546 | 21 | 10 | {'yellowKey': 1, 'blueKey': 1} |
| 449 | 拿钥匙 yellowKey×1 | (2,9)@MT5 | 546 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 450 | 回血+50 | (3,9)@MT5 | 596 | 21 | 10 | {'yellowKey': 2, 'blueKey': 1} |
| 454 | 拿防御宝石+1DEF @(1, 9)  | (1,9)@MT5 | 596 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 468 | 换层 MT5→MT6 | (1,2)@MT6 | 596 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 479 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血84 | (4,6)@MT6 | 512 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 487 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血93 | (5,11)@MT6 | 419 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 495 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血93 | (8,6)@MT6 | 326 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 506 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (2,11)@MT6 | 319 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 521 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血84 | (7,1)@MT6 | 235 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 523 | 拿钥匙 yellowKey×1 | (9,1)@MT6 | 235 | 21 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 524 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (10,1)@MT6 | 228 | 21 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 543 | 换层 MT6→MT7 | (11,10)@MT7 | 228 | 21 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 546 | 开门(耗yellowKey×1) @(11, 8) | (11,8)@MT7 | 228 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 551 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血93 | (9,5)@MT7 | 135 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 553 | 回血+50 | (9,3)@MT7 | 185 | 21 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 554 | 拿钥匙 yellowKey×1 | (9,2)@MT7 | 185 | 21 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 555 | 拿钥匙 yellowKey×1 | (9,1)@MT7 | 185 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 567 | 换层 MT7→MT6 | (11,10)@MT6 | 185 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 586 | 换层 MT6→MT5 | (1,2)@MT5 | 185 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 613 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (8,2)@MT5 | 178 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 637 | 换层 MT5→MT4 | (1,10)@MT4 | 178 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 647 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (3,10)@MT4 | 171 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 648 | 拿钥匙 yellowKey×1 | (3,11)@MT4 | 171 | 21 | 11 | {'yellowKey': 5, 'blueKey': 1} |
| 660 | 换层 MT4→MT5 | (2,11)@MT5 | 171 | 21 | 11 | {'yellowKey': 5, 'blueKey': 1} |
| 683 | 换层 MT5→MT6 | (1,2)@MT6 | 171 | 21 | 11 | {'yellowKey': 5, 'blueKey': 1} |
| 702 | 换层 MT6→MT7 | (11,10)@MT7 | 171 | 21 | 11 | {'yellowKey': 5, 'blueKey': 1} |
| 713 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血84 | (4,6)@MT7 | 87 | 21 | 11 | {'yellowKey': 5, 'blueKey': 1} |
| 715 | 开门(耗yellowKey×1) @(3, 6) | (3,6)@MT7 | 87 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 718 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血27 | (3,3)@MT7 | 60 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 719 | 回血+50 | (3,2)@MT7 | 110 | 21 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 720 | 拿攻击宝石+1ATK @(3, 1)  | (3,1)@MT7 | 110 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 738 | 换层 MT7→MT6 | (11,10)@MT6 | 110 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 757 | 换层 MT6→MT5 | (1,2)@MT5 | 110 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 780 | 换层 MT5→MT4 | (1,10)@MT4 | 110 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 792 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (4,11)@MT4 | 103 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 807 | 换层 MT4→MT3 | (10,11)@MT3 | 103 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 820 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血27 | (3,5)@MT3 | 76 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 834 | 换层 MT3→MT4 | (11,10)@MT4 | 76 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 846 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (8,11)@MT4 | 69 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 861 | 换层 MT4→MT5 | (2,11)@MT5 | 69 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 884 | 换层 MT5→MT6 | (1,2)@MT6 | 69 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 903 | 换层 MT6→MT7 | (11,10)@MT7 | 69 | 22 | 11 | {'yellowKey': 4, 'blueKey': 1} |
| 916 | 开门(耗yellowKey×1) @(3, 6) | (3,6)@MT7 | 69 | 22 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 920 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (3,10)@MT7 | 62 | 22 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 922 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血18 | (2,11)@MT7 | 44 | 22 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 924 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (1,10)@MT7 | 37 | 22 | 11 | {'yellowKey': 3, 'blueKey': 1} |
| 927 | 开门(耗yellowKey×1) @(1, 8) | (1,8)@MT7 | 37 | 22 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 930 | 开门(耗yellowKey×1) @(1, 6) | (1,6)@MT7 | 37 | 22 | 11 | {'yellowKey': 1, 'blueKey': 1} |
| 945 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT7 | 37 | 22 | 11 | {'blueKey': 1} |
| 948 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血27 | (5,9)@MT7 | 10 | 22 | 11 | {'blueKey': 1} |
| 949 | 拿钥匙 yellowKey×1 | (5,10)@MT7 | 10 | 22 | 11 | {'yellowKey': 1, 'blueKey': 1} |
| 950 | 拿钥匙 yellowKey×1 | (5,11)@MT7 | 10 | 22 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 974 | 换层 MT7→MT8 | (1,2)@MT8 | 10 | 22 | 11 | {'yellowKey': 2, 'blueKey': 1} |
| 977 | 开门(耗yellowKey×1) @(2, 1) | (2,1)@MT8 | 10 | 22 | 11 | {'yellowKey': 1, 'blueKey': 1} |
| 979 | 开门(耗yellowKey×1) @(3, 1) | (3,1)@MT8 | 10 | 22 | 11 | {'blueKey': 1} |
| 984 | 换层 MT8→MT9 | (6,2)@MT9 | 10 | 22 | 11 | {'blueKey': 1} |
| 985 | 开门(耗blueKey×1) @(6, 2) | (6,2)@MT9 | 10 | 22 | 11 | {} |
| 988 | 拿钥匙 yellowKey×1 | (7,4)@MT9 | 10 | 22 | 11 | {'yellowKey': 1} |
| 990 | 拿攻击宝石+1ATK @(6, 5)  | (6,5)@MT9 | 10 | 23 | 11 | {'yellowKey': 1} |
| 992 | 拿钥匙 yellowKey×1 | (5,4)@MT9 | 10 | 23 | 11 | {'yellowKey': 2} |
| 998 | 开门(耗yellowKey×1) @(7, 1) | (7,1)@MT9 | 10 | 23 | 11 | {'yellowKey': 1} |
| 1000 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (9,1)@MT9 | 3 | 23 | 11 | {'yellowKey': 1} |
| 1002 | 回血+50 | (11,1)@MT9 | 53 | 23 | 11 | {'yellowKey': 1} |
| 1011 | 换层 MT9→MT8 | (6,2)@MT8 | 53 | 23 | 11 | {'yellowKey': 1} |
| 1012 | 开门(耗yellowKey×1) @(6, 2) | (6,2)@MT8 | 53 | 23 | 11 | {} |
| 1015 | 拿钥匙 yellowKey×1 | (5,4)@MT8 | 53 | 23 | 11 | {'yellowKey': 1} |
| 1016 | 拿钥匙 yellowKey×1 | (4,4)@MT8 | 53 | 23 | 11 | {'yellowKey': 2} |
| 1017 | 拿钥匙 yellowKey×1 | (3,4)@MT8 | 53 | 23 | 11 | {'yellowKey': 3} |
| 1023 | 换层 MT8→MT9 | (6,2)@MT9 | 53 | 23 | 11 | {'yellowKey': 3} |
| 1028 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血18 | (7,6)@MT9 | 35 | 23 | 11 | {'yellowKey': 3} |
| 1039 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (10,2)@MT9 | 28 | 23 | 11 | {'yellowKey': 3} |
| 1048 | 换层 MT9→MT8 | (6,2)@MT8 | 28 | 23 | 11 | {'yellowKey': 3} |
| 1049 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血7 | (7,2)@MT8 | 21 | 23 | 11 | {'yellowKey': 3} |
| 1051 | 换层 MT8→MT9 | (6,2)@MT9 | 21 | 23 | 11 | {'yellowKey': 3} |
| 1066 | 拿铁盾+10DEF @(9, 7)  | (9,7)@MT9 | 21 | 23 | 21 | {'yellowKey': 3} |
| 1083 | 换层 MT9→MT8 | (6,2)@MT8 | 21 | 23 | 21 | {'yellowKey': 3} |
| 1091 | 开门(耗yellowKey×1) @(1, 2) | (1,2)@MT8 | 21 | 23 | 21 | {'yellowKey': 2} |
| 1094 | 回血+50 | (1,5)@MT8 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1096 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (2,6)@MT8 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1097 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (3,6)@MT8 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1098 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (4,6)@MT8 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1106 | 换层 MT8→MT7 | (1,2)@MT7 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1135 | 换层 MT7→MT6 | (11,10)@MT6 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1154 | 换层 MT6→MT5 | (1,2)@MT5 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1177 | 换层 MT5→MT4 | (1,10)@MT4 | 71 | 23 | 21 | {'yellowKey': 2} |
| 1183 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (2,5)@MT4 | 38 | 23 | 21 | {'yellowKey': 2} |
| 1184 | 开门(耗yellowKey×1) @(2, 5) | (2,5)@MT4 | 38 | 23 | 21 | {'yellowKey': 1} |
| 1188 | 回血+50 | (1,2)@MT4 | 88 | 23 | 21 | {'yellowKey': 1} |
| 1190 | 拿钥匙 blueKey×1 | (2,1)@MT4 | 88 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1192 | 拿钥匙 yellowKey×1 | (3,2)@MT4 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1211 | 换层 MT4→MT3 | (10,11)@MT3 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1232 | 换层 MT3→MT2 | (1,10)@MT2 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1241 | 换层 MT2→MT1 | (2,1)@MT1 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1262 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (9,11)@MT1 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1264 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (11,11)@MT1 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1286 | 换层 MT1→MT2 | (1,2)@MT2 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1295 | 换层 MT2→MT3 | (2,11)@MT3 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1316 | 换层 MT3→MT4 | (11,10)@MT4 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1333 | 换层 MT4→MT5 | (2,11)@MT5 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1356 | 换层 MT5→MT6 | (1,2)@MT6 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1375 | 换层 MT6→MT7 | (11,10)@MT7 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1404 | 换层 MT7→MT8 | (1,2)@MT8 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1410 | 换层 MT8→MT9 | (6,2)@MT9 | 88 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1419 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (7,10)@MT9 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1431 | 换层 MT9→MT8 | (6,2)@MT8 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1439 | 换层 MT8→MT7 | (1,2)@MT7 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1468 | 换层 MT7→MT6 | (11,10)@MT6 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1487 | 换层 MT6→MT5 | (1,2)@MT5 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1510 | 换层 MT5→MT4 | (1,10)@MT4 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1527 | 换层 MT4→MT3 | (10,11)@MT3 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1548 | 换层 MT3→MT2 | (1,10)@MT2 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1557 | 换层 MT2→MT1 | (2,1)@MT1 | 71 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1588 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血42 | (2,4)@MT1 | 29 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1620 | 换层 MT1→MT2 | (1,2)@MT2 | 29 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1629 | 换层 MT2→MT3 | (2,11)@MT3 | 29 | 23 | 21 | {'yellowKey': 2, 'blueKey': 1} |
| 1645 | 开门(耗yellowKey×1) @(8, 2) | (8,2)@MT3 | 29 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1647 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (10,2)@MT3 | 12 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1649 | 回血+50 | (11,1)@MT3 | 62 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1660 | 开门(耗yellowKey×1) @(8, 8) | (8,8)@MT3 | 62 | 23 | 21 | {'blueKey': 1} |
| 1662 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (10,8)@MT3 | 29 | 23 | 21 | {'blueKey': 1} |
| 1663 | 拿钥匙 yellowKey×1 | (11,8)@MT3 | 29 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1664 | 回血+50 | (11,7)@MT3 | 79 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1674 | 换层 MT3→MT4 | (11,10)@MT4 | 79 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1691 | 换层 MT4→MT5 | (2,11)@MT5 | 79 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1714 | 换层 MT5→MT6 | (1,2)@MT6 | 79 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1733 | 换层 MT6→MT7 | (11,10)@MT7 | 79 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1762 | 换层 MT7→MT8 | (1,2)@MT8 | 79 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1768 | 换层 MT8→MT9 | (6,2)@MT9 | 79 | 23 | 21 | {'yellowKey': 1, 'blueKey': 1} |
| 1779 | 开门(耗yellowKey×1) @(7, 11) | (7,11)@MT9 | 79 | 23 | 21 | {'blueKey': 1} |
| 1783 | 开门(耗blueKey×1) @(4, 11) | (4,11)@MT9 | 79 | 23 | 21 | {} |
| 1786 | 回血+50 | (2,10)@MT9 | 129 | 23 | 21 | {} |
| 1805 | 换层 MT9→MT8 | (6,2)@MT8 | 129 | 23 | 21 | {} |
| 1813 | 换层 MT8→MT7 | (1,2)@MT7 | 129 | 23 | 21 | {} |
| 1836 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (9,7)@MT7 | 5 | 23 | 21 | {} |
| 1838 | 回血+200 | (9,9)@MT7 | 205 | 23 | 21 | {} |
| 1839 | 拿钥匙 yellowKey×1 | (9,10)@MT7 | 205 | 23 | 21 | {'yellowKey': 1} |
| 1840 | 拿钥匙 yellowKey×1 | (9,11)@MT7 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1852 | 换层 MT7→MT6 | (11,10)@MT6 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1871 | 换层 MT6→MT5 | (1,2)@MT5 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1894 | 换层 MT5→MT4 | (1,10)@MT4 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1911 | 换层 MT4→MT3 | (10,11)@MT3 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1932 | 换层 MT3→MT2 | (1,10)@MT2 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1941 | 换层 MT2→MT1 | (2,1)@MT1 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1973 | 开门(耗yellowKey×1) @(2, 4) | (2,4)@MT1 | 205 | 23 | 21 | {'yellowKey': 1} |
| 1976 | 拿钥匙 yellowKey×1 | (1,6)@MT1 | 205 | 23 | 21 | {'yellowKey': 2} |
| 1980 | 打怪 骷髅士兵(idskeletonSoldier hp55/atk52/def12) 损血124 | (2,7)@MT1 | 81 | 23 | 21 | {'yellowKey': 2} |
| 1981 | 开门(耗yellowKey×1) @(2, 7) | (2,7)@MT1 | 81 | 23 | 21 | {'yellowKey': 1} |
| 1985 | 拿钥匙 yellowKey×1 | (3,10)@MT1 | 81 | 23 | 21 | {'yellowKey': 2} |
| 1986 | 拿钥匙 yellowKey×1 | (3,11)@MT1 | 81 | 23 | 21 | {'yellowKey': 3} |
| 1988 | 回血+50 | (1,11)@MT1 | 131 | 23 | 21 | {'yellowKey': 3} |
| 1989 | 回血+50 | (1,10)@MT1 | 181 | 23 | 21 | {'yellowKey': 3} |
| 2004 | 开门(耗yellowKey×1) @(5, 6) | (5,6)@MT1 | 181 | 23 | 21 | {'yellowKey': 2} |
| 2006 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (7,6)@MT1 | 164 | 23 | 21 | {'yellowKey': 2} |
| 2007 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血33 | (8,6)@MT1 | 131 | 23 | 21 | {'yellowKey': 2} |
| 2008 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血17 | (9,6)@MT1 | 114 | 23 | 21 | {'yellowKey': 2} |
| 2009 | 开门(耗yellowKey×1) @(9, 6) | (9,6)@MT1 | 114 | 23 | 21 | {'yellowKey': 1} |
| 2013 | 拿钥匙 yellowKey×1 | (8,3)@MT1 | 114 | 23 | 21 | {'yellowKey': 2} |
| 2014 | 回血+50 | (8,4)@MT1 | 164 | 23 | 21 | {'yellowKey': 2} |
| 2015 | 拿防御宝石+1DEF @(7, 4)  | (7,4)@MT1 | 164 | 23 | 22 | {'yellowKey': 2} |
| 2016 | 拿攻击宝石+1ATK @(7, 3)  | (7,3)@MT1 | 164 | 24 | 22 | {'yellowKey': 2} |
| 2050 | 换层 MT1→MT2 | (1,2)@MT2 | 164 | 24 | 22 | {'yellowKey': 2} |
| 2059 | 换层 MT2→MT3 | (2,11)@MT3 | 164 | 24 | 22 | {'yellowKey': 2} |
| 2073 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 164 | 24 | 22 | {'yellowKey': 1} |
| 2075 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血30 | (1,3)@MT3 | 134 | 24 | 22 | {'yellowKey': 1} |
| 2077 | 回血+50 | (2,2)@MT3 | 184 | 24 | 22 | {'yellowKey': 1} |
| 2078 | 拿防御宝石+1DEF @(2, 1)  | (2,1)@MT3 | 184 | 24 | 23 | {'yellowKey': 1} |
| 2079 | 拿钥匙 yellowKey×1 | (1,1)@MT3 | 184 | 24 | 23 | {'yellowKey': 2} |
| 2084 | 开门(耗yellowKey×1) @(1, 5) | (1,5)@MT3 | 184 | 24 | 23 | {'yellowKey': 1} |
| 2086 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血38 | (1,7)@MT3 | 146 | 24 | 23 | {'yellowKey': 1} |
| 2088 | 回血+50 | (1,9)@MT3 | 196 | 24 | 23 | {'yellowKey': 1} |
| 2090 | 拿钥匙 yellowKey×1 | (2,8)@MT3 | 196 | 24 | 23 | {'yellowKey': 2} |
| 2091 | 拿攻击宝石+1ATK @(2, 9)  | (2,9)@MT3 | 196 | 25 | 23 | {'yellowKey': 2} |
| 2112 | 换层 MT3→MT4 | (11,10)@MT4 | 196 | 25 | 23 | {'yellowKey': 2} |
| 2129 | 换层 MT4→MT5 | (2,11)@MT5 | 196 | 25 | 23 | {'yellowKey': 2} |
| 2152 | 换层 MT5→MT6 | (1,2)@MT6 | 196 | 25 | 23 | {'yellowKey': 2} |
| 2171 | 换层 MT6→MT7 | (11,10)@MT7 | 196 | 25 | 23 | {'yellowKey': 2} |
| 2180 | 开门(耗yellowKey×1) @(7, 6) | (7,6)@MT7 | 196 | 25 | 23 | {'yellowKey': 1} |
| 2183 | 打怪 红色史来姆(idredSlime hp45/atk20/def2) 损血0 | (7,9)@MT7 | 196 | 25 | 23 | {'yellowKey': 1} |
| 2184 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血27 | (7,10)@MT7 | 169 | 25 | 23 | {'yellowKey': 1} |
| 2185 | 回血+200 | (7,11)@MT7 | 369 | 25 | 23 | {'yellowKey': 1} |
| 2211 | 换层 MT7→MT8 | (1,2)@MT8 | 369 | 25 | 23 | {'yellowKey': 1} |
| 2217 | 换层 MT8→MT9 | (6,2)@MT9 | 369 | 25 | 23 | {'yellowKey': 1} |
| 2222 | 开门(耗yellowKey×1) @(5, 5) | (5,5)@MT9 | 369 | 25 | 23 | {} |
| 2224 | 打怪 小蝙蝠(idbat hp35/atk38/def3) 损血15 | (3,5)@MT9 | 354 | 25 | 23 | {} |
| 2226 | 拿钥匙 yellowKey×1 | (2,4)@MT9 | 354 | 25 | 23 | {'yellowKey': 1} |
| 2228 | 拿防御宝石+1DEF @(1, 5)  | (1,5)@MT9 | 354 | 25 | 24 | {'yellowKey': 1} |
| 2245 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (5,10)@MT9 | 318 | 25 | 24 | {'yellowKey': 1} |
| 2250 | 换层 MT9→MT10 | (1,10)@MT10 | 318 | 25 | 24 | {'yellowKey': 1} |

