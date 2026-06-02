"""
sim/simulator.py
Deterministic multi-floor simulator.
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
    # 拦截型事件状态
    _event_intercepting: bool = False
    _event_pending_instrs: list = field(default_factory=list)
    _event_pending_choices: list = field(default_factory=list)  # for choices type
    _event_pending_xy: tuple = (0, 0)
    # 落点坐标（fly魔杖/楼梯飞入此层时的英雄位置）
    down_floor: list | None = None   # [x, y]，从低层飞来时落点
    up_floor: list | None = None     # [x, y]，从高层飞来时落点
    # firstArrive / afterGetItem（来自 JSON）
    first_arrive: list = field(default_factory=list)
    after_get_item: dict = field(default_factory=dict)
    _first_arrive_done: bool = False

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
    floors: dict           # dict[str, FloorState]
    current_floor: str
    floor_ids: list        # ordered floor ID list (from floorIds.json)
    visited_floors: set
    pending_floor_change: dict | None  # {"floor_id", "x", "y"} set by changeFloor event
    _floors_dir: Path      # base directory for lazy floor loading

    @property
    def floor(self) -> FloorState:
        """当前楼层（向后兼容访问入口）。"""
        return self.floors[self.current_floor]


# ─── State copy ──────────────────────────────────────────────────────────────

def _copy_state(state: GameState) -> GameState:
    h = state.hero
    new_hero = HeroState(
        x=h.x, y=h.y, hp=h.hp, atk=h.atk, def_=h.def_, mdef=h.mdef,
        gold=h.gold, kill_count=h.kill_count,
        keys=dict(h.keys), items=dict(h.items), flags=dict(h.flags),
    )
    new_floors: dict = {}
    for fid, f in state.floors.items():
        new_floors[fid] = FloorState(
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
            _event_pending_choices=list(f._event_pending_choices),
            _event_pending_xy=f._event_pending_xy,
            down_floor=f.down_floor,
            up_floor=f.up_floor,
            first_arrive=f.first_arrive,
            after_get_item=f.after_get_item,
            _first_arrive_done=f._first_arrive_done,
        )
    return GameState(
        hero=new_hero,
        floors=new_floors,
        current_floor=state.current_floor,
        floor_ids=state.floor_ids,
        visited_floors=set(state.visited_floors),
        pending_floor_change=dict(state.pending_floor_change) if state.pending_floor_change else None,
        _floors_dir=state._floors_dir,
    )


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

    raw_map = data["map"]
    H = len(raw_map)
    W = len(raw_map[0]) if H else 0
    terrain = [[0] * W for _ in range(H)]
    entities = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            t = raw_map[y][x]
            if t in tile_to_entity:
                entities[y][x] = t
            else:
                terrain[y][x] = t

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
        down_floor=data.get("downFloor"),
        up_floor=data.get("upFloor"),
        first_arrive=data.get("firstArrive", []),
        after_get_item=data.get("afterGetItem", {}),
    )


# ─── Floor helpers ───────────────────────────────────────────────────────────

def _load_floor_if_needed(state: GameState, floor_id: str) -> bool:
    """尝试加载楼层，若文件不存在则静默返回 False（楼梯视为不可通行）。"""
    if floor_id in state.floors:
        return True
    path = state._floors_dir / f"{floor_id}.json"
    if not path.exists():
        return False
    state.floors[floor_id] = load_floor(path)
    return True


def _resolve_floor_id(state: GameState, expr: str) -> str:
    if not expr.startswith(":"):
        return expr
    idx = state.floor_ids.index(state.current_floor)
    if expr == ":next":
        return state.floor_ids[idx + 1]
    if expr == ":before":
        return state.floor_ids[idx - 1]
    return expr


def _execute_floor_fly(state: GameState, target_floor_id: str) -> None:
    """fly魔杖切层：按 §I.3.2 落点规则切换到目标楼层。"""
    from_index = state.floor_ids.index(state.current_floor)
    to_index = state.floor_ids.index(target_floor_id)
    # §I.3.2: fromIndex ≤ toIndex → 目标层 downFloor；否则 upFloor
    use_down = from_index <= to_index
    if not _load_floor_if_needed(state, target_floor_id):
        return  # 目标楼层未提取，fly 操作失败（不切层）
    target = state.floors[target_floor_id]
    coords = target.down_floor if use_down else target.up_floor
    if coords:
        state.hero.x, state.hero.y = coords[0], coords[1]
    state.current_floor = target_floor_id
    state.visited_floors.add(target_floor_id)


def _apply_stair_change(state: GameState) -> bool:
    """检查英雄是否踩上楼梯 changeFloor 格，若是则立即切层。返回是否发生了切层。
    若目标楼层文件不存在（范围外），视为不可通行，返回 False。"""
    loc_key = f"{state.hero.x},{state.hero.y}"
    cf = state.floor.change_floor.get(loc_key)
    if cf is None:
        return False
    # h5mota: show 指令激活前 enable=False，楼梯不触发
    ev = state.floor.events.get(loc_key)
    if isinstance(ev, dict) and ev.get("enable") is False:
        return False
    target_id = _resolve_floor_id(state, cf["floorId"])
    if not _load_floor_if_needed(state, target_id):
        return False  # 目标楼层未提取，楼梯不可用
    stair = cf["stair"]  # "downFloor" or "upFloor"
    target = state.floors[target_id]
    coords = target.down_floor if stair == "downFloor" else target.up_floor
    if coords:
        state.hero.x, state.hero.y = coords[0], coords[1]
    state.current_floor = target_id
    state.visited_floors.add(target_id)
    return True


# ─── Public entry point ──────────────────────────────────────────────────────

def step(state: GameState, action: str) -> GameState:
    """Pure function: apply one action token to state, return new state."""
    state = _copy_state(state)

    # fly魔杖切层（FLOOR:MTn token）
    if action.startswith("FLOOR:"):
        _execute_floor_fly(state, action[6:])
        return state

    # 道具使用（ITEM:n）— upFly/downFly 等（MT1-MT11 段无此 token，暂为 no-op）
    if action.startswith("ITEM:"):
        _check_auto_events(state)
        return state

    floor = state.floor

    # firstArrive：首次踏上该楼层时立即执行（可能设置拦截状态，由后续 CHOICE token 消费）
    if not floor._first_arrive_done and floor.first_arrive:
        floor._first_arrive_done = True
        _execute_event_list(state, floor.first_arrive, 0, 0)
        floor = state.floor  # firstArrive 可能切层，重新绑定

    # 拦截型事件激活：勇者移动被暂停，等待 CHOICE token
    if floor._event_intercepting:
        if action.startswith("CHOICE:"):
            n = int(action.split(":")[1])
            choices = floor._event_pending_choices
            remaining = floor._event_pending_instrs
            ex, ey = floor._event_pending_xy
            floor._event_intercepting = False
            floor._event_pending_choices = []
            floor._event_pending_instrs = []
            # 若是 choices 型事件，执行选中分支的 action 列表
            if choices and 0 <= n < len(choices):
                _execute_event_list(state, choices[n].get("action", []), ex, ey)
            # 执行后续主流程剩余指令（无再次拦截时）
            if not state.floor._event_intercepting and remaining:
                _execute_event_list(state, remaining, ex, ey)
        _check_auto_events(state)
        return state

    if action in ("U", "D", "L", "R"):
        _process_move(state, action)

    # 优先处理事件 changeFloor 设置的切层
    if state.pending_floor_change:
        pfc = state.pending_floor_change
        state.pending_floor_change = None
        _load_floor_if_needed(state, pfc["floor_id"])
        state.hero.x, state.hero.y = pfc["x"], pfc["y"]
        state.current_floor = pfc["floor_id"]
        state.visited_floors.add(pfc["floor_id"])
        return state

    # 检查英雄是否踏上楼梯
    if _apply_stair_change(state):
        return state

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

    t_tile = floor.terrain[ny][nx]
    e_tile = floor.entities[ny][nx]

    if t_tile in WALL_TILES or t_tile == SPECIAL_DOOR:
        return

    if e_tile in floor._tile_to_enemy:
        _fight_monster(state, nx, ny)
        return

    if e_tile in floor._tile_to_item:
        _pickup_item(state, nx, ny)
        hero.x, hero.y = nx, ny
        _fire_events(state, nx, ny)
        return

    if e_tile in floor._tile_to_entity:
        ev = floor.events.get(f"{nx},{ny}")
        # 事件已禁用（enable: false）→ hero 直接通过（如 MT1 作者NPC）
        if isinstance(ev, dict) and ev.get("enable") is False:
            hero.x, hero.y = nx, ny
            return
        # 有激活事件（如 MT2 小偷列表事件）→ 触发；hide 清实体后 hero 可移入
        if ev is not None:
            _fire_events(state, nx, ny)
            cur_fl = state.floors.get(state.current_floor)
            if (cur_fl and not cur_fl._event_intercepting
                    and 0 <= ny < len(cur_fl.entities)
                    and 0 <= nx < len(cur_fl.entities[ny])
                    and cur_fl.entities[ny][nx] == 0):
                hero.x, hero.y = nx, ny
            return
        # 无楼层事件的 NPC（老人/商人等）→ 交互为 no-op：hero 停在原格
        # 路线中 CHOICE token 若随后到来，在非拦截状态下也是 no-op，不影响重放
        return

    if t_tile in DOOR_KEY_MAP:
        key_id = DOOR_KEY_MAP[t_tile]
        if hero.keys.get(key_id, 0) > 0:
            hero.keys[key_id] -= 1
            floor.terrain[ny][nx] = 0
            # 英雄不移入门格，下一个同向 token 走入（h5mota 引擎行为）
        return

    hero.x, hero.y = nx, ny
    _fire_events(state, nx, ny)


# ─── Combat ──────────────────────────────────────────────────────────────────

def _fight_monster(state: GameState, mx: int, my: int) -> None:
    hero = state.hero
    floor = state.floor

    tile = floor.entities[my][mx]
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
        return

    hero.hp -= result.damage
    hero.gold += m.get("gold", 0)
    hero.kill_count += 1
    floor.entities[my][mx] = 0
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
    tile = floor.entities[iy][ix]
    item_id = floor._tile_to_item[tile]
    floor.entities[iy][ix] = 0

    if item_id in _KEY_ITEMS:
        hero.keys[item_id] = hero.keys.get(item_id, 0) + 1
    else:
        idata = floor._items_db.get(item_id)
        if idata:
            effect = idata.get("pickup")
            if effect is None:
                hero.items[item_id] = hero.items.get(item_id, 0) + 1
            else:
                _apply_item_effect(hero, effect, floor.ratio)

    loc_key = f"{ix},{iy}"
    agi = floor.after_get_item.get(loc_key)
    if agi:
        _execute_event_list(state, agi, ix, iy)


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
                # 同步动画之后的对话 → 拦截型事件
                floor._event_intercepting = True
                floor._event_pending_instrs = list(event_list[i + 1:])
                floor._event_pending_choices = []
                floor._event_pending_xy = (event_x, event_y)
                return
            continue
        if isinstance(instr, dict):
            t = instr.get("type", "")

            # choices 型事件：始终拦截（不需要 sync anim 前置）
            if t == "choices":
                floor._event_intercepting = True
                floor._event_pending_choices = list(instr.get("choices", []))
                floor._event_pending_instrs = list(event_list[i + 1:])
                floor._event_pending_xy = (event_x, event_y)
                return

            # 同步的 move → 进入阻塞动画上下文（generateMove 是 h5mota 异步动画指令，不阻塞事件流）
            if t == "move" and not instr.get("async", False):
                ctx["had_sync_anim"] = True

            _execute_instruction(state, instr, event_x, event_y, ctx)

            # 指令执行后：传播拦截状态
            if floor._event_intercepting:
                outer_rest = list(event_list[i + 1:])
                if outer_rest:
                    floor._event_pending_instrs = floor._event_pending_instrs + outer_rest
                return

            # changeFloor 指令触发后：停止执行本层剩余事件
            if state.pending_floor_change is not None:
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
    if t in (
        "waitAsync", "sleep", "playBgm", "playSound", "setBgFgBlock",
        "setCurtain", "tip", "for", "function", "win", "vibrate",
        "setFg", "setBg", "flashBack", "fadeOut", "fadeIn", "scroll",
        "showStatusBar", "setStatusBar", "achievementGet",
    ):
        return

    # ── show ──────────────────────────────────────────────────────────────────
    if t == "show":
        for loc in instr.get("loc", []):
            lx, ly = loc[0], loc[1]
            lk = f"{lx},{ly}"
            ev = floor.events.get(lk)
            if isinstance(ev, dict):
                ev["enable"] = True
        return

    # ── hide ─────────────────────────────────────────────────────────────────
    if t == "hide":
        target_fid = instr.get("floorId")
        if target_fid and target_fid != state.current_floor:
            # 跨层 hide：仅当目标层已加载时应用
            if target_fid in state.floors:
                tf = state.floors[target_fid]
                loc_param = instr.get("loc")
                if loc_param is not None:
                    for loc in loc_param:
                        lx, ly = loc[0], loc[1]
                        if instr.get("remove"):
                            tf._suppressed_events.add(f"{lx},{ly}")
                        tf.entities[ly][lx] = 0
            return
        loc_param = instr.get("loc")
        if loc_param is not None:
            for loc in loc_param:
                lx, ly = loc[0], loc[1]
                if instr.get("remove"):
                    floor._suppressed_events.add(f"{lx},{ly}")
                floor.entities[ly][lx] = 0   # 清除实体（NPC/怪/道具）
        else:
            if instr.get("remove"):
                floor._suppressed_events.add(f"{event_x},{event_y}")
            floor.entities[event_y][event_x] = 0  # 无 loc 时清除事件触发格实体
        return

    # ── setBlock ──────────────────────────────────────────────────────────────
    if t == "setBlock":
        num_raw = instr.get("number", 0)
        try:
            num = int(num_raw)
        except (ValueError, TypeError):
            # String entity ID → look up tile integer
            num = floor._id_to_tile.get(str(num_raw), 0)
        for loc in instr.get("loc", []):
            lx, ly = loc[0], loc[1]
            if num == 0:
                floor.entities[ly][lx] = 0
                floor.terrain[ly][lx] = 0
            elif num in floor._tile_to_entity:
                floor.entities[ly][lx] = num
            else:
                floor.terrain[ly][lx] = num
                floor.entities[ly][lx] = 0
        return

    # ── openDoor ──────────────────────────────────────────────────────────────
    if t == "openDoor":
        loc = instr.get("loc")
        lx, ly = (event_x, event_y) if loc is None else (loc[0], loc[1])
        floor.terrain[ly][lx] = 0
        return

    # ── closeDoor ─────────────────────────────────────────────────────────────
    if t == "closeDoor":
        loc = instr.get("loc")
        lx, ly = (event_x, event_y) if loc is None else (loc[0], loc[1])
        floor.terrain[ly][lx] = _DOOR_ID_TO_TILE.get(instr.get("id", ""), 85)
        return

    # ── setValue ──────────────────────────────────────────────────────────────
    if t == "setValue":
        _set_value(state, instr.get("name", ""), instr.get("value", ""),
                   instr.get("operator"))
        return

    # ── changeFloor ───────────────────────────────────────────────────────────
    if t == "changeFloor":
        target_id = _resolve_floor_id(state, instr.get("floorId", ""))
        loc = instr.get("loc", [0, 0])
        state.pending_floor_change = {"floor_id": target_id, "x": loc[0], "y": loc[1]}
        return

    # ── move / generateMove ───────────────────────────────────────────────────
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
            tile_id = floor.entities[sy][sx]
            floor.entities[sy][sx] = 0
        else:
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

    if part.startswith("flag:"):
        return bool(hero.flags.get(part[5:], False))

    m = re.match(r"\(?blockId:(\d+),(\d+)\s*===\s*'(\w+)'\)?", part)
    if m:
        bx, by, bid = int(m.group(1)), int(m.group(2)), m.group(3)
        return floor._tile_to_entity.get(floor.entities[by][bx]) == bid

    m = re.match(r"core\.getBlockId\((\d+),\s*(\d+)\)\s*===\s*null", part)
    if m:
        bx, by = int(m.group(1)), int(m.group(2))
        return floor.entities[by][bx] not in floor._tile_to_entity

    return False


# ─── setValue helper ─────────────────────────────────────────────────────────

def _set_value(state: GameState, name: str, value, operator: str | None = None) -> None:
    hero = state.hero
    if isinstance(value, str):
        if value == "true":
            val: object = True
        elif value == "false":
            val = False
        elif value == "null":
            val = None
        else:
            try:
                val = int(value)
            except ValueError:
                val = value
    else:
        val = value

    if name.startswith("flag:"):
        key = name[5:]
        if operator == "+=":
            current = hero.flags.get(key, 0)
            if current is None:
                current = 0
            numeric_val = val if isinstance(val, (int, float)) else 1
            hero.flags[key] = current + numeric_val
        else:
            hero.flags[key] = val
    elif name.startswith("switch:"):
        hero.flags[f"switch:{name[7:]}"] = val
    elif name.startswith("status:money"):
        hero.gold = int(val) if val is not None else 0
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
