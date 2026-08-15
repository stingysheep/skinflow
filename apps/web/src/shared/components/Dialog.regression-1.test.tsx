import { useRef, useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { Button } from './Button'
import { Dialog } from './Dialog'

function ExternalTriggerDialog() {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  return <>
    <Button ref={triggerRef} onClick={() => setOpen(true)}>外部打开</Button>
    <Dialog open={open} onOpenChange={setOpen} finalFocusRef={triggerRef} title="受控弹窗">
      <Button onClick={() => setOpen(false)}>取消</Button>
    </Dialog>
  </>
}

describe('Dialog external trigger regression', () => {
  it('returns focus to the caller-provided trigger', async () => {
    render(<ExternalTriggerDialog />)
    const trigger = screen.getByRole('button', { name: '外部打开' })
    fireEvent.click(trigger)
    fireEvent.click(await screen.findByRole('button', { name: '取消' }))
    await waitFor(() => expect(trigger).toHaveFocus())
  })
})
