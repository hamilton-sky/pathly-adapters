const RATES: Array<[string, number, number]> = [
  ['claude-opus-4',     5.00, 25.00],
  ['claude-sonnet-4-6', 3.00, 15.00],
  ['claude-sonnet-4',   3.00, 15.00],
  ['claude-haiku-4',    1.00,  5.00],
]

export function computeCost(model: string, tokensIn: number, tokensOut: number, totalTokens = 0): number {
  const m = model.toLowerCase()
  const match = RATES.find(([prefix]) => m.startsWith(prefix))
  const [, inRate, outRate] = match ?? ['', 3.00, 15.00]
  if (tokensIn === 0 && tokensOut === 0 && totalTokens > 0) {
    // tokens_in/tokens_out absent — approximate with 80% in / 20% out (matches server telemetry.py)
    return (totalTokens * 0.8 / 1_000_000) * inRate + (totalTokens * 0.2 / 1_000_000) * outRate
  }
  return (tokensIn / 1_000_000) * inRate + (tokensOut / 1_000_000) * outRate
}
