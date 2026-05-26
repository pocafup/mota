import { GameState, GameData } from './types';
import { buyShopItem, cloneState } from './engine';

/** 商店贪心购买（供渲染器使用，避免循环引用）
 * Always buy all affordable items. The upper-bound comparison was preventing
 * any purchases because the F47 shop's cheap rate (2 gold/ATK) made buying
 * from earlier shops (10 gold/ATK) appear to hurt the upper bound — causing
 * the player to skip all shop upgrades and fail mid-game guardians.
 */
export function greedyShopBuyForRender(
  state: GameState,
  shopId: string,
  data: GameData
): GameState {
  const shop = data.shops.get(shopId);
  if (!shop) return state;
  let cur = cloneState(state);
  let improved = true;
  while (improved) {
    improved = false;
    for (let i = 0; i < shop.items.length; i++) {
      const res = buyShopItem(cur, shopId, i, data);
      if (res) {
        cur = res;
        improved = true;
        break;
      }
    }
  }
  return cur;
}
