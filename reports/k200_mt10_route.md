# K=200 V_zone 到达 MT10 最优候选路线（只导出，未分析）

- 来源：复跑 `probe_crossfloor_beam.py --beam 200 --score vzone` 的确定性搜索，on_admit 捕获到 MT10 的最优候选（最大 HP）。
- 搜索：cross_floor=True，beam_k=200，max_states=120000，hit_cap=True，耗时 419.8s。
- 起点：MT3(2,11) HP=400 ATK=10 DEF=10（穿过 82 token 开局噩梦后首个自由态）。
- 最优候选终态：MT10 HP=720 ATK=23 DEF=21 mdef=0，动作 1276 步。
- **这条是引擎重放过的**：solver.verify.replay 独立重放核对 → ✅ 一致（引擎重放=权威）
- 全部到达 MT10 的去重态 4 个：[(720, 23, 21, 0), (703, 23, 21, 0), (687, 23, 21, 0), (678, 23, 21, 0)]

## 1. 完整可照走动作序列

> 每个字符=一步 step token（移动/换层/触发都由引擎 step 解释）。原始串另存 `k200_mt10_route.json`。

```
RRRUUUUUUUULUURDRUDDLDDDDDDDDLLLLUUUUUUUUURRRRRRRRRDDDDDDDLDDDDUUURUUUUUUULLLLLLLLLLDDDDDDDDDRRRUUUUUURRRDDDDDDRRRRUUUULLLLLLLLLLDDDDDRRRRUUUUURRRRRDDLLLDDDDRRRRLLLUUURRRUULLLLLUUUUDDDDRRRRRUUUUULLLDDLDRUUURRDDDDDLLLLLDDDDDLLLLLUUURRRRRRRDDDDLRRULUULLLLDDDDRDUULLDDUURUULLLDDDDRRRRUUUUUUUUUULLLDDLLLLUUDDRRRRRRRRDDDDRUUUULLUUULDRDDRRDDDDRRRRDDDLURUULLLUUUULLLLLUUUDRRRDDDDLLLUDRRRUUULLLUUDDRRRRRDDDDRRRRRRDDDUUUUULLLLDDDDDDUUUUULLLLUUUUUUDDDDDRRRRRRUUUUUDDDDDLLLLDDDDDDUUUUURRRRDDDDDUUUUULLLLLLDDDDDDLLUUUUUUUUUUUURURRRRRDRUDDDRDLULRUUULULLLDLDDDDUUURURRRDRDDDLLLRRRUUUDDRRRRRRRUUUDDDLDDDLDURUULLLLUULURRLLURDDRRRRRUULRDDLLLLDLLLRRDULLLLULDLRRRRRRDDDDDDRRRRRLLUUDDLLUUUUUUULUULURLULLLDLDDDDRRLLUUUUUDDDDDDDDDRRUUUUURRRRRRRRDDDDDUULLLLLUUUULLLLLUUUDRRUURRRDDDDDDDDDDLLLLLUUURRRRRRRRRRDDDDLLUUUUUULLDLDDDDDLLLLUUUUUUUUURRRRRRRRRDDDDDDDLLLLLLUUUUULLLLLRRRRDDDDDRRRRRDDLDRRULUURUUUUUUULLLLLLLLLLDDDDDDDDDRRRUUUUUURRRDDDDDDRRRUUULLLLLLLDDDLDRUUUULLLDDDDRRRRUUUUURRRRRUUUUULLDLURRRDDDDDLLLLLUUUUULLDDLLLUUDDDDRRLLUURRRRRDDDDRRRRRDDDUUUULLLLLLLLDDDDDLLUUUUUUUUUUDDDDRRRLLLUUUUUDDDDDDDDDRRUUUUURRRRRRRRDDDDDUULLLLLUUUUUUURRRLLLDDDLLLLLUUUDRRUURRRDDDDDDDDDDLLLLLUUUUURUUUULURDRDLDDDDLDDDDRRRRUUUUUUUUUULLDDLLLUUDDRRRRRDDDDRRRRRDDDUUUULLLLLLLLDDDDDLLUUUUUUUUUURURRRRDDDRDDDDDDLLLLLLLUDL
```

## 2. 逐里程碑（每个关键节点：换层/拿装备宝石/拿钥匙/开门/打怪/到 MT10/停点）

| # | 第几步 | token | 事件 | 层 | 坐标 | HP | ATK | DEF | 钥匙 | 道具 |
|---|---|---|---|---|---|---|---|---|---|---|
| 【起点】 | 0 | `—` | | MT3 | (2,11) | 400 | 10 | 10 | — | fly:1,I333:1 |
| 钥匙 {}→{'blueKey': 1} | 11 | `U` | | MT3 | (5,3) | 400 | 10 | 10 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 12 | `L` | | MT3 | (4,3) | 400 | 10 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 14 | `U` | | MT3 | (4,1) | 600 | 10 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 16 | `D` | | MT3 | (5,2) | 800 | 10 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 18 | `U` | | MT3 | (6,1) | 1000 | 10 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 5, 'blueKey': 1} | 20 | `D` | | MT3 | (6,3) | 1000 | 10 | 10 | yellowKey:5,blueKey:1 | fly:1,I333:1 |
| 换层 MT3→MT2 | 33 | `L` | | MT2 | (1,10) | 1000 | 10 | 10 | yellowKey:5,blueKey:1 | fly:1,I333:1 |
| 换层 MT2→MT1 | 42 | `U` | | MT1 | (2,1) | 1000 | 10 | 10 | yellowKey:5,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 5, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 60 | `D` | | MT1 | (10,8) | 1000 | 10 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 1000→888） | 62 | `D` | | MT1 | (10,10) | 888 | 10 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 换层 MT1→MT2 | 84 | `L` | | MT2 | (1,2) | 1088 | 10 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 换层 MT2→MT3 | 93 | `D` | | MT3 | (2,11) | 1088 | 10 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 1088→1064） | 104 | `R` | | MT3 | (7,5) | 1064 | 10 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 1064→1014） | 110 | `D` | | MT3 | (8,10) | 1014 | 10 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 112 | `R` | | MT3 | (8,11) | 1014 | 10 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 换层 MT3→MT4 | 115 | `R` | | MT4 | (11,10) | 1014 | 10 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 117 | `U` | | MT4 | (11,9) | 1014 | 10 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 1014→990） | 127 | `L` | | MT4 | (3,7) | 990 | 10 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 990→940） | 129 | `L` | | MT4 | (1,7) | 940 | 10 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 130 | `D` | | MT4 | (1,7) | 940 | 10 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 换层 MT4→MT5 | 134 | `D` | | MT5 | (2,11) | 940 | 10 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 940→916） | 141 | `U` | | MT5 | (6,8) | 916 | 10 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 916→892） | 144 | `R` | | MT5 | (7,6) | 892 | 10 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 892→842） | 149 | `D` | | MT5 | (11,7) | 842 | 10 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'blueKey': 1} | 154 | `D` | | MT5 | (8,8) | 842 | 10 | 10 | blueKey:1 | fly:1,I333:1 |
| ATK 10→20（拿攻击装备/宝石） | 161 | `R` | | MT5 | (11,11) | 842 | 20 | 10 | blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 842→786） | 179 | `U` | | MT5 | (6,4) | 786 | 20 | 10 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 181 | `U` | | MT5 | (6,2) | 786 | 20 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 786→766） | 194 | `U` | | MT5 | (11,2) | 766 | 20 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'blueKey': 1} | 196 | `L` | | MT5 | (11,1) | 766 | 20 | 10 | blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 766→758） | 199 | `D` | | MT5 | (9,2) | 758 | 20 | 10 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 200 | `D` | | MT5 | (9,3) | 758 | 20 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 201 | `L` | | MT5 | (8,3) | 758 | 20 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 202 | `D` | | MT5 | (8,4) | 758 | 20 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 203 | `R` | | MT5 | (9,4) | 758 | 20 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 换层 MT5→MT4 | 228 | `L` | | MT4 | (1,10) | 758 | 20 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 239 | `D` | | MT4 | (8,7) | 758 | 20 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 758→670） | 241 | `D` | | MT4 | (8,9) | 670 | 20 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| ATK 20→21（拿攻击装备/宝石） | 243 | `L` | | MT4 | (7,10) | 670 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 254 | `D` | | MT4 | (4,7) | 720 | 21 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 720→692） | 256 | `D` | | MT4 | (4,9) | 692 | 21 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 258 | `R` | | MT4 | (5,10) | 692 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 259 | `D` | | MT4 | (5,11) | 692 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 692→684） | 264 | `D` | | MT4 | (3,10) | 684 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 5, 'blueKey': 1} | 265 | `D` | | MT4 | (3,11) | 684 | 21 | 10 | yellowKey:5,blueKey:1 | fly:1,I333:1 |
| 换层 MT4→MT5 | 277 | `D` | | MT5 | (2,11) | 684 | 21 | 10 | yellowKey:5,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 5, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 292 | `L` | | MT5 | (6,1) | 684 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 684→664） | 294 | `L` | | MT5 | (4,1) | 664 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 664→636） | 297 | `L` | | MT5 | (3,3) | 636 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 298 | `L` | | MT5 | (3,3) | 636 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 换层 MT5→MT6 | 302 | `U` | | MT6 | (1,2) | 636 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 305 | `R` | | MT6 | (1,4) | 636 | 21 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 307 | `R` | | MT6 | (2,4) | 636 | 21 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'blueKey': 1} | 310 | `R` | | MT6 | (4,4) | 636 | 21 | 10 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 314 | `D` | | MT6 | (6,6) | 636 | 21 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'blueKey': 1} | 317 | `R` | | MT6 | (6,8) | 636 | 21 | 10 | blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 636→616） | 324 | `U` | | MT6 | (4,3) | 616 | 21 | 10 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 325 | `U` | | MT6 | (4,2) | 616 | 21 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 326 | `U` | | MT6 | (4,1) | 616 | 21 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 327 | `L` | | MT6 | (3,1) | 616 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 328 | `D` | | MT6 | (3,2) | 616 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 339 | `R` | | MT6 | (7,8) | 616 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 616→596） | 342 | `D` | | MT6 | (9,9) | 596 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 换层 MT6→MT5 | 364 | `U` | | MT5 | (1,2) | 696 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 369 | `D` | | MT5 | (4,3) | 696 | 21 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 696→668） | 372 | `D` | | MT5 | (4,6) | 668 | 21 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 375 | `L` | | MT5 | (1,6) | 668 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 376 | `U` | | MT5 | (1,5) | 668 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 换层 MT5→MT6 | 388 | `U` | | MT6 | (1,2) | 668 | 21 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 403 | `R` | | MT6 | (9,8) | 668 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 668→648） | 406 | `D` | | MT6 | (11,9) | 648 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 换层 MT6→MT7 | 408 | `D` | | MT7 | (11,10) | 648 | 21 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 411 | `U` | | MT7 | (11,8) | 648 | 21 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 418 | `D` | | MT7 | (7,6) | 648 | 21 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 648→628） | 421 | `D` | | MT7 | (7,9) | 628 | 21 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 628→540） | 422 | `D` | | MT7 | (7,10) | 540 | 21 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 740→652） | 431 | `L` | | MT7 | (4,6) | 652 | 21 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'blueKey': 1} | 433 | `U` | | MT7 | (3,6) | 652 | 21 | 10 | blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 652→624） | 436 | `U` | | MT7 | (3,3) | 624 | 21 | 10 | blueKey:1 | fly:1,I333:1 |
| ATK 21→22（拿攻击装备/宝石） | 438 | `U` | | MT7 | (3,1) | 674 | 22 | 10 | blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 674→578） | 450 | `U` | | MT7 | (9,5) | 578 | 22 | 10 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 453 | `U` | | MT7 | (9,2) | 628 | 22 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 454 | `U` | | MT7 | (9,1) | 628 | 22 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 464 | `D` | | MT7 | (5,6) | 628 | 22 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 628→600） | 467 | `D` | | MT7 | (5,9) | 600 | 22 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 468 | `D` | | MT7 | (5,10) | 600 | 22 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 469 | `D` | | MT7 | (5,11) | 600 | 22 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 600→390） | 479 | `D` | | MT7 | (9,7) | 390 | 22 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 482 | `D` | | MT7 | (9,10) | 590 | 22 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 5, 'blueKey': 1} | 483 | `D` | | MT7 | (9,11) | 590 | 22 | 10 | yellowKey:5,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 5, 'blueKey': 1}→{'yellowKey': 4, 'blueKey': 1} | 495 | `D` | | MT7 | (3,6) | 590 | 22 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 590→582） | 499 | `D` | | MT7 | (3,10) | 582 | 22 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 582→562） | 501 | `L` | | MT7 | (2,11) | 562 | 22 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 562→554） | 503 | `U` | | MT7 | (1,10) | 554 | 22 | 10 | yellowKey:4,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 4, 'blueKey': 1}→{'yellowKey': 3, 'blueKey': 1} | 506 | `U` | | MT7 | (1,8) | 554 | 22 | 10 | yellowKey:3,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3, 'blueKey': 1}→{'yellowKey': 2, 'blueKey': 1} | 509 | `U` | | MT7 | (1,6) | 554 | 22 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 换层 MT7→MT8 | 514 | `U` | | MT8 | (1,2) | 554 | 22 | 10 | yellowKey:2,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2, 'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 517 | `R` | | MT8 | (2,1) | 554 | 22 | 10 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'blueKey': 1} | 519 | `R` | | MT8 | (3,1) | 554 | 22 | 10 | blueKey:1 | fly:1,I333:1 |
| 换层 MT8→MT9 | 524 | `U` | | MT9 | (6,2) | 554 | 22 | 10 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{} | 525 | `D` | | MT9 | (6,2) | 554 | 22 | 10 | — | fly:1,I333:1 |
| 钥匙 {}→{'yellowKey': 1} | 528 | `R` | | MT9 | (7,4) | 554 | 22 | 10 | yellowKey:1 | fly:1,I333:1 |
| ATK 22→23（拿攻击装备/宝石） | 530 | `L` | | MT9 | (6,5) | 554 | 23 | 10 | yellowKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1}→{'yellowKey': 2} | 532 | `L` | | MT9 | (5,4) | 554 | 23 | 10 | yellowKey:2 | fly:1,I333:1 |
| 换层 MT9→MT8 | 536 | `U` | | MT8 | (6,2) | 554 | 23 | 10 | yellowKey:2 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2}→{'yellowKey': 1} | 544 | `D` | | MT8 | (1,2) | 554 | 23 | 10 | yellowKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1}→{} | 558 | `D` | | MT8 | (6,2) | 604 | 23 | 10 | — | fly:1,I333:1 |
| 钥匙 {}→{'yellowKey': 1} | 561 | `L` | | MT8 | (5,4) | 604 | 23 | 10 | yellowKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1}→{'yellowKey': 2} | 562 | `L` | | MT8 | (4,4) | 604 | 23 | 10 | yellowKey:2 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2}→{'yellowKey': 3} | 563 | `L` | | MT8 | (3,4) | 604 | 23 | 10 | yellowKey:3 | fly:1,I333:1 |
| 换层 MT8→MT9 | 569 | `U` | | MT9 | (6,2) | 604 | 23 | 10 | yellowKey:3 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 3}→{'yellowKey': 2} | 573 | `R` | | MT9 | (7,4) | 604 | 23 | 10 | yellowKey:2 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 2}→{'yellowKey': 1} | 575 | `R` | | MT9 | (8,4) | 604 | 23 | 10 | yellowKey:1 | fly:1,I333:1 |
| DEF 10→20（拿防御装备/宝石） | 590 | `D` | | MT9 | (9,7) | 654 | 23 | 20 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT9→MT8 | 603 | `R` | | MT8 | (6,2) | 654 | 23 | 20 | yellowKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 654→654） | 604 | `R` | | MT8 | (7,2) | 654 | 23 | 20 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT8→MT9 | 608 | `R` | | MT9 | (6,2) | 654 | 23 | 20 | yellowKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 654→654） | 618 | `L` | | MT9 | (10,2) | 654 | 23 | 20 | yellowKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1}→{} | 629 | `L` | | MT9 | (5,5) | 654 | 23 | 20 | — | fly:1,I333:1 |
| 打怪 +1（HP 654→654） | 632 | `D` | | MT9 | (7,6) | 654 | 23 | 20 | — | fly:1,I333:1 |
| 打怪 +1（HP 654→636） | 637 | `L` | | MT9 | (3,5) | 636 | 23 | 20 | — | fly:1,I333:1 |
| 钥匙 {}→{'yellowKey': 1} | 639 | `L` | | MT9 | (2,4) | 636 | 23 | 20 | yellowKey:1 | fly:1,I333:1 |
| DEF 20→21（拿防御装备/宝石） | 641 | `L` | | MT9 | (1,5) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 636→619） | 652 | `D` | | MT9 | (7,10) | 619 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1}→{} | 654 | `R` | | MT9 | (7,11) | 619 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 619→586） | 656 | `R` | | MT9 | (9,11) | 586 | 23 | 21 | — | fly:1,I333:1 |
| 钥匙 {}→{'yellowKey': 1} | 662 | `U` | | MT9 | (9,9) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT9→MT8 | 679 | `R` | | MT8 | (6,2) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 636→636） | 691 | `R` | | MT8 | (2,6) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 636→636） | 692 | `R` | | MT8 | (3,6) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT8→MT7 | 699 | `U` | | MT7 | (1,2) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT7→MT6 | 728 | `D` | | MT6 | (11,10) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT6→MT5 | 747 | `U` | | MT5 | (1,2) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT5→MT4 | 770 | `L` | | MT4 | (1,10) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT4→MT3 | 787 | `D` | | MT3 | (10,11) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT3→MT2 | 808 | `L` | | MT2 | (1,10) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT2→MT1 | 817 | `U` | | MT1 | (2,1) | 636 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1}→{} | 845 | `L` | | MT1 | (5,3) | 636 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 686→686） | 867 | `D` | | MT1 | (9,11) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 686→686） | 869 | `R` | | MT1 | (11,11) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT1→MT2 | 891 | `L` | | MT2 | (1,2) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT2→MT3 | 900 | `D` | | MT3 | (2,11) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT3→MT4 | 921 | `R` | | MT4 | (11,10) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 686→686） | 937 | `R` | | MT4 | (4,11) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT4→MT5 | 948 | `D` | | MT5 | (2,11) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 686→686） | 971 | `L` | | MT5 | (8,2) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT5→MT6 | 999 | `U` | | MT6 | (1,2) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 686→686） | 1005 | `R` | | MT6 | (3,6) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT6→MT7 | 1026 | `D` | | MT7 | (11,10) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT7→MT8 | 1055 | `U` | | MT8 | (1,2) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 686→686） | 1062 | `R` | | MT8 | (4,6) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT8→MT7 | 1070 | `U` | | MT7 | (1,2) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT7→MT6 | 1099 | `D` | | MT6 | (11,10) | 686 | 23 | 21 | — | fly:1,I333:1 |
| 打怪 +1（HP 686→653） | 1114 | `R` | | MT6 | (7,1) | 653 | 23 | 21 | — | fly:1,I333:1 |
| 钥匙 {}→{'yellowKey': 1} | 1116 | `R` | | MT6 | (9,1) | 653 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT6→MT5 | 1130 | `U` | | MT5 | (1,2) | 653 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 换层 MT5→MT4 | 1153 | `L` | | MT4 | (1,10) | 653 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 打怪 +1（HP 653→620） | 1159 | `R` | | MT4 | (2,5) | 620 | 23 | 21 | yellowKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1}→{} | 1160 | `U` | | MT4 | (2,5) | 620 | 23 | 21 | — | fly:1,I333:1 |
| 钥匙 {}→{'blueKey': 1} | 1166 | `R` | | MT4 | (2,1) | 670 | 23 | 21 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{'yellowKey': 1, 'blueKey': 1} | 1168 | `R` | | MT4 | (3,2) | 670 | 23 | 21 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 换层 MT4→MT5 | 1179 | `D` | | MT5 | (2,11) | 670 | 23 | 21 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 换层 MT5→MT6 | 1202 | `U` | | MT6 | (1,2) | 670 | 23 | 21 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 换层 MT6→MT7 | 1221 | `D` | | MT7 | (11,10) | 670 | 23 | 21 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 换层 MT7→MT8 | 1250 | `U` | | MT8 | (1,2) | 670 | 23 | 21 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 换层 MT8→MT9 | 1256 | `R` | | MT9 | (6,2) | 670 | 23 | 21 | yellowKey:1,blueKey:1 | fly:1,I333:1 |
| 钥匙 {'yellowKey': 1, 'blueKey': 1}→{'blueKey': 1} | 1267 | `L` | | MT9 | (7,11) | 670 | 23 | 21 | blueKey:1 | fly:1,I333:1 |
| 钥匙 {'blueKey': 1}→{} | 1271 | `L` | | MT9 | (4,11) | 670 | 23 | 21 | — | fly:1,I333:1 |
| 换层 MT9→MT10 | 1276 | `L` | | MT10 | (1,10) | 720 | 23 | 21 | — | fly:1,I333:1 |
| 【终点/停点】 | 1276 | `—` | | MT10 | (1,10) | 720 | 23 | 21 | — | fly:1,I333:1 |

## 3. 停点

- 动作序列在第 1276 步结束，终态停在 **MT10(1,10)**，HP=720 ATK=23 DEF=21，钥匙=无，累计杀怪=49。
- 这是该候选**首次被 admit 到 MT10 时的快照**（搜索捕获到 MT10 的那一刻）。全程到达 MT10 的去重态仅 4 个，未见更深推进的 MT10 态被 admit。

## 4. 性质 / 终态字段

- 性质：**搜索缩点产出 + 引擎独立重放核对**（动作串经 solver.verify.replay 重放，✅ 一致（引擎重放=权威））。
- 终态字段（引擎重放 rep）：floor=MT10 (x=1,y=10) HP=720 ATK=23 DEF=21 mdef=0 gold=118 钥匙={} 累计杀怪=49。