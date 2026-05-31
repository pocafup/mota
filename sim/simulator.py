"""
sim/simulator.py
Deterministic single-floor simulator.
step(state, action) -> new_state (pure function, no side effects).

双层地图模型
  terrain 层：墙/地板/楼梯/门/装饰地形（静态或经 openDoor/closeDoor/setBlock 变动）
  entities 层：怪物/道具/NPC（0=空，由 move/generateMove/setBlock/战斗/拾取 变动）
可通行性 = terrain 可走 AND entities 无阻挡实体
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from sim.combat import Monster, PlayerState, compute_combat

# ─── Tile constants ───────────────────────────────────────────────────────────

WALL_TILES = {1, 4, 5, 330}
SPECIAL_DOOR = 85
DOOR_KEY_MAP = {
    81: "yellowKey", 82: "blueKey", 83: "redKey",
    84: "greenKey", 86: "steelKey",
}
_DOOR_ID_TO_TILE = {
    "yellowDoor": 81, "blueDoor": 82, "redDoor": 83,
    "greenDoor": 84, "specialDoor": 85, "steelDoor": 86,
    "unbreakableWall": 330,
}
_DIR = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
_MOVE_DIR = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_KEY_ITEMS = {"yellowKey", "blueKey", "redKey", "greenKey", "steelKey", "bigKey"}


# ─── State dataclasses ───────────────────────────────────────────────────────

@dataclass
class HeroState:
    x: int
    y: int
    hp: int
    atk: int
    def_: int
    mdef: int = 0
    gold: int = 0
    keys: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    kill_count: int = 0


@dataclass
class FloorState:
    floor_id: str
    terrain: list       # list[list[int]] 地形层：墙/地板/楼梯/门/装饰
    entities: list      # list[list[int]] 实体层：怪/道具/NPC（0=空）
    ratio: int
    events: dict        # shared reference (read-only after load)
    after_battle: dict  # shared reference
    auto_event: dict    # shared reference
    change_floor: dict  # shared reference
    _items_db: dict     # shared reference
    _monsters_db: dict  # shared reference
    _tile_to_enemy: dict    # {tile_int: monster_id}
    _tile_to_item: dict     # {tile_int: item_id}
    _tile_to_entity: dict   # {tile_int: entity_id} (enemies + items + npcs)
    _id_to_tile: dict       # {entity_id: tile_int}
    _suppressed_events: set  # loc keys where hide+remove fired; also autoEvent once-keys
    _done_after_battle: set  # loc keys where afterBattle already ran
    # 拦截型事件状态：事件脚本遇到对话后暂停勇者移动，等待 CHOICE token 推进
    _event_intercepting: bool = False
    _event_pending_instrs: list = field(default_factory=list)
    _event_pending_xy: tuple = (0, 0)
    # 出口状态：英雄踏上 changeFloor 格后，本层不再处理任何 token
    _exited: bool = False

    @property
    def map(self) -> list:
        """向后兼容视图：实体层非空时返回实体 tile，否则返回地形 tile。"""
        return [
            [
                self.entities[y][x] if self.entities[y][x] else self.terrain[y][x]
                for x in range(len(self.terrain[y]))
            ]
            for y in range(len(self.terrain))
        ]


@dataclass
class GameState:
    hero: HeroState
    floor: FloorState


# ─── State copy ──────────────────────────────────────────────────────────────

def _copy_state(state: GameState) -> GameState:
    h = state.hero
    new_hero = HeroState(
        x=h.x, y=h.y, hp=h.hp, atk=h.atk, def_=h.def_, mdef=h.mdef,
        gold=h.gold, kill_count=h.kill_count,
        keys=dict(h.keys), items=dict(h.items), flags=dict(h.flags),
    )
    f = state.floor
    new_floor = FloorState(
        floor_id=f.floor_id,
        terrain=[row[:] for row in f.terrain],
        entities=[row[:] for row in f.entities],
        ratio=f.ratio,
        events=f.events,
        after_battle=f.after_battle,
        auto_event=f.auto_event,
        change_floor=f.change_floor,
        _items_db=f._items_db,
        _monsters_db=f._monsters_db,
        _tile_to_enemy=f._tile_to_enemy,
        _tile_to_item=f._tile_to_item,
        _tile_to_entity=f._tile_to_entity,
        _id_to_tile=f._id_to_tile,
        _suppressed_events=set(f._suppressed_events),
        _done_after_battle=set(f._done_after_battle),
        _event_intercepting=f._event_intercepting,
        _event_pending_instrs=list(f._event_pending_instrs),
        _event_pending_xy=f._event_pending_xy,
        _exited=f._exited,
    )
    return GameState(hero=new_hero, floor=new_floor)


# ─── Floor loading ───────────────────────────────────────────────────────────

def load_floor(path: Path) -> FloorState:
    data = json.loads(path.read_text(encoding="utf-8"))
    data_dir = path.parent.parent  # …/data/games51/

    items_db = json.loads((data_dir / "items.json").read_text(encoding="utf-8"))
    monsters_db = json.loads((data_dir / "monsters.json").read_text(encoding="utf-8"))
    tiles_db = json.loads((data_dir / "tiles.json").read_text(encoding="utf-8"))

    tile_to_enemy = {int(k): v["_monster"] for k, v in tiles_db["enemys"].items()}
    tile_to_item = {int(k): v["_item"] for k, v in tiles_db["items"].items()}

    tile_to_entity: dict = {}
    tile_to_entity.update(tile_to_enemy)
    tile_to_entity.update(tile_to_item)
    for k, v in tiles_db.get("npcs", {}).items():
        tile_to_entity[int(k)] = v["id"]

    id_to_tile = {v: int(k) for k, v in tile_to_entity.items()}

    # 把原始 map 数组拆分为 terrain / entities 两层
    raw_map = data["map"]
    H = len(raw_map)
    W = len(raw_map[0]) if H else 0
    terrain = [[0] * W for _ in range(H)]
    entities = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            t = raw_map[y][x]
            if t in tile_to_entity:
                entities[y][x] = t   # 怪/道具/NPC → 实体层，地形为地板
            else:
                terrain[y][x] = t    # 墙/门/楼梯/装饰 → 地形层

    return FloorState(
        floor_id=data["floorId"],
        terrain=terrain,
        entities=entities,
        ratio=data.get("ratio", 1),
        events=data.get("events", {}),
        after_battle=data.get("afterBattle", {}),
        auto_event=data.get("autoEvent", {}),
        change_floor=data.get("changeFloor", {}),
        _items_db=items_db,
        _monsters_db=monsters_db,
        _tile_to_enemy=tile_to_enemy,
        _tile_to_item=tile_to_item,
        _tile_to_entity=tile_to_entity,
        _id_to_tile=id_to_tile,
        _suppressed_events=set(),
        _done_after_battle=set(),
    )


# ─── Public entry point ──────────────────────────────────────────────────────

def step(state: GameState, action: str) -> GameState:
    """Pure function: apply one action token to state, return new state."""
    state = _copy_state(state)
    floor = state.floor

    # 英雄已离开本层（踏上 changeFloor 格），后续所有 token 均为 no-op
    if floor._exited:
        return state

    # 拦截型事件激活：勇者移动被暂停
    if floor._event_intercepting:
        if action.startswith("CHOICE"):
            # CHOICE 推进/关闭对话，执行剩余自动指令
            remaining = floor._event_pending_instrs
            ex, ey = floor._event_pending_xy
            floor._event_intercepting = False
            floor._event_pending_instrs = []
            _execute_event_list(state, remaining, ex, ey)
        # UDLR 等其他 token：勇者被锁，废弃输入
        _check_auto_events(state)
        return state

    if action in ("U", "D", "L", "R"):
        _process_move(state, action)
        # 英雄踏上 changeFloor 格 → 标记已退出本层
        loc_key = f"{state.hero.x},{state.hero.y}"
        if loc_key in floor.change_floor:
            floor._exited = True

    # CHOICE:n、ITEM:n、FLOOR:x 且无拦截事件 → no-op at the floor level
    _check_auto_events(state)
    return state


# ─── Movement ────────────────────────────────────────────────────────────────

def _process_move(state: GameState, direction: str) -> None:
    hero = state.hero
    floor = state.floor
    dx, dy = _DIR[direction]
    nx, ny = hero.x + dx, hero.y + dy

    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    if not (0 <= ny < rows and 0 <= nx < cols):
        return

    t_tile = floor.terrain[ny][nx]   # 地形 tile
    e_tile = floor.entities[ny][nx]  # 实体 tile（0=空）

    # 地形阻挡优先
    if t_tile in WALL_TILES or t_tile == SPECIAL_DOOR:
        return

    # 实体层：怪物 → 战斗
    if e_tile in floor._tile_to_enemy:
        _fight_monster(state, nx, ny)
        return

    # 实体层：道具 → 拾取
    if e_tile in floor._tile_to_item:
        _pickup_item(state, nx, ny)
        hero.x, hero.y = nx, ny
        _fire_events(state, nx, ny)
        return

    # 实体层：NPC → 碰撞（英雄原地不动，触发事件）
    if e_tile in floor._tile_to_entity:
        _fire_events(state, nx, ny)
        return

    # 地形层：门 → 需要钥匙
    if t_tile in DOOR_KEY_MAP:
        key_id = DOOR_KEY_MAP[t_tile]
        if hero.keys.get(key_id, 0) > 0:
            hero.keys[key_id] -= 1
            floor.terrain[ny][nx] = 0
            hero.x, hero.y = nx, ny
            _fire_events(state, nx, ny)
        # else: 无钥匙 → 原地
        return

    # 地板/装饰地形/楼梯 → 可通行
    hero.x, hero.y = nx, ny
    _fire_events(state, nx, ny)


# ─── Combat ──────────────────────────────────────────────────────────────────

def _fight_monster(state: GameState, mx: int, my: int) -> None:
    hero = state.hero
    floor = state.floor

    tile = floor.entities[my][mx]   # 怪物在实体层
    monster_id = floor._tile_to_enemy[tile]
    m = floor._monsters_db[monster_id]

    sp = m.get("special", [])
    if isinstance(sp, int):
        sp = [sp] if sp else []

    monster = Monster(
        id=monster_id, name=m["name"],
        hp=m["hp"], atk=m["atk"], def_=m["def"],
        special=sp, n=m.get("n", 0), value=m.get("value", 0.0),
        add=m.get("add", False), atkValue=m.get("atkValue", 0.1),
        defValue=m.get("defValue", 0.9), damage=m.get("damage", 0),
    )
    hero_ps = PlayerState(hp=hero.hp, atk=hero.atk, def_=hero.def_, mdef=hero.mdef)
    result = compute_combat(hero_ps, monster)

    if result.damage is None:
        return  # unkillable → blocked

    hero.hp -= result.damage
    hero.gold += m.get("gold", 0)
    hero.kill_count += 1
    floor.entities[my][mx] = 0   # 怪物从实体层消失
    hero.x, hero.y = mx, my

    if result.effects.poison:
        hero.flags["poison"] = True
    if result.effects.weak:
        hero.atk -= 20
        hero.def_ -= 20
    if result.effects.curse:
        hero.flags["curse"] = True
    if result.effects.explode:
        hero.hp = 1

    loc_key = f"{mx},{my}"
    if loc_key in floor.after_battle and loc_key not in floor._done_after_battle:
        floor._done_after_battle.add(loc_key)
        _execute_event_list(state, floor.after_battle[loc_key], mx, my)

    _fire_events(state, mx, my)


# ─── Item pickup ─────────────────────────────────────────────────────────────

def _pickup_item(state: GameState, ix: int, iy: int) -> None:
    hero = state.hero
    floor = state.floor
    tile = floor.entities[iy][ix]   # 道具在实体层
    item_id = floor._tile_to_item[tile]
    floor.entities[iy][ix] = 0     # 道具从实体层消失

    if item_id in _KEY_ITEMS:
        hero.keys[item_id] = hero.keys.get(item_id, 0) + 1
        return

    idata = floor._items_db.get(item_id)
    if not idata:
        return
    effect = idata.get("pickup")
    if effect is None:
        hero.items[item_id] = hero.items.get(item_id, 0) + 1
        return

    _apply_item_effect(hero, effect, floor.ratio)


def _apply_item_effect(hero: HeroState, effect: dict, ratio: int) -> None:
    t = effect["type"]
    if t == "stat":
        stat = effect["stat"]
        attr = "def_" if stat == "def" else stat
        delta = effect["base"] * ratio if effect.get("ratio_scaled") else effect.get("delta", 0)
        setattr(hero, attr, getattr(hero, attr) + delta)
        for k, v in effect.get("set_flags", {}).items():
            hero.flags[k] = v
    elif t == "multi":
        for op in effect["ops"]:
            attr = "def_" if op["stat"] == "def" else op["stat"]
            setattr(hero, attr, getattr(hero, attr) + op["delta"])


# ─── Event firing ────────────────────────────────────────────────────────────

def _fire_events(state: GameState, x: int, y: int) -> None:
    floor = state.floor
    loc_key = f"{x},{y}"

    if loc_key not in floor.events:
        return
    if loc_key in floor._suppressed_events:
        return

    event_data = floor.events[loc_key]

    if isinstance(event_data, dict):
        if not event_data.get("enable", True):
            return
        data = event_data.get("data", [])
        if data:
            _execute_event_list(state, data, x, y)
        return

    if isinstance(event_data, list):
        _execute_event_list(state, event_data, x, y)


def _execute_event_list(
    state: GameState, event_list: list, event_x: int, event_y: int,
    ctx: dict | None = None,
) -> None:
    if ctx is None:
        ctx = {"had_sync_anim": False}
    floor = state.floor
    for i, instr in enumerate(event_list):
        if isinstance(instr, str):
            if ctx.get("had_sync_anim"):
                # 同步动画之后出现对话 → 拦截型事件：暂停执行，等待 CHOICE token
                floor._event_intercepting = True
                floor._event_pending_instrs = list(event_list[i + 1:])
                floor._event_pending_xy = (event_x, event_y)
                return
            # 无同步动画前置 → 非拦截型对话，跳过（英雄可继续移动）
            continue
        if isinstance(instr, dict):
            t = instr.get("type", "")
            # 同步的 move/generateMove（无 async:true）→ 进入阻塞式动画上下文
            if t in ("move", "generateMove") and not instr.get("async", False):
                ctx["had_sync_anim"] = True
            _execute_instruction(state, instr, event_x, event_y, ctx)
            if floor._event_intercepting:
                # 暂停从嵌套分支传播上来；将本层剩余指令追加到 pending
                outer_rest = list(event_list[i + 1:])
                if outer_rest:
                    floor._event_pending_instrs = floor._event_pending_instrs + outer_rest
                return


def _execute_instruction(
    state: GameState, instr: dict, event_x: int, event_y: int,
    ctx: dict | None = None,
) -> None:
    if ctx is None:
        ctx = {}
    floor = state.floor
    t = instr.get("type", "")

    # ── no-ops ────────────────────────────────────────────────────────────────
    if t in ("waitAsync", "sleep", "playBgm", "playSound", "setBgFgBlock", "show"):
        return

    # ── hide ─────────────────────────────────────────────────────────────────
    if t == "hide":
        if instr.get("remove"):
            floor._suppressed_events.add(f"{event_x},{event_y}")
        return

    # ── setBlock ──────────────────────────────────────────────────────────────
    if t == "setBlock":
        num = int(instr["number"])
        for loc in instr.get("loc", []):
            lx, ly = loc[0], loc[1]
            if num == 0:
                # 清空：两层均清零
                floor.entities[ly][lx] = 0
                floor.terrain[ly][lx] = 0
            elif num in floor._tile_to_entity:
                # 放置实体（怪/道具/NPC）→ 实体层
                floor.entities[ly][lx] = num
            else:
                # 放置地形（墙/门/楼梯/装饰）→ 地形层，清空实体层
                floor.terrain[ly][lx] = num
                floor.entities[ly][lx] = 0
        return

    # ── openDoor ──────────────────────────────────────────────────────────────
    if t == "openDoor":
        loc = instr.get("loc")
        lx, ly = (event_x, event_y) if loc is None else (loc[0], loc[1])
        floor.terrain[ly][lx] = 0   # 门是地形层
        return

    # ── closeDoor ─────────────────────────────────────────────────────────────
    if t == "closeDoor":
        loc = instr.get("loc")
        lx, ly = (event_x, event_y) if loc is None else (loc[0], loc[1])
        floor.terrain[ly][lx] = _DOOR_ID_TO_TILE.get(instr.get("id", ""), 85)
        return

    # ── setValue ──────────────────────────────────────────────────────────────
    if t == "setValue":
        _set_value(state, instr.get("name", ""), instr.get("value", ""))
        return

    # ── move / generateMove ───────────────────────────────────────────────────
    # 两者均只操作实体层，地形层不变
    if t in ("move", "generateMove"):
        loc = instr.get("loc")
        if loc is None:
            return
        sx, sy = loc[0], loc[1]
        dx, dy = sx, sy
        for s in instr.get("steps", []):
            d, cnt = s.split(":")
            dd = _MOVE_DIR[d]
            dx += dd[0] * int(cnt)
            dy += dd[1] * int(cnt)

        if t == "move":
            # 移动实体层上的现有实体
            tile_id = floor.entities[sy][sx]
            floor.entities[sy][sx] = 0
        else:
            # generateMove：若源位置实体层有实体则移走，否则按 id 新建
            entity_id = instr.get("id")
            src_entity = floor.entities[sy][sx]
            if src_entity in floor._tile_to_entity:
                tile_id = src_entity
                floor.entities[sy][sx] = 0
            else:
                tile_id = floor._id_to_tile.get(entity_id, 0) if entity_id else 0

        rows = len(floor.terrain)
        cols = len(floor.terrain[0]) if rows else 0
        if instr.get("keep") is True and 0 <= dy < rows and 0 <= dx < cols:
            floor.entities[dy][dx] = tile_id
        return

    # ── if ────────────────────────────────────────────────────────────────────
    if t == "if":
        branch = (
            instr.get("true", [])
            if _eval_condition(instr.get("condition", ""), state)
            else instr.get("false", [])
        )
        _execute_event_list(state, branch, event_x, event_y, ctx)
        return


# ─── Condition evaluator ─────────────────────────────────────────────────────

def _eval_condition(condition: str, state: GameState) -> bool:
    return all(_eval_single(p.strip(), state) for p in condition.split("&&"))


def _eval_single(part: str, state: GameState) -> bool:
    floor = state.floor
    hero = state.hero

    # flag:name
    if part.startswith("flag:"):
        return bool(hero.flags.get(part[5:], False))

    # (blockId:X,Y==='id') — 检查实体层
    m = re.match(r"\(?blockId:(\d+),(\d+)\s*===\s*'(\w+)'\)?", part)
    if m:
        bx, by, bid = int(m.group(1)), int(m.group(2)), m.group(3)
        return floor._tile_to_entity.get(floor.entities[by][bx]) == bid

    # core.getBlockId(X,Y) === null — 检查实体层（null 表示该格无实体）
    m = re.match(r"core\.getBlockId\((\d+),\s*(\d+)\)\s*===\s*null", part)
    if m:
        bx, by = int(m.group(1)), int(m.group(2))
        return floor.entities[by][bx] not in floor._tile_to_entity

    return False


# ─── setValue helper ─────────────────────────────────────────────────────────

def _set_value(state: GameState, name: str, value) -> None:
    hero = state.hero
    if isinstance(value, str):
        if value == "true":
            val: object = True
        elif value == "false":
            val = False
        else:
            try:
                val = int(value)
            except ValueError:
                val = value
    else:
        val = value

    if name.startswith("flag:"):
        hero.flags[name[5:]] = val
    elif name.startswith("switch:"):
        hero.flags[f"switch:{name[7:]}"] = val
    elif name.startswith("status:money"):
        hero.gold = int(val)
    elif name.startswith("status:hp"):
        hero.hp = int(val)
    elif name.startswith("status:atk"):
        hero.atk = int(val)
    elif name.startswith("status:def"):
        hero.def_ = int(val)


# ─── autoEvent ───────────────────────────────────────────────────────────────

def _check_auto_events(state: GameState) -> None:
    floor = state.floor
    for loc_key, entries in floor.auto_event.items():
        if not isinstance(entries, dict):
            continue
        lx, ly = map(int, loc_key.split(","))
        for idx_key, entry in entries.items():
            if entry is None:
                continue
            multi = entry.get("multiExecute", True)
            once_key = f"__auto__{loc_key}__{idx_key}"
            if not multi and once_key in floor._suppressed_events:
                continue
            if not _eval_condition(entry.get("condition", ""), state):
                continue
            if not multi:
                floor._suppressed_events.add(once_key)
            _execute_event_list(state, entry.get("data", []), lx, ly)
