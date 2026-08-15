let startupToken: string | null = null
let recovery: Promise<boolean> | null = null

export function rememberStartupToken(token: string | null): void {
  startupToken = token
}

export async function exchangeLocalSession(token: string): Promise<void> {
  const response = await fetch('/api/auth/session', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ startup_token: token }),
  })
  if (!response.ok) throw new Error(`本地会话恢复失败 (${response.status})`)
}

export async function recoverLocalSession(): Promise<boolean> {
  if (!startupToken) return false
  if (!recovery) {
    recovery = exchangeLocalSession(startupToken)
      .then(() => true)
      .catch(() => false)
      .finally(() => { recovery = null })
  }
  return recovery
}
