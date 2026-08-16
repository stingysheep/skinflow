export type InventoryAsset = {
  platform: 'steam'
  appid: 730
  contextid: string
  assetid: string
  market_hash_name: string
  display_name: string
  image_url: string
  marketable: boolean
  tradable: boolean
  hold_text: string | null
  wear_text?: string | null
  status: 'available' | 'missing' | 'listed' | 'sold'
}

export const inventoryAssetKey = (item: Pick<InventoryAsset, 'platform' | 'appid' | 'contextid' | 'assetid'>) =>
  `${item.platform}:${item.appid}:${item.contextid}:${item.assetid}`

export type InventoryResponse = {
  status: 'ready' | 'session_required'
  items: InventoryAsset[]
  groups?: InventoryGroup[]
  message?: string
  steamid64?: string
}

export type InventoryGroup = {
  market_hash_name: string
  display_name: string
  image_url: string
  wear_text?: string | null
  total_quantity: number
  available_quantity: number
  listed_quantity: number
  marketable_quantity: number
  tradable_quantity: number
  average_cost?: number | null
  held_quantity?: number
  cooldown_batches?: Array<{
    tradable_after: number | null
    quantity: number
    hold_text?: string | null
  }>
}

export type InventoryGroupDetails = {
  market_hash_name: string
  display_name: string
  image_url: string
  average_cost: number | null
  current: {
    observed_at: number | null
    lowest_ask: number | null
    highest_bid: number | null
    ask_levels: Array<{ price: number; quantity: number }>
    bid_levels: Array<{ price: number; quantity: number }>
  }
  trend: Array<{
    observed_at: number | null
    median_price: number | null
    lowest_ask: number | null
    highest_bid: number | null
    quantity?: number | null
    source?: 'csqaq' | 'legacy_snapshot'
  }>
}

export type ListingPreview = {
  id: string
  status: string
  expires_at: number
  items: Array<{
    id: string
    market_hash_name: string
    display_name: string
    image_url: string
    assetid: string
    buyer_pays: number
    steam_fee: number
    publisher_fee: number
    seller_proceeds: number
    cost_each: number | null
    ratio_ppm: number | null
    ask_levels?: Array<{ price: number; quantity: number }>
    bid_levels?: Array<{ price: number; quantity: number }>
    trend?: Array<{ observed_at: number | null; median_price: number | null; lowest_ask: number | null; highest_bid: number | null; quantity?: number | null; source?: 'csqaq' | 'legacy_snapshot' }>
  }>
}
