"""【方向2·诊断·只读】dump beam"打怪拿血"决策 → 排序键 v_boss_score 到底怎么算拿血净收益。
（只读·用引擎 compute_combat + 真实重放·不手算·不碰封板件 search_quotient/beam.py）

★玩家纠正后的根本原因（精确·2026-06-17）：
  beam"积极拿血"的病 ≠ "早拿的血浪费了"（旧错误理解·血没浪费、该拿的还要拿）。
  真因 = 【拿血的代价(打怪损血)随属性降低】：
    血分两类——①无代价血(地上直接拿·不打怪)→随时拿无所谓、早晚都行；
              ②有代价血(要打怪才拿到)→属性越高打怪损血越少→净拿到的血越多→净收益越大。
    ⇒ "有代价的血"该等属性高了再拿(那时损血少、净赚多)。= 时序问题(何时拿)·非数量问题(拿多少)。
  beam 病：属性还低时就去打怪拿有代价的血(损血多·净收益小)、还打没意义怪掉没意义血。

本脚本只读坐实三件事：
 【A】重放 beam 实际半截路径(dir2_redkey_halfway_bk400)，逐步标注每个 hp 变化(战斗损血/拿血/
      地形)与属性变化 → 统计 beam 在低属性段打了多少怪、损了多少血、其中多少"打完没涨属性/钥匙"。
 【B】拿血代价随属性：守门 yellowGuard(已知真值)损血随 ATK 曲线 → 同一怪 ATK 高损血少
      = 拿其后的血净收益随属性升而增大(该推迟)。
 【C】排序键 v_boss=hp+delta 病机制：hp 是 step 净值(已扣损血)；但 myopic→低属性时"打怪拿血"
      子态 hp 立即更高→排序分涨→beam 现在就拿，看不到"推迟到高属性净赚更多"。

用法：python -u analysis/dir2_redkey_bloodcost_dump.py
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from analysis.extract_zone1_milestones import build_initial_state          # noqa: E402
from analysis.dir2_redkey_beam_probe import v_boss_score, TOK_SHIELD, fmt   # noqa: E402
from extract.decode_route import parse_rle_route, decompress               # noqa: E402
from sim.simulator import step                                             # noqa: E402
from sim.combat import Monster, PlayerState, compute_combat                # noqa: E402

HALFWAY = ROOT / "dir2_redkey_halfway_bk400.h5route"


def decode_actions(path):
    raw = Path(path).read_text(encoding="utf-8").strip()
    outer = json.loads(decompress(raw))
    return parse_rle_route(decompress(outer["route"])), outer


def keytuple(h):
    return tuple(sorted((k, v) for k, v in h.keys.items()
                        if isinstance(v, (int, float)) and v))


def main():
    actions, outer = decode_actions(HALFWAY)
    n_beam = len(actions) - (TOK_SHIELD + 1)
    print("=" * 86)
    print(f"半截路线 {HALFWAY.name}  seed={outer.get('seed')}  共 {len(actions)} token")
    print(f"前缀(开局→铁盾)=tok[:{TOK_SHIELD + 1}]  beam 探索段=tok[{TOK_SHIELD + 1}:] ({n_beam} 步)")
    print("=" * 86)

    # ── 【A】重放整条，从铁盾态(tok TOK_SHIELD)起逐步记录事件 ──
    s = build_initial_state()
    shield_state = None
    fights = []   # (i, atk_b, def_b, hp_b, dmg, datk, ddef, dkey)
    bloods = []   # (i, atk_b, dhp)  无代价拿血(dhp>0 且非战斗)
    gems = []     # (i, datk, ddef)
    for i, t in enumerate(actions):
        h_b = s.hero
        atk_b, def_b, hp_b, kill_b = h_b.atk, h_b.def_, h_b.hp, h_b.kill_count
        keys_b = keytuple(h_b)
        s = step(s, t)
        if s.dead:
            print(f"  ⚠ 重放在 tok{i} 死亡，停")
            break
        if i == TOK_SHIELD:
            shield_state = s
        if i <= TOK_SHIELD:
            continue
        h_a = s.hero
        dhp = h_a.hp - hp_b
        datk = h_a.atk - atk_b
        ddef = h_a.def_ - def_b
        dkill = h_a.kill_count - kill_b
        dkey = (keytuple(h_a) != keys_b)
        if dkill > 0:
            fights.append((i, atk_b, def_b, hp_b, -dhp, datk, ddef, dkey))
        elif dhp > 0:
            bloods.append((i, atk_b, dhp))
        if datk > 0 or ddef > 0:
            gems.append((i, datk, ddef))

    print(f"\n铁盾起点态: {fmt(shield_state)}")
    print(f"半截终态:   {fmt(s)}")

    # 战斗汇总
    n_fight = len(fights)
    total_loss = sum(f[4] for f in fights)
    by_atk = Counter(f[1] for f in fights)              # 战斗发生时的 ATK 分布
    loss_by_atk = Counter()
    for f in fights:
        loss_by_atk[f[1]] += f[4]
    # "无兑现"战斗 = 打完该步 atk/def/钥匙都没变（嫌疑刷怪/没意义怪·不下断言、如实报）
    barren = [f for f in fights if f[5] == 0 and f[6] == 0 and not f[7]]
    barren_loss = sum(f[4] for f in barren)

    print("\n" + "─" * 86)
    print("【A】beam 探索段实战统计（重放真实路径·hero 状态逐步 diff）")
    print("─" * 86)
    print(f"  打怪(kill+)步数 = {n_fight}    战斗总损血 = {total_loss}")
    print(f"  拿属性宝石步 = {len(gems)} (ATK+{sum(g[1] for g in gems)} / DEF+{sum(g[2] for g in gems)})")
    print(f"  无代价拿血步 = {len(bloods)}    无代价得血合计 = {sum(b[2] for b in bloods)}")
    print(f"\n  战斗按【当时 ATK】分布（看 beam 在多低属性时就开打）：")
    for atk in sorted(by_atk):
        print(f"    ATK{atk}: 打了 {by_atk[atk]:>3} 次  损血 {loss_by_atk[atk]:>5}")
    print(f"\n  ★【无兑现战斗】(打完该步 ATK/DEF/钥匙均未变) = {len(barren)} 次  损血 {barren_loss}")
    print(f"    = 嫌疑的'打没意义怪掉没意义血'(不下断言·开机关门的怪也可能在内·如实报供判断)")
    # 列前 12 个无兑现战斗看样子
    print(f"    前 12 例(tok, 当时ATK/DEF/HP, 损血)：")
    for f in barren[:12]:
        print(f"      tok{f[0]}: ATK{f[1]}/DEF{f[2]}/HP{f[3]} → 损血 {f[4]}")

    # ── 【B】拿血代价随属性：守门 yellowGuard 损血随 ATK（引擎权威·非手算）──
    print("\n" + "─" * 86)
    print("【B】拿血代价随属性降低（守门 yellowGuard 损血随 ATK·引擎 compute_combat）")
    print("─" * 86)
    mdb = json.loads((ROOT / "data/games51/monsters.json").read_text(encoding="utf-8"))
    g = mdb["yellowGuard"]
    G = Monster(id=g["id"], name=g["name"], hp=g["hp"], atk=g["atk"],
                def_=g["def"], special=list(g.get("special", [])))
    print(f"  yellowGuard: hp={G.hp} atk={G.atk} def={G.def_}")
    loss_at = {}
    for atk in range(23, 29):
        r = compute_combat(PlayerState(hp=99999, atk=atk, def_=25), G)
        loss_at[atk] = r.damage
        print(f"    ATK{atk}/DEF25: 杀1守卫损血 = {r.damage}")
    print(f"\n  ★净收益演示：设此怪挡着一瓶血 P（P 恒定·与属性无关）→ 拿到这瓶血净收益 = P − 损血。")
    print(f"     损血随 ATK 升而降 → 净收益随属性升而【增大】→ 早拿(低属性)净赚少、推迟(高属性)净赚多：")
    for P in (300, 400):
        cells = "  ".join(f"ATK{a}:净{P - loss_at[a]:>4}" for a in (23, 25, 27))
        print(f"     若 P={P}:  {cells}    (ATK23→27 净收益多赚 {loss_at[23] - loss_at[27]})")

    # ── 【C】v_boss=hp+delta 排序键的 myopic 病 ──
    print("\n" + "─" * 86)
    print("【C】排序键 v_boss=hp+delta 怎么算'拿血'——扣了损血、但 myopic 不表达'推迟更划算'")
    print("─" * 86)
    print("  • v_boss(state)=hero.hp + delta(atk,def)；hp 取自 step 后的态 → 损血【已扣】(净值)。")
    print("  • 但它是【对当前态的短视估值】：决策时刻比较'拿了血的子态'(hp 立即更高) vs '没拿血去攒")
    print("    属性的子态'(hp 不占优甚至更低·攒属性路上要走/打/踩地形)→ 排序偏好 hp 高者=【现在就拿】。")
    print("  • 同一瓶有代价的血，低属性拿 net 小但仍>0 → v_boss 涨 → beam 拿；它【看不到】'推迟到高属性")
    print("    净赚更多'(那条路径中途 hp 不占优、被 beam 截掉)。↓ 用守卫损血代入演示 v_boss 的 hp 增量：")
    print(f"    {'属性':>10} | {'杀此怪损血':>10} | {'拿血P=400净赚(=v_boss的hp增量)':>30}")
    for a in (25, 27):
        net = 400 - loss_at[a]
        print(f"    {'ATK' + str(a) + '/DEF25':>10} | {loss_at[a]:>10} | {net:>20}  (v_boss +{net})")
    print(f"  ⟹ ATK25 拿净 {400 - loss_at[25]}、ATK27 拿净 {400 - loss_at[27]}：两者 v_boss 都涨(都>0)，")
    print(f"     beam 在 ATK25 就把血拿了(net{400 - loss_at[25]})，没等到 ATK27(net{400 - loss_at[27]})多赚")
    print(f"     {loss_at[25] - loss_at[27]} → 正是'该推迟的有代价血、被 myopic 排序提前拿掉'的病。")


if __name__ == "__main__":
    main()
