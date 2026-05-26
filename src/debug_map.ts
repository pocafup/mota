import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';
import { getReachable } from './engine';
import { GameState, PlayerState } from './types';

async function main() {
  const fmt = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(fmt);

  // Show floor 1 and 2 layout
  for (let fid = 1; fid <= 3; fid++) {
    const floor = game.floors.get(fid)!;
    if (!floor) continue;
    console.log(`\n=== Floor ${fid} (area=${floor.area}) startPos=(${floor.startPos.row},${floor.startPos.col}) ===`);
    for (let r = 0; r < floor.height; r++) {
      const row = floor.cells[r].map(cell => {
        switch (cell.kind) {
          case 'empty': return '.';
          case 'wall': return '#';
          case 'stairsUp': return 'U';
          case 'stairsDown': return 'D';
          case 'monster': return 'm';
          case 'item': {
            const ef = game.items.get(cell.itemId)?.effect;
            if (!ef) return 'i';
            if (ef.type === 'yellowKey') return 'y';
            if (ef.type === 'blueKey') return 'b';
            if (ef.type === 'redKey') return 'r';
            if (ef.type === 'hp' || ef.type === 'hpLarge') return 'h';
            if (ef.type === 'attack' || ef.type === 'sword') return 'a';
            return 'i';
          }
          case 'door': return cell.color === 'yellow' ? 'Y' : cell.color === 'blue' ? 'B' : 'R';
          case 'shop': return '$';
          case 'npc': return '@';
          default: return '?';
        }
      }).join('');
      console.log(`  ${String(r).padStart(2)} ${row}`);
    }
  }

  // Check initial reachable positions from floor 1
  const initPlayer: PlayerState = {
    ...game.initialPlayer, floorId: game.startFloor,
    row: game.startPos.row, col: game.startPos.col,
  };
  const initState: GameState = { player: initPlayer, consumed: new Set(), consumedHash: 0, shopBought: new Set() };
  const reachable = getReachable(initState, game);
  console.log(`\n=== Initial reachable from (F${game.startFloor}, ${game.startPos.row}, ${game.startPos.col}) ===`);
  console.log(`  ${reachable.length} positions:`, reachable.slice(0, 20).map(p => `F${p.floorId}(${p.row},${p.col})`).join(', '));
}
main().catch(console.error);
