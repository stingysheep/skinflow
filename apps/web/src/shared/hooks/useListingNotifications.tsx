import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { CheckCircle2, X, XCircle } from 'lucide-react'
import { getJson, postJson } from '../api/client'

type ListingStatus = {
  id: string
  status: string
  items: Array<{ status: string }>
}

type Notification = {
  id: string
  tone: 'success' | 'danger'
  title: string
  detail: string
}

type ListingNotificationContextValue = {
  trackListingRequest: (requestId: string) => void
  revision: number
}

const ListingNotificationContext = createContext<ListingNotificationContextValue | null>(null)
const POLL_INTERVAL_MS = 5_000
const TOAST_DURATION_MS = 5_000

export function ListingNotificationProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Set<string>>(new Set())
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [revision, setRevision] = useState(0)
  const polling = useRef(false)
  const pendingKey = [...pending].sort().join('|')

  const trackListingRequest = useCallback((requestId: string) => {
    if (!requestId) return
    setPending((current) => new Set(current).add(requestId))
  }, [])

  useEffect(() => {
    const requestIds = pendingKey ? pendingKey.split('|') : []
    if (!requestIds.length) return
    let disposed = false

    async function poll() {
      if (disposed || polling.current) return
      polling.current = true
      try {
        await postJson('/api/listing-requests/reconcile', {})
        const results = await Promise.all(requestIds.map((requestId) => getJson<ListingStatus>(`/api/listing-requests/${encodeURIComponent(requestId)}`)))
        if (disposed) return
        const resolved = results.filter((request) => {
          const statuses = request.items.map((item) => item.status)
          return statuses.length > 0 && (statuses.every((status) => status === 'active') || statuses.some((status) => ['cancelled', 'failed'].includes(status)))
        })
        if (!resolved.length) return
        setPending((current) => {
          const next = new Set(current)
          resolved.forEach((request) => next.delete(request.id))
          return next
        })
        setNotifications((current) => [
          ...resolved.map((request) => {
            const cancelled = request.items.some((item) => item.status === 'cancelled')
            const failed = request.items.some((item) => item.status === 'failed')
            return {
              id: `${request.id}:${failed ? 'failed' : cancelled ? 'cancelled' : 'success'}`,
              tone: failed || cancelled ? 'danger' as const : 'success' as const,
              title: failed ? 'Steam 挂单失败' : cancelled ? 'Steam 挂单已取消' : 'Steam 挂单成功',
              detail: failed ? '部分挂单未成功，请打开挂单记录查看详情。' : cancelled ? '手机端取消已同步，未计入成交。' : '手机确认完成，挂单已在售。',
            }
          }),
          ...current,
        ].slice(0, 3))
        setRevision((value) => value + 1)
      } catch {
        // Keep the request pending; transient Steam/API failures retry next cycle.
      } finally {
        polling.current = false
      }
    }

    void poll()
    const timer = window.setInterval(() => void poll(), POLL_INTERVAL_MS)
    return () => {
      disposed = true
      window.clearInterval(timer)
    }
  }, [pendingKey])

  useEffect(() => {
    const timers = notifications.map((notification) => window.setTimeout(() => {
      setNotifications((current) => current.filter((item) => item.id !== notification.id))
    }, TOAST_DURATION_MS))
    return () => timers.forEach((timer) => window.clearTimeout(timer))
  }, [notifications])

  const value = useMemo(() => ({ trackListingRequest, revision }), [revision, trackListingRequest])
  return <ListingNotificationContext.Provider value={value}>
    {children}
    <div className="global-notification-stack" aria-live="polite" aria-atomic="true">
      {notifications.map((notification) => {
        const Icon = notification.tone === 'success' ? CheckCircle2 : XCircle
        return <div className={`global-notification is-${notification.tone}`} key={notification.id} role="status">
          <Icon size={18} aria-hidden="true" />
          <span><strong>{notification.title}</strong><small>{notification.detail}</small></span>
          <button type="button" aria-label="关闭通知" onClick={() => setNotifications((current) => current.filter((item) => item.id !== notification.id))}><X size={15} aria-hidden="true" /></button>
        </div>
      })}
    </div>
  </ListingNotificationContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useListingNotifications() {
  const value = useContext(ListingNotificationContext)
  return value ?? { trackListingRequest: () => undefined, revision: 0 }
}
