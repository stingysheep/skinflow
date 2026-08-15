import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { AppProviders } from './app/providers'
import { bootstrapLocalSession } from './app/bootstrapAuth'
import { bootstrapPreferences } from './shared/api/preferences'
import './styles/tokens.css'
import './styles/globals.css'
import './features/inventory/inventory.css'
import './features/holdings/holdings.css'
import './features/settings/settings.css'
import './features/listings/listings.css'
import './shared/components/components.css'

const root = document.getElementById('root')

if (!root) {
  throw new Error('Missing #root element')
}

void bootstrapLocalSession().catch(() => undefined).then(() => bootstrapPreferences()).finally(() => {
  createRoot(root).render(
    <StrictMode>
      <AppProviders />
    </StrictMode>,
  )
})
