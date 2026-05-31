"""
全塔切层事件分析：解析完整 route trace，输出 data/games51/floor_transitions.json。

切层类型分类（经 trace 实测修正版）：
  changeFloor   : 走楼梯（UDLR 废输入；途中可能捡道具 ITEM:n）
  centerFly     : 使用 centerFly 道具（ITEM:50 + CHOICE:n → FLOOR:MTx，30-token 窗口）
  keyboard_fly  : 使用键盘快捷键 K49/K50/K52 触发飞行
  unknown_p     : UNK:p 前驱（未知，需源码调查）

注意：
  UNK:Mn:（M1:-M10:）= 领域伤害 per-step 记录，不是切层触发；对应切层仍归 changeFloor。
  ITEM:54(snow)/ITEM:56(superPotion) = 踩到地面道具拾取，不是飞行触发；归 changeFloor。
"""
import json
from pathlib import Path
from lzstring import LZString

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"

MOVE_TOKENS = {"U", "D", "L", "R"}
FLY_ITEM_IDS = {"50"}   # ITEM:50 = centerFly (瞬移)；ITEM:51/52 拾取，由 K49/K50 激活
KB_FLY_TOKENS = {"UNK:K49", "UNK:K49:", "UNK:K50", "UNK:K50:", "UNK:K52", "UNK:K52:"}
# "(help)" 原始字符 '(' 'h' 'e' 'l' 'p' ')' → 解码器输出 UNK:h/e/l/p（括号被跳过）
HELP_TOKENS = {"UNK:h", "UNK:e", "UNK:l", "UNK:p"}
# 非飞行道具直接拾取（ITEM:54=snow, ITEM:56=superPotion 等）→ 视为中性
NONFLIGHT_ITEM_PREFIXES = {"ITEM:"}  # 所有非 fly item


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def decode_full_route() -> list[str]:
    h5route = next(ROOT.glob("51_*.h5route"))
    raw_outer = decompress(h5route.read_text(encoding="utf-8").strip())
    outer = json.loads(raw_outer)
    route_raw = decompress(outer["route"])

    actions = []
    i, n = 0, len(route_raw)
    while i < n:
        c = route_raw[i]
        if route_raw[i:i+3] == "FMT":
            j = i + 3
            while j < n and route_raw[j].isdigit():
                j += 1
            floor_num = route_raw[i+3:j]
            if j < n and route_raw[j] == ":":
                j += 1
            actions.append(f"FLOOR:MT{floor_num}")
            i = j
        elif c in "UDLR":
            i += 1
            j = i
            while j < n and route_raw[j].isdigit():
                j += 1
            count = int(route_raw[i:j]) if j > i else 1
            i = j
            actions.extend([c] * count)
        elif c == "C":
            i += 1
            j = i
            while j < n and route_raw[j].isdigit():
                j += 1
            val = int(route_raw[i:j]) if j > i else 0
            i = j
            actions.append(f"CHOICE:{val}")
        elif c == "I":
            i += 1
            j = i
            while j < n and route_raw[j].isdigit():
                j += 1
            tile_id = route_raw[i:j]
            if j < n and route_raw[j] == ":":
                j += 1
            actions.append(f"ITEM:{tile_id}")
            i = j
        elif c.isalpha():
            j = i + 1
            while j < n and route_raw[j].isdigit():
                j += 1
            tok = route_raw[i:j]
            if j < n and route_raw[j] == ":":
                j += 1
                tok += ":"
            actions.append(f"UNK:{tok}")
            i = j
        else:
            i += 1
    return actions


def _is_neutral(tok: str) -> bool:
    """Token 不影响切层类型判断：UDLR、CHOICE、Mn:领域伤害、ITEM:n道具拾取、(help)字符。"""
    if tok in MOVE_TOKENS or tok.startswith("CHOICE:"):
        return True
    if tok.startswith("UNK:M") and tok.endswith(":"):
        return True   # 领域伤害 per-step
    if tok in HELP_TOKENS:
        return True   # (help) 按钮字符
    if tok.startswith("ITEM:") and tok.split(":")[1] not in FLY_ITEM_IDS:
        return True   # 非飞行道具拾取
    return False


def classify_transition(actions: list[str], floor_idx: int) -> dict:
    """
    分析 FLOOR:MTn token（floor_idx）前 30 token，判断切层类型。
    返回 dict 含 type, trigger_token, waste_inputs, context_before, context_after。
    """
    window = 30
    before = actions[max(0, floor_idx - window): floor_idx]
    after  = actions[floor_idx + 1: floor_idx + 1 + 10]

    # ── 寻找最近的非中性前驱 token ────────────────────────────────────────────
    trigger = None
    for tok in reversed(before):
        if _is_neutral(tok):
            continue
        if tok.startswith("FLOOR:"):
            break      # 遇到上一个楼层标记，停止
        trigger = tok
        break

    # ── 废输入数 = 紧邻 FLOOR 前的连续 UDLR/CHOICE/Mn:/ITEM:54/56 ─────────────
    waste = 0
    for tok in reversed(before):
        if _is_neutral(tok):
            waste += 1
        else:
            break

    # ── 类型判断 ──────────────────────────────────────────────────────────────
    if trigger is None:
        ttype = "changeFloor"
    elif trigger.startswith("ITEM:") and trigger.split(":")[1] in FLY_ITEM_IDS:
        # centerFly = ITEM:50 + CHOICE 在窗口内
        has_choice = any(t.startswith("CHOICE:") for t in before)
        ttype = "centerFly" if has_choice else "changeFloor"
    elif trigger in KB_FLY_TOKENS:
        ttype = "keyboard_fly"
    elif trigger == "UNK:p":
        ttype = "unknown_p"
    else:
        ttype = "anomaly"   # 其他意外情况

    return {
        "type": ttype,
        "trigger_token": trigger,
        "waste_inputs_before_floor_marker": waste,
        "context_before": before[-15:],
        "context_after":  after,
    }


def main():
    actions = decode_full_route()
    print(f"Total actions decoded: {len(actions)}")

    floor_events = [(i, tok) for i, tok in enumerate(actions) if tok.startswith("FLOOR:")]
    print(f"FLOOR tokens found: {len(floor_events)}")

    transitions = []
    for seq_idx, (gidx, tok) in enumerate(floor_events):
        to_floor   = tok[6:]
        from_floor = floor_events[seq_idx - 1][1][6:] if seq_idx > 0 else None

        info = classify_transition(actions, gidx)
        transitions.append({
            "seq":        seq_idx,
            "global_idx": gidx,
            "from_floor": from_floor,
            "to_floor":   to_floor,
            "type":       info["type"],
            "trigger_token": info["trigger_token"],
            "waste_inputs_before_floor_marker": info["waste_inputs_before_floor_marker"],
            "context_before": info["context_before"],
            "context_after":  info["context_after"],
        })

    # ── 统计 ──────────────────────────────────────────────────────────────────
    type_counts: dict[str, int] = {}
    for t in transitions:
        type_counts[t["type"]] = type_counts.get(t["type"], 0) + 1

    floor_visit_count: dict[str, int] = {}
    for t in transitions:
        k = t["to_floor"]
        floor_visit_count[k] = floor_visit_count.get(k, 0) + 1

    multi_visit = {k: v for k, v in floor_visit_count.items() if v > 1}

    anomalies = [t for t in transitions if t["type"] not in ("changeFloor", "centerFly", "keyboard_fly")]

    # 找每种方式的代表示例（第一个）
    examples: dict[str, dict] = {}
    for t in transitions:
        if t["type"] not in examples:
            examples[t["type"]] = t

    # ── 构建输出 ──────────────────────────────────────────────────────────────
    result = {
        "_note": (
            "全塔切层事件清单（共 220 次）。"
            "type: changeFloor=楼梯（途中可能有 Mn:/ITEM 噪声）, "
            "centerFly=ITEM:50+CHOICE, keyboard_fly=K49/K50/K52 快捷键, "
            "unknown_p=UNK:p前驱（待查）。"
        ),
        "total_transitions": len(transitions),
        "type_counts": type_counts,
        "multi_visit_floors": multi_visit,
        "anomalies": [
            {"seq": t["seq"], "global_idx": t["global_idx"],
             "from": t["from_floor"], "to": t["to_floor"],
             "type": t["type"], "trigger": t["trigger_token"],
             "context_before": t["context_before"]}
            for t in anomalies
        ],
        "type_examples": {
            ttype: {
                "seq": ex["seq"], "global_idx": ex["global_idx"],
                "from_floor": ex["from_floor"], "to_floor": ex["to_floor"],
                "waste": ex["waste_inputs_before_floor_marker"],
                "trigger": ex["trigger_token"],
                "context_before_last15": ex["context_before"],
                "context_after_10": ex["context_after"],
            }
            for ttype, ex in examples.items()
        },
        "transitions": [
            {
                "seq": t["seq"], "global_idx": t["global_idx"],
                "from_floor": t["from_floor"], "to_floor": t["to_floor"],
                "type": t["type"], "trigger_token": t["trigger_token"],
                "waste": t["waste_inputs_before_floor_marker"],
            }
            for t in transitions
        ],
    }

    out_path = DATA / "floor_transitions.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written: {out_path}")

    # ── stdout 摘要 ────────────────────────────────────────────────────────────
    print(f"\n=== 切层统计 ===")
    print(f"总切层次数: {len(transitions)}")
    for tt, cnt in sorted(type_counts.items()):
        print(f"  {tt}: {cnt}")

    print(f"\n=== 多次进入的楼层（进入≥2次）===")
    multi_sorted = sorted(multi_visit.items(), key=lambda x: int(x[0][2:]))
    for fl, cnt in multi_sorted:
        print(f"  {fl}: {cnt}次")

    print(f"\n=== 异常切层（非 changeFloor/centerFly/keyboard_fly）===")
    for a in result["anomalies"]:
        print(f"  seq={a['seq']:3d} g={a['global_idx']:5d} {a['from']:6s}→{a['to']:6s} "
              f"type={a['type']:12s} trigger={a['trigger']}")

    print(f"\n=== 各类型代表示例 ===")
    for ttype, ex in result["type_examples"].items():
        print(f"  [{ttype}]  seq={ex['seq']} g={ex['global_idx']}  "
              f"{ex['from_floor']}→{ex['to_floor']}  waste={ex['waste']}  trigger={ex['trigger']}")
        print(f"    before: {ex['context_before_last15']}")
        print(f"    after:  {ex['context_after_10']}")

    print(f"\n=== 全部切层序列 ===")
    for t in result["transitions"]:
        print(f"  [{t['seq']:3d}] g{t['global_idx']:5d}  "
              f"{str(t['from_floor']):6s}→{t['to_floor']:6s}  "
              f"{t['type']:14s}  waste={t['waste']:3d}  trigger={t['trigger_token']}")


if __name__ == "__main__":
    main()
