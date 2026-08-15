import { exchangeLocalSession, rememberStartupToken } from '../shared/api/localSession'

export async function bootstrapLocalSession(): Promise<void> {
  const url = new URL(window.location.href)
  const startupToken = url.searchParams.get('startup_token')
  if (!startupToken) return
  rememberStartupToken(startupToken)
  await exchangeLocalSession(startupToken)
  url.searchParams.delete('startup_token')
  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
}
