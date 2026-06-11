"""MT2 (1,9) 小偷 hide 抑制修法的决定性 AB 验证（用 test_checkpoints 金标准口径）。

单跑【当前 sim/simulator.py】，打印越狱小偷段三个关键时刻的 (1,9) 实体 + 英雄落点：
  u#70 后：触发 (3,7)、小偷搬到 (1,9)；
  u#75 后：二次踩 (3,7)——【修法前】re-fire 清掉 (1,9) 小偷 / 【修法后】抑制、小偷仍在；
  u#82 后：英雄是否重收敛进 MT3。

用法（外层做真实产品码前后对照，不靠 monkeypatch，避免 _orig 捕获已修法版本的陷阱）：
  python extract/verify_thief19_fix_ab.py 修法后        # 当前工作区
  git stash push -- sim/simulator.py
  python extract/verify_thief19_fix_ab.py 修法前        # 还原 HEAD
  git stash pop
"""
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

label = sys.argv[1] if len(sys.argv) > 1 else "当前"

spec = importlib.util.spec_from_file_location("tc", ROOT / "tests" / "test_checkpoints.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)
from sim.simulator import step


def t19(s):
    return s.floors["MT2"].entities[9][1] if "MT2" in s.floors else None


def main():
    toks = tc._load_tokens()
    s = tc._build_initial_state()
    print(f"[{label}] MT2(1,9) 小偷越狱段 AB：")
    for i in range(len(toks)):
        s = step(s, toks[i])
        if i == 70:
            print(f"  u#70 后  (1,9)实体={t19(s)!s:<5} pos=({s.current_floor},{s.hero.x},{s.hero.y})  ← 触发(3,7)、小偷搬到(1,9)")
        elif i == 75:
            mk = "仍在·未被清" if t19(s) else "被清空"
            print(f"  u#75 后  (1,9)实体={t19(s)!s:<5} pos=({s.current_floor},{s.hero.x},{s.hero.y})  ← 二次踩(3,7)：{mk}")
        elif i == 82:
            mk = "已进 MT3 ✅" if s.current_floor == "MT3" else f"仍在 {s.current_floor}"
            print(f"  u#82 后  pos=({s.current_floor},{s.hero.x},{s.hero.y})  ← {mk}")
            break


if __name__ == "__main__":
    main()
