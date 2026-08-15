import type { ScanMode, ScanResult } from './types'

export function modeRatio(result: ScanResult, mode: ScanMode): number | null {
  const first = result.curves[0]
  const curveRatio = mode === 'listing'
    ? first?.recommended_ratio_ppm ?? null
    : first?.immediate_ratio_ppm ?? null
  if (curveRatio !== null && curveRatio !== undefined) return curveRatio
  // A partial row can still contain CSQAQ's summary bid while Steam's
  // histogram is temporarily rate-limited. Keep the ratio useful instead of
  // hiding the row until a full ten-level snapshot is available.
  if (result.acquisition_lowest_ask == null) return null
  const proceeds = mode === 'listing'
    ? result.recommendation_seller_proceeds
    : result.steam_bid_seller_proceeds
  return proceeds && proceeds > 0
    ? Math.floor(result.acquisition_lowest_ask * 1_000_000 / proceeds)
    : null
}

export function modeSteamPrice(result: ScanResult, mode: ScanMode): number | null {
  return mode === 'listing' ? result.recommendation_price : result.steam_highest_bid
}

export function actualProceeds(result: ScanResult, mode: ScanMode): number | null {
  return mode === 'listing' ? result.recommendation_seller_proceeds : result.steam_bid_seller_proceeds ?? null
}

export function modeLabel(mode: ScanMode): string {
  return mode === 'listing' ? '挂底价' : '丢求购'
}

export function modeRatioLabel(mode: ScanMode): string {
  return mode === 'listing' ? '挂底价比例' : '丢求购比例'
}

export function resultIsReady(result: ScanResult, mode: ScanMode): boolean {
  return mode === 'listing'
    ? !result.recommendation_unavailable
    : result.steam_highest_bid !== null
}

export function sourceDepth(result: ScanResult): number {
  return result.acquisition_platform === 'youpin' ? result.youpin_depth : result.buff_depth
}

export function sourceLabel(result: ScanResult): string {
  return result.acquisition_platform === 'youpin' ? '悠悠' : 'BUFF'
}
