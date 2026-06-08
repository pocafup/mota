"""solver/frontier.py 单测：段间前沿合并的两层支配语义。

钉死：① 同残留指纹组内对持有资源做 Pareto（被支配/相等丢、不可比都留）；② 残留地图不同
（活怪/地上资源差异）→ 指纹不同 → 不可比、都留（哪怕 HP 更低也不被高 HP 点支配）；③ 持有资源
（hp/gold/keys/items）【不】进指纹 → 仅价值维比较。这是 C 段「跨段兑现时机」课的回归闸：
段间绝不能用标量把「留着活怪/资源」的点压掉。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sim.simulator import GameState, HeroState, load_floor, _copy_state
from solver.frontier import FrontierPoint, merge_frontier, residual_fingerprint

DATA = Path(__file__).parent.parent / "data/games51"
FLOORS = DATA / "floors"
FLOOR_IDS = json.loads((DATA / "floorIds.json").read_text(encoding="utf-8"))


def _base():
    f = load_floor(FLOORS / "MT1.json")
    hero = HeroState(x=6, y=11, hp=1000, atk=10, def_=10, mdef=0,
                     gold=0, keys={}, items={}, flags={})
    return GameState(hero=hero, floors={"MT1": f}, current_floor="MT1",
                     floor_ids=FLOOR_IDS, visited_floors={"MT1"},
                     pending_floor_change=None, _floors_dir=FLOORS)


def _variant(hp=None, gold=None, atk=None, keys=None, kill_entity=False):
    st = _copy_state(_base())
    if hp is not None:
        st.hero.hp = hp
    if gold is not None:
        st.hero.gold = gold
    if atk is not None:
        st.hero.atk = atk
    if keys is not None:
        st.hero.keys = dict(keys)
    if kill_entity:
        # 抹掉地图上第一个非空实体（代表「清掉一只怪 / 拾走一件地上资源」）→ 残留指纹变。
        ent = st.floors["MT1"].entities
        for y, row in enumerate(ent):
            for x, t in enumerate(row):
                if t:
                    ent[y][x] = 0
                    return st
        ent[0][0] = 999  # 兜底：MT1 无实体时人造一处差异
    return st


def test_same_fingerprint_dominated_dropped():
    """同残留指纹：HP 全面更低且其余相等 → 被支配，合并后只剩高 HP 点。"""
    hi = FrontierPoint(state=_variant(hp=1000), actions=("hi",))
    lo = FrontierPoint(state=_variant(hp=500), actions=("lo",))
    kept, stats = merge_frontier([hi, lo])
    assert stats["fingerprints"] == 1, "持有 HP 不入指纹 → 同组"
    assert stats["width"] == 1 and len(kept) == 1
    assert kept[0].state.hero.hp == 1000
    assert kept[0].actions == ("hi",)


def test_same_fingerprint_incomparable_both_kept():
    """同残留指纹但价值不可比（一个 HP 高、一个金币高）→ 都留。"""
    a = FrontierPoint(state=_variant(hp=1000, gold=0))
    b = FrontierPoint(state=_variant(hp=500, gold=100))
    kept, stats = merge_frontier([a, b])
    assert stats["fingerprints"] == 1
    assert stats["width"] == 2 and len(kept) == 2


def test_different_residual_incomparable_even_if_hp_lower():
    """残留地图不同（一只怪被清）→ 指纹不同 → 不可比：低 HP 的「已清怪」点也不被高 HP 点支配。"""
    alive_hi = FrontierPoint(state=_variant(hp=1000, kill_entity=False))
    dead_lo = FrontierPoint(state=_variant(hp=500, kill_entity=True))
    assert (residual_fingerprint(alive_hi.state)
            != residual_fingerprint(dead_lo.state)), "清怪应改变残留指纹"
    kept, stats = merge_frontier([alive_hi, dead_lo])
    assert stats["fingerprints"] == 2
    assert stats["width"] == 2, "跨指纹不可比，低 HP 残留点必须保留（跨段时机课）"


def test_identical_states_deduped():
    """完全相同的两点（同指纹同价值）→ 去重为 1。"""
    p1 = FrontierPoint(state=_variant(hp=700), actions=("a",))
    p2 = FrontierPoint(state=_variant(hp=700), actions=("b",))
    kept, stats = merge_frontier([p1, p2])
    assert stats["fingerprints"] == 1 and stats["width"] == 1


def test_held_keys_are_value_not_identity():
    """持有钥匙是价值维（不入指纹）：多钥匙 vs 多 HP 不可比 → 都留；指纹相同。"""
    more_keys = FrontierPoint(state=_variant(hp=500, keys={"yellowKey": 3}))
    more_hp = FrontierPoint(state=_variant(hp=1000, keys={"yellowKey": 0}))
    assert (residual_fingerprint(more_keys.state)
            == residual_fingerprint(more_hp.state)), "持有钥匙不应进残留指纹"
    kept, stats = merge_frontier([more_keys, more_hp])
    assert stats["fingerprints"] == 1 and stats["width"] == 2
