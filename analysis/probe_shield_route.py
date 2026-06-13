"""定位本 route 神圣盾(shield5/tile44)拾取 token + 追踪 flag:魔法免疫 翻转点；
并对持盾后每一步做 dry-run：若【不免疫】该格是否会吃区域伤(领域15/夹击16/阻击18)，
以核实"持盾后是否经过区域伤格"(玩家 Task1 子任务3)。只读，不改产品代码。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from extract.decode_route import parse_rle_route
from lzstring import LZString
from sim.simulator import (
    GameState, HeroState, load_floor, step,
    _live_zone_monsters, _in_zone_range, _is_adjacent, _between_same_special16,
    _SP_ZONE, _SP_BETWEEN, _SP_REPULSE,
)

DATA = Path(__file__).parent.parent / 'data/games51'
FLOORS = DATA / 'floors'


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


def would_take_zone_damage(state):
    """dry-run：当前英雄格，【忽略免疫】是否有区域怪会触发伤害。
    返回触发明细 [(类型, mid)]。复刻 _apply_zone_damage 的触发条件(不算具体值)。"""
    hero = state.hero
    x, y = hero.x, hero.y
    hits = []
    for (mx, my, mid, sp, value, rng, zsq) in _live_zone_monsters(state):
        if _SP_ZONE in sp and _in_zone_range(x, y, mx, my, rng, zsq):
            hits.append(('领域15', mid))
        if _SP_REPULSE in sp and _is_adjacent(x, y, mx, my, zsq):
            hits.append(('阻击18', mid))
    if _between_same_special16(state, x, y):
        hits.append(('夹击16', '同id对'))
    return hits


def main():
    tokens = load_tokens()
    state = build_initial_state()

    prev_imm = bool(state.hero.flags.get('魔法免疫'))
    prev_def = state.hero.def_
    prev_shield = 'shield5' in state.hero.items and state.hero.items.get('shield5')
    shield_token = None
    imm_flip_token = None

    # 持盾后(以 魔法免疫=true 起)经过的区域伤格记录
    post_imm_zone_hits = []   # (idx, floor, x, y, hits)
    # 全程(无论是否免疫)经过区域伤格记录，用于核对全 route 区域伤暴露面
    all_zone_hits = []        # (idx, floor, x, y, hits, immune)
    floors_after_shield = []  # 持盾后进入的楼层序列(去重相邻)

    for idx, tok in enumerate(tokens):
        state = step(state, tok)
        h = state.hero
        imm = bool(h.flags.get('魔法免疫'))
        shield_now = h.items.get('shield5')

        # 神圣盾拾取检测
        if shield_token is None and shield_now and not prev_shield:
            shield_token = (idx, tok, state.current_floor, h.x, h.y, prev_def, h.def_)
        if imm_flip_token is None and imm and not prev_imm:
            imm_flip_token = (idx, tok, state.current_floor, h.x, h.y)

        # 区域伤 dry-run（每步英雄格）
        hits = would_take_zone_damage(state)
        if hits:
            all_zone_hits.append((idx, state.current_floor, h.x, h.y, hits, imm))
            if imm:
                post_imm_zone_hits.append((idx, state.current_floor, h.x, h.y, hits))

        # 持盾后楼层序列
        if imm:
            fl = state.current_floor
            if not floors_after_shield or floors_after_shield[-1] != fl:
                floors_after_shield.append(fl)

        prev_imm = imm
        prev_def = h.def_
        prev_shield = shield_now

    print('=' * 70)
    print('【神圣盾拾取】')
    if shield_token:
        idx, tok, fl, x, y, d0, d1 = shield_token
        print(f'  shield5 进背包: token[{idx}] {tok}  @ {fl}({x},{y})  DEF {d0}→{d1}')
    else:
        print('  本 route 未拾取 shield5')
    if imm_flip_token:
        idx, tok, fl, x, y = imm_flip_token
        print(f'  flag:魔法免疫 翻 True: token[{idx}] {tok}  @ {fl}({x},{y})')
    else:
        print('  flag:魔法免疫 全程未翻 True')

    print('\n【全 route 经过区域伤格（dry-run，忽略免疫的触发面）】')
    if not all_zone_hits:
        print('  全程从未踩进任何区域怪的领域/夹击/阻击格。')
    else:
        for idx, fl, x, y, hits, imm in all_zone_hits:
            tag = '免疫✓' if imm else '⚠未免疫'
            hs = ', '.join(f'{t}({m})' for t, m in hits)
            print(f'  tok[{idx}] {fl}({x},{y}) [{tag}]  {hs}')

    print('\n【持盾后(魔法免疫=true)经过的区域伤格】')
    if not post_imm_zone_hits:
        print('  持盾后从未踩进任何区域伤格 → 免疫机制本 route 无真值覆盖（与之前对齐无暴露一致）。')
    else:
        print(f'  共 {len(post_imm_zone_hits)} 处（这些格因免疫吃 0 伤，是免疫机制的隐性验证点）：')
        for idx, fl, x, y, hits in post_imm_zone_hits:
            hs = ', '.join(f'{t}({m})' for t, m in hits)
            print(f'  tok[{idx}] {fl}({x},{y})  {hs}')

    print(f'\n【持盾后进入的楼层序列】\n  {" → ".join(floors_after_shield)}')
    print('=' * 70)


if __name__ == '__main__':
    main()
