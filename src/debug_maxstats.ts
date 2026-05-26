/**
 * Sum up all available stat upgrades in the game to check theoretical max stats.
 */
import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';
import { calcDamage } from './engine';
import { PlayerState } from './types';

async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);

  let totalAtk = 0;
  let totalDef = 0;
  let totalHp = 0;
  let totalGold = 0;
  let totalYellowKeys = 0;
  let totalBlueKeys = 0;
  let totalRedKeys = 0;

  console.log('=== Items by floor (ATK/DEF/HP gains) ===');
  for (const [fid, floor] of [...game.floors.entries()].sort((a, b) => a[0] - b[0])) {
    let floorAtk = 0, floorDef = 0, floorHp = 0, floorKeys = '';
    const itemDetails: string[] = [];

    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind === 'item') {
          const item = game.items.get(cell.itemId);
          if (!item) continue;
          const ef = item.effect;
          switch (ef.type) {
            case 'hp':      { const v = ef.base * floor.area; floorHp += v; totalHp += v; itemDetails.push(`HP+${v}`); break; }
            case 'hpLarge': { const v = ef.base * floor.area; floorHp += v; totalHp += v; itemDetails.push(`HP+${v}(L)`); break; }
            case 'attack':  { const v = ef.base * floor.area; floorAtk += v; totalAtk += v; itemDetails.push(`ATK+${v}`); break; }
            case 'defense': { const v = ef.base * floor.area; floorDef += v; totalDef += v; itemDetails.push(`DEF+${v}`); break; }
            case 'sword':   { floorAtk += ef.bonus; totalAtk += ef.bonus; itemDetails.push(`ATK+${ef.bonus}(sword)`); break; }
            case 'shield':  { floorDef += ef.bonus; totalDef += ef.bonus; itemDetails.push(`DEF+${ef.bonus}(shield)`); break; }
            case 'yellowKey': { totalYellowKeys++; floorKeys += 'Y'; break; }
            case 'blueKey':   { totalBlueKeys++; floorKeys += 'B'; break; }
            case 'redKey':    { totalRedKeys++; floorKeys += 'R'; break; }
            case 'compound':  {
              floorAtk += ef.attack; totalAtk += ef.attack;
              floorDef += ef.defense; totalDef += ef.defense;
              floorHp += ef.hp; totalHp += ef.hp;
              itemDetails.push(`ATK+${ef.attack} DEF+${ef.defense} HP+${ef.hp}`);
              break;
            }
          }
        }
        if (cell.kind === 'monster') {
          const m = game.monsters.get(cell.monsterId);
          if (m) totalGold += m.gold;
        }
      }
    }
    if (floorAtk > 0 || floorDef > 0 || floorHp > 0) {
      console.log(`F${fid}: ATK+${floorAtk} DEF+${floorDef} HP+${floorHp} ${floorKeys} [${itemDetails.join(', ')}]`);
    }
  }

  console.log('\n=== Shop items ===');
  for (const [sid, shop] of game.shops) {
    console.log(`Shop ${sid}:`);
    for (const item of shop.items) {
      console.log(`  ${item.label}: ${item.effect}+${item.amount} cost=${item.cost} ${item.repeatable ? '(repeatable)' : '(once)'}`);
    }
  }

  const maxPlayer: PlayerState = {
    ...game.initialPlayer,
    floorId: 0, row: 0, col: 0,
    attack: game.initialPlayer.attack + totalAtk,
    defense: game.initialPlayer.defense + totalDef,
    hp: game.initialPlayer.hp + totalHp,
    gold: totalGold,
    yellowKeys: totalYellowKeys,
    blueKeys: totalBlueKeys,
    redKeys: totalRedKeys,
  };

  console.log(`\n=== Theoretical maximum stats (items only, no shops) ===`);
  console.log(`ATK: ${game.initialPlayer.attack} + ${totalAtk} = ${maxPlayer.attack}`);
  console.log(`DEF: ${game.initialPlayer.defense} + ${totalDef} = ${maxPlayer.defense}`);
  console.log(`HP:  ${game.initialPlayer.hp} + ${totalHp} = ${maxPlayer.hp}`);
  console.log(`Gold: ${totalGold}`);
  console.log(`Keys: Y=${totalYellowKeys} B=${totalBlueKeys} R=${totalRedKeys}`);

  // Boss fight with max stats
  const bossFloor = game.floors.get(game.bossLocation.floorId)!;
  const bossCell = bossFloor.cells[game.bossLocation.row][game.bossLocation.col];
  if (bossCell.kind === 'monster') {
    const boss = game.monsters.get(bossCell.monsterId);
    if (boss) {
      console.log(`\n=== Boss fight (max item stats) ===`);
      console.log(`Boss: ATK=${boss.attack} DEF=${boss.defense} HP=${boss.hp}`);
      const dmg = calcDamage(maxPlayer, boss);
      console.log(`Fight damage: ${dmg}`);
      console.log(`Player would ${maxPlayer.hp > dmg ? 'SURVIVE' : 'DIE'} (HP=${maxPlayer.hp} vs dmg=${dmg})`);
    }
  }
}

main().catch(console.error);
