import { useEffect, useState } from 'react'
import { apiGetPricing, type PricingByProvider } from '../../../../store/commsApi'

// Loads the provider pricing table (db/pricing.py::PRICING via GET /telemetry/pricing) once on
// mount — it drives the model dropdowns (a model list per company) and their $/MTok cost hints.
// Returns {} until the server responds (dropdowns then offer only "Engine default" + "Custom…").
export function usePricing(): PricingByProvider {
  const [pricing, setPricing] = useState<PricingByProvider>({})

  useEffect(() => {
    let alive = true
    void apiGetPricing().then((p) => {
      if (alive) setPricing(p)
    })
    return () => {
      alive = false
    }
  }, [])

  return pricing
}
