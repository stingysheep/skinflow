import { render } from '@testing-library/react'

import type { ScanResult } from '../model/types'
import { ScanResultTable } from './ScanResultTable'

const result: ScanResult = {
  market_hash_name: 'AK-47 | Slate',
  name: 'AK-47 | 板岩',
  image_url: '',
  buff_goods_id: 1,
  youpin_goods_id: 2,
  acquisition_platform: 'buff',
  acquisition_lowest_ask: 100,
  buff_lowest_ask: 100,
  youpin_lowest_ask: 110,
  steam_highest_bid: 200,
  steam_lowest_ask: 220,
  steam_transaction_price: 215,
  buff_observed_at: null,
  youpin_observed_at: null,
  steam_observed_at: null,
  daily_volume: 10,
  fee_policy_version: 'steam-cs2-cny-v1',
  buff_depth: 10,
  youpin_depth: 10,
  steam_bid_depth: 10,
  steam_ask_depth: 10,
  recommendation_unavailable: false,
  recommendation_price: 219,
  recommendation_gross: 219,
  recommendation_fees: 33,
  recommendation_seller_proceeds: 186,
  queue_ahead: 0,
  eta_estimate_days: null,
  recommendation_confidence: 'high',
  curves: [{
    quantity: 1,
    cost_total: 100,
    immediate_ratio_ppm: 500_000,
    recommended_ratio_ppm: 537_634,
    market_ask_ratio_ppm: 454_545,
  }],
}

describe('ScanResultTable regression', () => {
  it('renders result and details rows without a missing-key warning', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    render(
      <ScanResultTable
        results={[result]}
        mode="listing"
        selectedName={null}
        onSelect={vi.fn()}
        filter="all"
        onFilter={vi.fn()}
      />,
    )

    expect(consoleError).not.toHaveBeenCalledWith(
      expect.stringContaining('unique "key" prop'),
    )
    consoleError.mockRestore()
  })
})
