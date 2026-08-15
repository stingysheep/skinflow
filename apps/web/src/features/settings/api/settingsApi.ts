import { deleteJson, getJson, postJson } from '../../../shared/api/client'

export type SteamSession = {
  status: 'absent' | 'active' | 'expired'
  steamid64: string | null
  login_running: boolean
  error: string | null
}

export const getSteamSession = (signal?: AbortSignal) =>
  getJson<SteamSession>('/api/steam/session', signal)

export const startSteamLogin = () => postJson<SteamSession>('/api/steam/session/login', {})

export const clearSteamSession = () => deleteJson<SteamSession>('/api/steam/session')
