import { getJson, postJson } from '../../../shared/api/client'

export type ListingRequest = {
  id: string
  status: string
  created_at: number
  completed_at: number | null
  items: Array<{
    id: string
    assetid: string
    status: string
    steam_listing_id: string | null
    message: string | null
    market_hash_name: string
    display_name: string
    image_url: string
    wear_text?: string | null
    cost_each: number | null
    buyer_pays: number
    seller_proceeds: number
  }>
}

export const getListingRequests = (signal?: AbortSignal) =>
  getJson<{ items: ListingRequest[] }>('/api/listing-requests', signal)

export const reconcileListingRequests = () =>
  postJson<{ checked: number; sold: number; cancelled: number; errors: number }>('/api/listing-requests/reconcile', {})

export const cancelListingItems = (item_ids: string[]) =>
  postJson<{ items: Array<{ id: string; status: string; message: string | null }> }>('/api/listing-requests/cancel', { item_ids })

export const getListingRequest = (requestId: string, signal?: AbortSignal) =>
  getJson<ListingRequest>(`/api/listing-requests/${encodeURIComponent(requestId)}`, signal)
