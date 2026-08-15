import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import { AppShell } from './AppShell'
import { ScanPage } from '../features/scan'
import { InventoryPage } from '../features/inventory'
import { HoldingsPage } from '../features/holdings'
import { SettingsPage } from '../features/settings'
import { ListingsPage } from '../features/listings'
import { WorkspacePage } from '../features/workspace'

const rootRoute = createRootRoute({ component: AppShell })
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: ScanPage,
})
const inventoryRoute = createRoute({ getParentRoute: () => rootRoute, path: '/inventory', component: InventoryPage })
const holdingsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/holdings', component: HoldingsPage })
const historyRoute = createRoute({ getParentRoute: () => rootRoute, path: '/history', component: () => <WorkspacePage mode="history" /> })
const listingsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/listings', component: ListingsPage })
const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/settings', component: SettingsPage })

const routeTree = rootRoute.addChildren([indexRoute, inventoryRoute, holdingsRoute, historyRoute, listingsRoute, settingsRoute])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
