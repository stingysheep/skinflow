export function formatMoney(value: number | null): string {
  return value === null ? '--' : `¥${(value / 100).toFixed(2)}`
}

export function formatRatio(value: number | null): string {
  return value === null ? '--' : (value / 1_000_000).toFixed(3)
}

export function scanFailureMessage(code: string | null): string {
  const messages: Record<string, string> = {
    APP_RESTARTED: '应用重启导致扫描中断，请重新开始。',
    CSQAQ_ACCESS_DENIED: 'csqaq 拒绝访问：当前网络 IP 未加入 API 白名单，请在 csqaq 更新白名单后重试。',
    RATE_LIMITED: '上游平台触发限流，请稍后重试。',
    UPSTREAM_RATE_LIMITED: '上游平台请求过于频繁，请稍后重试。',
    UPSTREAM_UNAVAILABLE: '上游行情暂时不可用，请稍后重试。',
  }
  return code ? messages[code] ?? `扫描失败：${code}` : '扫描任务失败，请稍后重试。'
}
