"""
Decode a .h5route file and normalize route tokens to an action list.

Outer layer: lz-string Base64 -> JSON {name, version, hard, seed, route}
Inner route: lz-string Base64 -> RLE action string

Confirmed token formats (from source analysis):
  U[n] D[n] L[n] R[n]  -- move n steps (n omitted = 1)
  C[n]                  -- dialog choice, n is 0-indexed option index
  FMT<floor>:           -- floor-transition marker (player arrives at MT<floor>)
  I<mapID>:             -- use item with map tile ID <mapID>
  K<n>                  -- keypress: engine key:<n>, n=keyCode (NO trailing colon).
                           keyUp(n) 触发存档自定义快捷键绑定 → 等效使用某道具。
                           keyCode↔字符: 49='1' 50='2' 51='3' 52='4'。
                           键→道具的绑定是存档特有数据，存 data/games51/replay_keybindings.json，
                           解析器只忠实产出 KEY:<n>，不在此解析绑定。
  (xxx)                 -- 自定义/插入 action：引擎 encodeOne 对任何无前缀 token 包成 "("+t+")"，
                           decodeOne 读到 ')' 为止整串作【单】token。本塔仅出现 (help)，2 处
                           (raw@4294/4308 → 修正索引 5315/5320)。
                           【已坐实】help = 引擎内置 replayAction(extract/replay_action_handlers_src.txt)：
                           core.insertAction([{type:"insert",name:"游戏说明"}]) → 插入"游戏说明"
                           公共事件(游戏帮助菜单)。作者 MT1 自述「自动操作已实装，可以在游戏帮助中打开」
                           (MT1.json:75)，故自动操作开关挂该菜单，紧随 help 的 CHOICE token 在菜单内导航。
                           【已验证】help 与其菜单 CHOICE 对回放为无副作用 no-op
                           (verify 窗口 tok5314→5328 状态全冻结)。
                           【已定论·玩家裁定金标准】help = 开启"自动模式"开关(方案B：每步 hook，
                           route 不另记 auto 走法)。语义落地在 sim/simulator.py 的 _auto_floodfill：
                           开启后每次【当前层移动】(开门/撞墙不算)结算后跑一轮 floodfill，自动秒杀
                           可达零伤非事件怪 + 自动拾取可达道具，迭代到不动点(门挡=不可达，不穿门)。
                           落地后锚点 tok5347/5386/5545 转 PASS；首个 FAIL 推进至 tok5833(MT49 区
                           缺 +15ATK/+15DEF/+1红/HP，窗口 5545→5833 交玩家逐笔裁定中)。
"""

import json
import sys
from collections import Counter
from pathlib import Path

try:
    from lzstring import LZString
except ImportError:
    print("ERROR: pip install lzstring")
    sys.exit(1)


def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def parse_rle_route(raw: str) -> list[str]:
    """
    Parse RLE-encoded route string into normalized action list.
    Each element is one of:
      'U' 'D' 'L' 'R'       -- single step
      'CHOICE:n'             -- dialog choice n (0-indexed, pending confirmation)
      'FLOOR:MTn'            -- floor transition marker
      'ITEM:n'               -- use item (map tile ID n)
      'KEY:n'                -- keypress keyCode n (engine key:<n>); 绑定见 sim 数据
      'UNKNOWN:xxx'          -- unrecognized token, flagged for question list
    """
    actions = []
    i = 0
    n = len(raw)

    while i < n:
        c = raw[i]

        # 自定义/插入 action：(xxx) → 单 token 'xxx'（对齐引擎 _decodeRoute_decodeOne：
        # c=='(' 读到第一个 ')' 为止，整串入列）。本塔仅 (help)；help=插入"游戏说明"公共
        # 事件(自动操作开关菜单)，对回放为无副作用 no-op，详见模块 docstring。
        if c == '(':
            close = raw.find(')', i + 1)
            if close >= 0:
                actions.append(raw[i+1:close])
                i = close + 1
            else:
                i += 1  # 无闭合括号：跳过该字符（容错）
            continue

        # Floor transition: FMT<digits>:
        if raw[i:i+3] == 'FMT':
            j = i + 3
            while j < n and raw[j].isdigit():
                j += 1
            floor_num = raw[i+3:j]
            if j < n and raw[j] == ':':
                j += 1
            actions.append(f'FLOOR:MT{floor_num}')
            i = j

        # Movement: U/D/L/R + optional count
        elif c in 'UDLR':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            count = int(raw[i:j]) if j > i else 1
            i = j
            actions.extend([c] * count)

        # Dialog choice: C + digit(s)
        elif c == 'C':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            choice_n = int(raw[i:j]) if j > i else 0
            i = j
            actions.append(f'CHOICE:{choice_n}')

        # Item use: I<mapID>:
        elif c == 'I':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            item_id = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1
            actions.append(f'ITEM:{item_id}')
            i = j

        # Keypress shortcut: K<keyCode>  (engine key:<n>, NO trailing colon)
        # keyUp(n) 触发存档自定义快捷键 → 等效使用某道具；键→道具绑定是数据，不在此解析。
        elif c == 'K':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            keycode = raw[i:j]
            actions.append(f'KEY:{keycode}')
            i = j

        # Direct coordinate jump: M<x>:<y>  →  MOVE:x:y
        elif c == 'M':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            x = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1          # skip ':'
            k = j
            while k < n and raw[k].isdigit():
                k += 1
            y = raw[j:k]
            actions.append(f'MOVE:{x}:{y}')
            i = k

        # Unknown alphabetic token + optional digits + optional colon
        elif c.isalpha():
            j = i + 1
            while j < n and raw[j].isdigit():
                j += 1
            suffix = raw[i+1:j]
            if j < n and raw[j] == ':':
                j += 1
                actions.append(f'UNKNOWN:{c}{suffix}:')
            else:
                actions.append(f'UNKNOWN:{c}{suffix}')
            i = j

        else:
            i += 1

    return actions


def decode_route_file(path: str) -> dict:
    raw_bytes = Path(path).read_text(encoding='utf-8').strip()

    outer_json = decompress(raw_bytes)
    if not outer_json:
        raise ValueError("Outer decompression failed")

    outer = json.loads(outer_json)
    meta = {k: v for k, v in outer.items() if k != 'route'}
    print("=== Outer JSON meta:")
    for k, v in meta.items():
        print(f"  {k}: {v!r}")

    route_raw = decompress(outer.get('route', ''))
    if not route_raw:
        raise ValueError("Inner route decompression failed")

    print(f"\n=== Raw route (first 200 chars):\n{route_raw[:200]}")
    print(f"    Total length: {len(route_raw)} chars")

    actions = parse_rle_route(route_raw)

    types = Counter(a.split(':')[0] if ':' in a else a for a in actions)
    print(f"\n=== Token type counts: {dict(types.most_common())}")
    print(f"\n=== First 50 actions:")
    for idx, a in enumerate(actions[:50]):
        print(f"  [{idx:3d}] {a}")

    return {
        'meta': meta,
        'route_raw': route_raw,
        'actions': actions,
    }


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        candidates = list(Path(__file__).parent.parent.glob('51_*.h5route'))
        if not candidates:
            print("No .h5route file found.")
            sys.exit(1)
        path = str(candidates[0])
        print(f"Using: {path}\n")

    decode_route_file(path)
