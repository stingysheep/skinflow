import type { ScanConnection, ScanStatus } from '../model/types'

export function ScanSummary({ status, resultCount, candidateLimit, discoveredCount, connection, rejectedCount, backoffCount, sourceUnavailableCount, platforms, connectionError }: { status: ScanStatus | null; resultCount: number; candidateLimit: number; discoveredCount: number; connection: ScanConnection; rejectedCount: number; backoffCount: number; sourceUnavailableCount: number; platforms: string[]; connectionError?: string | null }) {
  const completedCount = Math.min(candidateLimit, resultCount + rejectedCount)
  const queuedCount = Math.min(candidateLimit, Math.max(completedCount, discoveredCount))
  const progress = candidateLimit ? Math.min(100, queuedCount / candidateLimit * 100) : 0
  return <div className="scan-summary-strip">
    <span className={`status-dot status-dot-${status === 'failed' ? 'danger' : status === 'succeeded' ? 'success' : 'active'}`} />
    <strong>{status === 'running' ? '正在扫描' : status === 'succeeded' ? '扫描完成' : status === 'failed' ? '扫描失败' : status === 'cancelled' ? '已取消' : '等待扫描'}</strong>
    <span>{completedCount} / {candidateLimit} 个候选已完成</span>
    {discoveredCount > completedCount ? <span className="summary-discovered">已发现 {discoveredCount} 个</span> : null}
    <span className="summary-progress"><i style={{ width: `${progress}%` }} /></span>
    <span>{progress.toFixed(1)}%</span>
    <span className={`summary-connection summary-connection-${connection}`}>{connection === 'reconnecting' ? '断线续传中' : connection === 'connected' ? '事件已连接' : '等待事件'}</span>
    {rejectedCount ? <span className="summary-warning">拒绝 {rejectedCount}</span> : null}
    {backoffCount ? <span className="summary-warning">限流 {backoffCount}</span> : null}
    {sourceUnavailableCount ? <span className="summary-warning">悠悠不可用 {sourceUnavailableCount}</span> : null}
    {connectionError ? <span className="summary-warning">{connectionError}</span> : null}
    <span className="summary-note">{platforms.map((value) => value === 'youpin' ? '悠悠' : 'BUFF').join(' · ')} · Steam · csqaq</span>
  </div>
}
