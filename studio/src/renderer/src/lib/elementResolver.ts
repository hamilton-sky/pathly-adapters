import { embed, cosineSim } from './embedRouter'

function collectElements(): Array<{ selector: string; description: string }> {
  const results: Array<{ selector: string; description: string }> = []

  const candidates = document.querySelectorAll(
    'button, input, select, textarea, a, [role="button"], [role="menuitem"], [role="option"], [data-label], [aria-label]'
  )

  candidates.forEach((el, i) => {
    const description = [
      el.getAttribute('data-label'),
      el.getAttribute('aria-label'),
      el.getAttribute('placeholder'),
      el.textContent?.trim().slice(0, 50),
      el.tagName.toLowerCase(),
    ].filter(Boolean).join(' ')

    if (description.trim()) {
      let selector = ''
      if (el.id) selector = '#' + el.id
      else if (el.getAttribute('data-label')) selector = '[data-label="' + el.getAttribute('data-label') + '"]'
      else if (el.getAttribute('aria-label')) selector = '[aria-label="' + el.getAttribute('aria-label') + '"]'
      else selector = el.tagName.toLowerCase() + ':nth-of-type(' + (i + 1) + ')'

      results.push({ selector, description })
    }
  })

  return results
}

async function resolveElement(label: string): Promise<string | null> {
  const elements = collectElements()
  if (elements.length === 0) return null

  const labelVec = await embed(label)

  let bestSelector: string | null = null
  let bestScore = 0.4

  for (const el of elements) {
    const elVec = await embed(el.description)
    const score = cosineSim(labelVec, elVec)
    if (score > bestScore) {
      bestScore = score
      bestSelector = el.selector
    }
  }

  return bestSelector
}

export function registerElementResolver(): void {
  ;(window as unknown as Record<string, unknown>)['__pathlyResolveElement'] = resolveElement
}
