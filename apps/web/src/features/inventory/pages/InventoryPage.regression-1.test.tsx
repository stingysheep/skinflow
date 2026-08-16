import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { ApiError } from '../../../shared/api/client'
import { getInventory, createListingPreview, refreshInventory, submitListing } from '../api/inventoryApi'
import { InventoryPage } from './InventoryPage'

vi.mock('../api/inventoryApi', () => ({
  createListingPreview: vi.fn(),
  getInventory: vi.fn(),
  refreshInventory: vi.fn(),
  submitListing: vi.fn(),
}))

const mockedGetInventory = vi.mocked(getInventory)
const mockedCreatePreview = vi.mocked(createListingPreview)
const mockedRefreshInventory = vi.mocked(refreshInventory)
const mockedSubmitListing = vi.mocked(submitListing)

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
    mockedSubmitListing.mockResolvedValue({
      id: 'request-1',
      status: 'submitted',
      items: [{ status: 'pending_confirmation' }],
    } as Awaited<ReturnType<typeof submitListing>>)
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

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('确认 Steam 挂单')
    const price = within(dialog).getByRole('textbox', { name: 'AK-47 | 板岩 买家支付价（实际提交）' })
    fireEvent.change(price, { target: { value: '20' } })
    fireEvent.blur(price)
    expect(price).toHaveValue('19.98')
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

  it('clears the submitted selection and removes a fully listed group from tradable holdings', async () => {
    mockedGetInventory.mockReset()
    mockedGetInventory
      .mockResolvedValueOnce({
        status: 'ready',
        items: [],
        groups: [{
          market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '',
          total_quantity: 1, available_quantity: 1, listed_quantity: 0,
          marketable_quantity: 1, tradable_quantity: 1, held_quantity: 1,
        }],
      })
      .mockResolvedValueOnce({
        status: 'ready',
        items: [],
        groups: [{
          market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '',
          total_quantity: 1, available_quantity: 0, listed_quantity: 1,
          marketable_quantity: 0, tradable_quantity: 0, held_quantity: 1,
        }],
      })
    mockedCreatePreview.mockResolvedValue({
      id: 'preview-1',
      status: 'ready',
      expires_at: Date.now() + 60_000,
      items: [{
        id: 'preview-item-1', market_hash_name: 'AK-47 | Slate',
        display_name: 'AK-47 | 板岩', image_url: '', assetid: '1001',
        buyer_pays: 100, steam_fee: 5, publisher_fee: 10,
        seller_proceeds: 85, cost_each: 50, ratio_ppm: 588_235,
      }],
    })

    render(<InventoryPage />)
    fireEvent.change(screen.getByRole('combobox', { name: '库存范围' }), { target: { value: 'held' } })
    fireEvent.change(screen.getByRole('combobox', { name: '交易状态' }), { target: { value: 'tradable' } })
    const selection = await screen.findByRole('checkbox', { name: '选择 AK-47 | 板岩' })
    fireEvent.click(selection)
    fireEvent.click(screen.getByRole('button', { name: '预览挂单' }))
    fireEvent.click(await screen.findByRole('button', { name: '确认并提交' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: '预览挂单' })).toBeDisabled()
    await waitFor(() => expect(screen.queryByText('AK-47 | 板岩')).not.toBeInTheDocument())
  })

  it('unchecks the submitted group when other tradable copies remain', async () => {
    mockedGetInventory.mockReset()
    mockedGetInventory
      .mockResolvedValueOnce({
        status: 'ready',
        items: [],
        groups: [{
          market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '',
          total_quantity: 2, available_quantity: 2, listed_quantity: 0,
          marketable_quantity: 2, tradable_quantity: 2, held_quantity: 2,
        }],
      })
      .mockResolvedValueOnce({
        status: 'ready',
        items: [],
        groups: [{
          market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '',
          total_quantity: 2, available_quantity: 1, listed_quantity: 1,
          marketable_quantity: 1, tradable_quantity: 1, held_quantity: 2,
        }],
      })
    mockedCreatePreview.mockResolvedValue({
      id: 'preview-1',
      status: 'ready',
      expires_at: Date.now() + 60_000,
      items: [{
        id: 'preview-item-1', market_hash_name: 'AK-47 | Slate',
        display_name: 'AK-47 | 板岩', image_url: '', assetid: '1001',
        buyer_pays: 100, steam_fee: 5, publisher_fee: 10,
        seller_proceeds: 85, cost_each: 50, ratio_ppm: 588_235,
      }],
    })

    render(<InventoryPage />)
    const selection = await screen.findByRole('checkbox', { name: '选择 AK-47 | 板岩' })
    fireEvent.click(selection)
    fireEvent.click(screen.getByRole('button', { name: '预览挂单' }))
    fireEvent.click(await screen.findByRole('button', { name: '确认并提交' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(selection).not.toBeChecked())
    expect(screen.getByRole('button', { name: '预览挂单' })).toBeDisabled()
    expect(screen.getByText('AK-47 | 板岩')).toBeInTheDocument()
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
        listed_quantity: 0,
        marketable_quantity: 0,
        tradable_quantity: 0,
        held_quantity: 2,
        average_cost: 100,
      }],
    })

    render(<InventoryPage />)
    fireEvent.change(screen.getByRole('combobox', { name: '库存范围' }), { target: { value: 'held' } })
    fireEvent.change(screen.getByRole('combobox', { name: '交易状态' }), { target: { value: 'all' } })

    expect(await screen.findByText('AK-47 | 已记录持仓')).toBeInTheDocument()
  })

  it('applies trade status filtering inside recorded holdings', async () => {
    mockedGetInventory.mockResolvedValue({
      status: 'ready',
      items: [],
      groups: [
        {
          market_hash_name: 'P90 | Tradable', display_name: 'P90 | 可交易', image_url: '',
          total_quantity: 23, available_quantity: 23, listed_quantity: 0, marketable_quantity: 23,
          tradable_quantity: 23, held_quantity: 23,
        },
        {
          market_hash_name: 'Sawed-Off | Cooldown', display_name: '截短霰弹枪 | 冷却中', image_url: '',
          total_quantity: 19, available_quantity: 19, listed_quantity: 0, marketable_quantity: 0,
          tradable_quantity: 0, held_quantity: 19,
          cooldown_batches: [{ tradable_after: Date.now() + 60_000, quantity: 19 }],
        },
      ],
    })

    render(<InventoryPage />)
    await screen.findByText('P90 | 可交易')
    fireEvent.change(screen.getByRole('combobox', { name: '库存范围' }), { target: { value: 'held' } })
    fireEvent.change(screen.getByRole('combobox', { name: '交易状态' }), { target: { value: 'cooldown' } })

    expect(screen.queryByText('P90 | 可交易')).not.toBeInTheDocument()
    expect(screen.getByText('截短霰弹枪 | 冷却中')).toBeInTheDocument()

    fireEvent.change(screen.getByRole('combobox', { name: '交易状态' }), { target: { value: 'tradable' } })
    expect(screen.getByText('P90 | 可交易')).toBeInTheDocument()
    expect(screen.queryByText('截短霰弹枪 | 冷却中')).not.toBeInTheDocument()
  })

  it('filters Steam-listed holdings separately from cooldown inventory', async () => {
    mockedGetInventory.mockResolvedValue({
      status: 'ready',
      items: [],
      groups: [{
        market_hash_name: 'FAMAS | Grey Ghost (Factory New)',
        display_name: '法玛斯 | 灰色幽灵',
        image_url: '',
        total_quantity: 5,
        available_quantity: 0,
        listed_quantity: 5,
        marketable_quantity: 0,
        tradable_quantity: 0,
        held_quantity: 5,
      }],
    })

    render(<InventoryPage />)
    fireEvent.change(screen.getByRole('combobox', { name: '交易状态' }), { target: { value: 'listed' } })

    expect(await screen.findByText('法玛斯 | 灰色幽灵')).toBeInTheDocument()
    expect(screen.getByText('在售 5')).toBeInTheDocument()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('synchronizes Steam inventory periodically so trade status changes appear', async () => {
    vi.useFakeTimers()
    try {
      render(<InventoryPage />)
      await act(async () => {})
      mockedRefreshInventory.mockClear()
      mockedGetInventory.mockClear()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000)
      })

      expect(mockedRefreshInventory).toHaveBeenCalledTimes(1)
      expect(mockedGetInventory).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('allows direct quantity editing and clears selection when set to zero', async () => {
    mockedGetInventory.mockResolvedValue({
      status: 'ready',
      items: [],
      groups: [{ market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '', total_quantity: 5, available_quantity: 5, listed_quantity: 0, marketable_quantity: 5, tradable_quantity: 5 }],
    })
    render(<InventoryPage />)
    fireEvent.change(screen.getByRole('combobox', { name: '库存范围' }), { target: { value: 'all' } })
    fireEvent.change(screen.getByRole('combobox', { name: '交易状态' }), { target: { value: 'all' } })
    const checkbox = await screen.findByRole('checkbox')
    const quantity = screen.getByRole('textbox', { name: '挂单数量 AK-47 | 板岩' })

    fireEvent.focus(quantity)
    fireEvent.change(quantity, { target: { value: '3' } })
    expect(checkbox).toBeChecked()
    expect(quantity).toHaveValue('3')

    fireEvent.change(quantity, { target: { value: '0' } })
    expect(checkbox).not.toBeChecked()
    expect(quantity).toHaveValue('0')
  })
})
