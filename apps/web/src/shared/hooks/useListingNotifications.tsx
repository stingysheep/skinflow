import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { CheckCircle2, LoaderCircle, X, XCircle } from 'lucide-react'
import { getJson, postJson } from '../api/client'

type ListingItemStatus = {
  status: string
  market_hash_name?: string
  display_name?: string
  message?: string | null
}

type ListingStatus = {
  id: string
  status: string
  items: ListingItemStatus[]
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
const POLL_INTERVAL_MS = 3_000
const TOAST_DURATION_MS = 5_000
const RECOVERABLE_ITEM_STATUSES = new Set(['queued', 'submitting', 'pending_confirmation'])
const TERMINAL_ITEM_STATUSES = new Set(['active', 'sold', 'cancelled', 'failed'])

export function ListingNotificationProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Set<string>>(new Set())
  const [tasks, setTasks] = useState<Record<string, ListingStatus>>({})
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [revision, setRevision] = useState(0)
  const polling = useRef(false)
  const pendingKey = [...pending].sort().join('|')

  const trackListingRequest = useCallback((requestId: string) => {
    if (!requestId) return
    setPending((current) => new Set(current).add(requestId))
  }, [])

  useEffect(() => {
    let disposed = false
    void getJson<{ items: ListingStatus[] }>('/api/listing-requests')
      .then((response) => {
        if (disposed || !Array.isArray(response.items)) return
        const active = response.items.filter((request) => request && Array.isArray(request.items) && request.items.some((item) => RECOVERABLE_ITEM_STATUSES.has(item.status)))
        if (!active.length) return
        setPending((current) => new Set([...current, ...active.map((request) => request.id)]))
      })
      .catch(() => undefined)
    return () => { disposed = true }
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
        setTasks((current) => Object.fromEntries([...Object.entries(current), ...results.map((request) => [request.id, request])]))
        const resolved = results.filter((request) => request.items.length > 0 && request.items.every((item) => TERMINAL_ITEM_STATUSES.has(item.status)))
        if (!resolved.length) return
        setPending((current) => {
          const next = new Set(current)
          resolved.forEach((request) => next.delete(request.id))
          return next
        })
        setTasks((current) => {
          const next = { ...current }
          resolved.forEach((request) => delete next[request.id])
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
              detail: failed ? '部分挂单未成功，请打开挂单记录查看失败原因。' : cancelled ? '手机端取消已同步，未计入成交。' : '手机确认完成，挂单已在售。',
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
      {Object.values(tasks).map((task) => <ListingTaskNotification key={task.id} task={task} />)}
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

function ListingTaskNotification({ task }: { task: ListingStatus }) {
  const total = task.items.length
  const submitted = task.items.filter((item) => !['queued', 'submitting'].includes(item.status)).length
  const pendingConfirmation = task.items.filter((item) => item.status === 'pending_confirmation').length
  const failed = task.items.filter((item) => item.status === 'failed').length
  const percentage = total ? Math.round((submitted / total) * 100) : 0
  const firstName = task.items.find((item) => item.display_name)?.display_name ?? '本次物品'
  const detail = pendingConfirmation
    ? `${firstName} · ${pendingConfirmation} 件等待手机确认`
    : failed
      ? `${firstName} · ${failed} 件提交失败`
      : `${firstName} · 已提交 ${submitted} / ${total} 件`
  const title = submitted < total ? '正在提交 Steam 挂单' : pendingConfirmation ? '等待 Steam 手机确认' : failed ? '挂单提交需要处理' : '正在核对挂单状态'
  return <div className="global-notification global-notification-task is-progress" role="status">
    <LoaderCircle className="global-notification-spinner" size={18} aria-hidden="true" />
    <span>
      <strong>{title} <em>{submitted} / {total}</em></strong>
      <small>{detail}</small>
      <span className="global-task-progress" aria-label={`挂单进度 ${percentage}%`}><i style={{ width: `${percentage}%` }} /></span>
    </span>
  </div>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useListingNotifications() {
  const value = useContext(ListingNotificationContext)
  return value ?? { trackListingRequest: () => undefined, revision: 0 }
}
