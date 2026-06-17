"""一区（MT1 → 打过 MT10 队长 boss）里程碑提取——为"段链"切段提供关键节点。

只读重放新基准存档 51_20260616144514.h5route（seed=2097323316，公认最优"25 血"路线，
终态 MT10 队长格(6,1) HP25/ATK27/DEF27/钥匙全0/won=False）。逐 token 送入 sim.step，
自动捕捉里程碑：
  - 每层 MT1..MT10 第一次成为 current_floor 的 token index + 当时属性快照
  - 装备/宝石拾取点：items dict 新增键，或 ATK/DEF 跳变（自动识别，不硬编码"铁剑/铁盾"）
  - 各色钥匙数变化（含红钥匙第一次到手）
  - MT3 伏击触发（ATK 被重置为 10 那一刻）
  - MT10 队长战：战前/战后 token + HP 变化（应为 329→25 那一步）
  - 终点 token（队长格 (6,1)）

加载方式照 analysis/replay_new_baseline_confirm.py：明确指名新存档，不靠 glob。
绝不修改 sim/solver/extract/data；不调用任何 search。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))
SAVE = ROOT / "51_20260616144514.h5route"  # 明确指名新基准存档，不靠 glob


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def build_initial_state():
    hero_init = json.loads((DATA / "hero_init.json").read_text(encoding="utf-8"))
    kb_raw = json.loads((DATA / "replay_keybindings.json").read_text(encoding="utf-8"))
    key_bindings = {int(k): v for k, v in kb_raw.get("bindings", {}).items()}
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
        _key_bindings=key_bindings,
    )


def load_tokens():
    raw = SAVE.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    tokens = parse_rle_route(decompress(outer["route"]))
    return tokens, outer


def snap(s):
    h = s.hero
    return dict(
        floor=s.current_floor, x=h.x, y=h.y, hp=h.hp, atk=h.atk, df=h.def_,
        yk=h.keys.get("yellowKey", 0), bk=h.keys.get("blueKey", 0),
        rk=h.keys.get("redKey", 0),
        items={k: v for k, v in h.items.items() if v},
        kills=h.kill_count,
        won=getattr(s, "won", False), dead=getattr(s, "dead", False),
    )


def keystr(sp):
    return f"黄{sp['yk']}/蓝{sp['bk']}/红{sp['rk']}"


def attrstr(sp):
    return f"HP={sp['hp']} ATK={sp['atk']} DEF={sp['df']} {keystr(sp)}"


def main():
    tokens, outer = load_tokens()
    state = build_initial_state()

    milestones = []  # (idx, kind, desc, snap_after)

    def add(idx, kind, desc, sp):
        milestones.append((idx, kind, desc, sp))

    seen_floors = {state.current_floor}
    prev = snap(state)
    add(-1, "起点", f"route 初态（MT1 起步，token 未消耗）", prev)

    boss_pre = None  # 队长战前一步快照（HP 大跌的前一行）

    for idx, tok in enumerate(tokens):
        before = prev
        state = step(state, tok)
        cur = snap(state)

        # 1) 楼层首达
        if cur["floor"] not in seen_floors:
            seen_floors.add(cur["floor"])
            add(idx, "楼层首达", f"第一次进入 {cur['floor']}（来自 {before['floor']}）", cur)

        # 2) MT3 伏击：ATK 被强制重置（突降，通常到 10）
        if cur["atk"] < before["atk"]:
            add(idx, "伏击/ATK降",
                f"ATK 突降 {before['atk']}→{cur['atk']}（{cur['floor']} 伏击重置）", cur)

        # 3) ATK 跳变上升（装备/宝石）
        if cur["atk"] > before["atk"]:
            newitems = {k: cur["items"][k] for k in cur["items"]
                        if cur["items"].get(k, 0) > before["items"].get(k, 0)}
            tag = f" 物品+{newitems}" if newitems else ""
            add(idx, "ATK+",
                f"ATK {before['atk']}→{cur['atk']} (+{cur['atk'] - before['atk']}) "
                f"@ {cur['floor']}({cur['x']},{cur['y']}){tag}", cur)

        # 4) DEF 跳变上升（装备/宝石）
        if cur["df"] > before["df"]:
            newitems = {k: cur["items"][k] for k in cur["items"]
                        if cur["items"].get(k, 0) > before["items"].get(k, 0)}
            tag = f" 物品+{newitems}" if newitems else ""
            add(idx, "DEF+",
                f"DEF {before['df']}→{cur['df']} (+{cur['df'] - before['df']}) "
                f"@ {cur['floor']}({cur['x']},{cur['y']}){tag}", cur)

        # 5) items 新增键（即便不引起 ATK/DEF 跳变，如钥匙类道具/飞行符/血瓶以外的装备）
        new_keys = set(cur["items"]) - set(before["items"])
        if new_keys:
            add(idx, "拾取道具",
                f"items 新增 {{{', '.join(sorted(new_keys))}}} "
                f"@ {cur['floor']}({cur['x']},{cur['y']}) → items={cur['items']}", cur)

        # 6) 钥匙数变化（任何色，含红钥匙第一次到手）
        for kk, lab in (("yk", "黄钥匙"), ("bk", "蓝钥匙"), ("rk", "红钥匙")):
            if cur[kk] > before[kk]:
                first = " ★首次到手" if before[kk] == 0 and kk == "rk" else ""
                add(idx, f"{lab}+",
                    f"{lab} {before[kk]}→{cur[kk]} @ {cur['floor']}({cur['x']},{cur['y']}){first}",
                    cur)

        # 7) 大额掉血（疑似 boss/强制战）：记录战前候选
        dhp = cur["hp"] - before["hp"]
        if dhp <= -100:
            add(idx, "大额掉血",
                f"HP {before['hp']}→{cur['hp']} ({dhp}) @ {cur['floor']}({cur['x']},{cur['y']}) "
                f"前一格({before['x']},{before['y']})", cur)
            boss_pre = (idx, before)

        prev = cur

    final = prev
    add(len(tokens) - 1, "终点", f"路线终点 {final['floor']}({final['x']},{final['y']})", final)

    # ── 报告 ──────────────────────────────────────────────────────────────────
    print(f"meta name={outer.get('name')!r} seed={outer.get('seed')}  tokens={len(tokens)}")
    print(f"终态: {final['floor']}({final['x']},{final['y']}) {attrstr(final)} "
          f"GOLD={state.hero.gold} won={final['won']} dead={final['dead']}")
    print(f"端态核对（任务期望 MT10(6,1) HP25/ATK27/DEF27/钥匙全0/won=False）: "
          f"{'吻合' if (final['floor']=='MT10' and (final['x'],final['y'])==(6,1) and final['hp']==25 and final['atk']==27 and final['df']==27 and final['yk']==final['bk']==final['rk']==0 and not final['won']) else '⚠不吻合'}")
    print()
    print("=" * 100)
    print("一区里程碑表（token_index → 事件 → 属性快照）")
    print("=" * 100)
    hdr = f"{'tok':>5}  {'楼层':<5} {'坐标':<8} {'类型':<10} 事件 / 属性快照"
    print(hdr)
    print("-" * 100)
    for idx, kind, desc, sp in milestones:
        pos = f"({sp['x']},{sp['y']})"
        line1 = f"{idx:>5}  {sp['floor']:<5} {pos:<8} {kind:<10} {desc}"
        line2 = f"{'':>5}  {'':<5} {'':<8} {'':<10}   ↳ {attrstr(sp)}"
        print(line1)
        print(line2)

    # ── 楼层首达汇总（切段最直接依据）──────────────────────────────────────────
    print()
    print("=" * 100)
    print("楼层首达汇总（MT1..MT10 第一次成为 current_floor）")
    print("=" * 100)
    first_seen = {}
    for idx, kind, desc, sp in milestones:
        if kind in ("楼层首达", "起点"):
            f = sp["floor"]
            if f not in first_seen:
                first_seen[f] = (idx, sp)
    for f in [f"MT{i}" for i in range(1, 11)]:
        if f in first_seen:
            idx, sp = first_seen[f]
            tokshow = "起步" if idx < 0 else f"tok {idx}"
            print(f"  {f:<5} {tokshow:<10} ({sp['x']},{sp['y']})  {attrstr(sp)}")
        else:
            print(f"  {f:<5} （路线未首达此层 / 已在更早记录）")

    # ── 关键节点源码对照（机制溯源，非硬编码猜测）─────────────────────────────
    # 以下出处已在 data/games51/floors/*.json 逐条核对，写明依据供切段参考。
    print()
    print("=" * 100)
    print("关键节点源码对照（已核对 data/games51/floors/*.json，非心算猜测）")
    print("=" * 100)
    print("  伏击/夺装  触发格 MT3(5,9)：setValue hp=400/atk=10/def=10 + flag:nowWeapon/nowShield=null")
    print("            + 魔法免疫=false + changeFloor→MT2(3,8)。本 route 于 tok46 触发（MT3(5,10)→MT2(3,8)）。")
    print("            ⇒ 注意：触发格在 MT3，但 ATK/DEF→10 与落点都在 MT2(3,8)。剑盾(sword5/shield5)被剥夺。")
    print("  小偷台词  MT2(1,9)：'你的剑和盾被警卫拿走了…铁剑在5楼，铁盾在9楼'——铁剑/铁盾去向的剧情依据。")
    print("  铁剑      MT5(11,11) tok161：ATK 10→20 (+10)，引擎按 itemEffect 直接加点(不进 items dict)。")
    print("  铁盾      MT9(9,7)  tok454：DEF 10→20 (+10)，同上。")
    print("  红钥匙    MT8(10,2) tok945：红钥匙 0→1（一区唯一红钥首次到手）。")
    print("  MT10队长战 终点 tok1043：踏入队长格 MT10(6,1)（前一格(6,2)），HP 329→25（−304），won=False。")
    print("            ⇒ 这是一区终点；战前态 ATK27/DEF27/HP329/钥匙全0。")


if __name__ == "__main__":
    main()
