"""导出 K=200 V_zone 跑到 MT10 的【最优候选】完整路线（玩家要先自己看，只导出不分析）。

复现 probe_crossfloor_beam.py --beam 200 --score vzone 的确定性搜索，on_admit 捕获到达 MT10 的
最优候选动作序列；再用引擎 step 逐步重放，标注每个里程碑（换层/拿装备宝石/拿钥匙/开门/打怪/到 MT10/
停点）当刻坐标+HP/ATK/DEF+持有。终态经 solver.verify.replay 独立重放核对（引擎裁判=权威）。
输出 → k200_mt10_route.md（人读） + k200_mt10_route.json（原始动作串，可照走/复跑）。"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state
from solver.quotient import search_quotient, value_vector
from solver.verify import replay
from probe_crossfloor import build_start
from vzone import build_zone, v_zone

OUT = Path(__file__).parent


def snap(s):
    """当刻可读快照：坐标/属性/持有/累计杀怪。"""
    h = s.hero
    vv = value_vector(s)
    return dict(floor=s.current_floor, x=h.x, y=h.y, hp=h.hp, atk=h.atk, def_=h.def_,
                mdef=h.mdef, gold=h.gold,
                keys={k: v for k, v in dict(h.keys).items() if v},
                items={k: v for k, v in dict(h.items).items() if v},
                kill=vv.get("kill", 0))


def main():
    start, nopen = build_start()
    zone = build_zone()
    memo = {}

    def beam_score_fn(s):
        hit = memo.get(id(s))
        if hit is not None and hit[0] is s:
            return hit[1]
        v = v_zone(zone, s)[0]
        memo[id(s)] = (s, v)
        return v

    mt10_admits = []   # (hp, atk, def, mdef, actions_tuple, wave_len)

    def on_admit(stt, actions):
        if stt.current_floor == "MT10":
            h = stt.hero
            mt10_admits.append((h.hp, h.atk, h.def_, h.mdef, tuple(actions)))

    goal_cell = ("MT0", 1, 1)
    print(f"复跑 K=200 V_zone 搜索（确定性，复现 720 态）… 起点={start.current_floor}"
          f"({start.hero.x},{start.hero.y}) HP={start.hero.hp} ATK={start.hero.atk} DEF={start.hero.def_}")
    t0 = time.perf_counter()
    res = search_quotient(start, goal_cell, step, max_states=120000, cross_floor=True,
                          beam_k=200, on_admit=on_admit, beam_score_fn=beam_score_fn)
    dt = time.perf_counter() - t0
    print(f"搜索完成 {dt:.1f}s  hit_cap={res.hit_cap}  到达 MT10 admit 次数={len(mt10_admits)}")
    if not mt10_admits:
        print("⚠ 未捕获任何 MT10 到达态")
        return

    # 最优候选 = 最大 HP（与报告 maxHP=720 同口径）
    best = max(mt10_admits, key=lambda t: t[0])
    hp, atk, df, md, acts = best
    print(f"最优候选 MT10：HP={hp} ATK={atk} DEF={df} mdef={md}  动作步数={len(acts)}")
    # 列出全部 MT10 到达态（去重看 Pareto）
    uniq = sorted(set((a[0], a[1], a[2], a[3]) for a in mt10_admits), reverse=True)
    print(f"全部 MT10 到达态(去重) {len(uniq)} 个：{uniq[:8]}")

    # ── 引擎逐步重放标注里程碑 ──
    s = _copy_state(start)
    prev = snap(s)
    rows = [("【起点】", 0, "", prev)]
    for i, tok in enumerate(acts):
        s = step(s, tok)
        cur = snap(s)
        tags = []
        if cur["floor"] != prev["floor"]:
            tags.append(f"换层 {prev['floor']}→{cur['floor']}")
        if cur["atk"] != prev["atk"]:
            tags.append(f"ATK {prev['atk']}→{cur['atk']}（拿攻击装备/宝石）")
        if cur["def_"] != prev["def_"]:
            tags.append(f"DEF {prev['def_']}→{cur['def_']}（拿防御装备/宝石）")
        if cur["mdef"] != prev["mdef"]:
            tags.append(f"MDEF {prev['mdef']}→{cur['mdef']}")
        if cur["keys"] != prev["keys"]:
            tags.append(f"钥匙 {prev['keys']}→{cur['keys']}")
        if cur["items"] != prev["items"]:
            tags.append(f"道具 {prev['items']}→{cur['items']}")
        if cur["kill"] != prev["kill"]:
            tags.append(f"打怪 +{cur['kill'] - prev['kill']}（HP {prev['hp']}→{cur['hp']}）")
        if tags:
            rows.append((" ; ".join(tags), i + 1, tok, cur))
        prev = cur
    final = snap(s)
    rows.append(("【终点/停点】", len(acts), "", final))

    # ── 独立重放核对（引擎裁判）──
    rep = replay(start, list(acts), step, _copy_state)
    ok = (rep.current_floor == "MT10" and rep.hero.hp == hp
          and rep.hero.atk == atk and rep.hero.def_ == df)
    verdict = "✅ 一致（引擎重放=权威）" if ok else (
        f"⚠ 不一致：重放={rep.current_floor} HP={rep.hero.hp} ATK={rep.hero.atk} DEF={rep.hero.def_}")

    # ── 写 markdown ──
    md_lines = []
    A = md_lines.append
    A("# K=200 V_zone 到达 MT10 最优候选路线（只导出，未分析）\n")
    A(f"- 来源：复跑 `probe_crossfloor_beam.py --beam 200 --score vzone` 的确定性搜索，"
      f"on_admit 捕获到 MT10 的最优候选（最大 HP）。")
    A(f"- 搜索：cross_floor=True，beam_k=200，max_states=120000，hit_cap={res.hit_cap}，耗时 {dt:.1f}s。")
    A(f"- 起点：{rows[0][3]['floor']}({rows[0][3]['x']},{rows[0][3]['y']}) "
      f"HP={rows[0][3]['hp']} ATK={rows[0][3]['atk']} DEF={rows[0][3]['def_']}（穿过 {nopen} token 开局噩梦后首个自由态）。")
    A(f"- 最优候选终态：MT10 HP={hp} ATK={atk} DEF={df} mdef={md}，动作 {len(acts)} 步。")
    A(f"- **这条是引擎重放过的**：solver.verify.replay 独立重放核对 → {verdict}")
    A(f"- 全部到达 MT10 的去重态 {len(uniq)} 个：{uniq[:8]}\n")

    A("## 1. 完整可照走动作序列\n")
    A("> 每个字符=一步 step token（移动/换层/触发都由引擎 step 解释）。原始串另存 `k200_mt10_route.json`。\n")
    A("```")
    A("".join(acts))
    A("```\n")

    A("## 2. 逐里程碑（每个关键节点：换层/拿装备宝石/拿钥匙/开门/打怪/到 MT10/停点）\n")
    A("| # | 第几步 | token | 事件 | 层 | 坐标 | HP | ATK | DEF | 钥匙 | 道具 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for tag, stepno, tok, st in rows:
        keys = ",".join(f"{k}:{v}" for k, v in st["keys"].items()) or "—"
        items = ",".join(f"{k}:{v}" for k, v in st["items"].items()) or "—"
        A(f"| {tag} | {stepno} | `{tok or '—'}` | | {st['floor']} | ({st['x']},{st['y']}) | "
          f"{st['hp']} | {st['atk']} | {st['def_']} | {keys} | {items} |")
    A("")

    A("## 3. 停点\n")
    A(f"- 动作序列在第 {len(acts)} 步结束，终态停在 **{final['floor']}({final['x']},{final['y']})**，"
      f"HP={final['hp']} ATK={final['atk']} DEF={final['def_']}，"
      f"钥匙={final['keys'] or '无'}，累计杀怪={final['kill']}。")
    A(f"- 这是该候选**首次被 admit 到 MT10 时的快照**（搜索捕获到 MT10 的那一刻）。"
      f"全程到达 MT10 的去重态仅 {len(uniq)} 个，未见更深推进的 MT10 态被 admit。")

    A("\n## 4. 性质 / 终态字段\n")
    A(f"- 性质：**搜索缩点产出 + 引擎独立重放核对**（动作串经 solver.verify.replay 重放，{verdict}）。")
    A(f"- 终态字段（引擎重放 rep）：floor={rep.current_floor} (x={rep.hero.x},y={rep.hero.y}) "
      f"HP={rep.hero.hp} ATK={rep.hero.atk} DEF={rep.hero.def_} mdef={rep.hero.mdef} "
      f"gold={rep.hero.gold} 钥匙={ {k: v for k, v in dict(rep.hero.keys).items() if v} } "
      f"累计杀怪={value_vector(rep).get('kill', 0)}。")

    md_path = OUT / "k200_mt10_route.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    json_path = OUT / "k200_mt10_route.json"
    json_path.write_text(json.dumps({
        "source": "probe_crossfloor_beam --beam 200 --score vzone (复跑捕获)",
        "start": rows[0][3], "terminal": final,
        "replay_ok": ok, "n_steps": len(acts),
        "actions": list(acts),
        "milestones": [{"tag": t, "step": sn, "token": tok, "state": st} for t, sn, tok, st in rows],
        "all_mt10_states": uniq,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写 → {md_path.name} / {json_path.name}")


if __name__ == "__main__":
    main()
