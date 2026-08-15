import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useScanEvents } from './useScanEvents'

class FakeEventSource {
  static instances: FakeEventSource[] = []
  readonly listeners = new Map<string, Array<(event: MessageEvent<string>) => void>>()
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false

  constructor(readonly url: string) { FakeEventSource.instances.push(this) }
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }
  close() { this.closed = true }
  emit(type: string, data: unknown) {
    for (const listener of this.listeners.get(type) ?? []) listener({ data: JSON.stringify(data) } as MessageEvent<string>)
  }
}

describe('useScanEvents', () => {
  beforeEach(() => { FakeEventSource.instances = []; vi.stubGlobal('EventSource', FakeEventSource) })
  afterEach(() => vi.unstubAllGlobals())

  it('deduplicates replayed events and closes on terminal event', () => {
    const { result } = renderHook(() => useScanEvents('job-1'))
    const stream = FakeEventSource.instances[0]
    expect(stream.url).toBe('/api/scans/job-1/stream?after=0')
    act(() => stream.onopen?.())
    act(() => stream.emit('result.created', { schema_version: 1, job_id: 'job-1', sequence: 2, type: 'result.created', payload: {} }))
    act(() => stream.emit('result.created', { schema_version: 1, job_id: 'job-1', sequence: 2, type: 'result.created', payload: {} }))
    expect(result.current.events).toHaveLength(1)
    act(() => stream.emit('job.succeeded', { schema_version: 1, job_id: 'job-1', sequence: 3, type: 'job.succeeded', payload: {} }))
    expect(stream.closed).toBe(true)
    expect(result.current.connection).toBe('idle')
  })

  it('shows reconnecting after a stream error', () => {
    const { result } = renderHook(() => useScanEvents('job-2'))
    const stream = FakeEventSource.instances[0]
    act(() => stream.onerror?.())
    expect(result.current.connection).toBe('reconnecting')
    expect(result.current.lastError).toBe('事件连接中断，正在续传')
  })
})
