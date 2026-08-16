import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ApiError } from '../../../shared/api/client'
import { getInventory, createListingPreview, refreshInventory } from '../api/inventoryApi'
import { InventoryPage } from './InventoryPage'

vi.mock('../api/inventoryApi', () => ({
  createListingPreview: vi.fn(),
  getInventory: vi.fn(),
  refreshInventory: vi.fn(),
}))

const mockedGetInventory = vi.mocked(getInventory)
const mockedCreatePreview = vi.mocked(createListingPreview)
const mockedRefreshInventory = vi.mocked(refreshInventory)

describe('InventoryPage listing preview regression', () => {
  beforeEach(() => {
    mockedGetInventory.mockResolvedValue({
      status: 'ready',
      items: [{
        platform: 'steam',
        appid: 730,
        contextid: '2',
        assetid: '1001',
        market_hash_name: 'AK-47 | Slate',
        display_name: 'AK-47 | 板岩',
        image_url: '',
        marketable: true,
        tradable: true,
        hold_text: null,
        status: 'available',
      }],
    })
    mockedCreatePreview.mockRejectedValue(new ApiError('没有当前 Steam 行情快照', 409, 'CONFLICT'))
    mockedRefreshInventory.mockResolvedValue({ asset_count: 0, observed_at: Date.now() })
  })

  it('shows a visible error when preview creation is rejected', async () => {
    render(<InventoryPage />)

    const selection = await screen.findByRole('checkbox')
    fireEvent.click(selection)
    fireEvent.click(screen.getByRole('button', { name: '预览挂单' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('无法预览挂单'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens the controlled preview dialog after a successful request', async () => {
    mockedCreatePreview.mockResolvedValue({
      id: 'preview-1',
      status: 'ready',
      expires_at: Date.now() + 60_000,
      items: [{
        id: 'preview-item-1',
        market_hash_name: 'AK-47 | Slate',
        display_name: 'AK-47 | 板岩',
        image_url: '',
        assetid: '1001',
        buyer_pays: 100,
        steam_fee: 5,
        publisher_fee: 10,
        seller_proceeds: 85,
        cost_each: 50,
        ratio_ppm: 588_235,
      }],
    })

    render(<InventoryPage />)
    fireEvent.click(await screen.findByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: '预览挂单' }))

    expect(await screen.findByRole('dialog')).toHaveTextContent('确认 Steam 挂单')
  })

  it('clears selections that disappear after an inventory refresh', async () => {
    mockedGetInventory.mockReset()
    mockedGetInventory
      .mockResolvedValueOnce({
        status: 'ready',
        items: [{
          platform: 'steam', appid: 730, contextid: '2', assetid: '1001',
          market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '',
          marketable: true, tradable: true, hold_text: null, status: 'available',
        }],
      })
      .mockResolvedValueOnce({ status: 'ready', items: [] })

    render(<InventoryPage />)
    fireEvent.click(await screen.findByRole('checkbox'))
    expect(screen.getByRole('button', { name: '预览挂单' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: '刷新库存' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '预览挂单' })).toBeDisabled())
    expect(screen.queryByText('所选资产已失效')).not.toBeInTheDocument()
  })

  it('shows recorded holdings even when Steam no longer returns the asset', async () => {
    mockedGetInventory.mockResolvedValue({
      status: 'ready',
      items: [],
      groups: [{
        market_hash_name: 'AK-47 | Held',
        display_name: 'AK-47 | 已记录持仓',
        image_url: '',
        total_quantity: 0,
        available_quantity: 0,
        marketable_quantity: 0,
        tradable_quantity: 0,
        held_quantity: 2,
        average_cost: 100,
      }],
    })

    render(<InventoryPage />)
    fireEvent.change(screen.getByRole('combobox', { name: '库存范围' }), { target: { value: 'held' } })

    expect(await screen.findByText('AK-47 | 已记录持仓')).toBeInTheDocument()
  })
})
