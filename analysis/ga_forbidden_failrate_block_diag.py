"""【一次性诊断·只读·不碰产品码】块为目标版·带禁区寻路 fail 率摸底 —— §S15 禁区实现前风险量化（块化后）。

接 analysis/ga_forbidden_failrate_diag.py（§S16 单物品版·块化后已不适用：meta 现为【块 id】非 cell、
传给 navigate_to 会解包失败）。块化（§S20·commit 25221af）后基因=块 id 序列、禁区=【后续未拿块的全部
cell】（非单物品 cell）。本脚本用块版口径重测 fail 率，给 §S15「判无效落地」方案提供真实数据
（五钥已归并成 3 钥块 → 预期 §S15 单物品版『长基因 100% 黄·五钥互碰绕路』大幅缓解）。

═══ 红线（同旧脚本）═══
只读：不改 navigate_to/quotient/decode/fitness/任何产品码。用【现状 navigate_to（不带禁区）】跑贪心路
+【重放真引擎 step】看踏过哪些 cell（不靠观察推断·CLAUDE.md 铁律）→ 三档判定：
  · 绿 green ：贪心路不碰任何后续块 cell → 禁区下原样合法 → 确定不 fail。
  · 黄 yellow：碰了后续块 cell 但结构上（后续块全 cell 当墙）goal 仍可达 → 也许能绕（待 B' 真搜确认）。
  · 红 red   ：碰了且结构上 goal 被后续块封死 → 禁区下必无路 → 铁定判无效。
→ 真实判无效率 ∈ [红率, 红率+黄率]。绿/红不跑带禁区 GBFS 即成立（便宜）、黄是上界内不确定区。

块化对旧脚本的三处改动：①goal=块 id → goal_to_cell 归一成代表 cell 喂 navigate_to；②forbidden=后续未拿
块的【全部 cell】（block_index['block_cells']）非单物品 cell；③进包判定=块版（块物品 marker cell 全空=
整块已吸·block_markers）。三档判定核心（_hop_field_avoiding/_trace_cells/leg_verdict）复用旧脚本坐实逻辑。
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
from ga_decode import goal_to_cell                              # noqa: E402
from ga_navigate import navigate_to                             # noqa: E402
from vzone import _passable, _NB4                               # noqa: E402


# ─── 结构封死判断（复刻 ga_navigate._hop_field_to_goal + forbidden 当墙·纯几何·不碰产品码）──────
def _hop_field_avoiding(zone, goal_cell, forbidden):
    """从 goal 反向 BFS 结构 hop 场，forbidden（cell 集）当墙·不扩展。返回 {cell: hop}。
    英雄当前格 ∈ 场 ⟺ 结构上（后续块当墙）英雄仍能到 goal。goal 自身不在 forbidden（基因无重复·
    forbidden=排 goal 后的目标块 cell）→ 正常作 BFS 源。区外/未知层格跳过（同 _hop_field_to_goal）。"""
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
    """重放 moves（真引擎 step），返回踏过的 cell 集 {(fid,x,y)}（不含起点）。
    navigate_to 的 moves 含 _absorb 进块吸道具走法 → 踏过某后续块 cell ⟺ 顺路碰/吸了该后续块。"""
    s = state
    cells = set()
    for m in moves:
        s = step(s, m)
        cells.add((s.current_floor, s.hero.x, s.hero.y))
    return cells


def _block_taken(state, bid, block_markers):
    """块是否已进包 = 该块物品 marker cell 全空（被吸）。无 marker（理论上 pool 块都有）→ 视未拿。"""
    markers = block_markers.get(bid)
    if not markers:
        return False
    return all(_taken(state, c) for c in markers)


def leg_verdict(state, goal_bid, forbidden, zone, step, cache):
    """一腿带禁区三档判定（块版）。goal_bid=目标块 id；forbidden=后续未拿块的全部 cell 集。
    返回 (verdict, final, moves, touched)。verdict∈{unreached(够不到·与禁区无关),green,yellow,red}。"""
    goal_cell = goal_to_cell(goal_bid)
    final, moves, reached = navigate_to(state, goal_cell, zone, step, cache=cache)
    if not reached:
        return "unreached", final, moves, set()      # 缺钥/打不过/真不可达 → 现状 decode 本就跳过
    cells = _trace_cells(state, moves, step)
    touched = cells & forbidden
    if not touched:
        return "green", final, moves, set()           # 贪心路不碰后续块 → 禁区下原样合法 → 确定不 fail
    hop = _hop_field_avoiding(zone, goal_cell, forbidden)
    here = (state.current_floor, state.hero.x, state.hero.y)
    if here in hop:
        return "yellow", final, moves, touched         # 碰了但结构有绕路 → fail 不确定（待 B' 验证）
    return "red", final, moves, touched                # 碰了且结构封死 → 铁定判无效


# ─── 标签（块 id → 剑/盾/钥/宝石块·诊断可读·塔知识仅在诊断侧）────────────────────────────────
def _labeler(meta):
    keys, gems = set(meta["keys"]), set(meta["gems"])

    def lab(b):
        if b == meta["sword"]:
            return f"剑块{b}"
        if b == meta["shield"]:
            return f"盾块{b}"
        if b in keys:
            return f"钥块{b}"
        if b in gems:
            return f"宝石块{b}"
        return f"?块{b}"
    return lab


_MARK = {"green": "✅绿", "yellow": "⚠黄", "red": "❌红", "unreached": "·够不到"}


# ─── 块A：剑盾谎报锚点 + +16826 生死线护栏验证（§S17 去钥不碰剑）─────────────────────────────
def block_a(H, lab, bcells):
    print("\n" + "=" * 80)
    print("块A 剑盾谎报锚点 + 生死线护栏：去盾禁剑块(谎报候选) / 去剑禁钥·去钥禁剑(应全绿·+16826守住)")
    print("=" * 80)
    start, zone, step, cache = H["start"], H["zone"], H["step"], H["decode_cache"]
    sword, shield, keys = H["meta"]["sword"], H["meta"]["shield"], H["meta"]["keys"]

    # [盾块,剑块] 去盾·禁【剑块全 cell】：复现 §S8『去盾顺路吸剑』在块层级
    forbidden = set(bcells[sword])
    t0 = time.time()
    v, final, moves, touched = leg_verdict(start, shield, forbidden, zone, step, cache)
    print(f"\n  [盾块,剑块] 去 {lab(shield)}（禁 {lab(sword)} 全 {len(forbidden)} cell）→ {_MARK[v]}  "
          f"tokens={len(moves)}  {time.time()-t0:.1f}s")
    print(f"    踏过禁区(顺路碰的剑块 cell) = {sorted(touched) or '无'}  终态 ATK={final.hero.atk}")
    if v == "red":
        print("    ❗去盾【唯一】经剑块 → 禁区下铁定判无效（[盾块,剑块] 淘汰·不调换）")
    elif v == "yellow":
        print("    ⚠去盾碰剑但几何有绕路 → 正是 §S15『先盾不碰剑的更优路』候选（B' 真搜定）")

    # 生死线护栏（§S17 去 MT4 钥不碰剑·反向去剑不碰钥）：去剑禁全部钥块 / 去每把钥块禁剑块 → 应全绿
    print("\n  ── 生死线护栏验证（[剑块,5钥块]/[5钥块,剑块] 各腿·异层应不互碰=全绿→+16826 守住）──")
    fk = set().union(*(bcells[k] for k in keys))
    v2, _f2, m2, t2 = leg_verdict(start, sword, fk, zone, step, cache)
    print(f"  去 {lab(sword)}（禁 {len(keys)} 钥块共 {len(fk)} cell）→ {_MARK[v2]}  "
          f"碰={sorted(t2) or '无'}  tokens={len(m2)}")
    tally = {"green": 0, "yellow": 0, "red": 0, "unreached": 0}
    tally[v2] += 1
    for kb in keys:
        vk, _fk, mk, tk = leg_verdict(start, kb, set(bcells[sword]), zone, step, cache)
        tally[vk] += 1
        print(f"  去 {lab(kb)}（禁 {lab(sword)}）→ {_MARK[vk]}  碰={sorted(tk) or '无'}  tokens={len(mk)}")
    ok = tally["red"] == 0
    print(f"\n  护栏小结: {tally}  → {'✅ 全绿/无红·剑钥不互碰·两序列都有效·+16826 守住' if ok else '❗有红·须复核护栏'}")
    return v, tally


# ─── 块C：随机块序列三档分布（逐条逐腿·按基因长度看 fail 率）──────────────────────────────────
def block_c(H, lab, bcells, n, seed):
    print("\n" + "=" * 80)
    print(f"块C 随机块序列三档分布（n={n} 随机基因·逐腿带禁区判定·按基因长度汇总）")
    print("=" * 80)
    start, zone, step, cache = H["start"], H["zone"], H["step"], H["decode_cache"]
    pool, bmark = H["pool"], H["block_markers"]
    rng = random.Random(seed)
    genes = [_random_individual(pool, rng) for _ in range(n)]

    by_len = {}
    leg_tally = {"green": 0, "yellow": 0, "red": 0, "unreached": 0}
    red_samples = []
    t0 = time.time()
    for gene in genes:
        state = start
        worst = "green"
        fail_leg = None
        for i, goal in enumerate(gene):
            if state.dead or state.won:
                break
            later = gene[i + 1:]
            forbidden = set()
            for b in later:
                if not _block_taken(state, b, bmark):
                    forbidden |= set(bcells[b])
            if not forbidden:                         # 最后目标/后续全已拿 → 无禁区 → 等同现状
                final, moves, reached = navigate_to(state, goal_to_cell(goal), zone, step, cache=cache)
                v, touched = ("green" if reached else "unreached"), set()
            else:
                v, final, moves, touched = leg_verdict(state, goal, forbidden, zone, step, cache)
            leg_tally[v] += 1
            if v == "unreached":
                continue                              # 够不到=现状也跳过、state 不变、与禁区正交
            state = final                             # 用现状 navigate_to 推进（诊断到首个红腿即可定整条）
            if v == "red":
                worst = "red"
                fail_leg = (i, goal, touched)
                break
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
        print("\n  红样本(铁定判无效·哪腿被后续块封死):")
        for gene, i, goal, touched in red_samples:
            print(f"    {[lab(g) for g in gene]}")
            print(f"        第{i}腿 去 {lab(goal)} 被封死·禁区里碰到 {sorted(touched)}")
    return by_len, leg_tally


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="只跑块A（最快·验证脚本+拿剑盾锚点）")
    ap.add_argument("--n", type=int, default=24, help="块C 随机基因数")
    ap.add_argument("--seed", type=int, default=20260614)
    ap.add_argument("--no-persistent", action="store_true", help="禁用持久化缓存（默认用·复用 GA 暖桶）")
    args = ap.parse_args()

    print("组装 GA 电池组（build_start 重放 + 标尺 route 回放 + 目标池涌现 + 块涌现层）…")
    t0 = time.time()
    H = build_harness(persistent=not args.no_persistent)
    lab = _labeler(H["meta"])
    bcells = H["block_index"]["block_cells"]
    print(f"  就绪 {time.time()-t0:.1f}s  pool({len(H['pool'])} 块) = {[lab(b) for b in H['pool']]}")
    dc = H["decode_cache"]
    if hasattr(dc, "version_tag"):
        print(f"  navigate_to 持久化桶={dc.version_tag}  起始 stats={dc.stats}")

    block_a(H, lab, bcells)
    if args.smoke:
        print("\n[smoke] 只跑块A，结束。去掉 --smoke 跑块C 随机种群。")
        return
    block_c(H, lab, bcells, args.n, args.seed)

    if hasattr(dc, "stats"):
        print(f"\n  navigate_to 缓存收尾 stats={dc.stats}")


if __name__ == "__main__":
    main()
