"""【只读对照】κ=0+stairs vs κ=1+stairs 两份 cut 文件直接比，回答"climber 受分坑保护时 κ 有没有增量价值"。

不重放、不改逻辑：只读两份 beam 截断落盘(每行含 floor/atk/def/hp/wave)，逐文件报：
  · 触达层集合 + 每层态数
  · 每层 maxHP / maxATK / maxDEF（cut 态口径——只含被截断的，非全前沿，但"出现即证明到达过"）
  · MT9 / MT10 顶尖 (hp,atk,def) 候选
关键判据：κ=1 是否把更高层 / 更高 DEF（盾）/ 更好 boss 层属性带出来。
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).parent
FILES = [
    ("κ=0+stairs", HERE / "crossbeam_cut_K50_vzone_lam0.0_stairs.jsonl"),
    ("κ=1+stairs", HERE / "crossbeam_cut_K50_vzone_k1_lam0.0_stairs.jsonl"),
]


def fk(s):
    try:
        return int(s[2:])
    except Exception:
        return -1


def load(fn):
    rows = []
    with open(fn, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def summarize(tag, rows):
    by_floor = defaultdict(list)            # floor -> [(hp,atk,def),...]
    for r in rows:
        by_floor[r["floor"]].append((r["hp"], r["atk"], r["def"]))
    floors = sorted(by_floor, key=fk)
    print("=" * 92)
    print(f"{tag}: 共 {len(rows)} 行 cut；触达层 {[f for f in floors]}")
    print(f"  层    态数   maxHP   maxATK   maxDEF   (该层最高DEF态 hp/atk/def)")
    for f in floors:
        v = by_floor[f]
        mhp = max(x[0] for x in v)
        matk = max(x[1] for x in v)
        mdef = max(x[2] for x in v)
        # 最高 DEF 的代表态
        bd = max(v, key=lambda x: (x[2], x[1], x[0]))
        print(f"  {f:>4} {len(v):>6}  {mhp:>6}  {matk:>6}  {mdef:>6}   ({bd[0]}/{bd[1]}/{bd[2]})")
    # MT9/MT10 顶尖：按 def 再按 atk 再按 hp
    for tgt in ("MT9", "MT10"):
        if tgt in by_floor:
            top = sorted(by_floor[tgt], key=lambda x: (-x[2], -x[1], -x[0]))[:5]
            print(f"  ── {tgt} 顶尖(def↓,atk↓,hp↓): " + ", ".join(f"{h}/{a}/{d}" for h, a, d in top))
        else:
            print(f"  ── {tgt}: ✗ cut 文件里没有该层任何态")
    return by_floor


def main():
    summ = {}
    for tag, fn in FILES:
        if not fn.exists():
            print(f"⚠ 缺文件: {fn}")
            continue
        summ[tag] = summarize(tag, load(fn))
    print("=" * 92)
    print("【对照结论速读】")
    f0 = summ.get("κ=0+stairs", {})
    f1 = summ.get("κ=1+stairs", {})
    def topfloor(bf):
        return max((fk(f) for f in bf), default=-1)
    def maxdef(bf):
        return max((d for v in bf.values() for _, _, d in v), default=-1)
    print(f"  最高触达层: κ=0 → MT{topfloor(f0)} | κ=1 → MT{topfloor(f1)}")
    print(f"  全局 maxDEF: κ=0 → {maxdef(f0)} | κ=1 → {maxdef(f1)}   (盾=+10DEF；base DEF=10)")
    print("  注：cut=被截断态，'出现即到达过'为硬证据；'未出现'为弱证据(可能在前沿未被截).")
    print("=" * 92)


if __name__ == "__main__":
    main()
