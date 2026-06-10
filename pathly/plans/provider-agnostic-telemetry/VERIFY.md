RESULT: PASS

GET /telemetry/pricing returned 200 with all four providers (claude, codex, google, antigravity), PricingRegistry.compute("claude","claude-sonnet-4-6",800,200) returned (0.0054,"estimated"), 80/20 split block removed, cost_source included in record_activity response, and all 469 previously passing tests continued to pass (6 pre-existing failures unchanged).
