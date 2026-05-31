"""
Trace hero path in MT10 for all 4 visits by:
1. Decoding the h5route action list
2. Segmenting actions by floor
3. Simulating hero movement on MT10 map (with door/monster pass-through)
4. Determining whether hero crosses (6,3) and when (6,5) is triggered
"""
import json
import sys
from pathlib import Path
from lzstring import LZString

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "games51"


# ── route decoding ────────────────────────────────────────────────────────────

def decompress(s: str) -> str:
    return LZString().decompressFromBase64(s)


def parse_rle(raw: str) -> list[str]:
    """Expand RLE-encoded route string into individual action tokens."""
    actions = []
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if raw[i:i+3] == 'FMT':      # floor transition FMT<digits>:
            j = i + 3
            while j < n and raw[j].isdigit():
                j += 1
            floor_num = raw[i+3:j]
            if j < n and raw[j] == ':':
                j += 1
            actions.append(f'FLOOR:MT{floor_num}')
            i = j
        elif c in 'UDLR':             # move (with optional repeat count)
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            count = int(raw[i:j]) if j > i else 1
            i = j
            actions.extend([c] * count)
        elif c == 'C':                # dialog choice
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            i = j
            actions.append('CHOICE')
        elif c == 'I':                # item use
            i += 1
            j = i
            while j < n and raw[j].isdigit():
                j += 1
            if j < n and raw[j] == ':':
                j += 1
            actions.append('ITEM')
            i = j
        elif c.isalpha():             # unknown (K = key?, M = move event?)
            j = i + 1
            while j < n and raw[j].isdigit():
                j += 1
            token = raw[i:j]
            if j < n and raw[j] == ':':
                j += 1
                token += ':'
            actions.append(f'UNK:{token}')
            i = j
        else:
            i += 1
    return actions


def load_route(path: Path) -> list[str]:
    raw = decompress(path.read_text(encoding='utf-8').strip())
    outer = json.loads(raw)
    route_raw = decompress(outer['route'])
    return parse_rle(route_raw)


# ── map helpers ───────────────────────────────────────────────────────────────

WALL_TILES  = {1, 4, 330}        # hard impassable
SPECIAL_DOOR_TILE = 85            # specialDoor (no key in this game → impassable)
DOOR_TILES  = {81, 82, 83, 84, 86}   # regular doors (passable with key)
STAIR_TILES = {87, 88}

def tile_passable(tile: int, treat_special_door_as_wall: bool = True) -> bool:
    """Return True if hero can move onto this tile."""
    if tile in WALL_TILES:
        return False
    if treat_special_door_as_wall and tile == SPECIAL_DOOR_TILE:
        return False
    return True


def apply_delta(x: int, y: int, direction: str):
    if direction == 'U': return x, y - 1
    if direction == 'D': return x, y + 1
    if direction == 'L': return x - 1, y
    if direction == 'R': return x + 1, y
    return x, y


# ── per-visit simulation ──────────────────────────────────────────────────────

def segment_visits(actions: list[str], floor_id: str) -> list[tuple[int, list[str]]]:
    """
    Returns list of (start_index_in_actions, [actions_within_floor])
    for each visit to floor_id.
    """
    visits = []
    current_floor = None
    visit_start = None
    visit_actions: list[str] = []

    for i, act in enumerate(actions):
        if act.startswith('FLOOR:'):
            dest = act[6:]
            if current_floor == floor_id:
                # Leaving MT10 — close current visit
                visits.append((visit_start, visit_actions))
                visit_actions = []
            if dest == floor_id:
                # Entering MT10
                current_floor = floor_id
                visit_start = i
                visit_actions = []
            else:
                current_floor = dest
        elif current_floor == floor_id:
            visit_actions.append(act)

    # If route ends inside MT10
    if current_floor == floor_id and visit_actions:
        visits.append((visit_start, visit_actions))

    return visits


def simulate_visit(visit_seq: list[str], map_grid: list[list[int]],
                   start: tuple[int, int]) -> list[tuple[int, int]]:
    """
    Walk the hero through visit_seq starting from `start` on `map_grid`.
    Returns list of (x,y) positions visited (including start).
    Only UDLR actions move the hero; CHOICE/ITEM/UNK are skipped.
    Stops on impassable tile (reports and continues).
    """
    x, y = start
    path = [(x, y)]
    h = len(map_grid)
    w = len(map_grid[0]) if h > 0 else 0

    for act in visit_seq:
        if act not in ('U', 'D', 'L', 'R'):
            continue
        nx, ny = apply_delta(x, y, act)
        if 0 <= nx < w and 0 <= ny < h and tile_passable(map_grid[ny][nx]):
            x, y = nx, ny
            path.append((x, y))
        else:
            # Blocked — record attempted move with '!' suffix but DON'T advance
            tile = map_grid[ny][nx] if 0 <= nx < w and 0 <= ny < h else -1
            path.append(('!', nx, ny, tile, act))
    return path


def try_all_starts(visit_seq: list[str], map_grid: list[list[int]],
                   target_end: tuple[int, int] | None = None
                   ) -> list[tuple[tuple[int,int], list]]:
    """
    Try every non-wall start position on the map.
    Returns starts whose path has no blocked moves AND
    (if target_end given) ends at target_end.
    """
    h = len(map_grid)
    w = len(map_grid[0])
    results = []
    for sy in range(h):
        for sx in range(w):
            if not tile_passable(map_grid[sy][sx]):
                continue
            path = simulate_visit(visit_seq, map_grid, (sx, sy))
            has_block = any(isinstance(p, tuple) and p[0] == '!' for p in path)
            if has_block:
                continue
            if target_end is None or (isinstance(path[-1], tuple)
                                      and len(path[-1]) == 2
                                      and path[-1] == target_end):
                results.append(((sx, sy), path))
    return results


# ── landing position logic ────────────────────────────────────────────────────

def get_floor_index(floor_ids: list[str], fid: str) -> int:
    return floor_ids.index(fid) if fid in floor_ids else -1


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    h5route = next(ROOT.glob('51_*.h5route'))
    print(f"Route: {h5route.name}")

    actions = load_route(h5route)
    print(f"Total actions: {len(actions)}")

    # Segment MT10 visits
    visits = segment_visits(actions, 'MT10')
    print(f"\nMT10 visits: {len(visits)}")
    for i, (idx, seq) in enumerate(visits, 1):
        moves = [a for a in seq if a in 'UDLR']
        print(f"  Visit {i}: global action index {idx}, "
              f"{len(seq)} tokens total, {len(moves)} move steps")
        print(f"    Actions: {seq}")

    # Load MT10 map
    mt10 = json.loads((DATA / "floors" / "MT10.json").read_text(encoding='utf-8'))
    grid = mt10['map']  # grid[y][x]
    print(f"\nMT10 map: {mt10['height']}x{mt10['width']}")

    # For each visit, determine preceding floor (for landing logic)
    # Build per-visit "preceding floor" table
    preceding_floor = {}
    current = None
    visit_counter = {0: 0}  # visit index
    vi = 0
    for i, act in enumerate(actions):
        if act.startswith('FLOOR:'):
            dest = act[6:]
            if dest == 'MT10':
                preceding_floor[vi] = current
                vi += 1
            current = dest

    print(f"\nPreceding floors for MT10 visits:")
    for i, (idx, seq) in enumerate(visits):
        prev = preceding_floor.get(i, '?')
        print(f"  Visit {i+1}: came from {prev}")

    # MT10 staircase positions (from changeFloor + tiles.json)
    # downFloor(88) at (1,11) = arrives from lower-indexed floor
    # upFloor(87)   at (6,11) = arrives from higher-indexed floor
    # Floor ordering: MT1=0, MT2=1, ..., MT10=9
    STAIR_DOWN = (1, 11)   # arrives when fromFloor < MT10
    STAIR_UP   = (6, 11)   # arrives when fromFloor > MT10

    mt10_index = 9   # 0-based index in floor list [MT1..MT10..]
    floor_order = {f'MT{n}': n-1 for n in range(1, 51)}

    # For Visit 4 (main visit), determine start and simulate
    print("\n" + "="*70)
    for vi, (idx, seq) in enumerate(visits, 1):
        prev_floor = preceding_floor.get(vi-1, None)
        if prev_floor and prev_floor in floor_order:
            prev_idx = floor_order[prev_floor]
            if prev_idx <= mt10_index:
                start = STAIR_DOWN
                stair_label = "downFloor (1,11)"
            else:
                start = STAIR_UP
                stair_label = "upFloor (6,11)"
        else:
            start = STAIR_DOWN
            stair_label = "downFloor (1,11) [assumed]"

        moves = [a for a in seq if a in 'UDLR']
        print(f"\n=== Visit {vi} (from {prev_floor} → stair={stair_label}) ===")
        print(f"Move sequence ({len(moves)} steps): {' '.join(moves)}")

        path = simulate_visit(seq, grid, start)
        clean = [p for p in path if isinstance(p, tuple) and len(p) == 2]
        blocked = [p for p in path if isinstance(p, tuple) and p[0] == '!']

        print(f"Path length: {len(clean)} positions")
        if blocked:
            print(f"BLOCKED moves: {len(blocked)}")
            for b in blocked[:5]:
                print(f"  Attempted ({b[1]},{b[2]}) tile={b[3]} dir={b[4]}")

        # Check if (6,3) appears
        passes_63 = (6, 3) in clean
        # Check if (6,5) appears (ambush trigger)
        passes_65 = (6, 5) in clean
        print(f"Passes (6,3): {passes_63}")
        print(f"Passes (6,5): {passes_65}")
        print(f"Final position: {clean[-1] if clean else 'N/A'}")

        if blocked:
            # Try all starts to find which start works
            print(f"\n  Trying all valid start positions...")
            valid = try_all_starts(moves, grid)
            if valid:
                print(f"  Valid starts: {[(s, len(p)) for s, p in valid]}")
            else:
                print("  No valid start found with clean path.")
                # Show which starts get furthest
                best_len = 0
                best_start = None
                best_path = None
                h = len(grid)
                w = len(grid[0])
                for sy in range(h):
                    for sx in range(w):
                        if not tile_passable(grid[sy][sx]):
                            continue
                        p = simulate_visit(moves, grid, (sx, sy))
                        clean_p = [x for x in p if isinstance(x, tuple) and len(x)==2]
                        if len(clean_p) > best_len:
                            best_len = len(clean_p)
                            best_start = (sx, sy)
                            best_path = p
                print(f"  Furthest: start={best_start}, {best_len} clean steps")
                if best_path:
                    print(f"  Path: {[p for p in best_path if isinstance(p, tuple) and len(p)==2]}")
                    blk = [p for p in best_path if isinstance(p, tuple) and p[0]=='!']
                    if blk:
                        print(f"  First block: {blk[0]}")


if __name__ == '__main__':
    main()
