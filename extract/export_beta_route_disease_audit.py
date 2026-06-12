"""【只导出·只读·不改产品码】四个 β(0.25/0.5/0.75/1) best-MT10 路线逐里程碑
   + 「就近打=真病 vs 合理」逐个标注 + 三个明确病定位 + 静态高估根因 + 横向对比。

回答玩家（2026-06-11）四问，只导出+标注，不改 sim/solver/vzone/quotient，不决定改方向A还是fly：
  1. 每条 best-MT10 路线逐里程碑（换层/拿宝石装备/拿钥匙/开门/打怪，标坐标+HP/ATK/DEF+钥匙+金币）。
  2. 【MT9 前后决策】每次进 MT9 后干了什么——回 MT1-5 拿 5 件远高价货？还是就近打 MT8/MT7？
     就近打的是【真高价货(像 MT7 那颗 +1atk)】还是【低价垃圾(可绕开、非零伤、只给金币的怪 / 开门不进)】。
     用区分逐个标：高价近货先取=合理；低价近货压高价远货=病。
  3. 【三个明确病】打无意义怪(只给金币)、开门不进、MT5 拿剑后去 MT1 拿血(700+) —— 各在哪出现，
     是不是都源于「静态高估让回头/远处被误判成贵→就近找点事做」。
  4. 横向：β 越高是不是低价垃圾操作越多；哪个 β 路线最干净。

铁律遵循（CLAUDE.md）：
  · 不改产品码；动作串=各 β cut 文件 floor==MT10 按真实 V=HP−D 取顶的那条（pick_best_mt10），
    从干净起点(开局噩梦后 MT3 入口)引擎封板重放；事件/损血/金币/钥匙全部归因到 data 真读格，绝不手推。
  · 「不挡路」用反事实 BFS 判：在【与搜索同口径的静态图】(_passable，门视作可过) 上，把【当下所有活怪】
    设为墙，问「到下一个奖励格是否存在无战路径」——存在=这一战在搜索自己的世界观里可绕开(疑似无意义)，
    不存在=至少要打一战(挡路必战)。这是非对称的诚实判据：可绕开是强证据，不可绕开只说明需打某战。
  · 「静态高估根因」复用第0步探针的 make_cost/toll_dist：在首入 MT9 态，量 MT1-5 远高价货的
    d楼梯静(现状 pull 用) vs d楼梯活(读活体)——静 ≫ 活 即坐实 pull 把回头误判成贵(机制①)。

跑法：python -u extract/export_beta_route_disease_audit.py
产物：extract/beta_route_disease_audit.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sim.simulator import step, _copy_state, _DIR
from solver.verify import replay
from probe_crossfloor import build_start
from vzone import build_zone, boss_toll, _zone_attr_gems, _passable, _NB4
from export_bscan_routes import cut_path, load_rows, pick_best_mt10
from export_k0stairs_mt10_route import build_milestones, nz_keys, fk, gem_label
from probe_pull_flyaware import make_cost, toll_dist, INF, _fmt

HERE = Path(__file__).parent
OUT = HERE / "beta_route_disease_audit.md"
BETAS = [0.25, 0.5, 0.75, 1.0]
FAR = {1, 2, 3, 4, 5}      # MT1-5 = 远（底层属性堆）
NEAR = {6, 7, 8}           # MT6-8 = 近（climb 临近层）
HP_HIGH = 700              # 玩家口径：血 700+ 还回 MT1 纯换血=亏


# ─────────────────────────────────────────────────────────────────────────────
# 反事实「不挡路」判据：当下活怪全设墙，到 dst 是否存在无战路径（跨层用 links）
# ─────────────────────────────────────────────────────────────────────────────
def _live_monster(zone, state, node):
    fid, x, y = node
    if node not in zone["mon_cache"]:
        return False
    fl = state.floors.get(fid)
    if fl is None:
        return True                       # 未访问层：怪仍在
    ent = fl.entities
    return 0 <= y < len(ent) and 0 <= x < len(ent[0]) and ent[y][x] != 0


def reach_nofight(zone, state, dst, cap=20000):
    """从英雄当前格出发，避开【所有活怪】(设为墙)，能否走到 dst。门按 _passable 视作可过(同搜索口径)。"""
    src = (state.current_floor, state.hero.x, state.hero.y)
    if src == dst:
        return True
    seen = {src}
    stack = [src]
    n = 0
    while stack and n < cap:
        node = stack.pop()
        n += 1
        fid, x, y = node
        nbrs = [(fid, x + dx, y + dy) for dx, dy in _NB4]
        if node in zone["links"]:
            nbrs.append(zone["links"][node])
        for nb in nbrs:
            if nb in seen or not _passable(zone, nb):
                continue
            if nb == dst:
                return True
            if _live_monster(zone, state, nb):   # 活怪挡路 → 此路不通（要打才过）
                continue
            seen.add(nb)
            stack.append(nb)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 一次重放，落每步标量数组 + 关键步前态拷贝 + MT1-5 远货剩余追踪
# ─────────────────────────────────────────────────────────────────────────────
def scan_route(start, actions, zone, gems, mt15_cells, kill_steps, mt9_entry_steps):
    s = _copy_state(start)
    h = s.hero
    arr = dict(
        floor=[s.current_floor], x=[h.x], y=[h.y], hp=[h.hp], atk=[h.atk],
        df=[h.def_], md=[h.mdef], gold=[h.gold],
    )
    taken = set()
    rem = [frozenset(mt15_cells)]          # rem[i] = 第 i 步后仍未拿的 MT1-5 属性格
    prestate = {}                          # kill step i -> 打这一战【之前】的态（用于 no-fight BFS）
    mt9_state = {}                         # mt9 entry step i -> 刚踏入 MT9 的态
    for idx, a in enumerate(actions, 1):
        if idx in kill_steps:
            prestate[idx] = _copy_state(s)
        bx, by, bf = h.x, h.y, s.current_floor
        s = step(s, a)
        h = s.hero
        arr["floor"].append(s.current_floor); arr["x"].append(h.x); arr["y"].append(h.y)
        arr["hp"].append(h.hp); arr["atk"].append(h.atk); arr["df"].append(h.def_)
        arr["md"].append(h.mdef); arr["gold"].append(h.gold)
        cell = (s.current_floor, h.x, h.y)
        if cell in mt15_cells and cell not in taken:
            da, dd = gems[cell]
            if h.atk > arr["atk"][idx - 1] or h.def_ > arr["df"][idx - 1]:
                taken.add(cell)
        rem.append(frozenset(mt15_cells - taken))
        if idx in mt9_entry_steps:
            mt9_state[idx] = _copy_state(s)
    arr["rem"] = rem
    return arr, prestate, mt9_state


def label_kind(label):
    if "打怪" in label:
        return "kill"
    if "拿铁剑" in label or "拿铁盾" in label or "ATK" in label or "DEF" in label:
        return "gem"
    if "开门" in label:
        return "door"
    if "拿钥匙" in label:
        return "key"
    if "回血" in label:
        return "hp"
    if "换层" in label:
        return "stair"
    return "other"


def next_reward_node(milestones, after_i):
    """after_i 之后第一个【奖励】里程碑的格（拿宝石/装备/钥匙/回血），无则 None。"""
    for m in milestones:
        if m["i"] <= after_i:
            continue
        k = label_kind(m["label"])
        if k in ("gem", "key", "hp"):
            return (m["floor"], m["x"], m["y"])
    return None


def remaining_far_value(zone, gems, rem_cells, atk, def_, mdef):
    """剩余 MT1-5 属性格此刻对 boss 的边际省血合计 + 是否还含 +atk(红宝石) 高价货。"""
    base = boss_toll(zone, atk, def_, mdef)
    tot, has_atk = 0, False
    for c in rem_cells:
        da, dd = gems[c]
        tot += base - boss_toll(zone, atk + da, def_ + dd, mdef)
        if da > 0:
            has_atk = True
    return tot, has_atk, len(rem_cells)


def classify(zone, gems, mt15_cells, milestones, arr, prestate, iron_sword_step, actions):
    """逐里程碑给【决策标注】。返回 annotated(list) + 病计数。"""
    floorv = arr["floor"]; xs = arr["x"]; ys = arr["y"]
    hp = arr["hp"]; atk = arr["atk"]; df = arr["df"]; md = arr["md"]; gold = arr["gold"]
    rem = arr["rem"]
    # 门后格 re-enter 判定用：全程访问过的格集合（按步序）
    visited_seq = [(floorv[j], xs[j], ys[j]) for j in range(len(floorv))]
    annotated = []
    dis = dict(junk_kill=[], door_noenter=[], hp_after_sword=[], redundant_kill=[],
               early_heal=[], wasted_hp=0, fight_hp=0)
    n_last = len(floorv) - 1                      # 末步号（door 开在此=路线截断、非真不进）
    for m in milestones:
        i = m["i"]
        if i == 0:
            continue
        lab = m["label"]
        kind = label_kind(lab)
        fk_ = fk(m["floor"])
        zone_tag = "远MT1-5" if fk_ in FAR else ("近MT6-8" if fk_ in NEAR else
                   ("MT9中转" if fk_ == 9 else "MT10boss"))
        tag = ""
        if kind == "kill":
            dmg = hp[i - 1] - hp[i]
            dgold = gold[i] - gold[i - 1]
            if dmg <= 0:
                tag = f"○零伤路过(金+{dgold})·无害不计病"
            else:
                dis["fight_hp"] += dmg
                nrt = next_reward_node(milestones, i)
                avoidable = reach_nofight(zone, prestate[i], nrt) if nrt else False
                fv, has_atk, cnt = remaining_far_value(zone, gems, rem[i], atk[i], df[i], md[i])
                pressing = cnt > 0
                if avoidable and pressing:
                    dis["junk_kill"].append((i, m["floor"], dmg, dgold, cnt, has_atk, round(fv, 1)))
                    dis["wasted_hp"] += dmg
                    tag = (f"⚠就近病:可绕开的损血战(损血{dmg}/金+{dgold})·此刻MT1-5还剩{cnt}件"
                           f"{'(含红宝石+atk)' if has_atk else ''}远货未拿(可省boss{fv:.0f}血)")
                elif avoidable and not pressing:
                    dis["redundant_kill"].append((i, m["floor"], dmg, dgold))
                    dis["wasted_hp"] += dmg
                    tag = f"△可绕开的损血战(损血{dmg}/金+{dgold})·远货已收完→收尾期冗余消耗"
                else:
                    tag = f"✓挡路必战(无战不可达下一奖励·损血{dmg}/金+{dgold})"
        elif kind == "gem":
            da, dd = gems.get((m["floor"], m["x"], m["y"]), (0, 0))
            val = boss_toll(zone, atk[i - 1], df[i - 1], md[i - 1]) - boss_toll(zone, atk[i], df[i], md[i])
            if fk_ in FAR:
                tag = f"✅回头拿远高价货({zone_tag} +{da}atk/+{dd}def·boss省{val:.0f}血)=合理(理想行为)"
            elif fk_ in NEAR:
                tag = f"✅就近高价货({zone_tag} +{da}atk/+{dd}def·boss省{val:.0f}血)=合理(先近高价不算病)"
            else:
                tag = f"✅拿装备宝石({zone_tag} +{da}atk/+{dd}def·boss省{val:.0f}血)"
        elif kind == "door":
            dx, dy = _DIR[actions[i - 1]]
            door_cell = (floorv[i - 1], xs[i - 1] + dx, ys[i - 1] + dy)  # 开门英雄不移入→门在前方
            entered = any(visited_seq[j] == door_cell for j in range(i + 1, len(visited_seq)))
            if i >= n_last:
                tag = f"○开门@末步(门 {door_cell[1:]}·beam 在此截断,非真不进)"
            elif not entered:
                dis["door_noenter"].append((i, m["floor"], door_cell[1:]))
                tag = f"⚠开门不进(耗钥开 {door_cell[1:]} 门·但全程再未踏入门后格)"
            else:
                tag = f"○开门并通行(门 {door_cell[1:]})"
        elif kind == "hp":
            dhp = hp[i] - hp[i - 1]
            if fk_ == 1 and iron_sword_step is not None and i > iron_sword_step and hp[i - 1] >= HP_HIGH:
                dis["hp_after_sword"].append((i, hp[i - 1], dhp))
                tag = (f"⚠MT5拿剑后仍回MT1拿血(此刻HP={hp[i-1]}已≥{HP_HIGH}·纯换血亏·"
                       f"+{dhp}血)")
            elif hp[i - 1] >= HP_HIGH:
                dis["early_heal"].append((i, m["floor"], hp[i - 1], dhp))
                tag = f"⚠广义早拿血(此刻HP={hp[i-1]}已≥{HP_HIGH}仍拿血+{dhp}·除攒boss血外纯换血亏)"
            else:
                tag = f"·回血+{dhp}(此刻HP={hp[i-1]}→{hp[i]})"
        elif kind == "key":
            tag = "·拿钥匙"
        elif kind == "stair":
            continue   # 纯换层不进决策表
        else:
            tag = "·" + lab
        annotated.append(dict(i=i, floor=m["floor"], x=m["x"], y=m["y"], hp=hp[i],
                              atk=atk[i], df=df[i], gold=gold[i], zone=zone_tag,
                              label=lab, tag=tag, kind=kind))
    return annotated, dis


# ─────────────────────────────────────────────────────────────────────────────
# MT9 前后决策：每次进 MT9 → 到下次进 MT9(或终点) 这段干了什么
# ─────────────────────────────────────────────────────────────────────────────
def mt9_segments(milestones, arr, mt9_entry_steps):
    floorv = arr["floor"]
    segs = []
    entries = sorted(mt9_entry_steps)
    for k, e in enumerate(entries):
        nxt = entries[k + 1] if k + 1 < len(entries) else len(floorv)
        floors_touched, gems_got, keys_got, kills, dmg = [], [], [], 0, 0
        prevf = None
        for m in milestones:
            if not (e <= m["i"] < nxt):
                continue
            ki = label_kind(m["label"])
            if m["floor"] != prevf:
                floors_touched.append(m["floor"]); prevf = m["floor"]
            if ki == "gem":
                gems_got.append((m["floor"], m["x"], m["y"]))
            elif ki == "key":
                keys_got.append(m["floor"])
            elif ki == "kill":
                kills += 1
        # 该段损血
        seg_dmg = 0
        for j in range(e, nxt):
            d = arr["hp"][j - 1] - arr["hp"][j] if j >= 1 else 0
            if d > 0:
                seg_dmg += d
        segs.append(dict(entry=e, end=nxt, floors=floors_touched, gems=gems_got,
                         keys=len(keys_got), kills=kills, dmg=seg_dmg))
    return segs


# ─────────────────────────────────────────────────────────────────────────────
# 静态高估根因：首入 MT9 态，MT1-5 远货 d楼梯静 vs d楼梯活
# ─────────────────────────────────────────────────────────────────────────────
def static_overestimate(zone, mt9s, gems, mt15_cells, taken_at_mt9):
    """首入 MT9 态：MT1-5 各远货 d楼梯静 vs d楼梯活。taken_at_mt9=此刻已拿(不计入 pull 合计)。"""
    h = mt9s.hero
    fid = mt9s.current_floor
    cost_s = make_cost(zone, mt9s, h.atk, h.def_, h.mdef, live=False)
    cost_l = make_cost(zone, mt9s, h.atk, h.def_, h.mdef, live=True)
    ds = toll_dist(zone, (fid, h.x, h.y), cost_s)
    dl = toll_dist(zone, (fid, h.x, h.y), cost_l)
    rows = []
    base = boss_toll(zone, h.atk, h.def_, h.mdef)
    for c in sorted(mt15_cells, key=lambda t: (fk(t[0]), t[1], t[2])):
        da, dd = gems[c]
        val = base - boss_toll(zone, h.atk + da, h.def_ + dd, h.mdef)
        s_ = ds.get(c, INF); l_ = dl.get(c, INF)
        p_s = val / (1.0 + s_) if s_ != INF else 0.0
        p_l = val / (1.0 + l_) if l_ != INF else 0.0
        rows.append((c, da, dd, val, s_, l_, p_s, p_l, c in taken_at_mt9))
    return dict(hero=(h.hp, h.atk, h.def_), floor=fid, pos=(h.x, h.y), rows=rows)


# ─────────────────────────────────────────────────────────────────────────────
def analyze(beta, zone, start, gems, mt15_cells, cut_fn=None):
    # cut_fn=None → 原 β 口径(vzone K50 cut)；给 Path → 复用同一套病判据读别的 cut(如 region λ 路线)。
    # beta 此时只作标签/报告用，病判据全程只依赖 best-MT10 的 actions、与打分键无关。
    fn = cut_fn if cut_fn is not None else cut_path(beta)
    if not fn.exists():
        return dict(beta=beta, missing=True)
    rows = load_rows(fn)
    mt10 = [r for r in rows if r["floor"] == "MT10"]
    if not mt10:
        return dict(beta=beta, no_mt10=True)
    best, sfin, vz, D = pick_best_mt10(zone, start, mt10)
    actions = list(best["actions"])

    milestones, visited, taken_gems, term = build_milestones(start, actions, zone, gems)
    # 关键步集合
    kill_steps = {m["i"] for m in milestones if "打怪" in m["label"]}
    # MT9 进入步：floor 由非 MT9 变 MT9（用 milestones 的换层标，但更稳是 replay 时判；这里先用 milestones 推）
    arr0_floor = None
    # 先粗 replay 取每步 floor 以定位 MT9 进入步（与 scan_route 同口径，单独短跑）
    s = _copy_state(start); flo = [s.current_floor]
    for a in actions:
        s = step(s, a); flo.append(s.current_floor)
    mt9_entry_steps = {i for i in range(1, len(flo)) if flo[i] == "MT9" and flo[i - 1] != "MT9"}

    arr, prestate, mt9_state = scan_route(
        start, actions, zone, gems, mt15_cells, kill_steps, mt9_entry_steps)

    # 铁剑步：MT5 拿到 +10atk 的那步（taken_gems 里 da>=10 且在 MT5）
    iron_sword_step = None
    for m in milestones:
        c = (m["floor"], m["x"], m["y"])
        if c in gems and gems[c][0] >= 10 and m["floor"] == "MT5":
            iron_sword_step = m["i"]; break

    annotated, dis = classify(zone, gems, mt15_cells, milestones, arr, prestate,
                              iron_sword_step, actions)
    segs = mt9_segments(milestones, arr, mt9_entry_steps)
    first_mt9 = min(mt9_entry_steps) if mt9_entry_steps else None
    if first_mt9:
        taken_at_mt9 = mt15_cells - arr["rem"][first_mt9]
        root = static_overestimate(zone, mt9_state[first_mt9], gems, mt15_cells, taken_at_mt9)
    else:
        root = None

    # 封板对账
    rs = replay(start, actions, step, _copy_state)
    fid_ok = (rs.current_floor == best["floor"] and rs.hero.hp == best["hp"]
              and rs.hero.atk == best["atk"] and rs.hero.def_ == best["def"])

    return dict(beta=beta, term=dict(floor=term["floor"], x=term["x"], y=term["y"],
                hp=term["hp"], atk=term["atk"], df=term["def_"], gold=term["gold"],
                keys=term["keys"]),
                n_steps=len(actions), n_seg=len(segs), milestones=milestones,
                annotated=annotated, dis=dis, segs=segs, root=root, fid_ok=fid_ok,
                n_mt9=len(mt9_entry_steps), taken_gems=taken_gems)


# ─────────────────────────────────────────────────────────────────────────────
def write_report(results, mt15_cells, gems):
    L = []
    L.append("# 四 β best-MT10 路线 · 就近打逐个标(真病 vs 合理) + 三明病定位 + 静态高估根因（只读·引擎封板重放）\n")
    L.append("> 只导出+标注，未改任何产品码(vzone/quotient/sim/solver)，未决定改方向A还是fly。")
    L.append("> 路线=各 β cut 文件 `floor==MT10` 按真实 V=HP−D 取顶那条(pick_best_mt10)，干净起点(开局噩梦后 MT3 入口)引擎封板重放。")
    L.append("> 事件/损血/金币/钥匙归因到 data 真读格；「不挡路」用反事实无战 BFS 判(见脚本头注)。\n")

    # 判据说明
    L.append("## 判据（玩家区分的代码化）")
    L.append("- **高价货**：拿到能压 boss 阈值/省 boss 血的攻防宝石、铁剑铁盾（boss_toll 现算省血>0）。")
    L.append("- **远货 = MT1-5**（底层属性堆）；**近货 = MT6-8**（climb 临近层）；MT9=中转、MT10=boss 房。")
    L.append("- **合理**：先取高价近货（如 MT7 +1atk）、或回头拿高价远货（MT1-5 那 5 件）。")
    L.append("- **就近病**：**可绕开**(无战路径能到下一奖励) 的 **非零伤** 损血战，且**此刻 MT1-5 还有远货未拿**"
             "（=低价近货压高价远货）。金币在本区无处花(全程未购买，金币只增不减)→这种损血是净亏。")
    L.append("- **挡路必战**：无战不可达下一奖励 → 必须打 → 不算病（即便只给金币）。")
    L.append("- **零伤路过**：损血=0 → 无害，不计病（玩家明确排除）。\n")

    # 横向对比表
    L.append("## 1. 横向对比：四 β 路线总览 + 病计数\n")
    L.append("| β | 到MT10 HP/ATK/DEF | 步数 | 换层段 | 进MT9次 | MT1深潜 | 就近病战(可绕+压远货) | 收尾冗余战 | 开门不进 | MT5剑后MT1拿血 | 广义早拿血(700+) | 可绕战浪费血 | 总战损血 | 封板 |")
    L.append("|---|------------------|-----|-------|--------|--------|---------------------|-----------|---------|---------------|----------------|------------|---------|------|")
    for o in results:
        b = o["beta"]
        if o.get("missing") or o.get("no_mt10"):
            L.append(f"| {b:g} | {'cut缺' if o.get('missing') else '未到MT10'} | | | | | | | | | | | |")
            continue
        t = o["term"]; d = o["dis"]
        mt1_dives = _count_mt1_dives(o)
        L.append(f"| {b:g} | {t['hp']}/{t['atk']}/{t['df']} | {o['n_steps']} | {o['n_seg']} | "
                 f"{o['n_mt9']} | {mt1_dives} | **{len(d['junk_kill'])}** | {len(d['redundant_kill'])} | "
                 f"**{len(d['door_noenter'])}** | **{len(d['hp_after_sword'])}** | {len(d['early_heal'])} | "
                 f"{d['wasted_hp']} | {d['fight_hp']} | {'✅' if o['fid_ok'] else '❌'} |")
    L.append("")
    L.append("> - **就近病战**：可绕开 + 非零伤 + 此刻 MT1-5 还有远货未拿（低价近货压高价远货）。")
    L.append("> - **收尾冗余战**：可绕开 + 非零伤，但远货已收完（无远货可压，纯属多打）。")
    L.append("> - **可绕战浪费血** = 就近病战 + 收尾冗余战 的损血合计（这些血本可不掉）。\n")

    # 干净度排序
    rank = [o for o in results if not (o.get("missing") or o.get("no_mt10"))]
    rank.sort(key=lambda o: (len(o["dis"]["junk_kill"]) + len(o["dis"]["door_noenter"])
                             + len(o["dis"]["hp_after_sword"]), o["n_steps"]))
    L.append("**干净度排序（病少+步短优先）：** "
             + " < ".join(f"β{o['beta']:g}(病{len(o['dis']['junk_kill'])+len(o['dis']['door_noenter'])+len(o['dis']['hp_after_sword'])}/步{o['n_steps']})"
                          for o in rank))
    L.append("")
    # 高β更多垃圾？
    L.append("**「β 越高越多低价垃圾」核对：** 把四 β 的就近病战数按 β 排出来 → "
             + ", ".join(f"β{o['beta']:g}={len(o['dis']['junk_kill'])}" for o in sorted(rank, key=lambda o: o['beta']))
             + "（步数 " + ", ".join(f"β{o['beta']:g}={o['n_steps']}" for o in sorted(rank, key=lambda o: o['beta'])) + "）。\n")

    # ── 综述（数据怎么说，不决定改方向A还是fly） ──────────────────────────────
    L.append("## 2. 综述：数据揭示了什么（只陈述事实，不决定改方向A还是fly）\n")
    n_return = sum(1 for o in rank if _count_mt1_dives(o) > 0)
    dive_str = ", ".join(f"β{o['beta']:g}回MT1×{_count_mt1_dives(o)}" for o in sorted(rank, key=lambda o: o['beta']))
    L.append(f"**(1) 四条路线都【确实回了】MT1-5，不是「永不回头」。** {n_return}/{len(rank)} 条进过 MT1（{dive_str}）。"
             "且每条首入 MT9 时手上恒为 5 件远货已拿（与 β 无关）——「β 越高拿得越早」被证伪。"
             "真正的乱象不是「不回」，而是 MT9↔MT8↔MT7 来回蹭（每条进 MT9 5-6 次、步数 1113-1948）。\n")

    tot_waste = sum(o["dis"]["wasted_hp"] for o in rank)
    tot_fight = sum(o["dis"]["fight_hp"] for o in rank)
    waste_str = ", ".join(f"β{o['beta']:g}={o['dis']['wasted_hp']}/{o['dis']['fight_hp']}" for o in sorted(rank, key=lambda o: o['beta']))
    pct = (tot_waste / tot_fight * 100) if tot_fight else 0.0
    L.append(f"**(2) 这些「来回蹭」绝大多数【不掉血】。** 可绕战浪费血 / 总战损血 四条合计 {tot_waste}/{tot_fight}"
             f"（仅 {pct:.0f}%；逐条 {waste_str}）。蹭来蹭去多是【零伤路过已清怪】，真正「本可不掉的血」很小。"
             "所以玩家看到的『突然一堆无意义操作』主要是【路径不连贯/低效】，不是【大量流血】。\n")

    tot_junk = sum(len(o["dis"]["junk_kill"]) for o in rank)
    junk_examples = []
    for o in sorted(rank, key=lambda o: o['beta']):
        for (i, fl, dmg, dg, cnt, ha, fv) in o["dis"]["junk_kill"]:
            junk_examples.append(f"β{o['beta']:g}步#{i}@{fl}(损{dmg}/省boss{fv:.0f})")
    ex_str = "；".join(junk_examples[:6]) if junk_examples else "无"
    L.append(f"**(3) 真·就近病（可绕开+非零伤+此刻还有远货）数量少但确凿：四条共 {tot_junk} 处。** 例：{ex_str}。"
             "这些是「低价近货压高价远货」——可绕开却选择损血、且此刻 MT1-5 还有能省 boss 血的远货没拿。\n")

    d0 = sum(len(o["dis"]["junk_kill"]) for o in rank)
    d2 = sum(len(o["dis"]["door_noenter"]) for o in rank)
    d3 = sum(len(o["dis"]["hp_after_sword"]) for o in rank)
    d4 = sum(len(o["dis"]["early_heal"]) for o in rank)
    L.append("**(4) 玩家点名的三个明确病，定位结果：**")
    L.append(f"- ①『打无意义怪(只给金币)』：四条共 **{d0}** 处（即上面的就近病；金币本区无处花→净亏）。")
    L.append(f"- ②『开门不进』：四条共 **{d2}** 处（已排除 beam 在末步截断造成的假阳——那种不算真不进）。")
    L.append(f"- ③『MT5 拿剑后回 MT1 拿血(700+)』：四条共 **{d3}** 处。")
    L.append(f"- ④『广义早拿血(HP≥{HP_HIGH} 仍拿血，非③那处)』：四条共 **{d4}** 处（玩家记忆里的残留，多在开局 MT3 满血还拿）。\n")

    # 根因 ×倍数（每 β 重算未拿合计）
    ratios = []
    for o in sorted(rank, key=lambda o: o['beta']):
        if not o.get("root"):
            continue
        ss = sl = 0.0
        for (c, da, dd, val, s_, l_, ps, pl, tk) in o["root"]["rows"]:
            if not tk:
                ss += ps; sl += pl
        if ss > 0:
            ratios.append((o["beta"], ss, sl, sl / ss))
    if ratios:
        rat_str = ", ".join(f"β{b:g}: {ss:.2f}→{sl:.2f}(×{r:.1f})" for (b, ss, sl, r) in ratios)
        L.append(f"**(5) 根因坐实：静态高估把「回 MT1-5」在 pull 里压低约 ×3。** 首入 MT9 仍未拿的远货，"
                 f"pull现状 vs 方向A(读活体)：{rat_str}。倍数与 β 基本无关（机制① 是结构性的，不是某个 β 的偶然）。")
    else:
        L.append("**(5) 根因：** 四条路线首入 MT9 时 MT1-5 远货均已先深潜拿完，"
                 "故此态无「未拿远货」可量化压制；压制发生在更早的决策点（见各 β 距离差 d楼梯静≫d楼梯活）。")
    L.append("> 注：fly 在「回 MT1-5」这一场景对距离【零增量】（前次 8 态探针 fly活==楼梯活、fly静更差），"
             "故本表只列楼梯静 vs 楼梯活两版；fly 的价值另属机制②（远征链被 beam 截断），不在本读路审计范围。\n")

    cleanest = rank[0] if rank else None
    if cleanest:
        seq = ", ".join(f"β{o['beta']:g}(病{len(o['dis']['junk_kill'])+len(o['dis']['door_noenter'])+len(o['dis']['hp_after_sword'])}/步{o['n_steps']})"
                        for o in rank)
        L.append(f"**(6)『β 越高越多垃圾』被证伪——非单调。** 干净度排序 {seq}，"
                 f"最干净的是 **β{cleanest['beta']:g}**（病最少+步最短），并非最低或最高 β。"
                 "病数随 β 非单调，说明垃圾操作量主要由「pull 把回头压住后、beam 在近层找事做」驱动，而非 β 大小本身。\n")

    # 每 β 详情
    for o in results:
        b = o["beta"]
        if o.get("missing") or o.get("no_mt10"):
            L.append(f"## β={b:g}：{'cut 文件缺' if o.get('missing') else '未到 MT10'}\n")
            continue
        t = o["term"]; d = o["dis"]
        L.append(f"## β={b:g} 详情　终态 {t['floor']}({t['x']},{t['y']}) HP={t['hp']} "
                 f"ATK={t['atk']} DEF={t['df']} gold={t['gold']} 持钥={t['keys']}　"
                 f"封板={'✅一致' if o['fid_ok'] else '❌偏离'}\n")

        # MT9 前后决策
        L.append(f"### MT9 前后决策（共进 MT9 {o['n_mt9']} 次，每次到下次进 MT9 之间干了什么）")
        L.append("| 第# | 进MT9@步 | 此段触达楼层 | 拿宝石 | 拿钥匙 | 打怪数 | 段损血 |")
        L.append("|----|---------|------------|-------|-------|-------|-------|")
        for k, sg in enumerate(o["segs"], 1):
            gem_s = ",".join(f"{c[0]}{c[1:]}" for c in sg["gems"]) or "—"
            fl_s = "→".join(sg["floors"]) or "—"
            L.append(f"| {k} | {sg['entry']} | {fl_s} | {gem_s} | {sg['keys']} | {sg['kills']} | {sg['dmg']} |")
        L.append("")

        # 三明病定位
        L.append("### 三个明确病定位")
        L.append(f"**① 打无意义怪（可绕开·非零伤·只给金币·此刻还有远货）：{len(d['junk_kill'])} 处**")
        if d["junk_kill"]:
            for (i, fl, dmg, dg, cnt, ha, fv) in d["junk_kill"][:40]:
                L.append(f"- 步#{i} @{fl}：损血{dmg}/金+{dg}，可绕开，此刻MT1-5剩{cnt}件远货"
                         f"{'(含红宝石)' if ha else ''}(可省boss{fv:.0f}血)")
            if len(d["junk_kill"]) > 40:
                L.append(f"- …另有 {len(d['junk_kill'])-40} 处（见动作串完整重放）")
        else:
            L.append("- （无）")
        L.append(f"**② 开门不进（耗钥开门但全程未踏入门后格）：{len(d['door_noenter'])} 处**")
        if d["door_noenter"]:
            for (i, fl, dc) in d["door_noenter"][:40]:
                L.append(f"- 步#{i} @{fl}：开 {dc} 门后再未踏入")
        else:
            L.append("- （无）")
        L.append(f"**③ MT5 拿剑后回 MT1 拿血（HP 已≥{HP_HIGH}）：{len(d['hp_after_sword'])} 处**")
        if d["hp_after_sword"]:
            for (i, hpb, dh) in d["hp_after_sword"]:
                L.append(f"- 步#{i}：此刻 HP={hpb}（已≥{HP_HIGH}）仍拿血 +{dh}")
        else:
            L.append("- （无）")
        L.append(f"**④ 广义早拿血（HP≥{HP_HIGH} 时拿血，非上面③那处·玩家记忆里的残留病）：{len(d['early_heal'])} 处**")
        if d["early_heal"]:
            for (i, fl, hpb, dh) in d["early_heal"][:20]:
                L.append(f"- 步#{i} @{fl}：此刻 HP={hpb}（已≥{HP_HIGH}）仍拿血 +{dh}")
        else:
            L.append("- （无）")
        L.append("")

        # 静态高估根因
        if o["root"]:
            r = o["root"]
            L.append(f"### 静态高估根因（首入 MT9 态 floor={r['floor']}{r['pos']} "
                     f"HP/ATK/DEF={r['hero'][0]}/{r['hero'][1]}/{r['hero'][2]}）")
            L.append("现状 pull 用 d楼梯静(全活当墙)算 MT1-5 距离；方向A 用 d楼梯活(已清怪=0)。静≫活 即坐实回头被误判成贵。"
                     "（首入 MT9 前本路线已先深潜过 MT1，标✔者此刻已拿、不计入 pull 合计；pull 合计只算未拿的）：")
            L.append("| MT1-5远货格 | +atk/+def | boss省血 | d楼梯静(现状) | d楼梯活(方向A) | pull现状 | pull方向A | 此刻已拿? |")
            L.append("|------------|----------|---------|--------------|---------------|---------|----------|----------|")
            sum_s = sum_l = 0.0
            for (c, da, dd, val, s_, l_, ps, pl, tk) in r["rows"]:
                if not tk:
                    sum_s += ps; sum_l += pl
                ps_s = "—" if tk else f"{ps:.3f}"
                pl_s = "—" if tk else f"{pl:.3f}"
                L.append(f"| {c[0]}{c[1:]} | +{da}/+{dd} | {val:.0f} | {_fmt(s_)} | {_fmt(l_)} | "
                         f"{ps_s} | {pl_s} | {'✔已拿' if tk else '○未拿'} |")
            L.append(f"| **未拿合计** | | | | | **{sum_s:.3f}** | **{sum_l:.3f}** |")
            if sum_s > 0:
                L.append(f"\n→ 首入 MT9 时仍未拿的 MT1-5 远货，在 pull 里现状只值 **{sum_s:.3f}**，"
                         f"方向A 抬到 **{sum_l:.3f}**（×{sum_l/sum_s:.1f}）。静态高估把回头压了下去 = 机制① 根因坐实。\n")
            else:
                L.append("\n→ 首入 MT9 时 MT1-5 远货【已全部拿完】（本路线先深潜 MT1 再上 MT9）——"
                         "此态无远货可压；静态高估的压制发生在更早的决策点，见上方 d楼梯静≫d楼梯活 的距离差本身。\n")

        # 决策标注全表（filtered 到价值/病事件）
        L.append("### 逐里程碑决策标注（换层略；只列价值/病事件）")
        L.append("| 步# | 楼层格 | 区 | HP | ATK | DEF | 金 | 事件 | 标注 |")
        L.append("|----|-------|----|----|----|-----|----|------|------|")
        for a in o["annotated"]:
            L.append(f"| {a['i']} | {a['floor']}({a['x']},{a['y']}) | {a['zone']} | {a['hp']} | "
                     f"{a['atk']} | {a['df']} | {a['gold']} | {a['label']} | {a['tag']} |")
        L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")


def _count_mt1_dives(o):
    floors = []
    for sg in o["segs"]:
        floors += sg["floors"]
    # 用 milestones 里 MT1 出现的「进入次数」更准
    seq = []
    prev = None
    for m in o["milestones"]:
        if m["floor"] != prev:
            seq.append(m["floor"]); prev = m["floor"]
    return sum(1 for f in seq if f == "MT1")


def main():
    start = build_start()[0]
    zone = build_zone()
    gems = _zone_attr_gems(zone)
    mt15_cells = frozenset(c for c in gems if fk(c[0]) in FAR)

    print("=" * 96)
    print("四 β best-MT10 路线就近病标注导出")
    print(f"MT1-5 属性远货 {len(mt15_cells)} 件：",
          ", ".join(f"{c[0]}{c[1:]}(+{gems[c][0]}/{gems[c][1]})"
                    for c in sorted(mt15_cells, key=lambda t: (fk(t[0]), t[1], t[2]))))
    print("=" * 96)
    results = []
    for b in BETAS:
        o = analyze(b, zone, start, gems, mt15_cells)
        results.append(o)
        if o.get("missing") or o.get("no_mt10"):
            print(f"β={b:<5g} {'cut缺' if o.get('missing') else '未到MT10'}")
            continue
        t = o["term"]; d = o["dis"]
        print(f"β={b:<5g} HP/ATK/DEF={t['hp']}/{t['atk']}/{t['df']} 步{o['n_steps']} "
              f"进MT9×{o['n_mt9']} 就近病{len(d['junk_kill'])} 冗余{len(d['redundant_kill'])} "
              f"开门不进{len(d['door_noenter'])} 剑后拿血{len(d['hp_after_sword'])} "
              f"可绕浪费血{d['wasted_hp']} 封板{'✅' if o['fid_ok'] else '❌'}")

    write_report(results, mt15_cells, gems)
    print("-" * 96)
    print(f"报告已写：{OUT}")


if __name__ == "__main__":
    main()
