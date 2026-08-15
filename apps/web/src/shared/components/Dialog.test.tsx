import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { Button } from './Button'
import { Dialog } from './Dialog'

describe('Dialog', () => {
  it('returns focus to the trigger when closed', async () => {
    render(
      <Dialog trigger={<Button>打开确认</Button>} title="确认操作">
        <p>内容</p>
      </Dialog>,
    )

    const trigger = screen.getByRole('button', { name: '打开确认' })
    fireEvent.click(trigger)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '关闭' }))
    await waitFor(() => expect(trigger).toHaveFocus())
  })
})
