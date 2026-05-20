export function generateUniqueStateId(base: string, existing: string[]): string {
  const upper = base.replace(/\.[^.]+$/, '').toUpperCase().replace(/[^A-Z0-9_]/g, '_')
  if (!existing.includes(upper)) return upper
  let i = 2
  while (existing.includes(`${upper}_${i}`)) i++
  return `${upper}_${i}`
}
