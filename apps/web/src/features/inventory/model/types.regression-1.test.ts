import { inventoryAssetKey } from './types'

describe('inventory asset identity regression', () => {
  it('keeps identical asset ids in different contexts distinct', () => {
    const contextTwo = inventoryAssetKey({
      platform: 'steam', appid: 730, contextid: '2', assetid: '42',
    })
    const contextSixteen = inventoryAssetKey({
      platform: 'steam', appid: 730, contextid: '16', assetid: '42',
    })

    expect(contextTwo).not.toBe(contextSixteen)
  })
})
