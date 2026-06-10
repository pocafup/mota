"""导出 MT10 过 boss 那条路线（玩家要拿去真实游戏照走验收）。

口径（回应玩家铁律「引擎裁判同意≠真走得通」）：
  · 这条线是【缩点搜索算子展开成的动作序列】，不是抄存档。每个算子(door/trigger/kill/stair)
    都由 solver.quotient._expand_op 经【封板引擎 sim.step】真实推进、累积 U/D/L/R；
  · 展开完后，把那串纯 U/D/L/R 动作【从干净入口副本重新喂一遍 step】(solver.verify.replay)，
    与算子展开的终态【逐字段 diff】(diff_states)——空 diff = 终态一致 = 不是只在抽象层「算过了」。
  · 入口态(HP/atk/def/钥匙/道具/flags + MT10 楼层对象现状)取自真实存档重放到【过 boss 那一访】
    刚踏入 MT10 的那一刻（boss 访 = flag:10f机关 在该访被置位的那一访）。属性是真实的，无任何
    override（此前对话里的 HP=2475 来自 atk20/def10/hp4000 的 V_zone 压测 override，非真实，已废）。
  · 坐标 (6,9红门)/(6,5埋伏)/(6,3机关门)/(6,2决斗)/(6,1队长)/(6,11楼梯) 与事件顺序均来自核对
    data/games51/floors/MT10.json 源码——玩家正好拿真实游戏对一遍格子/触发顺序有没有搞错。

跑法：python -m extract.export_mt10_boss_route
产物：extract/mt10_boss_route.md
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lzstring import LZString
from extract.decode_route import parse_rle_route
from sim.simulator import GameState, HeroState, step, load_floor, _copy_state
from solver.quotient import (_free_cells, _boundary_ops, _expand_op, _bfs_moves,
                             _killable)
from solver.verify import replay, diff_states

DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
OUT = ROOT / "extract" / "mt10_boss_route.md"

CAPTAIN = (6, 1)
RED_DOOR = (6, 9)
AMBUSH_TRIGGER = (6, 5)
DUEL = (6, 2)
STAIR = (6, 11)
# 埋伏后 8 怪落点（核对 MT10.json events["6,5"] 各 move steps 推出，环绕 (6,5)）
AMBUSH_CELLS = {(5, 4), (6, 4), (7, 4), (5, 5), (7, 5), (5, 6), (6, 6), (7, 6)}


# ── 真实存档：重放到「过 boss 那一访」刚踏入 MT10 的入口态 ──────────────────────

def make_initial_state():
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    floor = load_floor(FLOORS / "MT1.json")
    hero = HeroState(
        x=hero_init["loc"]["x"], y=hero_init["loc"]["y"],
        hp=hero_init["hp"], atk=hero_init["atk"], def_=hero_init["def"],
        mdef=hero_init.get("mdef", 0), gold=hero_init.get("gold", 0),
        keys={}, items=dict(hero_init.get("items", {})),
        flags=dict(hero_init.get("flags", {})),
    )
    return GameState(
        hero=hero, floors={"MT1": floor}, current_floor="MT1",
        floor_ids=FLOOR_IDS, visited_floors={"MT1"},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def load_tokens():
    route_path = next(ROOT.glob("51_*.h5route"), None)
    if route_path is None:
        sys.exit("存档 51_*.h5route 未找到")
    raw = route_path.read_text(encoding="utf-8").strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer["route"]))


def capture_boss_entry():
    """重放存档，捕获 boss 访(flag:10f机关 被置位那一访) 刚踏入 MT10 的入口态副本。"""
    tokens = load_tokens()
    state = make_initial_state()
    last_mt10_entry = None
    prev_floor = state.current_floor
    for i, tok in enumerate(tokens):
        state = step(state, tok)
        if state.current_floor == "MT10" and prev_floor != "MT10":
            last_mt10_entry = (i, _copy_state(state))   # 刚踏入 MT10
        if state.hero.flags.get("10f机关") and last_mt10_entry is not None:
            return last_mt10_entry                       # 本访已触发埋伏 → 即 boss 访
        prev_floor = state.current_floor
    sys.exit("未能在存档中定位 boss 访（flag:10f机关 从未置位）")


# ── 缩点算子驱动：从入口态走完 boss，纯 U/D/L/R 落盘 ────────────────────────────

def _mid_at(floor, x, y):
    return floor._tile_to_enemy.get(floor.entities[y][x])


def _ops_sorted(s):
    """边界算子按 (kind, ox, oy) 排序 → 驱动完全确定、产物可复现。"""
    free = _free_cells(s)
    ops = _boundary_ops(s, free, cross_floor=True)
    return free, sorted(ops, key=lambda o: (o[0], o[1], o[2]))


def do_target(s, target, kinds):
    """展开「目标格==target 且 kind∈kinds」的算子（经真 step），返回 (new_s, moves) 或 None。"""
    free, ops = _ops_sorted(s)
    cand = [o for o in ops if (o[1], o[2]) == target and o[0] in kinds]
    if not cand:
        return None
    return _expand_op(s, free, cand[0], step)


def absorb_sorted(s):
    """吸收当前自由块内所有道具（块内零损血，顺序无关）；目标按坐标排序 → 确定性。返回 (s, moves)。"""
    moves = []
    while True:
        free = _free_cells(s)
        floor = s.floor
        items = sorted((x, y) for (x, y) in free
                       if floor.entities[y][x] in floor._tile_to_item)
        if not items:
            return s, moves
        path = _bfs_moves(s, free, items[0])
        if not path:
            return s, moves
        for m in path:
            s = step(s, m)
            if s.dead:
                return s, moves
        moves += path


def snap(label, s, action_idx):
    h = s.hero
    return {"label": label, "i": action_idx, "floor": s.current_floor,
            "x": h.x, "y": h.y, "hp": h.hp, "atk": h.atk, "def": h.def_}


def drive_boss_pass(s0):
    """缩点算子驱动过 boss。返回 (final_state, actions[U/D/L/R...], nodes[里程碑标注])。"""
    actions, nodes = [], []
    s = s0
    nodes.append(snap("踏入 MT10（入口）", s, 0))

    def resolve_red_door(state, label):
        """中央走廊唯一网关 (6,9)：先开红门(door 算子)，再触发其 if-事件格(trigger 算子)踏过。
        升时 if 条件(已胜队长)未成立→false 空分支(不自删，仍是节点，但人已越过)；
        降时条件成立→true 分支(小偷)末 hide remove 自删。两次都靠这一步把走廊接通。"""
        nonlocal actions
        touched = False
        for kind in ("door", "trigger"):
            r2 = do_target(state, RED_DOOR, {kind})
            if r2 is not None:
                state, mv = r2; actions += mv; touched = True
        state, mv = absorb_sorted(state); actions += mv
        if touched:
            nodes.append(snap(label, state, len(actions)))
        return state

    # 入口先吸一遍块内免费道具
    s, mv = absorb_sorted(s); actions += mv

    # M1 上行过红门网关 (6,9)（开门 + 越过其事件格）
    s = resolve_red_door(s, "上行过红门网关 (6,9)")

    # M2 触发埋伏 (6,5)：队长 move 到 (6,1)、8 怪环绕、(6,3) 关门、(5,6)/(7,6) 开
    r = do_target(s, AMBUSH_TRIGGER, {"trigger"})
    assert r is not None, "应能走到 (6,5) 触发埋伏（红门已开、走廊通）"
    s, mv = r; actions += mv
    assert _mid_at(s.floor, *CAPTAIN) is not None, "埋伏后队长应在 (6,1)"
    assert s.hero.flags.get("10f机关"), "埋伏应置 flag:10f机关"
    nodes.append(snap("踏 (6,5) 触发埋伏 → 队长退 (6,1)、8 怪环绕、(6,3) 落机关门", s, len(actions)))

    # M3 连杀 8 埋伏怪（每杀一只暴露更多，直到 8 格无怪）
    kills = 0
    while True:
        free, ops = _ops_sorted(s)
        kops = [o for o in ops if o[0] == "kill" and (o[1], o[2]) in AMBUSH_CELLS]
        if not kops:
            break
        op = kops[0]
        r = _expand_op(s, free, op, step)
        assert r is not None, f"杀埋伏怪 {(op[1], op[2])} 应成功"
        s, mv = r; actions += mv
        kills += 1
        nodes.append(snap(f"杀第 {kills} 只埋伏怪 ({op[1]},{op[2]})", s, len(actions)))
        s, mv = absorb_sorted(s); actions += mv      # 杀后若有格变空露出道具，顺手吸
    assert kills == 8, f"应清完 8 只埋伏怪，实清 {kills}"
    # autoEvent (6,3)：8 怪皆 null + flag:10f机关 → openDoor，机关门重开
    assert s.floors["MT10"].map[3][6] == 0, "8 怪清完后 autoEvent 应开 (6,3) 机关门"
    nodes.append(snap("8 怪清完 → autoEvent 自动开 (6,3) 机关门", s, len(actions)))

    # M4 触发决斗喊话 (6,2)（hide remove 自删 → 英雄踏入 (6,2)，队长暴露）
    r = do_target(s, DUEL, {"trigger"})
    assert r is not None, "8 怪清完、(6,3) 开后应能触发 (6,2) 决斗喊话"
    s, mv = r; actions += mv
    assert (s.hero.x, s.hero.y) == DUEL, "触发后英雄应踏入 (6,2)"
    nodes.append(snap("踏 (6,2) 触发决斗喊话（自删，队长暴露）", s, len(actions)))

    # M5 杀队长 (6,1) → afterBattle 开 boss 三门 (4,4)/(6,7)/(8,4)、清红门 (6,9)、置胜旗
    r = do_target(s, CAPTAIN, {"kill"})
    assert r is not None, "触发决斗后队长应暴露在自由块边界、生成 kill 算子"
    s, mv = r; actions += mv
    assert _mid_at(s.floor, *CAPTAIN) is None, "杀后 (6,1) 不应再是怪"
    mt10 = s.floors["MT10"]
    assert mt10.map[4][4] == 0 and mt10.map[7][6] == 0 and mt10.map[4][8] == 0, \
        "afterBattle 应开 boss 三门 (4,4)/(6,7)/(8,4)"
    assert mt10.map[9][6] == 0, "afterBattle 应清红门 (6,9)"
    assert s.hero.flags.get("10f战胜骷髅队长") is True, "afterBattle 应置 flag:10f战胜骷髅队长"
    nodes.append(snap("杀队长 (6,1) → afterBattle 开三门/清红门/置胜旗", s, len(actions)))

    # 过 boss 后吸全块免费道具（宝石/血瓶，atk/def/HP 在此兑现）
    s, mv = absorb_sorted(s); actions += mv
    nodes.append(snap("过 boss 后吸自由块道具", s, len(actions)))

    # M6 下行过红门网关 (6,9)（此时 flag:10f战胜骷髅队长 已置 → 触发小偷 true 分支、自删接通走廊）
    s = resolve_red_door(s, "下行过红门网关 (6,9)（触发小偷事件、自删）")
    s, mv = absorb_sorted(s); actions += mv

    # M7 走楼梯 (6,11) → MT11
    r = do_target(s, STAIR, {"stair"})
    assert r is not None, "boss 后 (6,11) 楼梯应显形可走"
    s, mv = r; actions += mv
    assert s.current_floor == "MT11", "走 (6,11) 应换到 MT11"
    nodes.append(snap("走 (6,11) 楼梯 → 进 MT11", s, len(actions)))
    return s, actions, nodes


# ── 独立封板重放校验（铁律：纯动作串从干净副本再喂一遍 step，逐字段一致）──────────

def independent_verify(boss_entry_state, actions, claimed_final):
    replayed = replay(boss_entry_state, actions, step, _copy_state)
    diffs = diff_states(claimed_final, replayed)
    return replayed, diffs


# ── 落盘报告 ───────────────────────────────────────────────────────────────────

def fmt_actions_segmented(actions, nodes):
    """按里程碑切片输出动作（每段 = 上一里程碑到本里程碑之间的 U/D/L/R）。"""
    lines = []
    prev_i = 0
    for nd in nodes:
        seg = actions[prev_i:nd["i"]]
        if seg:
            lines.append(f"  {''.join(seg)}")
            lines.append(f"    ↑ {len(seg)} 步 → {nd['label']}  "
                         f"@({nd['x']},{nd['y']}) HP={nd['hp']} ATK={nd['atk']} DEF={nd['def']}")
        else:
            lines.append(f"    （0 步）→ {nd['label']}  "
                         f"@({nd['x']},{nd['y']}) HP={nd['hp']} ATK={nd['atk']} DEF={nd['def']}")
        prev_i = nd["i"]
    return "\n".join(lines)


def write_report(entry_idx, entry_state, final, actions, nodes, replayed, diffs):
    e, f = entry_state.hero, final.hero
    full = "".join(actions)
    ud = {c: full.count(c) for c in "UDLR"}
    lines = []
    lines.append("# MT10 过 boss 路线（缩点算子展开 + 封板引擎重放校验）\n")
    lines.append("> 玩家拿去真实游戏照走验收用。动作只有 U/D/L/R（上/下/左/右方向键）；")
    lines.append("> 「触发埋伏」「决斗喊话」「换层进 MT11」都是【走到那一格自动发生】，不是另外的按键。\n")

    lines.append("## 1. 这条线的来历（provenance）")
    lines.append("- **来源**：缩点搜索算子（door/trigger/kill/stair）展开 —— 不是抄存档、不是手推。")
    lines.append("  每个算子都由 `solver.quotient._expand_op` 经【封板引擎 `sim.step`】真实推进、累积动作。")
    lines.append("- **封板重放校验**：把展开出的纯 U/D/L/R 动作串，从干净入口副本【重新喂一遍 `step`】")
    lines.append("  (`solver.verify.replay`)，与算子展开终态【逐字段 diff】(`diff_states`)。")
    diff_txt = "空（完全一致 ✅）" if not diffs else f"{diffs} ❌"
    lines.append(f"  - diff 结果：**{diff_txt}** —— 证明不是只在缩点抽象层「算过了」，纯动作串真能走到同一终态。")
    lines.append(f"  - 独立重放终态：floor={replayed.current_floor} HP={replayed.hero.hp} "
                 f"ATK={replayed.hero.atk} DEF={replayed.hero.def_} dead={replayed.dead}\n")

    lines.append("## 2. 入口/出口状态与掉血账")
    lines.append(f"- **入口**（存档重放到 boss 访、刚踏入 MT10、token #{entry_idx}）：")
    lines.append(f"  @({e.x},{e.y}) **HP={e.hp} ATK={e.atk} DEF={e.def_}**  "
                 f"keys={dict(e.keys)} 红钥={e.keys.get('redKey', 0)}")
    lines.append(f"- **出口**（踏 MT10 (6,11) 楼梯换层后、落在 MT11 那一刻）：")
    lines.append(f"  floor={final.current_floor} 落点@({f.x},{f.y}) **HP={f.hp} ATK={f.atk} DEF={f.def_}**")
    net = f.hp - e.hp
    lines.append(f"- **HP 账**：入口 {e.hp} → 出口 {f.hp}，净 {net:+d}。"
                 f"（过程先掉血杀怪、过 boss 后吸到回血道具反超；逐段见下表当刻 HP）")
    lines.append(f"- **属性账**：ATK {e.atk}→{f.atk}（+{f.atk - e.atk}）、DEF {e.def_}→{f.def_}"
                 f"（+{f.def_ - e.def_}），来自过 boss 后吸到的宝石。")
    lines.append("- **关于此前的 HP=2475**：那是 atk20/def10/hp4000 的 V_zone 压测 override 跑出来的，"
                 "不是真实属性，已废。真实入口属性下出口 HP 见上。\n")

    lines.append("## 3. 完整动作序列（按里程碑分段，逐段照走）")
    lines.append("```")
    lines.append(fmt_actions_segmented(actions, nodes))
    lines.append("```")
    lines.append(f"- 全程合计 **{len(actions)} 步**：U×{ud['U']} D×{ud['D']} L×{ud['L']} R×{ud['R']}")
    lines.append("- 连续整串（可一次性照走）：")
    lines.append("```")
    lines.append(full)
    lines.append("```\n")

    lines.append("## 4. 里程碑节点表（当刻坐标/属性）")
    lines.append("| # | 里程碑 | 坐标 | HP | ATK | DEF | 到此累计步数 |")
    lines.append("|---|--------|------|----|----|-----|------|")
    for k, nd in enumerate(nodes):
        lines.append(f"| {k} | {nd['label']} | ({nd['x']},{nd['y']}) | "
                     f"{nd['hp']} | {nd['atk']} | {nd['def']} | {nd['i']} |")
    lines.append("")

    lines.append("## 5. 坐标/事件顺序的来源（玩家请对一遍）")
    lines.append("以下均核对自 `data/games51/floors/MT10.json` 源码，可能有我读错的地方，请拿真实游戏对：")
    lines.append("- (6,5) `events`：踏上触发埋伏 → 队长(6,4) move up:3 到 (6,1)、8 怪 generateMove 环绕 "
                 "(5,4)(6,4)(7,4)(5,5)(7,5)(5,6)(6,6)(7,6)、closeDoor (6,3)、置 flag:10f机关。")
    lines.append("- (6,3) `autoEvent`：flag:10f机关 且 8 怪格皆空 → openDoor，机关门重开。")
    lines.append("- (6,2) `events`：骷髅队长决斗喊话 + hide remove（自删）。")
    lines.append("- (6,1) `afterBattle`（杀队长后触发）：开 (4,4)/(6,7)/(8,4) 三门、setBlock (6,9)=0 清红门、"
                 "show (6,9)/(6,11)、置 flag:10f战胜骷髅队长=true。")
    lines.append("- (6,11) `changeFloor`：→ :next (MT11)，stair downFloor。")
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")


def main():
    entry_idx, entry_state = capture_boss_entry()
    final, actions, nodes = drive_boss_pass(_copy_state(entry_state))
    replayed, diffs = independent_verify(entry_state, actions, final)
    write_report(entry_idx, entry_state, final, actions, nodes, replayed, diffs)

    e, f = entry_state.hero, final.hero
    print(f"boss 访入口 token #{entry_idx}: @({e.x},{e.y}) HP={e.hp} ATK={e.atk} DEF={e.def_}")
    print(f"出口(进 MT11): @({f.x},{f.y}) HP={f.hp} ATK={f.atk} DEF={f.def_} floor={final.current_floor}")
    print(f"动作 {len(actions)} 步；独立封板重放 diff = {diffs if diffs else '空(逐字段一致 ✅)'}")
    print(f"报告已写入: {OUT}")
    if diffs:
        sys.exit("独立重放 diff 非空 —— 缩点展开与纯动作串终态不一致，需排查")


if __name__ == "__main__":
    main()
