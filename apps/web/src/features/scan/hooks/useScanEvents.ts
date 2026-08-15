import { useEffect, useRef, useState } from 'react'

import { scanEventStreamUrl } from '../api/scanApi'
import type { ScanConnection, ScanEvent } from '../model/types'

const EVENT_TYPES = [
  'job.created', 'job.started', 'job.cancelling', 'job.cancelled',
  'job.succeeded', 'job.failed', 'result.created', 'candidate.rejected',
  'candidate.discovered',
  'candidate.source_unavailable',
  'upstream.backoff_started', 'upstream.backoff_completed',
]
const TERMINAL_TYPES = new Set(['job.cancelled', 'job.succeeded', 'job.failed'])

export function useScanEvents(jobId: string | null) {
  const [state, setState] = useState<{ jobId: string | null; events: ScanEvent[] }>({ jobId: null, events: [] })
  const [connection, setConnection] = useState<ScanConnection>('idle')
  const [lastError, setLastError] = useState<string | null>(null)
  const cursor = useRef(0)

  useEffect(() => {
    if (!jobId) return
    cursor.current = 0
    let disposed = false
    let stream: EventSource | null = null
    queueMicrotask(() => { if (!disposed) setConnection('reconnecting') })

    const connect = () => {
      if (disposed) return
      stream = new EventSource(scanEventStreamUrl(jobId, cursor.current))
      stream.onopen = () => { setConnection('connected'); setLastError(null) }
      stream.onerror = () => { if (!disposed) { setConnection('reconnecting'); setLastError('事件连接中断，正在续传') } }
      for (const eventType of EVENT_TYPES) {
        stream.addEventListener(eventType, (message) => {
          let event: ScanEvent
          try {
            event = JSON.parse((message as MessageEvent<string>).data) as ScanEvent
          } catch {
            setLastError('扫描事件格式异常，正在等待后续事件')
            return
          }
          cursor.current = Math.max(cursor.current, event.sequence)
          setState((current) => ({
            jobId,
            events: current.jobId === jobId && current.events.some((existing) => existing.sequence === event.sequence)
              ? current.events
              : current.jobId === jobId ? [...current.events, event] : [event],
          }))
          if (TERMINAL_TYPES.has(event.type)) { stream?.close(); setConnection('idle') }
        })
      }
    }

    connect()
    return () => { disposed = true; stream?.close() }
  }, [jobId])

  return { events: state.jobId === jobId ? state.events : [], connection, lastError }
}
