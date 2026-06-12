# κ=0+stairs 搜索到 MT10 的「最好那条」路线导出（只读·引擎封板重放）

> 仅导出，不含策略分析。动作串=搜索 cut 文件原样落盘的方向键，已从干净起点引擎重放对账。
> 来源文件：`crossbeam_cut_K50_vzone_lam0.0_stairs.jsonl` 中 `floor==MT10` 按 (DEF↓,ATK↓,HP↓) 取顶的那条。

## 0. 这条是引擎重放过的还是缩点算的（玩家问 #4）
- **产生**：κ=0+stairs 跨层 beam 搜索（缩点算子内部展开成方向键），cut 时把整串 RULD 落盘。
- **校验**：本脚本把这串方向键从【干净起点】(`build_start`，开局噩梦后 MT3 入口) 用封板引擎
  `sim.step` 经 `solver.verify.replay` 重放，与 cut 日志行【逐字段对账】：
  - floor: 重放=MT10 / 日志=MT10
  - HP: 重放=6 / 日志=6　ATK: 26/26　DEF: 25/25
  - **对账结果：逐字段一致 ✅（动作串真能引擎走到该终态，非仅缩点抽象层算过）**
- ⚠ 动作串从【开局噩梦后首个自由态】起算：真实游戏照走前，需先走完强制开局噩梦（build_start 内施加存档前 82 token，无博弈自由度的过场）。

## 1. 入口 / 终态字段
- **导出主态**（玩家口径 maxDEF=25/maxATK=26）：MT10 HP=6 ATK=26 DEF=25，动作 1653 步。
- **终态停点**：MT10(10,6) HP=6 ATK=26 DEF=25 mdef=0 gold=202 持钥={}
- 起点：MT3(2,11) HP=400 ATK=10 DEF=10 持钥={}
- 另存最宽口径 maxHP@MT10 兄弟态（非本条，仅 #3 参照）：HP=165 ATK=24 DEF=23

## 2. 逐里程碑（每个关键节点：换层/拿装备宝石/拿钥匙/开门/打怪 + 当刻坐标/属性/持钥）
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
| 1560 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血24 | (7,1)@MT6 | 118 | 25 | 24 | {'yellowKey': 2} |
| 1562 | 拿钥匙 yellowKey×1 | (9,1)@MT6 | 118 | 25 | 24 | {'yellowKey': 3} |
| 1563 | 打怪 绿色史来姆(idgreenSlime hp35/atk18/def1) 损血0 | (10,1)@MT6 | 118 | 25 | 24 | {'yellowKey': 3} |
| 1582 | 换层 MT6→MT7 | (11,10)@MT7 | 118 | 25 | 24 | {'yellowKey': 3} |
| 1601 | 换层 MT7→MT8 | (1,2)@MT8 | 118 | 25 | 24 | {'yellowKey': 3} |
| 1607 | 换层 MT8→MT9 | (6,2)@MT9 | 118 | 25 | 24 | {'yellowKey': 3} |
| 1623 | 换层 MT9→MT10 | (1,10)@MT10 | 118 | 25 | 24 | {'yellowKey': 3} |
| 1624 | 开门(耗yellowKey×1) @(1, 10) | (1,10)@MT10 | 118 | 25 | 24 | {'yellowKey': 2} |
| 1629 | 开门(耗yellowKey×1) @(3, 8) | (3,8)@MT10 | 118 | 25 | 24 | {'yellowKey': 1} |
| 1631 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血36 | (3,6)@MT10 | 82 | 25 | 24 | {'yellowKey': 1} |
| 1632 | 拿防御宝石+1DEF @(2, 6)  | (2,6)@MT10 | 82 | 25 | 25 | {'yellowKey': 1} |
| 1639 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血21 | (4,11)@MT10 | 61 | 25 | 25 | {'yellowKey': 1} |
| 1645 | 打怪 初级法师(idbluePriest hp60/atk32/def8) 损血21 | (8,11)@MT10 | 40 | 25 | 25 | {'yellowKey': 1} |
| 1648 | 开门(耗yellowKey×1) @(9, 10) | (9,10)@MT10 | 40 | 25 | 25 | {} |
| 1652 | 打怪 骷髅人(idskeleton hp50/atk42/def6) 损血34 | (9,6)@MT10 | 6 | 25 | 25 | {} |
| 1653 | 拿攻击宝石+1ATK @(10, 6)  | (10,6)@MT10 | 6 | 26 | 25 | {} |

## 3. 重点：拿了哪些 / 跳过哪些 / 守着没拿 / 钥匙花在哪（玩家问 #2）
### 攻防宝石+铁剑铁盾（本区 MT1-MT10 共 16 处）
**拿到的：**
- ✅ ('MT1', 7, 3) 攻击宝石+1ATK
- ✅ ('MT1', 7, 4) 防御宝石+1DEF
- ✅ ('MT3', 2, 1) 防御宝石+1DEF
- ✅ ('MT3', 2, 9) 攻击宝石+1ATK
- ✅ ('MT4', 7, 10) 攻击宝石+1ATK
- ✅ ('MT5', 1, 9) 防御宝石+1DEF
- ✅ ('MT5', 11, 11) 铁剑+10ATK
- ✅ ('MT7', 3, 1) 攻击宝石+1ATK
- ✅ ('MT9', 1, 5) 防御宝石+1DEF
- ✅ ('MT9', 6, 5) 攻击宝石+1ATK
- ✅ ('MT9', 9, 7) 铁盾+10DEF
- ✅ ('MT10', 2, 6) 防御宝石+1DEF
- ✅ ('MT10', 10, 6) 攻击宝石+1ATK
**擦肩没拿（曼哈顿≤1，走到隔壁却没踏上）：**
- （无）
**到过该层但绕开了（曼哈顿>1）：**
- ○ ('MT6', 4, 9) 防御宝石+1DEF（最近 3 格）
- ○ ('MT8', 4, 10) 攻击宝石+1ATK（最近 4 格）
- ○ ('MT8', 5, 11) 防御宝石+1DEF（最近 6 格）
**整层没进、自然没拿：**
- （无）

### 铁剑 / 铁盾 专项（+10 装备）
- 铁剑+10ATK @('MT5', 11, 11)：✅拿到
- 铁盾+10DEF @('MT9', 9, 7)：✅拿到

### 钥匙花在哪
- 起点持钥：{}　→　终态持钥：{}
- **开门耗钥事件：**
  - 步#28 开门(耗yellowKey×1) @(1, 5) → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#91 开门(耗yellowKey×1) @(5, 3) → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#110 开门(耗yellowKey×1) @(10, 8) → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#162 开门(耗yellowKey×1) @(8, 11) → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#167 开门(耗yellowKey×1) @(11, 9) → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#307 开门(耗yellowKey×1) @(4, 7) → 当刻持钥 {'blueKey': 1}
  - 步#321 开门(耗yellowKey×1) @(1, 7) → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#345 开门(耗yellowKey×1) @(8, 8) → 当刻持钥 {'blueKey': 1}
  - 步#399 开门(耗yellowKey×1) @(8, 7) → 当刻持钥 {'blueKey': 1}
  - 步#448 开门(耗yellowKey×1) @(11, 1) → 当刻持钥 {'blueKey': 1}
  - 步#478 开门(耗yellowKey×1) @(6, 1) → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#483 开门(耗yellowKey×1) @(4, 3) → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#485 开门(耗yellowKey×1) @(3, 3) → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#508 开门(耗yellowKey×1) @(1, 4) → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#510 开门(耗yellowKey×1) @(2, 4) → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#521 开门(耗yellowKey×1) @(4, 4) → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#528 开门(耗yellowKey×1) @(6, 8) → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#530 开门(耗yellowKey×1) @(7, 8) → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#533 开门(耗yellowKey×1) @(9, 8) → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#555 开门(耗yellowKey×1) @(11, 8) → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#566 开门(耗yellowKey×1) @(3, 6) → 当刻持钥 {'blueKey': 1}
  - 步#595 开门(耗yellowKey×1) @(7, 6) → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#676 开门(耗yellowKey×1) @(5, 6) → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#691 开门(耗yellowKey×1) @(1, 6) → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#697 开门(耗yellowKey×1) @(1, 2) → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#706 开门(耗yellowKey×1) @(2, 1) → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#708 开门(耗yellowKey×1) @(3, 1) → 当刻持钥 {'blueKey': 1}
  - 步#714 开门(耗blueKey×1) @(6, 2) → 当刻持钥 {}
  - 步#727 开门(耗yellowKey×1) @(7, 1) → 当刻持钥 {'yellowKey': 1}
  - 步#762 开门(耗yellowKey×1) @(6, 2) → 当刻持钥 {}
  - 步#778 开门(耗yellowKey×1) @(5, 5) → 当刻持钥 {'yellowKey': 2}
  - 步#977 开门(耗yellowKey×1) @(2, 5) → 当刻持钥 {'yellowKey': 3}
  - 步#1074 开门(耗yellowKey×1) @(7, 11) → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#1078 开门(耗blueKey×1) @(4, 11) → 当刻持钥 {'yellowKey': 3}
  - 步#1088 开门(耗yellowKey×1) @(7, 11) → 当刻持钥 {'yellowKey': 2}
  - 步#1297 开门(耗yellowKey×1) @(8, 2) → 当刻持钥 {'yellowKey': 2}
  - 步#1316 开门(耗yellowKey×1) @(1, 5) → 当刻持钥 {'yellowKey': 1}
  - 步#1337 开门(耗yellowKey×1) @(8, 8) → 当刻持钥 {'yellowKey': 1}
  - 步#1402 开门(耗yellowKey×1) @(2, 4) → 当刻持钥 {'yellowKey': 1}
  - 步#1410 开门(耗yellowKey×1) @(2, 7) → 当刻持钥 {'yellowKey': 1}
  - 步#1433 开门(耗yellowKey×1) @(5, 6) → 当刻持钥 {'yellowKey': 2}
  - 步#1438 开门(耗yellowKey×1) @(9, 6) → 当刻持钥 {'yellowKey': 1}
  - 步#1624 开门(耗yellowKey×1) @(1, 10) → 当刻持钥 {'yellowKey': 2}
  - 步#1629 开门(耗yellowKey×1) @(3, 8) → 当刻持钥 {'yellowKey': 1}
  - 步#1648 开门(耗yellowKey×1) @(9, 10) → 当刻持钥 {}
- **沿途捡钥事件：**
  - 步#11 拿钥匙 blueKey×1 → 当刻持钥 {'blueKey': 1}
  - 步#12 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#14 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#16 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#18 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#20 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 5, 'blueKey': 1}
  - 步#34 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 5, 'blueKey': 1}
  - 步#311 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#312 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#389 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#433 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#453 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#454 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#455 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#456 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#492 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#493 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#514 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#515 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#516 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#517 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 5, 'blueKey': 1}
  - 步#525 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 5, 'blueKey': 1}
  - 步#586 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1, 'blueKey': 1}
  - 步#587 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#611 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2, 'blueKey': 1}
  - 步#612 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#680 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#681 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#717 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1}
  - 步#721 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2}
  - 步#765 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 1}
  - 步#766 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2}
  - 步#767 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3}
  - 步#788 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3}
  - 步#875 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 4}
  - 步#983 拿钥匙 blueKey×1 → 当刻持钥 {'yellowKey': 3, 'blueKey': 1}
  - 步#985 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 4, 'blueKey': 1}
  - 步#1096 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3}
  - 步#1322 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2}
  - 步#1340 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2}
  - 步#1405 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2}
  - 步#1414 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2}
  - 步#1415 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3}
  - 步#1442 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 2}
  - 步#1562 拿钥匙 yellowKey×1 → 当刻持钥 {'yellowKey': 3}

## 4. 最后停在 MT10 哪、为什么过不了 boss（玩家问 #3）
- **boss（本层队长）**：骷髅队长(idskeletonCaptain) hp100/atk65/def15 special[]
- **终态停点**：MT10(10,6) HP=6 ATK=26 DEF=25
- **打 boss 这一战的模型损血**（boss_toll，按终态 atk26/def25）= **360**　vs 终态 HP=**6**
  - → 仅这一战就要掉 360 血，手里只有 6，**差 354 血**（还没算到 boss 前路上损血）。
- 最宽口径兄弟态 maxHP@MT10：HP=165 ATK=24 DEF=23 → 该属性下 boss_toll=462，仍差 297 血。
- 说明：cut 态是 beam 截断点，动作串止于该 MT10 格、并未实际推进 boss 埋伏序列；上面 boss_toll 是引擎战斗模型对【单挑队长那一战】的损血，仅供看「差多少」。

## 5. 完整动作序列（方向键，可照走；先走完强制开局噩梦再接此串）
```
RRRUUUUUUUULUURDRUDDLDDLLLLDDDDDURDUULUURRRDRDDDDDLLLLUUUUUUUUURRRRRRRRRDDDDDDDLLLLLLUUUUULLLLLRRRRDDDDDRRRRRDDDDUUURUUUUUUULLLLLLLLLLDDDDDDDDDRRRUUUUUURRRDDDDDDRRRRUUUULLLLLLLLLLRRRRRRRRRRDDDDLLUUUUUULLDLDDDDDLLLLUUUUUUUUURRRRRRRRRDDDDDDDLDDDLURUURUUUUUUULLLLLLLLLLDDDDDDDDDRRRUUUUUURRRDDDDDDRRRUUULLLLLLLDDDDRDUULUULLLDDDDDRRRRUUUUURRRRRDDLLLDDDDRRRRLLLUUURRRUULLLLLDDDDDLLLLLUUURRRDDLDDUURUURRRRDDDDLRRULUULLLLLLLDDDDRRRRUUUUUUUUUDDDDRRRRRUUUUULLLLDDDRULUURRRDDDDDLLLLLUUUUULLLDDDLLRDDDLLLUDRRRUUULLLUUDDRRRRRUUULDRDDRRRDDDDRRRRRRRRDULLDDDLURUURRDDDUUUUULLLLLLLLUUUUUUDDDDDRRRRRRUUUUUDDDDDLLDDDDDDUUUUURRDDDDDUUUUURRDDDDDUULLLLLUUUULLLLLDDRRLLUURRRRRDDDDRRRRRDDDUUUULLLLLLDDDDDDUUUUULLLLUUUUUUDDDDUUURURRRRRDRUDDDRDLULRUURURRRRRDDDLDDDLDURUURUUULLDRULLLDLLURDDDLLLRRRUUUDDDLLRRDULLLLULDLRRRRURUULURRLLULLLDLDDDDRRRLLLUUUUUDDDDRRRRRRRRRRDDDDDUULLLLLUUUULLLLLUUUDRRRDDDLLDDDRRLLLURUURRUUUUURRDDDDDRRRRRUUUUULLLDRURRDDDDDLLLLLDDDDDLLLLLUUURRRDDDLDRUUUURRRRDDDRDLUUUULLLLLULLURUUUULURDRDLDDDDLDDDDRRRRUUUUUUUUUULLDDLLLUUDDRRRRRDDDDRRRRRDDDUUUULLLLLLLLLLUUUUURURRRRDDDRDDDDDDLLLLLLLUDRRRRRRRRRRLLUUDDLLUUUUUUULUULURLULLLDLUDDDDRRRRRRRRRRDDDDDUULLLLLUUUULLLLLUUUDRRUURRRDDDDDDDDDDLLLLLUUURRRRRRRRRRDDDDLLUUUUUULLDLDDDDDLLLLUUUUUUUUURRRRRRRRRDDDDDDDLDDDRULUURUUUUUUULLLLLLLLLLDDDDDDDDDRRRUUUUUURRRUUURRRURDLLLDDDLLLLLLLUUUURULDDDDRRRRRRRDDDRRRRUDLLLUUULLDLDDDDDLLLLUUUUUUUUURRRRRRRRRDDDDDDDLLLLLLUUUUULLDLDDDLRRDLDDDDRDLLUURUUUUUURRRDDDRRRRRUUUULDLUDRRDDLLLLDDRRRRRRUUUUUUULLLLLLLLLLDDDDDDDDDRRRUUUUUURRRDDDDDDRRRUUULLLLLLLLLLDDDDRRRRUUUUUUUUUULLDDLLLUUDDRRRRRUUURRRRLLLLDDDDDDDRRRRRDDDUUUULLLLLLLLLLUUUUURURRRRDDDRDDDDDDLLLLLLUUURRDUULRDDDDDRRURRDRRUUUUUUR
```
- 合计 1653 步：U×440 D×439 L×384 R×390
