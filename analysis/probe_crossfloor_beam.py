"""跨层楼梯缩点 + beam 控宽【自主爬升检验】探针（玩家 2026-06-08 选项③：先控宽再加飞行）。

口径：把 solver/beam.py 的 Δ形式 V（攒攻防奖励、对杀怪中性）+ 保护维（钥匙/消耗道具/飞行道具）
接到跨层 search_quotient 的 wave 截断上（beam_k）。核心检验：搜索能否【自己往上爬去合并含永久
属性的上层块】——纯靠拓扑(楼梯边)+V 自评每个上层块值不值得，自己撞到盾（floor_graph §8 第二步
飞行未接，本探针只走楼梯边）。

【避免喂答案】goal 给【楼梯不可达的 MT0】→ 搜索无定向终点、纯探索；on_admit 记录各层【可达最优
属性 Pareto】、beam_cut_sink 落盘被截点（红线审计，不静默丢）。绝不把 handoff 里 shield 坐标喂进
搜索作目标——是否爬到上层拿盾由 V 自己算。route 仅作下界对照（不喂走法）。

多层安全：起点 _single_floor_copy=False（深拷，跨层兄弟分支不共享引用）。引擎只当裁判：最优候选
丢 solver.verify.replay 独立重放逐字段核对（证明楼梯线路可照走）。
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from seg_experiment import build_initial_state, load_tokens
from sim.simulator import step, _copy_state
from solver.quotient import search_quotient, value_vector
from solver.beam import build_future_roster, FutureCfg, _future_potential, _region_bounds
from solver.verify import replay
from probe_crossfloor import build_start, _fidx, OPENING_PREFIX

OUT = Path(__file__).parent


# ─── route 下界对照（仅参照，不喂走法）──────────────────────────────────────────────

def route_profile():
    """重放整条 route，按层记录英雄属性轨迹 + 通关末态。供「搜索 vs route」对照（route=下界）。
    只记【开局噩梦之后】(token≥OPENING_PREFIX) 的轨迹——与搜索起点(噩梦后 MT3 400/10/10)同口径；
    噩梦前的 1000/100/100 过场态不可路由(floor_graph §5)，计入会污染对照。

    【基准纠正 2026-06-08】route 是整条 50 层通关存档，大后期会反复回低层收尾/找商人刷属性，所以
    某低层的【全程峰值】几乎都是 77%–98% 进度处的【后期回访态】，不是该层同期水平（实测一区首过
    ATK≤27，峰值却 217/507）。对照基准【必须用首次通过】(first_entry/first_exit)，max_* 仅留作
    「全程峰(后期回访·非同期参照)」展示、绝不当基准。详见 memory feedback-route-baseline。"""
    state = build_initial_state()
    tokens = load_tokens()
    prof = {}
    prev_floor = None

    def rec(s):
        h = s.hero
        d = prof.setdefault(s.current_floor,
                            {"first_entry": None, "first_exit": None, "_open": False,
                             "max_hp": -1, "max_atk": 0, "max_def": 0})
        if d["first_entry"] is None:    # 首次进入该层
            d["first_entry"] = (h.hp, h.atk, h.def_)
            d["_open"] = True
        if d["_open"]:                  # 仍在首次访问段内 → 滚动更新「首次离开」属性
            d["first_exit"] = (h.hp, h.atk, h.def_)
        d["max_hp"] = max(d["max_hp"], h.hp)
        d["max_atk"] = max(d["max_atk"], h.atk)
        d["max_def"] = max(d["max_def"], h.def_)

    for i, tok in enumerate(tokens):
        state = step(state, tok)
        if i >= OPENING_PREFIX - 1:     # 噩梦后首个自由态起记（与 build_start 同口径）
            fl = state.current_floor
            if prev_floor is not None and fl != prev_floor:   # 离开上一层 → 关其首次访问段
                pd = prof.get(prev_floor)
                if pd and pd["_open"]:
                    pd["_open"] = False
            rec(state)
            prev_floor = fl
    final = value_vector(state)
    final["_floor"] = state.current_floor
    final["_won"] = state.won
    return prof, final


# ─── 各层可达最优属性 Pareto（on_admit 累计；含日后被 beam 截掉的——「到达过」即记）─────────

class FloorBest:
    """单层「永久属性+HP」Pareto 非支配集：维 (hp, atk, def, mdef)，越大越优。存动作供裁判重放。"""
    __slots__ = ("pts",)

    def __init__(self):
        self.pts = []   # [(vec4, actions, full_value_vector)]

    def offer(self, vec4, actions, valvec):
        for ev, _, _ in self.pts:
            if all(ev[i] >= vec4[i] for i in range(4)):
                return
        self.pts = [(ev, ea, evv) for ev, ea, evv in self.pts
                    if not all(vec4[i] >= ev[i] for i in range(4))]
        self.pts.append((vec4, actions, valvec))

    def max_by(self, idx):
        return max(self.pts, key=lambda t: t[0][idx]) if self.pts else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beam", type=int, default=50, help="beam 宽度 K（玩家标定 50 起）")
    ap.add_argument("--cap", type=int, default=120000,
                    help="max_states 生成上限（控宽后应远不到；撞到=beam 没压住，需调）")
    ap.add_argument("--goal-floor", default="MT0",
                    help="目标层；默认 MT0（楼梯不可达→纯探索，不喂定向终点）")
    ap.add_argument("--lam", type=float, default=0.0,
                    help="远区势能折扣 λ：0=关(与原版字节一致，零回归基线)；>0=开 B 轻量版"
                         "(近区精确+远区乐观折扣)，让搜索按【上层永久增益对整区总减伤】自评爬升")
    ap.add_argument("--diversity", default="none", choices=["none", "floor", "stairs"],
                    help="beam 分坑保护维：none=单坑(原版，低层刷怪便宜货占满 K 槽挤死 climber)；"
                         "floor=按 current_floor 分坑各保骨架，强制保留爬楼党；"
                         "stairs=按 (层,可达楼梯集) 分坑(推进度签名，同层内够到上行梯 vs 没够到分两坑)")
    ap.add_argument("--score", default="region", choices=["region", "vzone"],
                    help="beam 打分键：region=原区势能/roster（默认，λ 控；λ=0 与原版字节一致=零回归基线）；"
                         "vzone=V_zone=HP−D 替换式打分（前置2 修好的 live boss 梯度，注入 beam_score_fn 旁路 roster）")
    ap.add_argument("--beta", type=float, default=0.0,
                    help="目标导向 pull 引导系数 β（仅 --score vzone 生效，弃 κ 势能形后的新方向，玩家 2026-06-10）："
                         "0=关(beam_rank_score 退回纯 HP−D_free，与 β=0/κ=0 字节零回归，单测硬保证)；"
                         ">0=开(排序键=HP−D_free + β·pull；pull=朝可达高区势能下降攻防道具的引导，拿走离场、够不到门控0；"
                         "只进 beam score_override，绝不进 D/value_vector—— 防 κ=1 反向病，命门单测钉死)。"
                         "β>0 时基分恒用 κ=0（pull 取代 κ，一次只动 β 一个变量）")
    ap.add_argument("--beta-big", type=float, default=0.0,
                    help="【结合】大件 pull 引导系数 β_big（仅 --score region 生效，玩家 2026-06-11）："
                         "0=关(纯 region 区势能基分，与原版字节一致=零回归基线)；"
                         ">0=开(排序键=region 区势能基分(兑现侧) + β_big·pull_大件(引导侧) + β_big·ΔRP₀(大件已拿走))。pull_大件 只对"
                         "【ΔRP 减伤量涌现出的大件】(剑盾,数据自动找缝、不硬编码)给'去拿它'梯度，治剑盾误判；"
                         "拿到即离场→pull 归 0、但满额兑现 G 补 β_big·ΔRP₀(≥守着引导)→结构性拿走≥守着、不复发 κ=1/就近病。只进 beam_score_extra"
                         "排序键，绝不进 D/value_vector(守红线，单测钉死)。一次只动 β_big 一个变量")
    ap.add_argument("--beta-small", type=float, default=0.0,
                    help="【满额兑现】小宝石拿取奖励系数 β_small（仅 --score region 生效，玩家 2026-06-11）："
                         "0=关(小宝石不给引导、纯走 region 兑现侧，零回归)；"
                         ">0=开(小宝石【已拿走·entities==0】才给 β_small·ΔRP₀(g)，【只拿取奖励、无在场 pull】→无平台、无就近病风险)。"
                         "小宝石不在 big_cells、不进 pull_大件；ΔRP₀ 由 detect_big_items 数据涌现。只进 beam_score_extra，"
                         "绝不进 D/value_vector(守红线)。与 β_big 独立、一次只扫一个变量")
    ap.add_argument("--gamma-door", type=float, default=0.0,
                    help="【钥匙价值·门锚定全臂梯度】系数 γ（仅 --score region 生效，玩家 2026-06-12 选项1）："
                         "0=关(无 door_pull，与原版字节零回归基线)；"
                         ">0=开(排序键 += Σ_{门后有未吸价值·够得到} γ·R_未吸(门)/(1+dist_arc))。R(门)=门后专属 pocket 内"
                         "【小宝石 ΔRP₀+血瓶 HP(+win 若 boss 在 pocket)】，排怪 toll(已在 D)/排大件(pull_大件已引导)；"
                         "dist_arc=门乐观 dist 到最近未吸格 + 钥匙腿(门闭且无该色钥→加最近同色钥匙 dist=拿钥匙→开门→吸价值全臂)。"
                         "锚在【开门动作+pocket 未吸】非锚【持有钥匙】→ 不复发 κ=1；只进 beam_score_extra，绝不进 D/value_vector。"
                         "与 β_big/β_small 独立、一次只扫一个变量")
    ap.add_argument("--door-win", action="store_true",
                    help="门后价值是否计入【解锁 boss/通关】巨值（阶段2·长臂红钥过 boss）：默认关(阶段1·短臂，"
                         "纯宝石/血 pocket、干净接 G/HP 崖)；开=include_win，R 含 win=_region_pot(整区待克势能 hp 当量)，验红钥→boss 长臂")
    ap.add_argument("--alpha", type=float, default=1.0,
                    help="【door_pull 距离衰减旋钮 α】door_pull 门后价值的距离折扣 (1+dist_arc)^α（仅 --score region 生效）："
                         "1=关(原 /(1+dist_arc) 线性衰减，字节零回归)；α∈(0,1)=减弱衰减、抬【远门后】引导梯度（治 MT8 门后谷被淹没）。"
                         "注：2026-06-12 拆旋钮——pull_大件 改由独立的 --alpha-big 控（根因：一个 α 背『愿意去远』与『目标价值排序』"
                         "两冲突角色，见 project-alpha-dual-role），本旗 now 仅作用 door_pull")
    ap.add_argument("--alpha-big", type=float, default=1.0,
                    help="【pull_大件 独立距离衰减旋钮 α_big】pull_大件 的距离折扣 (1+dist)^α_big（仅 --score region 生效，玩家 2026-06-12 拆旋钮）："
                         "1=关(原 /(1+dist) 线性衰减，字节零回归)；α_big∈(0,1)=减弱衰减、抬【远处大件】在场引导梯度"
                         "（治剑盾长途被 (1+dist) 压扁致先扫近宝石）。须严格>0（≤0 破满额 G 上界红线/退化无距离区分）。与 door_pull 的 --alpha 解耦；"
                         "满额兑现 G=β·ΔRP₀ 对任意 α_big>0 仍是在场引导上界 → 拿走≥守着、不复发 κ=1/hover（只调引导陡峭度、守红线）")
    ap.add_argument("--no-cut", action="store_true",
                    help="跳过 beam 截断点审计文件 crossbeam_cut_*.jsonl 落盘（纯审计副产物、不影响搜索/打分/floorbest）："
                         "扫参/磁盘紧张时省 I/O 与空间。red-line 审计需要时去掉本旗即恢复。")
    args = ap.parse_args()
    beam_diversity = None if args.diversity == "none" else args.diversity
    goal_cell = (args.goal_floor, 1, 1)
    score_tag = "" if args.score == "region" else f"_{args.score}"
    if args.score == "vzone" and args.beta:
        score_tag += f"_b{args.beta:g}"
    if args.score == "region" and args.beta_big:
        score_tag += f"_bb{args.beta_big:g}"
    if args.score == "region" and args.beta_small:
        score_tag += f"_bs{args.beta_small:g}"
    if args.score == "region" and args.gamma_door:
        score_tag += f"_gd{args.gamma_door:g}" + ("w" if args.door_win else "")
    if args.score == "region" and args.alpha != 1.0:
        score_tag += f"_a{args.alpha:g}"
    if args.score == "region" and args.alpha_big != 1.0:
        score_tag += f"_ab{args.alpha_big:g}"

    # ── V_zone 替换式打分（仅 --score vzone 时注入）：塔特有 zone（含 MT10 boss）在驱动层 extract/ 构建、
    #    闭包持有；solver 只收一个 state→数值 闭包、不 import 任何塔特有模块（塔无关铁律）。score_override 优先于 roster。
    beam_score_fn = None
    beam_score_extra = None     # 【结合】大件 pull 引导（仅 region 路；roster 建好后注入，见下方）
    if args.score == "vzone":
        from vzone import (build_zone as _build_zone_vz, v_zone_score as _v_zone_score,
                           beam_rank_score as _beam_rank_score)
        _vz_zone = _build_zone_vz()
        _beta = args.beta
        _vz_memo = {}                       # id(state)->(state_ref, score)：beam_select 每点多次调 score_fn，
        def beam_score_fn(s):               # 而打分每调一次跑 Dijkstra（pull 再跑一次全图距离）；按对象 memo
            hit = _vz_memo.get(id(s))
            if hit is not None and hit[0] is s:
                return hit[1]
            if _beta:                       # 目标导向：HP−D_free(κ=0) + β·pull（pull 只进此排序键，不碰 D/value_vector）
                v = _beam_rank_score(_vz_zone, s, _beta)
            else:                           # β=0 → 退回纯 HP−D_free（字节零回归基线）；-inf=boss 无路(排最末)
                v = _v_zone_score(_vz_zone, s)[0]
            _vz_memo[id(s)] = (s, v)
            return v

    start, nopen = build_start()
    h = start.hero
    print("=" * 96)
    if args.score == "vzone":
        if args.beta:
            _score_desc = f"V_zone 目标导向=HP−D_free + β·pull(β={args.beta:g})"
        else:
            _score_desc = "V_zone=HP−D_free(纯标量β=0,字节零回归)"
    else:
        _score_desc = f"区势能/roster λ={args.lam}"
    print(f"跨层楼梯缩点 + beam 控宽 自主爬升检验（cross_floor=True，beam K={args.beam}，"
          f"打分={_score_desc}，分坑={args.diversity}，_single_floor_copy=False）")
    print("=" * 96)
    print(f"起点(穿过 {nopen} token 强制开局噩梦后首个自由态): {start.current_floor}"
          f"({h.x},{h.y}) HP={h.hp} ATK={h.atk} DEF={h.def_}")
    print(f"目标={goal_cell}（楼梯不可达→纯探索；不喂 shield 坐标，爬不爬由 V 自评）  "
          f"cap={args.cap:,}")
    print("-" * 96)

    # ── 区势能层（玩家 2026-06-08 裁定补 ΔV：修 R 近视 + 时序性；按「永久增益对【本区到boss·剩余存活怪】总减伤」自评爬升）──
    # roster 一次构建（读全塔静态地图怪 + 门禁结构检测 boss 层，塔无关）；标定打印=「+装备→本区剩余存活怪
    # grind 损血落差」，即盾/剑势能值的【真实数据来源】（守铁律：从塔数据真算，不硬塞「盾优先」权重）。
    roster = build_future_roster(start)
    beam_future = FutureCfg(roster, args.lam) if args.lam else None
    if args.score == "vzone":
        beam_future = None     # V_zone 替换式打分时区势能旁路（score_override 优先）；下方 roster 标定仅作减伤数据参照

    # ── 【结合】大件 pull 引导（仅 --score region + β_big>0）：region 区势能基分(兑现侧) + β_big·pull_大件(引导侧)。
    #    大件由 ΔRP 减伤量【数据涌现】（detect_big_items 找最大乘性缝、不硬编码"剑盾"）；只进 beam_score_extra 排序键，
    #    绝不进 D/value_vector（守红线）。塔特有 zone/大件判据在驱动层闭包，solver 只收 state→数值 不 import。
    if args.score == "region" and (args.beta_big or args.beta_small or args.gamma_door):
        from big_item_pull import detect_big_items, pull_big, build_pickup_bonus, pickup_bonus
        from door_value import build_door_reward, door_pull
        from vzone import build_zone as _build_zone_bb
        _bb_zone = _build_zone_bb()
        _big_cells, _tau, _ranked = detect_big_items(_bb_zone, roster, start)
        _beta_big = args.beta_big
        _beta_small = args.beta_small
        _gamma_door = args.gamma_door
        _alpha = args.alpha                 # door_pull 距离衰减旋钮 (1+dist_arc)^α
        _alpha_big = args.alpha_big         # pull_大件【独立】距离衰减旋钮 (1+dist)^α_big（2026-06-12 拆旋钮、与 door_pull 解耦）
        # 满额兑现拿取奖励表（ΔRP₀ 参照态固定常数·数据涌现）：大件→β_big·ΔRP₀、小宝石→β_small·ΔRP₀（拿走才兑现）。
        _bonus_table = build_pickup_bonus(_ranked, _big_cells, _beta_big, _beta_small)
        # 门后价值表（仅 γ>0 才建）：门锚定全臂梯度 door_pull 的奖励源 R(门)。塔无关：门/钥匙/boss 门禁结构读出。
        _door_reward = (build_door_reward(_bb_zone, roster, start, _big_cells, _ranked,
                                          include_win=args.door_win) if _gamma_door else {})
        print(f"【结合】大件涌现（ΔRP 最大乘性缝，不硬编码）：τ={_tau:,.0f}  大件 {len(_big_cells)} 件  "
              f"β_big={_beta_big:g} β_small={_beta_small:g}  拿取奖励表 {len(_bonus_table)} 格：")
        for drp, cell, da, dd in _ranked:
            mark = "★大件" if cell in _big_cells else "  小宝石"
            g = _bonus_table.get(cell)
            gtag = f"  G拿取={g:,.0f}" if g else ""
            print(f"    {mark} {cell[0]}({cell[1]},{cell[2]}) +atk{da}/+def{dd}  ΔRP={drp:,.0f}{gtag}")
        if _gamma_door:
            print(f"【钥匙价值】门锚定全臂梯度 γ={_gamma_door:g}  include_win={args.door_win}  "
                  f"门后有可兑现价值的门 {len(_door_reward)} 扇（R 降序）：")
            for dcell, info in sorted(_door_reward.items(), key=lambda kv: -kv[1]["R"]):
                wtag = f"  win={info['win']:,.0f}" if info["win"] else ""
                print(f"    门{dcell[0]}({dcell[1]},{dcell[2]}) {info['color']:<9} R={info['R']:>12,.0f}  "
                      f"pocket={len(info['pocket']):>3} 宝石{len(info['gems'])} 血{len(info['blood'])}{wtag}")
        _bb_memo = {}                       # id(state)->(state_ref, extra)：beam_select 每点多次调 score_fn，
        def beam_score_extra(s):            # pull_big/door_pull 每调跑全图 Dijkstra；按对象 memo（拿光大件后早退近零成本）
            hit = _bb_memo.get(id(s))
            if hit is not None and hit[0] is s:
                return hit[1]
            # 引导侧 = β_big·pull_大件(在场折扣引导·α_big 独立衰减) + G(满额兑现拿取奖励) + γ·door_pull(门后价值·α 衰减)。
            v = _beta_big * pull_big(_bb_zone, roster, s, _big_cells, _alpha_big) if _beta_big else 0.0
            v += pickup_bonus(s, _bonus_table)
            if _gamma_door:                 # γ=0 → 跳过 → 与 β_big/β_small 路字节零回归
                v += door_pull(_bb_zone, s, _door_reward, _gamma_door, _alpha)
            _bb_memo[id(s)] = (s, v)
            return v

    def far(datk=0, ddef=0):
        s2 = _copy_state(start)
        s2.hero.atk += datk
        s2.hero.def_ += ddef
        return int(_future_potential(s2, FutureCfg(roster, 1.0)))

    base_far = far()
    nf = len(roster["by_floor"])
    cur_i = roster["idx_of"].get(start.current_floor)
    fids = roster["floor_ids"]
    boss_fids = [fids[b] for b in roster["boss_idxs"]]
    print(f"区边界(boss 层)检测（门禁结构塔无关读出，floor_graph §4）：{boss_fids}（共 {len(boss_fids)} 个）")
    if cur_i is not None:
        lo, hi = _region_bounds(roster, cur_i)
        hi_tag = fids[hi] + ("=boss" if hi in roster["boss_idxs"] else "=塔顶(本区无 boss 界)")
        reg_floors = [fids[i] for i in range(lo, hi + 1)
                      if i != cur_i and i in roster["mon_cells"]]
        print(f"当前区跨度（{start.current_floor} 所在区→boss）：[{fids[lo]} .. {hi_tag}]，"
              f"区内非当前层有怪 {len(reg_floors)} 层 {reg_floors}")
    print(f"区势能标定（λ={args.lam}）：Σ_区 toll(λ=1, 本区到boss·剩余存活怪 grind 损血)={base_far:,}"
          f"（全塔 {nf} 层有怪）")
    print(f"  假想加装→本区剩余存活怪 grind 损血落差（=该永久增益对本区的累计减伤，数据真算）：")
    # 标注真实出处：一区楼梯可达的只有 +10 铁剑/铁盾；+100 神圣剑盾在 MT44 飞行层(楼梯够不到)。
    for tag, da, dd in (("+10DEF(铁盾@MT9楼梯)", 0, 10), ("+30DEF", 0, 30),
                        ("+100DEF(神圣盾@MT44飞行)", 0, 100),
                        ("+10ATK(铁剑@MT5楼梯)", 10, 0), ("+100ATK(神圣剑@MT44飞行)", 100, 0)):
        f2 = far(da, dd)
        print(f"    {tag:>12}: Σ_区={f2:>14,}  落差={base_far - f2:>14,}  "
              f"(本地 λ 项={args.lam * (base_far - f2):>12,.0f})")
    print("-" * 96)

    # on_admit：累计各层可达最优属性；beam_cut_sink：流式落盘被截点（审计）
    per_floor = defaultdict(FloorBest)
    first_wave_reach = {}

    def on_admit(stt, actions):
        hh = stt.hero
        per_floor[stt.current_floor].offer((hh.hp, hh.atk, hh.def_, hh.mdef),
                                           actions, value_vector(stt))
        first_wave_reach.setdefault(stt.current_floor, len(actions))

    cut_path = OUT / f"crossbeam_cut_K{args.beam}{score_tag}_lam{args.lam}_{args.diversity}.jsonl"
    n_cut_written = [0]
    if args.no_cut:
        fh = None

        def sink(records):
            for _ in records:                  # 仍消费迭代器、只计数不落盘（审计被 --no-cut 关）
                n_cut_written[0] += 1
    else:
        fh = cut_path.open("w", encoding="utf-8")

        def sink(records):
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                n_cut_written[0] += 1

    t0 = time.perf_counter()
    res = search_quotient(start, goal_cell, step, max_states=args.cap, cross_floor=True,
                          beam_k=args.beam, beam_cut_sink=sink, on_admit=on_admit,
                          beam_future=beam_future, beam_diversity=beam_diversity,
                          beam_score_fn=beam_score_fn, beam_score_extra=beam_score_extra)
    dt = time.perf_counter() - t0
    if fh is not None:
        fh.close()

    floors_seen = getattr(res, "floors_seen", [])
    fpf = getattr(res, "fp_by_floor", {})
    print(f"耗时={dt:.1f}s  hit_cap={res.hit_cap}  展开={res.states_expanded:,}  "
          f"生成={res.states_generated:,}  入队={res.states_admitted:,}  "
          f"指纹={res.distinct_fingerprints:,}  wave 数={res.n_waves}")
    print(f"beam 累计截断={res.beam_cut_total:,}（落盘 {n_cut_written[0]:,} 行 → {cut_path.name}）  "
          f"截断 wave 数={res.beam_waves_truncated}  保护让位 wave={res.beam_overflow_waves}")
    print(f"到达层数={len(floors_seen)}  到达层={sorted(floors_seen, key=_fidx)}")
    icpt = getattr(res, "intercept_locs", [])
    if icpt:
        print(f"拦截(choices)事件格={icpt}（商人/祭坛/老人，块图记录不强解）")

    # ── 膨胀曲线（控宽后宽度）：wave (入宽, 原始出宽, 截后出宽) ──
    print("-" * 96)
    print("膨胀曲线（每 wave：入宽=本层待展开；原始出宽=去重后 admitted；截后出宽=beam 留存≤K）")
    wl = getattr(res, "wave_log", [])
    print(f"{'wave':>4} {'入宽':>7} {'原始出宽':>9} {'截后出宽':>9}  {'(原始/截后 比)':>12}")
    for i, (win, raw, kept) in enumerate(wl):
        ratio = f"{raw / kept:.1f}×" if kept else "—"
        bar = "█" * min(48, kept * 48 // max(1, args.beam))
        print(f"{i:>4} {win:>7,} {raw:>9,} {kept:>9,}  {ratio:>12}  {bar}")
    if wl:
        print(f"  原始出宽峰={max(r for _, r, _ in wl):,}（无 beam 时该 wave 要全展开）  "
              f"截后恒≤K={args.beam}")

    # ── route 下界对照 ──
    prof, rfinal = route_profile()
    print("-" * 96)
    print(f"route 通关末态（下界，仅对照不喂走法）: {rfinal['_floor']} won={rfinal['_won']}  "
          f"HP={rfinal['hp']} ATK={rfinal['atk']} DEF={rfinal['def']} "
          f"gold={rfinal['gold']} kill={rfinal['kill']}")

    # ── 各层可达最优属性（搜索自主到达）vs route 该层轨迹 ──
    print("-" * 96)
    print("各层【搜索可达最优属性】(on_admit 累计，含被 beam 截点) vs route【首次通过】(同期基准)：")
    print("  注：基准=route 首次离开该层属性（同期）；『全程峰』含大后期回访(77–98%进度)，非同期、仅展示。")
    print(f"{'层':>5} {'指纹':>6} {'搜索maxHP':>9} {'搜索maxATK':>10} {'搜索maxDEF':>10}   "
          f"{'route首过出(hp/atk/def)':>22} {'全程峰(后期回访)':>18}")
    for fid in sorted(per_floor, key=_fidx):
        fb = per_floor[fid]
        mh = fb.max_by(0)[0][0]
        ma = fb.max_by(1)[0][1]
        md = fb.max_by(2)[0][2]
        rp = prof.get(fid)
        if rp:
            fx = rp["first_exit"]
            rexit = f"{fx[0]}/{fx[1]}/{fx[2]}"
            rpeak = f"{rp['max_hp']}/{rp['max_atk']}/{rp['max_def']}"
        else:
            rexit, rpeak = "—(未访)", "—"
        flag = ""
        if rp and (ma > rp["first_exit"][1] or md > rp["first_exit"][2]):
            flag = "  ★攻或防超route首过(同期)"
        print(f"{fid:>5} {fpf.get(fid, 0):>6,} {mh:>9} {ma:>10} {md:>10}   "
              f"{rexit:>22} {rpeak:>18}{flag}")

    # ── 永久增益【自主发现】信号 + 降维打击(realized)：全局最高 DEF / ATK 态，其属性带回起点参照算
    #    「本区(到boss)剩余存活怪 grind 损血」vs 起点 → 隔离楼层位置、只看永久属性把本区损血压了多少（盾真值实测）──
    print("-" * 96)
    print("永久增益【自主发现】信号（全局最高 DEF / ATK 态）+ 降维打击(realized，属性带回起点参照算本区减伤)：")
    top_floor = max(per_floor, key=_fidx) if per_floor else None
    print(f"  最高到达层={top_floor}（MT9=铁盾层 shield1=+10DEF，楼梯可达；+100神圣盾在MT44飞行层够不到）")
    gmax = {}
    for fid, fb in per_floor.items():
        for idx, name in ((2, "最高DEF"), (1, "最高ATK")):
            b = fb.max_by(idx)
            if b and (name not in gmax or b[0][idx] > gmax[name][1][0][idx]):
                gmax[name] = (fid, b)
    for name in ("最高DEF", "最高ATK"):
        if name not in gmax:
            continue
        fid, (vec4, actions, valvec) = gmax[name]
        s2 = _copy_state(start)
        s2.hero.atk, s2.hero.def_, s2.hero.mdef = vec4[1], vec4[2], vec4[3]
        realized = int(_future_potential(s2, FutureCfg(roster, 1.0)))
        print(f"  {name}: {fid} HP={vec4[0]} ATK={vec4[1]} DEF={vec4[2]} mdef={vec4[3]} "
              f"({len(actions)}步)  该属性下本区 Σ_区={realized:,}  vs 起点 {base_far:,}  "
              f"↓{base_far - realized:,}")

    # ── 全局最优攻/防候选 → 引擎独立重放裁判（证明楼梯线路可照走）──
    print("-" * 96)
    print("全局最优攻 / 防 / 血 候选 → 封板引擎独立重放裁判（跨层线路可直接照走？）：")
    cand = {}
    for fid, fb in per_floor.items():
        for idx, name in ((1, "maxATK"), (2, "maxDEF"), (0, "maxHP")):
            best = fb.max_by(idx)
            if best is None:
                continue
            key = name
            cur = cand.get(key)
            if cur is None or best[0][idx] > cur[1][0][idx]:
                cand[key] = (fid, best)
    for name in ("maxATK", "maxDEF", "maxHP"):
        if name not in cand:
            continue
        fid, (vec4, actions, valvec) = cand[name]
        rep = replay(start, list(actions), step, _copy_state)
        ok = (rep.current_floor == fid and rep.hero.hp == vec4[0]
              and rep.hero.atk == vec4[1] and rep.hero.def_ == vec4[2])
        print(f"  {name}: {fid}  HP={vec4[0]} ATK={vec4[1]} DEF={vec4[2]} "
              f"({len(actions)}步) → "
              + ("✅一致" if ok else f"⚠不一致(重放={rep.current_floor} HP={rep.hero.hp} "
                                     f"ATK={rep.hero.atk} DEF={rep.hero.def_})"))

    # ── ③ Φ_key 信号：各层可达态钥匙留存（κ=0 易"血高钥匙空"；κ>0 应保住到本区 boss 路上要的钥匙）──
    print("-" * 96)
    print("③ 钥匙留存（各层 Pareto 前沿：maxHP 态的钥匙 / 前沿内最大总钥匙数）——看 κ 有没有让搜索留住钥匙：")

    def _keys_of(vv):
        return {k[4:]: v for k, v in vv.items() if k.startswith("key:") and v}

    def _nkeys(vv):
        return sum(v for k, v in vv.items() if k.startswith("key:"))

    print(f"{'层':>5} {'前沿点':>6} {'maxHP态(hp/钥匙)':>36} {'前沿最大总钥匙':>14}")
    for fid in sorted(per_floor, key=_fidx):
        fb = per_floor[fid]
        mh = fb.max_by(0)
        mh_str = f"{mh[0][0]}/{_keys_of(mh[2])}" if mh else "—"
        max_nk = max((_nkeys(vv) for _, _, vv in fb.pts), default=0)
        print(f"{fid:>5} {len(fb.pts):>6} {mh_str:>36} {max_nk:>14}")

    # ── 是否搜出【严格支配 route 末态】的态（HP/ATK/DEF 全≥且≥1 严格）──
    print("-" * 96)
    dominators = []
    for fid, fb in per_floor.items():
        for vec4, actions, valvec in fb.pts:
            hp, atk, df, _ = vec4
            if (hp >= rfinal["hp"] and atk >= rfinal["atk"] and df >= rfinal["def"]
                    and (hp > rfinal["hp"] or atk > rfinal["atk"] or df > rfinal["def"])):
                dominators.append((fid, vec4, actions, valvec))
    if dominators:
        print(f"★找到 {len(dominators)} 个【在 HP/ATK/DEF 上严格支配 route 末态】的搜索态"
              f"（注：route 已通关、这些是中途态，仅作属性优势信号，全程通关价值需玩家终审）：")
        for fid, vec4, actions, valvec in sorted(dominators, key=lambda t: -t[1][0])[:5]:
            print(f"    {fid} HP={vec4[0]} ATK={vec4[1]} DEF={vec4[2]} ({len(actions)}步)")
        dom_path = OUT / f"crossbeam_dominators_K{args.beam}{score_tag}_lam{args.lam}_{args.diversity}.jsonl"
        with dom_path.open("w", encoding="utf-8") as dfh:
            for fid, vec4, actions, valvec in dominators:
                dfh.write(json.dumps({"floor": fid, "hp": vec4[0], "atk": vec4[1],
                                      "def": vec4[2], "mdef": vec4[3], "keys": _keys_of(valvec),
                                      "n_steps": len(actions),
                                      "actions": list(actions)}, ensure_ascii=False) + "\n")
        print(f"  完整动作序列已落盘 → {dom_path.name}（玩家真实游戏终审重放，未喂盾坐标=真自主发现）")
    else:
        print("未发现严格支配 route 末态的中途态（route 末态=通关全程积累，中途态本就难支配；"
              "核心看上面『攻/防超 route 峰』的 ★ 行=是否自主爬升拿到永久属性优势）。")

    # ── 各层【可达最优属性 Pareto】完整落盘（on_admit 累计的 best-reached，含 beam 留存的好态）──
    # cut 文件只含【被 beam 截掉的 worse 点】，K 大时某层（如 MT10）可能 0 条 → 不可作"最优到达"源。
    # per_floor 是 on_admit 记的真·可达最优 Pareto(hp/atk/def/mdef)，是下游取 best-MT10 的正确源。
    # 纯附加产物，不改搜索/打分；行 schema 与 cut 对齐(floor/hp/atk/def/mdef/value/actions)，复用 load_rows。
    floorbest_path = OUT / f"crossbeam_floorbest_K{args.beam}{score_tag}_lam{args.lam}_{args.diversity}.jsonl"
    n_fb = 0
    with floorbest_path.open("w", encoding="utf-8") as ffh:
        for fid in sorted(per_floor, key=_fidx):
            for vec4, actions, valvec in per_floor[fid].pts:
                ffh.write(json.dumps({"floor": fid, "hp": vec4[0], "atk": vec4[1],
                                      "def": vec4[2], "mdef": vec4[3], "value": valvec,
                                      "n_steps": len(actions),
                                      "actions": list(actions)}, ensure_ascii=False) + "\n")
                n_fb += 1
    print(f"各层最优 Pareto 完整落盘 → {floorbest_path.name}（{n_fb:,} 条，供下游取 best-MT10；"
          f"区别于只含截点的 cut 文件）")

    print("=" * 96)


if __name__ == "__main__":
    main()
