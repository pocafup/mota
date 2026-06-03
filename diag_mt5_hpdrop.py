"""
诊断 token[210..546]（MT5/MT4/MT5 交替段）的 HP 变化。
输出：
  1. 英雄是否经过 MT5(9,11) 暗墙 / (11,11) 铁剑
  2. 所有 HP 减少事件（含损血量、位置、当时 ATK/DEF）
  3. token[210] 到 token[546] 的 ATK 变化时间轴
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'
FLOOR_IDS = json.loads((DATA / 'floorIds.json').read_text(encoding='utf-8'))

def decompress(s):
    return LZString().decompressFromBase64(s)

route_path = next(Path('.').glob('51_*.h5route'))
raw = route_path.read_text(encoding='utf-8').strip()
outer = json.loads(decompress(raw))
tokens = parse_rle_route(decompress(outer['route']))[:1318]

# ── 重放到 token[209] ────────────────────────────────────────────────────────
hero_init = json.loads((DATA / 'hero_init.json').read_text(encoding='utf-8'))
floor = load_floor(FLOORS / 'MT1.json')
hero = HeroState(
    x=hero_init['loc']['x'], y=hero_init['loc']['y'],
    hp=hero_init['hp'], atk=hero_init['atk'], def_=hero_init['def'],
    mdef=hero_init.get('mdef', 0), gold=hero_init.get('gold', 0),
    keys={}, items=dict(hero_init.get('items', {})), flags=dict(hero_init.get('flags', {})),
)
state = GameState(hero=hero, floors={'MT1': floor}, current_floor='MT1',
    floor_ids=FLOOR_IDS, visited_floors={'MT1'}, pending_floor_change=None, _floors_dir=FLOORS)

for tok in tokens[:210]:
    state = step(state, tok)

print(f"token[209] 结束: floor={state.current_floor} pos=({state.hero.x},{state.hero.y}) "
      f"hp={state.hero.hp} atk={state.hero.atk} def={state.hero.def_}")
print()

# ── 追踪 token[210..546] ─────────────────────────────────────────────────────
hp_drops = []
atk_changes = []
visited_mt5_sword_area = []  # 记录经过 (9,11) (10,11) (11,11) 的时刻
prev_atk = state.hero.atk

for idx in range(210, 547):
    tok = tokens[idx]
    fl_before = state.current_floor
    pos_before = (state.hero.x, state.hero.y)
    hp_before = state.hero.hp
    atk_before = state.hero.atk

    state = step(state, tok)

    fl_after = state.current_floor
    pos_after = (state.hero.x, state.hero.y)
    hp_after = state.hero.hp
    atk_after = state.hero.atk

    # 记录 HP 减少
    if hp_after < hp_before:
        hp_drops.append({
            'idx': idx, 'tok': tok,
            'floor': fl_before, 'pos': pos_before, 'pos_after': pos_after,
            'hp_before': hp_before, 'hp_after': hp_after,
            'loss': hp_before - hp_after,
            'atk': atk_before, 'def_': state.hero.def_,
        })

    # 记录 ATK 变化
    if atk_after != atk_before:
        atk_changes.append({
            'idx': idx, 'tok': tok,
            'floor': fl_before, 'pos': pos_after,
            'atk_before': atk_before, 'atk_after': atk_after,
        })

    # 记录经过铁剑区域
    if fl_after == 'MT5' and pos_after[0] >= 8 and pos_after[1] == 11:
        visited_mt5_sword_area.append({
            'idx': idx, 'tok': tok,
            'pos_before': pos_before, 'pos_after': pos_after,
            'hp': hp_after, 'atk': atk_after,
        })

# ── 报告 1：铁剑区域访问记录 ──────────────────────────────────────────────────
print("=== MT5 铁剑区域 (x≥8, y=11) 访问记录 ===")
if visited_mt5_sword_area:
    for r in visited_mt5_sword_area:
        print(f"  [{r['idx']:>4}] {r['tok']:<6} {r['pos_before']} → {r['pos_after']}  "
              f"hp={r['hp']}  atk={r['atk']}")
else:
    print("  【从未进入 MT5 row11 x≥8 区域】→ 英雄没有机会拿铁剑")

# 检查 (11,11) 是否被清空（铁剑被拾取）
if 'MT5' in state.floors:
    mt5 = state.floors['MT5']
    tile_at_sword = mt5.entities[11][11] if len(mt5.entities) > 11 else '?'
    print(f"\n  token[546] 时 MT5(11,11) 实体层 tile={tile_at_sword}  (35=铁剑未拾取, 0=已拾取)")

# ── 报告 2：ATK 变化时间轴 ────────────────────────────────────────────────────
print("\n=== ATK 变化时间轴 ===")
if atk_changes:
    for r in atk_changes:
        print(f"  [{r['idx']:>4}] {r['tok']:<6} {r['floor']} {r['pos']}  "
              f"{r['atk_before']} → {r['atk_after']}")
else:
    print("  ATK 全程未变化（整段 token[210..546] atk 固定为 10）")

# ── 报告 3：损血排行榜（前 15 名）────────────────────────────────────────────
print(f"\n=== token[210..546] 损血事件（共 {len(hp_drops)} 笔，列前 15 大）===")
top_drops = sorted(hp_drops, key=lambda x: -x['loss'])[:15]
for r in top_drops:
    pos_str = f"({r['pos'][0]},{r['pos'][1]})"
    print(f"  [{r['idx']:>4}] {r['tok']:<6} {r['floor']:<5} {pos_str:<10} "
          f"HP {r['hp_before']:>5} → {r['hp_after']:>5}  损{r['loss']:>5}  "
          f"atk={r['atk']} def={r['def_']}")

# ── 报告 4：累计损血与最终状态 ────────────────────────────────────────────────
total_loss = sum(r['loss'] for r in hp_drops)
print(f"\n=== 累计损血 = {total_loss}，token[546] 最终状态 ===")
print(f"  floor={state.current_floor}  pos=({state.hero.x},{state.hero.y})")
print(f"  hp={state.hero.hp}  atk={state.hero.atk}  def={state.hero.def_}")
print(f"  keys={dict(state.hero.keys)}")
