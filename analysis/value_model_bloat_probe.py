"""【§S34 A*化前置·只读探针 2】量"价值向量里 kill_count/gold 维是不是 MT9 指纹爆炸的伪元凶"。

探针 1 结论：MT9→seam 穷尽 486s 的瓶颈 = MT9 资源态组合爆炸（distinct_fp=21460@MT9），不是搜索
顺序 → 纯无损 best-first A* 砍不动。且出口前沿 32 点里大量【低 HP 点】（HP=2/28/30…）在 ATK/DEF/钥
都被高 HP 点支配的情况下仍非支配 → 只能靠【隐藏维】撑着：嫌疑 = kill_count（纯计数器·非可用资源·
极可能伪非支配制造机）与 gold（仅在有商店时可兑现·本段 allow_purchase=False 花不掉）。

本探针【不改产品码】，probe-local monkeypatch `solver.quotient.value_vector`（reassign 模块全局·原
_value_map 不动），把 kill / kill+gold 移出价值向量后重跑【同一小段】，对比已知基线：

  基线（探针 1 实测）：distinct_fp=21488  expanded=46848  486.3s  前沿=32点  H*(max-HP)=324

判读铁律——★看 H* 是否仍 = 324：
  • H* 不变(=324) 且 distinct_fp 大降 → 移除的是【伪维】、缩搜【无损】（没砍掉任何真 HP 选项）→
    把该维移出 Pareto 是比 A* 更治本的杠杆（待查商店兑现性定 gold 的 soundness）。
  • H* 变小 → 移除了【真选项】（该维确有终值）→ 不可移、得另寻提速（有界队列/全局 beam）。

⚠ soundness 归 soundness、机械缩搜归机械缩搜：本探针只量【机械缩搜规模 + H* 动没动】；某维到底有没
有终值（gold 能不能在二区花、kill 有没有事件读）是【数据/机制】问题，须查源码定、不在此断言。

只读·复用 seam_astar_smoke 已验证 harness。用法：python -u analysis/value_model_bloat_probe.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import solver.quotient as Q                                              # noqa: E402
from solver.search import _value_map                                    # noqa: E402
from analysis.seam_astar_smoke import first_enter_mt9, SEAM, seg_step   # noqa: E402

BASE = dict(distinct_fp=21488, expanded=46848, secs=486.3, fr=32, hstar=324)


def make_reduced(drop_exact=(), drop_prefix=()):
    de = set(drop_exact)
    dp = tuple(drop_prefix)
    def reduced(state):
        m = _value_map(state)
        return {k: v for k, v in m.items()
                if k not in de and not any(k.startswith(p) for p in dp)}
    return reduced


def run_variant(mt9, drop_exact, drop_prefix, label):
    drop = set(drop_exact) | set(drop_prefix)
    Q.value_vector = make_reduced(drop_exact, drop_prefix) if drop else _value_map
    t0 = time.time()
    res = Q.search_quotient(mt9, SEAM, seg_step, max_states=600_000,
                            cross_floor=True, beam_k=None, distinguish_doors=True)
    secs = time.time() - t0
    fr = res.goal_frontier if res.found else []
    hstar = max((v.get("hp", 0) for v in fr), default=0)
    print(f"\n【{label}】drop={sorted(drop) if drop else '—(基线复跑)'}")
    print(f"  found={res.found} {secs:.1f}s  distinct_fp={res.distinct_fingerprints} "
          f"expanded={res.states_expanded} generated={res.states_generated} goal_hits={res.goal_hits}")
    print(f"  前沿点数={len(fr)}  H*(max-HP)={hstar}")
    # 缩搜倍率 + H* 判读
    if res.found:
        shrink = BASE["distinct_fp"] / max(1, res.distinct_fingerprints)
        spd = BASE["secs"] / max(0.1, secs)
        verdict = ("✅H*不变=无损缩搜" if hstar == BASE["hstar"]
                   else f"⚠H*变了({BASE['hstar']}→{hstar})=移除了真选项·不可移")
        print(f"  vs 基线：distinct_fp {BASE['distinct_fp']}→{res.distinct_fingerprints} "
              f"(×{shrink:.1f} 缩)  时间 {BASE['secs']:.0f}s→{secs:.1f}s (×{spd:.1f})  {verdict}")
        # 全前沿向量（看哪些点塌掉·验 soundness）
        print("  前沿全维（HP 降序）：")
        for v in sorted(fr, key=lambda d: -d.get("hp", 0)):
            extra = {k: v[k] for k in v if k not in ("hp", "atk", "def")}
            print(f"     HP={v.get('hp'):>4} ATK={v.get('atk'):>3} DEF={v.get('def'):>3}  {extra}")
    Q.value_vector = _value_map   # 复原·别污染后续
    return res, secs, hstar


def main():
    print("=" * 84)
    print("§S34 A*化前置只读探针2：kill_count/gold 是不是 MT9 指纹爆炸伪元凶（monkeypatch·只读）")
    print("=" * 84)
    print(f"已知基线（探针1）：distinct_fp={BASE['distinct_fp']} expanded={BASE['expanded']} "
          f"{BASE['secs']}s 前沿={BASE['fr']}点 H*={BASE['hstar']}")

    mt9, idx = first_enter_mt9()
    if mt9 is None:
        print("🛑 没找到 MT9")
        sys.exit(1)
    h0 = mt9.hero
    print(f"起点 token[{idx}]：{mt9.current_floor}({h0.x},{h0.y}) "
          f"HP={h0.hp} ATK={h0.atk} DEF={h0.def_} gold={h0.gold} kill={h0.kill_count}")

    run_variant(mt9, {"kill"}, (), "变体A：移除 kill_count")
    run_variant(mt9, {"kill", "gold"}, (), "变体B：移除 kill_count + gold")
    run_variant(mt9, {"kill", "gold"}, ("item:",), "变体C：移除 kill+gold+items(留hp/atk/def/mdef/keys)")

    print("\n" + "=" * 84)
    print("【判读】H* 仍=324 且 distinct_fp 大降 → 该维是伪元凶、移出 Pareto=无损缩搜杠杆（比 A* 治本）；")
    print("        H* 变小 → 该维有真终值、不可移 → 提速改走有界队列/全局 beam。soundness 另查源码。")
    print("=" * 84)


if __name__ == "__main__":
    main()
