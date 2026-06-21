"""§S56 A/B 对比：旧锚点 max-(atk,hp) vs 新锚点 score 最优(字典序)。

验玩家担心的"屯血871"是不是旧导出锚点 key=(atk,hp) 显式追血造成的假象。
两条半截路线各重放 → 跟踪 hp 峰值 / 蓝门开几道(及位置) / 打怪数 / 终态。
新锚点 hp 峰值降很多 = 屯血是导出口径假象；不降 = 真评分病(末键 hp 线性)。

只读重放(sim.step)，复用 decode_route。★产品码零改动。
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from extract.decode_route import parse_rle_route, decompress          # noqa: E402
from analysis.extract_zone1_milestones import build_initial_state     # noqa: E402
from sim.simulator import step                                        # noqa: E402

DXDY = {"U": (0, -1), "D": (0, 1), "L": (-1, 0), "R": (1, 0)}
KEYS = ("yellowKey", "blueKey", "redKey")

A_FILE = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly.h5route"
B_FILE = ROOT / "dir2_redkey_pathloss_halfway_s53_smartphi_k800_fly_scoremax.h5route"
# 前缀 tokens[:455]=玩家手打前期(开局1000血掉到铁盾点166)·A/B 共享·屯血只量 beam 段(tok≥455)
BEAM_START = 455


def decode(path):
    outer = json.loads(decompress(path.read_text(encoding="utf-8").strip()))
    return parse_rle_route(decompress(outer["route"]))


def adj_cell(before, tok):
    dx, dy = DXDY.get(tok, (0, 0))
    return before.hero.x + dx, before.hero.y + dy


def analyze(path, label):
    if not path.exists():
        print(f"  ✗ {label}: 文件不存在 {path.name}（跑还没导出？）")
        return None
    tokens = decode(path)
    s = build_initial_state()
    hp_peak = -1            # 只量 beam 段(tok≥BEAM_START)·排除前缀开局1000血
    hp_peak_at = None
    shield_hp = None        # 铁盾点(beam 段起点)hp 参照
    blue_doors = []         # beam 段开的蓝门 (floor,ox,oy,tok_idx)
    yellow_doors = kills = 0
    for i, t in enumerate(tokens):
        b = s
        s = step(s, t)
        if i < BEAM_START:
            continue
        if shield_hp is None:
            shield_hp = b.hero.hp        # 进 beam 段前一刻的血(铁盾点)
        if s.hero.hp > hp_peak:
            hp_peak = s.hero.hp
            hp_peak_at = (s.current_floor, s.hero.x, s.hero.y, i)
        if s.hero.kill_count > b.hero.kill_count:
            kills += 1
        if s.hero.keys.get("blueKey", 0) < b.hero.keys.get("blueKey", 0):
            ox, oy = adj_cell(b, t)
            blue_doors.append((b.current_floor, ox, oy, i))
        if s.hero.keys.get("yellowKey", 0) < b.hero.keys.get("yellowKey", 0):
            yellow_doors += 1
    h = s.hero
    print(f"\n══ {label} ══  ({path.name})")
    print(f"  token 数={len(tokens)}（beam 段 tok≥{BEAM_START}）  铁盾点 HP={shield_hp}")
    print(f"  终态: {s.current_floor}({h.x},{h.y}) HP{h.hp} ATK{h.atk} DEF{h.def_} "
          f"钥{{Y{h.keys.get('yellowKey',0)},B{h.keys.get('blueKey',0)},R{h.keys.get('redKey',0)}}} kills{h.kill_count}")
    f, x, y, ti = hp_peak_at
    print(f"  ★beam 段屯血峰值 HP={hp_peak}  在 {f}({x},{y}) tok{ti}")
    print(f"  蓝门开={len(blue_doors)} 道：", end="")
    print("  ".join(f"{fl}({ox},{oy})@tok{ix}" for fl, ox, oy, ix in blue_doors) or "（无）")
    print(f"  黄门开={yellow_doors} 道   打怪={kills} 只")
    return dict(hp_peak=hp_peak, hp_peak_at=hp_peak_at, blue_doors=blue_doors,
                yellow_doors=yellow_doors, kills=kills, shield_hp=shield_hp,
                final=(s.current_floor, h.x, h.y, h.atk, h.def_, h.hp))


def main():
    print("=" * 84)
    print("§S56 A/B 对比：屯血是不是旧锚点 key=(atk,hp) 追血造成的导出口径假象")
    print("=" * 84)
    a = analyze(A_FILE, "[A] 旧锚点 max-(atk,hp)")
    b = analyze(B_FILE, "[B] 新锚点 score 最优(字典序)")
    if a and b:
        print("\n" + "=" * 84)
        print("── 对比结论 ──")
        d_peak = a["hp_peak"] - b["hp_peak"]
        print(f"  屯血峰值: A={a['hp_peak']}  B={b['hp_peak']}  差={d_peak:+d}")
        print(f"  蓝门数:   A={len(a['blue_doors'])}  B={len(b['blue_doors'])}")
        print(f"  打怪数:   A={a['kills']}  B={b['kills']}")
        if d_peak >= 80:
            print("  → 新锚点屯血明显降 → 屯血871 主要是【导出口径假象】(玩家担心被夸大)")
        elif d_peak <= 20:
            print("  → 新锚点屯血几乎不降 → 是【真评分病】(末键 hp 线性)·须血饱和解")
        else:
            print("  → 部分降·两者皆有(导出口径 + 末键 hp 线性都有贡献)")
        print("=" * 84)


if __name__ == "__main__":
    main()
