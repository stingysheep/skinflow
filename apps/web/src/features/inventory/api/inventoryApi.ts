import { getJson, postJson } from '../../../shared/api/client'
import type { InventoryGroupDetails, InventoryResponse, ListingPreview } from '../model/types'
import type { ListingRequest } from '../../listings/api/listingsApi'

export const getInventory = (signal?: AbortSignal) =>
  getJson<InventoryResponse>('/api/inventory', signal)

export const refreshInventory = () =>
  postJson<{ asset_count: number; observed_at: number }>(
    '/api/inventory/refresh',
    {},
    120_000,
  )

type AssetPreviewInput = { platform: string; appid: number; contextid: string; assetid: string }
type GroupPreviewInput = { market_hash_name: string; quantity: number; buyer_pays?: number }

export const createListingPreview = (items: AssetPreviewInput[] | GroupPreviewInput[]) => {
  const first = items[0] as AssetPreviewInput | GroupPreviewInput | undefined
  return postJson<ListingPreview>('/api/listing-previews', 'market_hash_name' in (first ?? {})
    ? { groups: items as GroupPreviewInput[] }
    : { items: items as AssetPreviewInput[] })
}

export const createGroupedListingPreview = (
  groups: Array<{ market_hash_name: string; quantity: number; buyer_pays?: number }>,
) => postJson<ListingPreview>('/api/listing-previews', { groups })

export const getInventoryGroupDetails = (marketHashName: string) =>
  getJson<InventoryGroupDetails>(
    `/api/inventory/groups/${encodeURIComponent(marketHashName)}/details`,
  )

export const submitListing = (previewId: string, prices: Record<string, number> = {}) =>
  postJson<ListingRequest>(
    '/api/listing-requests',
    { preview_id: previewId, idempotency_key: crypto.randomUUID(), confirmed: true, prices },
    30_000,
  )
