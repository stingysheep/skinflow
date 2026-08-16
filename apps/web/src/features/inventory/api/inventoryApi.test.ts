import { postJson } from '../../../shared/api/client'
import { refreshInventory, submitListing } from './inventoryApi'

vi.mock('../../../shared/api/client', () => ({
  getJson: vi.fn(),
  postJson: vi.fn(),
}))

it('allows inventory and listing reconciliation to complete before timing out', async () => {
  vi.mocked(postJson).mockResolvedValue({ asset_count: 44, observed_at: 1 })

  await refreshInventory()

  expect(postJson).toHaveBeenCalledWith('/api/inventory/refresh', {}, 120_000)
})

it('keeps a serial listing submission alive beyond the default request timeout', async () => {
  vi.mocked(postJson).mockResolvedValue({ id: 'request-1', status: 'submitted', items: [] })

  await submitListing('preview-1')

  expect(postJson).toHaveBeenCalledWith(
    '/api/listing-requests',
    expect.objectContaining({ preview_id: 'preview-1', confirmed: true }),
    1_200_000,
  )
})
