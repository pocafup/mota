"""
Deterministic single-combat engine.

Implements getDamageInfo + getEnemyInfo (坚固/模仿) from the h5mota engine.
Zone damage (specials 15/16/18/24) and terrain damage are NOT handled here;
those belong in the movement layer.

Post-combat effects (poison/weak/curse/explode) are returned as data fields —
the caller (simulator step function) is responsible for applying them to state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Monster:
    id: str
    name: str
    hp: int
    atk: int
    def_: int
    special: List[int] = field(default_factory=list)
    # special-specific parameters
    n: int = 0              # n-hit count (special 6); purify multiplier (special 9)
    value: float = 0.0      # vampire drain fraction (special 11)
    add: bool = False       # vampire also restores own HP (special 11)
    atkValue: float = 0.1   # counter multiplier (special 8); engine default = 0.1
    defValue: float = 0.9   # break-armor multiplier (special 7); engine default = 0.9
    damage: int = 0         # fixed extra damage added to total (special 22)


@dataclass
class PlayerState:
    hp: int
    atk: int
    def_: int
    mdef: int = 0


@dataclass
class PostCombatEffects:
    """
    State changes that apply after combat resolves.
    Caller must apply each flagged effect to the hero:
      poison  → set poison flag (hero loses values.poisonDamage=10 HP per step)
      weak    → ATK -= values.weakValue(20), DEF -= values.weakValue(20)
      curse   → set curse flag (gold/exp from future battles = 0)
      explode → set hero.hp = 1
    Source: core.events.eventdata.afterBattle (extracted from engine via toString())
    """
    poison: bool = False
    weak: bool = False
    curse: bool = False
    explode: bool = False


@dataclass
class CombatResult:
    """
    Result of compute_combat().
    damage=None: hero cannot kill the monster (hero_per_damage==0 or 无敌).
    turn=0 when damage is None.
    """
    damage: Optional[int]
    turn: int = 0
    effects: PostCombatEffects = field(default_factory=PostCombatEffects)


def _has(special: List[int], n: int) -> bool:
    return n in special


_CROSS_ENEMIES = {"zombie", "zombieKnight", "vampire"}


def compute_combat(
    hero: PlayerState,
    enemy: Monster,
    extra_turn: int = 0,
    hatred: int = 0,
    has_cross: bool = False,
) -> CombatResult:
    """
    Pure implementation of getEnemyInfo + getDamageInfo + post-combat effects.
    Does not mutate hero or enemy.

    Parameters
    ----------
    hero       : hero stats at the moment combat begins
    enemy      : base enemy stats (光环/支援 adjustments applied by caller if needed)
    extra_turn : value of flag __extraTurn__ (guard system; 0 in normal combat)
    hatred     : value of flag hatred (accumulated from prior kills; for special 17)
    has_cross  : hero holds cross item (doubles ATK vs zombie/zombieKnight/vampire)
    """
    sp = enemy.special

    # ── cross: double ATK against undead/vampire ─────────────────────────────
    # Source: getDamageInfo → hasItem("cross") && [...].indexOf(enemy.id) >= 0 → hero_atk *= 2
    hero_atk = hero.atk
    if has_cross and enemy.id in _CROSS_ENEMIES:
        hero_atk *= 2

    # ── getEnemyInfo: 模仿(10) and 坚固(3) ──────────────────────────────────
    mon_hp = enemy.hp
    mon_atk = enemy.atk
    mon_def = enemy.def_

    if _has(sp, 10):  # 模仿: copy hero ATK/DEF
        mon_atk = hero_atk
        mon_def = hero.def_

    if _has(sp, 3) and mon_def < hero_atk - 1:  # 坚固: floor hero_per at 1
        mon_def = hero_atk - 1

    # ── 无敌(20)：本游戏无怪物有此属性；cross 持有时应可突破，但实际无影响 ─────
    if _has(sp, 20) and not has_cross:
        return CombatResult(damage=None)

    # ── init_damage ──────────────────────────────────────────────────────────
    init_damage = 0

    if _has(sp, 11):  # 吸血: fraction of hero HP as upfront damage
        vamp = math.floor(hero.hp * enemy.value)
        init_damage += vamp
        if enemy.add:
            mon_hp += vamp

    # ── per_damage ───────────────────────────────────────────────────────────
    per_damage = mon_atk - hero.def_
    if _has(sp, 2):   # 魔攻: ignore hero defense
        per_damage = mon_atk
    per_damage = max(0, per_damage)

    if _has(sp, 4):   per_damage *= 2               # 2连击
    if _has(sp, 5):   per_damage *= 3               # 3连击
    if _has(sp, 6):   per_damage *= (enemy.n or 4)  # n连击 (default n=4)

    # ── counter_damage (per turn, triggered by hero's attack) ────────────────
    counter_damage = 0
    if _has(sp, 8):
        counter_damage = math.floor((enemy.atkValue or 0.1) * hero_atk)

    # ── init_damage adjustments ──────────────────────────────────────────────
    if _has(sp, 1):  # 先攻: monster attacks once before hero's first strike
        init_damage += per_damage
    if _has(sp, 7):  # 破甲: fraction of hero DEF as extra init damage
        init_damage += math.floor((enemy.defValue or 0.9) * hero.def_)
    if _has(sp, 9):  # 净化: multiple of hero mdef as extra init damage
        init_damage += math.floor((enemy.n or 3) * hero.mdef)

    # ── killability check ────────────────────────────────────────────────────
    hero_per_damage = max(0, hero_atk - mon_def)
    if hero_per_damage == 0:
        return CombatResult(damage=None)

    # ── turn count ───────────────────────────────────────────────────────────
    turn = math.ceil(mon_hp / hero_per_damage) + extra_turn

    # ── total damage ─────────────────────────────────────────────────────────
    # monster attacks (turn-1) times; counter triggers turn times
    damage = init_damage + (turn - 1) * per_damage + turn * counter_damage
    damage -= hero.mdef         # mdef applied once as flat reduction
    damage = max(0, damage)     # enableNegativeDamage = false

    if _has(sp, 17):  damage += hatred          # 仇恨
    if _has(sp, 22):  damage += enemy.damage    # 固伤

    # ── post-combat effects (applied by caller, not here) ────────────────────
    effects = PostCombatEffects(
        poison=_has(sp, 12),
        weak=_has(sp, 13),
        curse=_has(sp, 14),
        explode=_has(sp, 19),
    )

    return CombatResult(damage=damage, turn=turn, effects=effects)
