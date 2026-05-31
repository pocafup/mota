"""
Unit tests for sim/combat.py.

Oracle cases (test_oracle_*) reproduce the 8 engine-verified rows from
docs/mechanics_51.md §A.5.  All expected values were confirmed against the
live h5mota engine via core.getDamageInfo().

Hero configurations used:
  hero_weak   – ATK=15  DEF=10  HP=1000  mdef=0  (oracle cases 1–5)
  hero_strong – ATK=100 DEF=50  HP=10000 mdef=0  (oracle cases 6–8)
"""

import pytest
from sim.combat import Monster, PlayerState, PostCombatEffects, compute_combat


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def hero_weak():
    return PlayerState(hp=1000, atk=15, def_=10)


@pytest.fixture
def hero_strong():
    return PlayerState(hp=10000, atk=100, def_=50)


# ── Oracle cases (engine-verified, docs/mechanics_51.md §A.5) ───────────────

def test_oracle_greenSlime(hero_weak):
    # per=18-10=8; hero_per=15-1=14; turn=ceil(35/14)=3; damage=(3-1)*8=16
    m = Monster(id="greenSlime", name="绿色史莱姆", hp=35, atk=18, def_=1)
    r = compute_combat(hero_weak, m)
    assert r.damage == 16
    assert r.turn == 3


def test_oracle_bat(hero_weak):
    # per=38-10=28; hero_per=15-3=12; turn=3; damage=(3-1)*28=56
    m = Monster(id="bat", name="蝙蝠", hp=35, atk=38, def_=3)
    r = compute_combat(hero_weak, m)
    assert r.damage == 56
    assert r.turn == 3


def test_oracle_skeletonSoldier(hero_weak):
    # per=52-10=42; hero_per=15-12=3; turn=ceil(55/3)=19; damage=(19-1)*42=756
    m = Monster(id="skeletonSoldier", name="骷髅士兵", hp=55, atk=52, def_=12)
    r = compute_combat(hero_weak, m)
    assert r.damage == 756
    assert r.turn == 19


def test_oracle_skeleton(hero_weak):
    # per=42-10=32; hero_per=15-6=9; turn=ceil(50/9)=6; damage=(6-1)*32=160
    m = Monster(id="skeleton", name="骷髅", hp=50, atk=42, def_=6)
    r = compute_combat(hero_weak, m)
    assert r.damage == 160
    assert r.turn == 6


def test_oracle_vampire_not_killable(hero_weak):
    # hero_per=max(0,15-66)=0 → cannot kill
    m = Monster(id="vampire", name="吸血鬼", hp=444, atk=199, def_=66)
    r = compute_combat(hero_weak, m)
    assert r.damage is None


def test_oracle_evilBat_magic_solid(hero_strong):
    # special [2,3]: 魔攻→per=mon_atk=1; 坚固→mon_def=99→hero_per=1
    # turn=ceil(1000/1)=1000; damage=(1000-1)*1=999
    m = Monster(id="evilBat", name="邪恶蝙蝠", hp=1000, atk=1, def_=0,
                special=[2, 3])
    r = compute_combat(hero_strong, m)
    assert r.damage == 999
    assert r.turn == 1000


def test_oracle_redSwordsman_n_hit(hero_strong):
    # special 6 n=8: per=max(0,120-50)=70; ×8=560; turn=ceil(100/100)=1
    # damage=(1-1)×560=0
    m = Monster(id="redSwordsman", name="红色剑士", hp=100, atk=120, def_=0,
                special=[6], n=8)
    r = compute_combat(hero_strong, m)
    assert r.damage == 0
    assert r.turn == 1


def test_oracle_blueKnight_counter(hero_strong):
    # special 8: counter=floor(0.1×100)=10; per=120-50=70; turn=1
    # damage=(1-1)×70+1×10=10
    m = Monster(id="blueKnight", name="蓝色骑士", hp=100, atk=120, def_=0,
                special=[8])
    r = compute_combat(hero_strong, m)
    assert r.damage == 10
    assert r.turn == 1


# ── Post-combat effects ──────────────────────────────────────────────────────
# Source: core.events.eventdata.afterBattle (extracted from live engine)

def test_post_poison():
    # special 12: hero gets poisoned after battle (10 HP/step until cured)
    m = Monster(id="p_mob", name="毒怪", hp=10, atk=0, def_=0, special=[12])
    r = compute_combat(PlayerState(hp=1000, atk=50, def_=10), m)
    assert r.damage is not None, "monster should be killable"
    assert r.effects == PostCombatEffects(poison=True)


def test_post_weak():
    # special 13: hero ATK -= 20, DEF -= 20 after battle
    m = Monster(id="w_mob", name="衰弱怪", hp=10, atk=0, def_=0, special=[13])
    r = compute_combat(PlayerState(hp=1000, atk=50, def_=10), m)
    assert r.damage is not None
    assert r.effects == PostCombatEffects(weak=True)


def test_post_curse():
    # special 14: hero gets curse flag (gold/exp from future battles = 0)
    # triggerDebuff sets flag.curse=true; no immediate stat change
    m = Monster(id="c_mob", name="诅咒怪", hp=10, atk=0, def_=0, special=[14])
    r = compute_combat(PlayerState(hp=1000, atk=50, def_=10), m)
    assert r.damage is not None
    assert r.effects == PostCombatEffects(curse=True)


def test_post_explode():
    # special 19: hero.hp set to 1 after battle (caller's responsibility)
    m = Monster(id="e_mob", name="自爆怪", hp=10, atk=0, def_=0, special=[19])
    r = compute_combat(PlayerState(hp=1000, atk=50, def_=10), m)
    assert r.damage is not None
    assert r.effects == PostCombatEffects(explode=True)


# ── Additional edge-case for special 6 (n defaults to 4 when n=0) ───────────

def test_special6_n_default():
    # n=0 → engine uses 4; per=max(0,60-50)=10; ×4=40
    # hero_per=100-0=100; turn=ceil(300/100)=3; damage=(3-1)×40=80
    m = Monster(id="nhit", name="4连击怪", hp=300, atk=60, def_=0,
                special=[6], n=0)
    r = compute_combat(PlayerState(hp=10000, atk=100, def_=50), m)
    assert r.damage == 80
    assert r.turn == 3
