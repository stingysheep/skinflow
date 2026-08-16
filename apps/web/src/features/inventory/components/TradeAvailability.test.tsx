import { render, screen } from '@testing-library/react'

import type { InventoryGroup } from '../model/types'
import { TradeAvailability } from './TradeAvailability'

const group = (overrides: Partial<InventoryGroup> = {}): InventoryGroup => ({
  market_hash_name: 'Sawed-Off | Analog Input (Factory New)',
  display_name: '截短霰弹枪 | 模拟输入',
  image_url: '',
  total_quantity: 20,
  available_quantity: 20,
  marketable_quantity: 8,
  tradable_quantity: 8,
  ...overrides,
})

describe('TradeAvailability', () => {
  it('renders proportional tradable and cooldown segments with batch countdowns', () => {
    const { container } = render(
      <TradeAvailability
        group={group({
          cooldown_batches: [
            { tradable_after: Date.UTC(2026, 7, 17, 2, 0), quantity: 7 },
            { tradable_after: Date.UTC(2026, 7, 17, 3, 0), quantity: 5 },
          ],
        })}
        now={Date.UTC(2026, 7, 17, 1, 0)}
      />,
    )

    const availability = container.querySelector('.trade-availability')
    expect(availability).toHaveStyle({ '--tradable-share': '40%', '--cooldown-share': '60%' })
    expect(screen.getByRole('tooltip')).toHaveTextContent('7 件')
    expect(screen.getByRole('tooltip')).toHaveTextContent('1小时')
    expect(availability).toHaveAttribute('tabindex', '0')
  })

  it('does not enable expansion when every item is tradable', () => {
    const { container } = render(
      <TradeAvailability
        group={group({ tradable_quantity: 20, marketable_quantity: 20 })}
        now={Date.UTC(2026, 7, 17, 1, 0)}
      />,
    )

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    expect(container.querySelector('.trade-availability')).not.toHaveAttribute('tabindex')
  })
})
