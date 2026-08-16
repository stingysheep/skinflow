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
    buyer_pays: number | null
    seller_proceeds: number | null
    sold_receive_total?: number | null
    sold_at?: number | null
    last_checked_at?: number | null
  }>
}

export const getListingRequests = (signal?: AbortSignal) =>
  getJson<{ items: ListingRequest[] }>('/api/listing-requests', signal)

export const reconcileListingRequests = () =>
  postJson<{ checked: number; sold: number; cancelled: number; errors: number }>('/api/listing-requests/reconcile', {})

export async function cancelListingItems(item_ids: string[]) {
  const items: Array<{ id: string; status: string; message: string | null }> = []
  for (let start = 0; start < item_ids.length; start += 100) {
    const batch = item_ids.slice(start, start + 100)
    try {
      const result = await postJson<{ items: Array<{ id: string; status: string; message: string | null }> }>('/api/listing-requests/cancel', { item_ids: batch })
      items.push(...result.items)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'CANCEL_REQUEST_FAILED'
      items.push(...batch.map((id) => ({ id, status: 'failed', message })))
    }
  }
  return { items }
}

export const getListingRequest = (requestId: string, signal?: AbortSignal) =>
  getJson<ListingRequest>(`/api/listing-requests/${encodeURIComponent(requestId)}`, signal)
