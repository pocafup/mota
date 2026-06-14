"""【§S13 持久化 navigate_to 缓存 · 验证门】拆成本墙正确性 + 收益 + 失效 三关。

跑真实 GA（同 seed/pool/pop/gen）三遍，证「持久化只改耗时、不改结果」+ 暖跑省深目标冷算 + 版本失效：
  关①【开/关结果逐字段相同】：off(内存 {}) vs cold(空桶·算+写盘) vs warm(满桶·读盘) → 三份 GAResult
        逐字段相同（gen_best_fitness/best_individual/best_fitness/n_unique_evals/gen_history）。改了=bug。
  关②【冷暖耗时对比】：cold 每个深目标冷算一次（盾≈26s）；warm 全从磁盘读回 → 应显著快。
  关③【版本失效正确】：真实改一处 sim/（尾部加注释·try/finally 铁 revert）→ version_tag 变 → 走新桶 →
        旧值不可见（会重算）→ 绝不读旧桶返错；revert 后版本回原桶、旧值仍命中。

用法：python analysis/ga_persist_cache_verify.py [--pop N] [--gen M]
  默认 pop6×gen3（关①③只需结果稳定多字段、关②只需深目标被命中两次——小规模即可证，非训练）。
  自建临时缓存桶（tempfile）→ 不污染真实 cache/、冷暖完全可控。
"""
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import nav_cache                                                  # noqa: E402
from nav_cache import PersistentNavCache                          # noqa: E402
from ga_loop import build_harness, make_decode_fitness_eval, run_ga  # noqa: E402

SEED = 20260613


def _fields(res):
    """GAResult 的逐字段可比快照（浮点定点化防表示噪声）。"""
    return dict(
        gen_best_fitness=[round(x, 6) for x in res.gen_best_fitness],
        best_individual=list(res.best_individual),
        best_fitness=round(res.best_fitness, 6),
        n_unique_evals=res.n_unique_evals,
        gen_history=res.gen_history,
    )


def _assert_identical(a, b, label):
    fa, fb = _fields(a), _fields(b)
    for k in fa:
        assert fa[k] == fb[k], f"❌ {label}: 字段 {k} 不一致\n   A={fa[k]}\n   B={fb[k]}"
    print(f"  ✅ {label}: GAResult 逐字段相同")


def gate_onoff_and_timing(pop, gen):
    print("=" * 78)
    print(f"关①②　开/关结果一致 + 冷暖耗时（pop{pop}×gen{gen}·seed={SEED}）")
    print("=" * 78)
    print("  组装电池组（build_harness·路线回放+目标池涌现）…")
    t0 = time.time()
    H = build_harness()                          # persistent=False；取构件 + off eval_fn(内存 {})
    print(f"    电池组就绪 {time.time() - t0:.1f}s   pool({len(H['pool'])})")
    start, zone, step = H["start"], H["zone"], H["step"]
    roster_fit, big, zone_fids, pool = H["roster_fit"], H["big"], H["zone_fids"], H["pool"]

    def fresh_eval(cache):
        return make_decode_fitness_eval(
            start, zone, step, roster_fit, big, zone_fids, decode_cache=cache)[0]

    tmp = Path(tempfile.mkdtemp(prefix="navcache_verify_"))
    try:
        # off：内存 {}（＝现状字节行为）
        t = time.time()
        res_off = run_ga(pool, H["eval_fn"], population=pop, generations=gen, seed=SEED)
        t_off = time.time() - t

        # cold：空桶 → 每个(中途态,目标)冷算一次 + 写盘
        cold = PersistentNavCache(cache_root=tmp)
        t = time.time()
        res_cold = run_ga(pool, fresh_eval(cold), population=pop, generations=gen, seed=SEED)
        t_cold = time.time() - t

        # warm：全新实例(空内存)指向同一满桶 → 全程磁盘读回、零冷算
        warm = PersistentNavCache(cache_root=tmp)
        t = time.time()
        res_warm = run_ga(pool, fresh_eval(warm), population=pop, generations=gen, seed=SEED)
        t_warm = time.time() - t

        print("\n  — 关①：开/关 GAResult 逐字段相同 —")
        _assert_identical(res_off, res_cold, "off(内存) vs cold(持久化冷)")
        _assert_identical(res_off, res_warm, "off(内存) vs warm(持久化暖)")
        print(f"     best_fitness={res_off.best_fitness:.1f}  n_unique_evals={res_off.n_unique_evals}")

        print("\n  — 关②：冷暖耗时 —")
        print(f"     off (内存{{}})        : {t_off:7.1f}s   {res_off.n_unique_evals} 评估")
        print(f"     cold(持久化·空桶算写): {t_cold:7.1f}s   桶={cold.version_tag}  {cold.stats}")
        print(f"     warm(持久化·满桶读回): {t_warm:7.1f}s   {warm.stats}")
        speedup = (t_cold / t_warm) if t_warm > 0 else float("inf")
        print(f"     ▸ 暖/冷加速 ≈ {speedup:.1f}×   "
              f"{'✅ 暖显著快(深目标省冷算)' if t_warm < t_cold else '⚠ 暖未更快(小规模冷算占比低?)'}")
        assert warm.stats["disk_hit"] > 0, "暖跑竟无磁盘命中（持久化没接上？）"
        assert warm.stats["miss"] == 0, f"暖跑仍有 miss={warm.stats['miss']}（桶没覆盖全部目标？）"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def gate_version_invalidation():
    print("\n" + "=" * 78)
    print("关③　版本失效：改一处 sim/ → 换桶 → 旧值不可见（真实改文件·try/finally 铁 revert）")
    print("=" * 78)
    simfile = ROOT / "sim" / "simulator.py"
    orig = simfile.read_bytes()
    tmp = Path(tempfile.mkdtemp(prefix="navcache_ver3_"))
    key = (id(object()), 8000, ("MT1", 7, 3), (1, 2, 3, "synthetic"))   # 合成键(不跑导航)
    val = ("OLD_BUCKET_VALUE", (), True)
    try:
        c_old = PersistentNavCache(cache_root=tmp)
        tag_old = c_old.version_tag
        c_old[key] = val
        assert c_old.get(key, "M") == val and c_old._path(key).exists()
        print(f"  旧桶就绪: version_tag={tag_old}  写入合成键")

        simfile.write_bytes(orig + b"\n# nav_cache invalidation probe (auto-reverted)\n")
        c_new = PersistentNavCache(cache_root=tmp)
        assert c_new.version_tag != tag_old, "★sim/ 改了但 version_tag 没变 → 失效失灵！"
        assert c_new.bucket != c_old.bucket, "★version_tag 变了但桶没换！"
        assert c_new.get(key, "MISS") == "MISS", "★新桶竟读到旧值 → 会返回过期结果！"
        print(f"  改 sim/simulator.py 后: version_tag={c_new.version_tag}（变了✅）")
        print(f"    → 走新桶 {c_new.bucket.name}（≠旧桶✅）→ 旧值不可见 MISS（会重算✅）")
    finally:
        simfile.write_bytes(orig)
        assert simfile.read_bytes() == orig, \
            "★★ revert 失败！请手动用 git 恢复 sim/simulator.py ★★"
        print("  sim/simulator.py 已 revert（字节核对一致✅）")

    c_back = PersistentNavCache(cache_root=tmp)
    assert c_back.version_tag == tag_old, "revert 后 version_tag 未回原值"
    assert c_back.get(key, "MISS") == val, "revert 后旧桶应仍命中"
    print(f"  revert 后: version_tag 回到 {c_back.version_tag} → 旧桶仍命中（版本=身份✅）")
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    pop = gen = None
    av = sys.argv
    if "--pop" in av:
        pop = int(av[av.index("--pop") + 1])
    if "--gen" in av:
        gen = int(av[av.index("--gen") + 1])
    pop = pop or 6
    gen = gen or 3
    gate_onoff_and_timing(pop, gen)
    gate_version_invalidation()
    print("\n" + "=" * 78)
    print("✅ 三关全过：持久化缓存 开/关结果一致 · 暖跑省冷算 · 版本失效正确")
    print("=" * 78)


if __name__ == "__main__":
    main()
