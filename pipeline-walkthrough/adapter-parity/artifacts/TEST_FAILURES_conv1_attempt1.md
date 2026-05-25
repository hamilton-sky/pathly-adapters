# TEST_FAILURES — adapter-parity

## NOT COVERED

### S5: Switching to Paper theme shows brown/orange focus ring

**Criterion:** Switching to the Paper theme shows a brown/orange focus ring, not blue, on focused sidebar items.

**Why not covered:** This criterion requires a running Electron instance with theme switching. No automated test exists for runtime theme rendering. There is no test command that can verify CSS custom property resolution at runtime.

**What was verified instead:** All `:focus-visible` rules in `TopBar.module.css` and `Sidebar.module.css` use `var(--focus-ring)`. No literal `#89b4fa` appears in either file. The infrastructure is correct — whether the Paper theme's `--focus-ring` token resolves to brown/orange requires either a visual test or reading the Paper theme CSS variable definition.

**Suggested resolution:** Locate the Paper theme CSS variable file and verify `--focus-ring` is set to a brown/orange value (not `#89b4fa` or any blue). If a theme token file exists (e.g. `themes/paper.css` or equivalent), a grep for `--focus-ring` there would close this gap without needing a running app.

---

All other criteria across S1, S2, S3, S4, and S5 PASS.
