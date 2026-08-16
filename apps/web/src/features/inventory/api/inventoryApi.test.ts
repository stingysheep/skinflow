import { postJson } from '../../../shared/api/client'
import { refreshInventory } from './inventoryApi'

vi.mock('../../../shared/api/client', () => ({
  getJson: vi.fn(),
  postJson: vi.fn(),
}))

it('allows inventory and listing reconciliation to complete before timing out', async () => {
  vi.mocked(postJson).mockResolvedValue({ asset_count: 44, observed_at: 1 })

  await refreshInventory()

  expect(postJson).toHaveBeenCalledWith('/api/inventory/refresh', {}, 120_000)
})
