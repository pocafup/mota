"""【想法3·只读·第一阶段：玩家决策序列检测+映射验证】

用玩家自己打的通关路线 51_20260529133740.h5route 当【标尺】，反推算法参数空间。
本文件是【第一阶段】：沿玩家 token 流重放，把玩家在【一区(MT1-MT10)】做的每个【边界算子跨越】
(杀怪/开门/上下楼/触发)检测出来，并映射到缩点商图 _boundary_ops 的候选算子上，验证
"token 流 → 商图算子" 这条映射对不对(每个跨越能不能在该决策态的候选算子里找到)。

口径(与 solver/quotient.py、probe_dissect_score.py 完全一致)：
  · 决策态 s0 = 进入当前自由块后 _absorb(吸光块内免费道具)的规范态；候选 = _boundary_ops(s0, cross_floor=True)。
  · 玩家"跨越"= 一个 token 让地图发生【杀怪/开门/换层/触发改图】之一(纯移动/纯拾道具不算跨越)。
  · 跨越检测【不靠】floodfill 推断，而是直接 diff step 前后【当前层 entities/terrain 网格 + current_floor】，
    最稳健、不依赖英雄移动细节：怪格 nonzero→0(且 prev 是怪)=杀；门格 door→非door=开门；换层=current_floor 变；
    其余 terrain/entity 变(小偷移位/机关关门)=触发。拾道具(item→0)不算跨越。

为什么不靠玩家路线"学走法"：CLAUDE.md 红线——存档只作【正确性校验+基准下界】，绝不让求解器模仿其走法。
本探针把玩家路线当【标尺/校准工具】反推参数、找结构盲区，是【分析】，不入搜索循环、不改产品码。

跑法：python -u extract/probe_player_decisions.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from lzstring import LZString
from decode_route import parse_rle_route
from sim.simulator import step, _copy_state, DOOR_KEY_MAP
from solver.quotient import _free_cells, _boundary_ops, _absorb
from seg_experiment import build_initial_state

ROOT = Path(__file__).parent.parent
ROUTE = ROOT / "51_20260529133740.h5route"        # 玩家通关串(显式按名加载、不靠 glob 顺序)
OPENING_PREFIX = 83                                # tokens[:83]=强制开局噩梦→落 MT3 入口(与 build_start 同口径)
ZONE1_MAX = 10                                     # 一区=MT1..MT10；首次踏入 MT11+ 即出区、停检测

DELTA = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}


def fidx(fid):
    m = re.match(r"MT(\d+)$", fid or "")
    return int(m.group(1)) if m else 10 ** 6


def load_player_tokens():
    raw = ROUTE.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def build_entry(tokens):
    """玩家路线重放到 MT3 入口(tokens[:83])= 求解器起点 = 玩家在第 83 token 的态。
    _single_floor_copy=False 全程多层安全深拷(跨层重放/diff 不受非当前层引用共享影响)。"""
    s = build_initial_state()
    s._single_floor_copy = False
    for tok in tokens[:OPENING_PREFIX]:
        s = step(s, tok)
    assert s.current_floor == "MT3", s.current_floor
    return s


def op_label(state, op):
    """算子人读简述：kind + 目标格上是什么(怪 id / 门类型 / 楼梯去向)。"""
    kind, ox, oy, fx, fy, mv = op
    fl = state.floor
    if kind == "kill":
        mid = fl._tile_to_enemy.get(fl.entities[oy][ox])
        return f"杀怪[{mid}]@({ox},{oy})"
    if kind == "door":
        t = fl.terrain[oy][ox]
        return f"开门[{DOOR_KEY_MAP.get(t)}]@({ox},{oy})"
    if kind == "stair":
        dest = fl.change_floor.get(f"{ox},{oy}")
        return f"楼梯@({ox},{oy})→{dest}"
    if kind == "autoopen":
        return f"自开假墙@({ox},{oy})"
    if kind == "trigger":
        return f"触发事件@({ox},{oy})"
    return f"{kind}@({ox},{oy})"


def establish(state):
    """(重新)进入一个自由块：吸光块内免费道具得规范决策态 s0，枚举其边界候选算子 ops0。
    cross_floor=True：边界上的换层格作 stair 算子(上下楼也是一个决策)。"""
    s0, _ = _absorb(_copy_state(state), step)
    free0 = _free_cells(s0)
    ops0 = _boundary_ops(s0, free0, cross_floor=True)
    return s0, ops0, free0


def grid_snapshot(state):
    fl = state.floor
    return ([row[:] for row in fl.entities], [row[:] for row in fl.terrain],
            fl._tile_to_enemy)


def detect_crossing(prev, s, prev_fid, prev_ent, prev_ter, tile_to_enemy, tok):
    """返回 (kind, cell, detail) 或 None。cell=(ox,oy)(stair 时为换层格、无则 None)。
    优先级：换层 > 杀怪 > 开门 > 触发(其余改图)。拾道具/纯移动 → None。"""
    new_fid = s.current_floor
    if new_fid != prev_fid:
        # 换层三分类(引擎实证·非猜测)：
        #  · event 事件传送：上一 token 的事件 setValue 了 pending_floor_change(本步 step 开头结算)。
        #    商图【排除】事件传送(MT3重置/剧情)——结构外。
        #  · fly 飞行楼传：FLOOR:MTn 飞行魔杖 token(本塔一区玩家用 30 次)。商图【无飞行边】(留待第二步)——结构外。
        #  · stair 真楼梯：方向移动踏上 change_floor 格、引擎当步立即 _apply_stair_change(simulator.py:813)。
        #    楼梯格 = 跨越前英雄格 + 移动方向，按 prev 层静态 change_floor 校验。商图 cross_floor=True 含此边。
        if prev.pending_floor_change is not None:
            return ("teleport", None, f"{prev_fid}→{new_fid}(事件传送)")
        if isinstance(tok, str) and tok.startswith("FLOOR"):
            return ("fly", None, f"{prev_fid}→{new_fid}(飞行楼传 {tok})")
        cf = prev.floor.change_floor
        if tok in DELTA:
            c = (prev.hero.x + DELTA[tok][0], prev.hero.y + DELTA[tok][1])
            if f"{c[0]},{c[1]}" in cf:
                return ("stair", c, f"{prev_fid}→{new_fid}")
        return ("fly", None, f"{prev_fid}→{new_fid}(非楼梯·飞行/传送 tok={tok})")
    # 同层：diff 网格
    nfl = s.floor
    kills, doors, others = [], [], []
    H, W = len(prev_ent), len(prev_ent[0])
    for y in range(H):
        for x in range(W):
            pe, ne = prev_ent[y][x], nfl.entities[y][x]
            if pe != ne:
                if ne == 0 and tile_to_enemy.get(pe) is not None:
                    kills.append((x, y))
                elif tile_to_enemy.get(ne) is not None:
                    others.append(("怪现身", x, y))      # 小偷移位等
                # else: 拾道具(item→0) 或道具现身 → 非跨越
            pt, nt = prev_ter[y][x], nfl.terrain[y][x]
            if pt != nt:
                if DOOR_KEY_MAP.get(pt) is not None and DOOR_KEY_MAP.get(nt) is None:
                    doors.append((x, y))
                else:
                    others.append(("地形变", x, y))       # 关门(floor→door)/机关
    if kills:
        return ("kill", kills[0], f"杀{len(kills)}怪" + (f"+连带{len(doors)}门/{len(others)}图变" if (doors or others) else ""))
    if doors:
        return ("door", doors[0], f"开{len(doors)}门" + (f"+连带{len(others)}图变" if others else ""))
    if others:
        k, ox, oy = others[0]
        return ("trigger", (ox, oy), f"{k}×{len(others)}")
    return None


def match_op(kind, cell, ops0, s0):
    """把检测到的跨越映射到 ops0 里的候选算子。返回 (matched_op 或 None, 说明)。"""
    if kind in ("fly", "teleport"):
        # 结构外：商图无飞行边、排除事件传送 → 任何参数都复现不了(Idea3 结构盲区)。
        return None, ("商图无飞行边(结构外)" if kind == "fly" else "商图排除事件传送(结构外)")
    if kind == "stair":
        stairs = [op for op in ops0 if op[0] == "stair"]
        if cell is not None:
            for op in stairs:
                if (op[1], op[2]) == cell:
                    return op, "格匹配"
        return None, f"楼梯格{cell}不在 stair 候选{[(o[1], o[2]) for o in stairs]}"
    # kill/door/trigger/autoopen：按 (ox,oy) 匹配同 kind
    for op in ops0:
        if op[0] == kind and (op[1], op[2]) == cell:
            return op, "格+kind匹配"
    # kind 不符但格匹配(例如 autoopen 假墙被检测为地形变 trigger)
    for op in ops0:
        if (op[1], op[2]) == cell:
            return op, f"格匹配(检测{kind}/候选{op[0]})"
    return None, f"{kind}{cell}不在候选"


def detect(tokens, verbose=True):
    entry = build_entry(tokens)
    h = entry.hero
    if verbose:
        print("=" * 100)
        print(f"玩家决策检测·一区(MT1-MT10)  路线={ROUTE.name}  总 token={len(tokens)}")
        print(f"起点(tokens[:{OPENING_PREFIX}]→开局噩梦后): {entry.current_floor}({h.x},{h.y}) "
              f"HP={h.hp} ATK={h.atk} DEF={h.def_} keys={ {k: v for k, v in h.keys.items() if v} }")
        print("=" * 100)

    s = entry
    block_entry = s
    s0, ops0, free0 = establish(s)
    block_tok = OPENING_PREFIX

    decisions = []
    i = OPENING_PREFIX
    while i < len(tokens):
        tok = tokens[i]
        prev = s
        prev_fid = prev.current_floor
        prev_ent, prev_ter, t2e = grid_snapshot(prev)
        s = step(prev, tok)
        cr = detect_crossing(prev, s, prev_fid, prev_ent, prev_ter, t2e, tok)
        if cr is not None:
            kind, cell, detail = cr
            matched, why = match_op(kind, cell, ops0, s0)
            ph = prev.hero
            dec = dict(
                idx=len(decisions) + 1, tok_i=i, tok=tok,
                block_floor=prev_fid, block_tok=block_tok,
                kind=kind, cell=cell, detail=detail,
                matched=matched is not None, matched_op=matched, why=why,
                n_ops=len(ops0),
                ops_kinds={k: sum(1 for o in ops0 if o[0] == k)
                           for k in ("stair", "kill", "door", "autoopen", "trigger")},
                p_hp=ph.hp, p_atk=ph.atk, p_def=ph.def_,
                p_keys={k: v for k, v in ph.keys.items() if v},
                s0=s0, ops0=ops0, free0=free0,
                s0_hp=s0.hero.hp, s0_atk=s0.hero.atk, s0_def=s0.hero.def_,
            )
            dec["label"] = op_label(s0, matched) if matched is not None else f"{kind}@{cell}(未匹配)"
            decisions.append(dec)
            # 重建块
            block_entry = s
            s0, ops0, free0 = establish(s)
            block_tok = i + 1
        # 出区停：首次踏入 MT11+
        if fidx(s.current_floor) > ZONE1_MAX:
            if verbose:
                print(f"\n[出区] tok[{i}] 踏入 {s.current_floor}(>MT{ZONE1_MAX}) → 停止一区决策检测。")
            break
        i += 1

    return decisions, s


def main():
    tokens = load_player_tokens()
    decisions, end_state = detect(tokens, verbose=True)

    # 验证表
    print(f"\n一区共检测到 {len(decisions)} 个边界算子跨越(决策)：")
    print(f"  {'#':>3} {'tok':>5} {'层':>5} {'类型':>7} {'目标格':>9} {'玩家HP/A/D':>13} "
          f"{'候选数':>5} {'映射':>4} {'选中算子':>22}  {'明细/why':<22}")
    miss = []
    by_kind = {}
    for d in decisions:
        by_kind[d["kind"]] = by_kind.get(d["kind"], 0) + 1
        ok = "✓" if d["matched"] else "✗"
        if not d["matched"]:
            miss.append(d)
        cell = d["cell"] if d["cell"] is not None else "—"
        print(f"  {d['idx']:>3} {d['tok_i']:>5} {d['block_floor']:>5} {d['kind']:>7} "
              f"{str(cell):>9} {d['p_hp']:>5}/{d['p_atk']:>2}/{d['p_def']:>2} "
              f"{d['n_ops']:>5} {ok:>4} {d['label']:>22}  {(d['detail'] + ' | ' + d['why']):<22}")

    print("\n" + "-" * 100)
    print(f"按类型：{by_kind}")
    structural = [d for d in miss if d["kind"] in ("fly", "teleport")]
    method_miss = [d for d in miss if d["kind"] not in ("fly", "teleport")]
    matched_n = len(decisions) - len(miss)
    print(f"映射成功(商图算子可表达)：{matched_n}/{len(decisions)}")
    print(f"结构外(玩家用了商图【没有】的动作 → 任何参数都复现不了)：{len(structural)} 个")
    print(f"  · 飞行楼传 fly(FLOOR:MTn 飞行魔杖，商图无飞行边·留待第二步)："
          f"{sum(1 for d in structural if d['kind'] == 'fly')} 个")
    print(f"  · 事件传送 teleport(商图排除剧情传送)：{sum(1 for d in structural if d['kind'] == 'teleport')} 个")
    for d in structural:
        print(f"      #{d['idx']} tok[{d['tok_i']}] {d['detail']}")
    if method_miss:
        print(f"⚠ 应可表达却未匹配 {len(method_miss)} 个(查是否 MT10 boss 埋伏链动态机关 / 方法盲点)：")
        for d in method_miss:
            print(f"    #{d['idx']} tok[{d['tok_i']}] {d['block_floor']} {d['kind']}@{d['cell']} "
                  f"detail={d['detail']} why={d['why']} 候选kinds={d['ops_kinds']}")
    else:
        print("✅ 所有【非飞行/非传送】跨越都映射到了商图候选算子(楼梯/杀怪/开门/触发)。")
    # 楼层访问序列
    seq = []
    for d in decisions:
        if not seq or seq[-1] != d["block_floor"]:
            seq.append(d["block_floor"])
    print(f"\n决策所在层序列：{' → '.join(seq)}")
    return decisions


if __name__ == "__main__":
    main()
