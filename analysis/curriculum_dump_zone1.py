"""【课程学习·只读支撑脚本①】dump 真实存档(剩余HP=14382)在一区(MT1-MT10)的关键节点状态序列。

用途（§S27 课程学习框架的"切段地基"）：把真实通关路径在一区的轨迹拆出来，看清
  ①攒攻防阶段(MT1-MT9 反复回访)的属性爬升；②打一区 boss(MT10 Visit5)的完整流程节点。
为"切段方案"提供数据事实（哪几段、每段起点状态/终点目标），并为打 boss 段验证定起点。

只读：复用 verify_all_checkpoints.build_initial_state / load_tokens / sim.step，绝不改产品码。
"""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # 让 load_tokens 的 Path('.').glob('51_*.h5route') 命中

from analysis.verify_all_checkpoints import build_initial_state, load_tokens
from sim.simulator import step
from solver.quotient import _free_cells, partition_floor_blocks, _boundary_ops


def snap(s):
    h = s.hero
    keys = {k: v for k, v in h.keys.items() if v}
    return (f"{s.current_floor}({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_} "
            f"钥={keys} 金={h.gold} kills={h.kill_count}")


def main():
    tokens = load_tokens()
    print(f"route 总 token 数 = {len(tokens)}")

    # ── 1) 一区楼层访问序列（攒攻防轨迹）─────────────────────────────
    s = build_initial_state()
    prev = s.current_floor
    print("\n========== 一区楼层访问序列（每次 current_floor 变化）==========")
    print(f" start          {snap(s)}")
    last_mt10_entry = None
    mt10_visits = 0
    for i, tok in enumerate(tokens[:1256]):
        s = step(s, tok)
        if s.current_floor != prev:
            print(f" tok[{i:4}] {prev:>4}->{s.current_floor:<4} {snap(s)}")
            if s.current_floor == "MT10":
                mt10_visits += 1
                last_mt10_entry = i
            prev = s.current_floor
    print(f"\n MT10 共访问 {mt10_visits} 次；最后一次(打boss Visit)进入 tok = {last_mt10_entry}")

    # ── 2) 打 boss 段逐 token 状态（Visit5：进 MT10 → 进 MT11）─────────
    print("\n========== 打 boss 段逐 token 状态（tok 1160-1255）==========")
    s = build_initial_state()
    for i, tok in enumerate(tokens[:1256]):
        s = step(s, tok)
        if 1160 <= i <= 1255:
            print(f" tok[{i:4}] {str(tok):7} {snap(s)}")

    # ── 3) 打 boss 段起点(最后一次进 MT10)的块结构 / 可达算子 ──────────
    if last_mt10_entry is not None:
        s = build_initial_state()
        for tok in tokens[:last_mt10_entry + 1]:
            s = step(s, tok)
        print(f"\n========== 打 boss 段起点状态（tok {last_mt10_entry}，刚进 MT10）==========")
        print(f" {snap(s)}")
        free = _free_cells(s)
        print(f" 英雄当前自由块大小 = {len(free)} 格")
        print(f" 自由块格(排序前20) = {sorted(free)[:20]}")
        blocks = partition_floor_blocks(s)
        print(f" 整层零损血连通块数 = {len(blocks)}（块大小: "
              f"{sorted((len(b) for b in blocks), reverse=True)}）")
        ops = _boundary_ops(s, free, cross_floor=True)
        kinds = {}
        for op in ops:
            kinds.setdefault(op[0], []).append((op[1], op[2]))
        print(f" 当前自由块边界算子（cross_floor=True）：")
        for k, v in sorted(kinds.items()):
            print(f"   {k:9}: {len(v)} 个 -> {v}")


if __name__ == "__main__":
    main()
