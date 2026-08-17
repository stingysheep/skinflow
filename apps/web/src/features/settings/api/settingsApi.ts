import { deleteJson, getJson, postJson, putJson } from '../../../shared/api/client'

export type SteamSession = {
  status: 'absent' | 'active' | 'expired'
  steamid64: string | null
  login_running: boolean
  error: string | null
}

export type CsqaqConfiguration = {
  token_configured: boolean
  whitelist_ip: string
  status: 'missing' | 'ready' | 'access_denied' | 'rate_limited' | 'unavailable'
}

export const getSteamSession = (signal?: AbortSignal) =>
  getJson<SteamSession>('/api/steam/session', signal)

export const startSteamLogin = () => postJson<SteamSession>('/api/steam/session/login', {})

export const clearSteamSession = () => deleteJson<SteamSession>('/api/steam/session')

export const getCsqaqConfiguration = () => getJson<CsqaqConfiguration>('/api/preferences/csqaq')
export const saveCsqaqConfiguration = (value: { token?: string; whitelist_ip: string }) => putJson<CsqaqConfiguration>('/api/preferences/csqaq', value)
export const validateCsqaqConfiguration = () => postJson<CsqaqConfiguration>('/api/preferences/csqaq/validate', {})
