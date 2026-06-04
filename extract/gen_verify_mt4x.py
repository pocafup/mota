"""扩层第四批 MT34-MT41 提取+逐格校验+连通报告。

复用 gen_verify_mt2x 的 gen_one/report/build_entities 逻辑，仅把数据源换成
extract/mt34_41_raw_combined.json（live engine Playwright dump，double-encoded）。

用法:
    python gen_verify_mt4x.py            # 默认 34 35 36 37 38 39 40 41
    python gen_verify_mt4x.py 34 35      # 只处理指定层
任一层 >0 不一致或出现未知 tile 即 STOP，不再处理后续层。
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_verify_mt2x as g

COMBINED = Path(__file__).parent / "mt34_41_raw_combined.json"


def load_combined():
    t = COMBINED.read_text(encoding="utf-8").strip()
    return json.loads(json.loads(t)) if t.startswith('"') else json.loads(t)


def main():
    args = sys.argv[1:] or ["34", "35", "36", "37", "38", "39", "40", "41"]
    all_raw = load_combined()
    for a in args:
        fid = f"MT{a}"
        if fid not in all_raw:
            print(f"⚠ {fid} 不在 dump 中，跳过"); continue
        raw = all_raw[fid]
        errs, unknown, entities, out_path = g.gen_one(fid, raw, all_raw)
        g.report(fid, raw, errs, unknown, entities, all_raw)
        print(f"  写入: {out_path}")
        if errs or unknown:
            print(f"\n🛑 {fid} 校验未过（{len(errs)}处不一致 / {len(unknown)}未知tile），STOP，不再处理后续层。")
            sys.exit(1)
    print(f"\n✅ 全部完成：{', '.join('MT'+a for a in args)} 均 0 处不一致、无未知 tile。")


if __name__ == "__main__":
    main()
