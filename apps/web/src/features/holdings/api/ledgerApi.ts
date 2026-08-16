import { deleteJson, getJson, postJson, putJson } from '../../../shared/api/client'

export type Holding = {
  market_hash_name: string
  display_name: string
  image_url: string
  wear_text?: string | null
  game: string
  quantity: number
  sold_quantity: number
  open_quantity: number
  invested: number
  open_cost: number
  lots: number
}

export const getHoldings = (signal?: AbortSignal) =>
  getJson<{ items: Holding[] }>('/api/holdings', signal)

export type LedgerCatalogItem = { market_hash_name: string; display_name: string; image_url: string; open_quantity: number }

export const searchLedgerCatalog = (query: string, signal?: AbortSignal) =>
  getJson<{ items: LedgerCatalogItem[] }>(`/api/ledger/catalog?q=${encodeURIComponent(query)}&limit=20`, signal)

export const createPurchase = (body: {
  market_hash_name: string
  quantity: number
  cost_each: number
  venue: string
  pending_delivery: boolean
}) => postJson<{ id: string; status: string }>('/api/purchases', body)

export const createSale = (body: {
  market_hash_name: string
  quantity: number
  receive_total: number
}) => postJson<{ fills: unknown[] }>('/api/sales', body)

export const updateHoldingAverageCost = (marketHashName: string, costEach: number) =>
  putJson<{ market_hash_name: string; cost_each: number }>('/api/holdings/' + encodeURIComponent(marketHashName), { cost_each: costEach })

export const deleteHolding = (marketHashName: string) =>
  deleteJson<{ market_hash_name: string; deleted_quantity: number }>('/api/holdings/' + encodeURIComponent(marketHashName))
