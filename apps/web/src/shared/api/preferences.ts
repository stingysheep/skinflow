import { getJson } from './client'

type PreferencesResponse = { preferences?: Record<string, unknown> }

export async function bootstrapPreferences(): Promise<void> {
  try {
    const payload = await getJson<PreferencesResponse>('/api/preferences')
    for (const [key, value] of Object.entries(payload.preferences ?? {})) {
      try { window.localStorage.setItem(key, JSON.stringify(value)) } catch { /* storage is optional */ }
    }
  } catch { /* the page can still use local defaults while the service starts */ }
}
