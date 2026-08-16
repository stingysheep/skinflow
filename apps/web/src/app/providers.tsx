import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'

import { router } from './router'
import { ListingNotificationProvider } from '../shared/hooks/useListingNotifications'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
    },
  },
})

export function AppProviders() {
  return (
    <QueryClientProvider client={queryClient}>
      <ListingNotificationProvider>
        <RouterProvider router={router} />
      </ListingNotificationProvider>
    </QueryClientProvider>
  )
}
