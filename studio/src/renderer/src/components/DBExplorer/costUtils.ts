export type PricingTable = {
  providers: {
    [provider: string]: {
      [modelPrefix: string]: { input: number; output: number }
    }
  }
}

export type CostResult = {
  cost: number | null
  source: 'provider_reported' | 'estimated' | 'unpriced' | null
}

export async function fetchPricingTable(): Promise<PricingTable | null> {
  try {
    const res = await fetch('http://127.0.0.1:8765/telemetry/pricing')
    if (!res.ok) return null
    return (await res.json()) as PricingTable
  } catch {
    return null
  }
}

export function computeCost(
  model: string,
  tokensIn: number,
  tokensOut: number,
  table: PricingTable | null,
): CostResult {
  if (table === null) return { cost: null, source: null }
  if (tokensIn === 0 && tokensOut === 0) return { cost: null, source: 'unpriced' }

  const m = model.toLowerCase()
  for (const providerRates of Object.values(table.providers)) {
    let bestPrefix = ''
    let bestRates: { input: number; output: number } | null = null
    for (const [prefix, rates] of Object.entries(providerRates)) {
      if (m.startsWith(prefix) && prefix.length > bestPrefix.length) {
        bestPrefix = prefix
        bestRates = rates
      }
    }
    if (bestRates !== null) {
      const cost =
        (tokensIn / 1_000_000) * bestRates.input +
        (tokensOut / 1_000_000) * bestRates.output
      return { cost, source: 'estimated' }
    }
  }

  return { cost: null, source: 'unpriced' }
}
