const PPM = 1_000_000

export type RatioEstimate = { proceeds: number | null; ratio: number | null; exact: boolean }

function fee(receive: number, rate: number, minimum: number): number {
  return Math.max(minimum, Math.floor(receive * rate / PPM))
}

export function buyerPaysToProceeds(buyerPays: number): number | null {
  if (!Number.isFinite(buyerPays) || buyerPays < 3) return null
  const guess = Math.floor(buyerPays * PPM / 1_150_000)
  let nearest = Math.max(1, guess)
  let nearestDistance = Number.POSITIVE_INFINITY
  for (let receive = Math.max(1, guess - 4); receive <= guess + 4; receive += 1) {
    const total = receive + fee(receive, 50_000, 1) + fee(receive, 100_000, 1)
    const distance = Math.abs(total - buyerPays)
    if (distance < nearestDistance || (distance === nearestDistance && receive < nearest)) {
      nearest = receive
      nearestDistance = distance
    }
    if (distance === 0) return receive
  }
  return nearest
}

export function calculateRatio(cost: number, buyerPays: number): RatioEstimate {
  const proceeds = buyerPaysToProceeds(buyerPays)
  if (proceeds === null) return { proceeds: null, ratio: null, exact: false }
  const total = proceeds + fee(proceeds, 50_000, 1) + fee(proceeds, 100_000, 1)
  return { proceeds, ratio: cost > 0 ? cost / proceeds : null, exact: total === buyerPays }
}
