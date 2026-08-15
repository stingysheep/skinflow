import { scanFailureMessage } from '../model/formatters'

describe('ScanPage failure message regression', () => {
  it('shows a user-facing message for persisted upstream rate limiting', () => {
    expect(scanFailureMessage('UPSTREAM_RATE_LIMITED')).toBe(
      '上游平台请求过于频繁，请稍后重试。',
    )
  })
})
