"""
Extract MT10 Visit 4 full token sequence → data/games51/mt10_route_trace.json
Report: total tokens, global index range, step-43 neighbourhood.
"""
import json, sys
from pathlib import Path
from lzstring import LZString

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"


def decompress(s):
    return LZString().decompressFromBase64(s)


def parse_rle(raw):
    actions = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if raw[i:i+3] == 'FMT':
            j = i + 3
            while j < n and raw[j].isdigit():
                j += 1
            floor_num = raw[i+3:j]
            if j < n and raw[j] == ':':
                j += 1
            actions.append(f'FLOOR:MT{floor_num}')
            i = j
        elif c in 'UDLR':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            count = int(raw[i:j]) if j > i else 1
            i = j
            actions.extend([c] * count)
        elif c == 'C':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            val = int(raw[i:j]) if j > i else 0
            i = j
            actions.append(f'CHOICE:{val}')
        elif c == 'I':
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            tile_id = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1
            actions.append(f'ITEM:{tile_id}')
            i = j
        elif c.isalpha():
            j = i + 1
            while j < n and raw[j].isdigit():
                j += 1
            tok = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1
                tok += ':'
            actions.append(f'UNK:{tok}')
            i = j
        else:
            i += 1
    return actions


def segment_mt10_visits(actions):
    visits = []
    current_floor = None
    visit_start = None
    visit_actions = []

    for i, act in enumerate(actions):
        if act.startswith('FLOOR:'):
            dest = act[6:]
            if current_floor == 'MT10':
                visits.append({'global_start': visit_start, 'global_end': i - 1, 'tokens': visit_actions})
                visit_actions = []
            if dest == 'MT10':
                current_floor = 'MT10'
                visit_start = i
                visit_actions = []
            else:
                current_floor = dest
        elif current_floor == 'MT10':
            visit_actions.append({'global_idx': i, 'token': act})

    if current_floor == 'MT10' and visit_actions:
        visits.append({'global_start': visit_start, 'global_end': len(actions) - 1, 'tokens': visit_actions})

    return visits


def main():
    h5route = next(ROOT.glob('51_*.h5route'))
    raw_outer = decompress(h5route.read_text(encoding='utf-8').strip())
    outer = json.loads(raw_outer)
    route_raw = decompress(outer['route'])
    actions = parse_rle(route_raw)

    visits = segment_mt10_visits(actions)
    v4 = visits[3]  # 0-indexed Visit 4

    out = {
        '_note': 'MT10 Visit 4 full token sequence. global_idx = index in full 6360-action list.',
        'visit_number': 4,
        'global_start_floor_token': v4['global_start'],
        'global_end_floor_token': v4['global_end'],
        'total_tokens': len(v4['tokens']),
        'move_count': sum(1 for t in v4['tokens'] if t['token'] in ('U','D','L','R')),
        'tokens': v4['tokens'],
    }

    out_path = DATA / 'mt10_route_trace.json'
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')

    # ── summary to stdout ──
    toks = v4['tokens']
    total = len(toks)
    moves = [t for t in toks if t['token'] in ('U','D','L','R')]
    non_moves = [t for t in toks if t['token'] not in ('U','D','L','R')]

    print(f"Written: {out_path}")
    print(f"Total tokens: {total}  (moves={len(moves)}, non-moves={len(non_moves)})")
    print(f"Global index range: {v4['global_start']} → {v4['global_end']}")
    print(f"Non-move tokens:")
    for t in non_moves:
        # find move-step position (# of move tokens before this one)
        move_idx = sum(1 for tt in toks[:toks.index(t)] if tt['token'] in ('U','D','L','R'))
        print(f"  step {move_idx:3d} (global {t['global_idx']:4d}): {t['token']}")

    # step-43 neighbourhood (1-indexed move steps)
    print(f"\nMove steps 38-48 neighbourhood:")
    move_step = 0
    for t in toks:
        if t['token'] in ('U','D','L','R'):
            move_step += 1
            if 38 <= move_step <= 48:
                print(f"  move #{move_step:3d} (global {t['global_idx']:4d}): {t['token']}")


if __name__ == '__main__':
    main()
