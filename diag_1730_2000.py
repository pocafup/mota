"""逐 token 打印 tok[1730]→tok[2000]，定位 tok[1730] 之后第一个与真值分叉的点。

背景（玩家中间真值已推翻"206偏差在fly前"的旧结论）：
  sim 到 tok[1730] = MT12(10,11) 581/68/54 3黄 与真值一致 → 分叉在 1730 之后。
  那次 ATK+4(68→72)/DEF+2(54→56)：1809=68/54、1902=68/54、2000=72/56
  → 加攻加防事件落在 tok[1902]→tok[2000] 段(MT20→...→MT16)，sim 没拿到。

口径：tok[N] = 处理完 tokens[0..N]（与 test_checkpoints.py 一致）。
report-only：不改任何代码/数据/真值。
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent / 'data/games51'
FLOORS = DATA / 'floors'

# 玩家金标准锚点: idx -> (floor, x, y, hp, atk, def, yk, bk)  None=该项不校验
ANCHORS = {
    1649: ('MT12',  6,  3, 345, 64, 54, 2, None),   # 1730前确认锚点
    1680: ('MT11',  1, 11, 605, 66, 54, 5, None),
    1699: ('MT11',  7,  1, 581, 66, 54, 3, None),
    1730: ('MT12', 10, 11, 581, 68, 54, 3, None),   # fly前，分叉分界
    1809: ('MT15',  7, 10, 179, 68, 54, 2, None),   # MT15恶战后
    1902: ('MT20',  6, 10, 591, 68, 54, 2, 1),      # ATK仍=68
    2000: ('MT16',  3,  1, 618, 72, 56, 0, 0),      # ATK已=72 → +4在1902..2000段
}


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
    )


def load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'), None)
    if route_path is None:
        route_path = next(Path(__file__).parent.glob('51_*.h5route'), None)
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def snap(s):
    h = s.hero
    return (s.current_floor, h.x, h.y, h.hp, h.atk, h.def_,
            h.keys.get('yellowKey', 0), h.keys.get('blueKey', 0), h.gold)


def check_anchor(idx, cur):
    ef, ex, ey, ehp, eatk, edef, eyk, ebk = ANCHORS[idx]
    d = []
    if cur[0] != ef:
        d.append(f"floor sim={cur[0]}≠真{ef}")
    if (cur[1], cur[2]) != (ex, ey):
        d.append(f"pos sim=({cur[1]},{cur[2]})≠真({ex},{ey})")
    if cur[3] != ehp:
        d.append(f"HP sim={cur[3]}≠真{ehp}({cur[3]-ehp:+d})")
    if cur[4] != eatk:
        d.append(f"ATK sim={cur[4]}≠真{eatk}({cur[4]-eatk:+d})")
    if cur[5] != edef:
        d.append(f"DEF sim={cur[5]}≠真{edef}({cur[5]-edef:+d})")
    if eyk is not None and cur[6] != eyk:
        d.append(f"yk sim={cur[6]}≠真{eyk}")
    if ebk is not None and cur[7] != ebk:
        d.append(f"bk sim={cur[7]}≠真{ebk}")
    return d


PRINT_LO, PRINT_HI = 1730, 2000
tokens = load_tokens()
state = build_initial_state()

prev = None
floor_seq = []      # (idx, floor) 楼层切换点
anchor_log = []     # (idx, diffs)
first_div = None

print(f"{'idx':>4} {'token':<12} {'floor':<5} {'pos':<9} {'HP':>5} {'ATK':>3} "
      f"{'DEF':>3} {'yk':>2} {'bk':>2} {'gold':>5}  note")

for idx in range(0, PRINT_HI + 1):
    state = step(state, tokens[idx])
    cur = snap(state)

    if prev is None or cur[0] != prev[0]:
        floor_seq.append((idx, cur[0]))

    if idx in ANCHORS:
        diffs = check_anchor(idx, cur)
        anchor_log.append((idx, diffs))
        if diffs and first_div is None:
            first_div = (idx, diffs)

    if PRINT_LO <= idx <= PRINT_HI:
        notes = []
        if prev is not None:
            if cur[0] != prev[0]:
                notes.append(f"<<FLOOR {prev[0]}->{cur[0]}>>")
            if cur[3] != prev[3]:
                notes.append(f"HP{cur[3]-prev[3]:+d}")
            if cur[4] != prev[4]:
                notes.append(f"<<ATK{cur[4]-prev[4]:+d}>>")
            if cur[5] != prev[5]:
                notes.append(f"<<DEF{cur[5]-prev[5]:+d}>>")
            if cur[6] != prev[6]:
                notes.append(f"yk{cur[6]-prev[6]:+d}")
            if cur[7] != prev[7]:
                notes.append(f"bk{cur[7]-prev[7]:+d}")
            if cur[8] != prev[8]:
                notes.append(f"gold{cur[8]-prev[8]:+d}")
        tag = ""
        if idx in ANCHORS:
            d = check_anchor(idx, cur)
            tag = "  <<<锚点OK>>>" if not d else "  <<<锚MISMATCH: " + "; ".join(d) + ">>>"
        pos = f"({cur[1]},{cur[2]})"
        print(f"{idx:>4} {repr(tokens[idx]):<12} {cur[0]:<5} {pos:<9} {cur[3]:>5} {cur[4]:>3} "
              f"{cur[5]:>3} {cur[6]:>2} {cur[7]:>2} {cur[8]:>5}  {' '.join(notes)}{tag}")

    prev = cur

print("\n=== 锚点对齐汇总 ===")
for idx, diffs in anchor_log:
    print(f"  tok[{idx}]: {'OK' if not diffs else 'MISMATCH — ' + '; '.join(diffs)}")

print("\n=== 楼层访问序列(切换点, tok[1700..2000]) ===")
for idx, fl in floor_seq:
    if idx >= 1700:
        print(f"  tok[{idx}] -> {fl}")

print("\n=== 第一个分叉锚点 ===")
print("  无分叉" if first_div is None else f"  tok[{first_div[0]}]: " + "; ".join(first_div[1]))
