import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'

import { SystemStatus } from './SystemStatus'

function renderStatus() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <SystemStatus />
    </QueryClientProvider>,
  )
}

describe('SystemStatus', () => {
  it('shows the API version after a successful health request', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          status: 'ok',
          service: 'Skinflow',
          api_version: '0.1.0',
          environment: 'test',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    renderStatus()

    expect(await screen.findByText('本地服务正常')).toBeInTheDocument()
    expect(screen.getByText('API 0.1.0')).toBeInTheDocument()
  })

  it('shows an offline state and supports retry', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: 'ok',
            service: 'Skinflow',
            api_version: '0.1.0',
            environment: 'test',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )

    renderStatus()
    const retry = await screen.findByRole('button', { name: '重试' })
    fireEvent.click(retry)

    expect(await screen.findByText('本地服务正常')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

