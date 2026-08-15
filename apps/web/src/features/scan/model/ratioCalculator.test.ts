import { buyerPaysToProceeds, calculateRatio } from './ratioCalculator'

describe('ratioCalculator', () => {
  it('applies Steam and publisher fees before calculating the ratio', () => {
    expect(buyerPaysToProceeds(115)).toBe(100)
    expect(calculateRatio(100, 115).ratio).toBeCloseTo(1)
    expect(calculateRatio(100, 115).exact).toBe(true)
  })

  it('returns unavailable for invalid or unreachable prices', () => {
    expect(calculateRatio(100, 0)).toEqual({ proceeds: null, ratio: null, exact: false })
    expect(buyerPaysToProceeds(2)).toBeNull()
  })

  it('keeps a nearest Steam price for an otherwise unreachable amount', () => {
    const estimate = calculateRatio(1000, 2000)
    expect(estimate.proceeds).toBe(1740)
    expect(estimate.exact).toBe(false)
  })
})
