import { useQuery } from '@tanstack/react-query'
import { CircleAlert, CircleCheck, LoaderCircle } from 'lucide-react'

import { Button, StatusBadge } from '../../shared/components'
import { fetchHealth } from './api'

export function SystemStatus() {
  const query = useQuery({
    queryKey: ['system', 'health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    retry: false,
    refetchInterval: 30_000,
  })

  if (query.isPending) {
    return (
      <div className="system-status is-loading" role="status">
        <LoaderCircle aria-hidden="true" className="spin" size={16} />
        <span>正在连接本地服务</span>
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="system-status is-error" role="alert">
        <CircleAlert aria-hidden="true" size={16} />
        <span>本地服务离线</span>
        <Button variant="ghost" onClick={() => void query.refetch()}>
          重试
        </Button>
      </div>
    )
  }

  return (
    <div className="system-status is-ok" role="status">
      <CircleCheck aria-hidden="true" size={16} />
      <StatusBadge tone="success">本地服务正常</StatusBadge>
      <code>API {query.data.api_version}</code>
    </div>
  )
}
