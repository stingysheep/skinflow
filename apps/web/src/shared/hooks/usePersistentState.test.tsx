import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { usePersistentState } from './usePersistentState'

function Harness() {
  const [value, setValue] = usePersistentState('skinflow.test.preference', 'default')
  return <button type="button" onClick={() => setValue('changed')}>{value}</button>
}

describe('usePersistentState', () => {
  beforeEach(() => window.localStorage.clear())

  it('persists a changed value synchronously', () => {
    render(<Harness />)

    fireEvent.click(screen.getByRole('button', { name: 'default' }))

    expect(window.localStorage.getItem('skinflow.test.preference')).toBe(JSON.stringify('changed'))
    expect(screen.getByRole('button', { name: 'changed' })).toBeInTheDocument()
  })

  it('hydrates from the local service when the desktop port changes', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      key: 'skinflow.test.preference',
      found: true,
      value: 'from-service',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<Harness />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'from-service' })).toBeInTheDocument())
    expect(window.localStorage.getItem('skinflow.test.preference')).toBe(JSON.stringify('from-service'))
  })
})
