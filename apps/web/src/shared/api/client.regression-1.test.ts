import { postJson } from './client'
import { rememberStartupToken } from './localSession'

describe('local desktop session recovery regression', () => {
  afterEach(() => {
    rememberStartupToken(null)
    vi.restoreAllMocks()
  })

  it('re-exchanges the startup token and retries an unauthenticated write once', async () => {
    rememberStartupToken('desktop-startup-token')
    const fetch = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        error: { code: 'AUTH_REQUIRED', message: '本地启动会话无效' },
      }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ authenticated: true }), {
        status: 200,
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ job_id: 'job-1' }), {
        status: 200,
      }))

    await expect(postJson<{ job_id: string }>('/api/scans', {})).resolves.toEqual({
      job_id: 'job-1',
    })
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      '/api/auth/session',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetch).toHaveBeenCalledTimes(3)
  })

  it('does not retry unrelated unauthorized responses', async () => {
    rememberStartupToken('desktop-startup-token')
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        error: { code: 'STEAM_SESSION_EXPIRED', message: 'Steam 会话已过期' },
      }), { status: 401 }),
    )

    await expect(postJson('/api/inventory/refresh', {})).rejects.toMatchObject({
      code: 'STEAM_SESSION_EXPIRED',
    })
    expect(fetch).toHaveBeenCalledOnce()
  })
})
