"""逐 token 打印 tok[1603]→tok[2000]，与玩家提供的3个真值锚点对比，定位第一个分叉。
口径：tok[N] = 处理完 tokens[0..N]（与 test_checkpoints.py 一致）。
重点标注 ATK/DEF 每次变化（找漏掉的那次祭坛+4/+2 或宝石）+ 楼层切换 + HP 大跳（恶战）。
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

# 玩家金标准锚点: idx -> (floor, x, y, hp, atk, def, yk, bk)
ANCHORS = {
    1809: ('MT15', 7, 10, 179, 68, 54, 2, None),
    1902: ('MT20', 6, 10, 591, 68, 54, 2, 1),
    2000: ('MT16', 3, 1, 618, 72, 56, 0, 0),
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


LO, HI = 1602, 2000
tokens = load_tokens()
state = build_initial_state()
for idx in range(LO + 1):
    state = step(state, tokens[idx])

prev = snap(state)
print(f"=== tok[{LO}] 起点: floor={prev[0]} pos=({prev[1]},{prev[2]}) "
      f"HP={prev[3]} ATK={prev[4]} DEF={prev[5]} yk={prev[6]} bk={prev[7]} gold={prev[8]}")
print(f"{'idx':>4} {'token':<11} {'floor':<5} {'pos':<8} {'HP':>5} {'ATK':>3} "
      f"{'DEF':>3} {'yk':>2} {'bk':>2} {'gold':>4}  note")

first_div = None
for idx in range(LO + 1, HI + 1):
    tok = tokens[idx]
    state = step(state, tok)
    cur = snap(state)
    notes = []
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

    anchor_tag = ""
    if idx in ANCHORS:
        ef, ex, ey, ehp, eatk, edef, eyk, ebk = ANCHORS[idx]
        diffs = []
        if cur[0] != ef:
            diffs.append(f"floor sim={cur[0]}≠真{ef}")
        if (cur[1], cur[2]) != (ex, ey):
            diffs.append(f"pos sim=({cur[1]},{cur[2]})≠真({ex},{ey})")
        if cur[3] != ehp:
            diffs.append(f"HP sim={cur[3]}≠真{ehp}({cur[3]-ehp:+d})")
        if cur[4] != eatk:
            diffs.append(f"ATK sim={cur[4]}≠真{eatk}({cur[4]-eatk:+d})")
        if cur[5] != edef:
            diffs.append(f"DEF sim={cur[5]}≠真{edef}({cur[5]-edef:+d})")
        if eyk is not None and cur[6] != eyk:
            diffs.append(f"yk sim={cur[6]}≠真{eyk}")
        if ebk is not None and cur[7] != ebk:
            diffs.append(f"bk sim={cur[7]}≠真{ebk}")
        if diffs:
            anchor_tag = "  <<<锚点MISMATCH: " + "; ".join(diffs) + ">>>"
            if first_div is None:
                first_div = (idx, list(diffs))
        else:
            anchor_tag = "  <<<锚点OK>>>"

    # 只打印有变化的行 + 锚点行（否则 400 行太长）
    if notes or anchor_tag:
        pos = f"({cur[1]},{cur[2]})"
        print(f"{idx:>4} {repr(tok):<11} {cur[0]:<5} {pos:<8} {cur[3]:>5} {cur[4]:>3} "
              f"{cur[5]:>3} {cur[6]:>2} {cur[7]:>2} {cur[8]:>4}  {' '.join(notes)}{anchor_tag}")
    prev = cur

print("\n=== ATK/DEF 成长汇总（真值：1603=64/52 → 1809=68/54 → 2000=72/56）===")
print("=== 锚点对比小结 ===")
if first_div is None:
    print("3个锚点全部 OK，无分叉。")
else:
    print(f"第一个分叉锚点: tok[{first_div[0]}] — " + "; ".join(first_div[1]))
