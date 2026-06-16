"""【§S33 口径核实·只读·便宜版】geom 探针：核实"seam(首次跨进MT10) 是不是 boss 入口"。

不重跑任何搜索。只重放真实通关存档，量三件事：
  ① 首次进 MT9 / 首次进 MT10(=seam) 各在第几 token；boss 段起点 tok1168 在第几次进 MT10。
  ② 英雄一共进 MT10 几次、MT9↔MT10 来回几趟（"seam 之后还回不回 MT9"决定地上血瓶是否可后取）。
  ③ redKey(开 boss 红门必需) 第一次到手在第几 token——若远在 seam 之后，则 seam 态(redKey=0)
     根本不是"马上能打 boss"的口径。

只读：build_initial_state/load_tokens/step，绝不改产品码。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.verify_all_checkpoints import build_initial_state, load_tokens  # noqa: E402
from sim.simulator import step                                                # noqa: E402

BOSS_ENTRY_TOK = 1168   # curriculum_scan_vboss 钉死：真实存档打 boss 那一刻


def main():
    s = build_initial_state()
    tokens = load_tokens()
    print(f"存档总 token 数 = {len(tokens)}")

    prev = s.current_floor
    first_mt9 = first_mt10 = None
    mt10_entries = []          # token idx 列表：每次 current_floor 变成 MT10
    mt9_entries = []
    transitions = []           # (idx, from, to) 仅记录涉及 MT9/MT10 的换层
    redkey_first = None
    redkey_at_seam = None

    for i, tok in enumerate(tokens):
        s = step(s, tok)
        # 红钥首次到手
        if redkey_first is None and s.hero.keys.get("redKey", 0) >= 1:
            redkey_first = i
        # 换层事件
        if s.current_floor != prev:
            if s.current_floor in ("MT9", "MT10") or prev in ("MT9", "MT10"):
                transitions.append((i, prev, s.current_floor))
            if s.current_floor == "MT9":
                mt9_entries.append(i)
                if first_mt9 is None:
                    first_mt9 = i
            if s.current_floor == "MT10":
                mt10_entries.append(i)
                if first_mt10 is None:
                    first_mt10 = i
                    redkey_at_seam = s.hero.keys.get("redKey", 0)
            prev = s.current_floor

    print(f"\n首次进 MT9   = token[{first_mt9}]")
    print(f"首次进 MT10(=seam) = token[{first_mt10}]   该刻 redKey={redkey_at_seam}")
    print(f"boss 段起点 tok{BOSS_ENTRY_TOK} = 第 {sum(1 for t in mt10_entries if t <= BOSS_ENTRY_TOK)} 次进 MT10")
    print(f"\nMT10 一共进入 {len(mt10_entries)} 次：{mt10_entries}")
    print(f"MT9  一共进入 {len(mt9_entries)} 次：{mt9_entries}")
    print(f"\nredKey 第一次到手 = token[{redkey_first}]"
          + (f"（在 seam token[{first_mt10}] 之后 {redkey_first - first_mt10} 步）" if redkey_first and first_mt10 else ""))

    # seam 之后还回不回 MT9？（决定 MT9 地上血瓶是否"可后取潜力"还是"永久错过"）
    after_seam_mt9 = [t for t in mt9_entries if t > first_mt10]
    print(f"\nseam 之后是否再回 MT9：{'是' if after_seam_mt9 else '否'}"
          + (f"，回 MT9 的 token={after_seam_mt9}" if after_seam_mt9 else ""))

    print("\n── MT9↔MT10 换层流水（首次跨进 MT10 ~ boss 段附近）──")
    for idx, fr, to in transitions:
        mark = "  ← boss段起点附近" if abs(idx - BOSS_ENTRY_TOK) <= 5 else ""
        seam_mark = "  ← seam(首跨MT10)" if idx == first_mt10 else ""
        print(f"  token[{idx:>4}] {fr} → {to}{seam_mark}{mark}")


if __name__ == "__main__":
    main()
