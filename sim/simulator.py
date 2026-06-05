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
# fakeWall(2) 和 fakeWall2(3)：trigger="openDoor",keys={}，踩上自动开门，触发 afterOpenDoor
AUTO_OPEN_TILES = {2, 3}
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
_MOVE_DIR = {
    "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
    "rightdown": (1, 1), "leftdown": (-1, 1), "rightup": (1, -1), "leftup": (-1, -1),
}
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
    after_battle: dict      # shared reference
    after_open_door: dict   # shared reference
    auto_event: dict        # shared reference
    change_floor: dict  # shared reference
    _items_db: dict     # shared reference
    _monsters_db: dict  # shared reference
    _tile_to_enemy: dict    # {tile_int: monster_id}
    _tile_to_item: dict     # {tile_int: item_id}
    _tile_to_entity: dict        # {tile_int: entity_id} (enemies + items + npcs)
    _id_to_tile: dict            # {entity_id: tile_int}
    _tile_to_common_event: dict  # {tile_int: common_event_name} for NPC tiles
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
    # 隐藏层标记（来自 JSON isHide）：楼梯 :next/:before 解析对隐藏层透明（跳过），
    # 隐藏层只能用 upFly/downFly 进入。本塔仅 MT44。见 mechanics §I.5。
    is_hide: bool = False
    # firstArrive / afterGetItem（来自 JSON）
    first_arrive: list = field(default_factory=list)
    after_get_item: dict = field(default_factory=dict)
    _first_arrive_done: bool = False
    _event_break: bool = False
    # 不可通行地形 tile 集合（数据驱动，来自 tiles.json noPass:true：墙/熔岩/祭坛半格等）
    _no_pass_tiles: set = field(default_factory=set)
    # 大型怪 footprint（数据驱动，来自 monsters.json footprint 字段）：{怪 tile_int: [(dx,dy),...]}。
    # 怪实体存活时，其相对偏移覆盖的格全部 noPass（bigImage 多格碰撞，如魔龙/章鱼九宫格）。
    _monster_footprints: dict = field(default_factory=dict)
    # NPC tile → trigger 语义（数据驱动，来自 tiles.json npcs.trigger，如 122→"trader"）
    _tile_to_trigger: dict = field(default_factory=dict)
    # 全量 id→tile（覆盖 walls/terrains/animates/items/enemys/npcs）：
    # 供 setBlock 字符串 number（如 "specialDoor"/"yellowWall"）与 searchBlock 反查。见 mechanics §M.5/M.6
    _id_to_tile_full: dict = field(default_factory=dict)
    # 全量 tile→id 字符串（getBlockId 语义，来自 tiles.json id 字段）：
    # 供 centerFly 落点判定（认 'airwall' 等）。见 mechanics §I.6
    _tile_to_id: dict = field(default_factory=dict)
    # 可被地震卷轴 earthquake 破坏的 tile 集合（数据驱动，来自 tiles.json canBreak:true）。
    # 引擎 earthquake.useItemEffect = searchBlockWithFilter(block.event.canBreak)→openDoor。见 mechanics §L.6
    _can_break_tiles: set = field(default_factory=set)

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
    dead: bool = False     # 勇者死亡(HP≤0)硬终止：置位后 step() 对一切 token no-op。见 mechanics §M.8
    _common_events: dict = field(default_factory=dict)
    _merchants: dict = field(default_factory=dict)  # 商人目录缓存 {floorId@x@y: {price, give}}
    # setEnemy 临时改怪：{monster_id: {attr: value}}。special 存为 list（见 mechanics §M.1/M.4）
    _enemy_overrides: dict = field(default_factory=dict)
    # 存档键盘快捷键绑定 {keyCode_int: item_id}（数据驱动，来自 data/<塔>/replay_keybindings.json）。
    # KEY:<keyCode> token 按此表派发为使用对应道具；无绑定则 no-op。绝不在 sim 硬编码键→道具。
    _key_bindings: dict = field(default_factory=dict)

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
            after_open_door=f.after_open_door,
            auto_event=f.auto_event,
            change_floor=f.change_floor,
            _items_db=f._items_db,
            _monsters_db=f._monsters_db,
            _tile_to_enemy=f._tile_to_enemy,
            _tile_to_item=f._tile_to_item,
            _tile_to_entity=f._tile_to_entity,
            _id_to_tile=f._id_to_tile,
            _tile_to_common_event=f._tile_to_common_event,
            _suppressed_events=set(f._suppressed_events),
            _done_after_battle=set(f._done_after_battle),
            _event_intercepting=f._event_intercepting,
            _event_pending_instrs=list(f._event_pending_instrs),
            _event_pending_choices=list(f._event_pending_choices),
            _event_pending_xy=f._event_pending_xy,
            _event_break=f._event_break,
            down_floor=f.down_floor,
            up_floor=f.up_floor,
            first_arrive=f.first_arrive,
            after_get_item=f.after_get_item,
            _first_arrive_done=f._first_arrive_done,
            _no_pass_tiles=f._no_pass_tiles,
            _tile_to_trigger=f._tile_to_trigger,
            _id_to_tile_full=f._id_to_tile_full,
            _monster_footprints=f._monster_footprints,
            _tile_to_id=f._tile_to_id,
            _can_break_tiles=f._can_break_tiles,
            is_hide=f.is_hide,
        )
    return GameState(
        hero=new_hero,
        floors=new_floors,
        current_floor=state.current_floor,
        floor_ids=state.floor_ids,
        visited_floors=set(state.visited_floors),
        pending_floor_change=dict(state.pending_floor_change) if state.pending_floor_change else None,
        _floors_dir=state._floors_dir,
        _common_events=state._common_events,
        _merchants=state._merchants,
        _enemy_overrides={k: dict(v) for k, v in state._enemy_overrides.items()},
        _key_bindings=state._key_bindings,
        dead=state.dead,
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
    tile_to_common_event: dict = {}
    tile_to_trigger: dict = {}
    for k, v in tiles_db.get("npcs", {}).items():
        tile_to_entity[int(k)] = v["id"]
        if "_commonEvent" in v:
            tile_to_common_event[int(k)] = v["_commonEvent"]
        if "trigger" in v:
            tile_to_trigger[int(k)] = v["trigger"]

    id_to_tile = {v: int(k) for k, v in tile_to_entity.items()}

    # 全量 id→tile（覆盖所有分段：walls/terrains/animates/items/enemys/npcs）。
    # 实体用 _monster/_item，其余用 id。首次出现优先（避免重复 id 覆盖）。供 setBlock 字符串/searchBlock。
    id_to_tile_full: dict = {}
    tile_to_id: dict = {}
    for entries in tiles_db.values():
        if not isinstance(entries, dict):
            continue
        for k, v in entries.items():
            if not isinstance(v, dict):
                continue
            try:
                tid = int(k)
            except (ValueError, TypeError):
                continue
            ident = v.get("id") or v.get("_monster") or v.get("_item")
            if ident and ident not in id_to_tile_full:
                id_to_tile_full[ident] = tid
            if v.get("id") and tid not in tile_to_id:
                tile_to_id[tid] = v["id"]

    # 数据驱动收集不可通行地形 tile（tiles.json 任意段中 noPass:true 且非实体）。
    # 取代仅靠硬编码 WALL_TILES：祭坛半格(7/8)等塔特有装饰墙由数据声明。
    no_pass_tiles: set = set()
    for entries in tiles_db.values():
        if not isinstance(entries, dict):
            continue
        for k, v in entries.items():
            if isinstance(v, dict) and v.get("noPass") is True:
                tid = int(k)
                if tid not in tile_to_entity:
                    no_pass_tiles.add(tid)

    # 可被地震卷轴破坏的 tile 集合（数据驱动，tiles.json 任意段 canBreak:true）。
    # 引擎 earthquake 按 block.event.canBreak 过滤；本塔 = {1 yellowWall, 2 fakeWall}（3 fakeWall2=false）。
    can_break_tiles: set = set()
    for entries in tiles_db.values():
        if not isinstance(entries, dict):
            continue
        for k, v in entries.items():
            if isinstance(v, dict) and v.get("canBreak") is True:
                can_break_tiles.add(int(k))

    # 大型怪 footprint（数据驱动）：怪 tile → 相对偏移列表。来自 monsters.json 的 footprint 字段。
    monster_footprints: dict = {}
    for tnum, mid in tile_to_enemy.items():
        fp = monsters_db.get(mid, {}).get("footprint")
        if fp:
            monster_footprints[tnum] = [(int(o[0]), int(o[1])) for o in fp]

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
        after_open_door=data.get("afterOpenDoor", {}),
        auto_event=data.get("autoEvent", {}),
        change_floor=data.get("changeFloor", {}),
        _items_db=items_db,
        _monsters_db=monsters_db,
        _tile_to_enemy=tile_to_enemy,
        _tile_to_item=tile_to_item,
        _tile_to_entity=tile_to_entity,
        _id_to_tile=id_to_tile,
        _tile_to_common_event=tile_to_common_event,
        _suppressed_events=set(),
        _done_after_battle=set(),
        down_floor=data.get("downFloor"),
        up_floor=data.get("upFloor"),
        is_hide=data.get("isHide", False),
        first_arrive=data.get("firstArrive", []),
        after_get_item=data.get("afterGetItem", {}),
        _no_pass_tiles=no_pass_tiles,
        _tile_to_trigger=tile_to_trigger,
        _id_to_tile_full=id_to_tile_full,
        _monster_footprints=monster_footprints,
        _tile_to_id=tile_to_id,
        _can_break_tiles=can_break_tiles,
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
    step = 1 if expr == ":next" else -1 if expr == ":before" else 0
    if step == 0:
        return expr
    # 跳过隐藏层（isHide=true）：引擎对楼梯序列中的隐藏层透明（同 floorTofloor 递归跳过），
    # 隐藏层只能用 upFly/downFly 进入。本塔表现为 MT43↔MT45 楼梯直连（跳过 MT44）。见 §I.5。
    i = idx + step
    while 0 <= i < len(state.floor_ids):
        fid = state.floor_ids[i]
        if _load_floor_if_needed(state, fid) and state.floors[fid].is_hide:
            i += step
            continue
        return fid
    return state.floor_ids[idx + step]  # 越界兜底（理论不触发）


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

def _use_snow(state: GameState) -> None:
    """冰魔法 snow（cls=constants，永久持有不消耗）：移除英雄四方向相邻 lava，
    该格 tile→0 永久变空地。lava 的 tile 号经 _id_to_tile_full['lava'] 数据驱动解析，
    不硬编码。来源 §K.4（snowFourDirections=true）。"""
    floor = state.floor
    lava = floor._id_to_tile_full.get("lava")
    if lava is None:
        return
    hx, hy = state.hero.x, state.hero.y
    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        nx, ny = hx + dx, hy + dy
        if 0 <= ny < rows and 0 <= nx < cols and floor.terrain[ny][nx] == lava:
            floor.terrain[ny][nx] = 0


def _center_fly_can_land(floor: "FloorState", x: int, y: int) -> bool:
    """centerFly 落点判定（canUseItemEffect）：对称点 getBlockId ∈ {null,'none','airwall'}。
    = 空地/已清除(entity=0 且 terrain=0→getBlockId=null)、airwall(getBlockId='airwall')。
    本塔 tiles.json 未收录 id='none' 装饰地板，若后续落点命中再扩展。
    墙/fakeWall/门/楼梯/普通地形/怪/道具均拦截。注意：这是与常规移动 noPass 独立的另一套
    判定——airwall 移动不可通行，但 centerFly 可落。来源 §I.6。"""
    if floor.entities[y][x] != 0:
        return False
    ter = floor.terrain[y][x]
    if ter == 0:
        return True
    return floor._tile_to_id.get(ter) == "airwall"


def _use_center_fly(state: GameState) -> None:
    """centerFly（瞬移，cls=tools）：中心对称瞬移到 (W-1-x, H-1-y)，不切层。
    canUseItemEffect 校验对称点可落，否则整体 no-op（不瞬移、不消耗）。
    tools 类使用成功后消耗 1（_afterUseItem，见 §K.2）。来源 §I.6。"""
    hero, floor = state.hero, state.floor
    if hero.items.get("centerFly", 0) <= 0:
        return
    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    tx, ty = cols - 1 - hero.x, rows - 1 - hero.y
    if not (0 <= tx < cols and 0 <= ty < rows):
        return
    if not _center_fly_can_land(floor, tx, ty):
        return
    hero.x, hero.y = tx, ty
    hero.items["centerFly"] -= 1
    if hero.items["centerFly"] <= 0:
        del hero.items["centerFly"]


def _use_earthquake(state: GameState) -> None:
    """地震卷轴 earthquake（cls=tools，可破坏一层楼的墙）。
    引擎 useItemEffect：searchBlockWithFilter(block => !block.disable && block.event.canBreak)
    对每个命中块 openDoor → 清当前层全图所有 canBreak 墙格（本塔 = tile 1 yellowWall / 2 fakeWall）。
    canBreak 集合数据驱动来自 tiles.json（floor._can_break_tiles），不硬编码 tile 号。
    canUseItemEffect=true（无前置）；tools 类使用成功消耗 1。来源 §L.6（items.js toString）。"""
    hero, floor = state.hero, state.floor
    if hero.items.get("earthquake", 0) <= 0:
        return
    breakable = floor._can_break_tiles
    if breakable:
        rows = len(floor.terrain)
        cols = len(floor.terrain[0]) if rows else 0
        for y in range(rows):
            row = floor.terrain[y]
            for x in range(cols):
                if row[x] in breakable:
                    row[x] = 0  # openDoor：地形格清为空地（可达性实时重算自动生效）
    hero.items["earthquake"] -= 1
    if hero.items["earthquake"] <= 0:
        del hero.items["earthquake"]


def _use_pickaxe(state: GameState) -> None:
    """破墙镐 pickaxe（cls=tools）：破坏英雄【四方向相邻】、event.canBreak 的墙块。来源 §L（引擎 pickaxe.useItemEffect toString，2026-06-04）。
    引擎逐条：core.utils.scan 四方向相邻 → 每个 canBreak 块 openDoor(async)。
    与 earthquake 同 canBreak 口径(floor._can_break_tiles，本塔 = yellowWall/fakeWall)，区别仅范围：镐=相邻4格、震=整层。
    无 afterBattle/金币/经验；canUseItemEffect=true（无前置）；tools 用后 -1。"""
    hero, floor = state.hero, state.floor
    if hero.items.get("pickaxe", 0) <= 0:
        return
    breakable = floor._can_break_tiles
    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):  # 上/左/下/右，与 core.utils.scan 同序
        x, y = hero.x + dx, hero.y + dy
        if 0 <= x < cols and 0 <= y < rows and floor.terrain[y][x] in breakable:
            floor.terrain[y][x] = 0  # openDoor：破墙→空地（可达性实时重算自动生效）
    hero.items["pickaxe"] -= 1
    if hero.items["pickaxe"] <= 0:
        del hero.items["pickaxe"]


def _use_big_key(state: GameState) -> None:
    """魔法钥匙 bigKey（引擎名"魔法钥匙"，cls=tools；sim 存于 hero.keys）：开当前层【所有 yellowDoor】。
    引擎 useItemEffect（core.material.items.bigKey.useItemEffect toString，2026-06-05 实测）：
        core.searchBlock("yellowDoor").map(b => openDoor loc:[b.x,b.y] async); waitAsync; tip(...)
    即把当前层每一扇黄门 openDoor→空地。**仅黄门**（searchBlock 只查 'yellowDoor'，蓝/红/绿/铁门不开）；
    canUseItemEffect=true（无前置）；cls=tools 用后 -1（§K.2）。openDoor 语义与本 sim 既有 openDoor action
    一致 = terrain 置 0（不触发 afterOpenDoor，本塔 MT41 afterOpenDoor 为空）。yellowDoor tile 取模块通用
    映射 _DOOR_ID_TO_TILE（与 openDoor/closeDoor 同源，h5mota 引擎通用约定，非塔特有硬编码）。"""
    hero, floor = state.hero, state.floor
    if hero.keys.get("bigKey", 0) <= 0:
        return
    yd = _DOOR_ID_TO_TILE["yellowDoor"]
    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    for y in range(rows):
        row = floor.terrain[y]
        for x in range(cols):
            if row[x] == yd:
                row[x] = 0  # openDoor：黄门→空地（可达性实时重算自动生效）
    hero.keys["bigKey"] -= 1
    if hero.keys["bigKey"] <= 0:
        del hero.keys["bigKey"]


def _use_super_potion(state: GameState) -> None:
    """圣水 superPotion（cls=tools）：HP += round(0.74*(atk+def))*10，用后 -1。
    来源 items.js useItemEffect 字面量（§B.3）。round = JS Math.round = floor(x+0.5)，
    x=0.74*(atk+def) 恒正，用 int(x+0.5) 实现。获取自 MT16 老人 item:superPotion+=1。"""
    hero = state.hero
    if hero.items.get("superPotion", 0) <= 0:
        return
    heal = int(0.74 * (hero.atk + hero.def_) + 0.5) * 10
    hero.hp += heal
    hero.items["superPotion"] -= 1
    if hero.items["superPotion"] <= 0:
        del hero.items["superPotion"]


def _use_floor_fly_item(state: GameState, item_id: str, step_dir: int) -> None:
    """upFly(step_dir=+1)/downFly(step_dir=-1)：切到当前层 floorIds 下标 ±1 的楼层。
    与 fly 魔杖（_execute_floor_fly）不同：
      - 落点 = 当前英雄坐标(x,y)，【不】使用目标层 up/downFloor 字段；
      - 【不】检查 canFlyTo/canFlyFrom/hasVisitedFloor → 可进入隐藏层(如 MT44)；
      - 硬编码限制：upFly index>=49 拒绝、downFly index<1 拒绝；
      - canUseItemEffect：目标层该坐标须为空(getBlockId==null = 无地形块且无实体)。
    校验不过则整体 no-op(不切层、不消耗)。成功消耗 1。来源 §I.7（引擎 toString）。"""
    hero = state.hero
    if hero.items.get(item_id, 0) <= 0:
        return
    idx = state.floor_ids.index(state.current_floor)
    if step_dir > 0 and idx >= 49:   # upFly 硬顶
        return
    if step_dir < 0 and idx < 1:     # downFly 硬底
        return
    tgt_idx = idx + step_dir
    if not (0 <= tgt_idx < len(state.floor_ids)):
        return
    target_id = state.floor_ids[tgt_idx]
    if not _load_floor_if_needed(state, target_id):
        return
    target = state.floors[target_id]
    x, y = hero.x, hero.y
    rows = len(target.terrain)
    cols = len(target.terrain[0]) if rows else 0
    if not (0 <= x < cols and 0 <= y < rows):
        return
    if target.terrain[y][x] != 0 or target.entities[y][x] != 0:
        return  # 目标格非空（getBlockId!=null）→ 拒绝
    state.current_floor = target_id
    state.visited_floors.add(target_id)
    hero.items[item_id] -= 1
    if hero.items[item_id] <= 0:
        del hero.items[item_id]


def _enemy_gold(hero: HeroState, base: int) -> int:
    """战斗击杀金币结算：拥有幸运金币(coin, tile53, MT0(6,6) 拾取)后金币×2（被动经济道具）。
    效果来源：common_events.json 图书馆提示「拥有它在打败敌人后能获得2倍的金钱」+ items.json coin(cls=constants/use=null)。
    覆盖普通战 _fight_monster 与 battle 指令 _forced_battle 两条击杀路径。
    ⚠ bomb 炸杀(_use_bomb)分支【暂不乘】：本 route bomb(tok4524 MT44) 在 coin 拾取(MT0, tok4921 之后)之前，
    二者不同时发生；bomb×coin 交互的引擎 afterBattle 源码未抓取，solver 启动前必须坐实，登记于 mechanics §J。"""
    return base * 2 if hero.items.get("coin", 0) > 0 else base


def _use_bomb(state: GameState) -> None:
    """炸弹(tile49, cls=tools)：炸掉英雄四方向相邻、hp<500 的敌人。来源 §I.7（引擎 bomb.useItemEffect toString）。
    引擎逐条：
      - 范围：core.utils.scan = 上/左/下/右 四个【相邻】格（非 8 格）。
      - 可炸条件 canBomb：该格 block.event.trigger=='battle' 且 cls 以 'enemy' 开头，
        且 getEnemyValue(enemy,'hp',x,y) < 500（严格小于）。hp>=500(boss级)跳过该格。
      - 不可炸格逐个 return 跳过，不影响其余；canUseItemEffect 恒 true（无目标也消耗）。
      - 奖励：累加 money(金币 += getEnemyInfo.money)；无经验、引擎无 kill 计数概念。
      - 移除→触发：先 removeBlockByIndexes 批量移除，再 insertAction(todo) 统一跑每个被炸怪的
        floor.afterBattle[x,y]（+ enemy.afterBattle）。与正常战死【同一 afterBattle 路径】——
        这是 MT44 双 redGuard 炸死后 (6,8) openDoor 机关的触发命门。
      - 消耗：cls=tools → 用后 -1（_afterUseItem）。
    （注：enemy.afterBattle 本塔 redGuard 为空，sim 仅复刻 floor.afterBattle，与 _fight_monster 一致。）"""
    hero = state.hero
    if hero.items.get("bomb", 0) <= 0:
        return
    floor = state.floor
    rows = len(floor.entities)
    cols = len(floor.entities[0]) if rows else 0
    scan = [(0, -1), (-1, 0), (0, 1), (1, 0)]  # 上/左/下/右，与 core.utils.scan 同序
    kills = []  # [(x, y, monster_id)] 被炸怪，按 scan 顺序
    for dx, dy in scan:
        x, y = hero.x + dx, hero.y + dy
        if not (0 <= x < cols and 0 <= y < rows):
            continue
        monster_id = floor._tile_to_enemy.get(floor.entities[y][x])
        if monster_id is None:
            continue  # 非敌人格（地形/道具/门）跳过
        if _build_monster(state, monster_id).hp >= 500:
            continue  # boss级 hp>=500，炸不死，跳过该格
        kills.append((x, y, monster_id))

    # 先批量移除并结算金币（引擎 removeBlockByIndexes + money），再统一触发 afterBattle
    for x, y, monster_id in kills:
        floor.entities[y][x] = 0
        # bomb 炸杀金币【不】乘 coin×2（不走 _enemy_gold）：bomb×coin 交互待引擎 afterBattle 源码坐实，见 §J。
        # 本 route bomb(tok4524) 早于 coin 拾取(MT0)，二者不同时发生，此处不乘不影响回放正确性。
        hero.gold += floor._monsters_db[monster_id].get("gold", 0)
    for x, y, monster_id in kills:
        loc_key = f"{x},{y}"
        if loc_key in floor.after_battle and loc_key not in floor._done_after_battle:
            floor._done_after_battle.add(loc_key)
            _execute_event_list(state, floor.after_battle[loc_key], x, y)

    hero.items["bomb"] -= 1  # cls=tools 用后 -1（无目标也消耗，canUseItemEffect 恒 true）
    if hero.items["bomb"] <= 0:
        del hero.items["bomb"]


def _use_item_by_id(state: GameState, item_id: str | None) -> None:
    """按道具 id 派发使用效果（ITEM:<tile> 与 KEY:<keyCode> 快捷键共用）。
    未建模道具暂为 no-op。使用后统一检查 autoEvent。"""
    if item_id == "snow":
        _use_snow(state)
    elif item_id == "centerFly":
        _use_center_fly(state)
    elif item_id == "earthquake":
        _use_earthquake(state)
    elif item_id == "upFly":
        _use_floor_fly_item(state, "upFly", +1)
    elif item_id == "downFly":
        _use_floor_fly_item(state, "downFly", -1)
    elif item_id == "bomb":
        _use_bomb(state)
    elif item_id == "pickaxe":
        _use_pickaxe(state)
    elif item_id == "superPotion":
        _use_super_potion(state)
    elif item_id == "bigKey":
        _use_big_key(state)
    _check_auto_events(state)


def step(state: GameState, action: str) -> GameState:
    """Pure function: apply one action token to state, return new state.

    死亡硬终止（引擎机制，见 mechanics §M.8）：勇者 HP≤0 即 game over，
    之后一切 token 全部 no-op（不战斗/拾取/切层/触发事件），状态冻结在死亡点。
    任何绕过 canBattle 拦截的死亡来源（强制战斗 §M、地形伤、poison、事件扣血）
    都在此统一兜底——本 step 结束后若 HP≤0 即置 dead。"""
    if state.dead:
        return state  # 已死：冻结，原样返回（无副作用，等效 no-op）
    new_state = _step_impl(state, action)
    if new_state.hero.hp <= 0:
        new_state.dead = True
    return new_state


def _step_impl(state: GameState, action: str) -> GameState:
    state = _copy_state(state)

    # fly魔杖切层（FLOOR:MTn token）
    if action.startswith("FLOOR:"):
        _execute_floor_fly(state, action[6:])
        return state

    # 坐标直跳（MOVE:x:y）— h5mota moveDirectly；目标格 BFS 保证无 trigger，不触发任何事件
    if action.startswith("MOVE:"):
        parts = action.split(":")
        nx, ny = int(parts[1]), int(parts[2])
        if state.hero.flags.get("poison"):
            # ignoreSteps 近似为曼哈顿距离（真实 BFS 路径若更长则有偏，届时再改）
            ignore_steps = abs(nx - state.hero.x) + abs(ny - state.hero.y)
            state.hero.hp -= ignore_steps * 10  # poisonDamage = 10
        state.hero.x = nx
        state.hero.y = ny
        return state

    # 道具使用（ITEM:n，n=道具 tile）。按道具 id 派发；未建模道具暂为 no-op。
    if action.startswith("ITEM:"):
        tile = int(action.split(":", 1)[1])
        _use_item_by_id(state, state.floor._tile_to_item.get(tile))
        return state

    # 键盘快捷键（KEY:keyCode，引擎 key:<n>）：按存档绑定表派发为使用某道具。
    # 绑定来自 state._key_bindings（数据驱动）；无绑定则 no-op。绝不在此硬编码键→道具。
    if action.startswith("KEY:"):
        keycode = int(action.split(":", 1)[1])
        item_id = state._key_bindings.get(keycode)
        if item_id is not None:
            _use_item_by_id(state, item_id)
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
            # 执行后续主流程剩余指令（无再次拦截、无 break 时）
            if (not state.floor._event_intercepting
                    and remaining
                    and not state.floor._event_break):
                _execute_event_list(state, remaining, ex, ey)
            state.floor._event_break = False
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

def _in_alive_monster_footprint(floor: FloorState, nx: int, ny: int) -> bool:
    """大型怪（monsters.json 声明了 footprint）存活时，其相对偏移覆盖的格不可通过；
    怪本体格（偏移落回自身）除外，留给战斗判定，使"站正下方朝怪移动"仍能触发战斗。
    footprint 为相对怪实体的 (dx,dy) 偏移，引擎读数据，不硬编码具体怪。"""
    fps = floor._monster_footprints
    if not fps:
        return False
    ent = floor.entities
    H = len(ent)
    W = len(ent[0]) if H else 0
    for tile_num, offsets in fps.items():
        for dx, dy in offsets:
            ax, ay = nx - dx, ny - dy
            if (ax, ay) == (nx, ny):
                continue  # 偏移(0,0) → 怪本体格，留给战斗
            if 0 <= ay < H and 0 <= ax < W and ent[ay][ax] == tile_num:
                return True
    return False


# ─── 区域/地形伤（领域15 / 夹击16 / 阻击18）──────────────────────────────────
# 数据驱动：special 编号 + value/range/zoneSquare 全来自 monsters.json，sim 不认具体怪。
# 公式来源 mechanics §C.2/C.3/C.4（引擎 checkBlock）+ 阻击后退为玩家实测。
# 结算时机：英雄【走到】某格后立即结算该格所受区域伤（踩格瞬间，per-arrival）。
# 叠加：领域+阻击各自 value 累加(acc)；夹击在 acc 之上对剩余 HP 减半 floor((hp-acc)/2)。
# 免疫：flag:魔法免疫 全免；或各自 flag:no_zone / no_repulse / no_betweenAttack。
# 致死走 §M.8：hp≤0 置 state.dead 冻结，不再后退怪/触发本格事件。
_SP_ZONE = 15       # 领域
_SP_BETWEEN = 16    # 夹击
_SP_REPULSE = 18    # 阻击


def _enemy_special_set(state: GameState, mid: str) -> set:
    """怪的 special 集合（含 setEnemy 覆盖，与 _build_monster 口径一致）。"""
    ov = state._enemy_overrides.get(mid, {})
    sp = ov.get("special", state.floor._monsters_db.get(mid, {}).get("special", []))
    if isinstance(sp, int):
        sp = [sp] if sp else []
    return set(sp)


def _live_zone_monsters(state: GameState) -> list:
    """存活区域怪：entities 层有怪 tile 且 special 含 15/16/18。
    返回 [(mx,my,mid,sp_set,value,rng,zsq)]。"""
    floor = state.floor
    out = []
    for my, row in enumerate(floor.entities):
        for mx, tile in enumerate(row):
            mid = floor._tile_to_enemy.get(tile)
            if mid is None:
                continue
            sp = _enemy_special_set(state, mid)
            if sp & {_SP_ZONE, _SP_BETWEEN, _SP_REPULSE}:
                m = floor._monsters_db.get(mid, {})
                out.append((mx, my, mid, sp, m.get("value", 0),
                            m.get("range", 1) or 1, bool(m.get("zoneSquare", False))))
    return out


def _in_zone_range(x, y, mx, my, rng, square) -> bool:
    """(x,y) 在 (mx,my) 的领域内（不含怪本格）。square=方形(切比雪夫)，否则菱形(曼哈顿)。"""
    if (x, y) == (mx, my):
        return False
    ddx, ddy = abs(x - mx), abs(y - my)
    return max(ddx, ddy) <= rng if square else (ddx + ddy) <= rng


def _is_adjacent(x, y, mx, my, square) -> bool:
    """阻击影响格：正交相邻(距离1)；square 则含对角(8 相邻)。"""
    ddx, ddy = abs(x - mx), abs(y - my)
    return max(ddx, ddy) == 1 if square else (ddx + ddy) == 1


def _between_same_special16(state: GameState, x, y) -> bool:
    """(x,y) 被两个【同 id】special16 怪横向或纵向夹住（§C.4）。"""
    floor = state.floor
    ent = floor.entities
    H = len(ent)
    W = len(ent[0]) if H else 0

    def s16_id(cx, cy):
        if not (0 <= cy < H and 0 <= cx < W):
            return None
        mid = floor._tile_to_enemy.get(ent[cy][cx])
        if mid is None:
            return None
        return mid if _SP_BETWEEN in _enemy_special_set(state, mid) else None

    for (ax, ay), (bx, by) in (((x - 1, y), (x + 1, y)), ((x, y - 1), (x, y + 1))):
        a = s16_id(ax, ay)
        if a is not None and a == s16_id(bx, by):
            return True
    return False


def _repulse_monster(state: GameState, hx, hy, mx, my) -> None:
    """阻击怪后退一格：远离勇者方向(怪-勇者 单位向量延伸)。
    退路被墙/门/楼梯/任何实体/越界挡则不退（玩家实测）。games51 无 special18 怪，此分支休眠。"""
    floor = state.floor
    tx, ty = mx + (mx - hx), my + (my - hy)
    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    if not (0 <= ty < rows and 0 <= tx < cols):
        return
    t = floor.terrain[ty][tx]
    if t in WALL_TILES or t in floor._no_pass_tiles:
        return
    if t in DOOR_KEY_MAP or t == SPECIAL_DOOR or t in AUTO_OPEN_TILES:
        return
    if f"{tx},{ty}" in floor.change_floor:          # 楼梯
        return
    if floor.entities[ty][tx] != 0:                 # 道具/怪/NPC 占位
        return
    floor.entities[ty][tx] = floor.entities[my][mx]
    floor.entities[my][mx] = 0


def _apply_zone_damage(state: GameState, x: int, y: int) -> None:
    """英雄走到 (x,y) 后结算区域伤（§C.2/C.3/C.4 + 实测）。致死置 dead（§M.8）。"""
    hero = state.hero
    fl = hero.flags
    if fl.get("魔法免疫"):
        return
    zms = _live_zone_monsters(state)
    if not zms:
        return

    acc = 0
    repulse_hits = []
    for (mx, my, mid, sp, value, rng, zsq) in zms:
        if _SP_ZONE in sp and not fl.get("no_zone") and _in_zone_range(x, y, mx, my, rng, zsq):
            acc += value
        if _SP_REPULSE in sp and not fl.get("no_repulse") and _is_adjacent(x, y, mx, my, zsq):
            acc += value
            repulse_hits.append((mx, my))

    between = 0
    if not fl.get("no_betweenAttack") and hero.hp > acc and _between_same_special16(state, x, y):
        between = (hero.hp - acc) // 2   # floor；betweenAttackMax=false

    total = acc + between
    if total > 0:
        hero.hp -= total
        if hero.hp <= 0:
            state.dead = True
            return   # 死亡冻结：不再后退怪/触发本格事件（§M.8）

    for (mx, my) in repulse_hits:
        _repulse_monster(state, x, y, mx, my)


def _process_move(state: GameState, direction: str) -> None:
    hero = state.hero
    floor = state.floor
    dx, dy = _DIR[direction]
    nx, ny = hero.x + dx, hero.y + dy

    rows = len(floor.terrain)
    cols = len(floor.terrain[0]) if rows else 0
    if not (0 <= ny < rows and 0 <= nx < cols):
        return

    # 大型怪 footprint：存活时其覆盖格不可通过（怪本体格除外，留给下方战斗判定）。
    if _in_alive_monster_footprint(floor, nx, ny):
        return

    t_tile = floor.terrain[ny][nx]
    e_tile = floor.entities[ny][nx]

    if t_tile in WALL_TILES or t_tile in floor._no_pass_tiles or t_tile == SPECIAL_DOOR:
        # 撞 noPass/墙/特殊门：先看目标格有无【启用】事件并触发（互动不移入，英雄停原格）。
        # 隐藏怪假墙机制（MT41(10,2)）：人在(9,2)按 R 撞 330 假墙→events[10,2] 的 if 按
        # status:x===9&&status:y===2&&flag&&hasVisitedFloor 求值，成立则 setBlock 现身怪+置 flag。
        # 方向性由 if 条件自带（从(11,2)按 L 时 status:x===11≠9→false 分支空→不触发）。
        # _fire_events 自带门控：无事件/被 suppress/enable:false 直接返回 = 普通撞墙(原地)。
        # 通用：不分塔，事件存在与否、条件成立与否全由 data 的 events 决定，无硬编码。
        _fire_events(state, nx, ny)
        return

    if e_tile in floor._tile_to_enemy:
        _fight_monster(state, nx, ny)
        return

    if e_tile in floor._tile_to_item:
        _pickup_item(state, nx, ny)
        hero.x, hero.y = nx, ny
        _apply_zone_damage(state, nx, ny)
        _fire_events(state, nx, ny)
        return

    if e_tile in floor._tile_to_entity:
        ev = floor.events.get(f"{nx},{ny}")
        # 事件已禁用（enable: false）→ hero 直接通过（如 MT1 作者NPC）
        if isinstance(ev, dict) and ev.get("enable") is False:
            hero.x, hero.y = nx, ny
            _apply_zone_damage(state, nx, ny)
            return
        # 有激活事件（如商店/小偷列表事件）→ NPC 为 noPass，触发互动后 hero 不移入，需再按一次走入
        if ev is not None:
            _fire_events(state, nx, ny)
            return
        # trader 商人（trigger=trader）：独立于祭坛，首次买(choices)/二次对话消失，全程不移入
        if floor._tile_to_trigger.get(e_tile) == "trader":
            _handle_trader(state, nx, ny)
            return
        # oldman 老人（trigger=oldman）：撞→systemEvents.oldman→insert"对话"(args=[楼层号,x,y,0])
        # →按楼层 case 显示提示(MT2 给1000金币/MT3 给手册/MT18 等纯提示)→末尾 hide[x,y] remove
        # 老人消失；英雄不移入(撞 NPC)，需再按一次走入(与 trader/MT16 老人统一)
        if floor._tile_to_trigger.get(e_tile) == "oldman":
            _handle_oldman(state, nx, ny)
            return
        # 无楼层事件 → 查 NPC 的 common event（如祭坛），数据来自 tiles.json._commonEvent
        ce_name = floor._tile_to_common_event.get(e_tile)
        if ce_name:
            body = _get_common_events(state).get(ce_name)
            if body is not None:
                _execute_event_list(state, body, nx, ny)
            return
        # 完全无事件的 NPC（老人等）→ hero 停在原格
        return

    if t_tile in DOOR_KEY_MAP:
        key_id = DOOR_KEY_MAP[t_tile]
        if hero.keys.get(key_id, 0) > 0:
            hero.keys[key_id] -= 1
            floor.terrain[ny][nx] = 0
            # 英雄不移入门格，下一个同向 token 走入（h5mota 引擎行为）
        return

    if t_tile in AUTO_OPEN_TILES:
        # fakeWall/fakeWall2：撞上自动开门(墙→空地)，触发 afterOpenDoor；英雄不移入，
        # 下一同向 token 才走入(届时若 afterOpenDoor setBlock 了道具则按拾取分支取)，与钥匙门一致
        floor.terrain[ny][nx] = 0
        aod_key = f"{nx},{ny}"
        aod = floor.after_open_door.get(aod_key)
        if aod:
            _execute_event_list(state, aod, nx, ny)
        return

    hero.x, hero.y = nx, ny
    _apply_zone_damage(state, nx, ny)
    _fire_events(state, nx, ny)


# ─── Trader (商人) ─────────────────────────────────────────────────────────────

def _get_merchants(state: GameState) -> dict:
    """惰性加载 shops.json 商人目录 → {floorId@x@y: {price, give}}。"""
    if not state._merchants:
        path = state._floors_dir.parent / "shops.json"
        if path.exists():
            shops = json.loads(path.read_text(encoding="utf-8"))
            for entry in shops.get("merchants", {}).get("items", []):
                fl, pos = entry.get("floor"), entry.get("pos")
                if not fl or not pos:
                    continue
                px, py = pos.split(",")
                state._merchants[f"{fl}@{int(px)}@{int(py)}"] = {
                    "price": entry.get("price", 0),
                    "give": entry.get("give", {}),
                }
        state._merchants.setdefault("__loaded__", {})  # 空目录也不再反复读盘
    return state._merchants


def _handle_trader(state: GameState, x: int, y: int) -> None:
    """商人(trader 122)交互。来源 systemEvents.trader + commonEvent 商人/对话。
    首次：挂 choices 拦截[我太需要了/下次再说]，由下个 CHOICE token 决定买否；
    二次(flag 已置)：对话→商人消失(hide remove)。全程英雄不移入。"""
    floor = state.floor
    hero = state.hero
    flag_key = f"{floor.floor_id}@{x}@{y}@A"
    if hero.flags.get(flag_key, 0) == 1:
        floor.entities[y][x] = 0                       # 第2次交互 → 商人消失
        floor._suppressed_events.add(f"{x},{y}")
        return
    catalog = _get_merchants(state).get(f"{floor.floor_id}@{x}@{y}")
    if catalog is None:
        return  # 未在 shops.json 声明的商人 → 待建模，不静默买卖（铁律：绝不猜测）
    price = catalog["price"]
    buy_action: list = [
        {"type": "setValue", "name": "status:money", "value": str(price), "operator": "-="}
    ]
    for item_id, cnt in catalog["give"].items():
        buy_action.append({"type": "giveItem", "id": item_id, "count": cnt})
    buy_action.append({"type": "setValue", "name": f"flag:{flag_key}", "value": "1"})
    # 金币不足整体不买（对照 systemEvents: if money>=price …else 金币不够）
    guarded = [{"type": "if", "condition": f"status:money>={price}",
                "true": buy_action, "false": []}]
    floor._event_intercepting = True
    floor._event_pending_choices = [{"action": guarded}, {"action": []}]
    floor._event_pending_instrs = []
    floor._event_pending_xy = (x, y)


def _handle_oldman(state: GameState, x: int, y: int) -> None:
    """老人(oldman 121)交互。忠实 systemEvents.oldman：
    core.insertAction([{type:insert, name:'对话', args:[楼层号,x,y,0]}])。
    '对话' commonEvent 按 flag:arg1(楼层号) switch 显示提示(MT2 给1000金币/MT3 给手册/
    其余纯提示)，末尾 hide loc=[arg2,arg3] remove → 老人消失。英雄不移入(撞 NPC)，
    需下个同向 token 才走入。MT2/MT3 因 '有选择的对话'=true 会挂 choices 拦截(等 CHOICE
    token)；其余层为纯文字串(回放中自动翻页、不拦截、不消费额外 token)。"""
    floor_num = int(state.current_floor[2:])  # MT18→18，同引擎 floorId.substring(2)
    instr = {"type": "insert", "name": "对话", "args": [floor_num, x, y, 0]}
    _execute_instruction(state, instr, x, y, {})


# ─── Combat ──────────────────────────────────────────────────────────────────

def _build_monster(state: GameState, monster_id: str) -> Monster:
    """从 monsters.json + setEnemy 覆盖(_enemy_overrides)构建战斗用怪。
    普通战斗与剧情 boss 共用此逻辑，确保 setEnemy 改的 special(如先攻)对两者一致。见 mechanics §M.1/M.4。"""
    m = state.floor._monsters_db[monster_id]
    ov = state._enemy_overrides.get(monster_id, {})
    sp = ov.get("special", m.get("special", []))
    if isinstance(sp, int):
        sp = [sp] if sp else []
    return Monster(
        id=monster_id, name=m["name"],
        hp=ov.get("hp", m["hp"]), atk=ov.get("atk", m["atk"]), def_=ov.get("def", m["def"]),
        special=list(sp), n=m.get("n", 0), value=m.get("value", 0.0),
        add=m.get("add", False), atkValue=m.get("atkValue", 0.1),
        defValue=m.get("defValue", 0.9), damage=m.get("damage", 0),
    )


def _apply_post_combat_effects(hero: HeroState, result) -> None:
    if result.effects.poison:
        hero.flags["poison"] = True
    if result.effects.weak:
        hero.atk -= 20
        hero.def_ -= 20
    if result.effects.curse:
        hero.flags["curse"] = True
    if result.effects.explode:
        hero.hp = 1


def _fight_monster(state: GameState, mx: int, my: int) -> None:
    hero = state.hero
    floor = state.floor

    tile = floor.entities[my][mx]
    monster_id = floor._tile_to_enemy[tile]
    monster = _build_monster(state, monster_id)
    hero_ps = PlayerState(hp=hero.hp, atk=hero.atk, def_=hero.def_, mdef=hero.mdef)
    has_cross = hero.items.get("cross", 0) > 0
    result = compute_combat(hero_ps, monster, has_cross=has_cross)

    if result.damage is None:
        return

    # 引擎 canBattle 规则(core.enemys.canBattle: damage != null && damage < hp)：
    # 须 damage < hp 才可战斗；damage >= hp(战后 HP≤0)会死 → events.battle 拦截，
    # 不战斗、英雄原地不动(等同撞墙/noPass，这步无效，HP/坐标/钥匙/金币全不变)。
    # ⚠ 唯一例外：剧情 boss(MT32/MT40)用 battle 指令走 _forced_battle 强制路径，绕过本拦截。见 mechanics §M。
    if result.damage >= hero.hp:
        return

    hero.hp -= result.damage
    hero.gold += _enemy_gold(hero, floor._monsters_db[monster_id].get("gold", 0))  # 幸运金币×2
    hero.kill_count += 1
    floor.entities[my][mx] = 0
    hero.x, hero.y = mx, my

    _apply_post_combat_effects(hero, result)
    _apply_zone_damage(state, mx, my)
    if state.dead:
        return   # 战后落格区域伤致死 → 冻结，不触发 afterBattle（§M.8）

    loc_key = f"{mx},{my}"
    if loc_key in floor.after_battle and loc_key not in floor._done_after_battle:
        floor._done_after_battle.add(loc_key)
        _execute_event_list(state, floor.after_battle[loc_key], mx, my)

    _fire_events(state, mx, my)


def _forced_battle(state: GameState, enemy_id: str) -> None:
    """剧情 boss 强制战斗(battle 指令, force=true)：跳过 canBattle 拦截，无条件扣血(可致死)。
    不操作网格——boss 的生成/移除由演出的 setBlock/hide 自理。见 mechanics §M.1/M.4。"""
    floor = state.floor
    hero = state.hero
    if enemy_id not in floor._monsters_db:
        return
    monster = _build_monster(state, enemy_id)
    hero_ps = PlayerState(hp=hero.hp, atk=hero.atk, def_=hero.def_, mdef=hero.mdef)
    has_cross = hero.items.get("cross", 0) > 0
    result = compute_combat(hero_ps, monster, has_cross=has_cross)
    if result.damage is None:
        return  # 打不动(hero_per==0)：route 不会到此
    hero.hp -= result.damage          # force：不拦截，直接扣血（可致 hp<=0 = 死亡）
    hero.gold += _enemy_gold(hero, floor._monsters_db[enemy_id].get("gold", 0))  # 幸运金币×2
    hero.kill_count += 1
    _apply_post_combat_effects(hero, result)
    if hero.hp <= 0:
        state.dead = True             # 死在这一场 → 冻结于此，事件列剩余指令不再执行（§M.8）


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
    elif t == "add_item":
        # 拾取即向背包添加另一道具（引擎 core.addItem）。例：centerFly3 → +3 centerFly。
        item, count = effect["item"], effect.get("count", 1)
        if item in _KEY_ITEMS:
            hero.keys[item] = hero.keys.get(item, 0) + count
        else:
            hero.items[item] = hero.items.get(item, 0) + count


# ─── Event firing ────────────────────────────────────────────────────────────

def _fire_events(state: GameState, x: int, y: int) -> None:
    if state.dead:        # 区域伤/事件致死 → 冻结，不触发本格事件（§M.8）
        return
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
        ctx = {}
    floor = state.floor
    for i, instr in enumerate(event_list):
        if isinstance(instr, str):
            # 纯文字对话在回放中自动翻页、不消费 route token、不拦截事件流（引擎 replayActions
            # 无文字处理器，文字非 token 类型；仅 choices 读取选择 token）。故无条件跳过。
            continue
        if isinstance(instr, dict):
            t = instr.get("type", "")

            # choices 型事件：始终拦截（读取 CHOICE 选择 token）
            if t == "choices":
                floor._event_intercepting = True
                floor._event_pending_choices = list(instr.get("choices", []))
                floor._event_pending_instrs = list(event_list[i + 1:])
                floor._event_pending_xy = (event_x, event_y)
                return

            _execute_instruction(state, instr, event_x, event_y, ctx)

            # 死亡硬终止：本指令致 hp<=0（强制战斗/事件扣血）→ 冻结于死亡点，剩余指令不执行（§M.8）
            if state.dead:
                return

            # 指令执行后：传播拦截状态
            if floor._event_intercepting:
                outer_rest = list(event_list[i + 1:])
                if outer_rest:
                    floor._event_pending_instrs = floor._event_pending_instrs + outer_rest
                return

            # changeFloor 指令触发后：停止执行本层剩余事件
            if state.pending_floor_change is not None:
                return


def _get_common_events(state: GameState) -> dict:
    if not state._common_events:
        path = state._floors_dir.parent / "common_events.json"
        if path.exists():
            state._common_events.update(json.loads(path.read_text(encoding="utf-8")))
    return state._common_events


def _run_while_body(
    state: GameState, cond: str, body: list,
    event_x: int, event_y: int, ctx: dict,
) -> None:
    """Execute one while-loop iteration; if choices intercept, prepend _while_continue sentinel."""
    floor = state.floor
    if not _eval_condition(cond, state):
        return
    _execute_event_list(state, body, event_x, event_y, ctx)
    if floor._event_break:
        floor._event_break = False
        return
    if floor._event_intercepting:
        sentinel = {"type": "_while_continue", "_condition": cond, "_body": body}
        floor._event_pending_instrs = [sentinel] + floor._event_pending_instrs


def _norm_loc_pairs(loc_param, state: GameState) -> list:
    """规整 hide/show 的 loc，兼容两种 h5mota 写法：
      嵌套 [[x,y],[x,y],...]（多点，现有数据用）/ 扁平 [x,y]（单点，公共事件'对话'用）。
    每个坐标分量可为整数，或 flag:/status: 表达式字符串（如 '对话'的 ['flag:arg2 ','flag:arg3 ']），
    后者用 _eval_value_expr 求值。"""
    if not loc_param:
        return []
    pairs = loc_param if isinstance(loc_param[0], (list, tuple)) else [loc_param]
    out = []
    for p in pairs:
        x = p[0] if isinstance(p[0], int) else _eval_value_expr(str(p[0]), state)
        y = p[1] if isinstance(p[1], int) else _eval_value_expr(str(p[1]), state)
        out.append((int(x), int(y)))
    return out


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
        target_fid = instr.get("floorId")
        if target_fid and target_fid != state.current_floor:
            # 跨层 show：在目标层把隐藏事件(enable:false)显形（如 MT29(6,2) 小偷跨层显形 MT2(10,11)）。
            # 仿 hide 分支；用 _load_floor_if_needed 保证目标层已加载，显形才能持久。
            if _load_floor_if_needed(state, target_fid):
                tf = state.floors[target_fid]
                for lx, ly in _norm_loc_pairs(instr.get("loc"), state):
                    ev = tf.events.get(f"{lx},{ly}")
                    if isinstance(ev, dict):
                        ev["enable"] = True
            return
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
                for lx, ly in _norm_loc_pairs(instr.get("loc"), state):
                    if instr.get("remove"):
                        tf._suppressed_events.add(f"{lx},{ly}")
                        # 占位格（tile17 等大型怪 footprint）在 terrain 层，remove 时一并清除
                        if tf.entities[ly][lx] == 0:
                            tf.terrain[ly][lx] = 0
                    tf.entities[ly][lx] = 0
            return
        loc_param = instr.get("loc")
        if loc_param is not None:
            for lx, ly in _norm_loc_pairs(loc_param, state):
                if instr.get("remove"):
                    floor._suppressed_events.add(f"{lx},{ly}")
                    # 占位格（tile17 等大型怪 footprint）在 terrain 层，remove 时一并清除
                    if floor.entities[ly][lx] == 0:
                        floor.terrain[ly][lx] = 0
                floor.entities[ly][lx] = 0   # 清除实体（NPC/怪/道具）
        else:
            if instr.get("remove"):
                floor._suppressed_events.add(f"{event_x},{event_y}")
            floor.entities[event_y][event_x] = 0  # 无 loc 时清除事件触发格实体
        return

    # ── setBlock ──────────────────────────────────────────────────────────────
    if t == "setBlock":
        # 跨层 setBlock：floorId 指他层时改目标层（仿 show，必要时加载）。
        # 机制一：MT2(10,11) 小偷把 MT35(4,9) 由墙改为地面，开通左路暗道。见 mechanics §M.5
        target_fid = instr.get("floorId")
        if target_fid and target_fid != state.current_floor:
            if not _load_floor_if_needed(state, target_fid):
                return
            tf = state.floors[target_fid]
        else:
            tf = floor
        num_raw = instr.get("number", 0)
        try:
            num = int(num_raw)
        except (ValueError, TypeError):
            # 字符串 tile id → 反查编号（全量映射，含门/墙/地形，如 specialDoor/yellowWall）。见 mechanics §M.5
            num = tf._id_to_tile_full.get(str(num_raw), 0)
        locs = instr.get("loc")
        if not locs:
            locs = [[event_x, event_y]]   # 无 loc：默认事件自身格（如 MT41(10,2) destruct 现身怪）
        for loc in locs:
            lx, ly = loc[0], loc[1]
            if num == 0:
                tf.entities[ly][lx] = 0
                tf.terrain[ly][lx] = 0
            elif num in tf._tile_to_entity:
                tf.entities[ly][lx] = num
                tf.terrain[ly][lx] = 0   # 实体覆盖：清底层地形（假墙330→0），与引擎"一格一块"一致，怪才能被战斗走入
            else:
                tf.terrain[ly][lx] = num
                tf.entities[ly][lx] = 0
        return

    # ── setEnemy（临时改怪，如剧情 boss 赋予先攻）──────────────────────────────
    if t == "setEnemy":
        eid = instr.get("id")
        name = instr.get("name", "")
        value = instr.get("value")
        if eid:
            ov = state._enemy_overrides.setdefault(eid, {})
            if name == "special":
                iv = int(value) if value not in (None, "") else 0
                ov["special"] = [iv] if iv else []   # value 0 → 清空特技（解除先攻）
            else:
                try:
                    ov[name] = int(value)
                except (ValueError, TypeError):
                    ov[name] = value
        return

    # ── battle（剧情强制战斗，绕过 canBattle 拦截）─────────────────────────────
    if t == "battle":
        loc = instr.get("loc")
        if loc is not None:
            # 带 loc：源码 for 循环里 `if core.getBlockId(x,y)!==null` 的逐场存活判断
            # （怪先 move 到战斗点再 battle，sim 直接对源格存活怪结算）。见 mechanics §M.7。
            lx, ly = loc[0], loc[1]
            tile = state.floor.entities[ly][lx]
            if tile == 0:
                return  # getBlockId===null：该格怪已清 → 本场不触发、零伤
            eid = state.floor._tile_to_enemy.get(tile)
            if eid:
                _forced_battle(state, eid)
                state.floor.entities[ly][lx] = 0  # 战后清格（等效 move keep 把怪移走）
            return
        # 无 loc：无条件强制战斗（MT32），保持原语义不变
        eid = instr.get("id")
        if eid:
            _forced_battle(state, eid)
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
        did = instr.get("id", "")
        # id 走全量 id→tile 反查（如 yellowWall→1，afterBattle[10,2] 用它把蓝门口封成黄墙）；
        # 全量表无则回退门映射，再无则 85(specialDoor)。门类编号两表同源，旧行为不变。
        tile = floor._id_to_tile_full.get(did)
        if tile is None:
            tile = _DOOR_ID_TO_TILE.get(did, 85)
        floor.terrain[ly][lx] = tile
        return

    # ── setValue ──────────────────────────────────────────────────────────────
    if t == "setValue":
        _set_value(state, instr.get("name", ""), instr.get("value", ""),
                   instr.get("operator"))
        return

    # ── giveItem（通用给道具：路由 钥匙/hp/其它道具，供商人等使用）─────────────
    if t == "giveItem":
        item_id = instr.get("id", "")
        cnt = int(instr.get("count", 1))
        hero = state.hero
        if item_id in _KEY_ITEMS:
            hero.keys[item_id] = hero.keys.get(item_id, 0) + cnt
        elif item_id == "hp":
            hero.hp += cnt
        else:
            hero.items[item_id] = hero.items.get(item_id, 0) + cnt
        return

    # ── changeFloor ───────────────────────────────────────────────────────────
    if t == "changeFloor":
        target_id = _resolve_floor_id(state, instr.get("floorId", ""))
        loc = instr.get("loc")
        stair = instr.get("stair")
        if loc is not None:
            tx, ty = loc[0], loc[1]
        elif stair is not None:
            # 无 loc 有 stair：落点 = 目标层对应楼梯坐标（downFloor/upFloor 字段），
            # 与 fly 魔杖/_apply_stair_change 同一套解析（读目标层 down_floor/up_floor）。见 §I.3.2。
            if not _load_floor_if_needed(state, target_id):
                return  # 目标层未提取（范围外，如 MT42+）：切层失败，不默认 (0,0)
            tgt = state.floors[target_id]
            coords = tgt.down_floor if stair == "downFloor" else tgt.up_floor
            if not coords:
                raise ValueError(
                    f"changeFloor: 目标层 {target_id} 缺 {stair} 坐标，落点无法解析")
            tx, ty = coords[0], coords[1]
        else:
            # 既无 loc 又无 stair：落点无法确定，绝不静默默认 (0,0)（铁律：未知机制报错）。
            raise ValueError(
                f"changeFloor 缺 loc 且缺 stair（floorId={instr.get('floorId')!r}），落点无法确定")
        state.pending_floor_change = {"floor_id": target_id, "x": tx, "y": ty}
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

    # ── switch / caseList ─────────────────────────────────────────────────────
    if t == "switch":
        val = _eval_value_expr(instr.get("condition", ""), state)
        chosen = None
        default_action = None
        for c in instr.get("caseList", []):
            cv = c.get("case")
            if cv == "default":
                default_action = c.get("action", [])
            elif str(cv) == str(val):
                chosen = c.get("action", [])
                break
        action = chosen if chosen is not None else (default_action or [])
        _execute_event_list(state, action, event_x, event_y, ctx)
        # switch 内的 break(如 default 的 break n:1) 只为结束本 switch，不外泄
        if floor._event_break:
            floor._event_break = False
        return

    # ── insert ────────────────────────────────────────────────────────────────
    if t == "insert":
        name = instr.get("name", "")
        body = _get_common_events(state).get(name)
        if body is not None:
            args = instr.get("args")
            if args is not None:
                # h5mota: insert args → flag:arg1..argN(1-indexed)。用完保留(不恢复)：
                # 残留 argN 仅被公共事件读取，对其它逻辑无害；且 choices 拦截后续跑时
                # pending 指令(如 hide loc=[arg2,arg3])仍需读到这些 flag。
                for i, a in enumerate(args, start=1):
                    state.hero.flags[f"arg{i}"] = a
            _execute_event_list(state, body, event_x, event_y, ctx)
        return

    # ── while ─────────────────────────────────────────────────────────────────
    if t == "while":
        _run_while_body(state, instr.get("condition", "true"),
                        instr.get("data", []), event_x, event_y, ctx or {})
        return

    # ── _while_continue（内部哨兵，while 循环再入点）────────────────────────
    if t == "_while_continue":
        _run_while_body(state, instr.get("_condition", "true"),
                        instr.get("_body", []), event_x, event_y, ctx or {})
        return

    # ── break ─────────────────────────────────────────────────────────────────
    if t == "break":
        floor._event_break = True
        return


# ─── Condition evaluator ─────────────────────────────────────────────────────

def _search_block_count(state: GameState, block_id: str, floor_id: str) -> int:
    """core.searchBlock(id, floor).length：目标层上该 id 的方块数量（扫 terrain+entities）。
    目标层未提取/找不到 id 则记 0。见 mechanics §M.6。"""
    if not _load_floor_if_needed(state, floor_id):
        return 0
    tf = state.floors[floor_id]
    tile = tf._id_to_tile_full.get(block_id)
    if tile is None:
        return 0
    cnt = 0
    for row in tf.terrain:
        cnt += row.count(tile)
    for row in tf.entities:
        cnt += row.count(tile)
    return cnt


def _eval_condition(condition: str, state: GameState) -> bool:
    return all(_eval_single(p.strip(), state) for p in condition.split("&&"))


def _eval_single(part: str, state: GameState) -> bool:
    floor = state.floor
    hero = state.hero

    if part in ("true", ""):
        return True
    if part == "false":
        return False

    # flag:KEY op rhs（带运算符的 flag 比较）——须先于下面的裸布尔分支匹配，
    # 否则裸分支会把 "30 == 5" 整串当成 flag 名查找而恒为 False。
    # 未设的 flag 当 0（同引擎 core.getFlag(name, 0)），口径与 _eval_value_expr 一致。
    m = re.match(r"\(?flag:(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+?)\)?$", part)
    if m:
        key, op, rhs = m.group(1).strip(), m.group(2), m.group(3).strip()
        lhs_raw = hero.flags.get(key, 0)
        lhs = int(lhs_raw) if isinstance(lhs_raw, (int, float)) else 0
        rhs_val = _eval_value_expr(rhs, state)
        return {">=": lhs >= rhs_val, "<=": lhs <= rhs_val, ">": lhs > rhs_val,
                "<": lhs < rhs_val, "==": lhs == rhs_val, "!=": lhs != rhs_val}[op]

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

    # core.getBlock(x,y) ===/!== null：该格是否有 block（裸 getBlock，区别于 getBlockId）。
    # h5mota 口径（§I.6 调用链）：blockObjs 收录所有 tile≠0 的格（墙/门/楼梯/地形/装饰/
    # 怪/道具），tile==0→null。双层模型映射为 entity≠0 或 terrain≠0 即非 null。
    # 用于 MT39 autoEvent[8,4] 九宫格条件（开两门后 (4,4) 黄门变 centerFly）。
    m = re.match(r"core\.getBlock\((\d+),\s*(\d+)\)\s*(===|!==)\s*null", part)
    if m:
        bx, by, op = int(m.group(1)), int(m.group(2)), m.group(3)
        nonnull = floor.entities[by][bx] != 0 or floor.terrain[by][bx] != 0
        return (not nonnull) if op == "===" else nonnull

    # core.getBlockCls(x,y) ===/!== 'enemys'：判该格当前 entity 是否敌人类。
    # 数据驱动——敌人 tile 集合 = tiles.json enemys 段（_tile_to_enemy 键），不硬编码楼层。
    # 仅支持 'enemys'（全 50 层唯一出现的 cls）；其它 cls 落到末尾，需要时再扩展。
    m = re.match(r"core\.getBlockCls\((\d+),\s*(\d+)\)\s*(===|!==)\s*'(\w+)'", part)
    if m and m.group(4) == "enemys":
        bx, by, op = int(m.group(1)), int(m.group(2)), m.group(3)
        is_enemy = floor.entities[by][bx] in floor._tile_to_enemy
        return is_enemy if op == "===" else not is_enemy

    # status:xxx op rhs（商店 while 条件等）
    m = re.match(r'\(?status:(\w+)\s*(>=|<=|==|!=|>|<)\s*(.+?)\)?$', part)
    if m:
        stat, op, rhs = m.group(1), m.group(2), m.group(3).strip()
        stat_map = {"atk": hero.atk, "def": hero.def_, "hp": hero.hp, "money": hero.gold}
        lhs = stat_map.get(stat, 0)
        rhs_val = _eval_value_expr(rhs, state)
        if op == ">=": return lhs >= rhs_val
        if op == "<=": return lhs <= rhs_val
        if op == ">":  return lhs > rhs_val
        if op == "<":  return lhs < rhs_val
        if op == "==": return lhs == rhs_val
        if op == "!=": return lhs != rhs_val

    # core.canBattle('id')：剧情 boss if 分支用 = 能击杀且不致死(damage != null && damage < hp)。见 mechanics §M.4
    m = re.match(r"\(?core\.canBattle\('(\w+)'\)\)?", part)
    if m:
        eid = m.group(1)
        if eid not in floor._monsters_db:
            return False
        monster = _build_monster(state, eid)
        hero_ps = PlayerState(hp=hero.hp, atk=hero.atk, def_=hero.def_, mdef=hero.mdef)
        has_cross = hero.items.get("cross", 0) > 0
        result = compute_combat(hero_ps, monster, has_cross=has_cross)
        return result.damage is not None and result.damage < hero.hp

    # core.searchBlock('id','floor').length OP n：MT29 小偷暗道支线条件。见 mechanics §M.6
    m = re.match(r"\(?core\.searchBlock\('(\w+)',\s*'(\w+)'\)\.length\s*(>=|<=|==|!=|>|<)\s*(\d+)\)?", part)
    if m:
        bid, fid, op, num = m.group(1), m.group(2), m.group(3), int(m.group(4))
        cnt = _search_block_count(state, bid, fid)
        return {">=": cnt >= num, "<=": cnt <= num, "==": cnt == num,
                "!=": cnt != num, ">": cnt > num, "<": cnt < num}[op]

    # ── 嵌套括号 && 片段的兜底匹配 ──────────────────────────────────────────────
    # 形如 ((flag:41==1 )&&(( status:x===9 )&&(( status:y===2 )&& core.hasVisitedFloor('MT42'))))
    # 的条件按 && 切分后，片段会带不平衡分组括号和空格（如 "((flag:41==1 )"、" core.hasVisitedFloor('MT42'))))"），
    # 上面的锚定 re.match 分支匹配不到。用 re.search 在片段内定位谓词，容忍周围括号/空格。
    # === / !== 按 JS 严格等价，等同 == / !=。status:x/y = 英雄当前坐标（撞墙互动时尚未移动）。
    OPS = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b,
           "<": lambda a, b: a < b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b}

    m = re.search(r"flag:(\w+)\s*(===|!==|>=|<=|==|!=|>|<)\s*(-?\d+)\b", part)
    if m:
        op = m.group(2).replace("===", "==").replace("!==", "!=")
        lhs_raw = hero.flags.get(m.group(1), 0)
        lhs = int(lhs_raw) if isinstance(lhs_raw, (int, float)) else 0
        return OPS[op](lhs, int(m.group(3)))

    m = re.search(r"status:(\w+)\s*(===|!==|>=|<=|==|!=|>|<)\s*(-?\d+)\b", part)
    if m:
        op = m.group(2).replace("===", "==").replace("!==", "!=")
        stat_map = {"x": hero.x, "y": hero.y, "hp": hero.hp,
                    "atk": hero.atk, "def": hero.def_, "money": hero.gold}
        return OPS[op](stat_map.get(m.group(1), 0), int(m.group(3)))

    m = re.search(r"core\.hasVisitedFloor\('(\w+)'\)", part)
    if m:
        return m.group(1) in state.visited_floors

    return False


# ─── Value expression evaluator ──────────────────────────────────────────────

def _eval_value_expr(expr: str, state: GameState) -> int:
    """Evaluate a numeric expression containing flag:/status: references."""
    hero = state.hero

    def _replace(m: re.Match) -> str:
        kind, key = m.group(1), m.group(2)
        if kind == "flag":
            v = hero.flags.get(key, 0)
            return str(int(v) if isinstance(v, (int, float)) else 0)
        mapping = {"atk": hero.atk, "def": hero.def_, "hp": hero.hp,
                   "money": hero.gold, "mdef": hero.mdef}
        return str(mapping.get(key, 0))

    s = re.sub(r'(flag|status):(\w+)', _replace, str(expr))
    try:
        return int(eval(s, {"__builtins__": {}}))  # noqa: S307
    except Exception:
        return 0


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
        elif re.search(r'(flag|status):', value):
            val = _eval_value_expr(value, state)
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
    elif name.startswith("status:"):
        stat = name[7:]
        num = int(val) if isinstance(val, (int, float)) and val is not None else 0
        if stat == "money":
            if operator == "+=":   hero.gold += num
            elif operator == "-=": hero.gold -= num
            else:                  hero.gold = num
        elif stat == "hp":
            if operator == "+=":   hero.hp += num
            elif operator == "-=": hero.hp -= num
            else:                  hero.hp = num
        elif stat == "atk":
            if operator == "+=":   hero.atk += num
            elif operator == "-=": hero.atk -= num
            else:                  hero.atk = num
        elif stat == "def":
            if operator == "+=":   hero.def_ += num
            elif operator == "-=": hero.def_ -= num
            else:                  hero.def_ = num
        if hero.hp <= 0:
            state.dead = True   # 事件扣血致死 → 冻结于死亡点（§M.8）
    elif name.startswith("item:"):
        # 道具增减（setValue name=item:<id>）：钥匙类入 keys，其余入 items。
        # 来源：MT16 老人给圣水(item:superPotion+=1)、MT28 回收钥匙(item:yellowKey-=1) 等。
        # 旧实现缺此分支 → item: 静默 no-op（圣水/钥匙增减全丢失），本次补齐。
        item_id = name[5:]
        target = hero.keys if item_id in _KEY_ITEMS else hero.items
        delta = val if isinstance(val, int) else 1
        if operator == "+=":
            target[item_id] = target.get(item_id, 0) + delta
        elif operator == "-=":
            target[item_id] = target.get(item_id, 0) - delta
        else:
            target[item_id] = delta


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
