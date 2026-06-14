"""【navigate_to 持久化缓存单测】§S13 拆成本墙 —— PersistentNavCache 机制 + 指纹闭包 钉死。

不需要 build_harness（合成键 + 一个便宜真实 GameState）→ 全程秒级、不标 slow。钉死四组命门：
  · 指纹闭包快照：nav_code_files() 必含导航全链(ga_navigate/quotient/search/vzone/seg_*/sim/*)、必排
    beam(函数级 import)/fitness/ga_loop(未被导航 import) —— 防意外增减依赖让指纹漏纳/错纳。
  · dict-like 行为：内存往返 + 跨实例(=跨 run)磁盘往返 + contains/len，可直接当 navigate_to(cache=)。
  · disk_key 跨 run 稳定：剥离 id(zone)(内存地址不稳)、frozenset 构造序无关(消 PYTHONHASHSEED 依赖)。
  · 健壮性：损坏文件当 miss 不崩、原子写不留 .tmp、FORMAT_VERSION 变 → 换桶(物理隔离旧缓存)。
  · pickle 保真：真实 _nav_key 经磁盘往返后 _nav_key 逐字段不变(GA 终态正确性的底座)。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

import pytest                                      # noqa: E402

import nav_cache                                   # noqa: E402
from nav_cache import PersistentNavCache           # noqa: E402


# ── 合成 navigate_to 键：(id(zone), max_pops, goal_cell, _nav_key)；_nav_key 须全可哈希 ──
def _fake_key(zone_id=140_000_000_123, max_pops=8000, goal=("MT5", 10, 12)):
    navkey = (100, 5, 3,
              frozenset({("a", 1), ("b", 2)}),
              frozenset({7, 3, 9}),
              frozenset({("flag", frozenset({2, 1}))}))
    return (zone_id, max_pops, goal, navkey)


def _val():
    return ("FINAL_STATE_SENTINEL", ("up", "left", "left"), True)


# ═══ 指纹闭包快照 ════════════════════════════════════════════════════════════════════
EXPECTED_CLOSURE = {
    "extract/decode_route.py",
    "extract/ga_navigate.py",
    "extract/seg_identify_zone1.py",
    "extract/vzone.py",
    "seg_experiment.py",
    "sim/combat.py",
    "sim/simulator.py",
    "solver/quotient.py",
    "solver/search.py",
    "solver/verify.py",
}


def test_import_closure_snapshot():
    """导航代码指纹的输入文件集【精确快照】——意外新增/删除模块级 import → 此测红、强制人核对。"""
    got = {f.relative_to(nav_cache._ROOT).as_posix() for f in nav_cache.nav_code_files()}
    assert got == EXPECTED_CLOSURE, (
        f"闭包变了！多出={got - EXPECTED_CLOSURE}  少了={EXPECTED_CLOSURE - got}")


def test_closure_includes_both_hp_loss_layers():
    """两套扣血(地形伤+战斗)的实现文件必在闭包内 —— 改它们 → 指纹变 → 旧缓存作废。"""
    got = {f.relative_to(nav_cache._ROOT).as_posix() for f in nav_cache.nav_code_files()}
    assert "sim/simulator.py" in got      # 地形毒/领域/战斗扣血【应用】点
    assert "sim/combat.py" in got         # 战斗伤害值【计算】(getDamageInfo)
    assert "extract/ga_navigate.py" in got
    assert "solver/quotient.py" in got


def test_closure_excludes_nonnav():
    """函数级 import 的 beam、未被导航 import 的 fitness/ga_loop 不该进闭包(纳了=指纹过敏误失效)。"""
    got = {f.relative_to(nav_cache._ROOT).as_posix() for f in nav_cache.nav_code_files()}
    assert "solver/beam.py" not in got    # quotient 内函数级 import(避循环)→ 非依赖
    assert "extract/fitness.py" not in got
    assert "extract/ga_loop.py" not in got


def test_module_level_imports_skip_function_body(tmp_path):
    """_module_level_imports 只取模块级、跳过函数体内 import(beam 被排除的根因)。"""
    f = tmp_path / "probe.py"
    f.write_text(
        "import os\n"
        "from a.b import c\n"
        "def foo():\n"
        "    import should_be_skipped\n"
        "    from x.y import z\n"
        "if True:\n"
        "    import block_level_kept\n",
        encoding="utf-8")
    names = nav_cache._module_level_imports(f)
    assert "os" in names and "a.b" in names and "block_level_kept" in names
    assert "should_be_skipped" not in names and "x.y" not in names


# ═══ dict-like 行为 ══════════════════════════════════════════════════════════════════
def test_mem_roundtrip(tmp_path):
    c = PersistentNavCache(cache_root=tmp_path)
    k, v = _fake_key(), _val()
    assert c.get(k, "MISS") == "MISS"
    assert k not in c
    c[k] = v
    assert c.get(k) == v
    assert c[k] == v
    assert k in c
    assert len(c) == 1
    # 账目：set 前 get + contains(内部 get) = 2 miss；set=1 write；后续 get/getitem/contains = 3 mem_hit
    assert c.stats["miss"] == 2 and c.stats["write"] == 1 and c.stats["mem_hit"] == 3


def test_getitem_keyerror_on_miss(tmp_path):
    c = PersistentNavCache(cache_root=tmp_path)
    with pytest.raises(KeyError):
        _ = c[_fake_key()]


def test_disk_roundtrip_cross_instance(tmp_path):
    """set 在实例 A、清内存的实例 B 从磁盘读回 —— 模拟跨 run 命中(持久化的核心价值)。"""
    a = PersistentNavCache(cache_root=tmp_path)
    k, v = _fake_key(), _val()
    a[k] = v
    b = PersistentNavCache(cache_root=tmp_path)            # 全新实例 = 跨 run
    assert b.version_tag == a.version_tag                  # 同代码/数据 → 同桶
    assert b.get(k, "MISS") == v
    assert b.stats["disk_hit"] == 1


# ═══ disk_key 跨 run 稳定 ════════════════════════════════════════════════════════════
def test_disk_key_strips_zone_id(tmp_path):
    """id(zone)(内存地址·跨 run 不稳) 被剥离 → 仅 (max_pops,goal,_nav_key) 决定磁盘键。"""
    c = PersistentNavCache(cache_root=tmp_path)
    assert c._disk_key(_fake_key(zone_id=111)) == c._disk_key(_fake_key(zone_id=999_999))


def test_disk_key_frozenset_order_stable(tmp_path):
    """frozenset 不同构造序 → 同 canonical → 同磁盘键(消 PYTHONHASHSEED 依赖·跨 run 稳)。"""
    c = PersistentNavCache(cache_root=tmp_path)
    nk1 = (100, 5, 3, frozenset({("a", 1), ("b", 2)}), frozenset({7, 3, 9}),
           frozenset({("flag", frozenset({2, 1}))}))
    nk2 = (100, 5, 3, frozenset({("b", 2), ("a", 1)}), frozenset({9, 3, 7}),
           frozenset({("flag", frozenset({1, 2}))}))
    assert c._disk_key((7, 8000, ("MT5", 1, 1), nk1)) == \
           c._disk_key((7, 8000, ("MT5", 1, 1), nk2))


def test_disk_key_distinguishes_real_diffs(tmp_path):
    """不同 goal / 不同 _nav_key → 不同磁盘键(不能把不同导航请求误折叠成一条)。"""
    c = PersistentNavCache(cache_root=tmp_path)
    base = _fake_key()
    assert c._disk_key(base) != c._disk_key(_fake_key(goal=("MT9", 2, 2)))
    assert c._disk_key(base) != c._disk_key(_fake_key(max_pops=4000))


# ═══ 健壮性：损坏当 miss、原子写、版本桶 ═══════════════════════════════════════════════
def test_corrupt_file_treated_as_miss(tmp_path):
    """磁盘文件损坏/截断 → 当 miss(返 default)、计 corrupt、best-effort 删、绝不崩。"""
    c = PersistentNavCache(cache_root=tmp_path)
    k = _fake_key()
    p = c._path(k)
    p.write_bytes(b"GARBAGE_NOT_PICKLE")
    fresh = PersistentNavCache(cache_root=tmp_path)        # 清内存 → 强制走磁盘
    assert fresh.get(k, "MISS") == "MISS"
    assert fresh.stats["corrupt"] == 1
    assert not p.exists()                                  # 坏文件被清理


def test_atomic_write_leaves_no_tmp(tmp_path):
    """原子写(tmp+os.replace) 成功后桶内不留 .tmp 残片，只剩正式 .pkl。"""
    c = PersistentNavCache(cache_root=tmp_path)
    c[_fake_key()] = _val()
    leftovers = [p.name for p in c.bucket.iterdir() if ".tmp." in p.name]
    assert leftovers == [], f"残留 tmp: {leftovers}"
    assert sum(1 for p in c.bucket.iterdir() if p.suffix == ".pkl") == 1


def test_version_tag_deterministic_and_format_sensitive():
    """version_tag 对同输入确定；FORMAT_VERSION 变 → tag 变(换桶·旧缓存物理隔离作废)。"""
    assert nav_cache.compute_version_tag() == nav_cache.compute_version_tag()
    assert nav_cache.compute_version_tag(1) != nav_cache.compute_version_tag(2)


def test_version_bucket_isolation(tmp_path):
    """不同 format_version → 不同桶目录 → 互不可见(版本失效=走新桶、绝不读旧桶返错)。"""
    c1 = PersistentNavCache(cache_root=tmp_path, format_version=1)
    c2 = PersistentNavCache(cache_root=tmp_path, format_version=2)
    assert c1.bucket != c2.bucket
    k, v = _fake_key(), _val()
    c1[k] = v
    c2_fresh = PersistentNavCache(cache_root=tmp_path, format_version=2)
    assert c2_fresh.get(k, "MISS") == "MISS"               # v1 写的，v2 桶看不到


# ═══ pickle 保真：真实 _nav_key 经磁盘往返逐字段不变 ═══════════════════════════════════
def test_pickle_roundtrip_real_navkey(tmp_path):
    """便宜真实 GameState 的 (final, moves, reached) 经磁盘往返后，_nav_key 逐字段不变 + 英雄属性
    全等 —— pickle 不丢 GameState 字段，是「持久化 cache 开/关 GAResult 逐字段相同」的底座。"""
    from export_mt10_boss_route import make_initial_state
    from ga_navigate import _nav_key

    s = make_initial_state()
    key = (id(object()), 8000, ("MT1", s.hero.x, s.hero.y), _nav_key(s))
    value = (s, ("up", "down"), True)

    a = PersistentNavCache(cache_root=tmp_path)
    a[key] = value
    b = PersistentNavCache(cache_root=tmp_path)            # 跨实例 → 必走磁盘 unpickle
    final_r, moves_r, reached_r = b[key]

    assert reached_r is True
    assert moves_r == ("up", "down")
    assert _nav_key(final_r) == _nav_key(s)                # 逐字段身份不变
    h0, h1 = s.hero, final_r.hero
    assert (h1.hp, h1.atk, h1.def_, h1.mdef, h1.x, h1.y, h1.gold) == \
           (h0.hp, h0.atk, h0.def_, h0.mdef, h0.x, h0.y, h0.gold)
    assert b.stats["disk_hit"] == 1
