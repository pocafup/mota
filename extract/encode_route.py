"""把动作序列编码回 .h5route（decode_route.parse_rle_route + lzstring 两层包装的逆）。

格式（与 decode_route.py 对称）：
  外层：JSON {name, version, hard, seed, route} → lzstring compressToBase64
  内层 route：RLE 动作串 → lzstring compressToBase64

RLE 编码规则（逆 parse_rle_route，与引擎 _encodeRoute_encodeOne 对齐）：
  连续相同的 U/D/L/R → 字母 + 次数（次数=1 时省略）：UUU→U3，单个→U
  CHOICE:n   → C<n>           （选项号始终带数字，原存档 C0/C1 实测）
  FLOOR:MTn  → FMT<n>:        （换层到达标记）
  ITEM:n     → I<n>:          （用道具，地图格 ID）
  KEY:n      → K<n>           （快捷键 keyCode，无尾冒号）
  MOVE:x:y   → M<x>:<y>       （坐标跳转）
  其它无前缀 token（如 'help'）→ (token)   （引擎 encodeOne 对任意自定义 token 包圆括号）

【重要·回放从游戏起点开始】.h5route 没有"中途初始态"字段——回放永远从存档 seed 决定的
游戏起点跑。所以任何【从中途态出发】的纯解算动作串（β 路线、77 步 MT10 段）都必须在前面
拼上【玩家存档从游戏起点走到该中途态】的前缀 token，整条才能在网站上正确回放。

跑法：
  python -m extract.encode_route            # 自检：整盘存档 decode→encode 往返逐字符一致
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from lzstring import LZString
except ImportError:
    print("ERROR: pip install lzstring")
    sys.exit(1)

from extract.decode_route import parse_rle_route, decompress

# 外层 JSON 元字段（取自原存档 51_*.h5route；name/version/hard/seed 决定回放起点）
DEFAULT_META = {"name": "51", "version": "Ver 3.0", "hard": "", "seed": 1722097160}


def encode_rle_route(actions: list[str]) -> str:
    """逆 parse_rle_route：规范化动作序列 → RLE 路线串。"""
    out = []
    i = 0
    n = len(actions)
    while i < n:
        a = actions[i]
        if a in ("U", "D", "L", "R"):
            j = i
            while j < n and actions[j] == a:        # 折叠连续同向移动
                j += 1
            cnt = j - i
            out.append(a + (str(cnt) if cnt > 1 else ""))
            i = j
            continue
        if a.startswith("CHOICE:"):
            out.append("C" + a[len("CHOICE:"):])
        elif a.startswith("FLOOR:MT"):
            out.append("FMT" + a[len("FLOOR:MT"):] + ":")
        elif a.startswith("ITEM:"):
            out.append("I" + a[len("ITEM:"):] + ":")
        elif a.startswith("KEY:"):
            out.append("K" + a[len("KEY:"):])
        elif a.startswith("MOVE:"):
            _, x, y = a.split(":")
            out.append("M" + x + ":" + y)
        elif a.startswith("UNKNOWN:"):
            out.append(a[len("UNKNOWN:"):])          # 原样回写（含可能的尾冒号）
        else:
            out.append("(" + a + ")")                # 自定义/插入 token，如 help
        i += 1
    return "".join(out)


def make_h5route(actions: list[str], meta: dict | None = None) -> str:
    """动作序列 → 完整 .h5route 文件文本（外层 Base64 串）。"""
    meta = dict(meta) if meta else dict(DEFAULT_META)
    meta.pop("route", None)
    route_raw = encode_rle_route(actions)
    inner = LZString().compressToBase64(route_raw)
    outer_obj = {**meta, "route": inner}            # 保持 name/version/hard/seed/route 顺序
    outer_json = json.dumps(outer_obj, ensure_ascii=False, separators=(",", ":"))
    return LZString().compressToBase64(outer_json)


def write_h5route(path: str | Path, actions: list[str], meta: dict | None = None) -> Path:
    text = make_h5route(actions, meta)
    Path(path).write_text(text, encoding="utf-8")
    return Path(path)


# ── 自检：整盘存档 decode → encode 往返一致（用玩家自己的已知对存档证编码器）──────

def _selftest():
    src = next(ROOT.glob("51_*.h5route"), None)
    if src is None:
        sys.exit("未找到 51_*.h5route，无法自检")
    raw_file = src.read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw_file))
    orig_route_raw = decompress(outer["route"])
    actions = parse_rle_route(orig_route_raw)

    # (1) RLE 往返：encode(parse(raw)) 必须与原始 RLE 串逐字符一致
    re_route_raw = encode_rle_route(actions)
    rle_ok = (re_route_raw == orig_route_raw)
    print(f"[1] RLE 往返逐字符一致: {'✅' if rle_ok else '❌'}  "
          f"(原始 {len(orig_route_raw)} 字符 / 重编 {len(re_route_raw)} 字符)")
    if not rle_ok:
        # 定位首个不一致处，便于排查
        for k in range(min(len(orig_route_raw), len(re_route_raw))):
            if orig_route_raw[k] != re_route_raw[k]:
                lo = max(0, k - 20)
                print(f"    首个差异 @{k}: 原='...{orig_route_raw[lo:k+20]}...'")
                print(f"               重='...{re_route_raw[lo:k+20]}...'")
                break

    # (2) 整文件往返：我生成的文件 decode 回来，meta + route_raw 必须与原始一致
    my_text = make_h5route(actions, {k: v for k, v in outer.items() if k != "route"})
    my_outer = json.loads(decompress(my_text))
    my_route_raw = decompress(my_outer["route"])
    meta_ok = ({k: v for k, v in my_outer.items() if k != "route"}
               == {k: v for k, v in outer.items() if k != "route"})
    route_ok = (my_route_raw == orig_route_raw)
    print(f"[2] 整文件往返 meta 一致: {'✅' if meta_ok else '❌'}  "
          f"route 串一致: {'✅' if route_ok else '❌'}")
    print(f"    我的 meta: {dict((k, v) for k, v in my_outer.items() if k != 'route')}")

    # (3) 动作序列往返：parse(我的文件) 与原始动作序列逐项一致
    my_actions = parse_rle_route(my_route_raw)
    act_ok = (my_actions == actions)
    print(f"[3] 动作序列往返逐项一致: {'✅' if act_ok else '❌'}  ({len(actions)} 个动作)")

    ok = rle_ok and meta_ok and route_ok and act_ok
    print(f"\n编码器自检: {'全部通过 ✅ —— 用玩家自己的已知对存档证明 decode↔encode 互逆' if ok else '有失败 ❌'}")
    return ok


if __name__ == "__main__":
    _selftest()
