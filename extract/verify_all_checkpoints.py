"""全检查点统一对齐：重放 route 到最末检查点(token4141)，逐点对比玩家实测金标准。

口径同 test_checkpoints：tokens[:N+1]（tokens[0]=CHOICE:1 初始化事件，不计步；玩家 tok[N]=走完第 N 步后）。
只读验证——绝不改产品代码/断言/真值。报告【每个】检查点 PASS/FAIL（不在首个 FAIL 处停）。
首个 FAIL 窗口（上一 PASS 检查点 → 该 FAIL 检查点）的【逐 token 全状态清单】写入 ledger 文件，
交玩家裁定根因（§铁律：sim 与玩家实测冲突，结论只能是「sim 有 bug」，不得改真值/断言凑绿）。

真值来源（玩家在真实引擎逐点实测，金标准）：
  - 原 17：tests/test_checkpoints.py GROUND_TRUTH（token≤2000，无坐标）。
  - 1：extract/verify_tok2400.py（token2400，带坐标）。
  - 3：extract/verify_tok29xx.py（token2501/2804/2965，带坐标）。
  - 5：玩家给（token3212/3371/3704/4012/4141，带坐标）。
  - 6：终局段第一批（token4222/4350/4417/4504/4528/4582，带坐标）。
  - 7：token4723（带坐标）。
  - 8：MT0 段 token4925/5156（玩家 2026-06-05 裁定/订正；5156 带金 oracle 1724）。
  - 9：终局段第三批 10 锚点 token5313/5347/5386/5545/5833/6066/6132/6221/6248/6349（玩家 2026-06-05 给）。
  全部【落盘于此文件】，按 CLAUDE.md「确认过的数值立即落盘」要求持久化。
  注：批 8/9 索引为【修正解析器】口径——decode_route 已修 (help) 为单 token；help 区(tok5315/5320)
      及其菜单 CHOICE 已验证为无副作用 no-op。但批 9 自 tok5347 起 FAIL（sim 比真值少血/少防/
      后续少钥匙→路径分叉），疑自动操作的秒杀/拾取是回放期每步 hook(route 不另记)，待回 live 引擎
      抓"游戏说明"事件+自动操作 plugin 坐实并(若需)实现；当前 sim 尚【未】实现自动操作结算。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'
LEDGER_PATH = Path(__file__).parent.parent / 'checkpoint_ledger.txt'


def ck(idx, floor, hp, atk, df, yk=None, bk=None, rk=None, x=None, y=None, gold=None, won=None):
    return dict(idx=idx, floor=floor, hp=hp, atk=atk, df=df,
                yk=yk, bk=bk, rk=rk, x=x, y=y, gold=gold, won=won)


# ── 全部 25 个检查点（按 token 升序）。None 字段=玩家未给该项真值，不比对。──────────────
CHECKPOINTS = [
    # 原 17（无坐标）
    ck(100,  'MT3',  800, 10, 10, yk=3),
    ck(200,  'MT4',  666, 20, 10, yk=0, bk=1),
    ck(300,  'MT5',  604, 21, 10, yk=5),
    ck(400,  'MT7',  304, 21, 10, yk=4),
    ck(500,  'MT9',  290, 21, 10, yk=2),
    ck(600,  'MT3',  305, 23, 22, yk=1),
    ck(700,  'MT8',  218, 25, 23, yk=1),
    ck(800,  'MT10', 229, 26, 25),
    ck(900,  'MT7',  254, 26, 27),
    ck(1000, 'MT10', 304, 27, 27),
    ck(1100, 'MT1',  546, 27, 27),
    ck(1200, 'MT10', 510, 27, 27),
    ck(1300, 'MT14', 785, 42, 30),
    ck(1400, 'MT6',  545, 42, 30, yk=2),
    ck(1500, 'MT3',  459, 64, 32, yk=1),
    ck(1603, 'MT11', 599, 64, 52, yk=4),
    ck(2000, 'MT16', 618, 72, 56, yk=0, bk=0),
    # 1（verify_tok2400.py，带坐标）
    ck(2400, 'MT28', 1261, 78, 64, yk=5, x=2, y=11),
    # 3（带坐标）
    ck(2501, 'MT32', 143, 102, 64, yk=5, x=6,  y=10),
    ck(2804, 'MT33', 854, 112, 68, yk=3, x=7,  y=11),
    ck(2965, 'MT33', 6,   154, 70, yk=2, x=8,  y=3),
    # 5（玩家给，落盘）
    ck(3212, 'MT2',  906, 154, 70,  yk=2, bk=1,       x=1, y=10),
    ck(3371, 'MT32', 606, 158, 70,  yk=3,             x=1, y=4),
    ck(3704, 'MT38', 486, 162, 74,  yk=4, bk=1, rk=1, x=2, y=1),
    ck(4012, 'MT40', 870, 166, 122, yk=1,             x=3, y=11),
    ck(4141, 'MT41', 262, 182, 134, yk=7,             x=6, y=2),
    # 6（终局段第一批，玩家 2026-06-04 给，落盘）。DEF 暴涨 134→204→304→309（祭坛MT46/盾，对齐时核）。
    ck(4222, 'MT32', 1635, 182, 134, yk=2,             x=8,  y=8),
    ck(4350, 'MT47', 1479, 186, 138, yk=2, bk=1,       x=10, y=10),
    ck(4417, 'MT37', 1479, 202, 154, yk=11, bk=2, rk=1, x=2, y=3),  # 坐标真值 (2,4)→(2,3)：玩家 2026-06-04 主动订正(原实测记错一格)，属性不变
    ck(4504, 'MT43', 123,  202, 204, yk=5, bk=2,       x=9,  y=4),
    ck(4528, 'MT44', 623,  202, 304, yk=5, bk=2,       x=6,  y=5),
    ck(4582, 'MT47', 4723, 202, 309, yk=5, bk=2,       x=11, y=2),  # 楼层真值 MT44→MT47：玩家 2026-06-04 主动订正(原标"MT44?"存疑，route 末两跳 FLOOR 显式飞 MT47+坐标/HP/属性/钥匙全吻合为证)，属性不变
    # 7（终局段第二批，玩家 2026-06-04 给）。token4723 在 MT0 入口(tok4921 downFly→MT0)之前，不依赖 MT0。
    ck(4723, 'MT41', 4600, 212, 309, yk=14, x=3, y=6),
    # 8（MT0 段，玩家 2026-06-05 裁定/订正后落盘）。tok4925 坐标(2,5)系玩家订正(原误录(1,5))；
    #   tok5156 楼层/坐标/金按 sim 订正为 MT16(9,11)/金1724(原误录 MT?(9,6)/1768)——玩家主动订正真值，非凑绿。
    #   金1724 是幸运金币 coin×2 的 oracle（全 route 仅此点给了金真值）。
    ck(4925, 'MT0',  4943, 217, 314, yk=20, bk=1,        x=2,  y=5),
    ck(5156, 'MT16', 5193, 217, 314, yk=17, bk=1,        x=9,  y=11, gold=1724),
    # 9（终局段第三批 10 锚点，玩家 2026-06-05 给，落盘）。索引为【修正解析器】口径(help=单 token)。
    #   自动操作(tok5315 起 help 菜单开启)的秒杀/拾取已烘焙为显式 move token，按普通回放即可——
    #   引擎在 moveHero/battle 层记录每个自动动作，无自定义 replayAction，sim 无需自动结算逻辑(详见 decode_route 坐实)。
    ck(5313, 'MT36', 5693,  217, 318, yk=14, bk=1,        x=10, y=11),
    ck(5347, 'MT46', 5893,  217, 322, yk=13, bk=1,        x=11, y=2),
    ck(5386, 'MT48', 6095,  322, 322, yk=13, bk=1,        x=7,  y=8),
    ck(5545, 'MT45', 10845, 337, 327, yk=12, bk=2,        x=9,  y=1),
    ck(5833, 'MT49', 14547, 362, 347, yk=10, bk=3, rk=1),
    ck(6066, 'MT45', 21141, 482, 347, yk=7,  bk=3, rk=1,  x=2,  y=1),
    ck(6132, 'MT45', 24141, 492, 357, yk=5,  bk=3, rk=1,  x=10, y=1),
    # 索引 6221→6222：玩家 2026-06-05 主动订正(记锚点时读的是接受 3% 祝福【后】属性 507/373；
    #   游戏内 6221-6223 的撞击/选择不直接反映在 token 记录上，实际对应 sim tok6222=CHOICE 祝福生效那步)。
    #   HP 两处均 26391 吻合，撞击步(6221)属性为祝福前 492/362。属主订正真值，非凑绿。
    ck(6222, 'MT2',  26391, 507, 373),
    ck(6248, 'MT25', 22277, 507, 373, yk=3,  bk=1, rk=4),
    ck(6349, 'MT50', 32487, 507, 373,                     x=6,  y=7),
    # 10（通关锚点，玩家裁定 win=True + HP=14382）。tok6353=CHOICE:0(榜单"生命值")→
    #   afterBattle["6,5"] 榜单 while 经 break 跳出 → 续跑循环外 type:win → won=True(软终止)。
    #   HP=14382=32487(tok6349)−18105：MT50魔王 setEnemy hp5000/atk1580/def190；勇者ATK507vs防190
    #   每刀317→⌈5000/317⌉=16刀；受 boss ATK1580vs防373=1207/刀×(16−1)=18105。boss金500×幸运币2→g1928。
    ck(6353, 'MT50', 14382, 507, 373, x=6, y=5, won=True),
]
MAXTOK = max(c['idx'] for c in CHECKPOINTS)


def build_initial_state():
    floor_ids = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))
    hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
    kb_raw = json.loads((DATA / 'replay_keybindings.json').read_text(encoding='utf-8'))
    key_bindings = {int(k): v for k, v in kb_raw.get('bindings', {}).items()}
    floor = load_floor(FLOORS / 'MT1.json')
    hero = HeroState(
        x=hero_init['loc']['x'], y=hero_init['loc']['y'],
        hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
        mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
        keys={}, items=dict(hero_init.get('items', {})),
        flags=dict(hero_init.get('flags', {})),
    )
    return GameState(hero=hero, floors={'MT1': floor}, current_floor='MT1',
                     floor_ids=floor_ids, visited_floors={'MT1'},
                     pending_floor_change=None, _floors_dir=FLOORS,
                     _key_bindings=key_bindings)


def load_tokens():
    rp = next(Path('.').glob('51_*.h5route'), None) or \
         next((Path(__file__).parent.parent).glob('51_*.h5route'), None)
    raw = rp.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def full_snap(s):
    """逐 token ledger 用的完整状态快照。"""
    h = s.hero
    return dict(
        floor=s.current_floor, x=h.x, y=h.y, hp=h.hp, atk=h.atk, df=h.def_,
        gold=h.gold, kills=getattr(h, 'kill_count', 0),
        yk=h.keys.get('yellowKey', 0), bk=h.keys.get('blueKey', 0),
        rk=h.keys.get('redKey', 0),
        items={k: v for k, v in h.items.items() if v},
        won=getattr(s, 'won', False),
    )


def cmp_checkpoint(c, snap):
    """返回 (errs, sim_str, truth_str)。仅比对玩家给了真值的字段。"""
    errs = []
    if snap['floor'] != c['floor']:
        errs.append(f"floor sim={snap['floor']} 真值={c['floor']}")
    if c['x'] is not None and (snap['x'], snap['y']) != (c['x'], c['y']):
        errs.append(f"pos sim=({snap['x']},{snap['y']}) 真值=({c['x']},{c['y']})")
    for key, label in (('hp', 'HP'), ('atk', 'ATK'), ('df', 'DEF'),
                       ('yk', '黄'), ('bk', '蓝'), ('rk', '红'), ('gold', '金')):
        exp = c[key]
        if exp is None:
            continue
        got = snap[key]
        if got != exp:
            errs.append(f"{label} sim={got} 真值={exp} 差={got - exp:+d}")
    sim_str = (f"{snap['floor']}({snap['x']},{snap['y']}) HP={snap['hp']} "
               f"ATK={snap['atk']} DEF={snap['df']} 黄={snap['yk']} 蓝={snap['bk']} 红={snap['rk']} 金={snap['gold']}")
    tp = lambda v: '·' if v is None else v
    truth_str = (f"{c['floor']}({tp(c['x'])},{tp(c['y'])}) HP={c['hp']} "
                 f"ATK={c['atk']} DEF={c['df']} 黄={tp(c['yk'])} 蓝={tp(c['bk'])} 红={tp(c['rk'])} 金={tp(c['gold'])}")
    # 通关锚点：仅当真值给了 won 才比对(与死亡硬终止对偶的软终止标志)。
    if c.get('won') is not None:
        if snap.get('won') != c['won']:
            errs.append(f"won sim={snap.get('won')} 真值={c['won']}")
        sim_str += f" win={snap.get('won')}"
        truth_str += f" win={c['won']}"
    return errs, sim_str, truth_str


def write_ledger(window_rows, lo, hi, lo_truth, hi_truth):
    """把 [lo→hi] 窗口逐 token 全状态清单写入文件。window_rows: [(idx, tok, snap, deltas)]。"""
    lines = []
    lines.append(f"# 逐 token 清单（窗口 token[{lo}] → token[{hi}]）")
    lines.append(f"# 上一 PASS 检查点 token[{lo}] 真值: {lo_truth}")
    lines.append(f"# 首个 FAIL 检查点 token[{hi}] 真值: {hi_truth}")
    lines.append("# 每行: tok[idx] TOKEN | 楼层(x,y) HP ATK DEF gold 黄/蓝/红 kills | Δ变化")
    lines.append("# Δ 标注该 token 引起的状态变化（战斗=HP↓且kills↑/纯HP↓=地形或强制战;"
                 " 拾取=道具/钥匙/属性↑;切层=楼层变）。仅用于玩家裁定分叉点，sim 不据此自行改。")
    lines.append("")
    for idx, tok, snap, deltas in window_rows:
        base = (f"tok[{idx}] {tok:<10} | {snap['floor']}({snap['x']},{snap['y']}) "
                f"HP={snap['hp']} ATK={snap['atk']} DEF={snap['df']} g={snap['gold']} "
                f"{snap['yk']}/{snap['bk']}/{snap['rk']} k={snap['kills']}")
        dstr = ('  Δ ' + ', '.join(deltas)) if deltas else ''
        lines.append(base + dstr)
    LEDGER_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def diff_deltas(prev, cur):
    d = []
    if cur['floor'] != prev['floor']:
        d.append(f"楼层{prev['floor']}→{cur['floor']}")
    if cur['hp'] != prev['hp']:
        d.append(f"HP{cur['hp'] - prev['hp']:+d}")
    if cur['atk'] != prev['atk']:
        d.append(f"ATK{cur['atk'] - prev['atk']:+d}")
    if cur['df'] != prev['df']:
        d.append(f"DEF{cur['df'] - prev['df']:+d}")
    if cur['gold'] != prev['gold']:
        d.append(f"金{cur['gold'] - prev['gold']:+d}")
    if cur['kills'] != prev['kills']:
        d.append(f"击杀+{cur['kills'] - prev['kills']}")
    for k, lab in (('yk', '黄'), ('bk', '蓝'), ('rk', '红')):
        if cur[k] != prev[k]:
            d.append(f"{lab}{prev[k]}→{cur[k]}")
    if cur['items'] != prev['items']:
        d.append(f"道具{prev['items']}→{cur['items']}")
    return d


def main():
    tokens = load_tokens()
    print(f'route 总 token 数: {len(tokens)}（需 ≥{MAXTOK + 1}）')
    if len(tokens) < MAXTOK + 1:
        print(f'🛑 token 不足，无法回放到 {MAXTOK}')
        sys.exit(1)

    target_idx = {c['idx'] for c in CHECKPOINTS}
    state = build_initial_state()
    prev_snap = full_snap(state)
    snaps = {}
    # 滚动记录每个 token 的全状态与 Δ，供 ledger 取窗口
    all_rows = []  # (idx, tok, snap, deltas)

    for idx, tok in enumerate(tokens[:MAXTOK + 1]):
        try:
            state = step(state, tok)
        except Exception as e:
            print(f'\n🛑 token[{idx}] 抛异常 {type(e).__name__}: {e}  token={tok}')
            sys.exit(1)
        cur = full_snap(state)
        all_rows.append((idx, tok, cur, diff_deltas(prev_snap, cur)))
        if idx in target_idx:
            snaps[idx] = cur
        prev_snap = cur

    # 逐检查点报告（不在 FAIL 处停）
    results = []
    for c in CHECKPOINTS:
        errs, sim_str, truth_str = cmp_checkpoint(c, snaps[c['idx']])
        results.append((c, errs, sim_str, truth_str))

    n_pass = sum(1 for _, e, _, _ in results if not e)
    n_fail = len(results) - n_pass
    print(f'\n{"="*70}\n检查点总览：{len(results)} 个，PASS {n_pass}，FAIL {n_fail}\n{"="*70}')
    for c, errs, sim_str, truth_str in results:
        tag = '✅ PASS' if not errs else '🛑 FAIL'
        print(f'  [{tag}] token[{c["idx"]:>4}] {c["floor"]:<5}', end='')
        if errs:
            print(f'  ← {"; ".join(errs)}')
        else:
            print()

    # 首个 FAIL → 写 ledger（窗口=上一 PASS 检查点→该 FAIL）
    first_fail_i = next((i for i, (_, e, _, _) in enumerate(results) if e), None)
    if first_fail_i is None:
        print(f'\n✅ 全部 {len(results)} 个检查点 PASS。')
        sys.exit(0)

    fc, ferrs, fsim, ftruth = results[first_fail_i]
    # 上一 PASS 检查点（其前的最近一个无错检查点；若无则从 token0 起）
    lo = 0
    lo_truth = '(route 起点)'
    for j in range(first_fail_i - 1, -1, -1):
        if not results[j][1]:
            lo = results[j][0]['idx']
            lo_truth = results[j][3]
            break
    hi = fc['idx']
    window_rows = [r for r in all_rows if lo < r[0] <= hi]
    write_ledger(window_rows, lo, hi, lo_truth, ftruth)

    print(f'\n{"="*70}')
    print(f'首个 FAIL = token[{hi}] ({fc["floor"]})：{"; ".join(ferrs)}')
    print(f'  sim : {fsim}')
    print(f'  真值: {ftruth}')
    print(f'已将窗口 token[{lo}→{hi}]（{len(window_rows)} 步）逐 token 全状态清单写入：')
    print(f'  {LEDGER_PATH}')
    print('交玩家裁定分叉点根因（铁律：不得自行猜根因/改真值/改断言凑绿）。')
    print(f'{"="*70}')

    # 控制台贴出窗口中「有状态变化」的关键行，便于快速定位分叉
    print('\n窗口内有 Δ 变化的关键 token（完整清单见 ledger 文件）：')
    for idx, tok, snap, deltas in window_rows:
        if deltas:
            print(f'  tok[{idx}] {tok:<9} {snap["floor"]}({snap["x"]},{snap["y"]}) '
                  f'HP={snap["hp"]} ATK={snap["atk"]} DEF={snap["df"]}  Δ {", ".join(deltas)}')
    sys.exit(1)


if __name__ == '__main__':
    main()
