import { postJson } from '../../../shared/api/client'
import { cancelListingItems } from './listingsApi'

vi.mock('../../../shared/api/client', () => ({
  getJson: vi.fn(),
  postJson: vi.fn(),
}))

describe('cancelListingItems', () => {
  it('splits more than 100 selected listings into valid API batches', async () => {
    vi.mocked(postJson).mockImplementation(async (_path, body) => ({
      items: (body as { item_ids: string[] }).item_ids.map((id) => ({ id, status: 'cancelled', message: null })),
    }))
    const ids = Array.from({ length: 105 }, (_, index) => `item-${index}`)

    const result = await cancelListingItems(ids)

    expect(postJson).toHaveBeenCalledTimes(2)
    expect(vi.mocked(postJson).mock.calls[0][1]).toEqual({ item_ids: ids.slice(0, 100) })
    expect(vi.mocked(postJson).mock.calls[1][1]).toEqual({ item_ids: ids.slice(100) })
    expect(result.items).toHaveLength(105)
  })
})
