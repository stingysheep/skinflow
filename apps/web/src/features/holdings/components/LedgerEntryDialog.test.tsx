import { createRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { LedgerEntryDialog } from './LedgerEntryDialog'

vi.mock('../api/ledgerApi', () => ({
  createPurchase: vi.fn(),
  createSale: vi.fn(),
  searchLedgerCatalog: vi.fn(),
}))

describe('LedgerEntryDialog inventory picker', () => {
  it('lets a purchase start from a current inventory group', () => {
    render(<LedgerEntryDialog
      mode="purchase"
      open
      onOpenChange={vi.fn()}
      onSaved={vi.fn()}
      finalFocusRef={createRef<HTMLButtonElement>()}
      inventoryGroups={[{
        market_hash_name: 'FAMAS | ZX81 (Factory New)',
        display_name: '法玛斯 | ZX81',
        image_url: '',
        total_quantity: 44,
        available_quantity: 44,
        listed_quantity: 0,
        marketable_quantity: 44,
        tradable_quantity: 44,
      }]}
    />)

    expect(screen.getByRole('dialog')).toHaveClass('ledger-entry-dialog')
    fireEvent.click(screen.getByRole('button', { name: /法玛斯 \| ZX81/ }))

    expect(screen.getByRole('spinbutton', { name: '数量' })).toHaveValue(44)
    expect(screen.getByRole('textbox', { name: '选择物品' })).toHaveValue('法玛斯 | ZX81')
  })
})
