import { afterEach, describe, expect, it, vi } from 'vitest'
import { bootstrapLocalSession } from './bootstrapAuth'

describe('bootstrapLocalSession', () => {
  afterEach(() => vi.restoreAllMocks())

  it('exchanges and removes a desktop startup token', async () => {
    window.history.replaceState(null, '', '/?startup_token=secret-token-value')
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ authenticated: true }), { status: 200 }),
    )
    await bootstrapLocalSession()
    expect(fetch).toHaveBeenCalledWith(
      '/api/auth/session',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(window.location.search).toBe('')
  })
})
