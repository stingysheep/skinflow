import type { ScanResult } from './types'

export function buffMarketUrl(result: ScanResult): string | null {
  return result.buff_goods_id > 0
    ? `https://buff.163.com/market/goods?goods_id=${result.buff_goods_id}&from=market#tab=selling`
    : null
}

export function youpinMarketUrl(result: ScanResult): string | null {
  return result.youpin_goods_id > 0
    ? `https://www.youpin898.com/market/goods-list?templateId=${result.youpin_goods_id}`
    : null
}

export function steamMarketUrl(result: ScanResult): string | null {
  return result.csqaq_url
    ?? `https://steamcommunity.com/market/listings/730/${encodeURIComponent(result.market_hash_name)}`
}
