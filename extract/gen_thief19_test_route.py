"""生成"MT2 小偷 (1,9) 行为"网站验证用 .h5route。

目的：玩家要在 h5mota.com 看 MT2 小偷被搬到 (1,9) 后的真实表现，以印证 sim 1b 推断
（"keep-move 落点激活该格事件→挡路对话"）对不对。

【关键事实，决定本路线只能这么做——非断言，下面 trace 实测打印】：
小偷口袋 {(3,8),(4,8),(4,7)} 唯一入口是 MT3 伏击把英雄传送回 MT2(3,8)；触发 (3,7) 后
小偷搬到 (1,9)，但英雄要出口袋只能再踩 (3,7)（sim 里这步 re-fire 把 0 写回 (1,9) 清掉
小偷）或走 (5,8) 铁门（需杀 atk180/def110 蓝卫·该阶段杀不动）。所以【没有任何一条可走
路线能让英雄"绕开 (3,7) 再撞活的 (1,9) 小偷"】——玩家真 route 也因此走到 (1,9) 时小偷
已被清、畅通。本测试不假装能展示"持续挡路"，而是给玩家看 sim 模型里的三个关键时刻，
让网站裁定每一处对不对。

本脚本：重放玩家真 token，定位并打印小偷段（触发/清除/下行过 (1,9) 的精确单步），
按"触发后重进 MT3"截断，复用源存档 meta，生成 thief19_mt2_test.h5route。

跑法：python extract/gen_thief19_test_route.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "extract"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from lzstring import LZString

import sim.simulator as S
from extract.export_mt10_boss_route import make_initial_state, load_tokens
from extract.encode_route import write_h5route

FIRED = []
_orig_eel = S._execute_event_list


def _patched_eel(state, event_list, ex, ey, ctx=None):
    FIRED.append((state.current_floor, ex, ey))
    return _orig_eel(state, event_list, ex, ey, ctx)


S._execute_event_list = _patched_eel


def thief19(s):
    mt2 = s.floors.get("MT2")
    return mt2.entities[9][1] if mt2 else None


def source_meta():
    """读玩家源存档 51_*.h5route 外层 meta（name/version/hard/seed），保证回放对到同一存档。"""
    src = next(ROOT.glob("51_*.h5route"), None)
    if src is None:
        sys.exit("未找到 51_*.h5route")
    outer = json.loads(LZString().decompressFromBase64(src.read_text(encoding="utf-8").strip()))
    return src.name, {k: v for k, v in outer.items() if k != "route"}


def main():
    units = load_tokens()                       # parse_rle_route 已展开到单步
    s = make_initial_state()

    trigger_u = clear_u = reenter_u = None
    rows = []                                   # (ui, unit, before, after, t19, fired, fired_19, fired_37)
    prev_t19 = thief19(s)
    for ui in range(len(units)):
        u = units[ui]
        before = (s.current_floor, s.hero.x, s.hero.y)
        nf = len(FIRED)
        s = S.step(s, u)
        after = (s.current_floor, s.hero.x, s.hero.y)
        t19 = thief19(s)
        fired = FIRED[nf:]
        f19 = any(f == ("MT2", 1, 9) for f in fired)
        f37 = any(f == ("MT2", 3, 7) for f in fired)
        rows.append((ui, u, before, after, t19, fired, f19, f37))

        if trigger_u is None and prev_t19 in (0, None) and t19 not in (0, None):
            trigger_u = ui
        if trigger_u is not None and clear_u is None and prev_t19 not in (0, None) and t19 in (0, None):
            clear_u = ui
        if (trigger_u is not None and reenter_u is None
                and before[0] == "MT2" and after[0] == "MT3"):
            reenter_u = ui
            break
        prev_t19 = t19

    if reenter_u is None:
        sys.exit("未找到触发后重进 MT3 的边界，截断失败——需复查 token")
    cutoff = reenter_u + 1                       # 含踏入 MT3 那一步

    print(f"玩家真 route 共 {len(units)} 单步；MT2 小偷段关键单步：")
    print(f"  触发(3,7)、小偷搬到(1,9) = u#{trigger_u}")
    print(f"  sim 里 (1,9) 被清(再踩(3,7) re-fire) = u#{clear_u}")
    print(f"  触发后重进 MT3 = u#{reenter_u}  → 截断 cutoff = {cutoff}（含此步）\n")

    print("u#   单步  英雄(前→后)              (1,9)小偷  fire(3,7)  fire(1,9)")
    print("-" * 74)
    lo = max(0, (trigger_u or 0) - 8)
    for (ui, u, before, after, t19, fired, f19, f37) in rows:
        if ui < lo:
            continue
        mk_t = "在" if t19 else "空"
        mk37 = "★" if f37 else " "
        mk19 = "★" if f19 else " "
        tag = ""
        if ui == trigger_u:
            tag = "  ← 触发：小偷搬到(1,9)"
        elif ui == clear_u:
            tag = "  ← sim:再踩(3,7)清(1,9)"
        elif ui == reenter_u:
            tag = "  ← 重进MT3(截断处)"
        print(f"{ui:>3}  {u:>4}  {str(before):>22}→{str(after):<16}"
              f"{mk_t:>6}    {mk37:^6}   {mk19:^6}{tag}")

    src_name, meta = source_meta()
    out = ROOT / "thief19_mt2_test.h5route"
    write_h5route(out, units[:cutoff], meta)
    print(f"\n源存档 meta 取自 {src_name}: {meta}")
    print(f"已生成: {out}  （{cutoff} 单步，回放从游戏起点开始）")


if __name__ == "__main__":
    main()
