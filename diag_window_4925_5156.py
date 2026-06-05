"""只读诊断：打印 token[4925..5156] 窗口逐 token 清单（动作|楼层(x,y) HP 黄/蓝/红 金 | Δ标注）。
战斗行标注：打的哪只怪 / 基础金 / coin×2 乘没乘 / 实际+金。非战斗金币变化标注「非战斗」+Δ。
运行时 monkeypatch _fight_monster/_forced_battle 捕获战斗，不改任何产品代码/真值/断言。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
import sim.simulator as S
from sim.simulator import GameState, HeroState, load_floor, step

DATA = Path('data/games51')
FLOORS = DATA / 'floors'
LO, HI = 4925, 5156

# 锚点真值（仅参考打印，来源 diag_verify_endgame.py GT）
TRUTH = {
    LO: "MT0(2,5) HP=4943 ATK=217 DEF=314 黄20 蓝1  ← 上一 PASS",
    HI: "MT?(9,6) HP=5193 ATK=217 DEF=314 黄17 蓝1 金=1768  ← 唯一 FAIL（楼层未记录）",
}

COMBAT = []  # 本 step 内捕获的战斗：(monster_id, name, base_gold, coin_on, gold_delta)

_orig_fight = S._fight_monster
_orig_forced = S._forced_battle


def _wrap_fight(state, mx, my):
    floor = state.floor
    hero = state.hero
    mid, base, name = None, 0, ''
    try:
        tile = floor.entities[my][mx]
        mid = floor._tile_to_enemy.get(tile)
        if mid is not None:
            base = floor._monsters_db[mid].get('gold', 0)
            name = floor._monsters_db[mid].get('name', mid)
    except Exception:
        pass
    coin = hero.items.get('coin', 0) > 0
    k0, g0 = hero.kill_count, hero.gold
    _orig_fight(state, mx, my)
    if hero.kill_count > k0:
        COMBAT.append((mid, name, base, coin, hero.gold - g0))


def _wrap_forced(state, enemy_id):
    floor = state.floor
    hero = state.hero
    base, name = 0, enemy_id
    if enemy_id in floor._monsters_db:
        base = floor._monsters_db[enemy_id].get('gold', 0)
        name = floor._monsters_db[enemy_id].get('name', enemy_id)
    coin = hero.items.get('coin', 0) > 0
    k0, g0 = hero.kill_count, hero.gold
    _orig_forced(state, enemy_id)
    if hero.kill_count > k0:
        COMBAT.append((enemy_id, name, base, coin, hero.gold - g0))


S._fight_monster = _wrap_fight
S._forced_battle = _wrap_forced


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
    return GameState(
        hero=hero, floors={'MT1': floor}, current_floor='MT1',
        floor_ids=floor_ids, visited_floors={'MT1'},
        pending_floor_change=None, _floors_dir=FLOORS,
        _key_bindings=key_bindings,
    )


def load_tokens():
    route_path = next(Path('.').glob('51_*.h5route'))
    raw = route_path.read_text(encoding='utf-8').strip()
    outer = json.loads(LZString().decompressFromBase64(raw))
    return parse_rle_route(LZString().decompressFromBase64(outer['route']))


def snap(s):
    h = s.hero
    return dict(
        floor=s.current_floor, x=h.x, y=h.y, hp=h.hp,
        yk=h.keys.get('yellowKey', 0), bk=h.keys.get('blueKey', 0),
        rk=h.keys.get('redKey', 0), gold=h.gold,
        kills=h.kill_count, coin=h.items.get('coin', 0),
    )


def main():
    tokens = load_tokens()
    state = build_initial_state()
    print(f"# 窗口 token[{LO}..{HI}]  共 {HI - LO + 1} 行")
    print(f"# 锚点 tok[{LO}] 真值: {TRUTH[LO]}")
    print(f"# 锚点 tok[{HI}] 真值: {TRUTH[HI]}")
    print(f"# 列: tok[idx] 动作 | 楼层(x,y) HP 黄/蓝/红 金 | Δ标注")
    prev = None
    for idx, tok in enumerate(tokens[:HI + 1]):
        COMBAT.clear()
        state = step(state, tok)
        cur = snap(state)
        if idx >= LO:
            dgold = cur['gold'] - prev['gold'] if prev else 0
            ann = []
            for mid, name, bg, coin, dg in COMBAT:
                mult = "×coin2" if coin else "×1(无coin)"
                ann.append(f"战斗:{mid}({name}) 基础{bg}金{mult}→+{dg}")
            combat_sum = sum(c[4] for c in COMBAT)
            if dgold != 0 and dgold != combat_sum:
                tag = "非战斗" if not COMBAT else f"另含非战斗{dgold - combat_sum:+d}"
                ann.append(f"金Δ{dgold:+d}({tag})")
            for k, lab in (('yk', '黄'), ('bk', '蓝'), ('rk', '红')):
                if prev and cur[k] != prev[k]:
                    ann.append(f"{lab}{prev[k]}→{cur[k]}")
            row = (f"tok[{idx}] {tok:<11}| {cur['floor']}({cur['x']},{cur['y']}) "
                   f"HP={cur['hp']} {cur['yk']}/{cur['bk']}/{cur['rk']} 金={cur['gold']}")
            if ann:
                row += "  | " + " ; ".join(ann)
            print(row)
        prev = cur
    print(f"# 终: coin={cur['coin']}  kills={cur['kills']}")


if __name__ == '__main__':
    main()
