import { act, fireEvent, render, screen } from '@testing-library/react'

import { refreshInventory } from '../../inventory'
import { getSteamSession, startSteamLogin } from '../api/settingsApi'
import { SettingsPage } from './SettingsPage'

vi.mock('../../inventory', () => ({ refreshInventory: vi.fn() }))
vi.mock('../api/settingsApi', () => ({
  clearSteamSession: vi.fn(),
  getSteamSession: vi.fn(),
  startSteamLogin: vi.fn(),
}))

const absent = { status: 'absent' as const, steamid64: null, login_running: false, error: null }
const running = { ...absent, login_running: true }
const active = {
  status: 'active' as const,
  steamid64: '76561198000000000',
  login_running: false,
  error: null,
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(getSteamSession).mockResolvedValueOnce(absent).mockResolvedValueOnce(active)
    vi.mocked(startSteamLogin).mockResolvedValue(running)
    vi.mocked(refreshInventory).mockResolvedValue({ asset_count: 12, observed_at: 1 })
  })

  afterEach(() => vi.useRealTimers())

  it('polls login completion and refreshes inventory automatically', async () => {
    render(<SettingsPage />)
    await act(async () => { await Promise.resolve() })
    fireEvent.click(screen.getByRole('button', { name: '打开 Steam 登录' }))
    await act(async () => { await Promise.resolve() })
    await act(async () => { await vi.advanceTimersByTimeAsync(1000) })

    expect(refreshInventory).toHaveBeenCalledOnce()
    expect(screen.getByText('库存同步完成，共读取 12 件资产。')).toBeInTheDocument()
  })
})
