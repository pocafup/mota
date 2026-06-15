"""【一次性诊断·只读·不碰产品码】带禁区寻路 fail 率摸底 —— §S15 实现前的风险量化。

玩家拍板(2026-06-14)：实现禁区(B' 自写 _absorb_avoiding + 可区分差分给分)之前，先用便宜诊断摸清
"带禁区会判多少序列无效" = GA 还剩多少可搜空间。重点：MT4 五钥是否两两在路径上互碰致大批 fail、
短 vs 长基因 fail 率分布。

═══ 红线 ═══
本脚本【只读】，不改 navigate_to / quotient / decode / fitness / 任何产品码。用【现状 navigate_to
(不带禁区)】跑贪心路 + 【重放真引擎 step】看路线踏过哪些格(不靠观察推断·CLAUDE.md 铁律) → 三档判定：
  · 绿 green ：贪心路【不碰任何后续目标格】→ 禁区下贪心路原样合法 → 【确定不 fail】。
  · 黄 yellow：贪心路碰了后续目标格，但【结构上(后续目标当墙)goal 仍可达】→ 也许能绕路(打怪/开门
               待 B' 真带禁区搜索确认)→ fail 不确定。
  · 红 red   ：贪心路碰后续目标，且【结构上 goal 被后续目标格封死】→ 禁区下必无路 → 【铁定判无效】。

→ 真实判无效率 ∈ [红率, 红率+黄率]。绿/红是【确定结论·不需复刻 GBFS】，黄是上界内的不确定区
  (要 B' 实现后真带禁区搜索才能定，本诊断【不复刻 GBFS】、保持便宜——玩家要"便宜诊断")。

═══ 为什么三档够用、不必现在复刻带禁区 GBFS ═══
绿(不碰)即铁定不 fail、红(结构封死)即铁定 fail——二者不跑带禁区搜索就成立。只有黄区需 B' 实现后验证。
先用便宜三档圈定风险量级(尤其 MT4 五钥互碰、长短基因分布)，再决定 B' 实现。同玩家"动核心前先小步探"。

三档判定的【现状 navigate_to 复用】：禁区诊断里 navigate_to 是【不带禁区】跑(就是现在 GA 跑的样子)，
故缓存键与现有 GA 完全一致 → 复用之前 GA 暖的 PersistentNavCache 磁盘桶、深目标命中近免费。
"""
import argparse
import random
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from ga_loop import build_harness, _random_individual, _taken   # noqa: E402
from ga_navigate import navigate_to                              # noqa: E402
from vzone import _passable, _NB4                                # noqa: E402


# ─── 结构封死判断(复刻 ga_navigate._hop_field_to_goal + forbidden 当墙·纯几何·不碰产品码)──────
def _hop_field_avoiding(zone, goal_cell, forbidden):
    """从 goal 反向 BFS 结构 hop 场，但 forbidden 格【当墙·不扩展】。返回 {cell: hop}。
    goal 自身不在 forbidden(基因无重复·forbidden=排 goal 后的目标)→ 正常作 BFS 源。
    英雄当前格 ∈ 场 ⟺ 结构上(后续目标当墙)英雄仍能到 goal。区外/未知层格跳过(同 _hop_field_to_goal)。"""
    floors = zone["floors"]
    adj = {}
    for a, b in zone["links"].items():
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    dist = {goal_cell: 0}
    dq = deque([goal_cell])
    while dq:
        node = dq.popleft()
        d = dist[node]
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        nbrs.extend(adj.get(node, ()))
        for nb in nbrs:
            if (nb not in dist and nb not in forbidden
                    and nb[0] in floors and _passable(zone, nb)):
                dist[nb] = d + 1
                dq.append(nb)
    return dist


def _trace_cells(state, moves, step):
    """重放 moves(真引擎 step)，返回路线踏过的格集合 {(fid,x,y)}(不含起点)。
    navigate_to 的 moves 含 _absorb 进块吸道具的走法 → 踏过某 forbidden 道具格 ⟺ 顺路吸了该后续目标。"""
    s = state
    cells = set()
    for m in moves:
        s = step(s, m)
        cells.add((s.current_floor, s.hero.x, s.hero.y))
    return cells


def leg_verdict(state, goal, forbidden, zone, step, cache):
    """一腿带禁区三档判定。返回 (verdict, final, moves, touched)。
    verdict ∈ {unreached(够不到·与禁区无关), green, yellow, red}。forbidden=尚未拿的后续目标格集合。"""
    final, moves, reached = navigate_to(state, goal, zone, step, cache=cache)
    if not reached:
        return "unreached", final, moves, set()      # 缺钥/打不过/真不可达 → 现状 decode 本就跳过
    cells = _trace_cells(state, moves, step)
    touched = cells & forbidden
    if not touched:
        return "green", final, moves, set()          # 贪心路不碰后续目标 → 禁区下原样合法 → 确定不 fail
    hop = _hop_field_avoiding(zone, goal, forbidden)
    here = (state.current_floor, state.hero.x, state.hero.y)
    if here in hop:
        return "yellow", final, moves, touched       # 碰了但结构有绕路 → fail 不确定(待 B' 验证)
    return "red", final, moves, touched              # 碰了且结构封死 → 铁定判无效


# ─── 标签(cell → 剑/盾/钥/宝石·诊断可读·塔知识仅在诊断侧·不入引擎)──────────────────────────
def _labeler(meta):
    keys, gems = set(meta["keys"]), set(meta["gems"])

    def lab(c):
        if c == meta["sword"]:
            return f"剑{c}"
        if c == meta["shield"]:
            return f"盾{c}"
        if c in keys:
            return f"钥{c}"
        if c in gems:
            return f"宝石{c}"
        return f"?{c}"
    return lab


_MARK = {"green": "✅绿", "yellow": "⚠黄", "red": "❌红", "unreached": "·够不到"}


# ─── 块 A：剑盾谎报锚点([盾,剑] 去盾·禁剑·复现 §S8 dump 坐实的顺路吸剑)────────────────────────
def block_a(H, lab):
    print("\n" + "=" * 78)
    print("块A 剑盾谎报锚点：基因 [盾,剑] 去盾·剑排后→禁剑。复现 §S8『去盾顺路吸剑』")
    print("=" * 78)
    start, zone, step, cache = H["start"], H["zone"], H["step"], H["decode_cache"]
    sword, shield = H["meta"]["sword"], H["meta"]["shield"]
    forbidden = {sword}
    t0 = time.time()
    v, final, moves, touched = leg_verdict(start, shield, forbidden, zone, step, cache)
    dt = time.time() - t0
    print(f"  去 {lab(shield)}（禁 {lab(sword)}）→ {_MARK[v]}  tokens={len(moves)}  耗时{dt:.1f}s")
    print(f"    踏过禁区格(顺路吸的后续目标) = {sorted(lab(c) for c in touched) or '无'}")
    print(f"    终态 ATK={final.hero.atk}（基线开局 ATK 看是否因吸剑跳升=顺路吸剑物证）")
    if v == "red":
        print("    ❗结构封死：去盾【唯一】经剑格 → 禁区下铁定判无效（[盾,剑] 直接淘汰）")
    elif v == "yellow":
        print("    ⚠结构有绕路：去盾碰剑但几何上存在不经剑的路 → 正是 §S15『先盾不碰剑的更优路』候选")
    return v


# ─── 块 B：MT4 五钥互碰矩阵(去每把钥·禁其余四钥·看是否必经其他钥)──────────────────────────────
def block_b(H, lab):
    print("\n" + "=" * 78)
    print("块B MT4 五钥互碰：去每把钥·其余四钥全设禁区。看『去一把钥是否必经其他钥』=含多钥基因 fail 风险")
    print("=" * 78)
    start, zone, step, cache = H["start"], H["zone"], H["step"], H["decode_cache"]
    keys = H["meta"]["keys"]
    tally = {"green": 0, "yellow": 0, "red": 0, "unreached": 0}
    for A in keys:
        forbidden = set(keys) - {A}
        t0 = time.time()
        v, final, moves, touched = leg_verdict(start, A, forbidden, zone, step, cache)
        dt = time.time() - t0
        tally[v] += 1
        hit = sorted(lab(c) for c in touched)
        print(f"  去 {lab(A)}（禁其余四钥）→ {_MARK[v]}  碰={hit or '无'}  tokens={len(moves)}  {dt:.1f}s")
    print(f"\n  五钥小结: {tally}  ← 红/黄越多=去钥必经其他钥=含多钥基因大批判无效（GA 空间被啃）")
    return tally


# ─── 块 C：随机种群三档分布(逐条逐腿·按长度看 fail 率)───────────────────────────────────────
def block_c(H, lab, n, seed):
    print("\n" + "=" * 78)
    print(f"块C 随机种群三档分布（n={n} 随机基因·逐腿带禁区判定·按基因长度汇总）")
    print("=" * 78)
    start, zone, step, cache = H["start"], H["zone"], H["step"], H["decode_cache"]
    pool = H["pool"]
    rng = random.Random(seed)
    genes = [_random_individual(pool, rng) for _ in range(n)]

    # 按长度桶：每桶 [green, yellow, red] 整条基因计数（按最严腿分类）+ unreached 腿计数
    by_len = {}
    leg_tally = {"green": 0, "yellow": 0, "red": 0, "unreached": 0}
    red_samples = []
    t0 = time.time()
    for gi, gene in enumerate(genes):
        state = start
        worst = "green"
        fail_leg = None
        for i, goal in enumerate(gene):
            if state.dead or state.won:
                break
            later = gene[i + 1:]
            forbidden = {t for t in later if not _taken(state, t)}
            if not forbidden:                       # 最后一个目标(或后续全已拿)→ 无禁区→等同现状
                final, moves, reached = navigate_to(state, goal, zone, step, cache=cache)
                v, touched = ("green" if reached else "unreached"), set()
            else:
                v, final, moves, touched = leg_verdict(state, goal, forbidden, zone, step, cache)
            leg_tally[v] += 1
            if v == "unreached":
                continue                            # 够不到=现状也跳过、state 不变、与禁区正交
            state = final                           # 用现状 navigate_to 推进(诊断只到首个红腿即可定整条)
            if v == "red":
                worst = "red"
                fail_leg = (i, goal, touched)
                break                               # 整条已铁定判无效，后续无需再看
            if v == "yellow" and worst == "green":
                worst = "yellow"
                fail_leg = (i, goal, touched)
        L = len(gene)
        bucket = by_len.setdefault(L, {"green": 0, "yellow": 0, "red": 0})
        bucket[worst] += 1
        if worst == "red" and len(red_samples) < 8:
            i, goal, touched = fail_leg
            red_samples.append((gene, i, goal, touched))
    dt = time.time() - t0

    print(f"\n  腿级三档: {leg_tally}   （{n} 条基因·{dt:.1f}s）")
    print("\n  按基因长度的【整条】分类（按最严腿·red=至少一腿铁定判无效→整条淘汰）:")
    print(f"    {'len':>3} | {'绿':>4} {'黄':>4} {'红':>4} | {'红率':>6} {'红+黄率':>8}")
    tot = {"green": 0, "yellow": 0, "red": 0}
    for L in sorted(by_len):
        b = by_len[L]
        s = b["green"] + b["yellow"] + b["red"]
        for k in tot:
            tot[k] += b[k]
        rr = b["red"] / s if s else 0
        ry = (b["red"] + b["yellow"]) / s if s else 0
        print(f"    {L:>3} | {b['green']:>4} {b['yellow']:>4} {b['red']:>4} | {rr:>5.0%} {ry:>7.0%}")
    S = sum(tot.values())
    if S:
        print(f"    {'全':>3} | {tot['green']:>4} {tot['yellow']:>4} {tot['red']:>4} | "
              f"{tot['red']/S:>5.0%} {(tot['red']+tot['yellow'])/S:>7.0%}")
        print(f"\n  ★真实判无效率 ∈ [{tot['red']/S:.0%}(确定红), {(tot['red']+tot['yellow'])/S:.0%}(含黄上界)]"
              "  —— 黄区要 B' 实现后真带禁区搜索才能定")

    if red_samples:
        print("\n  红样本(铁定判无效·哪腿被后续目标封死):")
        for gene, i, goal, touched in red_samples:
            print(f"    {[lab(g) for g in gene]}")
            print(f"        第{i}腿 去 {lab(goal)} 被封死·禁区里碰到 {sorted(lab(c) for c in touched)}")
    return by_len, leg_tally


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="只跑块A(最快·验证脚本正确)")
    ap.add_argument("--no-block-b", action="store_true")
    ap.add_argument("--n", type=int, default=30, help="块C 随机基因数")
    ap.add_argument("--seed", type=int, default=20260614)
    ap.add_argument("--no-persistent", action="store_true",
                    help="禁用持久化缓存(默认用·复用 GA 暖桶让深目标命中近免费)")
    args = ap.parse_args()

    print("组装 GA 电池组(build_start 重放 + 标尺 route 回放 + 目标池涌现)…")
    t0 = time.time()
    H = build_harness(persistent=not args.no_persistent)
    print(f"  就绪 {time.time() - t0:.1f}s  pool({len(H['pool'])}) = {[ _labeler(H['meta'])(c) for c in H['pool'] ]}")
    dc = H["decode_cache"]
    if hasattr(dc, "version_tag"):
        print(f"  navigate_to 持久化桶={dc.version_tag}  起始 stats={dc.stats}")

    lab = _labeler(H["meta"])
    block_a(H, lab)
    if args.smoke:
        print("\n[smoke] 只跑块A，结束。去掉 --smoke 跑全量(块B 五钥矩阵 + 块C 随机种群)。")
        return
    if not args.no_block_b:
        block_b(H, lab)
    block_c(H, lab, args.n, args.seed)

    if hasattr(dc, "stats"):
        print(f"\n  navigate_to 缓存收尾 stats={dc.stats}")


if __name__ == "__main__":
    main()
