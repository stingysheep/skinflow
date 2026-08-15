import { formatRatio } from './formatters'

describe('scan presentation', () => {
  it('formats ppm as a decimal instead of a percentage', () => {
    expect(formatRatio(723_456)).toBe('0.723')
    expect(formatRatio(null)).toBe('--')
  })
})
