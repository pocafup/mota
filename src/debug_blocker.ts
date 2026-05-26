/**
 * Debug: check what monsters are on F22-F40 and what ATK is needed to beat them
 */
import { scrapeGame } from './scraper';
import { loadFromUniversal } from './loader/format';
import { calcDamage } from './engine';
import { PlayerState } from './types';

async function main() {
  const uFormat = await scrapeGame('https://h5mota.com/games/51/');
  const game = loadFromUniversal(uFormat);

  // Simulate a player who collected all items through each floor
  // and made optimal shop purchases

  // Accumulate stats floor by floor
  let atk = game.initialPlayer.attack;
  let def = game.initialPlayer.defense;
  let hp = game.initialPlayer.hp;
  let gold = 0;

  // Track shop purchases made
  const shopBought = new Set<string>();

  function buyShops(shopId: string, currentGold: number): { atk: number; def: number; gold: number } {
    const shop = game.shops.get(shopId);
    if (!shop) return { atk: 0, def: 0, gold: currentGold };
    let extraAtk = 0, extraDef = 0;
    let g = currentGold;
    let bought = true;
    while (bought) {
      bought = false;
      for (let i = 0; i < shop.items.length; i++) {
        const key = `${shopId},${i}`;
        if (shopBought.has(key)) continue;
        const item = shop.items[i];
        if (g < item.cost) continue;
        g -= item.cost;
        shopBought.add(key);
        if (item.effect === 'attack') extraAtk += item.amount;
        if (item.effect === 'defense') extraDef += item.amount;
        if (item.effect === 'hp') hp += item.amount;
        if (item.effect === 'yellowKey' || item.effect === 'blueKey' || item.effect === 'redKey') {
          // key purchase - ignore for now
        }
        bought = true;
        break;
      }
    }
    return { atk: extraAtk, def: extraDef, gold: g };
  }

  console.log('=== Simulated player progression (all items + greedy shops) ===');
  console.log('Floor | ATK | DEF | Gold | Monsters (DEF) — beatable?');

  for (const [fid, floor] of [...game.floors.entries()].sort((a, b) => a[0] - b[0])) {
    // Collect all items on this floor
    let floorAtk = 0, floorDef = 0, floorHp = 0, floorGold = 0;
    let shopVisited: string | null = null;
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind === 'item') {
          const item = game.items.get(cell.itemId);
          if (!item) continue;
          const ef = item.effect;
          if (ef.type === 'hp')      { floorHp += ef.base * floor.area; }
          if (ef.type === 'hpLarge') { floorHp += ef.base * floor.area; }
          if (ef.type === 'attack')  { floorAtk += ef.base * floor.area; }
          if (ef.type === 'defense') { floorDef += ef.base * floor.area; }
          if (ef.type === 'sword')   { floorAtk += ef.bonus; }
          if (ef.type === 'shield')  { floorDef += ef.bonus; }
          if (ef.type === 'compound') {
            floorAtk += ef.attack; floorDef += ef.defense; floorHp += ef.hp;
          }
        }
        if (cell.kind === 'monster') {
          const m = game.monsters.get(cell.monsterId);
          if (m) floorGold += m.gold;
        }
        if (cell.kind === 'shop') {
          shopVisited = cell.shopId;
        }
      }
    }

    // Apply floor items and gold
    atk += floorAtk; def += floorDef; hp += floorHp; gold += floorGold;

    // Apply shop purchases if there's a shop
    if (shopVisited) {
      const result = buyShops(shopVisited, gold);
      atk += result.atk; def += result.def; gold = result.gold;
    }

    // Check what monsters are on this floor and if they're beatable
    const player: PlayerState = {
      floorId: fid, row: 0, col: 0,
      hp, attack: atk, defense: def, maxHp: hp,
      gold, yellowKeys: 0, blueKeys: 0, redKeys: 0
    };

    const monsters: string[] = [];
    for (let r = 0; r < floor.height; r++) {
      for (let c = 0; c < floor.width; c++) {
        const cell = floor.cells[r][c];
        if (cell.kind === 'monster' && !cell.monsterId.includes('boss')) {
          const m = game.monsters.get(cell.monsterId);
          if (!m) continue;
          const dmg = calcDamage(player, m);
          if (dmg === Infinity || dmg > hp * 0.5) {
            monsters.push(`${m.name}(DEF=${m.defense},dmg=${dmg === Infinity ? '∞' : dmg})`);
          }
        }
      }
    }

    if (fid >= 22 && fid <= 50) {
      const shopInfo = shopVisited ? `[SHOP:${shopVisited}]` : '';
      console.log(`F${fid}: ATK=${atk} DEF=${def} HP=${hp} Gold=${gold} ${shopInfo}`);
      if (monsters.length > 0) {
        console.log(`  HARD MONSTERS: ${monsters.join(', ')}`);
      }
    }
  }

  // Final state
  console.log('\n=== Max stats with all items + all shops ===');
  console.log(`ATK=${atk} DEF=${def} HP=${hp} Gold=${gold}`);

  // Boss fight
  const bossFloor = game.floors.get(game.bossLocation.floorId)!;
  const bossCell = bossFloor.cells[game.bossLocation.row][game.bossLocation.col];
  if (bossCell.kind === 'monster') {
    const boss = game.monsters.get(bossCell.monsterId);
    if (boss) {
      const player: PlayerState = {
        floorId: 0, row: 0, col: 0, hp, attack: atk, defense: def, maxHp: hp,
        gold, yellowKeys: 0, blueKeys: 0, redKeys: 0
      };
      const dmg = calcDamage(player, boss);
      console.log(`Boss fight: damage=${dmg}, player HP=${hp} → ${hp > dmg ? 'SURVIVE' : 'DIE'}`);
    }
  }
}

main().catch(console.error);
