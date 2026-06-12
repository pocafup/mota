"""生成可在 h5mota 网站回放的 .h5route 文件（用 encode_route 编码器；该编码器已自检 decode↔encode 互逆）。

产物：
  1) 51_roundtrip_full.h5route —— 玩家原存档 decode→encode 整盘往返。点开应与原存档回放【完全一致】
     （50 层全程、终态相同）。最纯的编码器证明：纯往返、零解算内容、零拼接。若它能正常回放，
     说明 编码器 + Python lzstring↔网站 JS lz-string + 整条回放管线 全部打通。
  2) mt10_bosspass_77steps.h5route —— 玩家存档【游戏起点→MT10 入口】前缀(token[:N]，含原本 FMT10 标记)
     + 缩点解算的 77 步过 boss 段(末尾 MT10→MT11 处插 FMT11 标记)。点开应自动回放到 MT11、
     终态 HP=701 ATK=30 DEF=30 —— 验证【77 步过 boss 路线在游戏自己的引擎里真能走通】。
     ⚠ .h5route 无"中途初始态"字段，回放必须从游戏 seed 起点跑，故 77 步前必须拼玩家前缀。
     前缀是玩家自己已走通的录制(已知对)，被测的新内容只有那 77 步 boss 段。

落盘前【封板 sim 重放预检】：整 token 串从干净起点喂一遍 sim.step，断言终态符合预期再编码。
网站回放才是终审（走游戏自己的引擎），sim 预检只用来排除拼接/编码错误，不替代网站验收。

跑法：python -m extract.gen_h5routes
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extract.decode_route import parse_rle_route, decompress
from extract.encode_route import write_h5route, DEFAULT_META
from extract.export_mt10_boss_route import (capture_boss_entry, drive_boss_pass,
                                            make_initial_state, load_tokens)
from sim.simulator import step, _copy_state


def insert_floor_markers(actions, start_state):
    """在跨层处插入 FLOOR:MT<到达层>，对齐原存档"每次换层都带 FMT 标记"的格式。"""
    s = _copy_state(start_state)
    out, prev = [], s.current_floor
    for a in actions:
        s = step(s, a)
        out.append(a)
        if s.current_floor != prev:
            out.append(f"FLOOR:MT{s.current_floor[2:]}")
            prev = s.current_floor
    return out


def replay_all(actions, start_state=None):
    s = make_initial_state() if start_state is None else _copy_state(start_state)
    for a in actions:
        s = step(s, a)
    return s


def gen_roundtrip():
    src = next(ROOT.glob("51_*.h5route"))
    outer = json.loads(decompress(src.read_text(encoding="utf-8").strip()))
    meta = {k: v for k, v in outer.items() if k != "route"}
    actions = parse_rle_route(decompress(outer["route"]))
    out = write_h5route(ROOT / "51_roundtrip_full.h5route", actions, meta)
    return out, len(actions)


def gen_bosspass():
    tokens = load_tokens()
    entry_idx, entry_state = capture_boss_entry()
    end = entry_idx + 1
    if end < len(tokens) and tokens[end] == "FLOOR:MT10":   # 含玩家原本的 FMT10 标记
        end += 1
    prefix = tokens[:end]

    _, boss_actions, _ = drive_boss_pass(_copy_state(entry_state))
    boss_marked = insert_floor_markers(boss_actions, entry_state)
    spliced = prefix + boss_marked

    # 封板 sim 预检：前缀须到 MT10 入口；整串须到 MT11 HP701
    pre = replay_all(prefix)
    assert pre.current_floor == "MT10" and (pre.hero.x, pre.hero.y) == (1, 10) \
        and pre.hero.hp == 735, \
        f"前缀终态不符: {pre.current_floor} ({pre.hero.x},{pre.hero.y}) HP{pre.hero.hp}"
    fin = replay_all(spliced)
    assert fin.current_floor == "MT11" and fin.hero.hp == 701 and fin.hero.atk == 30 \
        and fin.hero.def_ == 30, \
        f"整串终态不符: {fin.current_floor} HP{fin.hero.hp} ATK{fin.hero.atk} DEF{fin.hero.def_}"

    out = write_h5route(ROOT / "mt10_bosspass_77steps.h5route", spliced, DEFAULT_META)
    return out, dict(entry_idx=entry_idx, prefix_len=len(prefix),
                     boss_steps=len(boss_actions), total=len(spliced),
                     fin=(fin.current_floor, fin.hero.hp, fin.hero.atk, fin.hero.def_))


def main():
    p1, n1 = gen_roundtrip()
    print(f"[文件1] {p1.name}  整盘往返，{n1} 个动作")
    print(f"        → 点开应与玩家原存档回放完全一致（50 层全程、终态相同）")
    p2, info = gen_bosspass()
    print(f"[文件2] {p2.name}")
    print(f"        前缀 token[:{info['prefix_len']}]（游戏起点→MT10 入口，含 FMT10）"
          f" + {info['boss_steps']} 步过 boss（插 FMT11）= 共 {info['total']} token")
    print(f"        封板 sim 预检终态: floor={info['fin'][0]} HP={info['fin'][1]} "
          f"ATK={info['fin'][2]} DEF={info['fin'][3]}  ✅")
    print(f"        → 点开应自动回放到 MT11、终态 HP=701 ATK=30 DEF=30")


if __name__ == "__main__":
    main()
