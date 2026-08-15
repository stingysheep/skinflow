export type ScanStatus = 'queued' | 'running' | 'cancelling' | 'cancelled' | 'succeeded' | 'failed'
export type ScanMode = 'listing' | 'buy_order'
export type AcquisitionPlatform = 'buff' | 'youpin'

export type ScanCriteria = {
  candidateLimit: number
  mode: ScanMode
  platforms: AcquisitionPlatform[]
  minPriceYuan: string
  maxPriceYuan: string
  minDailyVolume: number
}

export type CurvePoint = {
  quantity: number
  cost_total: number
  immediate_ratio_ppm: number | null
  recommended_ratio_ppm: number | null
  market_ask_ratio_ppm: number | null
}

export type MarketLevel = { price: number; quantity: number }
export type SteamTrendPoint = { observed_at: number | null; price: number | null; quantity?: number | null }

export type ScanResult = {
  job_id?: string
  market_hash_name: string
  name: string
  image_url: string
  buff_goods_id: number
  youpin_goods_id: number
  acquisition_platform: AcquisitionPlatform
  acquisition_lowest_ask: number | null
  buff_lowest_ask: number | null
  youpin_lowest_ask: number | null
  steam_highest_bid: number | null
  steam_lowest_ask: number | null
  steam_transaction_price: number | null
  steam_bid_seller_proceeds?: number | null
  csqaq_url?: string | null
  buff_observed_at: number | null
  youpin_observed_at: number | null
  steam_observed_at: number | null
  daily_volume: number | null
  fee_policy_version: string
  buff_depth: number
  youpin_depth: number
  steam_bid_depth: number
  steam_ask_depth: number
  steam_ask_levels?: MarketLevel[]
  steam_bid_levels?: MarketLevel[]
  steam_trend?: SteamTrendPoint[]
  recommendation_unavailable: boolean
  recommendation_price: number | null
  recommendation_gross: number | null
  recommendation_fees: number | null
  recommendation_seller_proceeds: number | null
  queue_ahead: number | null
  eta_estimate_days: number | null
  recommendation_confidence: string | null
  curves: CurvePoint[]
}

export type PlatformTrendPoint = { observed_at: number | null; price: number | null; quantity?: number | null }
export type ScanCharts = { market_hash_name: string; trends: Record<string, PlatformTrendPoint[]> }

export type ScanEvent = {
  schema_version: 1
  job_id: string
  sequence: number
  type: string
  payload: Record<string, unknown>
}

export type ScanConnection = 'idle' | 'connected' | 'reconnecting'

export type ScanJob = { job_id: string; status: ScanStatus; result_count: number; failure_code: string | null }
