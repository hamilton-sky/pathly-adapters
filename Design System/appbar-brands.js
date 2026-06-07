/* Pathly app-header split-buttons: VS Code + Terminal launchers with brand-icon
   dropdowns. Shared by Skill Notebook / Canvas / Monitor mocks.
   Injects the split/menu CSS, fills [data-brand] glyphs, and wires the
   chevron toggles. Self-initialises on DOM ready. */
(function () {
  var BRAND = {
    vscode: '<path fill="#007ACC" d="M23.15 2.587L18.21.21a1.494 1.494 0 00-1.705.29l-9.46 8.63-4.12-3.128a.999.999 0 00-1.276.057L.327 7.261A1 1 0 00.326 8.74L3.9 12 .326 15.26a1 1 0 00.001 1.479L1.65 17.94a.999.999 0 001.276.057l4.12-3.128 9.46 8.63a1.492 1.492 0 001.704.29l4.942-2.377A1.5 1.5 0 0024 20.06V3.939a1.5 1.5 0 00-.85-1.352zm-5.146 14.861L10.826 12l7.178-5.448v10.896z"/>',
    fileexplorer: '<path d="M2 8.5C2 7.67 2.67 7 3.5 7H9.4L11.1 9H20.5C21.33 9 22 9.67 22 10.5V18.5C22 19.33 21.33 20 20.5 20H3.5C2.67 20 2 19.33 2 18.5V8.5Z" fill="#E6A817"/><path d="M2 12H22V18.5C22 19.33 21.33 20 20.5 20H3.5C2.67 20 2 19.33 2 18.5V12Z" fill="#FFCA28"/>',
    winterminal: '<rect x="1.5" y="3" width="21" height="18" rx="3.5" fill="#0C0C0C"/><path d="M6 8.5L10.5 12L6 15.5" stroke="#13A10E" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 15.5H18" stroke="#13A10E" stroke-width="1.7" stroke-linecap="round"/>',
    gitbash: '<rect x="1.5" y="1.5" width="21" height="21" rx="4.5" fill="#1D1F21"/><path d="M12 3.5L20.5 12L12 20.5L3.5 12Z" fill="#F05133"/><circle cx="12" cy="8" r="1.6" fill="white"/><line x1="12" y1="9.6" x2="12" y2="12" stroke="white" stroke-width="1.4" stroke-linecap="round"/><line x1="12" y1="12" x2="9.2" y2="14.5" stroke="white" stroke-width="1.4" stroke-linecap="round"/><line x1="12" y1="12" x2="14.8" y2="14.5" stroke="white" stroke-width="1.4" stroke-linecap="round"/><circle cx="9.2" cy="16" r="1.6" fill="white"/><circle cx="14.8" cy="16" r="1.6" fill="white"/>',
    wsl: '<ellipse cx="12" cy="15" rx="6.5" ry="7" fill="#1A1A2E"/><ellipse cx="12" cy="15.5" rx="3.8" ry="5" fill="#F5F5F5"/><circle cx="12" cy="7.2" r="4.2" fill="#1A1A2E"/><ellipse cx="12" cy="7.2" rx="2.4" ry="2.6" fill="#F5F5F5"/><circle cx="10.8" cy="6.4" r="0.7" fill="#1A1A2E"/><circle cx="13.2" cy="6.4" r="0.7" fill="#1A1A2E"/><path d="M11.2 8 L12.8 8 L12 9.1Z" fill="#F57C00"/><path d="M9.5 21 Q8 21 8.5 19.5 L10 19.5 Q10.5 21 9.5 21Z" fill="#F57C00"/><path d="M14.5 21 Q16 21 15.5 19.5 L14 19.5 Q13.5 21 14.5 21Z" fill="#F57C00"/>',
    pycharm: '<defs><linearGradient id="pcGrad__ab" x1="4" y1="3" x2="20" y2="16" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#FCF84A"/><stop offset="50%" stop-color="#21D789"/><stop offset="100%" stop-color="#07C3F2"/></linearGradient></defs><rect x="1.5" y="1.5" width="21" height="21" rx="4.5" fill="#1A1A1A"/><rect x="5" y="5" width="2" height="10" rx="1" fill="url(#pcGrad__ab)"/><path d="M7 5 Q11.5 5 11.5 8 Q11.5 11 7 11Z" fill="url(#pcGrad__ab)"/><path d="M19 7.5 Q16 4.5 13 7.5 Q11 9.5 11 12 Q11 14.5 13 16.5 Q16 19.5 19 16.5" stroke="url(#pcGrad__ab)" stroke-width="2.2" stroke-linecap="round" fill="none"/><rect x="5" y="17.5" width="6" height="2" rx="1" fill="white"/>',
    shell: '<rect x="2.5" y="4" width="19" height="16" rx="4" fill="#1F6FEB"/><path d="m7 9 3 3-3 3" stroke="#F8FAFC" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M12.5 15h4.5" stroke="#F8FAFC" stroke-width="2" stroke-linecap="round"/>',
    claude: '<path fill="#D97757" d="m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z"/>',
    codex: '<rect x="2.5" y="2.5" width="19" height="19" rx="5" fill="#111827"/><g fill="none" stroke="#E5E7EB" stroke-width="1.8" stroke-linecap="round"><path d="M12 5.2c2.5 0 3.8 1.6 3.8 3.4 0 .9-.3 1.7-.9 2.4"/><path d="M18.1 8.8c1.2 2.1.4 4-1.2 4.9-.8.5-1.7.6-2.6.4"/><path d="M17.1 15.9c-1.2 2.1-3.3 2.4-4.9 1.5-.8-.4-1.4-1.1-1.7-2"/><path d="M12 18.8c-2.5 0-3.8-1.6-3.8-3.4 0-.9.3-1.7.9-2.4"/><path d="M5.9 15.2c-1.2-2.1-.4-4 1.2-4.9.8-.5 1.7-.6 2.6-.4"/><path d="M6.9 8.1c1.2-2.1 3.3-2.4 4.9-1.5.8.4 1.4 1.1 1.7 2"/></g><circle cx="12" cy="12" r="1.6" fill="#10B981"/>',
    antigravity: '<path fill="#1967D2" d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"/>',
  };

  var CSS = [
    '.ab-split{position:relative;display:inline-flex;align-items:center;border:1px solid var(--bg-surface1);border-radius:var(--radius-md);transition:border-color .12s,background .12s;}',
    '.ab-split:hover{border-color:var(--accent);background:var(--bg-surface0);}',
    '.ab-split .ab-ic{border-radius:var(--radius-md) 0 0 var(--radius-md);}',
    '.ab-split .ab-chev{width:16px;height:28px;display:inline-flex;align-items:center;justify-content:center;border:none;background:transparent;color:var(--text-muted);cursor:pointer;border-radius:0 var(--radius-md) var(--radius-md) 0;flex-shrink:0;}',
    '.ab-split .ab-chev:hover{background:var(--bg-surface1);color:var(--text-primary);}',
    '.ab-split-div{width:1px;height:14px;background:var(--bg-surface1);flex-shrink:0;}',
    '.ab-menu{display:none;position:absolute;top:100%;left:0;margin-top:6px;z-index:60;min-width:196px;background:var(--bg-surface1);border:1px solid rgba(255,255,255,.1);border-radius:9px;box-shadow:0 12px 32px rgba(0,0,0,.5);padding:5px;}',
    '.ab-menu.show{display:block;}',
    '.ab-menu.right{left:auto;right:0;}',
    '.ab-menu-label{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted);padding:6px 9px 4px;}',
    '.ab-menu-item{display:flex;align-items:center;gap:10px;width:100%;border:none;background:transparent;color:var(--text-secondary);font-size:13px;padding:7px 9px;border-radius:6px;cursor:pointer;text-align:left;font-family:var(--font-family-base);}',
    '.ab-menu-item:hover{background:var(--bg-surface0);color:var(--text-primary);}',
    '.ab-menu-item.on{color:var(--accent);}',
    '.ab-menu-item [data-brand],.ab-menu-item [data-icon]{display:inline-flex;flex-shrink:0;}',
  ].join('\n');

  function injectCss() {
    if (document.getElementById('ab-brands-css')) return;
    var s = document.createElement('style');
    s.id = 'ab-brands-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }
  function fill() {
    document.querySelectorAll('[data-brand]').forEach(function (el) {
      if (el.__abFilled) return;
      el.__abFilled = true;
      var n = el.getAttribute('data-brand'), s = el.getAttribute('data-bs') || 14;
      el.innerHTML = '<svg width="' + s + '" height="' + s + '" viewBox="0 0 24 24" fill="none" style="display:block">' + (BRAND[n] || '') + '</svg>';
    });
  }
  function wire() {
    document.querySelectorAll('.ab-chev').forEach(function (ch) {
      if (ch.__abWired) return;
      ch.__abWired = true;
      ch.addEventListener('click', function (e) {
        e.stopPropagation();
        var menu = ch.parentElement.querySelector('.ab-menu');
        if (!menu) return;
        var open = menu.classList.contains('show');
        document.querySelectorAll('.ab-menu.show').forEach(function (m) { m.classList.remove('show'); });
        if (!open) menu.classList.add('show');
      });
    });
    if (!window.__abOutsideWired) {
      window.__abOutsideWired = true;
      document.addEventListener('click', function () {
        document.querySelectorAll('.ab-menu.show').forEach(function (m) { m.classList.remove('show'); });
      });
    }
  }
  function init() { injectCss(); fill(); wire(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
  window.fillBrands = fill;
})();
