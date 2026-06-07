/* @ds-bundle: {"format":3,"namespace":"DesignSystem_ba588c","components":[{"name":"Button","sourcePath":"components/buttons/Button.jsx"},{"name":"IconButton","sourcePath":"components/buttons/IconButton.jsx"},{"name":"Badge","sourcePath":"components/feedback/Badge.jsx"},{"name":"ProgressBar","sourcePath":"components/feedback/ProgressBar.jsx"},{"name":"Spinner","sourcePath":"components/feedback/Spinner.jsx"},{"name":"StatePill","sourcePath":"components/feedback/StatePill.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"},{"name":"ContextMenu","sourcePath":"components/overlay/ContextMenu.jsx"},{"name":"Tooltip","sourcePath":"components/overlay/Tooltip.jsx"},{"name":"Card","sourcePath":"components/surface/Card.jsx"}],"sourceHashes":{"appbar-brands.js":"1db9ce690dc6","assets/vendor/icons.js":"aebfb7aac08e","assets/vendor/react-dom.production.min.js":"35f4f974f4b2","assets/vendor/react.production.min.js":"d949f1c3687a","components/buttons/Button.jsx":"886431c4f545","components/buttons/IconButton.jsx":"419122c1ef95","components/feedback/Badge.jsx":"d8c66cf07d93","components/feedback/ProgressBar.jsx":"ef8c3893fd1d","components/feedback/Spinner.jsx":"0fb2059c5af9","components/feedback/StatePill.jsx":"47734b6c862d","components/forms/Input.jsx":"0d3500297f56","components/forms/Select.jsx":"11b70673aec2","components/navigation/Tabs.jsx":"b68f8b49b9b9","components/overlay/ContextMenu.jsx":"42d506a24b13","components/overlay/Tooltip.jsx":"047d8edaed5f","components/surface/Card.jsx":"49755e484bcd","design-canvas.jsx":"bd8746af6e58","tweaks-panel.jsx":"6591467622ed","ui_kits/_shell/shell.js":"fa6718a6ab4f","ui_kits/db-explorer/db-explorer.js":"7944883cdef0","ui_kits/flow-canvas/canvas.js":"a74134dadad2","ui_kits/monitor/monitor.js":"fad15d06effd","ui_kits/skill-notebook/notebook.js":"94fe153f62c4"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.DesignSystem_ba588c = window.DesignSystem_ba588c || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// appbar-brands.js
try { (() => {
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
    antigravity: '<path fill="#1967D2" d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"/>'
  };
  var CSS = ['.ab-split{position:relative;display:inline-flex;align-items:center;border:1px solid var(--bg-surface1);border-radius:var(--radius-md);transition:border-color .12s,background .12s;}', '.ab-split:hover{border-color:var(--accent);background:var(--bg-surface0);}', '.ab-split .ab-ic{border-radius:var(--radius-md) 0 0 var(--radius-md);}', '.ab-split .ab-chev{width:16px;height:28px;display:inline-flex;align-items:center;justify-content:center;border:none;background:transparent;color:var(--text-muted);cursor:pointer;border-radius:0 var(--radius-md) var(--radius-md) 0;flex-shrink:0;}', '.ab-split .ab-chev:hover{background:var(--bg-surface1);color:var(--text-primary);}', '.ab-split-div{width:1px;height:14px;background:var(--bg-surface1);flex-shrink:0;}', '.ab-menu{display:none;position:absolute;top:100%;left:0;margin-top:6px;z-index:60;min-width:196px;background:var(--bg-surface1);border:1px solid rgba(255,255,255,.1);border-radius:9px;box-shadow:0 12px 32px rgba(0,0,0,.5);padding:5px;}', '.ab-menu.show{display:block;}', '.ab-menu.right{left:auto;right:0;}', '.ab-menu-label{font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted);padding:6px 9px 4px;}', '.ab-menu-item{display:flex;align-items:center;gap:10px;width:100%;border:none;background:transparent;color:var(--text-secondary);font-size:13px;padding:7px 9px;border-radius:6px;cursor:pointer;text-align:left;font-family:var(--font-family-base);}', '.ab-menu-item:hover{background:var(--bg-surface0);color:var(--text-primary);}', '.ab-menu-item.on{color:var(--accent);}', '.ab-menu-item [data-brand],.ab-menu-item [data-icon]{display:inline-flex;flex-shrink:0;}'].join('\n');
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
      var n = el.getAttribute('data-brand'),
        s = el.getAttribute('data-bs') || 14;
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
        document.querySelectorAll('.ab-menu.show').forEach(function (m) {
          m.classList.remove('show');
        });
        if (!open) menu.classList.add('show');
      });
    });
    if (!window.__abOutsideWired) {
      window.__abOutsideWired = true;
      document.addEventListener('click', function () {
        document.querySelectorAll('.ab-menu.show').forEach(function (m) {
          m.classList.remove('show');
        });
      });
    }
  }
  function init() {
    injectCss();
    fill();
    wire();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);else init();
  window.fillBrands = fill;
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "appbar-brands.js", error: String((e && e.message) || e) }); }

// assets/vendor/icons.js
try { (() => {
/* Pathly icon helper — self-hosted lucide subset (lucide v1.16.0, ISC).
   No build step, no CDN. Renders stroke icons identical to lucide-react.
   Usage:
     PathlyIcons.svg('menu', {size:15})            -> SVG markup string
     <i data-icon="trash-2" data-size="14"></i> + PathlyIcons.inject()
*/
(function (global) {
  var NODES = {
    "menu": [["path", {
      "d": "M4 5h16",
      "key": "1tepv9"
    }], ["path", {
      "d": "M4 12h16",
      "key": "1lakjw"
    }], ["path", {
      "d": "M4 19h16",
      "key": "1djgab"
    }]],
    "brain": [["path", {
      "d": "M12 18V5",
      "key": "adv99a"
    }], ["path", {
      "d": "M15 13a4.17 4.17 0 0 1-3-4 4.17 4.17 0 0 1-3 4",
      "key": "1e3is1"
    }], ["path", {
      "d": "M17.598 6.5A3 3 0 1 0 12 5a3 3 0 1 0-5.598 1.5",
      "key": "1gqd8o"
    }], ["path", {
      "d": "M17.997 5.125a4 4 0 0 1 2.526 5.77",
      "key": "iwvgf7"
    }], ["path", {
      "d": "M18 18a4 4 0 0 0 2-7.464",
      "key": "efp6ie"
    }], ["path", {
      "d": "M19.967 17.483A4 4 0 1 1 12 18a4 4 0 1 1-7.967-.517",
      "key": "1gq6am"
    }], ["path", {
      "d": "M6 18a4 4 0 0 1-2-7.464",
      "key": "k1g0md"
    }], ["path", {
      "d": "M6.003 5.125a4 4 0 0 0-2.526 5.77",
      "key": "q97ue3"
    }]],
    "square-pen": [["path", {
      "d": "M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7",
      "key": "1m0v6g"
    }], ["path", {
      "d": "M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z",
      "key": "ohrbg2"
    }]],
    "trash-2": [["path", {
      "d": "M10 11v6",
      "key": "nco0om"
    }], ["path", {
      "d": "M14 11v6",
      "key": "outv1u"
    }], ["path", {
      "d": "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6",
      "key": "miytrc"
    }], ["path", {
      "d": "M3 6h18",
      "key": "d0wm0j"
    }], ["path", {
      "d": "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2",
      "key": "e791ji"
    }]],
    "more-horizontal": [["circle", {
      "cx": "12",
      "cy": "12",
      "r": "1",
      "key": "41hilf"
    }], ["circle", {
      "cx": "19",
      "cy": "12",
      "r": "1",
      "key": "1wjl8i"
    }], ["circle", {
      "cx": "5",
      "cy": "12",
      "r": "1",
      "key": "1pcz8c"
    }]],
    "terminal": [["path", {
      "d": "M12 19h8",
      "key": "baeox8"
    }], ["path", {
      "d": "m4 17 6-6-6-6",
      "key": "1yngyt"
    }]],
    "download": [["path", {
      "d": "M12 15V3",
      "key": "m9g1x1"
    }], ["path", {
      "d": "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4",
      "key": "ih7n3h"
    }], ["path", {
      "d": "m7 10 5 5 5-5",
      "key": "brsn70"
    }]],
    "refresh-cw": [["path", {
      "d": "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8",
      "key": "v9h5vc"
    }], ["path", {
      "d": "M21 3v5h-5",
      "key": "1q7to0"
    }], ["path", {
      "d": "M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16",
      "key": "3uifl3"
    }], ["path", {
      "d": "M8 16H3v5",
      "key": "1cv678"
    }]],
    "square": [["rect", {
      "width": "18",
      "height": "18",
      "x": "3",
      "y": "3",
      "rx": "2",
      "key": "afitv7"
    }]],
    "x": [["path", {
      "d": "M18 6 6 18",
      "key": "1bl5f8"
    }], ["path", {
      "d": "m6 6 12 12",
      "key": "d8bk6v"
    }]],
    "chevron-down": [["path", {
      "d": "m6 9 6 6 6-6",
      "key": "qrunsl"
    }]],
    "chevron-right": [["path", {
      "d": "m9 18 6-6-6-6",
      "key": "mthhwq"
    }]],
    "chevron-up": [["path", {
      "d": "m18 15-6-6-6 6",
      "key": "153udz"
    }]],
    "chevrons-right": [["path", {
      "d": "m6 17 5-5-5-5",
      "key": "xnjwq"
    }], ["path", {
      "d": "m13 17 5-5-5-5",
      "key": "17xmmf"
    }]],
    "chevrons-up": [["path", {
      "d": "m17 11-5-5-5 5",
      "key": "e8nh98"
    }], ["path", {
      "d": "m17 18-5-5-5 5",
      "key": "2avn1x"
    }]],
    "play": [["path", {
      "d": "M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z",
      "key": "10ikf1"
    }]],
    "pause": [["rect", {
      "x": "14",
      "y": "3",
      "width": "5",
      "height": "18",
      "rx": "1",
      "key": "kaeet6"
    }], ["rect", {
      "x": "5",
      "y": "3",
      "width": "5",
      "height": "18",
      "rx": "1",
      "key": "1wsw3u"
    }]],
    "skip-forward": [["path", {
      "d": "M21 4v16",
      "key": "7j8fe9"
    }], ["path", {
      "d": "M6.029 4.285A2 2 0 0 0 3 6v12a2 2 0 0 0 3.029 1.715l9.997-5.998a2 2 0 0 0 .003-3.432z",
      "key": "zs4d6"
    }]],
    "shuffle": [["path", {
      "d": "m18 14 4 4-4 4",
      "key": "10pe0f"
    }], ["path", {
      "d": "m18 2 4 4-4 4",
      "key": "pucp1d"
    }], ["path", {
      "d": "M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22",
      "key": "1ailkh"
    }], ["path", {
      "d": "M2 6h1.972a4 4 0 0 1 3.6 2.2",
      "key": "km57vx"
    }], ["path", {
      "d": "M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45",
      "key": "os18l9"
    }]],
    "rotate-ccw": [["path", {
      "d": "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8",
      "key": "1357e3"
    }], ["path", {
      "d": "M3 3v5h5",
      "key": "1xhq8a"
    }]],
    "eye-off": [["path", {
      "d": "M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49",
      "key": "ct8e1f"
    }], ["path", {
      "d": "M14.084 14.158a3 3 0 0 1-4.242-4.242",
      "key": "151rxh"
    }], ["path", {
      "d": "M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143",
      "key": "13bj9a"
    }], ["path", {
      "d": "m2 2 20 20",
      "key": "1ooewy"
    }]],
    "send": [["path", {
      "d": "M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z",
      "key": "1ffxy3"
    }], ["path", {
      "d": "m21.854 2.147-10.94 10.939",
      "key": "12cjpa"
    }]],
    "plus": [["path", {
      "d": "M5 12h14",
      "key": "1ays0h"
    }], ["path", {
      "d": "M12 5v14",
      "key": "s699le"
    }]],
    "folder": [["path", {
      "d": "M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z",
      "key": "1kt360"
    }]],
    "folder-open": [["path", {
      "d": "m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2",
      "key": "usdka0"
    }]],
    "file-text": [["path", {
      "d": "M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z",
      "key": "1oefj6"
    }], ["path", {
      "d": "M14 2v5a1 1 0 0 0 1 1h5",
      "key": "wfsgrz"
    }], ["path", {
      "d": "M10 9H8",
      "key": "b1mrlr"
    }], ["path", {
      "d": "M16 13H8",
      "key": "t4e002"
    }], ["path", {
      "d": "M16 17H8",
      "key": "z1uh3a"
    }]],
    "book-open": [["path", {
      "d": "M12 7v14",
      "key": "1akyts"
    }], ["path", {
      "d": "M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z",
      "key": "ruj8y"
    }]],
    "sparkles": [["path", {
      "d": "M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z",
      "key": "1s2grr"
    }], ["path", {
      "d": "M20 2v4",
      "key": "1rf3ol"
    }], ["path", {
      "d": "M22 4h-4",
      "key": "gwowj6"
    }], ["circle", {
      "cx": "4",
      "cy": "20",
      "r": "2",
      "key": "6kqj1y"
    }]],
    "lock": [["rect", {
      "width": "18",
      "height": "11",
      "x": "3",
      "y": "11",
      "rx": "2",
      "ry": "2",
      "key": "1w4ew1"
    }], ["path", {
      "d": "M7 11V7a5 5 0 0 1 10 0v4",
      "key": "fwvmzm"
    }]],
    "grip-vertical": [["circle", {
      "cx": "9",
      "cy": "12",
      "r": "1",
      "key": "1vctgf"
    }], ["circle", {
      "cx": "9",
      "cy": "5",
      "r": "1",
      "key": "hp0tcf"
    }], ["circle", {
      "cx": "9",
      "cy": "19",
      "r": "1",
      "key": "fkjjf6"
    }], ["circle", {
      "cx": "15",
      "cy": "12",
      "r": "1",
      "key": "1tmaij"
    }], ["circle", {
      "cx": "15",
      "cy": "5",
      "r": "1",
      "key": "19l28e"
    }], ["circle", {
      "cx": "15",
      "cy": "19",
      "r": "1",
      "key": "f4zoj3"
    }]],
    "pencil": [["path", {
      "d": "M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z",
      "key": "1a8usu"
    }], ["path", {
      "d": "m15 5 4 4",
      "key": "1mk7zo"
    }]],
    "check": [["path", {
      "d": "M20 6 9 17l-5-5",
      "key": "1gmf2c"
    }]],
    "layout-grid": [["rect", {
      "width": "7",
      "height": "7",
      "x": "3",
      "y": "3",
      "rx": "1",
      "key": "1g98yp"
    }], ["rect", {
      "width": "7",
      "height": "7",
      "x": "14",
      "y": "3",
      "rx": "1",
      "key": "6d4xhi"
    }], ["rect", {
      "width": "7",
      "height": "7",
      "x": "14",
      "y": "14",
      "rx": "1",
      "key": "nxv5o0"
    }], ["rect", {
      "width": "7",
      "height": "7",
      "x": "3",
      "y": "14",
      "rx": "1",
      "key": "1bb6yr"
    }]],
    "list": [["path", {
      "d": "M3 5h.01",
      "key": "18ugdj"
    }], ["path", {
      "d": "M3 12h.01",
      "key": "nlz23k"
    }], ["path", {
      "d": "M3 19h.01",
      "key": "noohij"
    }], ["path", {
      "d": "M8 5h13",
      "key": "1pao27"
    }], ["path", {
      "d": "M8 12h13",
      "key": "1za7za"
    }], ["path", {
      "d": "M8 19h13",
      "key": "m83p4d"
    }]],
    "activity": [["path", {
      "d": "M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2",
      "key": "169zse"
    }]],
    "search": [["path", {
      "d": "m21 21-4.34-4.34",
      "key": "14j7rj"
    }], ["circle", {
      "cx": "11",
      "cy": "11",
      "r": "8",
      "key": "4ej97u"
    }]],
    "sun": [["circle", {
      "cx": "12",
      "cy": "12",
      "r": "4",
      "key": "4exip2"
    }], ["path", {
      "d": "M12 2v2",
      "key": "tus03m"
    }], ["path", {
      "d": "M12 20v2",
      "key": "1lh1kg"
    }], ["path", {
      "d": "m4.93 4.93 1.41 1.41",
      "key": "149t6j"
    }], ["path", {
      "d": "m17.66 17.66 1.41 1.41",
      "key": "ptbguv"
    }], ["path", {
      "d": "M2 12h2",
      "key": "1t8f8n"
    }], ["path", {
      "d": "M20 12h2",
      "key": "1q8mjw"
    }], ["path", {
      "d": "m6.34 17.66-1.41 1.41",
      "key": "1m8zz5"
    }], ["path", {
      "d": "m19.07 4.93-1.41 1.41",
      "key": "1shlcs"
    }]],
    "moon": [["path", {
      "d": "M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401",
      "key": "kfwtm"
    }]],
    "star": [["path", {
      "d": "M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z",
      "key": "r04s7s"
    }]],
    "columns-2": [["rect", {
      "width": "18",
      "height": "18",
      "x": "3",
      "y": "3",
      "rx": "2",
      "key": "afitv7"
    }], ["path", {
      "d": "M12 3v18",
      "key": "108xh3"
    }]],
    "external-link": [["path", {
      "d": "M15 3h6v6",
      "key": "1q9fwt"
    }], ["path", {
      "d": "M10 14 21 3",
      "key": "gplh6r"
    }], ["path", {
      "d": "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",
      "key": "a6xqqp"
    }]],
    "maximize-2": [["path", {
      "d": "M15 3h6v6",
      "key": "1q9fwt"
    }], ["path", {
      "d": "m21 3-7 7",
      "key": "1l2asr"
    }], ["path", {
      "d": "m3 21 7-7",
      "key": "tjx5ai"
    }], ["path", {
      "d": "M9 21H3v-6",
      "key": "wtvkvv"
    }]],
    "minimize-2": [["path", {
      "d": "m14 10 7-7",
      "key": "oa77jy"
    }], ["path", {
      "d": "M20 10h-6V4",
      "key": "mjg0md"
    }], ["path", {
      "d": "m3 21 7-7",
      "key": "tjx5ai"
    }], ["path", {
      "d": "M4 14h6v6",
      "key": "rmj7iw"
    }]],
    "zap": [["path", {
      "d": "M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z",
      "key": "1xq2db"
    }]],
    "history": [["path", {
      "d": "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8",
      "key": "1357e3"
    }], ["path", {
      "d": "M3 3v5h5",
      "key": "1xhq8a"
    }], ["path", {
      "d": "M12 7v5l4 2",
      "key": "1fdv2h"
    }]],
    "message-square": [["path", {
      "d": "M22 17a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 21.286V5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2z",
      "key": "18887p"
    }]],
    "undo-2": [["path", {
      "d": "M9 14 4 9l5-5",
      "key": "102s5s"
    }], ["path", {
      "d": "M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11",
      "key": "f3b9sd"
    }]],
    "redo-2": [["path", {
      "d": "m15 14 5-5-5-5",
      "key": "12vg1m"
    }], ["path", {
      "d": "M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13",
      "key": "6uklza"
    }]],
    "arrow-left": [["path", {
      "d": "m12 19-7-7 7-7",
      "key": "1l729n"
    }], ["path", {
      "d": "M19 12H5",
      "key": "x3x0zl"
    }]],
    "copy": [["rect", {
      "width": "14",
      "height": "14",
      "x": "8",
      "y": "8",
      "rx": "2",
      "ry": "2",
      "key": "17jyea"
    }], ["path", {
      "d": "M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2",
      "key": "zix9uf"
    }]],
    "database": [["ellipse", {
      "cx": "12",
      "cy": "5",
      "rx": "9",
      "ry": "3",
      "key": "msslwz"
    }], ["path", {
      "d": "M3 5V19A9 3 0 0 0 21 19V5",
      "key": "1wlel7"
    }], ["path", {
      "d": "M3 12A9 3 0 0 0 21 12",
      "key": "mv7ke4"
    }]],
    "git-branch": [["path", {
      "d": "M15 6a9 9 0 0 0-9 9V3",
      "key": "1cii5b"
    }], ["circle", {
      "cx": "18",
      "cy": "6",
      "r": "3",
      "key": "1h7g24"
    }], ["circle", {
      "cx": "6",
      "cy": "18",
      "r": "3",
      "key": "fqmcym"
    }]],
    "circle": [["circle", {
      "cx": "12",
      "cy": "12",
      "r": "10",
      "key": "1mglay"
    }]],
    "circle-check": [["circle", {
      "cx": "12",
      "cy": "12",
      "r": "10",
      "key": "1mglay"
    }], ["path", {
      "d": "m9 12 2 2 4-4",
      "key": "dzmm74"
    }]],
    "circle-dot": [["circle", {
      "cx": "12",
      "cy": "12",
      "r": "10",
      "key": "1mglay"
    }], ["circle", {
      "cx": "12",
      "cy": "12",
      "r": "1",
      "key": "41hilf"
    }]],
    "hard-drive": [["path", {
      "d": "M10 16h.01",
      "key": "1bzywj"
    }], ["path", {
      "d": "M2.212 11.577a2 2 0 0 0-.212.896V18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5.527a2 2 0 0 0-.212-.896L18.55 5.11A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
      "key": "18tbho"
    }], ["path", {
      "d": "M21.946 12.013H2.054",
      "key": "zqlbp7"
    }], ["path", {
      "d": "M6 16h.01",
      "key": "1pmjb7"
    }]],
    "table": [["path", {
      "d": "M12 3v18",
      "key": "108xh3"
    }], ["rect", {
      "width": "18",
      "height": "18",
      "x": "3",
      "y": "3",
      "rx": "2",
      "key": "afitv7"
    }], ["path", {
      "d": "M3 9h18",
      "key": "1pudct"
    }], ["path", {
      "d": "M3 15h18",
      "key": "5xshup"
    }]],
    "clock": [["circle", {
      "cx": "12",
      "cy": "12",
      "r": "10",
      "key": "1mglay"
    }], ["path", {
      "d": "M12 6v6l4 2",
      "key": "mmk7yg"
    }]],
    "dollar-sign": [["line", {
      "x1": "12",
      "x2": "12",
      "y1": "2",
      "y2": "22",
      "key": "7eqyqh"
    }], ["path", {
      "d": "M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
      "key": "1b0p4s"
    }]],
    "coins": [["path", {
      "d": "M13.744 17.736a6 6 0 1 1-7.48-7.48",
      "key": "bq4yh3"
    }], ["path", {
      "d": "M15 6h1v4",
      "key": "11y1tn"
    }], ["path", {
      "d": "m6.134 14.768.866-.5 2 3.464",
      "key": "17snzx"
    }], ["circle", {
      "cx": "16",
      "cy": "8",
      "r": "6",
      "key": "14bfc9"
    }]],
    "hash": [["line", {
      "x1": "4",
      "x2": "20",
      "y1": "9",
      "y2": "9",
      "key": "4lhtct"
    }], ["line", {
      "x1": "4",
      "x2": "20",
      "y1": "15",
      "y2": "15",
      "key": "vyu0kd"
    }], ["line", {
      "x1": "10",
      "x2": "8",
      "y1": "3",
      "y2": "21",
      "key": "1ggp8o"
    }], ["line", {
      "x1": "16",
      "x2": "14",
      "y1": "3",
      "y2": "21",
      "key": "weycgp"
    }]],
    "diamond": [["path", {
      "d": "M2.7 10.3a2.41 2.41 0 0 0 0 3.41l7.59 7.59a2.41 2.41 0 0 0 3.41 0l7.59-7.59a2.41 2.41 0 0 0 0-3.41l-7.59-7.59a2.41 2.41 0 0 0-3.41 0Z",
      "key": "1f1r0c"
    }]],
    "flame": [["path", {
      "d": "M12 3q1 4 4 6.5t3 5.5a1 1 0 0 1-14 0 5 5 0 0 1 1-3 1 1 0 0 0 5 0c0-2-1.5-3-1.5-5q0-2 2.5-4",
      "key": "1slcih"
    }]],
    "settings": [["path", {
      "d": "M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915",
      "key": "1i5ecw"
    }], ["circle", {
      "cx": "12",
      "cy": "12",
      "r": "3",
      "key": "1v7zrd"
    }]],
    "globe": [["circle", {
      "cx": "12",
      "cy": "12",
      "r": "10",
      "key": "1mglay"
    }], ["path", {
      "d": "M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20",
      "key": "13o1zl"
    }], ["path", {
      "d": "M2 12h20",
      "key": "9i4pu4"
    }]],
    "panel-left": [["rect", {
      "width": "18",
      "height": "18",
      "x": "3",
      "y": "3",
      "rx": "2",
      "key": "afitv7"
    }], ["path", {
      "d": "M9 3v18",
      "key": "fh3hqa"
    }]],
    "square-terminal": [["path", {
      "d": "m7 11 2-2-2-2",
      "key": "1lz0vl"
    }], ["path", {
      "d": "M11 13h4",
      "key": "1p7l4v"
    }], ["rect", {
      "width": "18",
      "height": "18",
      "x": "3",
      "y": "3",
      "rx": "2",
      "ry": "2",
      "key": "1m3agn"
    }]]
  };
  var DEF = 'xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"';
  function attrs(o) {
    return Object.keys(o).map(function (k) {
      var key = k.replace(/[A-Z]/g, function (c) {
        return '-' + c.toLowerCase();
      });
      return key + '="' + o[k] + '"';
    }).join(' ');
  }
  function svg(name, opts) {
    opts = opts || {};
    var size = opts.size || 16;
    var sw = opts.strokeWidth || 2;
    var nodes = NODES[name];
    if (!nodes) {
      return '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24"></svg>';
    }
    var inner = nodes.map(function (pair) {
      var tag = pair[0];
      var a = Object.assign({}, pair[1]);
      delete a.key;
      return '<' + tag + ' ' + attrs(a) + '></' + tag + '>';
    }).join('');
    return '<svg ' + DEF + ' width="' + size + '" height="' + size + '" viewBox="0 0 24 24" stroke-width="' + sw + '" class="lucide lucide-' + name + '">' + inner + '</svg>';
  }
  function inject(root) {
    root = root || document;
    root.querySelectorAll('i[data-icon]').forEach(function (el) {
      var name = el.getAttribute('data-icon');
      var size = parseInt(el.getAttribute('data-size') || '16', 10);
      var sw = el.getAttribute('data-stroke');
      var wrap = document.createElement('span');
      wrap.style.display = 'inline-flex';
      wrap.innerHTML = svg(name, {
        size: size,
        strokeWidth: sw ? parseFloat(sw) : 2
      });
      if (el.style.color) wrap.style.color = el.style.color;
      el.replaceWith(wrap.firstChild);
    });
  }
  global.PathlyIcons = {
    svg: svg,
    inject: inject,
    names: Object.keys(NODES)
  };
})(window);
})(); } catch (e) { __ds_ns.__errors.push({ path: "assets/vendor/icons.js", error: String((e && e.message) || e) }); }

// assets/vendor/react-dom.production.min.js
try { (() => {
/**
 * @license React
 * react-dom.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
(function () {
  /*
  Modernizr 3.0.0pre (Custom Build) | MIT
  */
  'use strict';

  (function (Q, zb) {
    "object" === typeof exports && "undefined" !== typeof module ? zb(exports, require("react")) : "function" === typeof define && define.amd ? define(["exports", "react"], zb) : (Q = Q || self, zb(Q.ReactDOM = {}, Q.React));
  })(this, function (Q, zb) {
    function m(a) {
      for (var b = "https://reactjs.org/docs/error-decoder.html?invariant=" + a, c = 1; c < arguments.length; c++) b += "&args[]=" + encodeURIComponent(arguments[c]);
      return "Minified React error #" + a + "; visit " + b + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
    }
    function mb(a, b) {
      Ab(a, b);
      Ab(a + "Capture", b);
    }
    function Ab(a, b) {
      $b[a] = b;
      for (a = 0; a < b.length; a++) cg.add(b[a]);
    }
    function bj(a) {
      if (Zd.call(dg, a)) return !0;
      if (Zd.call(eg, a)) return !1;
      if (cj.test(a)) return dg[a] = !0;
      eg[a] = !0;
      return !1;
    }
    function dj(a, b, c, d) {
      if (null !== c && 0 === c.type) return !1;
      switch (typeof b) {
        case "function":
        case "symbol":
          return !0;
        case "boolean":
          if (d) return !1;
          if (null !== c) return !c.acceptsBooleans;
          a = a.toLowerCase().slice(0, 5);
          return "data-" !== a && "aria-" !== a;
        default:
          return !1;
      }
    }
    function ej(a, b, c, d) {
      if (null === b || "undefined" === typeof b || dj(a, b, c, d)) return !0;
      if (d) return !1;
      if (null !== c) switch (c.type) {
        case 3:
          return !b;
        case 4:
          return !1 === b;
        case 5:
          return isNaN(b);
        case 6:
          return isNaN(b) || 1 > b;
      }
      return !1;
    }
    function Y(a, b, c, d, e, f, g) {
      this.acceptsBooleans = 2 === b || 3 === b || 4 === b;
      this.attributeName = d;
      this.attributeNamespace = e;
      this.mustUseProperty = c;
      this.propertyName = a;
      this.type = b;
      this.sanitizeURL = f;
      this.removeEmptyString = g;
    }
    function $d(a, b, c, d) {
      var e = R.hasOwnProperty(b) ? R[b] : null;
      if (null !== e ? 0 !== e.type : d || !(2 < b.length) || "o" !== b[0] && "O" !== b[0] || "n" !== b[1] && "N" !== b[1]) ej(b, c, e, d) && (c = null), d || null === e ? bj(b) && (null === c ? a.removeAttribute(b) : a.setAttribute(b, "" + c)) : e.mustUseProperty ? a[e.propertyName] = null === c ? 3 === e.type ? !1 : "" : c : (b = e.attributeName, d = e.attributeNamespace, null === c ? a.removeAttribute(b) : (e = e.type, c = 3 === e || 4 === e && !0 === c ? "" : "" + c, d ? a.setAttributeNS(d, b, c) : a.setAttribute(b, c)));
    }
    function ac(a) {
      if (null === a || "object" !== typeof a) return null;
      a = fg && a[fg] || a["@@iterator"];
      return "function" === typeof a ? a : null;
    }
    function bc(a, b, c) {
      if (void 0 === ae) try {
        throw Error();
      } catch (d) {
        ae = (b = d.stack.trim().match(/\n( *(at )?)/)) && b[1] || "";
      }
      return "\n" + ae + a;
    }
    function be(a, b) {
      if (!a || ce) return "";
      ce = !0;
      var c = Error.prepareStackTrace;
      Error.prepareStackTrace = void 0;
      try {
        if (b) {
          if (b = function () {
            throw Error();
          }, Object.defineProperty(b.prototype, "props", {
            set: function () {
              throw Error();
            }
          }), "object" === typeof Reflect && Reflect.construct) {
            try {
              Reflect.construct(b, []);
            } catch (n) {
              var d = n;
            }
            Reflect.construct(a, [], b);
          } else {
            try {
              b.call();
            } catch (n) {
              d = n;
            }
            a.call(b.prototype);
          }
        } else {
          try {
            throw Error();
          } catch (n) {
            d = n;
          }
          a();
        }
      } catch (n) {
        if (n && d && "string" === typeof n.stack) {
          for (var e = n.stack.split("\n"), f = d.stack.split("\n"), g = e.length - 1, h = f.length - 1; 1 <= g && 0 <= h && e[g] !== f[h];) h--;
          for (; 1 <= g && 0 <= h; g--, h--) if (e[g] !== f[h]) {
            if (1 !== g || 1 !== h) {
              do if (g--, h--, 0 > h || e[g] !== f[h]) {
                var k = "\n" + e[g].replace(" at new ", " at ");
                a.displayName && k.includes("<anonymous>") && (k = k.replace("<anonymous>", a.displayName));
                return k;
              } while (1 <= g && 0 <= h);
            }
            break;
          }
        }
      } finally {
        ce = !1, Error.prepareStackTrace = c;
      }
      return (a = a ? a.displayName || a.name : "") ? bc(a) : "";
    }
    function fj(a) {
      switch (a.tag) {
        case 5:
          return bc(a.type);
        case 16:
          return bc("Lazy");
        case 13:
          return bc("Suspense");
        case 19:
          return bc("SuspenseList");
        case 0:
        case 2:
        case 15:
          return a = be(a.type, !1), a;
        case 11:
          return a = be(a.type.render, !1), a;
        case 1:
          return a = be(a.type, !0), a;
        default:
          return "";
      }
    }
    function de(a) {
      if (null == a) return null;
      if ("function" === typeof a) return a.displayName || a.name || null;
      if ("string" === typeof a) return a;
      switch (a) {
        case Bb:
          return "Fragment";
        case Cb:
          return "Portal";
        case ee:
          return "Profiler";
        case fe:
          return "StrictMode";
        case ge:
          return "Suspense";
        case he:
          return "SuspenseList";
      }
      if ("object" === typeof a) switch (a.$$typeof) {
        case gg:
          return (a.displayName || "Context") + ".Consumer";
        case hg:
          return (a._context.displayName || "Context") + ".Provider";
        case ie:
          var b = a.render;
          a = a.displayName;
          a || (a = b.displayName || b.name || "", a = "" !== a ? "ForwardRef(" + a + ")" : "ForwardRef");
          return a;
        case je:
          return b = a.displayName || null, null !== b ? b : de(a.type) || "Memo";
        case Ta:
          b = a._payload;
          a = a._init;
          try {
            return de(a(b));
          } catch (c) {}
      }
      return null;
    }
    function gj(a) {
      var b = a.type;
      switch (a.tag) {
        case 24:
          return "Cache";
        case 9:
          return (b.displayName || "Context") + ".Consumer";
        case 10:
          return (b._context.displayName || "Context") + ".Provider";
        case 18:
          return "DehydratedFragment";
        case 11:
          return a = b.render, a = a.displayName || a.name || "", b.displayName || ("" !== a ? "ForwardRef(" + a + ")" : "ForwardRef");
        case 7:
          return "Fragment";
        case 5:
          return b;
        case 4:
          return "Portal";
        case 3:
          return "Root";
        case 6:
          return "Text";
        case 16:
          return de(b);
        case 8:
          return b === fe ? "StrictMode" : "Mode";
        case 22:
          return "Offscreen";
        case 12:
          return "Profiler";
        case 21:
          return "Scope";
        case 13:
          return "Suspense";
        case 19:
          return "SuspenseList";
        case 25:
          return "TracingMarker";
        case 1:
        case 0:
        case 17:
        case 2:
        case 14:
        case 15:
          if ("function" === typeof b) return b.displayName || b.name || null;
          if ("string" === typeof b) return b;
      }
      return null;
    }
    function Ua(a) {
      switch (typeof a) {
        case "boolean":
        case "number":
        case "string":
        case "undefined":
          return a;
        case "object":
          return a;
        default:
          return "";
      }
    }
    function ig(a) {
      var b = a.type;
      return (a = a.nodeName) && "input" === a.toLowerCase() && ("checkbox" === b || "radio" === b);
    }
    function hj(a) {
      var b = ig(a) ? "checked" : "value",
        c = Object.getOwnPropertyDescriptor(a.constructor.prototype, b),
        d = "" + a[b];
      if (!a.hasOwnProperty(b) && "undefined" !== typeof c && "function" === typeof c.get && "function" === typeof c.set) {
        var e = c.get,
          f = c.set;
        Object.defineProperty(a, b, {
          configurable: !0,
          get: function () {
            return e.call(this);
          },
          set: function (a) {
            d = "" + a;
            f.call(this, a);
          }
        });
        Object.defineProperty(a, b, {
          enumerable: c.enumerable
        });
        return {
          getValue: function () {
            return d;
          },
          setValue: function (a) {
            d = "" + a;
          },
          stopTracking: function () {
            a._valueTracker = null;
            delete a[b];
          }
        };
      }
    }
    function Pc(a) {
      a._valueTracker || (a._valueTracker = hj(a));
    }
    function jg(a) {
      if (!a) return !1;
      var b = a._valueTracker;
      if (!b) return !0;
      var c = b.getValue();
      var d = "";
      a && (d = ig(a) ? a.checked ? "true" : "false" : a.value);
      a = d;
      return a !== c ? (b.setValue(a), !0) : !1;
    }
    function Qc(a) {
      a = a || ("undefined" !== typeof document ? document : void 0);
      if ("undefined" === typeof a) return null;
      try {
        return a.activeElement || a.body;
      } catch (b) {
        return a.body;
      }
    }
    function ke(a, b) {
      var c = b.checked;
      return E({}, b, {
        defaultChecked: void 0,
        defaultValue: void 0,
        value: void 0,
        checked: null != c ? c : a._wrapperState.initialChecked
      });
    }
    function kg(a, b) {
      var c = null == b.defaultValue ? "" : b.defaultValue,
        d = null != b.checked ? b.checked : b.defaultChecked;
      c = Ua(null != b.value ? b.value : c);
      a._wrapperState = {
        initialChecked: d,
        initialValue: c,
        controlled: "checkbox" === b.type || "radio" === b.type ? null != b.checked : null != b.value
      };
    }
    function lg(a, b) {
      b = b.checked;
      null != b && $d(a, "checked", b, !1);
    }
    function le(a, b) {
      lg(a, b);
      var c = Ua(b.value),
        d = b.type;
      if (null != c) {
        if ("number" === d) {
          if (0 === c && "" === a.value || a.value != c) a.value = "" + c;
        } else a.value !== "" + c && (a.value = "" + c);
      } else if ("submit" === d || "reset" === d) {
        a.removeAttribute("value");
        return;
      }
      b.hasOwnProperty("value") ? me(a, b.type, c) : b.hasOwnProperty("defaultValue") && me(a, b.type, Ua(b.defaultValue));
      null == b.checked && null != b.defaultChecked && (a.defaultChecked = !!b.defaultChecked);
    }
    function mg(a, b, c) {
      if (b.hasOwnProperty("value") || b.hasOwnProperty("defaultValue")) {
        var d = b.type;
        if (!("submit" !== d && "reset" !== d || void 0 !== b.value && null !== b.value)) return;
        b = "" + a._wrapperState.initialValue;
        c || b === a.value || (a.value = b);
        a.defaultValue = b;
      }
      c = a.name;
      "" !== c && (a.name = "");
      a.defaultChecked = !!a._wrapperState.initialChecked;
      "" !== c && (a.name = c);
    }
    function me(a, b, c) {
      if ("number" !== b || Qc(a.ownerDocument) !== a) null == c ? a.defaultValue = "" + a._wrapperState.initialValue : a.defaultValue !== "" + c && (a.defaultValue = "" + c);
    }
    function Db(a, b, c, d) {
      a = a.options;
      if (b) {
        b = {};
        for (var e = 0; e < c.length; e++) b["$" + c[e]] = !0;
        for (c = 0; c < a.length; c++) e = b.hasOwnProperty("$" + a[c].value), a[c].selected !== e && (a[c].selected = e), e && d && (a[c].defaultSelected = !0);
      } else {
        c = "" + Ua(c);
        b = null;
        for (e = 0; e < a.length; e++) {
          if (a[e].value === c) {
            a[e].selected = !0;
            d && (a[e].defaultSelected = !0);
            return;
          }
          null !== b || a[e].disabled || (b = a[e]);
        }
        null !== b && (b.selected = !0);
      }
    }
    function ne(a, b) {
      if (null != b.dangerouslySetInnerHTML) throw Error(m(91));
      return E({}, b, {
        value: void 0,
        defaultValue: void 0,
        children: "" + a._wrapperState.initialValue
      });
    }
    function ng(a, b) {
      var c = b.value;
      if (null == c) {
        c = b.children;
        b = b.defaultValue;
        if (null != c) {
          if (null != b) throw Error(m(92));
          if (cc(c)) {
            if (1 < c.length) throw Error(m(93));
            c = c[0];
          }
          b = c;
        }
        null == b && (b = "");
        c = b;
      }
      a._wrapperState = {
        initialValue: Ua(c)
      };
    }
    function og(a, b) {
      var c = Ua(b.value),
        d = Ua(b.defaultValue);
      null != c && (c = "" + c, c !== a.value && (a.value = c), null == b.defaultValue && a.defaultValue !== c && (a.defaultValue = c));
      null != d && (a.defaultValue = "" + d);
    }
    function pg(a, b) {
      b = a.textContent;
      b === a._wrapperState.initialValue && "" !== b && null !== b && (a.value = b);
    }
    function qg(a) {
      switch (a) {
        case "svg":
          return "http://www.w3.org/2000/svg";
        case "math":
          return "http://www.w3.org/1998/Math/MathML";
        default:
          return "http://www.w3.org/1999/xhtml";
      }
    }
    function oe(a, b) {
      return null == a || "http://www.w3.org/1999/xhtml" === a ? qg(b) : "http://www.w3.org/2000/svg" === a && "foreignObject" === b ? "http://www.w3.org/1999/xhtml" : a;
    }
    function rg(a, b, c) {
      return null == b || "boolean" === typeof b || "" === b ? "" : c || "number" !== typeof b || 0 === b || dc.hasOwnProperty(a) && dc[a] ? ("" + b).trim() : b + "px";
    }
    function sg(a, b) {
      a = a.style;
      for (var c in b) if (b.hasOwnProperty(c)) {
        var d = 0 === c.indexOf("--"),
          e = rg(c, b[c], d);
        "float" === c && (c = "cssFloat");
        d ? a.setProperty(c, e) : a[c] = e;
      }
    }
    function pe(a, b) {
      if (b) {
        if (ij[a] && (null != b.children || null != b.dangerouslySetInnerHTML)) throw Error(m(137, a));
        if (null != b.dangerouslySetInnerHTML) {
          if (null != b.children) throw Error(m(60));
          if ("object" !== typeof b.dangerouslySetInnerHTML || !("__html" in b.dangerouslySetInnerHTML)) throw Error(m(61));
        }
        if (null != b.style && "object" !== typeof b.style) throw Error(m(62));
      }
    }
    function qe(a, b) {
      if (-1 === a.indexOf("-")) return "string" === typeof b.is;
      switch (a) {
        case "annotation-xml":
        case "color-profile":
        case "font-face":
        case "font-face-src":
        case "font-face-uri":
        case "font-face-format":
        case "font-face-name":
        case "missing-glyph":
          return !1;
        default:
          return !0;
      }
    }
    function re(a) {
      a = a.target || a.srcElement || window;
      a.correspondingUseElement && (a = a.correspondingUseElement);
      return 3 === a.nodeType ? a.parentNode : a;
    }
    function tg(a) {
      if (a = ec(a)) {
        if ("function" !== typeof se) throw Error(m(280));
        var b = a.stateNode;
        b && (b = Rc(b), se(a.stateNode, a.type, b));
      }
    }
    function ug(a) {
      Eb ? Fb ? Fb.push(a) : Fb = [a] : Eb = a;
    }
    function vg() {
      if (Eb) {
        var a = Eb,
          b = Fb;
        Fb = Eb = null;
        tg(a);
        if (b) for (a = 0; a < b.length; a++) tg(b[a]);
      }
    }
    function wg(a, b, c) {
      if (te) return a(b, c);
      te = !0;
      try {
        return xg(a, b, c);
      } finally {
        if (te = !1, null !== Eb || null !== Fb) yg(), vg();
      }
    }
    function fc(a, b) {
      var c = a.stateNode;
      if (null === c) return null;
      var d = Rc(c);
      if (null === d) return null;
      c = d[b];
      a: switch (b) {
        case "onClick":
        case "onClickCapture":
        case "onDoubleClick":
        case "onDoubleClickCapture":
        case "onMouseDown":
        case "onMouseDownCapture":
        case "onMouseMove":
        case "onMouseMoveCapture":
        case "onMouseUp":
        case "onMouseUpCapture":
        case "onMouseEnter":
          (d = !d.disabled) || (a = a.type, d = !("button" === a || "input" === a || "select" === a || "textarea" === a));
          a = !d;
          break a;
        default:
          a = !1;
      }
      if (a) return null;
      if (c && "function" !== typeof c) throw Error(m(231, b, typeof c));
      return c;
    }
    function jj(a, b, c, d, e, f, g, h, k) {
      gc = !1;
      Sc = null;
      kj.apply(lj, arguments);
    }
    function mj(a, b, c, d, e, f, g, h, k) {
      jj.apply(this, arguments);
      if (gc) {
        if (gc) {
          var n = Sc;
          gc = !1;
          Sc = null;
        } else throw Error(m(198));
        Tc || (Tc = !0, ue = n);
      }
    }
    function nb(a) {
      var b = a,
        c = a;
      if (a.alternate) for (; b.return;) b = b.return;else {
        a = b;
        do b = a, 0 !== (b.flags & 4098) && (c = b.return), a = b.return; while (a);
      }
      return 3 === b.tag ? c : null;
    }
    function zg(a) {
      if (13 === a.tag) {
        var b = a.memoizedState;
        null === b && (a = a.alternate, null !== a && (b = a.memoizedState));
        if (null !== b) return b.dehydrated;
      }
      return null;
    }
    function Ag(a) {
      if (nb(a) !== a) throw Error(m(188));
    }
    function nj(a) {
      var b = a.alternate;
      if (!b) {
        b = nb(a);
        if (null === b) throw Error(m(188));
        return b !== a ? null : a;
      }
      for (var c = a, d = b;;) {
        var e = c.return;
        if (null === e) break;
        var f = e.alternate;
        if (null === f) {
          d = e.return;
          if (null !== d) {
            c = d;
            continue;
          }
          break;
        }
        if (e.child === f.child) {
          for (f = e.child; f;) {
            if (f === c) return Ag(e), a;
            if (f === d) return Ag(e), b;
            f = f.sibling;
          }
          throw Error(m(188));
        }
        if (c.return !== d.return) c = e, d = f;else {
          for (var g = !1, h = e.child; h;) {
            if (h === c) {
              g = !0;
              c = e;
              d = f;
              break;
            }
            if (h === d) {
              g = !0;
              d = e;
              c = f;
              break;
            }
            h = h.sibling;
          }
          if (!g) {
            for (h = f.child; h;) {
              if (h === c) {
                g = !0;
                c = f;
                d = e;
                break;
              }
              if (h === d) {
                g = !0;
                d = f;
                c = e;
                break;
              }
              h = h.sibling;
            }
            if (!g) throw Error(m(189));
          }
        }
        if (c.alternate !== d) throw Error(m(190));
      }
      if (3 !== c.tag) throw Error(m(188));
      return c.stateNode.current === c ? a : b;
    }
    function Bg(a) {
      a = nj(a);
      return null !== a ? Cg(a) : null;
    }
    function Cg(a) {
      if (5 === a.tag || 6 === a.tag) return a;
      for (a = a.child; null !== a;) {
        var b = Cg(a);
        if (null !== b) return b;
        a = a.sibling;
      }
      return null;
    }
    function oj(a, b) {
      if (Ca && "function" === typeof Ca.onCommitFiberRoot) try {
        Ca.onCommitFiberRoot(Uc, a, void 0, 128 === (a.current.flags & 128));
      } catch (c) {}
    }
    function pj(a) {
      a >>>= 0;
      return 0 === a ? 32 : 31 - (qj(a) / rj | 0) | 0;
    }
    function hc(a) {
      switch (a & -a) {
        case 1:
          return 1;
        case 2:
          return 2;
        case 4:
          return 4;
        case 8:
          return 8;
        case 16:
          return 16;
        case 32:
          return 32;
        case 64:
        case 128:
        case 256:
        case 512:
        case 1024:
        case 2048:
        case 4096:
        case 8192:
        case 16384:
        case 32768:
        case 65536:
        case 131072:
        case 262144:
        case 524288:
        case 1048576:
        case 2097152:
          return a & 4194240;
        case 4194304:
        case 8388608:
        case 16777216:
        case 33554432:
        case 67108864:
          return a & 130023424;
        case 134217728:
          return 134217728;
        case 268435456:
          return 268435456;
        case 536870912:
          return 536870912;
        case 1073741824:
          return 1073741824;
        default:
          return a;
      }
    }
    function Vc(a, b) {
      var c = a.pendingLanes;
      if (0 === c) return 0;
      var d = 0,
        e = a.suspendedLanes,
        f = a.pingedLanes,
        g = c & 268435455;
      if (0 !== g) {
        var h = g & ~e;
        0 !== h ? d = hc(h) : (f &= g, 0 !== f && (d = hc(f)));
      } else g = c & ~e, 0 !== g ? d = hc(g) : 0 !== f && (d = hc(f));
      if (0 === d) return 0;
      if (0 !== b && b !== d && 0 === (b & e) && (e = d & -d, f = b & -b, e >= f || 16 === e && 0 !== (f & 4194240))) return b;
      0 !== (d & 4) && (d |= c & 16);
      b = a.entangledLanes;
      if (0 !== b) for (a = a.entanglements, b &= d; 0 < b;) c = 31 - ta(b), e = 1 << c, d |= a[c], b &= ~e;
      return d;
    }
    function sj(a, b) {
      switch (a) {
        case 1:
        case 2:
        case 4:
          return b + 250;
        case 8:
        case 16:
        case 32:
        case 64:
        case 128:
        case 256:
        case 512:
        case 1024:
        case 2048:
        case 4096:
        case 8192:
        case 16384:
        case 32768:
        case 65536:
        case 131072:
        case 262144:
        case 524288:
        case 1048576:
        case 2097152:
          return b + 5E3;
        case 4194304:
        case 8388608:
        case 16777216:
        case 33554432:
        case 67108864:
          return -1;
        case 134217728:
        case 268435456:
        case 536870912:
        case 1073741824:
          return -1;
        default:
          return -1;
      }
    }
    function tj(a, b) {
      for (var c = a.suspendedLanes, d = a.pingedLanes, e = a.expirationTimes, f = a.pendingLanes; 0 < f;) {
        var g = 31 - ta(f),
          h = 1 << g,
          k = e[g];
        if (-1 === k) {
          if (0 === (h & c) || 0 !== (h & d)) e[g] = sj(h, b);
        } else k <= b && (a.expiredLanes |= h);
        f &= ~h;
      }
    }
    function ve(a) {
      a = a.pendingLanes & -1073741825;
      return 0 !== a ? a : a & 1073741824 ? 1073741824 : 0;
    }
    function Dg() {
      var a = Wc;
      Wc <<= 1;
      0 === (Wc & 4194240) && (Wc = 64);
      return a;
    }
    function we(a) {
      for (var b = [], c = 0; 31 > c; c++) b.push(a);
      return b;
    }
    function ic(a, b, c) {
      a.pendingLanes |= b;
      536870912 !== b && (a.suspendedLanes = 0, a.pingedLanes = 0);
      a = a.eventTimes;
      b = 31 - ta(b);
      a[b] = c;
    }
    function uj(a, b) {
      var c = a.pendingLanes & ~b;
      a.pendingLanes = b;
      a.suspendedLanes = 0;
      a.pingedLanes = 0;
      a.expiredLanes &= b;
      a.mutableReadLanes &= b;
      a.entangledLanes &= b;
      b = a.entanglements;
      var d = a.eventTimes;
      for (a = a.expirationTimes; 0 < c;) {
        var e = 31 - ta(c),
          f = 1 << e;
        b[e] = 0;
        d[e] = -1;
        a[e] = -1;
        c &= ~f;
      }
    }
    function xe(a, b) {
      var c = a.entangledLanes |= b;
      for (a = a.entanglements; c;) {
        var d = 31 - ta(c),
          e = 1 << d;
        e & b | a[d] & b && (a[d] |= b);
        c &= ~e;
      }
    }
    function Eg(a) {
      a &= -a;
      return 1 < a ? 4 < a ? 0 !== (a & 268435455) ? 16 : 536870912 : 4 : 1;
    }
    function Fg(a, b) {
      switch (a) {
        case "focusin":
        case "focusout":
          Va = null;
          break;
        case "dragenter":
        case "dragleave":
          Wa = null;
          break;
        case "mouseover":
        case "mouseout":
          Xa = null;
          break;
        case "pointerover":
        case "pointerout":
          jc.delete(b.pointerId);
          break;
        case "gotpointercapture":
        case "lostpointercapture":
          kc.delete(b.pointerId);
      }
    }
    function lc(a, b, c, d, e, f) {
      if (null === a || a.nativeEvent !== f) return a = {
        blockedOn: b,
        domEventName: c,
        eventSystemFlags: d,
        nativeEvent: f,
        targetContainers: [e]
      }, null !== b && (b = ec(b), null !== b && Gg(b)), a;
      a.eventSystemFlags |= d;
      b = a.targetContainers;
      null !== e && -1 === b.indexOf(e) && b.push(e);
      return a;
    }
    function vj(a, b, c, d, e) {
      switch (b) {
        case "focusin":
          return Va = lc(Va, a, b, c, d, e), !0;
        case "dragenter":
          return Wa = lc(Wa, a, b, c, d, e), !0;
        case "mouseover":
          return Xa = lc(Xa, a, b, c, d, e), !0;
        case "pointerover":
          var f = e.pointerId;
          jc.set(f, lc(jc.get(f) || null, a, b, c, d, e));
          return !0;
        case "gotpointercapture":
          return f = e.pointerId, kc.set(f, lc(kc.get(f) || null, a, b, c, d, e)), !0;
      }
      return !1;
    }
    function Hg(a) {
      var b = ob(a.target);
      if (null !== b) {
        var c = nb(b);
        if (null !== c) if (b = c.tag, 13 === b) {
          if (b = zg(c), null !== b) {
            a.blockedOn = b;
            wj(a.priority, function () {
              xj(c);
            });
            return;
          }
        } else if (3 === b && c.stateNode.current.memoizedState.isDehydrated) {
          a.blockedOn = 3 === c.tag ? c.stateNode.containerInfo : null;
          return;
        }
      }
      a.blockedOn = null;
    }
    function Xc(a) {
      if (null !== a.blockedOn) return !1;
      for (var b = a.targetContainers; 0 < b.length;) {
        var c = ye(a.domEventName, a.eventSystemFlags, b[0], a.nativeEvent);
        if (null === c) {
          c = a.nativeEvent;
          var d = new c.constructor(c.type, c);
          ze = d;
          c.target.dispatchEvent(d);
          ze = null;
        } else return b = ec(c), null !== b && Gg(b), a.blockedOn = c, !1;
        b.shift();
      }
      return !0;
    }
    function Ig(a, b, c) {
      Xc(a) && c.delete(b);
    }
    function yj() {
      Ae = !1;
      null !== Va && Xc(Va) && (Va = null);
      null !== Wa && Xc(Wa) && (Wa = null);
      null !== Xa && Xc(Xa) && (Xa = null);
      jc.forEach(Ig);
      kc.forEach(Ig);
    }
    function mc(a, b) {
      a.blockedOn === b && (a.blockedOn = null, Ae || (Ae = !0, Jg(Kg, yj)));
    }
    function nc(a) {
      if (0 < Yc.length) {
        mc(Yc[0], a);
        for (var b = 1; b < Yc.length; b++) {
          var c = Yc[b];
          c.blockedOn === a && (c.blockedOn = null);
        }
      }
      null !== Va && mc(Va, a);
      null !== Wa && mc(Wa, a);
      null !== Xa && mc(Xa, a);
      b = function (b) {
        return mc(b, a);
      };
      jc.forEach(b);
      kc.forEach(b);
      for (b = 0; b < Ya.length; b++) c = Ya[b], c.blockedOn === a && (c.blockedOn = null);
      for (; 0 < Ya.length && (b = Ya[0], null === b.blockedOn);) Hg(b), null === b.blockedOn && Ya.shift();
    }
    function zj(a, b, c, d) {
      var e = z,
        f = Gb.transition;
      Gb.transition = null;
      try {
        z = 1, Be(a, b, c, d);
      } finally {
        z = e, Gb.transition = f;
      }
    }
    function Aj(a, b, c, d) {
      var e = z,
        f = Gb.transition;
      Gb.transition = null;
      try {
        z = 4, Be(a, b, c, d);
      } finally {
        z = e, Gb.transition = f;
      }
    }
    function Be(a, b, c, d) {
      if (Zc) {
        var e = ye(a, b, c, d);
        if (null === e) Ce(a, b, d, $c, c), Fg(a, d);else if (vj(e, a, b, c, d)) d.stopPropagation();else if (Fg(a, d), b & 4 && -1 < Bj.indexOf(a)) {
          for (; null !== e;) {
            var f = ec(e);
            null !== f && Cj(f);
            f = ye(a, b, c, d);
            null === f && Ce(a, b, d, $c, c);
            if (f === e) break;
            e = f;
          }
          null !== e && d.stopPropagation();
        } else Ce(a, b, d, null, c);
      }
    }
    function ye(a, b, c, d) {
      $c = null;
      a = re(d);
      a = ob(a);
      if (null !== a) if (b = nb(a), null === b) a = null;else if (c = b.tag, 13 === c) {
        a = zg(b);
        if (null !== a) return a;
        a = null;
      } else if (3 === c) {
        if (b.stateNode.current.memoizedState.isDehydrated) return 3 === b.tag ? b.stateNode.containerInfo : null;
        a = null;
      } else b !== a && (a = null);
      $c = a;
      return null;
    }
    function Lg(a) {
      switch (a) {
        case "cancel":
        case "click":
        case "close":
        case "contextmenu":
        case "copy":
        case "cut":
        case "auxclick":
        case "dblclick":
        case "dragend":
        case "dragstart":
        case "drop":
        case "focusin":
        case "focusout":
        case "input":
        case "invalid":
        case "keydown":
        case "keypress":
        case "keyup":
        case "mousedown":
        case "mouseup":
        case "paste":
        case "pause":
        case "play":
        case "pointercancel":
        case "pointerdown":
        case "pointerup":
        case "ratechange":
        case "reset":
        case "resize":
        case "seeked":
        case "submit":
        case "touchcancel":
        case "touchend":
        case "touchstart":
        case "volumechange":
        case "change":
        case "selectionchange":
        case "textInput":
        case "compositionstart":
        case "compositionend":
        case "compositionupdate":
        case "beforeblur":
        case "afterblur":
        case "beforeinput":
        case "blur":
        case "fullscreenchange":
        case "focus":
        case "hashchange":
        case "popstate":
        case "select":
        case "selectstart":
          return 1;
        case "drag":
        case "dragenter":
        case "dragexit":
        case "dragleave":
        case "dragover":
        case "mousemove":
        case "mouseout":
        case "mouseover":
        case "pointermove":
        case "pointerout":
        case "pointerover":
        case "scroll":
        case "toggle":
        case "touchmove":
        case "wheel":
        case "mouseenter":
        case "mouseleave":
        case "pointerenter":
        case "pointerleave":
          return 4;
        case "message":
          switch (Dj()) {
            case De:
              return 1;
            case Mg:
              return 4;
            case ad:
            case Ej:
              return 16;
            case Ng:
              return 536870912;
            default:
              return 16;
          }
        default:
          return 16;
      }
    }
    function Og() {
      if (bd) return bd;
      var a,
        b = Ee,
        c = b.length,
        d,
        e = "value" in Za ? Za.value : Za.textContent,
        f = e.length;
      for (a = 0; a < c && b[a] === e[a]; a++);
      var g = c - a;
      for (d = 1; d <= g && b[c - d] === e[f - d]; d++);
      return bd = e.slice(a, 1 < d ? 1 - d : void 0);
    }
    function cd(a) {
      var b = a.keyCode;
      "charCode" in a ? (a = a.charCode, 0 === a && 13 === b && (a = 13)) : a = b;
      10 === a && (a = 13);
      return 32 <= a || 13 === a ? a : 0;
    }
    function dd() {
      return !0;
    }
    function Pg() {
      return !1;
    }
    function ka(a) {
      function b(b, d, e, f, g) {
        this._reactName = b;
        this._targetInst = e;
        this.type = d;
        this.nativeEvent = f;
        this.target = g;
        this.currentTarget = null;
        for (var c in a) a.hasOwnProperty(c) && (b = a[c], this[c] = b ? b(f) : f[c]);
        this.isDefaultPrevented = (null != f.defaultPrevented ? f.defaultPrevented : !1 === f.returnValue) ? dd : Pg;
        this.isPropagationStopped = Pg;
        return this;
      }
      E(b.prototype, {
        preventDefault: function () {
          this.defaultPrevented = !0;
          var a = this.nativeEvent;
          a && (a.preventDefault ? a.preventDefault() : "unknown" !== typeof a.returnValue && (a.returnValue = !1), this.isDefaultPrevented = dd);
        },
        stopPropagation: function () {
          var a = this.nativeEvent;
          a && (a.stopPropagation ? a.stopPropagation() : "unknown" !== typeof a.cancelBubble && (a.cancelBubble = !0), this.isPropagationStopped = dd);
        },
        persist: function () {},
        isPersistent: dd
      });
      return b;
    }
    function Fj(a) {
      var b = this.nativeEvent;
      return b.getModifierState ? b.getModifierState(a) : (a = Gj[a]) ? !!b[a] : !1;
    }
    function Fe(a) {
      return Fj;
    }
    function Qg(a, b) {
      switch (a) {
        case "keyup":
          return -1 !== Hj.indexOf(b.keyCode);
        case "keydown":
          return 229 !== b.keyCode;
        case "keypress":
        case "mousedown":
        case "focusout":
          return !0;
        default:
          return !1;
      }
    }
    function Rg(a) {
      a = a.detail;
      return "object" === typeof a && "data" in a ? a.data : null;
    }
    function Ij(a, b) {
      switch (a) {
        case "compositionend":
          return Rg(b);
        case "keypress":
          if (32 !== b.which) return null;
          Sg = !0;
          return Tg;
        case "textInput":
          return a = b.data, a === Tg && Sg ? null : a;
        default:
          return null;
      }
    }
    function Jj(a, b) {
      if (Hb) return "compositionend" === a || !Ge && Qg(a, b) ? (a = Og(), bd = Ee = Za = null, Hb = !1, a) : null;
      switch (a) {
        case "paste":
          return null;
        case "keypress":
          if (!(b.ctrlKey || b.altKey || b.metaKey) || b.ctrlKey && b.altKey) {
            if (b.char && 1 < b.char.length) return b.char;
            if (b.which) return String.fromCharCode(b.which);
          }
          return null;
        case "compositionend":
          return Ug && "ko" !== b.locale ? null : b.data;
        default:
          return null;
      }
    }
    function Vg(a) {
      var b = a && a.nodeName && a.nodeName.toLowerCase();
      return "input" === b ? !!Kj[a.type] : "textarea" === b ? !0 : !1;
    }
    function Lj(a) {
      if (!Ia) return !1;
      a = "on" + a;
      var b = a in document;
      b || (b = document.createElement("div"), b.setAttribute(a, "return;"), b = "function" === typeof b[a]);
      return b;
    }
    function Wg(a, b, c, d) {
      ug(d);
      b = ed(b, "onChange");
      0 < b.length && (c = new He("onChange", "change", null, c, d), a.push({
        event: c,
        listeners: b
      }));
    }
    function Mj(a) {
      Xg(a, 0);
    }
    function fd(a) {
      var b = Ib(a);
      if (jg(b)) return a;
    }
    function Nj(a, b) {
      if ("change" === a) return b;
    }
    function Yg() {
      oc && (oc.detachEvent("onpropertychange", Zg), pc = oc = null);
    }
    function Zg(a) {
      if ("value" === a.propertyName && fd(pc)) {
        var b = [];
        Wg(b, pc, a, re(a));
        wg(Mj, b);
      }
    }
    function Oj(a, b, c) {
      "focusin" === a ? (Yg(), oc = b, pc = c, oc.attachEvent("onpropertychange", Zg)) : "focusout" === a && Yg();
    }
    function Pj(a, b) {
      if ("selectionchange" === a || "keyup" === a || "keydown" === a) return fd(pc);
    }
    function Qj(a, b) {
      if ("click" === a) return fd(b);
    }
    function Rj(a, b) {
      if ("input" === a || "change" === a) return fd(b);
    }
    function Sj(a, b) {
      return a === b && (0 !== a || 1 / a === 1 / b) || a !== a && b !== b;
    }
    function qc(a, b) {
      if (ua(a, b)) return !0;
      if ("object" !== typeof a || null === a || "object" !== typeof b || null === b) return !1;
      var c = Object.keys(a),
        d = Object.keys(b);
      if (c.length !== d.length) return !1;
      for (d = 0; d < c.length; d++) {
        var e = c[d];
        if (!Zd.call(b, e) || !ua(a[e], b[e])) return !1;
      }
      return !0;
    }
    function $g(a) {
      for (; a && a.firstChild;) a = a.firstChild;
      return a;
    }
    function ah(a, b) {
      var c = $g(a);
      a = 0;
      for (var d; c;) {
        if (3 === c.nodeType) {
          d = a + c.textContent.length;
          if (a <= b && d >= b) return {
            node: c,
            offset: b - a
          };
          a = d;
        }
        a: {
          for (; c;) {
            if (c.nextSibling) {
              c = c.nextSibling;
              break a;
            }
            c = c.parentNode;
          }
          c = void 0;
        }
        c = $g(c);
      }
    }
    function bh(a, b) {
      return a && b ? a === b ? !0 : a && 3 === a.nodeType ? !1 : b && 3 === b.nodeType ? bh(a, b.parentNode) : "contains" in a ? a.contains(b) : a.compareDocumentPosition ? !!(a.compareDocumentPosition(b) & 16) : !1 : !1;
    }
    function ch() {
      for (var a = window, b = Qc(); b instanceof a.HTMLIFrameElement;) {
        try {
          var c = "string" === typeof b.contentWindow.location.href;
        } catch (d) {
          c = !1;
        }
        if (c) a = b.contentWindow;else break;
        b = Qc(a.document);
      }
      return b;
    }
    function Ie(a) {
      var b = a && a.nodeName && a.nodeName.toLowerCase();
      return b && ("input" === b && ("text" === a.type || "search" === a.type || "tel" === a.type || "url" === a.type || "password" === a.type) || "textarea" === b || "true" === a.contentEditable);
    }
    function Tj(a) {
      var b = ch(),
        c = a.focusedElem,
        d = a.selectionRange;
      if (b !== c && c && c.ownerDocument && bh(c.ownerDocument.documentElement, c)) {
        if (null !== d && Ie(c)) if (b = d.start, a = d.end, void 0 === a && (a = b), "selectionStart" in c) c.selectionStart = b, c.selectionEnd = Math.min(a, c.value.length);else if (a = (b = c.ownerDocument || document) && b.defaultView || window, a.getSelection) {
          a = a.getSelection();
          var e = c.textContent.length,
            f = Math.min(d.start, e);
          d = void 0 === d.end ? f : Math.min(d.end, e);
          !a.extend && f > d && (e = d, d = f, f = e);
          e = ah(c, f);
          var g = ah(c, d);
          e && g && (1 !== a.rangeCount || a.anchorNode !== e.node || a.anchorOffset !== e.offset || a.focusNode !== g.node || a.focusOffset !== g.offset) && (b = b.createRange(), b.setStart(e.node, e.offset), a.removeAllRanges(), f > d ? (a.addRange(b), a.extend(g.node, g.offset)) : (b.setEnd(g.node, g.offset), a.addRange(b)));
        }
        b = [];
        for (a = c; a = a.parentNode;) 1 === a.nodeType && b.push({
          element: a,
          left: a.scrollLeft,
          top: a.scrollTop
        });
        "function" === typeof c.focus && c.focus();
        for (c = 0; c < b.length; c++) a = b[c], a.element.scrollLeft = a.left, a.element.scrollTop = a.top;
      }
    }
    function dh(a, b, c) {
      var d = c.window === c ? c.document : 9 === c.nodeType ? c : c.ownerDocument;
      Je || null == Jb || Jb !== Qc(d) || (d = Jb, "selectionStart" in d && Ie(d) ? d = {
        start: d.selectionStart,
        end: d.selectionEnd
      } : (d = (d.ownerDocument && d.ownerDocument.defaultView || window).getSelection(), d = {
        anchorNode: d.anchorNode,
        anchorOffset: d.anchorOffset,
        focusNode: d.focusNode,
        focusOffset: d.focusOffset
      }), rc && qc(rc, d) || (rc = d, d = ed(Ke, "onSelect"), 0 < d.length && (b = new He("onSelect", "select", null, b, c), a.push({
        event: b,
        listeners: d
      }), b.target = Jb)));
    }
    function gd(a, b) {
      var c = {};
      c[a.toLowerCase()] = b.toLowerCase();
      c["Webkit" + a] = "webkit" + b;
      c["Moz" + a] = "moz" + b;
      return c;
    }
    function hd(a) {
      if (Le[a]) return Le[a];
      if (!Kb[a]) return a;
      var b = Kb[a],
        c;
      for (c in b) if (b.hasOwnProperty(c) && c in eh) return Le[a] = b[c];
      return a;
    }
    function $a(a, b) {
      fh.set(a, b);
      mb(b, [a]);
    }
    function gh(a, b, c) {
      var d = a.type || "unknown-event";
      a.currentTarget = c;
      mj(d, b, void 0, a);
      a.currentTarget = null;
    }
    function Xg(a, b) {
      b = 0 !== (b & 4);
      for (var c = 0; c < a.length; c++) {
        var d = a[c],
          e = d.event;
        d = d.listeners;
        a: {
          var f = void 0;
          if (b) for (var g = d.length - 1; 0 <= g; g--) {
            var h = d[g],
              k = h.instance,
              n = h.currentTarget;
            h = h.listener;
            if (k !== f && e.isPropagationStopped()) break a;
            gh(e, h, n);
            f = k;
          } else for (g = 0; g < d.length; g++) {
            h = d[g];
            k = h.instance;
            n = h.currentTarget;
            h = h.listener;
            if (k !== f && e.isPropagationStopped()) break a;
            gh(e, h, n);
            f = k;
          }
        }
      }
      if (Tc) throw a = ue, Tc = !1, ue = null, a;
    }
    function B(a, b) {
      var c = b[Me];
      void 0 === c && (c = b[Me] = new Set());
      var d = a + "__bubble";
      c.has(d) || (hh(b, a, 2, !1), c.add(d));
    }
    function Ne(a, b, c) {
      var d = 0;
      b && (d |= 4);
      hh(c, a, d, b);
    }
    function sc(a) {
      if (!a[id]) {
        a[id] = !0;
        cg.forEach(function (b) {
          "selectionchange" !== b && (Uj.has(b) || Ne(b, !1, a), Ne(b, !0, a));
        });
        var b = 9 === a.nodeType ? a : a.ownerDocument;
        null === b || b[id] || (b[id] = !0, Ne("selectionchange", !1, b));
      }
    }
    function hh(a, b, c, d, e) {
      switch (Lg(b)) {
        case 1:
          e = zj;
          break;
        case 4:
          e = Aj;
          break;
        default:
          e = Be;
      }
      c = e.bind(null, b, c, a);
      e = void 0;
      !Oe || "touchstart" !== b && "touchmove" !== b && "wheel" !== b || (e = !0);
      d ? void 0 !== e ? a.addEventListener(b, c, {
        capture: !0,
        passive: e
      }) : a.addEventListener(b, c, !0) : void 0 !== e ? a.addEventListener(b, c, {
        passive: e
      }) : a.addEventListener(b, c, !1);
    }
    function Ce(a, b, c, d, e) {
      var f = d;
      if (0 === (b & 1) && 0 === (b & 2) && null !== d) a: for (;;) {
        if (null === d) return;
        var g = d.tag;
        if (3 === g || 4 === g) {
          var h = d.stateNode.containerInfo;
          if (h === e || 8 === h.nodeType && h.parentNode === e) break;
          if (4 === g) for (g = d.return; null !== g;) {
            var k = g.tag;
            if (3 === k || 4 === k) if (k = g.stateNode.containerInfo, k === e || 8 === k.nodeType && k.parentNode === e) return;
            g = g.return;
          }
          for (; null !== h;) {
            g = ob(h);
            if (null === g) return;
            k = g.tag;
            if (5 === k || 6 === k) {
              d = f = g;
              continue a;
            }
            h = h.parentNode;
          }
        }
        d = d.return;
      }
      wg(function () {
        var d = f,
          e = re(c),
          g = [];
        a: {
          var h = fh.get(a);
          if (void 0 !== h) {
            var k = He,
              m = a;
            switch (a) {
              case "keypress":
                if (0 === cd(c)) break a;
              case "keydown":
              case "keyup":
                k = Vj;
                break;
              case "focusin":
                m = "focus";
                k = Pe;
                break;
              case "focusout":
                m = "blur";
                k = Pe;
                break;
              case "beforeblur":
              case "afterblur":
                k = Pe;
                break;
              case "click":
                if (2 === c.button) break a;
              case "auxclick":
              case "dblclick":
              case "mousedown":
              case "mousemove":
              case "mouseup":
              case "mouseout":
              case "mouseover":
              case "contextmenu":
                k = ih;
                break;
              case "drag":
              case "dragend":
              case "dragenter":
              case "dragexit":
              case "dragleave":
              case "dragover":
              case "dragstart":
              case "drop":
                k = Wj;
                break;
              case "touchcancel":
              case "touchend":
              case "touchmove":
              case "touchstart":
                k = Xj;
                break;
              case jh:
              case kh:
              case lh:
                k = Yj;
                break;
              case mh:
                k = Zj;
                break;
              case "scroll":
                k = ak;
                break;
              case "wheel":
                k = bk;
                break;
              case "copy":
              case "cut":
              case "paste":
                k = ck;
                break;
              case "gotpointercapture":
              case "lostpointercapture":
              case "pointercancel":
              case "pointerdown":
              case "pointermove":
              case "pointerout":
              case "pointerover":
              case "pointerup":
                k = nh;
            }
            var l = 0 !== (b & 4),
              p = !l && "scroll" === a,
              w = l ? null !== h ? h + "Capture" : null : h;
            l = [];
            for (var A = d, t; null !== A;) {
              t = A;
              var M = t.stateNode;
              5 === t.tag && null !== M && (t = M, null !== w && (M = fc(A, w), null != M && l.push(tc(A, M, t))));
              if (p) break;
              A = A.return;
            }
            0 < l.length && (h = new k(h, m, null, c, e), g.push({
              event: h,
              listeners: l
            }));
          }
        }
        if (0 === (b & 7)) {
          a: {
            h = "mouseover" === a || "pointerover" === a;
            k = "mouseout" === a || "pointerout" === a;
            if (h && c !== ze && (m = c.relatedTarget || c.fromElement) && (ob(m) || m[Ja])) break a;
            if (k || h) {
              h = e.window === e ? e : (h = e.ownerDocument) ? h.defaultView || h.parentWindow : window;
              if (k) {
                if (m = c.relatedTarget || c.toElement, k = d, m = m ? ob(m) : null, null !== m && (p = nb(m), m !== p || 5 !== m.tag && 6 !== m.tag)) m = null;
              } else k = null, m = d;
              if (k !== m) {
                l = ih;
                M = "onMouseLeave";
                w = "onMouseEnter";
                A = "mouse";
                if ("pointerout" === a || "pointerover" === a) l = nh, M = "onPointerLeave", w = "onPointerEnter", A = "pointer";
                p = null == k ? h : Ib(k);
                t = null == m ? h : Ib(m);
                h = new l(M, A + "leave", k, c, e);
                h.target = p;
                h.relatedTarget = t;
                M = null;
                ob(e) === d && (l = new l(w, A + "enter", m, c, e), l.target = t, l.relatedTarget = p, M = l);
                p = M;
                if (k && m) b: {
                  l = k;
                  w = m;
                  A = 0;
                  for (t = l; t; t = Lb(t)) A++;
                  t = 0;
                  for (M = w; M; M = Lb(M)) t++;
                  for (; 0 < A - t;) l = Lb(l), A--;
                  for (; 0 < t - A;) w = Lb(w), t--;
                  for (; A--;) {
                    if (l === w || null !== w && l === w.alternate) break b;
                    l = Lb(l);
                    w = Lb(w);
                  }
                  l = null;
                } else l = null;
                null !== k && oh(g, h, k, l, !1);
                null !== m && null !== p && oh(g, p, m, l, !0);
              }
            }
          }
          a: {
            h = d ? Ib(d) : window;
            k = h.nodeName && h.nodeName.toLowerCase();
            if ("select" === k || "input" === k && "file" === h.type) var ma = Nj;else if (Vg(h)) {
              if (ph) ma = Rj;else {
                ma = Pj;
                var va = Oj;
              }
            } else (k = h.nodeName) && "input" === k.toLowerCase() && ("checkbox" === h.type || "radio" === h.type) && (ma = Qj);
            if (ma && (ma = ma(a, d))) {
              Wg(g, ma, c, e);
              break a;
            }
            va && va(a, h, d);
            "focusout" === a && (va = h._wrapperState) && va.controlled && "number" === h.type && me(h, "number", h.value);
          }
          va = d ? Ib(d) : window;
          switch (a) {
            case "focusin":
              if (Vg(va) || "true" === va.contentEditable) Jb = va, Ke = d, rc = null;
              break;
            case "focusout":
              rc = Ke = Jb = null;
              break;
            case "mousedown":
              Je = !0;
              break;
            case "contextmenu":
            case "mouseup":
            case "dragend":
              Je = !1;
              dh(g, c, e);
              break;
            case "selectionchange":
              if (dk) break;
            case "keydown":
            case "keyup":
              dh(g, c, e);
          }
          var ab;
          if (Ge) b: {
            switch (a) {
              case "compositionstart":
                var da = "onCompositionStart";
                break b;
              case "compositionend":
                da = "onCompositionEnd";
                break b;
              case "compositionupdate":
                da = "onCompositionUpdate";
                break b;
            }
            da = void 0;
          } else Hb ? Qg(a, c) && (da = "onCompositionEnd") : "keydown" === a && 229 === c.keyCode && (da = "onCompositionStart");
          da && (Ug && "ko" !== c.locale && (Hb || "onCompositionStart" !== da ? "onCompositionEnd" === da && Hb && (ab = Og()) : (Za = e, Ee = "value" in Za ? Za.value : Za.textContent, Hb = !0)), va = ed(d, da), 0 < va.length && (da = new qh(da, a, null, c, e), g.push({
            event: da,
            listeners: va
          }), ab ? da.data = ab : (ab = Rg(c), null !== ab && (da.data = ab))));
          if (ab = ek ? Ij(a, c) : Jj(a, c)) d = ed(d, "onBeforeInput"), 0 < d.length && (e = new fk("onBeforeInput", "beforeinput", null, c, e), g.push({
            event: e,
            listeners: d
          }), e.data = ab);
        }
        Xg(g, b);
      });
    }
    function tc(a, b, c) {
      return {
        instance: a,
        listener: b,
        currentTarget: c
      };
    }
    function ed(a, b) {
      for (var c = b + "Capture", d = []; null !== a;) {
        var e = a,
          f = e.stateNode;
        5 === e.tag && null !== f && (e = f, f = fc(a, c), null != f && d.unshift(tc(a, f, e)), f = fc(a, b), null != f && d.push(tc(a, f, e)));
        a = a.return;
      }
      return d;
    }
    function Lb(a) {
      if (null === a) return null;
      do a = a.return; while (a && 5 !== a.tag);
      return a ? a : null;
    }
    function oh(a, b, c, d, e) {
      for (var f = b._reactName, g = []; null !== c && c !== d;) {
        var h = c,
          k = h.alternate,
          n = h.stateNode;
        if (null !== k && k === d) break;
        5 === h.tag && null !== n && (h = n, e ? (k = fc(c, f), null != k && g.unshift(tc(c, k, h))) : e || (k = fc(c, f), null != k && g.push(tc(c, k, h))));
        c = c.return;
      }
      0 !== g.length && a.push({
        event: b,
        listeners: g
      });
    }
    function rh(a) {
      return ("string" === typeof a ? a : "" + a).replace(gk, "\n").replace(hk, "");
    }
    function jd(a, b, c, d) {
      b = rh(b);
      if (rh(a) !== b && c) throw Error(m(425));
    }
    function kd() {}
    function Qe(a, b) {
      return "textarea" === a || "noscript" === a || "string" === typeof b.children || "number" === typeof b.children || "object" === typeof b.dangerouslySetInnerHTML && null !== b.dangerouslySetInnerHTML && null != b.dangerouslySetInnerHTML.__html;
    }
    function ik(a) {
      setTimeout(function () {
        throw a;
      });
    }
    function Re(a, b) {
      var c = b,
        d = 0;
      do {
        var e = c.nextSibling;
        a.removeChild(c);
        if (e && 8 === e.nodeType) if (c = e.data, "/$" === c) {
          if (0 === d) {
            a.removeChild(e);
            nc(b);
            return;
          }
          d--;
        } else "$" !== c && "$?" !== c && "$!" !== c || d++;
        c = e;
      } while (c);
      nc(b);
    }
    function Ka(a) {
      for (; null != a; a = a.nextSibling) {
        var b = a.nodeType;
        if (1 === b || 3 === b) break;
        if (8 === b) {
          b = a.data;
          if ("$" === b || "$!" === b || "$?" === b) break;
          if ("/$" === b) return null;
        }
      }
      return a;
    }
    function sh(a) {
      a = a.previousSibling;
      for (var b = 0; a;) {
        if (8 === a.nodeType) {
          var c = a.data;
          if ("$" === c || "$!" === c || "$?" === c) {
            if (0 === b) return a;
            b--;
          } else "/$" === c && b++;
        }
        a = a.previousSibling;
      }
      return null;
    }
    function ob(a) {
      var b = a[Da];
      if (b) return b;
      for (var c = a.parentNode; c;) {
        if (b = c[Ja] || c[Da]) {
          c = b.alternate;
          if (null !== b.child || null !== c && null !== c.child) for (a = sh(a); null !== a;) {
            if (c = a[Da]) return c;
            a = sh(a);
          }
          return b;
        }
        a = c;
        c = a.parentNode;
      }
      return null;
    }
    function ec(a) {
      a = a[Da] || a[Ja];
      return !a || 5 !== a.tag && 6 !== a.tag && 13 !== a.tag && 3 !== a.tag ? null : a;
    }
    function Ib(a) {
      if (5 === a.tag || 6 === a.tag) return a.stateNode;
      throw Error(m(33));
    }
    function Rc(a) {
      return a[uc] || null;
    }
    function bb(a) {
      return {
        current: a
      };
    }
    function v(a, b) {
      0 > Mb || (a.current = Se[Mb], Se[Mb] = null, Mb--);
    }
    function y(a, b, c) {
      Mb++;
      Se[Mb] = a.current;
      a.current = b;
    }
    function Nb(a, b) {
      var c = a.type.contextTypes;
      if (!c) return cb;
      var d = a.stateNode;
      if (d && d.__reactInternalMemoizedUnmaskedChildContext === b) return d.__reactInternalMemoizedMaskedChildContext;
      var e = {},
        f;
      for (f in c) e[f] = b[f];
      d && (a = a.stateNode, a.__reactInternalMemoizedUnmaskedChildContext = b, a.__reactInternalMemoizedMaskedChildContext = e);
      return e;
    }
    function ea(a) {
      a = a.childContextTypes;
      return null !== a && void 0 !== a;
    }
    function th(a, b, c) {
      if (J.current !== cb) throw Error(m(168));
      y(J, b);
      y(S, c);
    }
    function uh(a, b, c) {
      var d = a.stateNode;
      b = b.childContextTypes;
      if ("function" !== typeof d.getChildContext) return c;
      d = d.getChildContext();
      for (var e in d) if (!(e in b)) throw Error(m(108, gj(a) || "Unknown", e));
      return E({}, c, d);
    }
    function ld(a) {
      a = (a = a.stateNode) && a.__reactInternalMemoizedMergedChildContext || cb;
      pb = J.current;
      y(J, a);
      y(S, S.current);
      return !0;
    }
    function vh(a, b, c) {
      var d = a.stateNode;
      if (!d) throw Error(m(169));
      c ? (a = uh(a, b, pb), d.__reactInternalMemoizedMergedChildContext = a, v(S), v(J), y(J, a)) : v(S);
      y(S, c);
    }
    function wh(a) {
      null === La ? La = [a] : La.push(a);
    }
    function jk(a) {
      md = !0;
      wh(a);
    }
    function db() {
      if (!Te && null !== La) {
        Te = !0;
        var a = 0,
          b = z;
        try {
          var c = La;
          for (z = 1; a < c.length; a++) {
            var d = c[a];
            do d = d(!0); while (null !== d);
          }
          La = null;
          md = !1;
        } catch (e) {
          throw null !== La && (La = La.slice(a + 1)), xh(De, db), e;
        } finally {
          z = b, Te = !1;
        }
      }
      return null;
    }
    function qb(a, b) {
      Ob[Pb++] = nd;
      Ob[Pb++] = od;
      od = a;
      nd = b;
    }
    function yh(a, b, c) {
      na[oa++] = Ma;
      na[oa++] = Na;
      na[oa++] = rb;
      rb = a;
      var d = Ma;
      a = Na;
      var e = 32 - ta(d) - 1;
      d &= ~(1 << e);
      c += 1;
      var f = 32 - ta(b) + e;
      if (30 < f) {
        var g = e - e % 5;
        f = (d & (1 << g) - 1).toString(32);
        d >>= g;
        e -= g;
        Ma = 1 << 32 - ta(b) + e | c << e | d;
        Na = f + a;
      } else Ma = 1 << f | c << e | d, Na = a;
    }
    function Ue(a) {
      null !== a.return && (qb(a, 1), yh(a, 1, 0));
    }
    function Ve(a) {
      for (; a === od;) od = Ob[--Pb], Ob[Pb] = null, nd = Ob[--Pb], Ob[Pb] = null;
      for (; a === rb;) rb = na[--oa], na[oa] = null, Na = na[--oa], na[oa] = null, Ma = na[--oa], na[oa] = null;
    }
    function zh(a, b) {
      var c = pa(5, null, null, 0);
      c.elementType = "DELETED";
      c.stateNode = b;
      c.return = a;
      b = a.deletions;
      null === b ? (a.deletions = [c], a.flags |= 16) : b.push(c);
    }
    function Ah(a, b) {
      switch (a.tag) {
        case 5:
          var c = a.type;
          b = 1 !== b.nodeType || c.toLowerCase() !== b.nodeName.toLowerCase() ? null : b;
          return null !== b ? (a.stateNode = b, la = a, fa = Ka(b.firstChild), !0) : !1;
        case 6:
          return b = "" === a.pendingProps || 3 !== b.nodeType ? null : b, null !== b ? (a.stateNode = b, la = a, fa = null, !0) : !1;
        case 13:
          return b = 8 !== b.nodeType ? null : b, null !== b ? (c = null !== rb ? {
            id: Ma,
            overflow: Na
          } : null, a.memoizedState = {
            dehydrated: b,
            treeContext: c,
            retryLane: 1073741824
          }, c = pa(18, null, null, 0), c.stateNode = b, c.return = a, a.child = c, la = a, fa = null, !0) : !1;
        default:
          return !1;
      }
    }
    function We(a) {
      return 0 !== (a.mode & 1) && 0 === (a.flags & 128);
    }
    function Xe(a) {
      if (D) {
        var b = fa;
        if (b) {
          var c = b;
          if (!Ah(a, b)) {
            if (We(a)) throw Error(m(418));
            b = Ka(c.nextSibling);
            var d = la;
            b && Ah(a, b) ? zh(d, c) : (a.flags = a.flags & -4097 | 2, D = !1, la = a);
          }
        } else {
          if (We(a)) throw Error(m(418));
          a.flags = a.flags & -4097 | 2;
          D = !1;
          la = a;
        }
      }
    }
    function Bh(a) {
      for (a = a.return; null !== a && 5 !== a.tag && 3 !== a.tag && 13 !== a.tag;) a = a.return;
      la = a;
    }
    function pd(a) {
      if (a !== la) return !1;
      if (!D) return Bh(a), D = !0, !1;
      var b;
      (b = 3 !== a.tag) && !(b = 5 !== a.tag) && (b = a.type, b = "head" !== b && "body" !== b && !Qe(a.type, a.memoizedProps));
      if (b && (b = fa)) {
        if (We(a)) {
          for (a = fa; a;) a = Ka(a.nextSibling);
          throw Error(m(418));
        }
        for (; b;) zh(a, b), b = Ka(b.nextSibling);
      }
      Bh(a);
      if (13 === a.tag) {
        a = a.memoizedState;
        a = null !== a ? a.dehydrated : null;
        if (!a) throw Error(m(317));
        a: {
          a = a.nextSibling;
          for (b = 0; a;) {
            if (8 === a.nodeType) {
              var c = a.data;
              if ("/$" === c) {
                if (0 === b) {
                  fa = Ka(a.nextSibling);
                  break a;
                }
                b--;
              } else "$" !== c && "$!" !== c && "$?" !== c || b++;
            }
            a = a.nextSibling;
          }
          fa = null;
        }
      } else fa = la ? Ka(a.stateNode.nextSibling) : null;
      return !0;
    }
    function Qb() {
      fa = la = null;
      D = !1;
    }
    function Ye(a) {
      null === wa ? wa = [a] : wa.push(a);
    }
    function vc(a, b, c) {
      a = c.ref;
      if (null !== a && "function" !== typeof a && "object" !== typeof a) {
        if (c._owner) {
          c = c._owner;
          if (c) {
            if (1 !== c.tag) throw Error(m(309));
            var d = c.stateNode;
          }
          if (!d) throw Error(m(147, a));
          var e = d,
            f = "" + a;
          if (null !== b && null !== b.ref && "function" === typeof b.ref && b.ref._stringRef === f) return b.ref;
          b = function (a) {
            var b = e.refs;
            null === a ? delete b[f] : b[f] = a;
          };
          b._stringRef = f;
          return b;
        }
        if ("string" !== typeof a) throw Error(m(284));
        if (!c._owner) throw Error(m(290, a));
      }
      return a;
    }
    function qd(a, b) {
      a = Object.prototype.toString.call(b);
      throw Error(m(31, "[object Object]" === a ? "object with keys {" + Object.keys(b).join(", ") + "}" : a));
    }
    function Ch(a) {
      var b = a._init;
      return b(a._payload);
    }
    function Dh(a) {
      function b(b, c) {
        if (a) {
          var d = b.deletions;
          null === d ? (b.deletions = [c], b.flags |= 16) : d.push(c);
        }
      }
      function c(c, d) {
        if (!a) return null;
        for (; null !== d;) b(c, d), d = d.sibling;
        return null;
      }
      function d(a, b) {
        for (a = new Map(); null !== b;) null !== b.key ? a.set(b.key, b) : a.set(b.index, b), b = b.sibling;
        return a;
      }
      function e(a, b) {
        a = eb(a, b);
        a.index = 0;
        a.sibling = null;
        return a;
      }
      function f(b, c, d) {
        b.index = d;
        if (!a) return b.flags |= 1048576, c;
        d = b.alternate;
        if (null !== d) return d = d.index, d < c ? (b.flags |= 2, c) : d;
        b.flags |= 2;
        return c;
      }
      function g(b) {
        a && null === b.alternate && (b.flags |= 2);
        return b;
      }
      function h(a, b, c, d) {
        if (null === b || 6 !== b.tag) return b = Ze(c, a.mode, d), b.return = a, b;
        b = e(b, c);
        b.return = a;
        return b;
      }
      function k(a, b, c, d) {
        var f = c.type;
        if (f === Bb) return l(a, b, c.props.children, d, c.key);
        if (null !== b && (b.elementType === f || "object" === typeof f && null !== f && f.$$typeof === Ta && Ch(f) === b.type)) return d = e(b, c.props), d.ref = vc(a, b, c), d.return = a, d;
        d = rd(c.type, c.key, c.props, null, a.mode, d);
        d.ref = vc(a, b, c);
        d.return = a;
        return d;
      }
      function n(a, b, c, d) {
        if (null === b || 4 !== b.tag || b.stateNode.containerInfo !== c.containerInfo || b.stateNode.implementation !== c.implementation) return b = $e(c, a.mode, d), b.return = a, b;
        b = e(b, c.children || []);
        b.return = a;
        return b;
      }
      function l(a, b, c, d, f) {
        if (null === b || 7 !== b.tag) return b = sb(c, a.mode, d, f), b.return = a, b;
        b = e(b, c);
        b.return = a;
        return b;
      }
      function u(a, b, c) {
        if ("string" === typeof b && "" !== b || "number" === typeof b) return b = Ze("" + b, a.mode, c), b.return = a, b;
        if ("object" === typeof b && null !== b) {
          switch (b.$$typeof) {
            case sd:
              return c = rd(b.type, b.key, b.props, null, a.mode, c), c.ref = vc(a, null, b), c.return = a, c;
            case Cb:
              return b = $e(b, a.mode, c), b.return = a, b;
            case Ta:
              var d = b._init;
              return u(a, d(b._payload), c);
          }
          if (cc(b) || ac(b)) return b = sb(b, a.mode, c, null), b.return = a, b;
          qd(a, b);
        }
        return null;
      }
      function r(a, b, c, d) {
        var e = null !== b ? b.key : null;
        if ("string" === typeof c && "" !== c || "number" === typeof c) return null !== e ? null : h(a, b, "" + c, d);
        if ("object" === typeof c && null !== c) {
          switch (c.$$typeof) {
            case sd:
              return c.key === e ? k(a, b, c, d) : null;
            case Cb:
              return c.key === e ? n(a, b, c, d) : null;
            case Ta:
              return e = c._init, r(a, b, e(c._payload), d);
          }
          if (cc(c) || ac(c)) return null !== e ? null : l(a, b, c, d, null);
          qd(a, c);
        }
        return null;
      }
      function p(a, b, c, d, e) {
        if ("string" === typeof d && "" !== d || "number" === typeof d) return a = a.get(c) || null, h(b, a, "" + d, e);
        if ("object" === typeof d && null !== d) {
          switch (d.$$typeof) {
            case sd:
              return a = a.get(null === d.key ? c : d.key) || null, k(b, a, d, e);
            case Cb:
              return a = a.get(null === d.key ? c : d.key) || null, n(b, a, d, e);
            case Ta:
              var f = d._init;
              return p(a, b, c, f(d._payload), e);
          }
          if (cc(d) || ac(d)) return a = a.get(c) || null, l(b, a, d, e, null);
          qd(b, d);
        }
        return null;
      }
      function x(e, g, h, k) {
        for (var n = null, m = null, l = g, t = g = 0, q = null; null !== l && t < h.length; t++) {
          l.index > t ? (q = l, l = null) : q = l.sibling;
          var A = r(e, l, h[t], k);
          if (null === A) {
            null === l && (l = q);
            break;
          }
          a && l && null === A.alternate && b(e, l);
          g = f(A, g, t);
          null === m ? n = A : m.sibling = A;
          m = A;
          l = q;
        }
        if (t === h.length) return c(e, l), D && qb(e, t), n;
        if (null === l) {
          for (; t < h.length; t++) l = u(e, h[t], k), null !== l && (g = f(l, g, t), null === m ? n = l : m.sibling = l, m = l);
          D && qb(e, t);
          return n;
        }
        for (l = d(e, l); t < h.length; t++) q = p(l, e, t, h[t], k), null !== q && (a && null !== q.alternate && l.delete(null === q.key ? t : q.key), g = f(q, g, t), null === m ? n = q : m.sibling = q, m = q);
        a && l.forEach(function (a) {
          return b(e, a);
        });
        D && qb(e, t);
        return n;
      }
      function I(e, g, h, k) {
        var n = ac(h);
        if ("function" !== typeof n) throw Error(m(150));
        h = n.call(h);
        if (null == h) throw Error(m(151));
        for (var l = n = null, q = g, t = g = 0, A = null, w = h.next(); null !== q && !w.done; t++, w = h.next()) {
          q.index > t ? (A = q, q = null) : A = q.sibling;
          var x = r(e, q, w.value, k);
          if (null === x) {
            null === q && (q = A);
            break;
          }
          a && q && null === x.alternate && b(e, q);
          g = f(x, g, t);
          null === l ? n = x : l.sibling = x;
          l = x;
          q = A;
        }
        if (w.done) return c(e, q), D && qb(e, t), n;
        if (null === q) {
          for (; !w.done; t++, w = h.next()) w = u(e, w.value, k), null !== w && (g = f(w, g, t), null === l ? n = w : l.sibling = w, l = w);
          D && qb(e, t);
          return n;
        }
        for (q = d(e, q); !w.done; t++, w = h.next()) w = p(q, e, t, w.value, k), null !== w && (a && null !== w.alternate && q.delete(null === w.key ? t : w.key), g = f(w, g, t), null === l ? n = w : l.sibling = w, l = w);
        a && q.forEach(function (a) {
          return b(e, a);
        });
        D && qb(e, t);
        return n;
      }
      function v(a, d, f, h) {
        "object" === typeof f && null !== f && f.type === Bb && null === f.key && (f = f.props.children);
        if ("object" === typeof f && null !== f) {
          switch (f.$$typeof) {
            case sd:
              a: {
                for (var k = f.key, n = d; null !== n;) {
                  if (n.key === k) {
                    k = f.type;
                    if (k === Bb) {
                      if (7 === n.tag) {
                        c(a, n.sibling);
                        d = e(n, f.props.children);
                        d.return = a;
                        a = d;
                        break a;
                      }
                    } else if (n.elementType === k || "object" === typeof k && null !== k && k.$$typeof === Ta && Ch(k) === n.type) {
                      c(a, n.sibling);
                      d = e(n, f.props);
                      d.ref = vc(a, n, f);
                      d.return = a;
                      a = d;
                      break a;
                    }
                    c(a, n);
                    break;
                  } else b(a, n);
                  n = n.sibling;
                }
                f.type === Bb ? (d = sb(f.props.children, a.mode, h, f.key), d.return = a, a = d) : (h = rd(f.type, f.key, f.props, null, a.mode, h), h.ref = vc(a, d, f), h.return = a, a = h);
              }
              return g(a);
            case Cb:
              a: {
                for (n = f.key; null !== d;) {
                  if (d.key === n) {
                    if (4 === d.tag && d.stateNode.containerInfo === f.containerInfo && d.stateNode.implementation === f.implementation) {
                      c(a, d.sibling);
                      d = e(d, f.children || []);
                      d.return = a;
                      a = d;
                      break a;
                    } else {
                      c(a, d);
                      break;
                    }
                  } else b(a, d);
                  d = d.sibling;
                }
                d = $e(f, a.mode, h);
                d.return = a;
                a = d;
              }
              return g(a);
            case Ta:
              return n = f._init, v(a, d, n(f._payload), h);
          }
          if (cc(f)) return x(a, d, f, h);
          if (ac(f)) return I(a, d, f, h);
          qd(a, f);
        }
        return "string" === typeof f && "" !== f || "number" === typeof f ? (f = "" + f, null !== d && 6 === d.tag ? (c(a, d.sibling), d = e(d, f), d.return = a, a = d) : (c(a, d), d = Ze(f, a.mode, h), d.return = a, a = d), g(a)) : c(a, d);
      }
      return v;
    }
    function af() {
      bf = Rb = td = null;
    }
    function cf(a, b) {
      b = ud.current;
      v(ud);
      a._currentValue = b;
    }
    function df(a, b, c) {
      for (; null !== a;) {
        var d = a.alternate;
        (a.childLanes & b) !== b ? (a.childLanes |= b, null !== d && (d.childLanes |= b)) : null !== d && (d.childLanes & b) !== b && (d.childLanes |= b);
        if (a === c) break;
        a = a.return;
      }
    }
    function Sb(a, b) {
      td = a;
      bf = Rb = null;
      a = a.dependencies;
      null !== a && null !== a.firstContext && (0 !== (a.lanes & b) && (ha = !0), a.firstContext = null);
    }
    function qa(a) {
      var b = a._currentValue;
      if (bf !== a) if (a = {
        context: a,
        memoizedValue: b,
        next: null
      }, null === Rb) {
        if (null === td) throw Error(m(308));
        Rb = a;
        td.dependencies = {
          lanes: 0,
          firstContext: a
        };
      } else Rb = Rb.next = a;
      return b;
    }
    function ef(a) {
      null === tb ? tb = [a] : tb.push(a);
    }
    function Eh(a, b, c, d) {
      var e = b.interleaved;
      null === e ? (c.next = c, ef(b)) : (c.next = e.next, e.next = c);
      b.interleaved = c;
      return Oa(a, d);
    }
    function Oa(a, b) {
      a.lanes |= b;
      var c = a.alternate;
      null !== c && (c.lanes |= b);
      c = a;
      for (a = a.return; null !== a;) a.childLanes |= b, c = a.alternate, null !== c && (c.childLanes |= b), c = a, a = a.return;
      return 3 === c.tag ? c.stateNode : null;
    }
    function ff(a) {
      a.updateQueue = {
        baseState: a.memoizedState,
        firstBaseUpdate: null,
        lastBaseUpdate: null,
        shared: {
          pending: null,
          interleaved: null,
          lanes: 0
        },
        effects: null
      };
    }
    function Fh(a, b) {
      a = a.updateQueue;
      b.updateQueue === a && (b.updateQueue = {
        baseState: a.baseState,
        firstBaseUpdate: a.firstBaseUpdate,
        lastBaseUpdate: a.lastBaseUpdate,
        shared: a.shared,
        effects: a.effects
      });
    }
    function Pa(a, b) {
      return {
        eventTime: a,
        lane: b,
        tag: 0,
        payload: null,
        callback: null,
        next: null
      };
    }
    function fb(a, b, c) {
      var d = a.updateQueue;
      if (null === d) return null;
      d = d.shared;
      if (0 !== (p & 2)) {
        var e = d.pending;
        null === e ? b.next = b : (b.next = e.next, e.next = b);
        d.pending = b;
        return kk(a, c);
      }
      e = d.interleaved;
      null === e ? (b.next = b, ef(d)) : (b.next = e.next, e.next = b);
      d.interleaved = b;
      return Oa(a, c);
    }
    function vd(a, b, c) {
      b = b.updateQueue;
      if (null !== b && (b = b.shared, 0 !== (c & 4194240))) {
        var d = b.lanes;
        d &= a.pendingLanes;
        c |= d;
        b.lanes = c;
        xe(a, c);
      }
    }
    function Gh(a, b) {
      var c = a.updateQueue,
        d = a.alternate;
      if (null !== d && (d = d.updateQueue, c === d)) {
        var e = null,
          f = null;
        c = c.firstBaseUpdate;
        if (null !== c) {
          do {
            var g = {
              eventTime: c.eventTime,
              lane: c.lane,
              tag: c.tag,
              payload: c.payload,
              callback: c.callback,
              next: null
            };
            null === f ? e = f = g : f = f.next = g;
            c = c.next;
          } while (null !== c);
          null === f ? e = f = b : f = f.next = b;
        } else e = f = b;
        c = {
          baseState: d.baseState,
          firstBaseUpdate: e,
          lastBaseUpdate: f,
          shared: d.shared,
          effects: d.effects
        };
        a.updateQueue = c;
        return;
      }
      a = c.lastBaseUpdate;
      null === a ? c.firstBaseUpdate = b : a.next = b;
      c.lastBaseUpdate = b;
    }
    function wd(a, b, c, d) {
      var e = a.updateQueue;
      gb = !1;
      var f = e.firstBaseUpdate,
        g = e.lastBaseUpdate,
        h = e.shared.pending;
      if (null !== h) {
        e.shared.pending = null;
        var k = h,
          n = k.next;
        k.next = null;
        null === g ? f = n : g.next = n;
        g = k;
        var l = a.alternate;
        null !== l && (l = l.updateQueue, h = l.lastBaseUpdate, h !== g && (null === h ? l.firstBaseUpdate = n : h.next = n, l.lastBaseUpdate = k));
      }
      if (null !== f) {
        var m = e.baseState;
        g = 0;
        l = n = k = null;
        h = f;
        do {
          var r = h.lane,
            p = h.eventTime;
          if ((d & r) === r) {
            null !== l && (l = l.next = {
              eventTime: p,
              lane: 0,
              tag: h.tag,
              payload: h.payload,
              callback: h.callback,
              next: null
            });
            a: {
              var x = a,
                v = h;
              r = b;
              p = c;
              switch (v.tag) {
                case 1:
                  x = v.payload;
                  if ("function" === typeof x) {
                    m = x.call(p, m, r);
                    break a;
                  }
                  m = x;
                  break a;
                case 3:
                  x.flags = x.flags & -65537 | 128;
                case 0:
                  x = v.payload;
                  r = "function" === typeof x ? x.call(p, m, r) : x;
                  if (null === r || void 0 === r) break a;
                  m = E({}, m, r);
                  break a;
                case 2:
                  gb = !0;
              }
            }
            null !== h.callback && 0 !== h.lane && (a.flags |= 64, r = e.effects, null === r ? e.effects = [h] : r.push(h));
          } else p = {
            eventTime: p,
            lane: r,
            tag: h.tag,
            payload: h.payload,
            callback: h.callback,
            next: null
          }, null === l ? (n = l = p, k = m) : l = l.next = p, g |= r;
          h = h.next;
          if (null === h) if (h = e.shared.pending, null === h) break;else r = h, h = r.next, r.next = null, e.lastBaseUpdate = r, e.shared.pending = null;
        } while (1);
        null === l && (k = m);
        e.baseState = k;
        e.firstBaseUpdate = n;
        e.lastBaseUpdate = l;
        b = e.shared.interleaved;
        if (null !== b) {
          e = b;
          do g |= e.lane, e = e.next; while (e !== b);
        } else null === f && (e.shared.lanes = 0);
        ra |= g;
        a.lanes = g;
        a.memoizedState = m;
      }
    }
    function Hh(a, b, c) {
      a = b.effects;
      b.effects = null;
      if (null !== a) for (b = 0; b < a.length; b++) {
        var d = a[b],
          e = d.callback;
        if (null !== e) {
          d.callback = null;
          d = c;
          if ("function" !== typeof e) throw Error(m(191, e));
          e.call(d);
        }
      }
    }
    function ub(a) {
      if (a === wc) throw Error(m(174));
      return a;
    }
    function gf(a, b) {
      y(xc, b);
      y(yc, a);
      y(Ea, wc);
      a = b.nodeType;
      switch (a) {
        case 9:
        case 11:
          b = (b = b.documentElement) ? b.namespaceURI : oe(null, "");
          break;
        default:
          a = 8 === a ? b.parentNode : b, b = a.namespaceURI || null, a = a.tagName, b = oe(b, a);
      }
      v(Ea);
      y(Ea, b);
    }
    function Tb(a) {
      v(Ea);
      v(yc);
      v(xc);
    }
    function Ih(a) {
      ub(xc.current);
      var b = ub(Ea.current);
      var c = oe(b, a.type);
      b !== c && (y(yc, a), y(Ea, c));
    }
    function hf(a) {
      yc.current === a && (v(Ea), v(yc));
    }
    function xd(a) {
      for (var b = a; null !== b;) {
        if (13 === b.tag) {
          var c = b.memoizedState;
          if (null !== c && (c = c.dehydrated, null === c || "$?" === c.data || "$!" === c.data)) return b;
        } else if (19 === b.tag && void 0 !== b.memoizedProps.revealOrder) {
          if (0 !== (b.flags & 128)) return b;
        } else if (null !== b.child) {
          b.child.return = b;
          b = b.child;
          continue;
        }
        if (b === a) break;
        for (; null === b.sibling;) {
          if (null === b.return || b.return === a) return null;
          b = b.return;
        }
        b.sibling.return = b.return;
        b = b.sibling;
      }
      return null;
    }
    function jf() {
      for (var a = 0; a < kf.length; a++) kf[a]._workInProgressVersionPrimary = null;
      kf.length = 0;
    }
    function V() {
      throw Error(m(321));
    }
    function lf(a, b) {
      if (null === b) return !1;
      for (var c = 0; c < b.length && c < a.length; c++) if (!ua(a[c], b[c])) return !1;
      return !0;
    }
    function mf(a, b, c, d, e, f) {
      vb = f;
      C = b;
      b.memoizedState = null;
      b.updateQueue = null;
      b.lanes = 0;
      yd.current = null === a || null === a.memoizedState ? lk : mk;
      a = c(d, e);
      if (zc) {
        f = 0;
        do {
          zc = !1;
          Ac = 0;
          if (25 <= f) throw Error(m(301));
          f += 1;
          N = K = null;
          b.updateQueue = null;
          yd.current = nk;
          a = c(d, e);
        } while (zc);
      }
      yd.current = zd;
      b = null !== K && null !== K.next;
      vb = 0;
      N = K = C = null;
      Ad = !1;
      if (b) throw Error(m(300));
      return a;
    }
    function nf() {
      var a = 0 !== Ac;
      Ac = 0;
      return a;
    }
    function Fa() {
      var a = {
        memoizedState: null,
        baseState: null,
        baseQueue: null,
        queue: null,
        next: null
      };
      null === N ? C.memoizedState = N = a : N = N.next = a;
      return N;
    }
    function sa() {
      if (null === K) {
        var a = C.alternate;
        a = null !== a ? a.memoizedState : null;
      } else a = K.next;
      var b = null === N ? C.memoizedState : N.next;
      if (null !== b) N = b, K = a;else {
        if (null === a) throw Error(m(310));
        K = a;
        a = {
          memoizedState: K.memoizedState,
          baseState: K.baseState,
          baseQueue: K.baseQueue,
          queue: K.queue,
          next: null
        };
        null === N ? C.memoizedState = N = a : N = N.next = a;
      }
      return N;
    }
    function Bc(a, b) {
      return "function" === typeof b ? b(a) : b;
    }
    function of(a, b, c) {
      b = sa();
      c = b.queue;
      if (null === c) throw Error(m(311));
      c.lastRenderedReducer = a;
      var d = K,
        e = d.baseQueue,
        f = c.pending;
      if (null !== f) {
        if (null !== e) {
          var g = e.next;
          e.next = f.next;
          f.next = g;
        }
        d.baseQueue = e = f;
        c.pending = null;
      }
      if (null !== e) {
        f = e.next;
        d = d.baseState;
        var h = g = null,
          k = null,
          n = f;
        do {
          var l = n.lane;
          if ((vb & l) === l) null !== k && (k = k.next = {
            lane: 0,
            action: n.action,
            hasEagerState: n.hasEagerState,
            eagerState: n.eagerState,
            next: null
          }), d = n.hasEagerState ? n.eagerState : a(d, n.action);else {
            var u = {
              lane: l,
              action: n.action,
              hasEagerState: n.hasEagerState,
              eagerState: n.eagerState,
              next: null
            };
            null === k ? (h = k = u, g = d) : k = k.next = u;
            C.lanes |= l;
            ra |= l;
          }
          n = n.next;
        } while (null !== n && n !== f);
        null === k ? g = d : k.next = h;
        ua(d, b.memoizedState) || (ha = !0);
        b.memoizedState = d;
        b.baseState = g;
        b.baseQueue = k;
        c.lastRenderedState = d;
      }
      a = c.interleaved;
      if (null !== a) {
        e = a;
        do f = e.lane, C.lanes |= f, ra |= f, e = e.next; while (e !== a);
      } else null === e && (c.lanes = 0);
      return [b.memoizedState, c.dispatch];
    }
    function pf(a, b, c) {
      b = sa();
      c = b.queue;
      if (null === c) throw Error(m(311));
      c.lastRenderedReducer = a;
      var d = c.dispatch,
        e = c.pending,
        f = b.memoizedState;
      if (null !== e) {
        c.pending = null;
        var g = e = e.next;
        do f = a(f, g.action), g = g.next; while (g !== e);
        ua(f, b.memoizedState) || (ha = !0);
        b.memoizedState = f;
        null === b.baseQueue && (b.baseState = f);
        c.lastRenderedState = f;
      }
      return [f, d];
    }
    function Jh(a, b, c) {}
    function Kh(a, b, c) {
      c = C;
      var d = sa(),
        e = b(),
        f = !ua(d.memoizedState, e);
      f && (d.memoizedState = e, ha = !0);
      d = d.queue;
      qf(Lh.bind(null, c, d, a), [a]);
      if (d.getSnapshot !== b || f || null !== N && N.memoizedState.tag & 1) {
        c.flags |= 2048;
        Cc(9, Mh.bind(null, c, d, e, b), void 0, null);
        if (null === O) throw Error(m(349));
        0 !== (vb & 30) || Nh(c, b, e);
      }
      return e;
    }
    function Nh(a, b, c) {
      a.flags |= 16384;
      a = {
        getSnapshot: b,
        value: c
      };
      b = C.updateQueue;
      null === b ? (b = {
        lastEffect: null,
        stores: null
      }, C.updateQueue = b, b.stores = [a]) : (c = b.stores, null === c ? b.stores = [a] : c.push(a));
    }
    function Mh(a, b, c, d) {
      b.value = c;
      b.getSnapshot = d;
      Oh(b) && Ph(a);
    }
    function Lh(a, b, c) {
      return c(function () {
        Oh(b) && Ph(a);
      });
    }
    function Oh(a) {
      var b = a.getSnapshot;
      a = a.value;
      try {
        var c = b();
        return !ua(a, c);
      } catch (d) {
        return !0;
      }
    }
    function Ph(a) {
      var b = Oa(a, 1);
      null !== b && xa(b, a, 1, -1);
    }
    function Qh(a) {
      var b = Fa();
      "function" === typeof a && (a = a());
      b.memoizedState = b.baseState = a;
      a = {
        pending: null,
        interleaved: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: Bc,
        lastRenderedState: a
      };
      b.queue = a;
      a = a.dispatch = ok.bind(null, C, a);
      return [b.memoizedState, a];
    }
    function Cc(a, b, c, d) {
      a = {
        tag: a,
        create: b,
        destroy: c,
        deps: d,
        next: null
      };
      b = C.updateQueue;
      null === b ? (b = {
        lastEffect: null,
        stores: null
      }, C.updateQueue = b, b.lastEffect = a.next = a) : (c = b.lastEffect, null === c ? b.lastEffect = a.next = a : (d = c.next, c.next = a, a.next = d, b.lastEffect = a));
      return a;
    }
    function Rh(a) {
      return sa().memoizedState;
    }
    function Bd(a, b, c, d) {
      var e = Fa();
      C.flags |= a;
      e.memoizedState = Cc(1 | b, c, void 0, void 0 === d ? null : d);
    }
    function Cd(a, b, c, d) {
      var e = sa();
      d = void 0 === d ? null : d;
      var f = void 0;
      if (null !== K) {
        var g = K.memoizedState;
        f = g.destroy;
        if (null !== d && lf(d, g.deps)) {
          e.memoizedState = Cc(b, c, f, d);
          return;
        }
      }
      C.flags |= a;
      e.memoizedState = Cc(1 | b, c, f, d);
    }
    function Sh(a, b) {
      return Bd(8390656, 8, a, b);
    }
    function qf(a, b) {
      return Cd(2048, 8, a, b);
    }
    function Th(a, b) {
      return Cd(4, 2, a, b);
    }
    function Uh(a, b) {
      return Cd(4, 4, a, b);
    }
    function Vh(a, b) {
      if ("function" === typeof b) return a = a(), b(a), function () {
        b(null);
      };
      if (null !== b && void 0 !== b) return a = a(), b.current = a, function () {
        b.current = null;
      };
    }
    function Wh(a, b, c) {
      c = null !== c && void 0 !== c ? c.concat([a]) : null;
      return Cd(4, 4, Vh.bind(null, b, a), c);
    }
    function rf(a, b) {}
    function Xh(a, b) {
      var c = sa();
      b = void 0 === b ? null : b;
      var d = c.memoizedState;
      if (null !== d && null !== b && lf(b, d[1])) return d[0];
      c.memoizedState = [a, b];
      return a;
    }
    function Yh(a, b) {
      var c = sa();
      b = void 0 === b ? null : b;
      var d = c.memoizedState;
      if (null !== d && null !== b && lf(b, d[1])) return d[0];
      a = a();
      c.memoizedState = [a, b];
      return a;
    }
    function Zh(a, b, c) {
      if (0 === (vb & 21)) return a.baseState && (a.baseState = !1, ha = !0), a.memoizedState = c;
      ua(c, b) || (c = Dg(), C.lanes |= c, ra |= c, a.baseState = !0);
      return b;
    }
    function pk(a, b, c) {
      c = z;
      z = 0 !== c && 4 > c ? c : 4;
      a(!0);
      var d = sf.transition;
      sf.transition = {};
      try {
        a(!1), b();
      } finally {
        z = c, sf.transition = d;
      }
    }
    function $h() {
      return sa().memoizedState;
    }
    function qk(a, b, c) {
      var d = hb(a);
      c = {
        lane: d,
        action: c,
        hasEagerState: !1,
        eagerState: null,
        next: null
      };
      if (ai(a)) bi(b, c);else if (c = Eh(a, b, c, d), null !== c) {
        var e = Z();
        xa(c, a, d, e);
        ci(c, b, d);
      }
    }
    function ok(a, b, c) {
      var d = hb(a),
        e = {
          lane: d,
          action: c,
          hasEagerState: !1,
          eagerState: null,
          next: null
        };
      if (ai(a)) bi(b, e);else {
        var f = a.alternate;
        if (0 === a.lanes && (null === f || 0 === f.lanes) && (f = b.lastRenderedReducer, null !== f)) try {
          var g = b.lastRenderedState,
            h = f(g, c);
          e.hasEagerState = !0;
          e.eagerState = h;
          if (ua(h, g)) {
            var k = b.interleaved;
            null === k ? (e.next = e, ef(b)) : (e.next = k.next, k.next = e);
            b.interleaved = e;
            return;
          }
        } catch (n) {} finally {}
        c = Eh(a, b, e, d);
        null !== c && (e = Z(), xa(c, a, d, e), ci(c, b, d));
      }
    }
    function ai(a) {
      var b = a.alternate;
      return a === C || null !== b && b === C;
    }
    function bi(a, b) {
      zc = Ad = !0;
      var c = a.pending;
      null === c ? b.next = b : (b.next = c.next, c.next = b);
      a.pending = b;
    }
    function ci(a, b, c) {
      if (0 !== (c & 4194240)) {
        var d = b.lanes;
        d &= a.pendingLanes;
        c |= d;
        b.lanes = c;
        xe(a, c);
      }
    }
    function ya(a, b) {
      if (a && a.defaultProps) {
        b = E({}, b);
        a = a.defaultProps;
        for (var c in a) void 0 === b[c] && (b[c] = a[c]);
        return b;
      }
      return b;
    }
    function tf(a, b, c, d) {
      b = a.memoizedState;
      c = c(d, b);
      c = null === c || void 0 === c ? b : E({}, b, c);
      a.memoizedState = c;
      0 === a.lanes && (a.updateQueue.baseState = c);
    }
    function di(a, b, c, d, e, f, g) {
      a = a.stateNode;
      return "function" === typeof a.shouldComponentUpdate ? a.shouldComponentUpdate(d, f, g) : b.prototype && b.prototype.isPureReactComponent ? !qc(c, d) || !qc(e, f) : !0;
    }
    function ei(a, b, c) {
      var d = !1,
        e = cb;
      var f = b.contextType;
      "object" === typeof f && null !== f ? f = qa(f) : (e = ea(b) ? pb : J.current, d = b.contextTypes, f = (d = null !== d && void 0 !== d) ? Nb(a, e) : cb);
      b = new b(c, f);
      a.memoizedState = null !== b.state && void 0 !== b.state ? b.state : null;
      b.updater = Dd;
      a.stateNode = b;
      b._reactInternals = a;
      d && (a = a.stateNode, a.__reactInternalMemoizedUnmaskedChildContext = e, a.__reactInternalMemoizedMaskedChildContext = f);
      return b;
    }
    function fi(a, b, c, d) {
      a = b.state;
      "function" === typeof b.componentWillReceiveProps && b.componentWillReceiveProps(c, d);
      "function" === typeof b.UNSAFE_componentWillReceiveProps && b.UNSAFE_componentWillReceiveProps(c, d);
      b.state !== a && Dd.enqueueReplaceState(b, b.state, null);
    }
    function uf(a, b, c, d) {
      var e = a.stateNode;
      e.props = c;
      e.state = a.memoizedState;
      e.refs = {};
      ff(a);
      var f = b.contextType;
      "object" === typeof f && null !== f ? e.context = qa(f) : (f = ea(b) ? pb : J.current, e.context = Nb(a, f));
      e.state = a.memoizedState;
      f = b.getDerivedStateFromProps;
      "function" === typeof f && (tf(a, b, f, c), e.state = a.memoizedState);
      "function" === typeof b.getDerivedStateFromProps || "function" === typeof e.getSnapshotBeforeUpdate || "function" !== typeof e.UNSAFE_componentWillMount && "function" !== typeof e.componentWillMount || (b = e.state, "function" === typeof e.componentWillMount && e.componentWillMount(), "function" === typeof e.UNSAFE_componentWillMount && e.UNSAFE_componentWillMount(), b !== e.state && Dd.enqueueReplaceState(e, e.state, null), wd(a, c, e, d), e.state = a.memoizedState);
      "function" === typeof e.componentDidMount && (a.flags |= 4194308);
    }
    function Ub(a, b) {
      try {
        var c = "",
          d = b;
        do c += fj(d), d = d.return; while (d);
        var e = c;
      } catch (f) {
        e = "\nError generating stack: " + f.message + "\n" + f.stack;
      }
      return {
        value: a,
        source: b,
        stack: e,
        digest: null
      };
    }
    function vf(a, b, c) {
      return {
        value: a,
        source: null,
        stack: null != c ? c : null,
        digest: null != b ? b : null
      };
    }
    function wf(a, b) {
      try {
        console.error(b.value);
      } catch (c) {
        setTimeout(function () {
          throw c;
        });
      }
    }
    function gi(a, b, c) {
      c = Pa(-1, c);
      c.tag = 3;
      c.payload = {
        element: null
      };
      var d = b.value;
      c.callback = function () {
        Ed || (Ed = !0, xf = d);
        wf(a, b);
      };
      return c;
    }
    function hi(a, b, c) {
      c = Pa(-1, c);
      c.tag = 3;
      var d = a.type.getDerivedStateFromError;
      if ("function" === typeof d) {
        var e = b.value;
        c.payload = function () {
          return d(e);
        };
        c.callback = function () {
          wf(a, b);
        };
      }
      var f = a.stateNode;
      null !== f && "function" === typeof f.componentDidCatch && (c.callback = function () {
        wf(a, b);
        "function" !== typeof d && (null === ib ? ib = new Set([this]) : ib.add(this));
        var c = b.stack;
        this.componentDidCatch(b.value, {
          componentStack: null !== c ? c : ""
        });
      });
      return c;
    }
    function ii(a, b, c) {
      var d = a.pingCache;
      if (null === d) {
        d = a.pingCache = new rk();
        var e = new Set();
        d.set(b, e);
      } else e = d.get(b), void 0 === e && (e = new Set(), d.set(b, e));
      e.has(c) || (e.add(c), a = sk.bind(null, a, b, c), b.then(a, a));
    }
    function ji(a) {
      do {
        var b;
        if (b = 13 === a.tag) b = a.memoizedState, b = null !== b ? null !== b.dehydrated ? !0 : !1 : !0;
        if (b) return a;
        a = a.return;
      } while (null !== a);
      return null;
    }
    function ki(a, b, c, d, e) {
      if (0 === (a.mode & 1)) return a === b ? a.flags |= 65536 : (a.flags |= 128, c.flags |= 131072, c.flags &= -52805, 1 === c.tag && (null === c.alternate ? c.tag = 17 : (b = Pa(-1, 1), b.tag = 2, fb(c, b, 1))), c.lanes |= 1), a;
      a.flags |= 65536;
      a.lanes = e;
      return a;
    }
    function aa(a, b, c, d) {
      b.child = null === a ? li(b, null, c, d) : Vb(b, a.child, c, d);
    }
    function mi(a, b, c, d, e) {
      c = c.render;
      var f = b.ref;
      Sb(b, e);
      d = mf(a, b, c, d, f, e);
      c = nf();
      if (null !== a && !ha) return b.updateQueue = a.updateQueue, b.flags &= -2053, a.lanes &= ~e, Qa(a, b, e);
      D && c && Ue(b);
      b.flags |= 1;
      aa(a, b, d, e);
      return b.child;
    }
    function ni(a, b, c, d, e) {
      if (null === a) {
        var f = c.type;
        if ("function" === typeof f && !yf(f) && void 0 === f.defaultProps && null === c.compare && void 0 === c.defaultProps) return b.tag = 15, b.type = f, oi(a, b, f, d, e);
        a = rd(c.type, null, d, b, b.mode, e);
        a.ref = b.ref;
        a.return = b;
        return b.child = a;
      }
      f = a.child;
      if (0 === (a.lanes & e)) {
        var g = f.memoizedProps;
        c = c.compare;
        c = null !== c ? c : qc;
        if (c(g, d) && a.ref === b.ref) return Qa(a, b, e);
      }
      b.flags |= 1;
      a = eb(f, d);
      a.ref = b.ref;
      a.return = b;
      return b.child = a;
    }
    function oi(a, b, c, d, e) {
      if (null !== a) {
        var f = a.memoizedProps;
        if (qc(f, d) && a.ref === b.ref) if (ha = !1, b.pendingProps = d = f, 0 !== (a.lanes & e)) 0 !== (a.flags & 131072) && (ha = !0);else return b.lanes = a.lanes, Qa(a, b, e);
      }
      return zf(a, b, c, d, e);
    }
    function pi(a, b, c) {
      var d = b.pendingProps,
        e = d.children,
        f = null !== a ? a.memoizedState : null;
      if ("hidden" === d.mode) {
        if (0 === (b.mode & 1)) b.memoizedState = {
          baseLanes: 0,
          cachePool: null,
          transitions: null
        }, y(Ga, ba), ba |= c;else {
          if (0 === (c & 1073741824)) return a = null !== f ? f.baseLanes | c : c, b.lanes = b.childLanes = 1073741824, b.memoizedState = {
            baseLanes: a,
            cachePool: null,
            transitions: null
          }, b.updateQueue = null, y(Ga, ba), ba |= a, null;
          b.memoizedState = {
            baseLanes: 0,
            cachePool: null,
            transitions: null
          };
          d = null !== f ? f.baseLanes : c;
          y(Ga, ba);
          ba |= d;
        }
      } else null !== f ? (d = f.baseLanes | c, b.memoizedState = null) : d = c, y(Ga, ba), ba |= d;
      aa(a, b, e, c);
      return b.child;
    }
    function qi(a, b) {
      var c = b.ref;
      if (null === a && null !== c || null !== a && a.ref !== c) b.flags |= 512, b.flags |= 2097152;
    }
    function zf(a, b, c, d, e) {
      var f = ea(c) ? pb : J.current;
      f = Nb(b, f);
      Sb(b, e);
      c = mf(a, b, c, d, f, e);
      d = nf();
      if (null !== a && !ha) return b.updateQueue = a.updateQueue, b.flags &= -2053, a.lanes &= ~e, Qa(a, b, e);
      D && d && Ue(b);
      b.flags |= 1;
      aa(a, b, c, e);
      return b.child;
    }
    function ri(a, b, c, d, e) {
      if (ea(c)) {
        var f = !0;
        ld(b);
      } else f = !1;
      Sb(b, e);
      if (null === b.stateNode) Fd(a, b), ei(b, c, d), uf(b, c, d, e), d = !0;else if (null === a) {
        var g = b.stateNode,
          h = b.memoizedProps;
        g.props = h;
        var k = g.context,
          n = c.contextType;
        "object" === typeof n && null !== n ? n = qa(n) : (n = ea(c) ? pb : J.current, n = Nb(b, n));
        var l = c.getDerivedStateFromProps,
          m = "function" === typeof l || "function" === typeof g.getSnapshotBeforeUpdate;
        m || "function" !== typeof g.UNSAFE_componentWillReceiveProps && "function" !== typeof g.componentWillReceiveProps || (h !== d || k !== n) && fi(b, g, d, n);
        gb = !1;
        var r = b.memoizedState;
        g.state = r;
        wd(b, d, g, e);
        k = b.memoizedState;
        h !== d || r !== k || S.current || gb ? ("function" === typeof l && (tf(b, c, l, d), k = b.memoizedState), (h = gb || di(b, c, h, d, r, k, n)) ? (m || "function" !== typeof g.UNSAFE_componentWillMount && "function" !== typeof g.componentWillMount || ("function" === typeof g.componentWillMount && g.componentWillMount(), "function" === typeof g.UNSAFE_componentWillMount && g.UNSAFE_componentWillMount()), "function" === typeof g.componentDidMount && (b.flags |= 4194308)) : ("function" === typeof g.componentDidMount && (b.flags |= 4194308), b.memoizedProps = d, b.memoizedState = k), g.props = d, g.state = k, g.context = n, d = h) : ("function" === typeof g.componentDidMount && (b.flags |= 4194308), d = !1);
      } else {
        g = b.stateNode;
        Fh(a, b);
        h = b.memoizedProps;
        n = b.type === b.elementType ? h : ya(b.type, h);
        g.props = n;
        m = b.pendingProps;
        r = g.context;
        k = c.contextType;
        "object" === typeof k && null !== k ? k = qa(k) : (k = ea(c) ? pb : J.current, k = Nb(b, k));
        var p = c.getDerivedStateFromProps;
        (l = "function" === typeof p || "function" === typeof g.getSnapshotBeforeUpdate) || "function" !== typeof g.UNSAFE_componentWillReceiveProps && "function" !== typeof g.componentWillReceiveProps || (h !== m || r !== k) && fi(b, g, d, k);
        gb = !1;
        r = b.memoizedState;
        g.state = r;
        wd(b, d, g, e);
        var x = b.memoizedState;
        h !== m || r !== x || S.current || gb ? ("function" === typeof p && (tf(b, c, p, d), x = b.memoizedState), (n = gb || di(b, c, n, d, r, x, k) || !1) ? (l || "function" !== typeof g.UNSAFE_componentWillUpdate && "function" !== typeof g.componentWillUpdate || ("function" === typeof g.componentWillUpdate && g.componentWillUpdate(d, x, k), "function" === typeof g.UNSAFE_componentWillUpdate && g.UNSAFE_componentWillUpdate(d, x, k)), "function" === typeof g.componentDidUpdate && (b.flags |= 4), "function" === typeof g.getSnapshotBeforeUpdate && (b.flags |= 1024)) : ("function" !== typeof g.componentDidUpdate || h === a.memoizedProps && r === a.memoizedState || (b.flags |= 4), "function" !== typeof g.getSnapshotBeforeUpdate || h === a.memoizedProps && r === a.memoizedState || (b.flags |= 1024), b.memoizedProps = d, b.memoizedState = x), g.props = d, g.state = x, g.context = k, d = n) : ("function" !== typeof g.componentDidUpdate || h === a.memoizedProps && r === a.memoizedState || (b.flags |= 4), "function" !== typeof g.getSnapshotBeforeUpdate || h === a.memoizedProps && r === a.memoizedState || (b.flags |= 1024), d = !1);
      }
      return Af(a, b, c, d, f, e);
    }
    function Af(a, b, c, d, e, f) {
      qi(a, b);
      var g = 0 !== (b.flags & 128);
      if (!d && !g) return e && vh(b, c, !1), Qa(a, b, f);
      d = b.stateNode;
      tk.current = b;
      var h = g && "function" !== typeof c.getDerivedStateFromError ? null : d.render();
      b.flags |= 1;
      null !== a && g ? (b.child = Vb(b, a.child, null, f), b.child = Vb(b, null, h, f)) : aa(a, b, h, f);
      b.memoizedState = d.state;
      e && vh(b, c, !0);
      return b.child;
    }
    function si(a) {
      var b = a.stateNode;
      b.pendingContext ? th(a, b.pendingContext, b.pendingContext !== b.context) : b.context && th(a, b.context, !1);
      gf(a, b.containerInfo);
    }
    function ti(a, b, c, d, e) {
      Qb();
      Ye(e);
      b.flags |= 256;
      aa(a, b, c, d);
      return b.child;
    }
    function Bf(a) {
      return {
        baseLanes: a,
        cachePool: null,
        transitions: null
      };
    }
    function ui(a, b, c) {
      var d = b.pendingProps,
        e = F.current,
        f = !1,
        g = 0 !== (b.flags & 128),
        h;
      (h = g) || (h = null !== a && null === a.memoizedState ? !1 : 0 !== (e & 2));
      if (h) f = !0, b.flags &= -129;else if (null === a || null !== a.memoizedState) e |= 1;
      y(F, e & 1);
      if (null === a) {
        Xe(b);
        a = b.memoizedState;
        if (null !== a && (a = a.dehydrated, null !== a)) return 0 === (b.mode & 1) ? b.lanes = 1 : "$!" === a.data ? b.lanes = 8 : b.lanes = 1073741824, null;
        g = d.children;
        a = d.fallback;
        return f ? (d = b.mode, f = b.child, g = {
          mode: "hidden",
          children: g
        }, 0 === (d & 1) && null !== f ? (f.childLanes = 0, f.pendingProps = g) : f = Gd(g, d, 0, null), a = sb(a, d, c, null), f.return = b, a.return = b, f.sibling = a, b.child = f, b.child.memoizedState = Bf(c), b.memoizedState = Cf, a) : Df(b, g);
      }
      e = a.memoizedState;
      if (null !== e && (h = e.dehydrated, null !== h)) return uk(a, b, g, d, h, e, c);
      if (f) {
        f = d.fallback;
        g = b.mode;
        e = a.child;
        h = e.sibling;
        var k = {
          mode: "hidden",
          children: d.children
        };
        0 === (g & 1) && b.child !== e ? (d = b.child, d.childLanes = 0, d.pendingProps = k, b.deletions = null) : (d = eb(e, k), d.subtreeFlags = e.subtreeFlags & 14680064);
        null !== h ? f = eb(h, f) : (f = sb(f, g, c, null), f.flags |= 2);
        f.return = b;
        d.return = b;
        d.sibling = f;
        b.child = d;
        d = f;
        f = b.child;
        g = a.child.memoizedState;
        g = null === g ? Bf(c) : {
          baseLanes: g.baseLanes | c,
          cachePool: null,
          transitions: g.transitions
        };
        f.memoizedState = g;
        f.childLanes = a.childLanes & ~c;
        b.memoizedState = Cf;
        return d;
      }
      f = a.child;
      a = f.sibling;
      d = eb(f, {
        mode: "visible",
        children: d.children
      });
      0 === (b.mode & 1) && (d.lanes = c);
      d.return = b;
      d.sibling = null;
      null !== a && (c = b.deletions, null === c ? (b.deletions = [a], b.flags |= 16) : c.push(a));
      b.child = d;
      b.memoizedState = null;
      return d;
    }
    function Df(a, b, c) {
      b = Gd({
        mode: "visible",
        children: b
      }, a.mode, 0, null);
      b.return = a;
      return a.child = b;
    }
    function Hd(a, b, c, d) {
      null !== d && Ye(d);
      Vb(b, a.child, null, c);
      a = Df(b, b.pendingProps.children);
      a.flags |= 2;
      b.memoizedState = null;
      return a;
    }
    function uk(a, b, c, d, e, f, g) {
      if (c) {
        if (b.flags & 256) return b.flags &= -257, d = vf(Error(m(422))), Hd(a, b, g, d);
        if (null !== b.memoizedState) return b.child = a.child, b.flags |= 128, null;
        f = d.fallback;
        e = b.mode;
        d = Gd({
          mode: "visible",
          children: d.children
        }, e, 0, null);
        f = sb(f, e, g, null);
        f.flags |= 2;
        d.return = b;
        f.return = b;
        d.sibling = f;
        b.child = d;
        0 !== (b.mode & 1) && Vb(b, a.child, null, g);
        b.child.memoizedState = Bf(g);
        b.memoizedState = Cf;
        return f;
      }
      if (0 === (b.mode & 1)) return Hd(a, b, g, null);
      if ("$!" === e.data) {
        d = e.nextSibling && e.nextSibling.dataset;
        if (d) var h = d.dgst;
        d = h;
        f = Error(m(419));
        d = vf(f, d, void 0);
        return Hd(a, b, g, d);
      }
      h = 0 !== (g & a.childLanes);
      if (ha || h) {
        d = O;
        if (null !== d) {
          switch (g & -g) {
            case 4:
              e = 2;
              break;
            case 16:
              e = 8;
              break;
            case 64:
            case 128:
            case 256:
            case 512:
            case 1024:
            case 2048:
            case 4096:
            case 8192:
            case 16384:
            case 32768:
            case 65536:
            case 131072:
            case 262144:
            case 524288:
            case 1048576:
            case 2097152:
            case 4194304:
            case 8388608:
            case 16777216:
            case 33554432:
            case 67108864:
              e = 32;
              break;
            case 536870912:
              e = 268435456;
              break;
            default:
              e = 0;
          }
          e = 0 !== (e & (d.suspendedLanes | g)) ? 0 : e;
          0 !== e && e !== f.retryLane && (f.retryLane = e, Oa(a, e), xa(d, a, e, -1));
        }
        Ef();
        d = vf(Error(m(421)));
        return Hd(a, b, g, d);
      }
      if ("$?" === e.data) return b.flags |= 128, b.child = a.child, b = vk.bind(null, a), e._reactRetry = b, null;
      a = f.treeContext;
      fa = Ka(e.nextSibling);
      la = b;
      D = !0;
      wa = null;
      null !== a && (na[oa++] = Ma, na[oa++] = Na, na[oa++] = rb, Ma = a.id, Na = a.overflow, rb = b);
      b = Df(b, d.children);
      b.flags |= 4096;
      return b;
    }
    function vi(a, b, c) {
      a.lanes |= b;
      var d = a.alternate;
      null !== d && (d.lanes |= b);
      df(a.return, b, c);
    }
    function Ff(a, b, c, d, e) {
      var f = a.memoizedState;
      null === f ? a.memoizedState = {
        isBackwards: b,
        rendering: null,
        renderingStartTime: 0,
        last: d,
        tail: c,
        tailMode: e
      } : (f.isBackwards = b, f.rendering = null, f.renderingStartTime = 0, f.last = d, f.tail = c, f.tailMode = e);
    }
    function wi(a, b, c) {
      var d = b.pendingProps,
        e = d.revealOrder,
        f = d.tail;
      aa(a, b, d.children, c);
      d = F.current;
      if (0 !== (d & 2)) d = d & 1 | 2, b.flags |= 128;else {
        if (null !== a && 0 !== (a.flags & 128)) a: for (a = b.child; null !== a;) {
          if (13 === a.tag) null !== a.memoizedState && vi(a, c, b);else if (19 === a.tag) vi(a, c, b);else if (null !== a.child) {
            a.child.return = a;
            a = a.child;
            continue;
          }
          if (a === b) break a;
          for (; null === a.sibling;) {
            if (null === a.return || a.return === b) break a;
            a = a.return;
          }
          a.sibling.return = a.return;
          a = a.sibling;
        }
        d &= 1;
      }
      y(F, d);
      if (0 === (b.mode & 1)) b.memoizedState = null;else switch (e) {
        case "forwards":
          c = b.child;
          for (e = null; null !== c;) a = c.alternate, null !== a && null === xd(a) && (e = c), c = c.sibling;
          c = e;
          null === c ? (e = b.child, b.child = null) : (e = c.sibling, c.sibling = null);
          Ff(b, !1, e, c, f);
          break;
        case "backwards":
          c = null;
          e = b.child;
          for (b.child = null; null !== e;) {
            a = e.alternate;
            if (null !== a && null === xd(a)) {
              b.child = e;
              break;
            }
            a = e.sibling;
            e.sibling = c;
            c = e;
            e = a;
          }
          Ff(b, !0, c, null, f);
          break;
        case "together":
          Ff(b, !1, null, null, void 0);
          break;
        default:
          b.memoizedState = null;
      }
      return b.child;
    }
    function Fd(a, b) {
      0 === (b.mode & 1) && null !== a && (a.alternate = null, b.alternate = null, b.flags |= 2);
    }
    function Qa(a, b, c) {
      null !== a && (b.dependencies = a.dependencies);
      ra |= b.lanes;
      if (0 === (c & b.childLanes)) return null;
      if (null !== a && b.child !== a.child) throw Error(m(153));
      if (null !== b.child) {
        a = b.child;
        c = eb(a, a.pendingProps);
        b.child = c;
        for (c.return = b; null !== a.sibling;) a = a.sibling, c = c.sibling = eb(a, a.pendingProps), c.return = b;
        c.sibling = null;
      }
      return b.child;
    }
    function wk(a, b, c) {
      switch (b.tag) {
        case 3:
          si(b);
          Qb();
          break;
        case 5:
          Ih(b);
          break;
        case 1:
          ea(b.type) && ld(b);
          break;
        case 4:
          gf(b, b.stateNode.containerInfo);
          break;
        case 10:
          var d = b.type._context,
            e = b.memoizedProps.value;
          y(ud, d._currentValue);
          d._currentValue = e;
          break;
        case 13:
          d = b.memoizedState;
          if (null !== d) {
            if (null !== d.dehydrated) return y(F, F.current & 1), b.flags |= 128, null;
            if (0 !== (c & b.child.childLanes)) return ui(a, b, c);
            y(F, F.current & 1);
            a = Qa(a, b, c);
            return null !== a ? a.sibling : null;
          }
          y(F, F.current & 1);
          break;
        case 19:
          d = 0 !== (c & b.childLanes);
          if (0 !== (a.flags & 128)) {
            if (d) return wi(a, b, c);
            b.flags |= 128;
          }
          e = b.memoizedState;
          null !== e && (e.rendering = null, e.tail = null, e.lastEffect = null);
          y(F, F.current);
          if (d) break;else return null;
        case 22:
        case 23:
          return b.lanes = 0, pi(a, b, c);
      }
      return Qa(a, b, c);
    }
    function Dc(a, b) {
      if (!D) switch (a.tailMode) {
        case "hidden":
          b = a.tail;
          for (var c = null; null !== b;) null !== b.alternate && (c = b), b = b.sibling;
          null === c ? a.tail = null : c.sibling = null;
          break;
        case "collapsed":
          c = a.tail;
          for (var d = null; null !== c;) null !== c.alternate && (d = c), c = c.sibling;
          null === d ? b || null === a.tail ? a.tail = null : a.tail.sibling = null : d.sibling = null;
      }
    }
    function W(a) {
      var b = null !== a.alternate && a.alternate.child === a.child,
        c = 0,
        d = 0;
      if (b) for (var e = a.child; null !== e;) c |= e.lanes | e.childLanes, d |= e.subtreeFlags & 14680064, d |= e.flags & 14680064, e.return = a, e = e.sibling;else for (e = a.child; null !== e;) c |= e.lanes | e.childLanes, d |= e.subtreeFlags, d |= e.flags, e.return = a, e = e.sibling;
      a.subtreeFlags |= d;
      a.childLanes = c;
      return b;
    }
    function xk(a, b, c) {
      var d = b.pendingProps;
      Ve(b);
      switch (b.tag) {
        case 2:
        case 16:
        case 15:
        case 0:
        case 11:
        case 7:
        case 8:
        case 12:
        case 9:
        case 14:
          return W(b), null;
        case 1:
          return ea(b.type) && (v(S), v(J)), W(b), null;
        case 3:
          d = b.stateNode;
          Tb();
          v(S);
          v(J);
          jf();
          d.pendingContext && (d.context = d.pendingContext, d.pendingContext = null);
          if (null === a || null === a.child) pd(b) ? b.flags |= 4 : null === a || a.memoizedState.isDehydrated && 0 === (b.flags & 256) || (b.flags |= 1024, null !== wa && (Gf(wa), wa = null));
          xi(a, b);
          W(b);
          return null;
        case 5:
          hf(b);
          var e = ub(xc.current);
          c = b.type;
          if (null !== a && null != b.stateNode) yk(a, b, c, d, e), a.ref !== b.ref && (b.flags |= 512, b.flags |= 2097152);else {
            if (!d) {
              if (null === b.stateNode) throw Error(m(166));
              W(b);
              return null;
            }
            a = ub(Ea.current);
            if (pd(b)) {
              d = b.stateNode;
              c = b.type;
              var f = b.memoizedProps;
              d[Da] = b;
              d[uc] = f;
              a = 0 !== (b.mode & 1);
              switch (c) {
                case "dialog":
                  B("cancel", d);
                  B("close", d);
                  break;
                case "iframe":
                case "object":
                case "embed":
                  B("load", d);
                  break;
                case "video":
                case "audio":
                  for (e = 0; e < Ec.length; e++) B(Ec[e], d);
                  break;
                case "source":
                  B("error", d);
                  break;
                case "img":
                case "image":
                case "link":
                  B("error", d);
                  B("load", d);
                  break;
                case "details":
                  B("toggle", d);
                  break;
                case "input":
                  kg(d, f);
                  B("invalid", d);
                  break;
                case "select":
                  d._wrapperState = {
                    wasMultiple: !!f.multiple
                  };
                  B("invalid", d);
                  break;
                case "textarea":
                  ng(d, f), B("invalid", d);
              }
              pe(c, f);
              e = null;
              for (var g in f) if (f.hasOwnProperty(g)) {
                var h = f[g];
                "children" === g ? "string" === typeof h ? d.textContent !== h && (!0 !== f.suppressHydrationWarning && jd(d.textContent, h, a), e = ["children", h]) : "number" === typeof h && d.textContent !== "" + h && (!0 !== f.suppressHydrationWarning && jd(d.textContent, h, a), e = ["children", "" + h]) : $b.hasOwnProperty(g) && null != h && "onScroll" === g && B("scroll", d);
              }
              switch (c) {
                case "input":
                  Pc(d);
                  mg(d, f, !0);
                  break;
                case "textarea":
                  Pc(d);
                  pg(d);
                  break;
                case "select":
                case "option":
                  break;
                default:
                  "function" === typeof f.onClick && (d.onclick = kd);
              }
              d = e;
              b.updateQueue = d;
              null !== d && (b.flags |= 4);
            } else {
              g = 9 === e.nodeType ? e : e.ownerDocument;
              "http://www.w3.org/1999/xhtml" === a && (a = qg(c));
              "http://www.w3.org/1999/xhtml" === a ? "script" === c ? (a = g.createElement("div"), a.innerHTML = "<script>\x3c/script>", a = a.removeChild(a.firstChild)) : "string" === typeof d.is ? a = g.createElement(c, {
                is: d.is
              }) : (a = g.createElement(c), "select" === c && (g = a, d.multiple ? g.multiple = !0 : d.size && (g.size = d.size))) : a = g.createElementNS(a, c);
              a[Da] = b;
              a[uc] = d;
              zk(a, b, !1, !1);
              b.stateNode = a;
              a: {
                g = qe(c, d);
                switch (c) {
                  case "dialog":
                    B("cancel", a);
                    B("close", a);
                    e = d;
                    break;
                  case "iframe":
                  case "object":
                  case "embed":
                    B("load", a);
                    e = d;
                    break;
                  case "video":
                  case "audio":
                    for (e = 0; e < Ec.length; e++) B(Ec[e], a);
                    e = d;
                    break;
                  case "source":
                    B("error", a);
                    e = d;
                    break;
                  case "img":
                  case "image":
                  case "link":
                    B("error", a);
                    B("load", a);
                    e = d;
                    break;
                  case "details":
                    B("toggle", a);
                    e = d;
                    break;
                  case "input":
                    kg(a, d);
                    e = ke(a, d);
                    B("invalid", a);
                    break;
                  case "option":
                    e = d;
                    break;
                  case "select":
                    a._wrapperState = {
                      wasMultiple: !!d.multiple
                    };
                    e = E({}, d, {
                      value: void 0
                    });
                    B("invalid", a);
                    break;
                  case "textarea":
                    ng(a, d);
                    e = ne(a, d);
                    B("invalid", a);
                    break;
                  default:
                    e = d;
                }
                pe(c, e);
                h = e;
                for (f in h) if (h.hasOwnProperty(f)) {
                  var k = h[f];
                  "style" === f ? sg(a, k) : "dangerouslySetInnerHTML" === f ? (k = k ? k.__html : void 0, null != k && yi(a, k)) : "children" === f ? "string" === typeof k ? ("textarea" !== c || "" !== k) && Fc(a, k) : "number" === typeof k && Fc(a, "" + k) : "suppressContentEditableWarning" !== f && "suppressHydrationWarning" !== f && "autoFocus" !== f && ($b.hasOwnProperty(f) ? null != k && "onScroll" === f && B("scroll", a) : null != k && $d(a, f, k, g));
                }
                switch (c) {
                  case "input":
                    Pc(a);
                    mg(a, d, !1);
                    break;
                  case "textarea":
                    Pc(a);
                    pg(a);
                    break;
                  case "option":
                    null != d.value && a.setAttribute("value", "" + Ua(d.value));
                    break;
                  case "select":
                    a.multiple = !!d.multiple;
                    f = d.value;
                    null != f ? Db(a, !!d.multiple, f, !1) : null != d.defaultValue && Db(a, !!d.multiple, d.defaultValue, !0);
                    break;
                  default:
                    "function" === typeof e.onClick && (a.onclick = kd);
                }
                switch (c) {
                  case "button":
                  case "input":
                  case "select":
                  case "textarea":
                    d = !!d.autoFocus;
                    break a;
                  case "img":
                    d = !0;
                    break a;
                  default:
                    d = !1;
                }
              }
              d && (b.flags |= 4);
            }
            null !== b.ref && (b.flags |= 512, b.flags |= 2097152);
          }
          W(b);
          return null;
        case 6:
          if (a && null != b.stateNode) Ak(a, b, a.memoizedProps, d);else {
            if ("string" !== typeof d && null === b.stateNode) throw Error(m(166));
            c = ub(xc.current);
            ub(Ea.current);
            if (pd(b)) {
              d = b.stateNode;
              c = b.memoizedProps;
              d[Da] = b;
              if (f = d.nodeValue !== c) if (a = la, null !== a) switch (a.tag) {
                case 3:
                  jd(d.nodeValue, c, 0 !== (a.mode & 1));
                  break;
                case 5:
                  !0 !== a.memoizedProps.suppressHydrationWarning && jd(d.nodeValue, c, 0 !== (a.mode & 1));
              }
              f && (b.flags |= 4);
            } else d = (9 === c.nodeType ? c : c.ownerDocument).createTextNode(d), d[Da] = b, b.stateNode = d;
          }
          W(b);
          return null;
        case 13:
          v(F);
          d = b.memoizedState;
          if (null === a || null !== a.memoizedState && null !== a.memoizedState.dehydrated) {
            if (D && null !== fa && 0 !== (b.mode & 1) && 0 === (b.flags & 128)) {
              for (f = fa; f;) f = Ka(f.nextSibling);
              Qb();
              b.flags |= 98560;
              f = !1;
            } else if (f = pd(b), null !== d && null !== d.dehydrated) {
              if (null === a) {
                if (!f) throw Error(m(318));
                f = b.memoizedState;
                f = null !== f ? f.dehydrated : null;
                if (!f) throw Error(m(317));
                f[Da] = b;
              } else Qb(), 0 === (b.flags & 128) && (b.memoizedState = null), b.flags |= 4;
              W(b);
              f = !1;
            } else null !== wa && (Gf(wa), wa = null), f = !0;
            if (!f) return b.flags & 65536 ? b : null;
          }
          if (0 !== (b.flags & 128)) return b.lanes = c, b;
          d = null !== d;
          d !== (null !== a && null !== a.memoizedState) && d && (b.child.flags |= 8192, 0 !== (b.mode & 1) && (null === a || 0 !== (F.current & 1) ? 0 === L && (L = 3) : Ef()));
          null !== b.updateQueue && (b.flags |= 4);
          W(b);
          return null;
        case 4:
          return Tb(), xi(a, b), null === a && sc(b.stateNode.containerInfo), W(b), null;
        case 10:
          return cf(b.type._context), W(b), null;
        case 17:
          return ea(b.type) && (v(S), v(J)), W(b), null;
        case 19:
          v(F);
          f = b.memoizedState;
          if (null === f) return W(b), null;
          d = 0 !== (b.flags & 128);
          g = f.rendering;
          if (null === g) {
            if (d) Dc(f, !1);else {
              if (0 !== L || null !== a && 0 !== (a.flags & 128)) for (a = b.child; null !== a;) {
                g = xd(a);
                if (null !== g) {
                  b.flags |= 128;
                  Dc(f, !1);
                  d = g.updateQueue;
                  null !== d && (b.updateQueue = d, b.flags |= 4);
                  b.subtreeFlags = 0;
                  d = c;
                  for (c = b.child; null !== c;) f = c, a = d, f.flags &= 14680066, g = f.alternate, null === g ? (f.childLanes = 0, f.lanes = a, f.child = null, f.subtreeFlags = 0, f.memoizedProps = null, f.memoizedState = null, f.updateQueue = null, f.dependencies = null, f.stateNode = null) : (f.childLanes = g.childLanes, f.lanes = g.lanes, f.child = g.child, f.subtreeFlags = 0, f.deletions = null, f.memoizedProps = g.memoizedProps, f.memoizedState = g.memoizedState, f.updateQueue = g.updateQueue, f.type = g.type, a = g.dependencies, f.dependencies = null === a ? null : {
                    lanes: a.lanes,
                    firstContext: a.firstContext
                  }), c = c.sibling;
                  y(F, F.current & 1 | 2);
                  return b.child;
                }
                a = a.sibling;
              }
              null !== f.tail && P() > Hf && (b.flags |= 128, d = !0, Dc(f, !1), b.lanes = 4194304);
            }
          } else {
            if (!d) if (a = xd(g), null !== a) {
              if (b.flags |= 128, d = !0, c = a.updateQueue, null !== c && (b.updateQueue = c, b.flags |= 4), Dc(f, !0), null === f.tail && "hidden" === f.tailMode && !g.alternate && !D) return W(b), null;
            } else 2 * P() - f.renderingStartTime > Hf && 1073741824 !== c && (b.flags |= 128, d = !0, Dc(f, !1), b.lanes = 4194304);
            f.isBackwards ? (g.sibling = b.child, b.child = g) : (c = f.last, null !== c ? c.sibling = g : b.child = g, f.last = g);
          }
          if (null !== f.tail) return b = f.tail, f.rendering = b, f.tail = b.sibling, f.renderingStartTime = P(), b.sibling = null, c = F.current, y(F, d ? c & 1 | 2 : c & 1), b;
          W(b);
          return null;
        case 22:
        case 23:
          return ba = Ga.current, v(Ga), d = null !== b.memoizedState, null !== a && null !== a.memoizedState !== d && (b.flags |= 8192), d && 0 !== (b.mode & 1) ? 0 !== (ba & 1073741824) && (W(b), b.subtreeFlags & 6 && (b.flags |= 8192)) : W(b), null;
        case 24:
          return null;
        case 25:
          return null;
      }
      throw Error(m(156, b.tag));
    }
    function Bk(a, b, c) {
      Ve(b);
      switch (b.tag) {
        case 1:
          return ea(b.type) && (v(S), v(J)), a = b.flags, a & 65536 ? (b.flags = a & -65537 | 128, b) : null;
        case 3:
          return Tb(), v(S), v(J), jf(), a = b.flags, 0 !== (a & 65536) && 0 === (a & 128) ? (b.flags = a & -65537 | 128, b) : null;
        case 5:
          return hf(b), null;
        case 13:
          v(F);
          a = b.memoizedState;
          if (null !== a && null !== a.dehydrated) {
            if (null === b.alternate) throw Error(m(340));
            Qb();
          }
          a = b.flags;
          return a & 65536 ? (b.flags = a & -65537 | 128, b) : null;
        case 19:
          return v(F), null;
        case 4:
          return Tb(), null;
        case 10:
          return cf(b.type._context), null;
        case 22:
        case 23:
          return ba = Ga.current, v(Ga), null;
        case 24:
          return null;
        default:
          return null;
      }
    }
    function Wb(a, b) {
      var c = a.ref;
      if (null !== c) if ("function" === typeof c) try {
        c(null);
      } catch (d) {
        G(a, b, d);
      } else c.current = null;
    }
    function If(a, b, c) {
      try {
        c();
      } catch (d) {
        G(a, b, d);
      }
    }
    function Ck(a, b) {
      Jf = Zc;
      a = ch();
      if (Ie(a)) {
        if ("selectionStart" in a) var c = {
          start: a.selectionStart,
          end: a.selectionEnd
        };else a: {
          c = (c = a.ownerDocument) && c.defaultView || window;
          var d = c.getSelection && c.getSelection();
          if (d && 0 !== d.rangeCount) {
            c = d.anchorNode;
            var e = d.anchorOffset,
              f = d.focusNode;
            d = d.focusOffset;
            try {
              c.nodeType, f.nodeType;
            } catch (M) {
              c = null;
              break a;
            }
            var g = 0,
              h = -1,
              k = -1,
              n = 0,
              q = 0,
              u = a,
              r = null;
            b: for (;;) {
              for (var p;;) {
                u !== c || 0 !== e && 3 !== u.nodeType || (h = g + e);
                u !== f || 0 !== d && 3 !== u.nodeType || (k = g + d);
                3 === u.nodeType && (g += u.nodeValue.length);
                if (null === (p = u.firstChild)) break;
                r = u;
                u = p;
              }
              for (;;) {
                if (u === a) break b;
                r === c && ++n === e && (h = g);
                r === f && ++q === d && (k = g);
                if (null !== (p = u.nextSibling)) break;
                u = r;
                r = u.parentNode;
              }
              u = p;
            }
            c = -1 === h || -1 === k ? null : {
              start: h,
              end: k
            };
          } else c = null;
        }
        c = c || {
          start: 0,
          end: 0
        };
      } else c = null;
      Kf = {
        focusedElem: a,
        selectionRange: c
      };
      Zc = !1;
      for (l = b; null !== l;) if (b = l, a = b.child, 0 !== (b.subtreeFlags & 1028) && null !== a) a.return = b, l = a;else for (; null !== l;) {
        b = l;
        try {
          var x = b.alternate;
          if (0 !== (b.flags & 1024)) switch (b.tag) {
            case 0:
            case 11:
            case 15:
              break;
            case 1:
              if (null !== x) {
                var v = x.memoizedProps,
                  z = x.memoizedState,
                  w = b.stateNode,
                  A = w.getSnapshotBeforeUpdate(b.elementType === b.type ? v : ya(b.type, v), z);
                w.__reactInternalSnapshotBeforeUpdate = A;
              }
              break;
            case 3:
              var t = b.stateNode.containerInfo;
              1 === t.nodeType ? t.textContent = "" : 9 === t.nodeType && t.documentElement && t.removeChild(t.documentElement);
              break;
            case 5:
            case 6:
            case 4:
            case 17:
              break;
            default:
              throw Error(m(163));
          }
        } catch (M) {
          G(b, b.return, M);
        }
        a = b.sibling;
        if (null !== a) {
          a.return = b.return;
          l = a;
          break;
        }
        l = b.return;
      }
      x = zi;
      zi = !1;
      return x;
    }
    function Gc(a, b, c) {
      var d = b.updateQueue;
      d = null !== d ? d.lastEffect : null;
      if (null !== d) {
        var e = d = d.next;
        do {
          if ((e.tag & a) === a) {
            var f = e.destroy;
            e.destroy = void 0;
            void 0 !== f && If(b, c, f);
          }
          e = e.next;
        } while (e !== d);
      }
    }
    function Id(a, b) {
      b = b.updateQueue;
      b = null !== b ? b.lastEffect : null;
      if (null !== b) {
        var c = b = b.next;
        do {
          if ((c.tag & a) === a) {
            var d = c.create;
            c.destroy = d();
          }
          c = c.next;
        } while (c !== b);
      }
    }
    function Lf(a) {
      var b = a.ref;
      if (null !== b) {
        var c = a.stateNode;
        switch (a.tag) {
          case 5:
            a = c;
            break;
          default:
            a = c;
        }
        "function" === typeof b ? b(a) : b.current = a;
      }
    }
    function Ai(a) {
      var b = a.alternate;
      null !== b && (a.alternate = null, Ai(b));
      a.child = null;
      a.deletions = null;
      a.sibling = null;
      5 === a.tag && (b = a.stateNode, null !== b && (delete b[Da], delete b[uc], delete b[Me], delete b[Dk], delete b[Ek]));
      a.stateNode = null;
      a.return = null;
      a.dependencies = null;
      a.memoizedProps = null;
      a.memoizedState = null;
      a.pendingProps = null;
      a.stateNode = null;
      a.updateQueue = null;
    }
    function Bi(a) {
      return 5 === a.tag || 3 === a.tag || 4 === a.tag;
    }
    function Ci(a) {
      a: for (;;) {
        for (; null === a.sibling;) {
          if (null === a.return || Bi(a.return)) return null;
          a = a.return;
        }
        a.sibling.return = a.return;
        for (a = a.sibling; 5 !== a.tag && 6 !== a.tag && 18 !== a.tag;) {
          if (a.flags & 2) continue a;
          if (null === a.child || 4 === a.tag) continue a;else a.child.return = a, a = a.child;
        }
        if (!(a.flags & 2)) return a.stateNode;
      }
    }
    function Mf(a, b, c) {
      var d = a.tag;
      if (5 === d || 6 === d) a = a.stateNode, b ? 8 === c.nodeType ? c.parentNode.insertBefore(a, b) : c.insertBefore(a, b) : (8 === c.nodeType ? (b = c.parentNode, b.insertBefore(a, c)) : (b = c, b.appendChild(a)), c = c._reactRootContainer, null !== c && void 0 !== c || null !== b.onclick || (b.onclick = kd));else if (4 !== d && (a = a.child, null !== a)) for (Mf(a, b, c), a = a.sibling; null !== a;) Mf(a, b, c), a = a.sibling;
    }
    function Nf(a, b, c) {
      var d = a.tag;
      if (5 === d || 6 === d) a = a.stateNode, b ? c.insertBefore(a, b) : c.appendChild(a);else if (4 !== d && (a = a.child, null !== a)) for (Nf(a, b, c), a = a.sibling; null !== a;) Nf(a, b, c), a = a.sibling;
    }
    function jb(a, b, c) {
      for (c = c.child; null !== c;) Di(a, b, c), c = c.sibling;
    }
    function Di(a, b, c) {
      if (Ca && "function" === typeof Ca.onCommitFiberUnmount) try {
        Ca.onCommitFiberUnmount(Uc, c);
      } catch (h) {}
      switch (c.tag) {
        case 5:
          X || Wb(c, b);
        case 6:
          var d = T,
            e = za;
          T = null;
          jb(a, b, c);
          T = d;
          za = e;
          null !== T && (za ? (a = T, c = c.stateNode, 8 === a.nodeType ? a.parentNode.removeChild(c) : a.removeChild(c)) : T.removeChild(c.stateNode));
          break;
        case 18:
          null !== T && (za ? (a = T, c = c.stateNode, 8 === a.nodeType ? Re(a.parentNode, c) : 1 === a.nodeType && Re(a, c), nc(a)) : Re(T, c.stateNode));
          break;
        case 4:
          d = T;
          e = za;
          T = c.stateNode.containerInfo;
          za = !0;
          jb(a, b, c);
          T = d;
          za = e;
          break;
        case 0:
        case 11:
        case 14:
        case 15:
          if (!X && (d = c.updateQueue, null !== d && (d = d.lastEffect, null !== d))) {
            e = d = d.next;
            do {
              var f = e,
                g = f.destroy;
              f = f.tag;
              void 0 !== g && (0 !== (f & 2) ? If(c, b, g) : 0 !== (f & 4) && If(c, b, g));
              e = e.next;
            } while (e !== d);
          }
          jb(a, b, c);
          break;
        case 1:
          if (!X && (Wb(c, b), d = c.stateNode, "function" === typeof d.componentWillUnmount)) try {
            d.props = c.memoizedProps, d.state = c.memoizedState, d.componentWillUnmount();
          } catch (h) {
            G(c, b, h);
          }
          jb(a, b, c);
          break;
        case 21:
          jb(a, b, c);
          break;
        case 22:
          c.mode & 1 ? (X = (d = X) || null !== c.memoizedState, jb(a, b, c), X = d) : jb(a, b, c);
          break;
        default:
          jb(a, b, c);
      }
    }
    function Ei(a) {
      var b = a.updateQueue;
      if (null !== b) {
        a.updateQueue = null;
        var c = a.stateNode;
        null === c && (c = a.stateNode = new Fk());
        b.forEach(function (b) {
          var d = Gk.bind(null, a, b);
          c.has(b) || (c.add(b), b.then(d, d));
        });
      }
    }
    function Aa(a, b, c) {
      c = b.deletions;
      if (null !== c) for (var d = 0; d < c.length; d++) {
        var e = c[d];
        try {
          var f = a,
            g = b,
            h = g;
          a: for (; null !== h;) {
            switch (h.tag) {
              case 5:
                T = h.stateNode;
                za = !1;
                break a;
              case 3:
                T = h.stateNode.containerInfo;
                za = !0;
                break a;
              case 4:
                T = h.stateNode.containerInfo;
                za = !0;
                break a;
            }
            h = h.return;
          }
          if (null === T) throw Error(m(160));
          Di(f, g, e);
          T = null;
          za = !1;
          var k = e.alternate;
          null !== k && (k.return = null);
          e.return = null;
        } catch (n) {
          G(e, b, n);
        }
      }
      if (b.subtreeFlags & 12854) for (b = b.child; null !== b;) Fi(b, a), b = b.sibling;
    }
    function Fi(a, b, c) {
      var d = a.alternate;
      c = a.flags;
      switch (a.tag) {
        case 0:
        case 11:
        case 14:
        case 15:
          Aa(b, a);
          Ha(a);
          if (c & 4) {
            try {
              Gc(3, a, a.return), Id(3, a);
            } catch (I) {
              G(a, a.return, I);
            }
            try {
              Gc(5, a, a.return);
            } catch (I) {
              G(a, a.return, I);
            }
          }
          break;
        case 1:
          Aa(b, a);
          Ha(a);
          c & 512 && null !== d && Wb(d, d.return);
          break;
        case 5:
          Aa(b, a);
          Ha(a);
          c & 512 && null !== d && Wb(d, d.return);
          if (a.flags & 32) {
            var e = a.stateNode;
            try {
              Fc(e, "");
            } catch (I) {
              G(a, a.return, I);
            }
          }
          if (c & 4 && (e = a.stateNode, null != e)) {
            var f = a.memoizedProps,
              g = null !== d ? d.memoizedProps : f,
              h = a.type,
              k = a.updateQueue;
            a.updateQueue = null;
            if (null !== k) try {
              "input" === h && "radio" === f.type && null != f.name && lg(e, f);
              qe(h, g);
              var n = qe(h, f);
              for (g = 0; g < k.length; g += 2) {
                var q = k[g],
                  u = k[g + 1];
                "style" === q ? sg(e, u) : "dangerouslySetInnerHTML" === q ? yi(e, u) : "children" === q ? Fc(e, u) : $d(e, q, u, n);
              }
              switch (h) {
                case "input":
                  le(e, f);
                  break;
                case "textarea":
                  og(e, f);
                  break;
                case "select":
                  var r = e._wrapperState.wasMultiple;
                  e._wrapperState.wasMultiple = !!f.multiple;
                  var p = f.value;
                  null != p ? Db(e, !!f.multiple, p, !1) : r !== !!f.multiple && (null != f.defaultValue ? Db(e, !!f.multiple, f.defaultValue, !0) : Db(e, !!f.multiple, f.multiple ? [] : "", !1));
              }
              e[uc] = f;
            } catch (I) {
              G(a, a.return, I);
            }
          }
          break;
        case 6:
          Aa(b, a);
          Ha(a);
          if (c & 4) {
            if (null === a.stateNode) throw Error(m(162));
            e = a.stateNode;
            f = a.memoizedProps;
            try {
              e.nodeValue = f;
            } catch (I) {
              G(a, a.return, I);
            }
          }
          break;
        case 3:
          Aa(b, a);
          Ha(a);
          if (c & 4 && null !== d && d.memoizedState.isDehydrated) try {
            nc(b.containerInfo);
          } catch (I) {
            G(a, a.return, I);
          }
          break;
        case 4:
          Aa(b, a);
          Ha(a);
          break;
        case 13:
          Aa(b, a);
          Ha(a);
          e = a.child;
          e.flags & 8192 && (f = null !== e.memoizedState, e.stateNode.isHidden = f, !f || null !== e.alternate && null !== e.alternate.memoizedState || (Of = P()));
          c & 4 && Ei(a);
          break;
        case 22:
          q = null !== d && null !== d.memoizedState;
          a.mode & 1 ? (X = (n = X) || q, Aa(b, a), X = n) : Aa(b, a);
          Ha(a);
          if (c & 8192) {
            n = null !== a.memoizedState;
            if ((a.stateNode.isHidden = n) && !q && 0 !== (a.mode & 1)) for (l = a, q = a.child; null !== q;) {
              for (u = l = q; null !== l;) {
                r = l;
                p = r.child;
                switch (r.tag) {
                  case 0:
                  case 11:
                  case 14:
                  case 15:
                    Gc(4, r, r.return);
                    break;
                  case 1:
                    Wb(r, r.return);
                    var x = r.stateNode;
                    if ("function" === typeof x.componentWillUnmount) {
                      c = r;
                      b = r.return;
                      try {
                        d = c, x.props = d.memoizedProps, x.state = d.memoizedState, x.componentWillUnmount();
                      } catch (I) {
                        G(c, b, I);
                      }
                    }
                    break;
                  case 5:
                    Wb(r, r.return);
                    break;
                  case 22:
                    if (null !== r.memoizedState) {
                      Gi(u);
                      continue;
                    }
                }
                null !== p ? (p.return = r, l = p) : Gi(u);
              }
              q = q.sibling;
            }
            a: for (q = null, u = a;;) {
              if (5 === u.tag) {
                if (null === q) {
                  q = u;
                  try {
                    e = u.stateNode, n ? (f = e.style, "function" === typeof f.setProperty ? f.setProperty("display", "none", "important") : f.display = "none") : (h = u.stateNode, k = u.memoizedProps.style, g = void 0 !== k && null !== k && k.hasOwnProperty("display") ? k.display : null, h.style.display = rg("display", g));
                  } catch (I) {
                    G(a, a.return, I);
                  }
                }
              } else if (6 === u.tag) {
                if (null === q) try {
                  u.stateNode.nodeValue = n ? "" : u.memoizedProps;
                } catch (I) {
                  G(a, a.return, I);
                }
              } else if ((22 !== u.tag && 23 !== u.tag || null === u.memoizedState || u === a) && null !== u.child) {
                u.child.return = u;
                u = u.child;
                continue;
              }
              if (u === a) break a;
              for (; null === u.sibling;) {
                if (null === u.return || u.return === a) break a;
                q === u && (q = null);
                u = u.return;
              }
              q === u && (q = null);
              u.sibling.return = u.return;
              u = u.sibling;
            }
          }
          break;
        case 19:
          Aa(b, a);
          Ha(a);
          c & 4 && Ei(a);
          break;
        case 21:
          break;
        default:
          Aa(b, a), Ha(a);
      }
    }
    function Ha(a) {
      var b = a.flags;
      if (b & 2) {
        try {
          a: {
            for (var c = a.return; null !== c;) {
              if (Bi(c)) {
                var d = c;
                break a;
              }
              c = c.return;
            }
            throw Error(m(160));
          }
          switch (d.tag) {
            case 5:
              var e = d.stateNode;
              d.flags & 32 && (Fc(e, ""), d.flags &= -33);
              var f = Ci(a);
              Nf(a, f, e);
              break;
            case 3:
            case 4:
              var g = d.stateNode.containerInfo,
                h = Ci(a);
              Mf(a, h, g);
              break;
            default:
              throw Error(m(161));
          }
        } catch (k) {
          G(a, a.return, k);
        }
        a.flags &= -3;
      }
      b & 4096 && (a.flags &= -4097);
    }
    function Hk(a, b, c) {
      l = a;
      Hi(a, b, c);
    }
    function Hi(a, b, c) {
      for (var d = 0 !== (a.mode & 1); null !== l;) {
        var e = l,
          f = e.child;
        if (22 === e.tag && d) {
          var g = null !== e.memoizedState || Jd;
          if (!g) {
            var h = e.alternate,
              k = null !== h && null !== h.memoizedState || X;
            h = Jd;
            var n = X;
            Jd = g;
            if ((X = k) && !n) for (l = e; null !== l;) g = l, k = g.child, 22 === g.tag && null !== g.memoizedState ? Ii(e) : null !== k ? (k.return = g, l = k) : Ii(e);
            for (; null !== f;) l = f, Hi(f, b, c), f = f.sibling;
            l = e;
            Jd = h;
            X = n;
          }
          Ji(a, b, c);
        } else 0 !== (e.subtreeFlags & 8772) && null !== f ? (f.return = e, l = f) : Ji(a, b, c);
      }
    }
    function Ji(a, b, c) {
      for (; null !== l;) {
        b = l;
        if (0 !== (b.flags & 8772)) {
          c = b.alternate;
          try {
            if (0 !== (b.flags & 8772)) switch (b.tag) {
              case 0:
              case 11:
              case 15:
                X || Id(5, b);
                break;
              case 1:
                var d = b.stateNode;
                if (b.flags & 4 && !X) if (null === c) d.componentDidMount();else {
                  var e = b.elementType === b.type ? c.memoizedProps : ya(b.type, c.memoizedProps);
                  d.componentDidUpdate(e, c.memoizedState, d.__reactInternalSnapshotBeforeUpdate);
                }
                var f = b.updateQueue;
                null !== f && Hh(b, f, d);
                break;
              case 3:
                var g = b.updateQueue;
                if (null !== g) {
                  c = null;
                  if (null !== b.child) switch (b.child.tag) {
                    case 5:
                      c = b.child.stateNode;
                      break;
                    case 1:
                      c = b.child.stateNode;
                  }
                  Hh(b, g, c);
                }
                break;
              case 5:
                var h = b.stateNode;
                if (null === c && b.flags & 4) {
                  c = h;
                  var k = b.memoizedProps;
                  switch (b.type) {
                    case "button":
                    case "input":
                    case "select":
                    case "textarea":
                      k.autoFocus && c.focus();
                      break;
                    case "img":
                      k.src && (c.src = k.src);
                  }
                }
                break;
              case 6:
                break;
              case 4:
                break;
              case 12:
                break;
              case 13:
                if (null === b.memoizedState) {
                  var n = b.alternate;
                  if (null !== n) {
                    var q = n.memoizedState;
                    if (null !== q) {
                      var p = q.dehydrated;
                      null !== p && nc(p);
                    }
                  }
                }
                break;
              case 19:
              case 17:
              case 21:
              case 22:
              case 23:
              case 25:
                break;
              default:
                throw Error(m(163));
            }
            X || b.flags & 512 && Lf(b);
          } catch (r) {
            G(b, b.return, r);
          }
        }
        if (b === a) {
          l = null;
          break;
        }
        c = b.sibling;
        if (null !== c) {
          c.return = b.return;
          l = c;
          break;
        }
        l = b.return;
      }
    }
    function Gi(a) {
      for (; null !== l;) {
        var b = l;
        if (b === a) {
          l = null;
          break;
        }
        var c = b.sibling;
        if (null !== c) {
          c.return = b.return;
          l = c;
          break;
        }
        l = b.return;
      }
    }
    function Ii(a) {
      for (; null !== l;) {
        var b = l;
        try {
          switch (b.tag) {
            case 0:
            case 11:
            case 15:
              var c = b.return;
              try {
                Id(4, b);
              } catch (k) {
                G(b, c, k);
              }
              break;
            case 1:
              var d = b.stateNode;
              if ("function" === typeof d.componentDidMount) {
                var e = b.return;
                try {
                  d.componentDidMount();
                } catch (k) {
                  G(b, e, k);
                }
              }
              var f = b.return;
              try {
                Lf(b);
              } catch (k) {
                G(b, f, k);
              }
              break;
            case 5:
              var g = b.return;
              try {
                Lf(b);
              } catch (k) {
                G(b, g, k);
              }
          }
        } catch (k) {
          G(b, b.return, k);
        }
        if (b === a) {
          l = null;
          break;
        }
        var h = b.sibling;
        if (null !== h) {
          h.return = b.return;
          l = h;
          break;
        }
        l = b.return;
      }
    }
    function Hc() {
      Hf = P() + 500;
    }
    function Z() {
      return 0 !== (p & 6) ? P() : -1 !== Kd ? Kd : Kd = P();
    }
    function hb(a) {
      if (0 === (a.mode & 1)) return 1;
      if (0 !== (p & 2) && 0 !== U) return U & -U;
      if (null !== Ik.transition) return 0 === Ld && (Ld = Dg()), Ld;
      a = z;
      if (0 !== a) return a;
      a = window.event;
      a = void 0 === a ? 16 : Lg(a.type);
      return a;
    }
    function xa(a, b, c, d) {
      if (50 < Ic) throw Ic = 0, Pf = null, Error(m(185));
      ic(a, c, d);
      if (0 === (p & 2) || a !== O) a === O && (0 === (p & 2) && (Md |= c), 4 === L && kb(a, U)), ia(a, d), 1 === c && 0 === p && 0 === (b.mode & 1) && (Hc(), md && db());
    }
    function ia(a, b) {
      var c = a.callbackNode;
      tj(a, b);
      var d = Vc(a, a === O ? U : 0);
      if (0 === d) null !== c && Ki(c), a.callbackNode = null, a.callbackPriority = 0;else if (b = d & -d, a.callbackPriority !== b) {
        null != c && Ki(c);
        if (1 === b) 0 === a.tag ? jk(Li.bind(null, a)) : wh(Li.bind(null, a)), Jk(function () {
          0 === (p & 6) && db();
        }), c = null;else {
          switch (Eg(d)) {
            case 1:
              c = De;
              break;
            case 4:
              c = Mg;
              break;
            case 16:
              c = ad;
              break;
            case 536870912:
              c = Ng;
              break;
            default:
              c = ad;
          }
          c = Mi(c, Ni.bind(null, a));
        }
        a.callbackPriority = b;
        a.callbackNode = c;
      }
    }
    function Ni(a, b) {
      Kd = -1;
      Ld = 0;
      if (0 !== (p & 6)) throw Error(m(327));
      var c = a.callbackNode;
      if (Xb() && a.callbackNode !== c) return null;
      var d = Vc(a, a === O ? U : 0);
      if (0 === d) return null;
      if (0 !== (d & 30) || 0 !== (d & a.expiredLanes) || b) b = Nd(a, d);else {
        b = d;
        var e = p;
        p |= 2;
        var f = Oi();
        if (O !== a || U !== b) Ra = null, Hc(), wb(a, b);
        do try {
          Kk();
          break;
        } catch (h) {
          Pi(a, h);
        } while (1);
        af();
        Od.current = f;
        p = e;
        null !== H ? b = 0 : (O = null, U = 0, b = L);
      }
      if (0 !== b) {
        2 === b && (e = ve(a), 0 !== e && (d = e, b = Qf(a, e)));
        if (1 === b) throw c = Jc, wb(a, 0), kb(a, d), ia(a, P()), c;
        if (6 === b) kb(a, d);else {
          e = a.current.alternate;
          if (0 === (d & 30) && !Lk(e) && (b = Nd(a, d), 2 === b && (f = ve(a), 0 !== f && (d = f, b = Qf(a, f))), 1 === b)) throw c = Jc, wb(a, 0), kb(a, d), ia(a, P()), c;
          a.finishedWork = e;
          a.finishedLanes = d;
          switch (b) {
            case 0:
            case 1:
              throw Error(m(345));
            case 2:
              xb(a, ja, Ra);
              break;
            case 3:
              kb(a, d);
              if ((d & 130023424) === d && (b = Of + 500 - P(), 10 < b)) {
                if (0 !== Vc(a, 0)) break;
                e = a.suspendedLanes;
                if ((e & d) !== d) {
                  Z();
                  a.pingedLanes |= a.suspendedLanes & e;
                  break;
                }
                a.timeoutHandle = Rf(xb.bind(null, a, ja, Ra), b);
                break;
              }
              xb(a, ja, Ra);
              break;
            case 4:
              kb(a, d);
              if ((d & 4194240) === d) break;
              b = a.eventTimes;
              for (e = -1; 0 < d;) {
                var g = 31 - ta(d);
                f = 1 << g;
                g = b[g];
                g > e && (e = g);
                d &= ~f;
              }
              d = e;
              d = P() - d;
              d = (120 > d ? 120 : 480 > d ? 480 : 1080 > d ? 1080 : 1920 > d ? 1920 : 3E3 > d ? 3E3 : 4320 > d ? 4320 : 1960 * Mk(d / 1960)) - d;
              if (10 < d) {
                a.timeoutHandle = Rf(xb.bind(null, a, ja, Ra), d);
                break;
              }
              xb(a, ja, Ra);
              break;
            case 5:
              xb(a, ja, Ra);
              break;
            default:
              throw Error(m(329));
          }
        }
      }
      ia(a, P());
      return a.callbackNode === c ? Ni.bind(null, a) : null;
    }
    function Qf(a, b) {
      var c = Kc;
      a.current.memoizedState.isDehydrated && (wb(a, b).flags |= 256);
      a = Nd(a, b);
      2 !== a && (b = ja, ja = c, null !== b && Gf(b));
      return a;
    }
    function Gf(a) {
      null === ja ? ja = a : ja.push.apply(ja, a);
    }
    function Lk(a) {
      for (var b = a;;) {
        if (b.flags & 16384) {
          var c = b.updateQueue;
          if (null !== c && (c = c.stores, null !== c)) for (var d = 0; d < c.length; d++) {
            var e = c[d],
              f = e.getSnapshot;
            e = e.value;
            try {
              if (!ua(f(), e)) return !1;
            } catch (g) {
              return !1;
            }
          }
        }
        c = b.child;
        if (b.subtreeFlags & 16384 && null !== c) c.return = b, b = c;else {
          if (b === a) break;
          for (; null === b.sibling;) {
            if (null === b.return || b.return === a) return !0;
            b = b.return;
          }
          b.sibling.return = b.return;
          b = b.sibling;
        }
      }
      return !0;
    }
    function kb(a, b) {
      b &= ~Sf;
      b &= ~Md;
      a.suspendedLanes |= b;
      a.pingedLanes &= ~b;
      for (a = a.expirationTimes; 0 < b;) {
        var c = 31 - ta(b),
          d = 1 << c;
        a[c] = -1;
        b &= ~d;
      }
    }
    function Li(a) {
      if (0 !== (p & 6)) throw Error(m(327));
      Xb();
      var b = Vc(a, 0);
      if (0 === (b & 1)) return ia(a, P()), null;
      var c = Nd(a, b);
      if (0 !== a.tag && 2 === c) {
        var d = ve(a);
        0 !== d && (b = d, c = Qf(a, d));
      }
      if (1 === c) throw c = Jc, wb(a, 0), kb(a, b), ia(a, P()), c;
      if (6 === c) throw Error(m(345));
      a.finishedWork = a.current.alternate;
      a.finishedLanes = b;
      xb(a, ja, Ra);
      ia(a, P());
      return null;
    }
    function Tf(a, b) {
      var c = p;
      p |= 1;
      try {
        return a(b);
      } finally {
        p = c, 0 === p && (Hc(), md && db());
      }
    }
    function yb(a) {
      null !== lb && 0 === lb.tag && 0 === (p & 6) && Xb();
      var b = p;
      p |= 1;
      var c = ca.transition,
        d = z;
      try {
        if (ca.transition = null, z = 1, a) return a();
      } finally {
        z = d, ca.transition = c, p = b, 0 === (p & 6) && db();
      }
    }
    function wb(a, b) {
      a.finishedWork = null;
      a.finishedLanes = 0;
      var c = a.timeoutHandle;
      -1 !== c && (a.timeoutHandle = -1, Nk(c));
      if (null !== H) for (c = H.return; null !== c;) {
        var d = c;
        Ve(d);
        switch (d.tag) {
          case 1:
            d = d.type.childContextTypes;
            null !== d && void 0 !== d && (v(S), v(J));
            break;
          case 3:
            Tb();
            v(S);
            v(J);
            jf();
            break;
          case 5:
            hf(d);
            break;
          case 4:
            Tb();
            break;
          case 13:
            v(F);
            break;
          case 19:
            v(F);
            break;
          case 10:
            cf(d.type._context);
            break;
          case 22:
          case 23:
            ba = Ga.current, v(Ga);
        }
        c = c.return;
      }
      O = a;
      H = a = eb(a.current, null);
      U = ba = b;
      L = 0;
      Jc = null;
      Sf = Md = ra = 0;
      ja = Kc = null;
      if (null !== tb) {
        for (b = 0; b < tb.length; b++) if (c = tb[b], d = c.interleaved, null !== d) {
          c.interleaved = null;
          var e = d.next,
            f = c.pending;
          if (null !== f) {
            var g = f.next;
            f.next = e;
            d.next = g;
          }
          c.pending = d;
        }
        tb = null;
      }
      return a;
    }
    function Pi(a, b) {
      do {
        var c = H;
        try {
          af();
          yd.current = zd;
          if (Ad) {
            for (var d = C.memoizedState; null !== d;) {
              var e = d.queue;
              null !== e && (e.pending = null);
              d = d.next;
            }
            Ad = !1;
          }
          vb = 0;
          N = K = C = null;
          zc = !1;
          Ac = 0;
          Uf.current = null;
          if (null === c || null === c.return) {
            L = 1;
            Jc = b;
            H = null;
            break;
          }
          a: {
            var f = a,
              g = c.return,
              h = c,
              k = b;
            b = U;
            h.flags |= 32768;
            if (null !== k && "object" === typeof k && "function" === typeof k.then) {
              var n = k,
                l = h,
                p = l.tag;
              if (0 === (l.mode & 1) && (0 === p || 11 === p || 15 === p)) {
                var r = l.alternate;
                r ? (l.updateQueue = r.updateQueue, l.memoizedState = r.memoizedState, l.lanes = r.lanes) : (l.updateQueue = null, l.memoizedState = null);
              }
              var v = ji(g);
              if (null !== v) {
                v.flags &= -257;
                ki(v, g, h, f, b);
                v.mode & 1 && ii(f, n, b);
                b = v;
                k = n;
                var x = b.updateQueue;
                if (null === x) {
                  var z = new Set();
                  z.add(k);
                  b.updateQueue = z;
                } else x.add(k);
                break a;
              } else {
                if (0 === (b & 1)) {
                  ii(f, n, b);
                  Ef();
                  break a;
                }
                k = Error(m(426));
              }
            } else if (D && h.mode & 1) {
              var y = ji(g);
              if (null !== y) {
                0 === (y.flags & 65536) && (y.flags |= 256);
                ki(y, g, h, f, b);
                Ye(Ub(k, h));
                break a;
              }
            }
            f = k = Ub(k, h);
            4 !== L && (L = 2);
            null === Kc ? Kc = [f] : Kc.push(f);
            f = g;
            do {
              switch (f.tag) {
                case 3:
                  f.flags |= 65536;
                  b &= -b;
                  f.lanes |= b;
                  var w = gi(f, k, b);
                  Gh(f, w);
                  break a;
                case 1:
                  h = k;
                  var A = f.type,
                    t = f.stateNode;
                  if (0 === (f.flags & 128) && ("function" === typeof A.getDerivedStateFromError || null !== t && "function" === typeof t.componentDidCatch && (null === ib || !ib.has(t)))) {
                    f.flags |= 65536;
                    b &= -b;
                    f.lanes |= b;
                    var B = hi(f, h, b);
                    Gh(f, B);
                    break a;
                  }
              }
              f = f.return;
            } while (null !== f);
          }
          Qi(c);
        } catch (ma) {
          b = ma;
          H === c && null !== c && (H = c = c.return);
          continue;
        }
        break;
      } while (1);
    }
    function Oi() {
      var a = Od.current;
      Od.current = zd;
      return null === a ? zd : a;
    }
    function Ef() {
      if (0 === L || 3 === L || 2 === L) L = 4;
      null === O || 0 === (ra & 268435455) && 0 === (Md & 268435455) || kb(O, U);
    }
    function Nd(a, b) {
      var c = p;
      p |= 2;
      var d = Oi();
      if (O !== a || U !== b) Ra = null, wb(a, b);
      do try {
        Ok();
        break;
      } catch (e) {
        Pi(a, e);
      } while (1);
      af();
      p = c;
      Od.current = d;
      if (null !== H) throw Error(m(261));
      O = null;
      U = 0;
      return L;
    }
    function Ok() {
      for (; null !== H;) Ri(H);
    }
    function Kk() {
      for (; null !== H && !Pk();) Ri(H);
    }
    function Ri(a) {
      var b = Qk(a.alternate, a, ba);
      a.memoizedProps = a.pendingProps;
      null === b ? Qi(a) : H = b;
      Uf.current = null;
    }
    function Qi(a) {
      var b = a;
      do {
        var c = b.alternate;
        a = b.return;
        if (0 === (b.flags & 32768)) {
          if (c = xk(c, b, ba), null !== c) {
            H = c;
            return;
          }
        } else {
          c = Bk(c, b);
          if (null !== c) {
            c.flags &= 32767;
            H = c;
            return;
          }
          if (null !== a) a.flags |= 32768, a.subtreeFlags = 0, a.deletions = null;else {
            L = 6;
            H = null;
            return;
          }
        }
        b = b.sibling;
        if (null !== b) {
          H = b;
          return;
        }
        H = b = a;
      } while (null !== b);
      0 === L && (L = 5);
    }
    function xb(a, b, c) {
      var d = z,
        e = ca.transition;
      try {
        ca.transition = null, z = 1, Rk(a, b, c, d);
      } finally {
        ca.transition = e, z = d;
      }
      return null;
    }
    function Rk(a, b, c, d) {
      do Xb(); while (null !== lb);
      if (0 !== (p & 6)) throw Error(m(327));
      c = a.finishedWork;
      var e = a.finishedLanes;
      if (null === c) return null;
      a.finishedWork = null;
      a.finishedLanes = 0;
      if (c === a.current) throw Error(m(177));
      a.callbackNode = null;
      a.callbackPriority = 0;
      var f = c.lanes | c.childLanes;
      uj(a, f);
      a === O && (H = O = null, U = 0);
      0 === (c.subtreeFlags & 2064) && 0 === (c.flags & 2064) || Pd || (Pd = !0, Mi(ad, function () {
        Xb();
        return null;
      }));
      f = 0 !== (c.flags & 15990);
      if (0 !== (c.subtreeFlags & 15990) || f) {
        f = ca.transition;
        ca.transition = null;
        var g = z;
        z = 1;
        var h = p;
        p |= 4;
        Uf.current = null;
        Ck(a, c);
        Fi(c, a);
        Tj(Kf);
        Zc = !!Jf;
        Kf = Jf = null;
        a.current = c;
        Hk(c, a, e);
        Sk();
        p = h;
        z = g;
        ca.transition = f;
      } else a.current = c;
      Pd && (Pd = !1, lb = a, Qd = e);
      f = a.pendingLanes;
      0 === f && (ib = null);
      oj(c.stateNode, d);
      ia(a, P());
      if (null !== b) for (d = a.onRecoverableError, c = 0; c < b.length; c++) e = b[c], d(e.value, {
        componentStack: e.stack,
        digest: e.digest
      });
      if (Ed) throw Ed = !1, a = xf, xf = null, a;
      0 !== (Qd & 1) && 0 !== a.tag && Xb();
      f = a.pendingLanes;
      0 !== (f & 1) ? a === Pf ? Ic++ : (Ic = 0, Pf = a) : Ic = 0;
      db();
      return null;
    }
    function Xb() {
      if (null !== lb) {
        var a = Eg(Qd),
          b = ca.transition,
          c = z;
        try {
          ca.transition = null;
          z = 16 > a ? 16 : a;
          if (null === lb) var d = !1;else {
            a = lb;
            lb = null;
            Qd = 0;
            if (0 !== (p & 6)) throw Error(m(331));
            var e = p;
            p |= 4;
            for (l = a.current; null !== l;) {
              var f = l,
                g = f.child;
              if (0 !== (l.flags & 16)) {
                var h = f.deletions;
                if (null !== h) {
                  for (var k = 0; k < h.length; k++) {
                    var n = h[k];
                    for (l = n; null !== l;) {
                      var q = l;
                      switch (q.tag) {
                        case 0:
                        case 11:
                        case 15:
                          Gc(8, q, f);
                      }
                      var u = q.child;
                      if (null !== u) u.return = q, l = u;else for (; null !== l;) {
                        q = l;
                        var r = q.sibling,
                          v = q.return;
                        Ai(q);
                        if (q === n) {
                          l = null;
                          break;
                        }
                        if (null !== r) {
                          r.return = v;
                          l = r;
                          break;
                        }
                        l = v;
                      }
                    }
                  }
                  var x = f.alternate;
                  if (null !== x) {
                    var y = x.child;
                    if (null !== y) {
                      x.child = null;
                      do {
                        var C = y.sibling;
                        y.sibling = null;
                        y = C;
                      } while (null !== y);
                    }
                  }
                  l = f;
                }
              }
              if (0 !== (f.subtreeFlags & 2064) && null !== g) g.return = f, l = g;else b: for (; null !== l;) {
                f = l;
                if (0 !== (f.flags & 2048)) switch (f.tag) {
                  case 0:
                  case 11:
                  case 15:
                    Gc(9, f, f.return);
                }
                var w = f.sibling;
                if (null !== w) {
                  w.return = f.return;
                  l = w;
                  break b;
                }
                l = f.return;
              }
            }
            var A = a.current;
            for (l = A; null !== l;) {
              g = l;
              var t = g.child;
              if (0 !== (g.subtreeFlags & 2064) && null !== t) t.return = g, l = t;else b: for (g = A; null !== l;) {
                h = l;
                if (0 !== (h.flags & 2048)) try {
                  switch (h.tag) {
                    case 0:
                    case 11:
                    case 15:
                      Id(9, h);
                  }
                } catch (ma) {
                  G(h, h.return, ma);
                }
                if (h === g) {
                  l = null;
                  break b;
                }
                var B = h.sibling;
                if (null !== B) {
                  B.return = h.return;
                  l = B;
                  break b;
                }
                l = h.return;
              }
            }
            p = e;
            db();
            if (Ca && "function" === typeof Ca.onPostCommitFiberRoot) try {
              Ca.onPostCommitFiberRoot(Uc, a);
            } catch (ma) {}
            d = !0;
          }
          return d;
        } finally {
          z = c, ca.transition = b;
        }
      }
      return !1;
    }
    function Si(a, b, c) {
      b = Ub(c, b);
      b = gi(a, b, 1);
      a = fb(a, b, 1);
      b = Z();
      null !== a && (ic(a, 1, b), ia(a, b));
    }
    function G(a, b, c) {
      if (3 === a.tag) Si(a, a, c);else for (; null !== b;) {
        if (3 === b.tag) {
          Si(b, a, c);
          break;
        } else if (1 === b.tag) {
          var d = b.stateNode;
          if ("function" === typeof b.type.getDerivedStateFromError || "function" === typeof d.componentDidCatch && (null === ib || !ib.has(d))) {
            a = Ub(c, a);
            a = hi(b, a, 1);
            b = fb(b, a, 1);
            a = Z();
            null !== b && (ic(b, 1, a), ia(b, a));
            break;
          }
        }
        b = b.return;
      }
    }
    function sk(a, b, c) {
      var d = a.pingCache;
      null !== d && d.delete(b);
      b = Z();
      a.pingedLanes |= a.suspendedLanes & c;
      O === a && (U & c) === c && (4 === L || 3 === L && (U & 130023424) === U && 500 > P() - Of ? wb(a, 0) : Sf |= c);
      ia(a, b);
    }
    function Ti(a, b) {
      0 === b && (0 === (a.mode & 1) ? b = 1 : (b = Rd, Rd <<= 1, 0 === (Rd & 130023424) && (Rd = 4194304)));
      var c = Z();
      a = Oa(a, b);
      null !== a && (ic(a, b, c), ia(a, c));
    }
    function vk(a) {
      var b = a.memoizedState,
        c = 0;
      null !== b && (c = b.retryLane);
      Ti(a, c);
    }
    function Gk(a, b) {
      var c = 0;
      switch (a.tag) {
        case 13:
          var d = a.stateNode;
          var e = a.memoizedState;
          null !== e && (c = e.retryLane);
          break;
        case 19:
          d = a.stateNode;
          break;
        default:
          throw Error(m(314));
      }
      null !== d && d.delete(b);
      Ti(a, c);
    }
    function Mi(a, b) {
      return xh(a, b);
    }
    function Tk(a, b, c, d) {
      this.tag = a;
      this.key = c;
      this.sibling = this.child = this.return = this.stateNode = this.type = this.elementType = null;
      this.index = 0;
      this.ref = null;
      this.pendingProps = b;
      this.dependencies = this.memoizedState = this.updateQueue = this.memoizedProps = null;
      this.mode = d;
      this.subtreeFlags = this.flags = 0;
      this.deletions = null;
      this.childLanes = this.lanes = 0;
      this.alternate = null;
    }
    function yf(a) {
      a = a.prototype;
      return !(!a || !a.isReactComponent);
    }
    function Uk(a) {
      if ("function" === typeof a) return yf(a) ? 1 : 0;
      if (void 0 !== a && null !== a) {
        a = a.$$typeof;
        if (a === ie) return 11;
        if (a === je) return 14;
      }
      return 2;
    }
    function eb(a, b) {
      var c = a.alternate;
      null === c ? (c = pa(a.tag, b, a.key, a.mode), c.elementType = a.elementType, c.type = a.type, c.stateNode = a.stateNode, c.alternate = a, a.alternate = c) : (c.pendingProps = b, c.type = a.type, c.flags = 0, c.subtreeFlags = 0, c.deletions = null);
      c.flags = a.flags & 14680064;
      c.childLanes = a.childLanes;
      c.lanes = a.lanes;
      c.child = a.child;
      c.memoizedProps = a.memoizedProps;
      c.memoizedState = a.memoizedState;
      c.updateQueue = a.updateQueue;
      b = a.dependencies;
      c.dependencies = null === b ? null : {
        lanes: b.lanes,
        firstContext: b.firstContext
      };
      c.sibling = a.sibling;
      c.index = a.index;
      c.ref = a.ref;
      return c;
    }
    function rd(a, b, c, d, e, f) {
      var g = 2;
      d = a;
      if ("function" === typeof a) yf(a) && (g = 1);else if ("string" === typeof a) g = 5;else a: switch (a) {
        case Bb:
          return sb(c.children, e, f, b);
        case fe:
          g = 8;
          e |= 8;
          break;
        case ee:
          return a = pa(12, c, b, e | 2), a.elementType = ee, a.lanes = f, a;
        case ge:
          return a = pa(13, c, b, e), a.elementType = ge, a.lanes = f, a;
        case he:
          return a = pa(19, c, b, e), a.elementType = he, a.lanes = f, a;
        case Ui:
          return Gd(c, e, f, b);
        default:
          if ("object" === typeof a && null !== a) switch (a.$$typeof) {
            case hg:
              g = 10;
              break a;
            case gg:
              g = 9;
              break a;
            case ie:
              g = 11;
              break a;
            case je:
              g = 14;
              break a;
            case Ta:
              g = 16;
              d = null;
              break a;
          }
          throw Error(m(130, null == a ? a : typeof a, ""));
      }
      b = pa(g, c, b, e);
      b.elementType = a;
      b.type = d;
      b.lanes = f;
      return b;
    }
    function sb(a, b, c, d) {
      a = pa(7, a, d, b);
      a.lanes = c;
      return a;
    }
    function Gd(a, b, c, d) {
      a = pa(22, a, d, b);
      a.elementType = Ui;
      a.lanes = c;
      a.stateNode = {
        isHidden: !1
      };
      return a;
    }
    function Ze(a, b, c) {
      a = pa(6, a, null, b);
      a.lanes = c;
      return a;
    }
    function $e(a, b, c) {
      b = pa(4, null !== a.children ? a.children : [], a.key, b);
      b.lanes = c;
      b.stateNode = {
        containerInfo: a.containerInfo,
        pendingChildren: null,
        implementation: a.implementation
      };
      return b;
    }
    function Vk(a, b, c, d, e) {
      this.tag = b;
      this.containerInfo = a;
      this.finishedWork = this.pingCache = this.current = this.pendingChildren = null;
      this.timeoutHandle = -1;
      this.callbackNode = this.pendingContext = this.context = null;
      this.callbackPriority = 0;
      this.eventTimes = we(0);
      this.expirationTimes = we(-1);
      this.entangledLanes = this.finishedLanes = this.mutableReadLanes = this.expiredLanes = this.pingedLanes = this.suspendedLanes = this.pendingLanes = 0;
      this.entanglements = we(0);
      this.identifierPrefix = d;
      this.onRecoverableError = e;
      this.mutableSourceEagerHydrationData = null;
    }
    function Vf(a, b, c, d, e, f, g, h, k, l) {
      a = new Vk(a, b, c, h, k);
      1 === b ? (b = 1, !0 === f && (b |= 8)) : b = 0;
      f = pa(3, null, null, b);
      a.current = f;
      f.stateNode = a;
      f.memoizedState = {
        element: d,
        isDehydrated: c,
        cache: null,
        transitions: null,
        pendingSuspenseBoundaries: null
      };
      ff(f);
      return a;
    }
    function Wk(a, b, c) {
      var d = 3 < arguments.length && void 0 !== arguments[3] ? arguments[3] : null;
      return {
        $$typeof: Cb,
        key: null == d ? null : "" + d,
        children: a,
        containerInfo: b,
        implementation: c
      };
    }
    function Vi(a) {
      if (!a) return cb;
      a = a._reactInternals;
      a: {
        if (nb(a) !== a || 1 !== a.tag) throw Error(m(170));
        var b = a;
        do {
          switch (b.tag) {
            case 3:
              b = b.stateNode.context;
              break a;
            case 1:
              if (ea(b.type)) {
                b = b.stateNode.__reactInternalMemoizedMergedChildContext;
                break a;
              }
          }
          b = b.return;
        } while (null !== b);
        throw Error(m(171));
      }
      if (1 === a.tag) {
        var c = a.type;
        if (ea(c)) return uh(a, c, b);
      }
      return b;
    }
    function Wi(a, b, c, d, e, f, g, h, k, l) {
      a = Vf(c, d, !0, a, e, f, g, h, k);
      a.context = Vi(null);
      c = a.current;
      d = Z();
      e = hb(c);
      f = Pa(d, e);
      f.callback = void 0 !== b && null !== b ? b : null;
      fb(c, f, e);
      a.current.lanes = e;
      ic(a, e, d);
      ia(a, d);
      return a;
    }
    function Sd(a, b, c, d) {
      var e = b.current,
        f = Z(),
        g = hb(e);
      c = Vi(c);
      null === b.context ? b.context = c : b.pendingContext = c;
      b = Pa(f, g);
      b.payload = {
        element: a
      };
      d = void 0 === d ? null : d;
      null !== d && (b.callback = d);
      a = fb(e, b, g);
      null !== a && (xa(a, e, g, f), vd(a, e, g));
      return g;
    }
    function Td(a) {
      a = a.current;
      if (!a.child) return null;
      switch (a.child.tag) {
        case 5:
          return a.child.stateNode;
        default:
          return a.child.stateNode;
      }
    }
    function Xi(a, b) {
      a = a.memoizedState;
      if (null !== a && null !== a.dehydrated) {
        var c = a.retryLane;
        a.retryLane = 0 !== c && c < b ? c : b;
      }
    }
    function Wf(a, b) {
      Xi(a, b);
      (a = a.alternate) && Xi(a, b);
    }
    function Xk(a) {
      a = Bg(a);
      return null === a ? null : a.stateNode;
    }
    function Yk(a) {
      return null;
    }
    function Xf(a) {
      this._internalRoot = a;
    }
    function Ud(a) {
      this._internalRoot = a;
    }
    function Yf(a) {
      return !(!a || 1 !== a.nodeType && 9 !== a.nodeType && 11 !== a.nodeType);
    }
    function Vd(a) {
      return !(!a || 1 !== a.nodeType && 9 !== a.nodeType && 11 !== a.nodeType && (8 !== a.nodeType || " react-mount-point-unstable " !== a.nodeValue));
    }
    function Yi() {}
    function Zk(a, b, c, d, e) {
      if (e) {
        if ("function" === typeof d) {
          var f = d;
          d = function () {
            var a = Td(g);
            f.call(a);
          };
        }
        var g = Wi(b, d, a, 0, null, !1, !1, "", Yi);
        a._reactRootContainer = g;
        a[Ja] = g.current;
        sc(8 === a.nodeType ? a.parentNode : a);
        yb();
        return g;
      }
      for (; e = a.lastChild;) a.removeChild(e);
      if ("function" === typeof d) {
        var h = d;
        d = function () {
          var a = Td(k);
          h.call(a);
        };
      }
      var k = Vf(a, 0, !1, null, null, !1, !1, "", Yi);
      a._reactRootContainer = k;
      a[Ja] = k.current;
      sc(8 === a.nodeType ? a.parentNode : a);
      yb(function () {
        Sd(b, k, c, d);
      });
      return k;
    }
    function Wd(a, b, c, d, e) {
      var f = c._reactRootContainer;
      if (f) {
        var g = f;
        if ("function" === typeof e) {
          var h = e;
          e = function () {
            var a = Td(g);
            h.call(a);
          };
        }
        Sd(b, g, a, e);
      } else g = Zk(c, b, a, e, d);
      return Td(g);
    }
    var cg = new Set(),
      $b = {},
      Ia = !("undefined" === typeof window || "undefined" === typeof window.document || "undefined" === typeof window.document.createElement),
      Zd = Object.prototype.hasOwnProperty,
      cj = /^[:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD][:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\-.0-9\u00B7\u0300-\u036F\u203F-\u2040]*$/,
      eg = {},
      dg = {},
      R = {};
    "children dangerouslySetInnerHTML defaultValue defaultChecked innerHTML suppressContentEditableWarning suppressHydrationWarning style".split(" ").forEach(function (a) {
      R[a] = new Y(a, 0, !1, a, null, !1, !1);
    });
    [["acceptCharset", "accept-charset"], ["className", "class"], ["htmlFor", "for"], ["httpEquiv", "http-equiv"]].forEach(function (a) {
      var b = a[0];
      R[b] = new Y(b, 1, !1, a[1], null, !1, !1);
    });
    ["contentEditable", "draggable", "spellCheck", "value"].forEach(function (a) {
      R[a] = new Y(a, 2, !1, a.toLowerCase(), null, !1, !1);
    });
    ["autoReverse", "externalResourcesRequired", "focusable", "preserveAlpha"].forEach(function (a) {
      R[a] = new Y(a, 2, !1, a, null, !1, !1);
    });
    "allowFullScreen async autoFocus autoPlay controls default defer disabled disablePictureInPicture disableRemotePlayback formNoValidate hidden loop noModule noValidate open playsInline readOnly required reversed scoped seamless itemScope".split(" ").forEach(function (a) {
      R[a] = new Y(a, 3, !1, a.toLowerCase(), null, !1, !1);
    });
    ["checked", "multiple", "muted", "selected"].forEach(function (a) {
      R[a] = new Y(a, 3, !0, a, null, !1, !1);
    });
    ["capture", "download"].forEach(function (a) {
      R[a] = new Y(a, 4, !1, a, null, !1, !1);
    });
    ["cols", "rows", "size", "span"].forEach(function (a) {
      R[a] = new Y(a, 6, !1, a, null, !1, !1);
    });
    ["rowSpan", "start"].forEach(function (a) {
      R[a] = new Y(a, 5, !1, a.toLowerCase(), null, !1, !1);
    });
    var Zf = /[\-:]([a-z])/g,
      $f = function (a) {
        return a[1].toUpperCase();
      };
    "accent-height alignment-baseline arabic-form baseline-shift cap-height clip-path clip-rule color-interpolation color-interpolation-filters color-profile color-rendering dominant-baseline enable-background fill-opacity fill-rule flood-color flood-opacity font-family font-size font-size-adjust font-stretch font-style font-variant font-weight glyph-name glyph-orientation-horizontal glyph-orientation-vertical horiz-adv-x horiz-origin-x image-rendering letter-spacing lighting-color marker-end marker-mid marker-start overline-position overline-thickness paint-order panose-1 pointer-events rendering-intent shape-rendering stop-color stop-opacity strikethrough-position strikethrough-thickness stroke-dasharray stroke-dashoffset stroke-linecap stroke-linejoin stroke-miterlimit stroke-opacity stroke-width text-anchor text-decoration text-rendering underline-position underline-thickness unicode-bidi unicode-range units-per-em v-alphabetic v-hanging v-ideographic v-mathematical vector-effect vert-adv-y vert-origin-x vert-origin-y word-spacing writing-mode xmlns:xlink x-height".split(" ").forEach(function (a) {
      var b = a.replace(Zf, $f);
      R[b] = new Y(b, 1, !1, a, null, !1, !1);
    });
    "xlink:actuate xlink:arcrole xlink:role xlink:show xlink:title xlink:type".split(" ").forEach(function (a) {
      var b = a.replace(Zf, $f);
      R[b] = new Y(b, 1, !1, a, "http://www.w3.org/1999/xlink", !1, !1);
    });
    ["xml:base", "xml:lang", "xml:space"].forEach(function (a) {
      var b = a.replace(Zf, $f);
      R[b] = new Y(b, 1, !1, a, "http://www.w3.org/XML/1998/namespace", !1, !1);
    });
    ["tabIndex", "crossOrigin"].forEach(function (a) {
      R[a] = new Y(a, 1, !1, a.toLowerCase(), null, !1, !1);
    });
    R.xlinkHref = new Y("xlinkHref", 1, !1, "xlink:href", "http://www.w3.org/1999/xlink", !0, !1);
    ["src", "href", "action", "formAction"].forEach(function (a) {
      R[a] = new Y(a, 1, !1, a.toLowerCase(), null, !0, !0);
    });
    var Sa = zb.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED,
      sd = Symbol.for("react.element"),
      Cb = Symbol.for("react.portal"),
      Bb = Symbol.for("react.fragment"),
      fe = Symbol.for("react.strict_mode"),
      ee = Symbol.for("react.profiler"),
      hg = Symbol.for("react.provider"),
      gg = Symbol.for("react.context"),
      ie = Symbol.for("react.forward_ref"),
      ge = Symbol.for("react.suspense"),
      he = Symbol.for("react.suspense_list"),
      je = Symbol.for("react.memo"),
      Ta = Symbol.for("react.lazy");
    Symbol.for("react.scope");
    Symbol.for("react.debug_trace_mode");
    var Ui = Symbol.for("react.offscreen");
    Symbol.for("react.legacy_hidden");
    Symbol.for("react.cache");
    Symbol.for("react.tracing_marker");
    var fg = Symbol.iterator,
      E = Object.assign,
      ae,
      ce = !1,
      cc = Array.isArray,
      Xd,
      yi = function (a) {
        return "undefined" !== typeof MSApp && MSApp.execUnsafeLocalFunction ? function (b, c, d, e) {
          MSApp.execUnsafeLocalFunction(function () {
            return a(b, c, d, e);
          });
        } : a;
      }(function (a, b) {
        if ("http://www.w3.org/2000/svg" !== a.namespaceURI || "innerHTML" in a) a.innerHTML = b;else {
          Xd = Xd || document.createElement("div");
          Xd.innerHTML = "<svg>" + b.valueOf().toString() + "</svg>";
          for (b = Xd.firstChild; a.firstChild;) a.removeChild(a.firstChild);
          for (; b.firstChild;) a.appendChild(b.firstChild);
        }
      }),
      Fc = function (a, b) {
        if (b) {
          var c = a.firstChild;
          if (c && c === a.lastChild && 3 === c.nodeType) {
            c.nodeValue = b;
            return;
          }
        }
        a.textContent = b;
      },
      dc = {
        animationIterationCount: !0,
        aspectRatio: !0,
        borderImageOutset: !0,
        borderImageSlice: !0,
        borderImageWidth: !0,
        boxFlex: !0,
        boxFlexGroup: !0,
        boxOrdinalGroup: !0,
        columnCount: !0,
        columns: !0,
        flex: !0,
        flexGrow: !0,
        flexPositive: !0,
        flexShrink: !0,
        flexNegative: !0,
        flexOrder: !0,
        gridArea: !0,
        gridRow: !0,
        gridRowEnd: !0,
        gridRowSpan: !0,
        gridRowStart: !0,
        gridColumn: !0,
        gridColumnEnd: !0,
        gridColumnSpan: !0,
        gridColumnStart: !0,
        fontWeight: !0,
        lineClamp: !0,
        lineHeight: !0,
        opacity: !0,
        order: !0,
        orphans: !0,
        tabSize: !0,
        widows: !0,
        zIndex: !0,
        zoom: !0,
        fillOpacity: !0,
        floodOpacity: !0,
        stopOpacity: !0,
        strokeDasharray: !0,
        strokeDashoffset: !0,
        strokeMiterlimit: !0,
        strokeOpacity: !0,
        strokeWidth: !0
      },
      $k = ["Webkit", "ms", "Moz", "O"];
    Object.keys(dc).forEach(function (a) {
      $k.forEach(function (b) {
        b = b + a.charAt(0).toUpperCase() + a.substring(1);
        dc[b] = dc[a];
      });
    });
    var ij = E({
        menuitem: !0
      }, {
        area: !0,
        base: !0,
        br: !0,
        col: !0,
        embed: !0,
        hr: !0,
        img: !0,
        input: !0,
        keygen: !0,
        link: !0,
        meta: !0,
        param: !0,
        source: !0,
        track: !0,
        wbr: !0
      }),
      ze = null,
      se = null,
      Eb = null,
      Fb = null,
      xg = function (a, b) {
        return a(b);
      },
      yg = function () {},
      te = !1,
      Oe = !1;
    if (Ia) try {
      var Lc = {};
      Object.defineProperty(Lc, "passive", {
        get: function () {
          Oe = !0;
        }
      });
      window.addEventListener("test", Lc, Lc);
      window.removeEventListener("test", Lc, Lc);
    } catch (a) {
      Oe = !1;
    }
    var kj = function (a, b, c, d, e, f, g, h, k) {
        var l = Array.prototype.slice.call(arguments, 3);
        try {
          b.apply(c, l);
        } catch (q) {
          this.onError(q);
        }
      },
      gc = !1,
      Sc = null,
      Tc = !1,
      ue = null,
      lj = {
        onError: function (a) {
          gc = !0;
          Sc = a;
        }
      },
      Ba = zb.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.Scheduler,
      Jg = Ba.unstable_scheduleCallback,
      Kg = Ba.unstable_NormalPriority,
      xh = Jg,
      Ki = Ba.unstable_cancelCallback,
      Pk = Ba.unstable_shouldYield,
      Sk = Ba.unstable_requestPaint,
      P = Ba.unstable_now,
      Dj = Ba.unstable_getCurrentPriorityLevel,
      De = Ba.unstable_ImmediatePriority,
      Mg = Ba.unstable_UserBlockingPriority,
      ad = Kg,
      Ej = Ba.unstable_LowPriority,
      Ng = Ba.unstable_IdlePriority,
      Uc = null,
      Ca = null,
      ta = Math.clz32 ? Math.clz32 : pj,
      qj = Math.log,
      rj = Math.LN2,
      Wc = 64,
      Rd = 4194304,
      z = 0,
      Ae = !1,
      Yc = [],
      Va = null,
      Wa = null,
      Xa = null,
      jc = new Map(),
      kc = new Map(),
      Ya = [],
      Bj = "mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset submit".split(" "),
      Gb = Sa.ReactCurrentBatchConfig,
      Zc = !0,
      $c = null,
      Za = null,
      Ee = null,
      bd = null,
      Yb = {
        eventPhase: 0,
        bubbles: 0,
        cancelable: 0,
        timeStamp: function (a) {
          return a.timeStamp || Date.now();
        },
        defaultPrevented: 0,
        isTrusted: 0
      },
      He = ka(Yb),
      Mc = E({}, Yb, {
        view: 0,
        detail: 0
      }),
      ak = ka(Mc),
      ag,
      bg,
      Nc,
      Yd = E({}, Mc, {
        screenX: 0,
        screenY: 0,
        clientX: 0,
        clientY: 0,
        pageX: 0,
        pageY: 0,
        ctrlKey: 0,
        shiftKey: 0,
        altKey: 0,
        metaKey: 0,
        getModifierState: Fe,
        button: 0,
        buttons: 0,
        relatedTarget: function (a) {
          return void 0 === a.relatedTarget ? a.fromElement === a.srcElement ? a.toElement : a.fromElement : a.relatedTarget;
        },
        movementX: function (a) {
          if ("movementX" in a) return a.movementX;
          a !== Nc && (Nc && "mousemove" === a.type ? (ag = a.screenX - Nc.screenX, bg = a.screenY - Nc.screenY) : bg = ag = 0, Nc = a);
          return ag;
        },
        movementY: function (a) {
          return "movementY" in a ? a.movementY : bg;
        }
      }),
      ih = ka(Yd),
      al = E({}, Yd, {
        dataTransfer: 0
      }),
      Wj = ka(al),
      bl = E({}, Mc, {
        relatedTarget: 0
      }),
      Pe = ka(bl),
      cl = E({}, Yb, {
        animationName: 0,
        elapsedTime: 0,
        pseudoElement: 0
      }),
      Yj = ka(cl),
      dl = E({}, Yb, {
        clipboardData: function (a) {
          return "clipboardData" in a ? a.clipboardData : window.clipboardData;
        }
      }),
      ck = ka(dl),
      el = E({}, Yb, {
        data: 0
      }),
      qh = ka(el),
      fk = qh,
      fl = {
        Esc: "Escape",
        Spacebar: " ",
        Left: "ArrowLeft",
        Up: "ArrowUp",
        Right: "ArrowRight",
        Down: "ArrowDown",
        Del: "Delete",
        Win: "OS",
        Menu: "ContextMenu",
        Apps: "ContextMenu",
        Scroll: "ScrollLock",
        MozPrintableKey: "Unidentified"
      },
      gl = {
        8: "Backspace",
        9: "Tab",
        12: "Clear",
        13: "Enter",
        16: "Shift",
        17: "Control",
        18: "Alt",
        19: "Pause",
        20: "CapsLock",
        27: "Escape",
        32: " ",
        33: "PageUp",
        34: "PageDown",
        35: "End",
        36: "Home",
        37: "ArrowLeft",
        38: "ArrowUp",
        39: "ArrowRight",
        40: "ArrowDown",
        45: "Insert",
        46: "Delete",
        112: "F1",
        113: "F2",
        114: "F3",
        115: "F4",
        116: "F5",
        117: "F6",
        118: "F7",
        119: "F8",
        120: "F9",
        121: "F10",
        122: "F11",
        123: "F12",
        144: "NumLock",
        145: "ScrollLock",
        224: "Meta"
      },
      Gj = {
        Alt: "altKey",
        Control: "ctrlKey",
        Meta: "metaKey",
        Shift: "shiftKey"
      },
      hl = E({}, Mc, {
        key: function (a) {
          if (a.key) {
            var b = fl[a.key] || a.key;
            if ("Unidentified" !== b) return b;
          }
          return "keypress" === a.type ? (a = cd(a), 13 === a ? "Enter" : String.fromCharCode(a)) : "keydown" === a.type || "keyup" === a.type ? gl[a.keyCode] || "Unidentified" : "";
        },
        code: 0,
        location: 0,
        ctrlKey: 0,
        shiftKey: 0,
        altKey: 0,
        metaKey: 0,
        repeat: 0,
        locale: 0,
        getModifierState: Fe,
        charCode: function (a) {
          return "keypress" === a.type ? cd(a) : 0;
        },
        keyCode: function (a) {
          return "keydown" === a.type || "keyup" === a.type ? a.keyCode : 0;
        },
        which: function (a) {
          return "keypress" === a.type ? cd(a) : "keydown" === a.type || "keyup" === a.type ? a.keyCode : 0;
        }
      }),
      Vj = ka(hl),
      il = E({}, Yd, {
        pointerId: 0,
        width: 0,
        height: 0,
        pressure: 0,
        tangentialPressure: 0,
        tiltX: 0,
        tiltY: 0,
        twist: 0,
        pointerType: 0,
        isPrimary: 0
      }),
      nh = ka(il),
      jl = E({}, Mc, {
        touches: 0,
        targetTouches: 0,
        changedTouches: 0,
        altKey: 0,
        metaKey: 0,
        ctrlKey: 0,
        shiftKey: 0,
        getModifierState: Fe
      }),
      Xj = ka(jl),
      kl = E({}, Yb, {
        propertyName: 0,
        elapsedTime: 0,
        pseudoElement: 0
      }),
      Zj = ka(kl),
      ll = E({}, Yd, {
        deltaX: function (a) {
          return "deltaX" in a ? a.deltaX : "wheelDeltaX" in a ? -a.wheelDeltaX : 0;
        },
        deltaY: function (a) {
          return "deltaY" in a ? a.deltaY : "wheelDeltaY" in a ? -a.wheelDeltaY : "wheelDelta" in a ? -a.wheelDelta : 0;
        },
        deltaZ: 0,
        deltaMode: 0
      }),
      bk = ka(ll),
      Hj = [9, 13, 27, 32],
      Ge = Ia && "CompositionEvent" in window,
      Oc = null;
    Ia && "documentMode" in document && (Oc = document.documentMode);
    var ek = Ia && "TextEvent" in window && !Oc,
      Ug = Ia && (!Ge || Oc && 8 < Oc && 11 >= Oc),
      Tg = String.fromCharCode(32),
      Sg = !1,
      Hb = !1,
      Kj = {
        color: !0,
        date: !0,
        datetime: !0,
        "datetime-local": !0,
        email: !0,
        month: !0,
        number: !0,
        password: !0,
        range: !0,
        search: !0,
        tel: !0,
        text: !0,
        time: !0,
        url: !0,
        week: !0
      },
      oc = null,
      pc = null,
      ph = !1;
    Ia && (ph = Lj("input") && (!document.documentMode || 9 < document.documentMode));
    var ua = "function" === typeof Object.is ? Object.is : Sj,
      dk = Ia && "documentMode" in document && 11 >= document.documentMode,
      Jb = null,
      Ke = null,
      rc = null,
      Je = !1,
      Kb = {
        animationend: gd("Animation", "AnimationEnd"),
        animationiteration: gd("Animation", "AnimationIteration"),
        animationstart: gd("Animation", "AnimationStart"),
        transitionend: gd("Transition", "TransitionEnd")
      },
      Le = {},
      eh = {};
    Ia && (eh = document.createElement("div").style, "AnimationEvent" in window || (delete Kb.animationend.animation, delete Kb.animationiteration.animation, delete Kb.animationstart.animation), "TransitionEvent" in window || delete Kb.transitionend.transition);
    var jh = hd("animationend"),
      kh = hd("animationiteration"),
      lh = hd("animationstart"),
      mh = hd("transitionend"),
      fh = new Map(),
      Zi = "abort auxClick cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(" ");
    (function () {
      for (var a = 0; a < Zi.length; a++) {
        var b = Zi[a],
          c = b.toLowerCase();
        b = b[0].toUpperCase() + b.slice(1);
        $a(c, "on" + b);
      }
      $a(jh, "onAnimationEnd");
      $a(kh, "onAnimationIteration");
      $a(lh, "onAnimationStart");
      $a("dblclick", "onDoubleClick");
      $a("focusin", "onFocus");
      $a("focusout", "onBlur");
      $a(mh, "onTransitionEnd");
    })();
    Ab("onMouseEnter", ["mouseout", "mouseover"]);
    Ab("onMouseLeave", ["mouseout", "mouseover"]);
    Ab("onPointerEnter", ["pointerout", "pointerover"]);
    Ab("onPointerLeave", ["pointerout", "pointerover"]);
    mb("onChange", "change click focusin focusout input keydown keyup selectionchange".split(" "));
    mb("onSelect", "focusout contextmenu dragend focusin keydown keyup mousedown mouseup selectionchange".split(" "));
    mb("onBeforeInput", ["compositionend", "keypress", "textInput", "paste"]);
    mb("onCompositionEnd", "compositionend focusout keydown keypress keyup mousedown".split(" "));
    mb("onCompositionStart", "compositionstart focusout keydown keypress keyup mousedown".split(" "));
    mb("onCompositionUpdate", "compositionupdate focusout keydown keypress keyup mousedown".split(" "));
    var Ec = "abort canplay canplaythrough durationchange emptied encrypted ended error loadeddata loadedmetadata loadstart pause play playing progress ratechange resize seeked seeking stalled suspend timeupdate volumechange waiting".split(" "),
      Uj = new Set("cancel close invalid load scroll toggle".split(" ").concat(Ec)),
      id = "_reactListening" + Math.random().toString(36).slice(2),
      gk = /\r\n?/g,
      hk = /\u0000|\uFFFD/g,
      Jf = null,
      Kf = null,
      Rf = "function" === typeof setTimeout ? setTimeout : void 0,
      Nk = "function" === typeof clearTimeout ? clearTimeout : void 0,
      $i = "function" === typeof Promise ? Promise : void 0,
      Jk = "function" === typeof queueMicrotask ? queueMicrotask : "undefined" !== typeof $i ? function (a) {
        return $i.resolve(null).then(a).catch(ik);
      } : Rf,
      Zb = Math.random().toString(36).slice(2),
      Da = "__reactFiber$" + Zb,
      uc = "__reactProps$" + Zb,
      Ja = "__reactContainer$" + Zb,
      Me = "__reactEvents$" + Zb,
      Dk = "__reactListeners$" + Zb,
      Ek = "__reactHandles$" + Zb,
      Se = [],
      Mb = -1,
      cb = {},
      J = bb(cb),
      S = bb(!1),
      pb = cb,
      La = null,
      md = !1,
      Te = !1,
      Ob = [],
      Pb = 0,
      od = null,
      nd = 0,
      na = [],
      oa = 0,
      rb = null,
      Ma = 1,
      Na = "",
      la = null,
      fa = null,
      D = !1,
      wa = null,
      Ik = Sa.ReactCurrentBatchConfig,
      Vb = Dh(!0),
      li = Dh(!1),
      ud = bb(null),
      td = null,
      Rb = null,
      bf = null,
      tb = null,
      kk = Oa,
      gb = !1,
      wc = {},
      Ea = bb(wc),
      yc = bb(wc),
      xc = bb(wc),
      F = bb(0),
      kf = [],
      yd = Sa.ReactCurrentDispatcher,
      sf = Sa.ReactCurrentBatchConfig,
      vb = 0,
      C = null,
      K = null,
      N = null,
      Ad = !1,
      zc = !1,
      Ac = 0,
      ml = 0,
      zd = {
        readContext: qa,
        useCallback: V,
        useContext: V,
        useEffect: V,
        useImperativeHandle: V,
        useInsertionEffect: V,
        useLayoutEffect: V,
        useMemo: V,
        useReducer: V,
        useRef: V,
        useState: V,
        useDebugValue: V,
        useDeferredValue: V,
        useTransition: V,
        useMutableSource: V,
        useSyncExternalStore: V,
        useId: V,
        unstable_isNewReconciler: !1
      },
      lk = {
        readContext: qa,
        useCallback: function (a, b) {
          Fa().memoizedState = [a, void 0 === b ? null : b];
          return a;
        },
        useContext: qa,
        useEffect: Sh,
        useImperativeHandle: function (a, b, c) {
          c = null !== c && void 0 !== c ? c.concat([a]) : null;
          return Bd(4194308, 4, Vh.bind(null, b, a), c);
        },
        useLayoutEffect: function (a, b) {
          return Bd(4194308, 4, a, b);
        },
        useInsertionEffect: function (a, b) {
          return Bd(4, 2, a, b);
        },
        useMemo: function (a, b) {
          var c = Fa();
          b = void 0 === b ? null : b;
          a = a();
          c.memoizedState = [a, b];
          return a;
        },
        useReducer: function (a, b, c) {
          var d = Fa();
          b = void 0 !== c ? c(b) : b;
          d.memoizedState = d.baseState = b;
          a = {
            pending: null,
            interleaved: null,
            lanes: 0,
            dispatch: null,
            lastRenderedReducer: a,
            lastRenderedState: b
          };
          d.queue = a;
          a = a.dispatch = qk.bind(null, C, a);
          return [d.memoizedState, a];
        },
        useRef: function (a) {
          var b = Fa();
          a = {
            current: a
          };
          return b.memoizedState = a;
        },
        useState: Qh,
        useDebugValue: rf,
        useDeferredValue: function (a) {
          return Fa().memoizedState = a;
        },
        useTransition: function () {
          var a = Qh(!1),
            b = a[0];
          a = pk.bind(null, a[1]);
          Fa().memoizedState = a;
          return [b, a];
        },
        useMutableSource: function (a, b, c) {},
        useSyncExternalStore: function (a, b, c) {
          var d = C,
            e = Fa();
          if (D) {
            if (void 0 === c) throw Error(m(407));
            c = c();
          } else {
            c = b();
            if (null === O) throw Error(m(349));
            0 !== (vb & 30) || Nh(d, b, c);
          }
          e.memoizedState = c;
          var f = {
            value: c,
            getSnapshot: b
          };
          e.queue = f;
          Sh(Lh.bind(null, d, f, a), [a]);
          d.flags |= 2048;
          Cc(9, Mh.bind(null, d, f, c, b), void 0, null);
          return c;
        },
        useId: function () {
          var a = Fa(),
            b = O.identifierPrefix;
          if (D) {
            var c = Na;
            var d = Ma;
            c = (d & ~(1 << 32 - ta(d) - 1)).toString(32) + c;
            b = ":" + b + "R" + c;
            c = Ac++;
            0 < c && (b += "H" + c.toString(32));
            b += ":";
          } else c = ml++, b = ":" + b + "r" + c.toString(32) + ":";
          return a.memoizedState = b;
        },
        unstable_isNewReconciler: !1
      },
      mk = {
        readContext: qa,
        useCallback: Xh,
        useContext: qa,
        useEffect: qf,
        useImperativeHandle: Wh,
        useInsertionEffect: Th,
        useLayoutEffect: Uh,
        useMemo: Yh,
        useReducer: of,
        useRef: Rh,
        useState: function (a) {
          return of(Bc);
        },
        useDebugValue: rf,
        useDeferredValue: function (a) {
          var b = sa();
          return Zh(b, K.memoizedState, a);
        },
        useTransition: function () {
          var a = of(Bc)[0],
            b = sa().memoizedState;
          return [a, b];
        },
        useMutableSource: Jh,
        useSyncExternalStore: Kh,
        useId: $h,
        unstable_isNewReconciler: !1
      },
      nk = {
        readContext: qa,
        useCallback: Xh,
        useContext: qa,
        useEffect: qf,
        useImperativeHandle: Wh,
        useInsertionEffect: Th,
        useLayoutEffect: Uh,
        useMemo: Yh,
        useReducer: pf,
        useRef: Rh,
        useState: function (a) {
          return pf(Bc);
        },
        useDebugValue: rf,
        useDeferredValue: function (a) {
          var b = sa();
          return null === K ? b.memoizedState = a : Zh(b, K.memoizedState, a);
        },
        useTransition: function () {
          var a = pf(Bc)[0],
            b = sa().memoizedState;
          return [a, b];
        },
        useMutableSource: Jh,
        useSyncExternalStore: Kh,
        useId: $h,
        unstable_isNewReconciler: !1
      },
      Dd = {
        isMounted: function (a) {
          return (a = a._reactInternals) ? nb(a) === a : !1;
        },
        enqueueSetState: function (a, b, c) {
          a = a._reactInternals;
          var d = Z(),
            e = hb(a),
            f = Pa(d, e);
          f.payload = b;
          void 0 !== c && null !== c && (f.callback = c);
          b = fb(a, f, e);
          null !== b && (xa(b, a, e, d), vd(b, a, e));
        },
        enqueueReplaceState: function (a, b, c) {
          a = a._reactInternals;
          var d = Z(),
            e = hb(a),
            f = Pa(d, e);
          f.tag = 1;
          f.payload = b;
          void 0 !== c && null !== c && (f.callback = c);
          b = fb(a, f, e);
          null !== b && (xa(b, a, e, d), vd(b, a, e));
        },
        enqueueForceUpdate: function (a, b) {
          a = a._reactInternals;
          var c = Z(),
            d = hb(a),
            e = Pa(c, d);
          e.tag = 2;
          void 0 !== b && null !== b && (e.callback = b);
          b = fb(a, e, d);
          null !== b && (xa(b, a, d, c), vd(b, a, d));
        }
      },
      rk = "function" === typeof WeakMap ? WeakMap : Map,
      tk = Sa.ReactCurrentOwner,
      ha = !1,
      Cf = {
        dehydrated: null,
        treeContext: null,
        retryLane: 0
      };
    var zk = function (a, b, c, d) {
      for (c = b.child; null !== c;) {
        if (5 === c.tag || 6 === c.tag) a.appendChild(c.stateNode);else if (4 !== c.tag && null !== c.child) {
          c.child.return = c;
          c = c.child;
          continue;
        }
        if (c === b) break;
        for (; null === c.sibling;) {
          if (null === c.return || c.return === b) return;
          c = c.return;
        }
        c.sibling.return = c.return;
        c = c.sibling;
      }
    };
    var xi = function (a, b) {};
    var yk = function (a, b, c, d, e) {
      var f = a.memoizedProps;
      if (f !== d) {
        a = b.stateNode;
        ub(Ea.current);
        e = null;
        switch (c) {
          case "input":
            f = ke(a, f);
            d = ke(a, d);
            e = [];
            break;
          case "select":
            f = E({}, f, {
              value: void 0
            });
            d = E({}, d, {
              value: void 0
            });
            e = [];
            break;
          case "textarea":
            f = ne(a, f);
            d = ne(a, d);
            e = [];
            break;
          default:
            "function" !== typeof f.onClick && "function" === typeof d.onClick && (a.onclick = kd);
        }
        pe(c, d);
        var g;
        c = null;
        for (l in f) if (!d.hasOwnProperty(l) && f.hasOwnProperty(l) && null != f[l]) if ("style" === l) {
          var h = f[l];
          for (g in h) h.hasOwnProperty(g) && (c || (c = {}), c[g] = "");
        } else "dangerouslySetInnerHTML" !== l && "children" !== l && "suppressContentEditableWarning" !== l && "suppressHydrationWarning" !== l && "autoFocus" !== l && ($b.hasOwnProperty(l) ? e || (e = []) : (e = e || []).push(l, null));
        for (l in d) {
          var k = d[l];
          h = null != f ? f[l] : void 0;
          if (d.hasOwnProperty(l) && k !== h && (null != k || null != h)) if ("style" === l) {
            if (h) {
              for (g in h) !h.hasOwnProperty(g) || k && k.hasOwnProperty(g) || (c || (c = {}), c[g] = "");
              for (g in k) k.hasOwnProperty(g) && h[g] !== k[g] && (c || (c = {}), c[g] = k[g]);
            } else c || (e || (e = []), e.push(l, c)), c = k;
          } else "dangerouslySetInnerHTML" === l ? (k = k ? k.__html : void 0, h = h ? h.__html : void 0, null != k && h !== k && (e = e || []).push(l, k)) : "children" === l ? "string" !== typeof k && "number" !== typeof k || (e = e || []).push(l, "" + k) : "suppressContentEditableWarning" !== l && "suppressHydrationWarning" !== l && ($b.hasOwnProperty(l) ? (null != k && "onScroll" === l && B("scroll", a), e || h === k || (e = [])) : (e = e || []).push(l, k));
        }
        c && (e = e || []).push("style", c);
        var l = e;
        if (b.updateQueue = l) b.flags |= 4;
      }
    };
    var Ak = function (a, b, c, d) {
      c !== d && (b.flags |= 4);
    };
    var Jd = !1,
      X = !1,
      Fk = "function" === typeof WeakSet ? WeakSet : Set,
      l = null,
      zi = !1,
      T = null,
      za = !1,
      Mk = Math.ceil,
      Od = Sa.ReactCurrentDispatcher,
      Uf = Sa.ReactCurrentOwner,
      ca = Sa.ReactCurrentBatchConfig,
      p = 0,
      O = null,
      H = null,
      U = 0,
      ba = 0,
      Ga = bb(0),
      L = 0,
      Jc = null,
      ra = 0,
      Md = 0,
      Sf = 0,
      Kc = null,
      ja = null,
      Of = 0,
      Hf = Infinity,
      Ra = null,
      Ed = !1,
      xf = null,
      ib = null,
      Pd = !1,
      lb = null,
      Qd = 0,
      Ic = 0,
      Pf = null,
      Kd = -1,
      Ld = 0;
    var Qk = function (a, b, c) {
      if (null !== a) {
        if (a.memoizedProps !== b.pendingProps || S.current) ha = !0;else {
          if (0 === (a.lanes & c) && 0 === (b.flags & 128)) return ha = !1, wk(a, b, c);
          ha = 0 !== (a.flags & 131072) ? !0 : !1;
        }
      } else ha = !1, D && 0 !== (b.flags & 1048576) && yh(b, nd, b.index);
      b.lanes = 0;
      switch (b.tag) {
        case 2:
          var d = b.type;
          Fd(a, b);
          a = b.pendingProps;
          var e = Nb(b, J.current);
          Sb(b, c);
          e = mf(null, b, d, a, e, c);
          var f = nf();
          b.flags |= 1;
          "object" === typeof e && null !== e && "function" === typeof e.render && void 0 === e.$$typeof ? (b.tag = 1, b.memoizedState = null, b.updateQueue = null, ea(d) ? (f = !0, ld(b)) : f = !1, b.memoizedState = null !== e.state && void 0 !== e.state ? e.state : null, ff(b), e.updater = Dd, b.stateNode = e, e._reactInternals = b, uf(b, d, a, c), b = Af(null, b, d, !0, f, c)) : (b.tag = 0, D && f && Ue(b), aa(null, b, e, c), b = b.child);
          return b;
        case 16:
          d = b.elementType;
          a: {
            Fd(a, b);
            a = b.pendingProps;
            e = d._init;
            d = e(d._payload);
            b.type = d;
            e = b.tag = Uk(d);
            a = ya(d, a);
            switch (e) {
              case 0:
                b = zf(null, b, d, a, c);
                break a;
              case 1:
                b = ri(null, b, d, a, c);
                break a;
              case 11:
                b = mi(null, b, d, a, c);
                break a;
              case 14:
                b = ni(null, b, d, ya(d.type, a), c);
                break a;
            }
            throw Error(m(306, d, ""));
          }
          return b;
        case 0:
          return d = b.type, e = b.pendingProps, e = b.elementType === d ? e : ya(d, e), zf(a, b, d, e, c);
        case 1:
          return d = b.type, e = b.pendingProps, e = b.elementType === d ? e : ya(d, e), ri(a, b, d, e, c);
        case 3:
          a: {
            si(b);
            if (null === a) throw Error(m(387));
            d = b.pendingProps;
            f = b.memoizedState;
            e = f.element;
            Fh(a, b);
            wd(b, d, null, c);
            var g = b.memoizedState;
            d = g.element;
            if (f.isDehydrated) {
              if (f = {
                element: d,
                isDehydrated: !1,
                cache: g.cache,
                pendingSuspenseBoundaries: g.pendingSuspenseBoundaries,
                transitions: g.transitions
              }, b.updateQueue.baseState = f, b.memoizedState = f, b.flags & 256) {
                e = Ub(Error(m(423)), b);
                b = ti(a, b, d, c, e);
                break a;
              } else if (d !== e) {
                e = Ub(Error(m(424)), b);
                b = ti(a, b, d, c, e);
                break a;
              } else for (fa = Ka(b.stateNode.containerInfo.firstChild), la = b, D = !0, wa = null, c = li(b, null, d, c), b.child = c; c;) c.flags = c.flags & -3 | 4096, c = c.sibling;
            } else {
              Qb();
              if (d === e) {
                b = Qa(a, b, c);
                break a;
              }
              aa(a, b, d, c);
            }
            b = b.child;
          }
          return b;
        case 5:
          return Ih(b), null === a && Xe(b), d = b.type, e = b.pendingProps, f = null !== a ? a.memoizedProps : null, g = e.children, Qe(d, e) ? g = null : null !== f && Qe(d, f) && (b.flags |= 32), qi(a, b), aa(a, b, g, c), b.child;
        case 6:
          return null === a && Xe(b), null;
        case 13:
          return ui(a, b, c);
        case 4:
          return gf(b, b.stateNode.containerInfo), d = b.pendingProps, null === a ? b.child = Vb(b, null, d, c) : aa(a, b, d, c), b.child;
        case 11:
          return d = b.type, e = b.pendingProps, e = b.elementType === d ? e : ya(d, e), mi(a, b, d, e, c);
        case 7:
          return aa(a, b, b.pendingProps, c), b.child;
        case 8:
          return aa(a, b, b.pendingProps.children, c), b.child;
        case 12:
          return aa(a, b, b.pendingProps.children, c), b.child;
        case 10:
          a: {
            d = b.type._context;
            e = b.pendingProps;
            f = b.memoizedProps;
            g = e.value;
            y(ud, d._currentValue);
            d._currentValue = g;
            if (null !== f) if (ua(f.value, g)) {
              if (f.children === e.children && !S.current) {
                b = Qa(a, b, c);
                break a;
              }
            } else for (f = b.child, null !== f && (f.return = b); null !== f;) {
              var h = f.dependencies;
              if (null !== h) {
                g = f.child;
                for (var k = h.firstContext; null !== k;) {
                  if (k.context === d) {
                    if (1 === f.tag) {
                      k = Pa(-1, c & -c);
                      k.tag = 2;
                      var l = f.updateQueue;
                      if (null !== l) {
                        l = l.shared;
                        var p = l.pending;
                        null === p ? k.next = k : (k.next = p.next, p.next = k);
                        l.pending = k;
                      }
                    }
                    f.lanes |= c;
                    k = f.alternate;
                    null !== k && (k.lanes |= c);
                    df(f.return, c, b);
                    h.lanes |= c;
                    break;
                  }
                  k = k.next;
                }
              } else if (10 === f.tag) g = f.type === b.type ? null : f.child;else if (18 === f.tag) {
                g = f.return;
                if (null === g) throw Error(m(341));
                g.lanes |= c;
                h = g.alternate;
                null !== h && (h.lanes |= c);
                df(g, c, b);
                g = f.sibling;
              } else g = f.child;
              if (null !== g) g.return = f;else for (g = f; null !== g;) {
                if (g === b) {
                  g = null;
                  break;
                }
                f = g.sibling;
                if (null !== f) {
                  f.return = g.return;
                  g = f;
                  break;
                }
                g = g.return;
              }
              f = g;
            }
            aa(a, b, e.children, c);
            b = b.child;
          }
          return b;
        case 9:
          return e = b.type, d = b.pendingProps.children, Sb(b, c), e = qa(e), d = d(e), b.flags |= 1, aa(a, b, d, c), b.child;
        case 14:
          return d = b.type, e = ya(d, b.pendingProps), e = ya(d.type, e), ni(a, b, d, e, c);
        case 15:
          return oi(a, b, b.type, b.pendingProps, c);
        case 17:
          return d = b.type, e = b.pendingProps, e = b.elementType === d ? e : ya(d, e), Fd(a, b), b.tag = 1, ea(d) ? (a = !0, ld(b)) : a = !1, Sb(b, c), ei(b, d, e), uf(b, d, e, c), Af(null, b, d, !0, a, c);
        case 19:
          return wi(a, b, c);
        case 22:
          return pi(a, b, c);
      }
      throw Error(m(156, b.tag));
    };
    var pa = function (a, b, c, d) {
        return new Tk(a, b, c, d);
      },
      aj = "function" === typeof reportError ? reportError : function (a) {
        console.error(a);
      };
    Ud.prototype.render = Xf.prototype.render = function (a) {
      var b = this._internalRoot;
      if (null === b) throw Error(m(409));
      Sd(a, b, null, null);
    };
    Ud.prototype.unmount = Xf.prototype.unmount = function () {
      var a = this._internalRoot;
      if (null !== a) {
        this._internalRoot = null;
        var b = a.containerInfo;
        yb(function () {
          Sd(null, a, null, null);
        });
        b[Ja] = null;
      }
    };
    Ud.prototype.unstable_scheduleHydration = function (a) {
      if (a) {
        var b = nl();
        a = {
          blockedOn: null,
          target: a,
          priority: b
        };
        for (var c = 0; c < Ya.length && 0 !== b && b < Ya[c].priority; c++);
        Ya.splice(c, 0, a);
        0 === c && Hg(a);
      }
    };
    var Cj = function (a) {
      switch (a.tag) {
        case 3:
          var b = a.stateNode;
          if (b.current.memoizedState.isDehydrated) {
            var c = hc(b.pendingLanes);
            0 !== c && (xe(b, c | 1), ia(b, P()), 0 === (p & 6) && (Hc(), db()));
          }
          break;
        case 13:
          yb(function () {
            var b = Oa(a, 1);
            if (null !== b) {
              var c = Z();
              xa(b, a, 1, c);
            }
          }), Wf(a, 1);
      }
    };
    var Gg = function (a) {
      if (13 === a.tag) {
        var b = Oa(a, 134217728);
        if (null !== b) {
          var c = Z();
          xa(b, a, 134217728, c);
        }
        Wf(a, 134217728);
      }
    };
    var xj = function (a) {
      if (13 === a.tag) {
        var b = hb(a),
          c = Oa(a, b);
        if (null !== c) {
          var d = Z();
          xa(c, a, b, d);
        }
        Wf(a, b);
      }
    };
    var nl = function () {
      return z;
    };
    var wj = function (a, b) {
      var c = z;
      try {
        return z = a, b();
      } finally {
        z = c;
      }
    };
    se = function (a, b, c) {
      switch (b) {
        case "input":
          le(a, c);
          b = c.name;
          if ("radio" === c.type && null != b) {
            for (c = a; c.parentNode;) c = c.parentNode;
            c = c.querySelectorAll("input[name=" + JSON.stringify("" + b) + '][type="radio"]');
            for (b = 0; b < c.length; b++) {
              var d = c[b];
              if (d !== a && d.form === a.form) {
                var e = Rc(d);
                if (!e) throw Error(m(90));
                jg(d);
                le(d, e);
              }
            }
          }
          break;
        case "textarea":
          og(a, c);
          break;
        case "select":
          b = c.value, null != b && Db(a, !!c.multiple, b, !1);
      }
    };
    (function (a, b, c) {
      xg = a;
      yg = c;
    })(Tf, function (a, b, c, d, e) {
      var f = z,
        g = ca.transition;
      try {
        return ca.transition = null, z = 1, a(b, c, d, e);
      } finally {
        z = f, ca.transition = g, 0 === p && Hc();
      }
    }, yb);
    var ol = {
      usingClientEntryPoint: !1,
      Events: [ec, Ib, Rc, ug, vg, Tf]
    };
    (function (a) {
      a = {
        bundleType: a.bundleType,
        version: a.version,
        rendererPackageName: a.rendererPackageName,
        rendererConfig: a.rendererConfig,
        overrideHookState: null,
        overrideHookStateDeletePath: null,
        overrideHookStateRenamePath: null,
        overrideProps: null,
        overridePropsDeletePath: null,
        overridePropsRenamePath: null,
        setErrorHandler: null,
        setSuspenseHandler: null,
        scheduleUpdate: null,
        currentDispatcherRef: Sa.ReactCurrentDispatcher,
        findHostInstanceByFiber: Xk,
        findFiberByHostInstance: a.findFiberByHostInstance || Yk,
        findHostInstancesForRefresh: null,
        scheduleRefresh: null,
        scheduleRoot: null,
        setRefreshHandler: null,
        getCurrentFiber: null,
        reconcilerVersion: "18.3.1"
      };
      if ("undefined" === typeof __REACT_DEVTOOLS_GLOBAL_HOOK__) a = !1;else {
        var b = __REACT_DEVTOOLS_GLOBAL_HOOK__;
        if (b.isDisabled || !b.supportsFiber) a = !0;else {
          try {
            Uc = b.inject(a), Ca = b;
          } catch (c) {}
          a = b.checkDCE ? !0 : !1;
        }
      }
      return a;
    })({
      findFiberByHostInstance: ob,
      bundleType: 0,
      version: "18.3.1-next-f1338f8080-20240426",
      rendererPackageName: "react-dom"
    });
    Q.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = ol;
    Q.createPortal = function (a, b) {
      var c = 2 < arguments.length && void 0 !== arguments[2] ? arguments[2] : null;
      if (!Yf(b)) throw Error(m(200));
      return Wk(a, b, null, c);
    };
    Q.createRoot = function (a, b) {
      if (!Yf(a)) throw Error(m(299));
      var c = !1,
        d = "",
        e = aj;
      null !== b && void 0 !== b && (!0 === b.unstable_strictMode && (c = !0), void 0 !== b.identifierPrefix && (d = b.identifierPrefix), void 0 !== b.onRecoverableError && (e = b.onRecoverableError));
      b = Vf(a, 1, !1, null, null, c, !1, d, e);
      a[Ja] = b.current;
      sc(8 === a.nodeType ? a.parentNode : a);
      return new Xf(b);
    };
    Q.findDOMNode = function (a) {
      if (null == a) return null;
      if (1 === a.nodeType) return a;
      var b = a._reactInternals;
      if (void 0 === b) {
        if ("function" === typeof a.render) throw Error(m(188));
        a = Object.keys(a).join(",");
        throw Error(m(268, a));
      }
      a = Bg(b);
      a = null === a ? null : a.stateNode;
      return a;
    };
    Q.flushSync = function (a) {
      return yb(a);
    };
    Q.hydrate = function (a, b, c) {
      if (!Vd(b)) throw Error(m(200));
      return Wd(null, a, b, !0, c);
    };
    Q.hydrateRoot = function (a, b, c) {
      if (!Yf(a)) throw Error(m(405));
      var d = null != c && c.hydratedSources || null,
        e = !1,
        f = "",
        g = aj;
      null !== c && void 0 !== c && (!0 === c.unstable_strictMode && (e = !0), void 0 !== c.identifierPrefix && (f = c.identifierPrefix), void 0 !== c.onRecoverableError && (g = c.onRecoverableError));
      b = Wi(b, null, a, 1, null != c ? c : null, e, !1, f, g);
      a[Ja] = b.current;
      sc(a);
      if (d) for (a = 0; a < d.length; a++) c = d[a], e = c._getVersion, e = e(c._source), null == b.mutableSourceEagerHydrationData ? b.mutableSourceEagerHydrationData = [c, e] : b.mutableSourceEagerHydrationData.push(c, e);
      return new Ud(b);
    };
    Q.render = function (a, b, c) {
      if (!Vd(b)) throw Error(m(200));
      return Wd(null, a, b, !1, c);
    };
    Q.unmountComponentAtNode = function (a) {
      if (!Vd(a)) throw Error(m(40));
      return a._reactRootContainer ? (yb(function () {
        Wd(null, null, a, !1, function () {
          a._reactRootContainer = null;
          a[Ja] = null;
        });
      }), !0) : !1;
    };
    Q.unstable_batchedUpdates = Tf;
    Q.unstable_renderSubtreeIntoContainer = function (a, b, c, d) {
      if (!Vd(c)) throw Error(m(200));
      if (null == a || void 0 === a._reactInternals) throw Error(m(38));
      return Wd(a, b, c, !1, d);
    };
    Q.version = "18.3.1-next-f1338f8080-20240426";
  });
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "assets/vendor/react-dom.production.min.js", error: String((e && e.message) || e) }); }

// assets/vendor/react.production.min.js
try { (() => {
/**
 * @license React
 * react.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
(function () {
  'use strict';

  (function (c, x) {
    "object" === typeof exports && "undefined" !== typeof module ? x(exports) : "function" === typeof define && define.amd ? define(["exports"], x) : (c = c || self, x(c.React = {}));
  })(this, function (c) {
    function x(a) {
      if (null === a || "object" !== typeof a) return null;
      a = V && a[V] || a["@@iterator"];
      return "function" === typeof a ? a : null;
    }
    function w(a, b, e) {
      this.props = a;
      this.context = b;
      this.refs = W;
      this.updater = e || X;
    }
    function Y() {}
    function K(a, b, e) {
      this.props = a;
      this.context = b;
      this.refs = W;
      this.updater = e || X;
    }
    function Z(a, b, e) {
      var m,
        d = {},
        c = null,
        h = null;
      if (null != b) for (m in void 0 !== b.ref && (h = b.ref), void 0 !== b.key && (c = "" + b.key), b) aa.call(b, m) && !ba.hasOwnProperty(m) && (d[m] = b[m]);
      var l = arguments.length - 2;
      if (1 === l) d.children = e;else if (1 < l) {
        for (var f = Array(l), k = 0; k < l; k++) f[k] = arguments[k + 2];
        d.children = f;
      }
      if (a && a.defaultProps) for (m in l = a.defaultProps, l) void 0 === d[m] && (d[m] = l[m]);
      return {
        $$typeof: y,
        type: a,
        key: c,
        ref: h,
        props: d,
        _owner: L.current
      };
    }
    function oa(a, b) {
      return {
        $$typeof: y,
        type: a.type,
        key: b,
        ref: a.ref,
        props: a.props,
        _owner: a._owner
      };
    }
    function M(a) {
      return "object" === typeof a && null !== a && a.$$typeof === y;
    }
    function pa(a) {
      var b = {
        "=": "=0",
        ":": "=2"
      };
      return "$" + a.replace(/[=:]/g, function (a) {
        return b[a];
      });
    }
    function N(a, b) {
      return "object" === typeof a && null !== a && null != a.key ? pa("" + a.key) : b.toString(36);
    }
    function B(a, b, e, m, d) {
      var c = typeof a;
      if ("undefined" === c || "boolean" === c) a = null;
      var h = !1;
      if (null === a) h = !0;else switch (c) {
        case "string":
        case "number":
          h = !0;
          break;
        case "object":
          switch (a.$$typeof) {
            case y:
            case qa:
              h = !0;
          }
      }
      if (h) return h = a, d = d(h), a = "" === m ? "." + N(h, 0) : m, ca(d) ? (e = "", null != a && (e = a.replace(da, "$&/") + "/"), B(d, b, e, "", function (a) {
        return a;
      })) : null != d && (M(d) && (d = oa(d, e + (!d.key || h && h.key === d.key ? "" : ("" + d.key).replace(da, "$&/") + "/") + a)), b.push(d)), 1;
      h = 0;
      m = "" === m ? "." : m + ":";
      if (ca(a)) for (var l = 0; l < a.length; l++) {
        c = a[l];
        var f = m + N(c, l);
        h += B(c, b, e, f, d);
      } else if (f = x(a), "function" === typeof f) for (a = f.call(a), l = 0; !(c = a.next()).done;) c = c.value, f = m + N(c, l++), h += B(c, b, e, f, d);else if ("object" === c) throw b = String(a), Error("Objects are not valid as a React child (found: " + ("[object Object]" === b ? "object with keys {" + Object.keys(a).join(", ") + "}" : b) + "). If you meant to render a collection of children, use an array instead.");
      return h;
    }
    function C(a, b, e) {
      if (null == a) return a;
      var c = [],
        d = 0;
      B(a, c, "", "", function (a) {
        return b.call(e, a, d++);
      });
      return c;
    }
    function ra(a) {
      if (-1 === a._status) {
        var b = a._result;
        b = b();
        b.then(function (b) {
          if (0 === a._status || -1 === a._status) a._status = 1, a._result = b;
        }, function (b) {
          if (0 === a._status || -1 === a._status) a._status = 2, a._result = b;
        });
        -1 === a._status && (a._status = 0, a._result = b);
      }
      if (1 === a._status) return a._result.default;
      throw a._result;
    }
    function O(a, b) {
      var e = a.length;
      a.push(b);
      a: for (; 0 < e;) {
        var c = e - 1 >>> 1,
          d = a[c];
        if (0 < D(d, b)) a[c] = b, a[e] = d, e = c;else break a;
      }
    }
    function p(a) {
      return 0 === a.length ? null : a[0];
    }
    function E(a) {
      if (0 === a.length) return null;
      var b = a[0],
        e = a.pop();
      if (e !== b) {
        a[0] = e;
        a: for (var c = 0, d = a.length, k = d >>> 1; c < k;) {
          var h = 2 * (c + 1) - 1,
            l = a[h],
            f = h + 1,
            g = a[f];
          if (0 > D(l, e)) f < d && 0 > D(g, l) ? (a[c] = g, a[f] = e, c = f) : (a[c] = l, a[h] = e, c = h);else if (f < d && 0 > D(g, e)) a[c] = g, a[f] = e, c = f;else break a;
        }
      }
      return b;
    }
    function D(a, b) {
      var c = a.sortIndex - b.sortIndex;
      return 0 !== c ? c : a.id - b.id;
    }
    function P(a) {
      for (var b = p(r); null !== b;) {
        if (null === b.callback) E(r);else if (b.startTime <= a) E(r), b.sortIndex = b.expirationTime, O(q, b);else break;
        b = p(r);
      }
    }
    function Q(a) {
      z = !1;
      P(a);
      if (!u) if (null !== p(q)) u = !0, R(S);else {
        var b = p(r);
        null !== b && T(Q, b.startTime - a);
      }
    }
    function S(a, b) {
      u = !1;
      z && (z = !1, ea(A), A = -1);
      F = !0;
      var c = k;
      try {
        P(b);
        for (n = p(q); null !== n && (!(n.expirationTime > b) || a && !fa());) {
          var m = n.callback;
          if ("function" === typeof m) {
            n.callback = null;
            k = n.priorityLevel;
            var d = m(n.expirationTime <= b);
            b = v();
            "function" === typeof d ? n.callback = d : n === p(q) && E(q);
            P(b);
          } else E(q);
          n = p(q);
        }
        if (null !== n) var g = !0;else {
          var h = p(r);
          null !== h && T(Q, h.startTime - b);
          g = !1;
        }
        return g;
      } finally {
        n = null, k = c, F = !1;
      }
    }
    function fa() {
      return v() - ha < ia ? !1 : !0;
    }
    function R(a) {
      G = a;
      H || (H = !0, I());
    }
    function T(a, b) {
      A = ja(function () {
        a(v());
      }, b);
    }
    function ka(a) {
      throw Error("act(...) is not supported in production builds of React.");
    }
    var y = Symbol.for("react.element"),
      qa = Symbol.for("react.portal"),
      sa = Symbol.for("react.fragment"),
      ta = Symbol.for("react.strict_mode"),
      ua = Symbol.for("react.profiler"),
      va = Symbol.for("react.provider"),
      wa = Symbol.for("react.context"),
      xa = Symbol.for("react.forward_ref"),
      ya = Symbol.for("react.suspense"),
      za = Symbol.for("react.memo"),
      Aa = Symbol.for("react.lazy"),
      V = Symbol.iterator,
      X = {
        isMounted: function (a) {
          return !1;
        },
        enqueueForceUpdate: function (a, b, c) {},
        enqueueReplaceState: function (a, b, c, m) {},
        enqueueSetState: function (a, b, c, m) {}
      },
      la = Object.assign,
      W = {};
    w.prototype.isReactComponent = {};
    w.prototype.setState = function (a, b) {
      if ("object" !== typeof a && "function" !== typeof a && null != a) throw Error("setState(...): takes an object of state variables to update or a function which returns an object of state variables.");
      this.updater.enqueueSetState(this, a, b, "setState");
    };
    w.prototype.forceUpdate = function (a) {
      this.updater.enqueueForceUpdate(this, a, "forceUpdate");
    };
    Y.prototype = w.prototype;
    var t = K.prototype = new Y();
    t.constructor = K;
    la(t, w.prototype);
    t.isPureReactComponent = !0;
    var ca = Array.isArray,
      aa = Object.prototype.hasOwnProperty,
      L = {
        current: null
      },
      ba = {
        key: !0,
        ref: !0,
        __self: !0,
        __source: !0
      },
      da = /\/+/g,
      g = {
        current: null
      },
      J = {
        transition: null
      };
    if ("object" === typeof performance && "function" === typeof performance.now) {
      var Ba = performance;
      var v = function () {
        return Ba.now();
      };
    } else {
      var ma = Date,
        Ca = ma.now();
      v = function () {
        return ma.now() - Ca;
      };
    }
    var q = [],
      r = [],
      Da = 1,
      n = null,
      k = 3,
      F = !1,
      u = !1,
      z = !1,
      ja = "function" === typeof setTimeout ? setTimeout : null,
      ea = "function" === typeof clearTimeout ? clearTimeout : null,
      na = "undefined" !== typeof setImmediate ? setImmediate : null;
    "undefined" !== typeof navigator && void 0 !== navigator.scheduling && void 0 !== navigator.scheduling.isInputPending && navigator.scheduling.isInputPending.bind(navigator.scheduling);
    var H = !1,
      G = null,
      A = -1,
      ia = 5,
      ha = -1,
      U = function () {
        if (null !== G) {
          var a = v();
          ha = a;
          var b = !0;
          try {
            b = G(!0, a);
          } finally {
            b ? I() : (H = !1, G = null);
          }
        } else H = !1;
      };
    if ("function" === typeof na) var I = function () {
      na(U);
    };else if ("undefined" !== typeof MessageChannel) {
      t = new MessageChannel();
      var Ea = t.port2;
      t.port1.onmessage = U;
      I = function () {
        Ea.postMessage(null);
      };
    } else I = function () {
      ja(U, 0);
    };
    t = {
      ReactCurrentDispatcher: g,
      ReactCurrentOwner: L,
      ReactCurrentBatchConfig: J,
      Scheduler: {
        __proto__: null,
        unstable_ImmediatePriority: 1,
        unstable_UserBlockingPriority: 2,
        unstable_NormalPriority: 3,
        unstable_IdlePriority: 5,
        unstable_LowPriority: 4,
        unstable_runWithPriority: function (a, b) {
          switch (a) {
            case 1:
            case 2:
            case 3:
            case 4:
            case 5:
              break;
            default:
              a = 3;
          }
          var c = k;
          k = a;
          try {
            return b();
          } finally {
            k = c;
          }
        },
        unstable_next: function (a) {
          switch (k) {
            case 1:
            case 2:
            case 3:
              var b = 3;
              break;
            default:
              b = k;
          }
          var c = k;
          k = b;
          try {
            return a();
          } finally {
            k = c;
          }
        },
        unstable_scheduleCallback: function (a, b, c) {
          var e = v();
          "object" === typeof c && null !== c ? (c = c.delay, c = "number" === typeof c && 0 < c ? e + c : e) : c = e;
          switch (a) {
            case 1:
              var d = -1;
              break;
            case 2:
              d = 250;
              break;
            case 5:
              d = 1073741823;
              break;
            case 4:
              d = 1E4;
              break;
            default:
              d = 5E3;
          }
          d = c + d;
          a = {
            id: Da++,
            callback: b,
            priorityLevel: a,
            startTime: c,
            expirationTime: d,
            sortIndex: -1
          };
          c > e ? (a.sortIndex = c, O(r, a), null === p(q) && a === p(r) && (z ? (ea(A), A = -1) : z = !0, T(Q, c - e))) : (a.sortIndex = d, O(q, a), u || F || (u = !0, R(S)));
          return a;
        },
        unstable_cancelCallback: function (a) {
          a.callback = null;
        },
        unstable_wrapCallback: function (a) {
          var b = k;
          return function () {
            var c = k;
            k = b;
            try {
              return a.apply(this, arguments);
            } finally {
              k = c;
            }
          };
        },
        unstable_getCurrentPriorityLevel: function () {
          return k;
        },
        unstable_shouldYield: fa,
        unstable_requestPaint: function () {},
        unstable_continueExecution: function () {
          u || F || (u = !0, R(S));
        },
        unstable_pauseExecution: function () {},
        unstable_getFirstCallbackNode: function () {
          return p(q);
        },
        get unstable_now() {
          return v;
        },
        unstable_forceFrameRate: function (a) {
          0 > a || 125 < a ? console.error("forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported") : ia = 0 < a ? Math.floor(1E3 / a) : 5;
        },
        unstable_Profiling: null
      }
    };
    c.Children = {
      map: C,
      forEach: function (a, b, c) {
        C(a, function () {
          b.apply(this, arguments);
        }, c);
      },
      count: function (a) {
        var b = 0;
        C(a, function () {
          b++;
        });
        return b;
      },
      toArray: function (a) {
        return C(a, function (a) {
          return a;
        }) || [];
      },
      only: function (a) {
        if (!M(a)) throw Error("React.Children.only expected to receive a single React element child.");
        return a;
      }
    };
    c.Component = w;
    c.Fragment = sa;
    c.Profiler = ua;
    c.PureComponent = K;
    c.StrictMode = ta;
    c.Suspense = ya;
    c.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED = t;
    c.act = ka;
    c.cloneElement = function (a, b, c) {
      if (null === a || void 0 === a) throw Error("React.cloneElement(...): The argument must be a React element, but you passed " + a + ".");
      var e = la({}, a.props),
        d = a.key,
        k = a.ref,
        h = a._owner;
      if (null != b) {
        void 0 !== b.ref && (k = b.ref, h = L.current);
        void 0 !== b.key && (d = "" + b.key);
        if (a.type && a.type.defaultProps) var l = a.type.defaultProps;
        for (f in b) aa.call(b, f) && !ba.hasOwnProperty(f) && (e[f] = void 0 === b[f] && void 0 !== l ? l[f] : b[f]);
      }
      var f = arguments.length - 2;
      if (1 === f) e.children = c;else if (1 < f) {
        l = Array(f);
        for (var g = 0; g < f; g++) l[g] = arguments[g + 2];
        e.children = l;
      }
      return {
        $$typeof: y,
        type: a.type,
        key: d,
        ref: k,
        props: e,
        _owner: h
      };
    };
    c.createContext = function (a) {
      a = {
        $$typeof: wa,
        _currentValue: a,
        _currentValue2: a,
        _threadCount: 0,
        Provider: null,
        Consumer: null,
        _defaultValue: null,
        _globalName: null
      };
      a.Provider = {
        $$typeof: va,
        _context: a
      };
      return a.Consumer = a;
    };
    c.createElement = Z;
    c.createFactory = function (a) {
      var b = Z.bind(null, a);
      b.type = a;
      return b;
    };
    c.createRef = function () {
      return {
        current: null
      };
    };
    c.forwardRef = function (a) {
      return {
        $$typeof: xa,
        render: a
      };
    };
    c.isValidElement = M;
    c.lazy = function (a) {
      return {
        $$typeof: Aa,
        _payload: {
          _status: -1,
          _result: a
        },
        _init: ra
      };
    };
    c.memo = function (a, b) {
      return {
        $$typeof: za,
        type: a,
        compare: void 0 === b ? null : b
      };
    };
    c.startTransition = function (a, b) {
      b = J.transition;
      J.transition = {};
      try {
        a();
      } finally {
        J.transition = b;
      }
    };
    c.unstable_act = ka;
    c.useCallback = function (a, b) {
      return g.current.useCallback(a, b);
    };
    c.useContext = function (a) {
      return g.current.useContext(a);
    };
    c.useDebugValue = function (a, b) {};
    c.useDeferredValue = function (a) {
      return g.current.useDeferredValue(a);
    };
    c.useEffect = function (a, b) {
      return g.current.useEffect(a, b);
    };
    c.useId = function () {
      return g.current.useId();
    };
    c.useImperativeHandle = function (a, b, c) {
      return g.current.useImperativeHandle(a, b, c);
    };
    c.useInsertionEffect = function (a, b) {
      return g.current.useInsertionEffect(a, b);
    };
    c.useLayoutEffect = function (a, b) {
      return g.current.useLayoutEffect(a, b);
    };
    c.useMemo = function (a, b) {
      return g.current.useMemo(a, b);
    };
    c.useReducer = function (a, b, c) {
      return g.current.useReducer(a, b, c);
    };
    c.useRef = function (a) {
      return g.current.useRef(a);
    };
    c.useState = function (a) {
      return g.current.useState(a);
    };
    c.useSyncExternalStore = function (a, b, c) {
      return g.current.useSyncExternalStore(a, b, c);
    };
    c.useTransition = function () {
      return g.current.useTransition();
    };
    c.version = "18.3.1";
  });
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "assets/vendor/react.production.min.js", error: String((e && e.message) || e) }); }

// components/buttons/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Pathly Button — the app-wide action button.
 *
 * Variants:
 *  - primary     accent-tinted fill (default interactive action)
 *  - cta         solid accent fill, dark text (high-emphasis, e.g. "Export Skill")
 *  - secondary   bordered, mantle bg, hover→accent (toolbar / FlowControlBar)
 *  - ghost       transparent, subtle border
 *  - destructive red-tinted
 */
function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  icon = null,
  onClick,
  type = 'button',
  style,
  ...rest
}) {
  const pad = size === 'sm' ? '4px 10px' : '6px 14px';
  const fontSize = size === 'sm' ? 'var(--font-size-sm)' : 'var(--font-size-base)';
  const variants = {
    primary: {
      background: 'var(--accent-bg)',
      color: 'var(--accent)',
      border: '1px solid var(--accent-border)'
    },
    cta: {
      background: 'var(--accent)',
      color: 'var(--bg-mantle)',
      border: '1px solid transparent',
      fontWeight: 'var(--font-weight-semibold)'
    },
    secondary: {
      background: 'var(--bg-mantle)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-color)'
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-color)'
    },
    destructive: {
      background: 'var(--red-bg)',
      color: 'var(--red)',
      border: '1px solid var(--red-border)'
    }
  };
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '6px',
    padding: pad,
    borderRadius: 'var(--radius-md)',
    fontFamily: 'var(--font-family-base)',
    fontSize,
    fontWeight: 'var(--font-weight-medium)',
    lineHeight: 1,
    whiteSpace: 'nowrap',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'background var(--transition-base), color var(--transition-base), border-color var(--transition-base)',
    position: 'relative',
    ...variants[variant],
    ...style
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    className: `pathly-btn pathly-btn--${variant}`,
    "data-loading": loading ? 'true' : undefined,
    style: base,
    disabled: disabled || loading,
    onClick: onClick
  }, rest), loading && /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      width: '12px',
      height: '12px',
      borderRadius: '50%',
      border: '2px solid transparent',
      borderTopColor: 'currentColor',
      animation: 'pathly-spin 0.7s linear infinite',
      marginRight: '-2px'
    }
  }), icon && !loading ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      flexShrink: 0
    }
  }, icon) : null, children, /*#__PURE__*/React.createElement("style", null, '@keyframes pathly-spin{to{transform:rotate(360deg)}}'));
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/buttons/Button.jsx", error: String((e && e.message) || e) }); }

// components/buttons/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Pathly IconButton — square icon-only control (topbar, toolbars, row actions).
 */
function IconButton({
  children,
  title,
  variant = 'default',
  size = 'sm',
  active = false,
  disabled = false,
  onClick,
  style,
  ...rest
}) {
  const dim = size === 'md' ? '30px' : '26px';
  const color = variant === 'danger' ? 'var(--red)' : variant === 'muted' ? 'var(--text-muted)' : active ? 'var(--accent)' : 'var(--text-secondary)';
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: dim,
    height: dim,
    flexShrink: 0,
    borderRadius: 'var(--radius-md)',
    border: '1px solid transparent',
    background: active ? 'var(--accent-bg)' : 'transparent',
    color,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.4 : 1,
    transition: 'background var(--transition-fast), color var(--transition-fast)',
    ...style
  };
  const onEnter = e => {
    if (!disabled && !active) e.currentTarget.style.background = 'var(--bg-surface1)';
  };
  const onLeave = e => {
    if (!active) e.currentTarget.style.background = 'transparent';
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    className: "pathly-icon-btn",
    title: title,
    "aria-label": title,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: onEnter,
    onMouseLeave: onLeave
  }, active ? {
    'data-active': 'true'
  } : {}, {
    style: base
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/buttons/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Badge.jsx
try { (() => {
/**
 * Pathly Badge — small monospace chip. Tinted from a single colour
 * (text = colour, bg = 18% colour, border = 44% colour).
 */
const PRESETS = {
  core: 'var(--green)',
  flow: 'var(--runtime)',
  integration: 'var(--yellow)',
  body: 'var(--blue)',
  neutral: 'var(--text-muted)'
};
function Badge({
  label,
  children,
  color,
  variant,
  style
}) {
  const c = color || PRESETS[variant] || 'var(--text-muted)';
  const s = {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '1px 6px',
    borderRadius: 'var(--radius-sm)',
    fontFamily: 'var(--font-family-mono)',
    fontSize: 'var(--font-size-sm)',
    lineHeight: 1.5,
    color: c,
    border: `1px solid color-mix(in srgb, ${c} 35%, transparent)`,
    background: `color-mix(in srgb, ${c} 14%, transparent)`,
    ...style
  };
  return /*#__PURE__*/React.createElement("span", {
    className: "pathly-badge",
    style: s
  }, label ?? children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Badge.jsx", error: String((e && e.message) || e) }); }

// components/feedback/ProgressBar.jsx
try { (() => {
/**
 * Pathly ProgressBar — thin rounded track with a coloured fill. Optional
 * fraction label (e.g. "3/3") shown to the right.
 */
function ProgressBar({
  value = 0,
  max = 100,
  color = 'var(--accent)',
  height = 6,
  label,
  style
}) {
  const pct = Math.max(0, Math.min(100, value / max * 100));
  return /*#__PURE__*/React.createElement("div", {
    className: "pathly-progress",
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: `${height}px`,
      background: 'var(--bg-surface1)',
      borderRadius: 'var(--radius-full)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${pct}%`,
      height: '100%',
      background: color,
      borderRadius: 'var(--radius-full)',
      transition: 'width var(--transition-base)'
    }
  })), label != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-family-mono)',
      fontSize: 'var(--font-size-sm)',
      color: 'var(--text-muted)',
      flexShrink: 0
    }
  }, label));
}
Object.assign(__ds_scope, { ProgressBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/ProgressBar.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Spinner.jsx
try { (() => {
/**
 * Pathly Spinner — small rotating ring. Inherits currentColor by default.
 */
function Spinner({
  size = 14,
  color = 'var(--accent)',
  strokeWidth = 2,
  style
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: "pathly-spinner",
    style: {
      display: 'inline-block',
      width: `${size}px`,
      height: `${size}px`,
      borderRadius: '50%',
      border: `${strokeWidth}px solid var(--bg-surface1)`,
      borderTopColor: color,
      animation: 'pathly-spin 0.7s linear infinite',
      ...style
    }
  }, /*#__PURE__*/React.createElement("style", null, '@keyframes pathly-spin{to{transform:rotate(360deg)}}'));
}
Object.assign(__ds_scope, { Spinner });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Spinner.jsx", error: String((e && e.message) || e) }); }

// components/feedback/StatePill.jsx
try { (() => {
/**
 * Pathly StatePill — the FSM stage pill (PLANNING · BUILDING · REVIEWING ·
 * TESTING · RETRO · DONE). A coloured dot + uppercase label, tinted to match.
 */
const STATE_COLORS = {
  PLANNING: 'var(--state-planning)',
  BUILDING: 'var(--state-building)',
  REVIEWING: 'var(--state-reviewing)',
  TESTING: 'var(--state-testing)',
  RETRO: 'var(--state-retro)',
  DONE: 'var(--state-done)',
  ERROR: 'var(--state-error)',
  IDLE: 'var(--text-muted)'
};
function StatePill({
  state = 'PLANNING',
  label,
  solid = false,
  style
}) {
  const key = String(state).toUpperCase();
  const c = STATE_COLORS[key] || 'var(--text-muted)';
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '3px 9px 3px 8px',
    borderRadius: 'var(--radius-full)',
    fontSize: 'var(--font-size-sm)',
    fontWeight: 600,
    letterSpacing: '0.04em',
    lineHeight: 1,
    color: solid ? 'var(--bg-mantle)' : c,
    background: solid ? c : `color-mix(in srgb, ${c} 13%, transparent)`,
    border: `1px solid color-mix(in srgb, ${c} ${solid ? 100 : 38}%, transparent)`,
    ...style
  };
  return /*#__PURE__*/React.createElement("span", {
    className: "pathly-state-pill",
    "data-state": key,
    style: base
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: '7px',
      height: '7px',
      borderRadius: '50%',
      background: solid ? 'var(--bg-mantle)' : c,
      flexShrink: 0
    }
  }), label || key);
}
Object.assign(__ds_scope, { StatePill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/StatePill.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Pathly Input — single-line text field. Optional leading icon and label.
 */
function Input({
  value,
  onChange,
  placeholder,
  label,
  icon = null,
  size = 'md',
  disabled = false,
  type = 'text',
  onKeyDown,
  style,
  ...rest
}) {
  const [focused, setFocused] = React.useState(false);
  const pad = size === 'sm' ? '5px 9px' : '7px 11px';
  const fontSize = size === 'sm' ? 'var(--font-size-sm)' : 'var(--font-size-base)';
  const wrap = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '7px',
    background: 'var(--bg-surface0)',
    border: focused ? '1px solid var(--accent)' : '1px solid var(--border-color)',
    borderRadius: 'var(--radius-md)',
    padding: pad,
    boxShadow: focused ? '0 0 0 2px var(--accent-bg)' : 'none',
    transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
    opacity: disabled ? 0.5 : 1,
    ...style
  };
  const inputStyle = {
    flex: 1,
    minWidth: 0,
    border: 'none',
    outline: 'none',
    background: 'transparent',
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-family-base)',
    fontSize
  };
  const field = /*#__PURE__*/React.createElement("div", {
    className: "pathly-input-wrap",
    style: wrap
  }, icon ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      color: 'var(--text-muted)',
      flexShrink: 0
    }
  }, icon) : null, /*#__PURE__*/React.createElement("input", _extends({
    type: type,
    className: "pathly-input",
    style: inputStyle,
    value: value,
    onChange: onChange,
    placeholder: placeholder,
    disabled: disabled,
    onKeyDown: onKeyDown,
    onFocus: () => setFocused(true),
    onBlur: () => setFocused(false)
  }, rest)));
  if (!label) return field;
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '5px'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--font-size-sm)',
      fontWeight: 600,
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, label), field);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Pathly Select — native dropdown styled to match Input. Pass an array of
 * { value, label } options (or plain strings).
 */
function Select({
  value,
  onChange,
  options = [],
  size = 'md',
  disabled = false,
  style,
  ...rest
}) {
  const pad = size === 'sm' ? '5px 28px 5px 9px' : '7px 30px 7px 11px';
  const fontSize = size === 'sm' ? 'var(--font-size-sm)' : 'var(--font-size-base)';
  const opts = options.map(o => typeof o === 'string' ? {
    value: o,
    label: o
  } : o);
  const chevron = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238899B0' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='m6 9 6 6 6-6'/></svg>";
  const sel = {
    appearance: 'none',
    WebkitAppearance: 'none',
    background: `var(--bg-surface0) url("${chevron}") no-repeat right 9px center`,
    border: '1px solid var(--border-color)',
    borderRadius: 'var(--radius-md)',
    color: 'var(--text-primary)',
    fontFamily: 'var(--font-family-base)',
    fontSize,
    padding: pad,
    cursor: disabled ? 'not-allowed' : 'pointer',
    outline: 'none',
    opacity: disabled ? 0.5 : 1,
    ...style
  };
  return /*#__PURE__*/React.createElement("select", _extends({
    className: "pathly-select",
    style: sel,
    value: value,
    onChange: onChange,
    disabled: disabled
  }, rest), opts.map(o => /*#__PURE__*/React.createElement("option", {
    key: o.value,
    value: o.value
  }, o.label)));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
/**
 * Pathly Tabs — horizontal tab bar. Two looks:
 *  - "underline" (default): in-panel tabs (Timeline · Events · Agents · SQL)
 *  - "pill": top-level view switch (active = accent-tinted pill)
 * Each tab is { id, label, count? }.
 */
function Tabs({
  tabs = [],
  activeId,
  onChange,
  variant = 'underline',
  style
}) {
  const isPill = variant === 'pill';
  const bar = {
    display: 'flex',
    alignItems: 'center',
    gap: isPill ? '4px' : '20px',
    borderBottom: isPill ? 'none' : 'var(--border)',
    ...style
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "pathly-tabs",
    style: bar
  }, tabs.map(t => {
    const active = t.id === activeId;
    const tabStyle = isPill ? {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '5px 11px',
      borderRadius: 'var(--radius-md)',
      cursor: 'pointer',
      border: 'none',
      background: active ? 'var(--accent-bg)' : 'transparent',
      color: active ? 'var(--accent)' : 'var(--text-secondary)',
      fontFamily: 'var(--font-family-base)',
      fontSize: 'var(--font-size-base)',
      fontWeight: 500,
      transition: 'background var(--transition-fast), color var(--transition-fast)'
    } : {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '0 0 9px',
      marginBottom: '-1px',
      cursor: 'pointer',
      border: 'none',
      borderBottom: `2px solid ${active ? 'var(--accent)' : 'transparent'}`,
      background: 'transparent',
      color: active ? 'var(--text-primary)' : 'var(--text-muted)',
      fontFamily: 'var(--font-family-base)',
      fontSize: 'var(--font-size-base)',
      fontWeight: active ? 600 : 500,
      transition: 'color var(--transition-fast)'
    };
    return /*#__PURE__*/React.createElement("button", {
      key: t.id,
      type: "button",
      className: "pathly-tab",
      "data-active": active ? 'true' : undefined,
      style: tabStyle,
      onClick: () => onChange && onChange(t.id)
    }, t.label, t.count != null && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-family-mono)',
        fontSize: 'var(--font-size-xs)',
        padding: '1px 5px',
        borderRadius: 'var(--radius-full)',
        lineHeight: 1.4,
        background: active ? 'var(--accent-bg)' : 'var(--bg-surface1)',
        color: active ? 'var(--accent)' : 'var(--text-muted)'
      }
    }, t.count));
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/overlay/ContextMenu.jsx
try { (() => {
/**
 * Pathly ContextMenu — floating menu surface of action rows. Each item is
 * { label, icon?, onClick?, danger?, shortcut? } or { separator: true }.
 * Renders the menu panel itself; pair with your own trigger/positioning.
 */
function ContextMenu({
  items = [],
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "pathly-context-menu",
    role: "menu",
    style: {
      minWidth: '180px',
      padding: '4px',
      background: 'var(--bg-mantle)',
      border: 'var(--border)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-lg)',
      ...style
    }
  }, items.map((it, i) => {
    if (it.separator) {
      return /*#__PURE__*/React.createElement("div", {
        key: i,
        style: {
          height: '1px',
          background: 'var(--border-color)',
          margin: '4px 0'
        }
      });
    }
    return /*#__PURE__*/React.createElement(MenuRow, {
      key: i,
      item: it
    });
  }));
}
function MenuRow({
  item
}) {
  const [hover, setHover] = React.useState(false);
  const color = item.danger ? 'var(--red)' : hover ? 'var(--accent)' : 'var(--text-primary)';
  return /*#__PURE__*/React.createElement("button", {
    type: "button",
    role: "menuitem",
    onClick: item.onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '9px',
      width: '100%',
      padding: '7px 10px',
      border: 'none',
      borderRadius: 'var(--radius-sm)',
      background: hover ? item.danger ? 'var(--red-bg)' : 'var(--bg-surface1)' : 'transparent',
      color,
      cursor: 'pointer',
      textAlign: 'left',
      fontFamily: 'var(--font-family-base)',
      fontSize: 'var(--font-size-base)',
      transition: 'background var(--transition-fast), color var(--transition-fast)'
    }
  }, item.icon && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      flexShrink: 0
    }
  }, item.icon), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, item.label), item.shortcut && /*#__PURE__*/React.createElement("kbd", {
    style: {
      fontFamily: 'var(--font-family-mono)',
      fontSize: 'var(--font-size-xs)',
      color: 'var(--text-muted)'
    }
  }, item.shortcut));
}
Object.assign(__ds_scope, { ContextMenu });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/overlay/ContextMenu.jsx", error: String((e && e.message) || e) }); }

// components/overlay/Tooltip.jsx
try { (() => {
/**
 * Pathly Tooltip — hover label on a wrapped trigger. Optional description
 * and keyboard shortcut. Dark surface, appears after a short delay.
 */
function Tooltip({
  label,
  description,
  shortcut,
  placement = 'bottom',
  children,
  style
}) {
  const [show, setShow] = React.useState(false);
  const timer = React.useRef(null);
  const enter = () => {
    timer.current = setTimeout(() => setShow(true), 350);
  };
  const leave = () => {
    clearTimeout(timer.current);
    setShow(false);
  };
  const pos = {
    top: {
      bottom: '100%',
      left: '50%',
      transform: 'translateX(-50%)',
      marginBottom: '7px'
    },
    bottom: {
      top: '100%',
      left: '50%',
      transform: 'translateX(-50%)',
      marginTop: '7px'
    },
    left: {
      right: '100%',
      top: '50%',
      transform: 'translateY(-50%)',
      marginRight: '7px'
    },
    right: {
      left: '100%',
      top: '50%',
      transform: 'translateY(-50%)',
      marginLeft: '7px'
    }
  }[placement];
  return /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'relative',
      display: 'inline-flex',
      ...style
    },
    onMouseEnter: enter,
    onMouseLeave: leave
  }, children, show && /*#__PURE__*/React.createElement("span", {
    role: "tooltip",
    style: {
      position: 'absolute',
      zIndex: 50,
      whiteSpace: 'nowrap',
      pointerEvents: 'none',
      background: 'var(--bg-mantle)',
      border: 'var(--border)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-md)',
      padding: '6px 9px',
      ...pos
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--font-size-sm)',
      fontWeight: 500,
      color: 'var(--text-primary)'
    }
  }, label), shortcut && /*#__PURE__*/React.createElement("kbd", {
    style: {
      fontFamily: 'var(--font-family-mono)',
      fontSize: 'var(--font-size-xs)',
      color: 'var(--text-muted)',
      border: 'var(--border)',
      borderRadius: 'var(--radius-xs)',
      padding: '0 4px'
    }
  }, shortcut)), description && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'block',
      marginTop: '3px',
      maxWidth: '220px',
      whiteSpace: 'normal',
      fontSize: 'var(--font-size-xs)',
      color: 'var(--text-muted)',
      lineHeight: 1.4
    }
  }, description)));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/overlay/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/surface/Card.jsx
try { (() => {
/**
 * Pathly Card — the standard surface container. Optional header row with a
 * title and right-aligned actions. `interactive` adds a hover lift for
 * clickable cards (e.g. the DB Explorer feature grid).
 */
function Card({
  title,
  actions,
  children,
  interactive = false,
  padding = '14px 16px',
  onClick,
  style
}) {
  const [hover, setHover] = React.useState(false);
  const base = {
    background: 'var(--bg-surface0)',
    border: hover && interactive ? '1px solid var(--accent-border)' : 'var(--border)',
    borderRadius: 'var(--radius-lg)',
    cursor: interactive ? 'pointer' : 'default',
    transition: 'border-color var(--transition-fast), background var(--transition-fast)',
    overflow: 'hidden',
    ...style
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "pathly-card",
    "data-interactive": interactive ? 'true' : undefined,
    style: base,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false)
  }, (title || actions) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '10px',
      padding: '11px 16px',
      borderBottom: 'var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--font-size-md)',
      fontWeight: 600,
      color: 'var(--text-primary)'
    }
  }, title), actions && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '6px'
    }
  }, actions)), /*#__PURE__*/React.createElement("div", {
    style: {
      padding
    }
  }, children));
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surface/Card.jsx", error: String((e && e.message) || e) }); }

// design-canvas.jsx
try { (() => {
// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)

/* BEGIN USAGE */
// DesignCanvas.jsx — Figma-ish design canvas wrapper
// Warm gray grid bg + Sections + Artboards + PostIt notes.
// Exports (to window): DesignCanvas, DCSection, DCArtboard, DCPostIt.
// Artboards are reorderable (grip-drag), deletable, labels/titles are
// inline-editable, and any artboard can be opened in a fullscreen focus
// overlay (←/→/Esc). State persists to a .design-canvas.state.json sidecar
// via the host bridge. No assets, no deps.
//
// Usage:
//   <DesignCanvas>
//     <DCSection id="onboarding" title="Onboarding" subtitle="First-run variants">
//       <DCArtboard id="a" label="A · Dusk" width={260} height={480}>…</DCArtboard>
//       <DCArtboard id="b" label="B · Minimal" width={260} height={480}>…</DCArtboard>
//     </DCSection>
//   </DesignCanvas>
//
// Artboards are static design frames, not scroll regions — never use
// height: 100% + overflow: auto/scroll on inner elements; size each artboard
// to fit its content (explicit pixel height, or let it grow).
/* END USAGE */

const DC = {
  bg: '#f0eee9',
  grid: 'rgba(0,0,0,0.06)',
  label: 'rgba(60,50,40,0.7)',
  title: 'rgba(40,30,20,0.85)',
  subtitle: 'rgba(60,50,40,0.6)',
  postitBg: '#fef4a8',
  postitText: '#5a4a2a',
  font: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif'
};

// One-time CSS injection (classes are dc-prefixed so they don't collide with
// the hosted design's own styles).
if (typeof document !== 'undefined' && !document.getElementById('dc-styles')) {
  const s = document.createElement('style');
  s.id = 'dc-styles';
  s.textContent = ['.dc-editable{cursor:text;outline:none;white-space:nowrap;border-radius:3px;padding:0 2px;margin:0 -2px}', '.dc-editable:focus{background:#fff;box-shadow:0 0 0 1.5px #c96442}', '[data-dc-slot]{transition:transform .18s cubic-bezier(.2,.7,.3,1)}', '[data-dc-slot].dc-dragging{transition:none;z-index:10;pointer-events:none}', '[data-dc-slot].dc-dragging .dc-card{box-shadow:0 12px 40px rgba(0,0,0,.25),0 0 0 2px #c96442;transform:scale(1.02)}',
  // isolation:isolate contains artboard content's z-indexes so a
  // z-indexed child (sticky navbar etc.) can't paint over .dc-header or
  // the .dc-menu popover that drops into the top of the card.
  '.dc-card{isolation:isolate;transition:box-shadow .15s,transform .15s}', '.dc-card *{scrollbar-width:none}', '.dc-card *::-webkit-scrollbar{display:none}',
  // Per-artboard header: grip + label on the left, delete/expand on the
  // right. Single flex row; when the artboard's on-screen width is too
  // narrow for both the label yields (ellipsis, then hidden entirely below
  // ~4ch via the container query) and the buttons stay on the row.
  '.dc-header{position:absolute;bottom:100%;left:-4px;margin-bottom:calc(4px * var(--dc-inv-zoom,1));z-index:2;', '  display:flex;align-items:center;container-type:inline-size}', '.dc-labelrow{display:flex;align-items:center;gap:4px;height:24px;flex:1 1 auto;min-width:0}', '.dc-grip{flex:0 0 auto;cursor:grab;display:flex;align-items:center;padding:5px 4px;border-radius:4px;transition:background .12s,opacity .12s}', '.dc-grip:hover{background:rgba(0,0,0,.08)}', '.dc-grip:active{cursor:grabbing}', '.dc-labeltext{flex:1 1 auto;min-width:0;cursor:pointer;border-radius:4px;padding:3px 6px;', '  display:flex;align-items:center;transition:background .12s;overflow:hidden}',
  // Below ~4ch of label room: hide the label entirely, and drop the grip to
  // hover-only (same reveal rule as .dc-btns) so a narrow header is clean
  // until the card is moused.
  '@container (max-width: 110px){', '  .dc-labeltext{display:none}', '  .dc-grip{opacity:0}', '  [data-dc-slot]:hover .dc-grip{opacity:1}', '}', '.dc-labeltext:hover{background:rgba(0,0,0,.05)}', '.dc-labeltext .dc-editable{overflow:hidden;text-overflow:ellipsis;max-width:100%}', '.dc-labeltext .dc-editable:focus{overflow:visible;text-overflow:clip}', '.dc-btns{flex:0 0 auto;margin-left:auto;display:flex;gap:2px;opacity:0;transition:opacity .12s}', '[data-dc-slot]:hover .dc-btns,.dc-btns:has(.dc-menu){opacity:1}', '.dc-expand,.dc-kebab{width:22px;height:22px;border-radius:5px;border:none;cursor:pointer;padding:0;', '  background:transparent;color:rgba(60,50,40,.7);display:flex;align-items:center;justify-content:center;', '  font:inherit;transition:background .12s,color .12s}', '.dc-expand:hover,.dc-kebab:hover{background:rgba(0,0,0,.06);color:#2a251f}',
  // Slot hosting an open menu floats above later siblings (which otherwise
  // paint on top — same z-index:auto, later DOM order) so the popup isn't
  // clipped by the next card.
  '[data-dc-slot]:has(.dc-menu){z-index:10}', '.dc-menu{position:absolute;top:100%;right:0;margin-top:4px;background:#fff;border-radius:8px;', '  box-shadow:0 8px 28px rgba(0,0,0,.18),0 0 0 1px rgba(0,0,0,.05);padding:4px;min-width:160px;z-index:10}', '.dc-menu button{display:block;width:100%;padding:7px 10px;border:0;background:transparent;', '  border-radius:5px;font-family:inherit;font-size:13px;font-weight:500;line-height:1.2;', '  color:#29261b;cursor:pointer;text-align:left;transition:background .12s;white-space:nowrap}', '.dc-menu button:hover{background:rgba(0,0,0,.05)}', '.dc-menu hr{border:0;border-top:1px solid rgba(0,0,0,.08);margin:4px 2px}', '.dc-menu .dc-danger{color:#c96442}', '.dc-menu .dc-danger:hover{background:rgba(201,100,66,.1)}',
  // Chrome (titles / labels / buttons) counter-scales against the viewport
  // zoom so it stays a constant on-screen size. --dc-inv-zoom is set by
  // DCViewport on every transform update and inherits to all descendants —
  // any overlay inside the world (e.g. a TweaksPanel on an artboard) can use
  // it the same way.
  //
  // The header uses transform:scale (out-of-flow, so layout impact doesn't
  // matter) with its world-space width set to card-width / inv-zoom so that
  // after counter-scaling its on-screen width exactly matches the card's —
  // that's what lets the container query + text-overflow behave against the
  // card's visible edge at every zoom level.
  //
  // The section head uses CSS zoom instead of transform so its layout box
  // grows with the counter-scale, pushing the card row down — otherwise the
  // constant-screen-size title would overflow into the (shrinking) world-
  // space gap and overlap the artboard headers at low zoom.
  '.dc-header{width:calc((100% + 4px) / var(--dc-inv-zoom,1));', '  transform:scale(var(--dc-inv-zoom,1));transform-origin:bottom left}', '.dc-sectionhead{zoom:var(--dc-inv-zoom,1)}'].join('\n');
  document.head.appendChild(s);
}
const DCCtx = React.createContext(null);

// Recursively unwrap React.Fragment so <>…</> grouping doesn't hide
// DCSection/DCArtboard children from the type-based walks below.
function dcFlatten(children) {
  const out = [];
  React.Children.forEach(children, c => {
    if (c && c.type === React.Fragment) out.push(...dcFlatten(c.props.children));else out.push(c);
  });
  return out;
}

// ─────────────────────────────────────────────────────────────
// DesignCanvas — stateful wrapper around the pan/zoom viewport.
// Owns runtime state (per-section order, renamed titles/labels, hidden
// artboards, focused artboard). Order/titles/labels/hidden persist to a
// .design-canvas.state.json
// sidecar next to the HTML. Reads go via plain fetch() so the saved
// arrangement is visible anywhere the HTML + sidecar are served together
// (omelette preview, direct link, downloaded zip). Writes go through the
// host's window.omelette bridge — editing requires the omelette runtime.
// Focus is ephemeral.
// ─────────────────────────────────────────────────────────────
const DC_STATE_FILE = '.design-canvas.state.json';
function DesignCanvas({
  children,
  minScale,
  maxScale,
  style
}) {
  const [state, setState] = React.useState({
    sections: {},
    focus: null
  });
  // Hold rendering until the sidecar read settles so the saved order/titles
  // appear on first paint (no source-order flash). didRead gates writes until
  // the read settles so the empty initial state can't clobber a slow read;
  // skipNextWrite suppresses the one echo-write that would otherwise follow
  // hydration.
  const [ready, setReady] = React.useState(false);
  const didRead = React.useRef(false);
  const skipNextWrite = React.useRef(false);
  React.useEffect(() => {
    let off = false;
    fetch('./' + DC_STATE_FILE).then(r => r.ok ? r.json() : null).then(saved => {
      if (off || !saved || !saved.sections) return;
      skipNextWrite.current = true;
      setState(s => ({
        ...s,
        sections: saved.sections
      }));
    }).catch(() => {}).finally(() => {
      didRead.current = true;
      if (!off) setReady(true);
    });
    const t = setTimeout(() => {
      if (!off) setReady(true);
    }, 150);
    return () => {
      off = true;
      clearTimeout(t);
    };
  }, []);
  React.useEffect(() => {
    if (!didRead.current) return;
    if (skipNextWrite.current) {
      skipNextWrite.current = false;
      return;
    }
    const t = setTimeout(() => {
      window.omelette?.writeFile(DC_STATE_FILE, JSON.stringify({
        sections: state.sections
      })).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [state.sections]);

  // Build registries synchronously from children so FocusOverlay can read
  // them in the same render. Fragments are flattened; wrapping in other
  // elements still opts out of focus/reorder.
  const registry = {}; // slotId -> { sectionId, artboard }
  const sectionMeta = {}; // sectionId -> { title, subtitle, slotIds[] }
  const sectionOrder = [];
  dcFlatten(children).forEach(sec => {
    if (!sec || sec.type !== DCSection) return;
    const sid = sec.props.id ?? sec.props.title;
    if (!sid) return;
    sectionOrder.push(sid);
    const persisted = state.sections[sid] || {};
    const abs = [];
    dcFlatten(sec.props.children).forEach(ab => {
      if (!ab || ab.type !== DCArtboard) return;
      const aid = ab.props.id ?? ab.props.label;
      if (aid) abs.push([aid, ab]);
    });
    // hidden is scoped to one source revision — when the agent regenerates
    // (artboard-ID set changes), prior deletes don't apply to new content.
    const srcKey = abs.map(([k]) => k).join('\x1f');
    const hidden = persisted.srcKey === srcKey ? persisted.hidden || [] : [];
    const srcIds = [];
    abs.forEach(([aid, ab]) => {
      if (hidden.includes(aid)) return;
      registry[`${sid}/${aid}`] = {
        sectionId: sid,
        artboard: ab
      };
      srcIds.push(aid);
    });
    const kept = (persisted.order || []).filter(k => srcIds.includes(k));
    sectionMeta[sid] = {
      title: persisted.title ?? sec.props.title,
      subtitle: sec.props.subtitle,
      slotIds: [...kept, ...srcIds.filter(k => !kept.includes(k))]
    };
  });
  const api = React.useMemo(() => ({
    state,
    section: id => state.sections[id] || {},
    patchSection: (id, p) => setState(s => ({
      ...s,
      sections: {
        ...s.sections,
        [id]: {
          ...s.sections[id],
          ...(typeof p === 'function' ? p(s.sections[id] || {}) : p)
        }
      }
    })),
    setFocus: slotId => setState(s => ({
      ...s,
      focus: slotId
    }))
  }), [state]);

  // Esc exits focus; any outside pointerdown commits an in-progress rename.
  React.useEffect(() => {
    const onKey = e => {
      if (e.key === 'Escape') api.setFocus(null);
    };
    const onPd = e => {
      const ae = document.activeElement;
      if (ae && ae.isContentEditable && !ae.contains(e.target)) ae.blur();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPd, true);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPd, true);
    };
  }, [api]);
  return /*#__PURE__*/React.createElement(DCCtx.Provider, {
    value: api
  }, /*#__PURE__*/React.createElement(DCViewport, {
    minScale: minScale,
    maxScale: maxScale,
    style: style
  }, ready && children), state.focus && registry[state.focus] && /*#__PURE__*/React.createElement(DCFocusOverlay, {
    entry: registry[state.focus],
    sectionMeta: sectionMeta,
    sectionOrder: sectionOrder
  }));
}

// ─────────────────────────────────────────────────────────────
// DCViewport — transform-based pan/zoom (internal)
//
// Input mapping (Figma-style):
//   • trackpad pinch  → zoom   (ctrlKey wheel; Safari gesture* events)
//   • trackpad scroll → pan    (two-finger)
//   • mouse wheel     → zoom   (notched; distinguished from trackpad scroll)
//   • middle-drag / primary-drag-on-bg → pan
//
// Transform state lives in a ref and is written straight to the DOM
// (translate3d + will-change) so wheel ticks don't go through React —
// keeps pans at 60fps on dense canvases.
// ─────────────────────────────────────────────────────────────
function DCViewport({
  children,
  minScale = 0.1,
  maxScale = 8,
  style = {}
}) {
  const vpRef = React.useRef(null);
  const worldRef = React.useRef(null);
  const tf = React.useRef({
    x: 0,
    y: 0,
    scale: 1
  });
  // Persist viewport across reloads so the user lands back where they were
  // after an agent edit or browser refresh. The sandbox origin is already
  // per-project; pathname keeps multiple canvas files in one project apart.
  const tfKey = 'dc-viewport:' + location.pathname;
  const saveT = React.useRef(0);
  const lastPostedScale = React.useRef();
  const apply = React.useCallback(() => {
    const {
      x,
      y,
      scale
    } = tf.current;
    const el = worldRef.current;
    if (!el) return;
    el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${scale})`;
    // Exposed for zoom-invariant chrome (labels, buttons, TweaksPanel).
    el.style.setProperty('--dc-inv-zoom', String(1 / scale));
    // Keep the host toolbar's % readout in sync with the canvas scale. Pan
    // ticks leave scale unchanged — skip the cross-frame post for those.
    if (lastPostedScale.current !== scale) {
      lastPostedScale.current = scale;
      window.parent.postMessage({
        type: '__dc_zoom',
        scale
      }, '*');
    }
    clearTimeout(saveT.current);
    saveT.current = setTimeout(() => {
      try {
        localStorage.setItem(tfKey, JSON.stringify(tf.current));
      } catch {}
    }, 200);
  }, [tfKey]);
  React.useLayoutEffect(() => {
    const flush = () => {
      clearTimeout(saveT.current);
      try {
        localStorage.setItem(tfKey, JSON.stringify(tf.current));
      } catch {}
    };
    try {
      const s = JSON.parse(localStorage.getItem(tfKey) || 'null');
      if (s && Number.isFinite(s.x) && Number.isFinite(s.y) && Number.isFinite(s.scale)) {
        tf.current = {
          x: s.x,
          y: s.y,
          scale: Math.min(maxScale, Math.max(minScale, s.scale))
        };
        apply();
      }
    } catch {}
    // Flush on pagehide and unmount so a reload within the 200ms debounce
    // window doesn't drop the last pan/zoom.
    window.addEventListener('pagehide', flush);
    return () => {
      window.removeEventListener('pagehide', flush);
      flush();
    };
  }, []);
  React.useEffect(() => {
    const vp = vpRef.current;
    if (!vp) return;
    const zoomAt = (cx, cy, factor) => {
      const r = vp.getBoundingClientRect();
      const px = cx - r.left,
        py = cy - r.top;
      const t = tf.current;
      const next = Math.min(maxScale, Math.max(minScale, t.scale * factor));
      const k = next / t.scale;
      // --dc-inv-zoom consumers (.dc-sectionhead's CSS zoom, each section's
      // marginBottom) reflow on every scale change, vertically shifting the
      // world layout — so a world point mathematically pinned under the cursor
      // drifts as you zoom (content creeps up on zoom-in, down on zoom-out).
      // Anchor the DOM element under the cursor instead: record its screen Y,
      // apply the transform + --dc-inv-zoom, then cancel whatever vertical
      // drift the reflow introduced so it stays put on screen.
      let marker = null,
        markerY0 = 0;
      if (k !== 1) {
        const hit = document.elementFromPoint(cx, cy);
        marker = hit && hit.closest ? hit.closest('[data-dc-slot],[data-dc-section]') : null;
        if (marker) markerY0 = marker.getBoundingClientRect().top;
      }
      // keep the world point under the cursor fixed
      t.x = px - (px - t.x) * k;
      t.y = py - (py - t.y) * k;
      t.scale = next;
      apply();
      if (marker) {
        // A pure zoom around (cx, cy) maps screen Y → cy + (Y - cy) * k. Any
        // departure after the --dc-inv-zoom reflow is the layout drift.
        const drift = marker.getBoundingClientRect().top - (cy + (markerY0 - cy) * k);
        if (Math.abs(drift) > 0.1) {
          t.y -= drift;
          apply();
        }
      }
    };

    // Mouse-wheel vs trackpad-scroll heuristic. A physical wheel sends
    // line-mode deltas (Firefox) or large integer pixel deltas with no X
    // component (Chrome/Safari, typically multiples of 100/120). Trackpad
    // two-finger scroll sends small/fractional pixel deltas, often with
    // non-zero deltaX. ctrlKey is set by the browser for trackpad pinch.
    const isMouseWheel = e => e.deltaMode !== 0 || e.deltaX === 0 && Number.isInteger(e.deltaY) && Math.abs(e.deltaY) >= 40;
    const onWheel = e => {
      e.preventDefault();
      if (isGesturing) return; // Safari: gesture* owns the pinch — discard concurrent wheels
      if ((e.ctrlKey || e.metaKey) && !isMouseWheel(e)) {
        // trackpad pinch, or ctrl/cmd + smooth-scroll mouse. Notched
        // wheels fall through to the fixed-step branch below.
        zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * 0.01));
      } else if (isMouseWheel(e)) {
        // notched mouse wheel — fixed-ratio step per click
        zoomAt(e.clientX, e.clientY, Math.exp(-Math.sign(e.deltaY) * 0.18));
      } else {
        // trackpad two-finger scroll — pan
        tf.current.x -= e.deltaX;
        tf.current.y -= e.deltaY;
        apply();
      }
    };

    // Safari sends native gesture* events for trackpad pinch with a smooth
    // e.scale; preferring these over the ctrl+wheel fallback gives a much
    // better feel there. No-ops on other browsers. Safari also fires
    // ctrlKey wheel events during the same pinch — isGesturing makes
    // onWheel drop those entirely so they neither zoom nor pan.
    let gsBase = 1;
    let isGesturing = false;
    const onGestureStart = e => {
      e.preventDefault();
      isGesturing = true;
      gsBase = tf.current.scale;
    };
    const onGestureChange = e => {
      e.preventDefault();
      zoomAt(e.clientX, e.clientY, gsBase * e.scale / tf.current.scale);
    };
    const onGestureEnd = e => {
      e.preventDefault();
      isGesturing = false;
    };

    // Drag-pan: middle button anywhere, or primary button on canvas
    // background (anything that isn't an artboard or an inline editor).
    let drag = null;
    const onPointerDown = e => {
      const onBg = !e.target.closest('[data-dc-slot], .dc-editable');
      if (!(e.button === 1 || e.button === 0 && onBg)) return;
      e.preventDefault();
      vp.setPointerCapture(e.pointerId);
      drag = {
        id: e.pointerId,
        lx: e.clientX,
        ly: e.clientY
      };
      vp.style.cursor = 'grabbing';
    };
    const onPointerMove = e => {
      if (!drag || e.pointerId !== drag.id) return;
      tf.current.x += e.clientX - drag.lx;
      tf.current.y += e.clientY - drag.ly;
      drag.lx = e.clientX;
      drag.ly = e.clientY;
      apply();
    };
    const onPointerUp = e => {
      if (!drag || e.pointerId !== drag.id) return;
      vp.releasePointerCapture(e.pointerId);
      drag = null;
      vp.style.cursor = '';
    };

    // Host-driven zoom (toolbar % menu). Zooms around viewport centre so the
    // visible midpoint stays fixed — matching the host's iframe-zoom feel.
    const onHostMsg = e => {
      const d = e.data;
      if (d && d.type === '__dc_set_zoom' && typeof d.scale === 'number') {
        const r = vp.getBoundingClientRect();
        zoomAt(r.left + r.width / 2, r.top + r.height / 2, d.scale / tf.current.scale);
      } else if (d && d.type === '__dc_probe') {
        // Host's [readyGen] reset asks whether a canvas is present; it
        // fires on the iframe's native 'load', which for canvases with
        // images/fonts is after our mount-time announce, so re-announce.
        // Clear the pan-tick guard so apply() re-posts the current scale
        // even if it's unchanged — the host just reset dcScale to 1.
        window.parent.postMessage({
          type: '__dc_present'
        }, '*');
        lastPostedScale.current = undefined;
        apply();
      }
    };
    window.addEventListener('message', onHostMsg);
    // Announce canvas mode so the host toolbar proxies its % control here
    // instead of scaling the iframe element (which would just shrink the
    // viewport window of an infinite canvas). The apply() that follows emits
    // the initial __dc_zoom so the toolbar % is correct before first pinch.
    // lastPostedScale reset mirrors the __dc_probe handler: the layout
    // effect's restore-path apply() may already have posted the restored
    // scale (before __dc_present), so clear the guard to re-post it in order.
    window.parent.postMessage({
      type: '__dc_present'
    }, '*');
    lastPostedScale.current = undefined;
    apply();
    vp.addEventListener('wheel', onWheel, {
      passive: false
    });
    vp.addEventListener('gesturestart', onGestureStart, {
      passive: false
    });
    vp.addEventListener('gesturechange', onGestureChange, {
      passive: false
    });
    vp.addEventListener('gestureend', onGestureEnd, {
      passive: false
    });
    vp.addEventListener('pointerdown', onPointerDown);
    vp.addEventListener('pointermove', onPointerMove);
    vp.addEventListener('pointerup', onPointerUp);
    vp.addEventListener('pointercancel', onPointerUp);
    return () => {
      window.removeEventListener('message', onHostMsg);
      vp.removeEventListener('wheel', onWheel);
      vp.removeEventListener('gesturestart', onGestureStart);
      vp.removeEventListener('gesturechange', onGestureChange);
      vp.removeEventListener('gestureend', onGestureEnd);
      vp.removeEventListener('pointerdown', onPointerDown);
      vp.removeEventListener('pointermove', onPointerMove);
      vp.removeEventListener('pointerup', onPointerUp);
      vp.removeEventListener('pointercancel', onPointerUp);
    };
  }, [apply, minScale, maxScale]);
  const gridSvg = `url("data:image/svg+xml,%3Csvg width='120' height='120' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M120 0H0v120' fill='none' stroke='${encodeURIComponent(DC.grid)}' stroke-width='1'/%3E%3C/svg%3E")`;
  return /*#__PURE__*/React.createElement("div", {
    ref: vpRef,
    className: "design-canvas",
    style: {
      height: '100vh',
      width: '100vw',
      background: DC.bg,
      overflow: 'hidden',
      overscrollBehavior: 'none',
      touchAction: 'none',
      position: 'relative',
      fontFamily: DC.font,
      boxSizing: 'border-box',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    ref: worldRef,
    style: {
      position: 'absolute',
      top: 0,
      left: 0,
      transformOrigin: '0 0',
      willChange: 'transform',
      width: 'max-content',
      minWidth: '100%',
      minHeight: '100%',
      padding: '60px 0 80px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: -6000,
      backgroundImage: gridSvg,
      backgroundSize: '120px 120px',
      pointerEvents: 'none',
      zIndex: -1
    }
  }), children));
}

// ─────────────────────────────────────────────────────────────
// DCSection — editable title + h-row of artboards in persisted order
// ─────────────────────────────────────────────────────────────
function DCSection({
  id,
  title,
  subtitle,
  children,
  gap = 48
}) {
  const ctx = React.useContext(DCCtx);
  const sid = id ?? title;
  const all = React.Children.toArray(dcFlatten(children));
  const artboards = all.filter(c => c && c.type === DCArtboard);
  const rest = all.filter(c => !(c && c.type === DCArtboard));
  const sec = ctx && sid && ctx.section(sid) || {};
  // Must match DesignCanvas's srcKey computation exactly (it filters falsy
  // IDs), or onDelete persists a srcKey that DesignCanvas never recognizes.
  const allIds = artboards.map(a => a.props.id ?? a.props.label).filter(Boolean);
  const srcKey = allIds.join('\x1f');
  const hidden = sec.srcKey === srcKey ? sec.hidden || [] : [];
  const srcOrder = allIds.filter(k => !hidden.includes(k));
  const order = React.useMemo(() => {
    const kept = (sec.order || []).filter(k => srcOrder.includes(k));
    return [...kept, ...srcOrder.filter(k => !kept.includes(k))];
  }, [sec.order, srcOrder.join('|')]);
  const byId = Object.fromEntries(artboards.map(a => [a.props.id ?? a.props.label, a]));

  // marginBottom counter-scales so the on-screen gap between sections stays
  // constant — otherwise at low zoom the (world-space) gap collapses while
  // the screen-constant sectionhead below it doesn't, and the title reads as
  // belonging to the section above. paddingBottom below is just enough for
  // the 24px artboard-header (abs-positioned above each card) plus ~8px, so
  // the title sits tight against its own row at every zoom.
  return /*#__PURE__*/React.createElement("div", {
    "data-dc-section": sid,
    style: {
      marginBottom: 'calc(80px * var(--dc-inv-zoom, 1))',
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 60px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "dc-sectionhead",
    style: {
      paddingBottom: 36
    }
  }, /*#__PURE__*/React.createElement(DCEditable, {
    tag: "div",
    value: sec.title ?? title,
    onChange: v => ctx && sid && ctx.patchSection(sid, {
      title: v
    }),
    style: {
      fontSize: 28,
      fontWeight: 600,
      color: DC.title,
      letterSpacing: -0.4,
      marginBottom: 6,
      display: 'inline-block'
    }
  }), subtitle && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 16,
      color: DC.subtitle
    }
  }, subtitle))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap,
      padding: '0 60px',
      alignItems: 'flex-start',
      width: 'max-content'
    }
  }, order.map(k => /*#__PURE__*/React.createElement(DCArtboardFrame, {
    key: k,
    sectionId: sid,
    artboard: byId[k],
    order: order,
    label: (sec.labels || {})[k] ?? byId[k].props.label,
    onRename: v => ctx && ctx.patchSection(sid, x => ({
      labels: {
        ...x.labels,
        [k]: v
      }
    })),
    onReorder: next => ctx && ctx.patchSection(sid, {
      order: next
    }),
    onDelete: () => ctx && ctx.patchSection(sid, x => ({
      hidden: [...(x.srcKey === srcKey ? x.hidden || [] : []), k],
      srcKey
    })),
    onFocus: () => ctx && ctx.setFocus(`${sid}/${k}`)
  }))), rest);
}

// DCArtboard — marker; rendered by DCArtboardFrame via DCSection.
function DCArtboard() {
  return null;
}

// Per-artboard export (kind: 'png' | 'html'). Both paths share the same
// self-contained clone: computed styles baked in, @font-face / <img> /
// inline-style background-image urls inlined as data URIs. PNG wraps the
// clone in foreignObject→canvas at 3× the artboard's natural width×height
// (same pipeline the host uses for page captures); HTML wraps it in a
// minimal standalone document. Both are independent of viewport zoom.
async function dcExport(node, w, h, name, kind) {
  try {
    await document.fonts.ready;
  } catch {}
  const toDataURL = url => fetch(url).then(r => r.blob()).then(b => new Promise(res => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.onerror = () => res(url);
    fr.readAsDataURL(b);
  })).catch(() => url);

  // Collect @font-face rules. ss.cssRules throws SecurityError on
  // cross-origin sheets (e.g. fonts.googleapis.com) — in that case fetch
  // the CSS text directly (those endpoints send ACAO:*) and regex-extract
  // the blocks. @import and @media/@supports are walked so nested
  // @font-face rules aren't missed.
  const fontRules = [],
    pending = [],
    seen = new Set();
  const scrapeCss = href => {
    if (seen.has(href)) return;
    seen.add(href);
    pending.push(fetch(href).then(r => r.text()).then(css => {
      for (const m of css.match(/@font-face\s*{[^}]*}/g) || []) fontRules.push({
        css: m,
        base: href
      });
      for (const m of css.matchAll(/@import\s+(?:url\()?['"]?([^'")\s;]+)/g)) scrapeCss(new URL(m[1], href).href);
    }).catch(() => {}));
  };
  const walk = (rules, base) => {
    for (const r of rules) {
      if (r.type === CSSRule.FONT_FACE_RULE) fontRules.push({
        css: r.cssText,
        base
      });else if (r.type === CSSRule.IMPORT_RULE && r.styleSheet) {
        const ibase = r.styleSheet.href || base;
        try {
          walk(r.styleSheet.cssRules, ibase);
        } catch {
          scrapeCss(ibase);
        }
      } else if (r.cssRules) walk(r.cssRules, base);
    }
  };
  for (const ss of document.styleSheets) {
    const base = ss.href || location.href;
    try {
      walk(ss.cssRules, base);
    } catch {
      if (ss.href) scrapeCss(ss.href);
    }
  }
  while (pending.length) await pending.shift();
  const fontCss = (await Promise.all(fontRules.map(async rule => {
    let out = rule.css,
      m;
    const re = /url\((['"]?)([^'")]+)\1\)/g;
    while (m = re.exec(rule.css)) {
      if (m[2].indexOf('data:') === 0) continue;
      let abs;
      try {
        abs = new URL(m[2], rule.base).href;
      } catch {
        continue;
      }
      out = out.split(m[0]).join('url("' + (await toDataURL(abs)) + '")');
    }
    return out;
  }))).join('\n');
  const cloneStyled = src => {
    if (src.nodeType === 8 || src.nodeType === 1 && src.tagName === 'SCRIPT') return document.createTextNode('');
    const dst = src.cloneNode(false);
    if (src.nodeType === 1) {
      const cs = getComputedStyle(src);
      let txt = '';
      for (let i = 0; i < cs.length; i++) txt += cs[i] + ':' + cs.getPropertyValue(cs[i]) + ';';
      dst.setAttribute('style', txt + 'animation:none;transition:none;');
      if (src.tagName === 'CANVAS') try {
        const im = document.createElement('img');
        im.src = src.toDataURL();
        im.setAttribute('style', txt);
        return im;
      } catch {}
    }
    for (let c = src.firstChild; c; c = c.nextSibling) dst.appendChild(cloneStyled(c));
    return dst;
  };
  const clone = cloneStyled(node);
  clone.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
  // Drop the card's own shadow/radius so the export is a flush w×h rect;
  // the artboard's own background (if any) is already in the computed style.
  clone.style.boxShadow = 'none';
  clone.style.borderRadius = '0';
  const jobs = [];
  clone.querySelectorAll('img').forEach(el => {
    const s = el.getAttribute('src');
    if (s && s.indexOf('data:') !== 0) jobs.push(toDataURL(el.src).then(d => el.setAttribute('src', d)));
  });
  [clone, ...clone.querySelectorAll('*')].forEach(el => {
    const bg = el.style.backgroundImage;
    if (!bg) return;
    let m;
    const re = /url\(["']?([^"')]+)["']?\)/g;
    while (m = re.exec(bg)) {
      const tok = m[0],
        url = m[1];
      if (url.indexOf('data:') === 0) continue;
      jobs.push(toDataURL(url).then(d => {
        el.style.backgroundImage = el.style.backgroundImage.split(tok).join('url("' + d + '")');
      }));
    }
  });
  await Promise.all(jobs);
  const xml = new XMLSerializer().serializeToString(clone);
  const save = (blob, ext) => {
    if (!blob) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name + '.' + ext;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  if (kind === 'html') {
    const html = '<!doctype html><html><head><meta charset="utf-8"><title>' + name + '</title>' + (fontCss ? '<style>' + fontCss + '</style>' : '') + '</head><body style="margin:0">' + xml + '</body></html>';
    return save(new Blob([html], {
      type: 'text/html'
    }), 'html');
  }

  // PNG: the SVG's own width/height must be the output resolution — an
  // <img>-loaded SVG rasterizes at its intrinsic size, so sizing it at 1×
  // and ctx.scale()-ing up would just upscale a 1× bitmap. viewBox maps the
  // w×h foreignObject onto the px·w × px·h SVG canvas so the browser renders
  // the HTML at full resolution.
  const px = 3;
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + w * px + '" height="' + h * px + '" viewBox="0 0 ' + w + ' ' + h + '"><foreignObject width="' + w + '" height="' + h + '">' + (fontCss ? '<style><![CDATA[' + fontCss + ']]></style>' : '') + xml + '</foreignObject></svg>';
  const img = new Image();
  await new Promise((res, rej) => {
    img.onload = res;
    img.onerror = () => rej(new Error('svg load failed'));
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  });
  const cv = document.createElement('canvas');
  cv.width = w * px;
  cv.height = h * px;
  cv.getContext('2d').drawImage(img, 0, 0);
  cv.toBlob(blob => save(blob, 'png'), 'image/png');
}
function DCArtboardFrame({
  sectionId,
  artboard,
  label,
  order,
  onRename,
  onReorder,
  onFocus,
  onDelete
}) {
  const {
    id: rawId,
    label: rawLabel,
    width = 260,
    height = 480,
    children,
    style = {}
  } = artboard.props;
  const id = rawId ?? rawLabel;
  const ref = React.useRef(null);
  const cardRef = React.useRef(null);
  const menuRef = React.useRef(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);

  // ⋯ menu: close on any outside pointerdown. Two-click delete lives inside
  // the menu — first click arms the row, second commits; closing disarms.
  React.useEffect(() => {
    if (!menuOpen) {
      setConfirming(false);
      return;
    }
    const off = e => {
      if (!menuRef.current || !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    document.addEventListener('pointerdown', off, true);
    return () => document.removeEventListener('pointerdown', off, true);
  }, [menuOpen]);
  const doExport = kind => {
    setMenuOpen(false);
    if (!cardRef.current) return;
    const name = String(label || id || 'artboard').replace(/[^\w\s.-]+/g, '_');
    dcExport(cardRef.current, width, height, name, kind).catch(e => console.error('[design-canvas] export failed:', e));
  };

  // Live drag-reorder: dragged card sticks to cursor; siblings slide into
  // their would-be slots in real time via transforms. DOM order only
  // changes on drop.
  const onGripDown = e => {
    e.preventDefault();
    e.stopPropagation();
    const me = ref.current;
    // translateX is applied in local (pre-scale) space but pointer deltas and
    // getBoundingClientRect().left are screen-space — divide by the viewport's
    // current scale so the dragged card tracks the cursor at any zoom level.
    const scale = me.getBoundingClientRect().width / me.offsetWidth || 1;
    const peers = Array.from(document.querySelectorAll(`[data-dc-section="${sectionId}"] [data-dc-slot]`));
    const homes = peers.map(el => ({
      el,
      id: el.dataset.dcSlot,
      x: el.getBoundingClientRect().left
    }));
    const slotXs = homes.map(h => h.x);
    const startIdx = order.indexOf(id);
    const startX = e.clientX;
    let liveOrder = order.slice();
    me.classList.add('dc-dragging');
    const layout = () => {
      for (const h of homes) {
        if (h.id === id) continue;
        const slot = liveOrder.indexOf(h.id);
        h.el.style.transform = `translateX(${(slotXs[slot] - h.x) / scale}px)`;
      }
    };
    const move = ev => {
      const dx = ev.clientX - startX;
      me.style.transform = `translateX(${dx / scale}px)`;
      const cur = homes[startIdx].x + dx;
      let nearest = 0,
        best = Infinity;
      for (let i = 0; i < slotXs.length; i++) {
        const d = Math.abs(slotXs[i] - cur);
        if (d < best) {
          best = d;
          nearest = i;
        }
      }
      if (liveOrder.indexOf(id) !== nearest) {
        liveOrder = order.filter(k => k !== id);
        liveOrder.splice(nearest, 0, id);
        layout();
      }
    };
    const up = () => {
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', up);
      const finalSlot = liveOrder.indexOf(id);
      me.classList.remove('dc-dragging');
      me.style.transform = `translateX(${(slotXs[finalSlot] - homes[startIdx].x) / scale}px)`;
      // After the settle transition, kill transitions + clear transforms +
      // commit the reorder in the same frame so there's no visual snap-back.
      setTimeout(() => {
        for (const h of homes) {
          h.el.style.transition = 'none';
          h.el.style.transform = '';
        }
        if (liveOrder.join('|') !== order.join('|')) onReorder(liveOrder);
        requestAnimationFrame(() => requestAnimationFrame(() => {
          for (const h of homes) h.el.style.transition = '';
        }));
      }, 180);
    };
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', up);
  };
  return /*#__PURE__*/React.createElement("div", {
    ref: ref,
    "data-dc-slot": id,
    style: {
      position: 'relative',
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "dc-header",
    "data-omelette-chrome": "",
    style: {
      color: DC.label
    },
    onPointerDown: e => e.stopPropagation()
  }, /*#__PURE__*/React.createElement("div", {
    className: "dc-labelrow"
  }, /*#__PURE__*/React.createElement("div", {
    className: "dc-grip",
    onPointerDown: onGripDown,
    title: "Drag to reorder"
  }, /*#__PURE__*/React.createElement("svg", {
    width: "9",
    height: "13",
    viewBox: "0 0 9 13",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "2",
    cy: "2",
    r: "1.1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "7",
    cy: "2",
    r: "1.1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "2",
    cy: "6.5",
    r: "1.1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "7",
    cy: "6.5",
    r: "1.1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "2",
    cy: "11",
    r: "1.1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "7",
    cy: "11",
    r: "1.1"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "dc-labeltext",
    onClick: onFocus,
    title: "Click to focus"
  }, /*#__PURE__*/React.createElement(DCEditable, {
    value: label,
    onChange: onRename,
    onClick: e => e.stopPropagation(),
    style: {
      fontSize: 15,
      fontWeight: 500,
      color: DC.label,
      lineHeight: 1
    }
  }))), /*#__PURE__*/React.createElement("div", {
    className: "dc-btns"
  }, /*#__PURE__*/React.createElement("div", {
    ref: menuRef,
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("button", {
    className: "dc-kebab",
    title: "More",
    onClick: () => setMenuOpen(o => !o)
  }, /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 12 12",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "2.5",
    cy: "6",
    r: "1.1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "6",
    cy: "6",
    r: "1.1"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "9.5",
    cy: "6",
    r: "1.1"
  }))), menuOpen && /*#__PURE__*/React.createElement("div", {
    className: "dc-menu",
    onPointerDown: e => e.stopPropagation()
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => doExport('png')
  }, "Download PNG"), /*#__PURE__*/React.createElement("button", {
    onClick: () => doExport('html')
  }, "Download HTML"), /*#__PURE__*/React.createElement("hr", null), /*#__PURE__*/React.createElement("button", {
    className: "dc-danger",
    onClick: () => {
      if (confirming) {
        setMenuOpen(false);
        onDelete();
      } else setConfirming(true);
    }
  }, confirming ? 'Click again to delete' : 'Delete'))), /*#__PURE__*/React.createElement("button", {
    className: "dc-expand",
    onClick: onFocus,
    title: "Focus"
  }, /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 12 12",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M7 1h4v4M5 11H1V7M11 1L7.5 4.5M1 11l3.5-3.5"
  }))))), /*#__PURE__*/React.createElement("div", {
    ref: cardRef,
    className: "dc-card",
    style: {
      borderRadius: 2,
      boxShadow: '0 1px 3px rgba(0,0,0,.08),0 4px 16px rgba(0,0,0,.06)',
      overflow: 'hidden',
      width,
      height,
      background: '#fff',
      ...style
    }
  }, children || /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#bbb',
      fontSize: 13,
      fontFamily: DC.font
    }
  }, id)));
}

// Inline rename — commits on blur or Enter.
function DCEditable({
  value,
  onChange,
  style,
  tag = 'span',
  onClick
}) {
  const T = tag;
  return /*#__PURE__*/React.createElement(T, {
    className: "dc-editable",
    contentEditable: true,
    suppressContentEditableWarning: true,
    onClick: onClick,
    onPointerDown: e => e.stopPropagation(),
    onBlur: e => onChange && onChange(e.currentTarget.textContent),
    onKeyDown: e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        e.currentTarget.blur();
      }
    },
    style: style
  }, value);
}

// ─────────────────────────────────────────────────────────────
// Focus mode — overlay one artboard; ←/→ within section, ↑/↓ across
// sections, Esc or backdrop click to exit.
// ─────────────────────────────────────────────────────────────
function DCFocusOverlay({
  entry,
  sectionMeta,
  sectionOrder
}) {
  const ctx = React.useContext(DCCtx);
  const {
    sectionId,
    artboard
  } = entry;
  const sec = ctx.section(sectionId);
  const meta = sectionMeta[sectionId];
  const peers = meta.slotIds;
  const aid = artboard.props.id ?? artboard.props.label;
  const idx = peers.indexOf(aid);
  const secIdx = sectionOrder.indexOf(sectionId);
  const go = d => {
    const n = peers[(idx + d + peers.length) % peers.length];
    if (n) ctx.setFocus(`${sectionId}/${n}`);
  };
  const goSection = d => {
    // Sections whose artboards are all deleted have slotIds:[] — step past
    // them to the next non-empty section so ↑/↓ doesn't dead-end.
    const n = sectionOrder.length;
    for (let i = 1; i < n; i++) {
      const ns = sectionOrder[((secIdx + d * i) % n + n) % n];
      const first = sectionMeta[ns] && sectionMeta[ns].slotIds[0];
      if (first) {
        ctx.setFocus(`${ns}/${first}`);
        return;
      }
    }
  };
  React.useEffect(() => {
    const k = e => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        go(-1);
      }
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        go(1);
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        goSection(-1);
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        goSection(1);
      }
    };
    document.addEventListener('keydown', k);
    return () => document.removeEventListener('keydown', k);
  });
  const {
    width = 260,
    height = 480,
    children
  } = artboard.props;
  const [vp, setVp] = React.useState({
    w: window.innerWidth,
    h: window.innerHeight
  });
  React.useEffect(() => {
    const r = () => setVp({
      w: window.innerWidth,
      h: window.innerHeight
    });
    window.addEventListener('resize', r);
    return () => window.removeEventListener('resize', r);
  }, []);
  const scale = Math.max(0.1, Math.min((vp.w - 200) / width, (vp.h - 260) / height, 2));
  const [ddOpen, setDd] = React.useState(false);
  const Arrow = ({
    dir,
    onClick
  }) => /*#__PURE__*/React.createElement("button", {
    onClick: e => {
      e.stopPropagation();
      onClick();
    },
    style: {
      position: 'absolute',
      top: '50%',
      [dir]: 28,
      transform: 'translateY(-50%)',
      border: 'none',
      background: 'rgba(255,255,255,.08)',
      color: 'rgba(255,255,255,.9)',
      width: 44,
      height: 44,
      borderRadius: 22,
      fontSize: 18,
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'background .15s'
    },
    onMouseEnter: e => e.currentTarget.style.background = 'rgba(255,255,255,.18)',
    onMouseLeave: e => e.currentTarget.style.background = 'rgba(255,255,255,.08)'
  }, /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 18 18",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: dir === 'left' ? 'M11 3L5 9l6 6' : 'M7 3l6 6-6 6'
  })));

  // Portal to body so position:fixed is the real viewport regardless of any
  // transform on DesignCanvas's ancestors (including the canvas zoom itself).
  return ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
    onClick: () => ctx.setFocus(null),
    onWheel: e => e.preventDefault(),
    style: {
      position: 'fixed',
      inset: 0,
      zIndex: 100,
      background: 'rgba(24,20,16,.6)',
      backdropFilter: 'blur(14px)',
      fontFamily: DC.font,
      color: '#fff'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      height: 72,
      display: 'flex',
      alignItems: 'flex-start',
      padding: '16px 20px 0',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setDd(o => !o),
    style: {
      border: 'none',
      background: 'transparent',
      color: '#fff',
      cursor: 'pointer',
      padding: '6px 8px',
      borderRadius: 6,
      textAlign: 'left',
      fontFamily: 'inherit'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 18,
      fontWeight: 600,
      letterSpacing: -0.3
    }
  }, meta.title), /*#__PURE__*/React.createElement("svg", {
    width: "11",
    height: "11",
    viewBox: "0 0 11 11",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    style: {
      opacity: .7
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "M2 4l3.5 3.5L9 4"
  }))), meta.subtitle && /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'block',
      fontSize: 13,
      opacity: .6,
      fontWeight: 400,
      marginTop: 2
    }
  }, meta.subtitle)), ddOpen && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: '100%',
      left: 0,
      marginTop: 4,
      background: '#2a251f',
      borderRadius: 8,
      boxShadow: '0 8px 32px rgba(0,0,0,.4)',
      padding: 4,
      minWidth: 200,
      zIndex: 10
    }
  }, sectionOrder.filter(sid => sectionMeta[sid].slotIds.length).map(sid => /*#__PURE__*/React.createElement("button", {
    key: sid,
    onClick: () => {
      setDd(false);
      const f = sectionMeta[sid].slotIds[0];
      if (f) ctx.setFocus(`${sid}/${f}`);
    },
    style: {
      display: 'block',
      width: '100%',
      textAlign: 'left',
      border: 'none',
      cursor: 'pointer',
      background: sid === sectionId ? 'rgba(255,255,255,.1)' : 'transparent',
      color: '#fff',
      padding: '8px 12px',
      borderRadius: 5,
      fontSize: 14,
      fontWeight: sid === sectionId ? 600 : 400,
      fontFamily: 'inherit'
    }
  }, sectionMeta[sid].title)))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("button", {
    onClick: () => ctx.setFocus(null),
    onMouseEnter: e => e.currentTarget.style.background = 'rgba(255,255,255,.12)',
    onMouseLeave: e => e.currentTarget.style.background = 'transparent',
    style: {
      border: 'none',
      background: 'transparent',
      color: 'rgba(255,255,255,.7)',
      width: 32,
      height: 32,
      borderRadius: 16,
      fontSize: 20,
      cursor: 'pointer',
      lineHeight: 1,
      transition: 'background .12s'
    }
  }, "\xD7")), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 64,
      bottom: 56,
      left: 100,
      right: 100,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width: width * scale,
      height: height * scale,
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width,
      height,
      transform: `scale(${scale})`,
      transformOrigin: 'top left',
      background: '#fff',
      borderRadius: 2,
      overflow: 'hidden',
      boxShadow: '0 20px 80px rgba(0,0,0,.4)'
    }
  }, children || /*#__PURE__*/React.createElement("div", {
    style: {
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#bbb'
    }
  }, aid))), /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      fontSize: 14,
      fontWeight: 500,
      opacity: .85,
      textAlign: 'center'
    }
  }, (sec.labels || {})[aid] ?? artboard.props.label, /*#__PURE__*/React.createElement("span", {
    style: {
      opacity: .5,
      marginLeft: 10,
      fontVariantNumeric: 'tabular-nums'
    }
  }, idx + 1, " / ", peers.length))), /*#__PURE__*/React.createElement(Arrow, {
    dir: "left",
    onClick: () => go(-1)
  }), /*#__PURE__*/React.createElement(Arrow, {
    dir: "right",
    onClick: () => go(1)
  }), /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      position: 'absolute',
      bottom: 20,
      left: '50%',
      transform: 'translateX(-50%)',
      display: 'flex',
      gap: 8
    }
  }, peers.map((p, i) => /*#__PURE__*/React.createElement("button", {
    key: p,
    onClick: () => ctx.setFocus(`${sectionId}/${p}`),
    style: {
      border: 'none',
      padding: 0,
      cursor: 'pointer',
      width: 6,
      height: 6,
      borderRadius: 3,
      background: i === idx ? '#fff' : 'rgba(255,255,255,.3)'
    }
  })))), document.body);
}

// ─────────────────────────────────────────────────────────────
// Post-it — absolute-positioned sticky note
// ─────────────────────────────────────────────────────────────
function DCPostIt({
  children,
  top,
  left,
  right,
  bottom,
  rotate = -2,
  width = 180
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top,
      left,
      right,
      bottom,
      width,
      background: DC.postitBg,
      padding: '14px 16px',
      fontFamily: '"Comic Sans MS", "Marker Felt", "Segoe Print", cursive',
      fontSize: 14,
      lineHeight: 1.4,
      color: DC.postitText,
      boxShadow: '0 2px 8px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
      transform: `rotate(${rotate}deg)`,
      zIndex: 5
    }
  }, children);
}
Object.assign(window, {
  DesignCanvas,
  DCSection,
  DCArtboard,
  DCPostIt
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "design-canvas.jsx", error: String((e && e.message) || e) }); }

// tweaks-panel.jsx
try { (() => {
// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)

/* BEGIN USAGE */
// tweaks-panel.jsx
// Reusable Tweaks shell + form-control helpers.
// Exports (to window): useTweaks, TweaksPanel, TweakSection, TweakRow, TweakSlider,
//   TweakToggle, TweakRadio, TweakSelect, TweakText, TweakNumber, TweakColor, TweakButton.
//
// Owns the host protocol (listens for __activate_edit_mode / __deactivate_edit_mode,
// posts __edit_mode_available / __edit_mode_set_keys / __edit_mode_dismissed) so
// individual prototypes don't re-roll it. Ships a consistent set of controls so you
// don't hand-draw <input type="range">, segmented radios, steppers, etc.
//
// Usage (in an HTML file that loads React + Babel):
//
//   const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
//     "primaryColor": "#D97757",
//     "palette": ["#D97757", "#29261b", "#f6f4ef"],
//     "fontSize": 16,
//     "density": "regular",
//     "dark": false
//   }/*EDITMODE-END*/;
//
//   function App() {
//     const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
//     return (
//       <div style={{ fontSize: t.fontSize, color: t.primaryColor }}>
//         Hello
//         <TweaksPanel>
//           <TweakSection label="Typography" />
//           <TweakSlider label="Font size" value={t.fontSize} min={10} max={32} unit="px"
//                        onChange={(v) => setTweak('fontSize', v)} />
//           <TweakRadio  label="Density" value={t.density}
//                        options={['compact', 'regular', 'comfy']}
//                        onChange={(v) => setTweak('density', v)} />
//           <TweakSection label="Theme" />
//           <TweakColor  label="Primary" value={t.primaryColor}
//                        options={['#D97757', '#2A6FDB', '#1F8A5B', '#7A5AE0']}
//                        onChange={(v) => setTweak('primaryColor', v)} />
//           <TweakColor  label="Palette" value={t.palette}
//                        options={[['#D97757', '#29261b', '#f6f4ef'],
//                                  ['#475569', '#0f172a', '#f1f5f9']]}
//                        onChange={(v) => setTweak('palette', v)} />
//           <TweakToggle label="Dark mode" value={t.dark}
//                        onChange={(v) => setTweak('dark', v)} />
//         </TweaksPanel>
//       </div>
//     );
//   }
//
// TweakRadio is the segmented control for 2–3 short options (auto-falls-back to
// TweakSelect past ~16/~10 chars per label); reach for TweakSelect directly when
// options are many or long. For color tweaks always curate 3-4 options rather than
// a free picker; an option can also be a whole 2–5 color palette (the stored value
// is the array). The Tweak* controls are a floor, not a ceiling — build custom
// controls inside the panel if a tweak calls for UI they don't cover.
/* END USAGE */
// ─────────────────────────────────────────────────────────────────────────────

const __TWEAKS_STYLE = `
  .twk-panel{position:fixed;right:16px;bottom:16px;z-index:2147483646;width:280px;
    max-height:calc(100vh - 32px);display:flex;flex-direction:column;
    transform:scale(var(--dc-inv-zoom,1));transform-origin:bottom right;
    background:rgba(250,249,247,.78);color:#29261b;
    -webkit-backdrop-filter:blur(24px) saturate(160%);backdrop-filter:blur(24px) saturate(160%);
    border:.5px solid rgba(255,255,255,.6);border-radius:14px;
    box-shadow:0 1px 0 rgba(255,255,255,.5) inset,0 12px 40px rgba(0,0,0,.18);
    font:11.5px/1.4 ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}
  .twk-hd{display:flex;align-items:center;justify-content:space-between;
    padding:10px 8px 10px 14px;cursor:move;user-select:none}
  .twk-hd b{font-size:12px;font-weight:600;letter-spacing:.01em}
  .twk-x{appearance:none;border:0;background:transparent;color:rgba(41,38,27,.55);
    width:22px;height:22px;border-radius:6px;cursor:default;font-size:13px;line-height:1}
  .twk-x:hover{background:rgba(0,0,0,.06);color:#29261b}
  .twk-body{padding:2px 14px 14px;display:flex;flex-direction:column;gap:10px;
    overflow-y:auto;overflow-x:hidden;min-height:0;
    scrollbar-width:thin;scrollbar-color:rgba(0,0,0,.15) transparent}
  .twk-body::-webkit-scrollbar{width:8px}
  .twk-body::-webkit-scrollbar-track{background:transparent;margin:2px}
  .twk-body::-webkit-scrollbar-thumb{background:rgba(0,0,0,.15);border-radius:4px;
    border:2px solid transparent;background-clip:content-box}
  .twk-body::-webkit-scrollbar-thumb:hover{background:rgba(0,0,0,.25);
    border:2px solid transparent;background-clip:content-box}
  .twk-row{display:flex;flex-direction:column;gap:5px}
  .twk-row-h{flex-direction:row;align-items:center;justify-content:space-between;gap:10px}
  .twk-lbl{display:flex;justify-content:space-between;align-items:baseline;
    color:rgba(41,38,27,.72)}
  .twk-lbl>span:first-child{font-weight:500}
  .twk-val{color:rgba(41,38,27,.5);font-variant-numeric:tabular-nums}

  .twk-sect{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;
    color:rgba(41,38,27,.45);padding:10px 0 0}
  .twk-sect:first-child{padding-top:0}

  .twk-field{appearance:none;box-sizing:border-box;width:100%;min-width:0;height:26px;padding:0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;
    background:rgba(255,255,255,.6);color:inherit;font:inherit;outline:none}
  .twk-field:focus{border-color:rgba(0,0,0,.25);background:rgba(255,255,255,.85)}
  select.twk-field{padding-right:22px;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'><path fill='rgba(0,0,0,.5)' d='M0 0h10L5 6z'/></svg>");
    background-repeat:no-repeat;background-position:right 8px center}

  .twk-slider{appearance:none;-webkit-appearance:none;width:100%;height:4px;margin:6px 0;
    border-radius:999px;background:rgba(0,0,0,.12);outline:none}
  .twk-slider::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;
    width:14px;height:14px;border-radius:50%;background:#fff;
    border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}
  .twk-slider::-moz-range-thumb{width:14px;height:14px;border-radius:50%;
    background:#fff;border:.5px solid rgba(0,0,0,.12);box-shadow:0 1px 3px rgba(0,0,0,.2);cursor:default}

  .twk-seg{position:relative;display:flex;padding:2px;border-radius:8px;
    background:rgba(0,0,0,.06);user-select:none}
  .twk-seg-thumb{position:absolute;top:2px;bottom:2px;border-radius:6px;
    background:rgba(255,255,255,.9);box-shadow:0 1px 2px rgba(0,0,0,.12);
    transition:left .15s cubic-bezier(.3,.7,.4,1),width .15s}
  .twk-seg.dragging .twk-seg-thumb{transition:none}
  .twk-seg button{appearance:none;position:relative;z-index:1;flex:1;border:0;
    background:transparent;color:inherit;font:inherit;font-weight:500;min-height:22px;
    border-radius:6px;cursor:default;padding:4px 6px;line-height:1.2;
    overflow-wrap:anywhere}

  .twk-toggle{position:relative;width:32px;height:18px;border:0;border-radius:999px;
    background:rgba(0,0,0,.15);transition:background .15s;cursor:default;padding:0}
  .twk-toggle[data-on="1"]{background:#34c759}
  .twk-toggle i{position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;
    background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.25);transition:transform .15s}
  .twk-toggle[data-on="1"] i{transform:translateX(14px)}

  .twk-num{display:flex;align-items:center;box-sizing:border-box;min-width:0;height:26px;padding:0 0 0 8px;
    border:.5px solid rgba(0,0,0,.1);border-radius:7px;background:rgba(255,255,255,.6)}
  .twk-num-lbl{font-weight:500;color:rgba(41,38,27,.6);cursor:ew-resize;
    user-select:none;padding-right:8px}
  .twk-num input{flex:1;min-width:0;height:100%;border:0;background:transparent;
    font:inherit;font-variant-numeric:tabular-nums;text-align:right;padding:0 8px 0 0;
    outline:none;color:inherit;-moz-appearance:textfield}
  .twk-num input::-webkit-inner-spin-button,.twk-num input::-webkit-outer-spin-button{
    -webkit-appearance:none;margin:0}
  .twk-num-unit{padding-right:8px;color:rgba(41,38,27,.45)}

  .twk-btn{appearance:none;height:26px;padding:0 12px;border:0;border-radius:7px;
    background:rgba(0,0,0,.78);color:#fff;font:inherit;font-weight:500;cursor:default}
  .twk-btn:hover{background:rgba(0,0,0,.88)}
  .twk-btn.secondary{background:rgba(0,0,0,.06);color:inherit}
  .twk-btn.secondary:hover{background:rgba(0,0,0,.1)}

  .twk-swatch{appearance:none;-webkit-appearance:none;width:56px;height:22px;
    border:.5px solid rgba(0,0,0,.1);border-radius:6px;padding:0;cursor:default;
    background:transparent;flex-shrink:0}
  .twk-swatch::-webkit-color-swatch-wrapper{padding:0}
  .twk-swatch::-webkit-color-swatch{border:0;border-radius:5.5px}
  .twk-swatch::-moz-color-swatch{border:0;border-radius:5.5px}

  .twk-chips{display:flex;gap:6px}
  .twk-chip{position:relative;appearance:none;flex:1;min-width:0;height:46px;
    padding:0;border:0;border-radius:6px;overflow:hidden;cursor:default;
    box-shadow:0 0 0 .5px rgba(0,0,0,.12),0 1px 2px rgba(0,0,0,.06);
    transition:transform .12s cubic-bezier(.3,.7,.4,1),box-shadow .12s}
  .twk-chip:hover{transform:translateY(-1px);
    box-shadow:0 0 0 .5px rgba(0,0,0,.18),0 4px 10px rgba(0,0,0,.12)}
  .twk-chip[data-on="1"]{box-shadow:0 0 0 1.5px rgba(0,0,0,.85),
    0 2px 6px rgba(0,0,0,.15)}
  .twk-chip>span{position:absolute;top:0;bottom:0;right:0;width:34%;
    display:flex;flex-direction:column;box-shadow:-1px 0 0 rgba(0,0,0,.1)}
  .twk-chip>span>i{flex:1;box-shadow:0 -1px 0 rgba(0,0,0,.1)}
  .twk-chip>span>i:first-child{box-shadow:none}
  .twk-chip svg{position:absolute;top:6px;left:6px;width:13px;height:13px;
    filter:drop-shadow(0 1px 1px rgba(0,0,0,.3))}
`;

// ── useTweaks ───────────────────────────────────────────────────────────────
// Single source of truth for tweak values. setTweak persists via the host
// (__edit_mode_set_keys → host rewrites the EDITMODE block on disk).
function useTweaks(defaults) {
  const [values, setValues] = React.useState(defaults);
  // Accepts either setTweak('key', value) or setTweak({ key: value, ... }) so a
  // useState-style call doesn't write a "[object Object]" key into the persisted
  // JSON block.
  const setTweak = React.useCallback((keyOrEdits, val) => {
    const edits = typeof keyOrEdits === 'object' && keyOrEdits !== null ? keyOrEdits : {
      [keyOrEdits]: val
    };
    setValues(prev => ({
      ...prev,
      ...edits
    }));
    window.parent.postMessage({
      type: '__edit_mode_set_keys',
      edits
    }, '*');
    // Same-window signal so in-page listeners (deck-stage rail thumbnails)
    // can react — the parent message only reaches the host, not peers.
    window.dispatchEvent(new CustomEvent('tweakchange', {
      detail: edits
    }));
  }, []);
  return [values, setTweak];
}

// ── TweaksPanel ─────────────────────────────────────────────────────────────
// Floating shell. Registers the protocol listener BEFORE announcing
// availability — if the announce ran first, the host's activate could land
// before our handler exists and the toolbar toggle would silently no-op.
// The close button posts __edit_mode_dismissed so the host's toolbar toggle
// flips off in lockstep; the host echoes __deactivate_edit_mode back which
// is what actually hides the panel.
function TweaksPanel({
  title = 'Tweaks',
  children
}) {
  const [open, setOpen] = React.useState(false);
  const dragRef = React.useRef(null);
  const offsetRef = React.useRef({
    x: 16,
    y: 16
  });
  const PAD = 16;
  const clampToViewport = React.useCallback(() => {
    const panel = dragRef.current;
    if (!panel) return;
    const w = panel.offsetWidth,
      h = panel.offsetHeight;
    const maxRight = Math.max(PAD, window.innerWidth - w - PAD);
    const maxBottom = Math.max(PAD, window.innerHeight - h - PAD);
    offsetRef.current = {
      x: Math.min(maxRight, Math.max(PAD, offsetRef.current.x)),
      y: Math.min(maxBottom, Math.max(PAD, offsetRef.current.y))
    };
    panel.style.right = offsetRef.current.x + 'px';
    panel.style.bottom = offsetRef.current.y + 'px';
  }, []);
  React.useEffect(() => {
    if (!open) return;
    clampToViewport();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', clampToViewport);
      return () => window.removeEventListener('resize', clampToViewport);
    }
    const ro = new ResizeObserver(clampToViewport);
    ro.observe(document.documentElement);
    return () => ro.disconnect();
  }, [open, clampToViewport]);
  React.useEffect(() => {
    const onMsg = e => {
      const t = e?.data?.type;
      if (t === '__activate_edit_mode') setOpen(true);else if (t === '__deactivate_edit_mode') setOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({
      type: '__edit_mode_available'
    }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);
  const dismiss = () => {
    setOpen(false);
    window.parent.postMessage({
      type: '__edit_mode_dismissed'
    }, '*');
  };
  const onDragStart = e => {
    const panel = dragRef.current;
    if (!panel) return;
    const r = panel.getBoundingClientRect();
    const sx = e.clientX,
      sy = e.clientY;
    const startRight = window.innerWidth - r.right;
    const startBottom = window.innerHeight - r.bottom;
    const move = ev => {
      offsetRef.current = {
        x: startRight - (ev.clientX - sx),
        y: startBottom - (ev.clientY - sy)
      };
      clampToViewport();
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };
  if (!open) return null;
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("style", null, __TWEAKS_STYLE), /*#__PURE__*/React.createElement("div", {
    ref: dragRef,
    className: "twk-panel",
    "data-omelette-chrome": "",
    style: {
      right: offsetRef.current.x,
      bottom: offsetRef.current.y
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-hd",
    onMouseDown: onDragStart
  }, /*#__PURE__*/React.createElement("b", null, title), /*#__PURE__*/React.createElement("button", {
    className: "twk-x",
    "aria-label": "Close tweaks",
    onMouseDown: e => e.stopPropagation(),
    onClick: dismiss
  }, "\u2715")), /*#__PURE__*/React.createElement("div", {
    className: "twk-body"
  }, children)));
}

// ── Layout helpers ──────────────────────────────────────────────────────────

function TweakSection({
  label,
  children
}) {
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "twk-sect"
  }, label), children);
}
function TweakRow({
  label,
  value,
  children,
  inline = false
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: inline ? 'twk-row twk-row-h' : 'twk-row'
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-lbl"
  }, /*#__PURE__*/React.createElement("span", null, label), value != null && /*#__PURE__*/React.createElement("span", {
    className: "twk-val"
  }, value)), children);
}

// ── Controls ────────────────────────────────────────────────────────────────

function TweakSlider({
  label,
  value,
  min = 0,
  max = 100,
  step = 1,
  unit = '',
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label,
    value: `${value}${unit}`
  }, /*#__PURE__*/React.createElement("input", {
    type: "range",
    className: "twk-slider",
    min: min,
    max: max,
    step: step,
    value: value,
    onChange: e => onChange(Number(e.target.value))
  }));
}
function TweakToggle({
  label,
  value,
  onChange
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "twk-row twk-row-h"
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-lbl"
  }, /*#__PURE__*/React.createElement("span", null, label)), /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: "twk-toggle",
    "data-on": value ? '1' : '0',
    role: "switch",
    "aria-checked": !!value,
    onClick: () => onChange(!value)
  }, /*#__PURE__*/React.createElement("i", null)));
}
function TweakRadio({
  label,
  value,
  options,
  onChange
}) {
  const trackRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);
  // The active value is read by pointer-move handlers attached for the lifetime
  // of a drag — ref it so a stale closure doesn't fire onChange for every move.
  const valueRef = React.useRef(value);
  valueRef.current = value;

  // Segments wrap mid-word once per-segment width runs out. The track is
  // ~248px (280 panel − 28 body pad − 4 seg pad), each button loses 12px
  // to its own padding, and 11.5px system-ui averages ~6.3px/char — so 2
  // options fit ~16 chars each, 3 fit ~10. Past that (or >3 options), fall
  // back to a dropdown rather than wrap.
  const labelLen = o => String(typeof o === 'object' ? o.label : o).length;
  const maxLen = options.reduce((m, o) => Math.max(m, labelLen(o)), 0);
  const fitsAsSegments = maxLen <= ({
    2: 16,
    3: 10
  }[options.length] ?? 0);
  if (!fitsAsSegments) {
    // <select> emits strings — map back to the original option value so the
    // fallback stays type-preserving (numbers, booleans) like the segment path.
    const resolve = s => {
      const m = options.find(o => String(typeof o === 'object' ? o.value : o) === s);
      return m === undefined ? s : typeof m === 'object' ? m.value : m;
    };
    return /*#__PURE__*/React.createElement(TweakSelect, {
      label: label,
      value: value,
      options: options,
      onChange: s => onChange(resolve(s))
    });
  }
  const opts = options.map(o => typeof o === 'object' ? o : {
    value: o,
    label: o
  });
  const idx = Math.max(0, opts.findIndex(o => o.value === value));
  const n = opts.length;
  const segAt = clientX => {
    const r = trackRef.current.getBoundingClientRect();
    const inner = r.width - 4;
    const i = Math.floor((clientX - r.left - 2) / inner * n);
    return opts[Math.max(0, Math.min(n - 1, i))].value;
  };
  const onPointerDown = e => {
    setDragging(true);
    const v0 = segAt(e.clientX);
    if (v0 !== valueRef.current) onChange(v0);
    const move = ev => {
      if (!trackRef.current) return;
      const v = segAt(ev.clientX);
      if (v !== valueRef.current) onChange(v);
    };
    const up = () => {
      setDragging(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("div", {
    ref: trackRef,
    role: "radiogroup",
    onPointerDown: onPointerDown,
    className: dragging ? 'twk-seg dragging' : 'twk-seg'
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-seg-thumb",
    style: {
      left: `calc(2px + ${idx} * (100% - 4px) / ${n})`,
      width: `calc((100% - 4px) / ${n})`
    }
  }), opts.map(o => /*#__PURE__*/React.createElement("button", {
    key: o.value,
    type: "button",
    role: "radio",
    "aria-checked": o.value === value
  }, o.label))));
}
function TweakSelect({
  label,
  value,
  options,
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("select", {
    className: "twk-field",
    value: value,
    onChange: e => onChange(e.target.value)
  }, options.map(o => {
    const v = typeof o === 'object' ? o.value : o;
    const l = typeof o === 'object' ? o.label : o;
    return /*#__PURE__*/React.createElement("option", {
      key: v,
      value: v
    }, l);
  })));
}
function TweakText({
  label,
  value,
  placeholder,
  onChange
}) {
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("input", {
    className: "twk-field",
    type: "text",
    value: value,
    placeholder: placeholder,
    onChange: e => onChange(e.target.value)
  }));
}
function TweakNumber({
  label,
  value,
  min,
  max,
  step = 1,
  unit = '',
  onChange
}) {
  const clamp = n => {
    if (min != null && n < min) return min;
    if (max != null && n > max) return max;
    return n;
  };
  const startRef = React.useRef({
    x: 0,
    val: 0
  });
  const onScrubStart = e => {
    e.preventDefault();
    startRef.current = {
      x: e.clientX,
      val: value
    };
    const decimals = (String(step).split('.')[1] || '').length;
    const move = ev => {
      const dx = ev.clientX - startRef.current.x;
      const raw = startRef.current.val + dx * step;
      const snapped = Math.round(raw / step) * step;
      onChange(clamp(Number(snapped.toFixed(decimals))));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "twk-num"
  }, /*#__PURE__*/React.createElement("span", {
    className: "twk-num-lbl",
    onPointerDown: onScrubStart
  }, label), /*#__PURE__*/React.createElement("input", {
    type: "number",
    value: value,
    min: min,
    max: max,
    step: step,
    onChange: e => onChange(clamp(Number(e.target.value)))
  }), unit && /*#__PURE__*/React.createElement("span", {
    className: "twk-num-unit"
  }, unit));
}

// Relative-luminance contrast pick — checkmarks drawn over a swatch need to
// read on both #111 and #fafafa without per-option configuration. Hex input
// only (#rgb / #rrggbb); named or rgb()/hsl() colors fall through to "light".
function __twkIsLight(hex) {
  const h = String(hex).replace('#', '');
  const x = h.length === 3 ? h.replace(/./g, c => c + c) : h.padEnd(6, '0');
  const n = parseInt(x.slice(0, 6), 16);
  if (Number.isNaN(n)) return true;
  const r = n >> 16 & 255,
    g = n >> 8 & 255,
    b = n & 255;
  return r * 299 + g * 587 + b * 114 > 148000;
}
const __TwkCheck = ({
  light
}) => /*#__PURE__*/React.createElement("svg", {
  viewBox: "0 0 14 14",
  "aria-hidden": "true"
}, /*#__PURE__*/React.createElement("path", {
  d: "M3 7.2 5.8 10 11 4.2",
  fill: "none",
  strokeWidth: "2.2",
  strokeLinecap: "round",
  strokeLinejoin: "round",
  stroke: light ? 'rgba(0,0,0,.78)' : '#fff'
}));

// TweakColor — curated color/palette picker. Each option is either a single
// hex string or an array of 1-5 hex strings; the card adapts — a lone color
// renders solid, a palette renders colors[0] as the hero (left ~2/3) with the
// rest stacked in a sharp column on the right. onChange emits the
// option in the shape it was passed (string stays string, array stays array).
// Without options it falls back to the native color input for back-compat.
function TweakColor({
  label,
  value,
  options,
  onChange
}) {
  if (!options || !options.length) {
    return /*#__PURE__*/React.createElement("div", {
      className: "twk-row twk-row-h"
    }, /*#__PURE__*/React.createElement("div", {
      className: "twk-lbl"
    }, /*#__PURE__*/React.createElement("span", null, label)), /*#__PURE__*/React.createElement("input", {
      type: "color",
      className: "twk-swatch",
      value: value,
      onChange: e => onChange(e.target.value)
    }));
  }
  // Native <input type=color> emits lowercase hex per the HTML spec, so
  // compare case-insensitively. String() guards JSON.stringify(undefined),
  // which returns the primitive undefined (no .toLowerCase).
  const key = o => String(JSON.stringify(o)).toLowerCase();
  const cur = key(value);
  return /*#__PURE__*/React.createElement(TweakRow, {
    label: label
  }, /*#__PURE__*/React.createElement("div", {
    className: "twk-chips",
    role: "radiogroup"
  }, options.map((o, i) => {
    const colors = Array.isArray(o) ? o : [o];
    const [hero, ...rest] = colors;
    const sup = rest.slice(0, 4);
    const on = key(o) === cur;
    return /*#__PURE__*/React.createElement("button", {
      key: i,
      type: "button",
      className: "twk-chip",
      role: "radio",
      "aria-checked": on,
      "data-on": on ? '1' : '0',
      "aria-label": colors.join(', '),
      title: colors.join(' · '),
      style: {
        background: hero
      },
      onClick: () => onChange(o)
    }, sup.length > 0 && /*#__PURE__*/React.createElement("span", null, sup.map((c, j) => /*#__PURE__*/React.createElement("i", {
      key: j,
      style: {
        background: c
      }
    }))), on && /*#__PURE__*/React.createElement(__TwkCheck, {
      light: __twkIsLight(hero)
    }));
  })));
}
function TweakButton({
  label,
  onClick,
  secondary = false
}) {
  return /*#__PURE__*/React.createElement("button", {
    type: "button",
    className: secondary ? 'twk-btn secondary' : 'twk-btn',
    onClick: onClick
  }, label);
}
Object.assign(window, {
  useTweaks,
  TweaksPanel,
  TweakSection,
  TweakRow,
  TweakSlider,
  TweakToggle,
  TweakRadio,
  TweakSelect,
  TweakText,
  TweakNumber,
  TweakColor,
  TweakButton
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "tweaks-panel.jsx", error: String((e && e.message) || e) }); }

// ui_kits/_shell/shell.js
try { (() => {
/* Pathly Studio shared chrome — topbar + sidebar from one config.
   The sidebar is context-aware and responsive:
     • cfg.sidebar:    'full' (default) | 'rail'  → Canvas uses 'rail'
     • cfg.sidebarTab: 'workspace' (default) | 'library' → Notebook uses 'library'
     • below 1080px viewport it auto-collapses to the icon rail
     • the topbar hamburger toggles collapse manually
   Usage:
     <div class="app">
       <div id="pathly-topbar"></div>
       <div class="app-body"><div id="pathly-sidebar"></div><main class="app-main">…</main></div>
     </div>
     <script>window.PATHLY_SHELL = { project:'…', activeNav:'monitor', activeSide:'db', sidebar:'full', sidebarTab:'workspace' };</script>
     <script src="../_shell/shell.js"></script>
*/
(function () {
  function ico(name, size) {
    return window.PathlyIcons ? window.PathlyIcons.svg(name, {
      size: size || 14
    }) : '';
  }
  var cfg = window.PATHLY_SHELL || {};
  var BP = 1080;
  var base = cfg.sidebar === 'rail';
  var manual = null; // user override via hamburger; reset on resize

  function isRail() {
    if (manual !== null) return manual;
    if (window.innerWidth < BP) return true;
    return base;
  }

  // ── library skill tree (Notebook context) ──
  var SKILLS = ['plan/storm', 'plan/scope', 'fix/build', 'team/build', 'review/quality', 'test/verify', 'retro/archive'];
  function activeSkill() {
    return cfg.activeSkill || new URLSearchParams(location.search).get('skill') || null;
  }

  // ── topbar ──
  function topbar() {
    var nav = [['flow', 'Canvas', 'layout-grid'], ['notebook', 'Notebook', 'book-open'], ['monitor', 'Monitor', 'activity']].map(function (n) {
      return '<button class="tb-navbtn" ' + (cfg.activeNav === n[0] ? 'data-active' : '') + '>' + ico(n[2], 13) + n[1] + '</button>';
    }).join('');
    return '<button class="tb-icon js-sb-toggle" title="Toggle sidebar">' + ico('menu', 15) + '</button>' + '<button class="tb-back">Projects</button>' + '<div class="tb-center">' + '<div class="tb-project">' + ico('database', 13) + '<span>' + (cfg.project || 'fsm-server-sqlite') + '</span><span class="chev">' + ico('chevron-down', 13) + '</span></div>' + '<button class="tb-icon" title="New window">' + ico('copy', 14) + '</button>' + '<div class="tb-nav">' + nav + '</div>' + '</div>' + '<div class="tb-right">' + '<button class="tb-icon" title="HQ">' + ico('brain', 14) + '</button>' + '<button class="tb-icon" title="Theme">' + ico('moon', 14) + '</button>' + '<button class="tb-icon" title="Terminal">' + ico('square-terminal', 14) + '</button>' + '<button class="tb-icon" title="Account">' + ico('globe', 14) + '</button>' + '</div>';
  }

  // ── full sidebar (workspace OR library tab) ──
  function fullSidebar() {
    var tab = cfg.sidebarTab === 'library' ? 'library' : 'workspace';
    var tabs = '<div class="sb-tabs">' + '<button class="sb-tab" ' + (tab === 'workspace' ? 'data-active' : '') + '>Workspace</button>' + '<button class="sb-tab" ' + (tab === 'library' ? 'data-active' : '') + '>Library</button></div>';
    var filter = '<div class="sb-filter"><input placeholder="' + (tab === 'library' ? 'Search skills…' : 'Filter…') + '" /></div>';
    var body;
    if (tab === 'library') {
      var as = activeSkill();
      body = '<div class="sb-label">Library · skills</div><div class="sb-tree">' + SKILLS.map(function (s) {
        return '<button class="sb-row" ' + (s === as ? 'data-active' : '') + '>' + ico('file-text', 13) + '<span class="skillname">' + s + '</span></button>';
      }).join('') + '</div>';
    } else {
      var tree = [['plan', 'Plan', 'fsm-server-sqlite'], ['debugs', 'Debugs'], ['explorations', 'Explorations'], ['lessons', 'Lessons'], ['pipeline', 'Pipeline-walkthrough']].map(function (r) {
        return '<button class="sb-row" ' + (cfg.activeSide === r[0] ? 'data-active' : '') + '>' + ico('diamond', 13) + '<span>' + r[1] + '</span>' + (r[2] ? '<span class="tag">[' + r[2] + ']</span>' : '') + '</button>';
      }).join('');
      body = '<div class="sb-label">Workspace</div><div class="sb-tree">' + tree + '<div class="sb-divider"></div>' + '<button class="sb-row" ' + (cfg.activeSide === 'monitor' ? 'data-active' : '') + '><span class="sb-dot">●</span><span>Monitor</span></button>' + '<button class="sb-row" ' + (cfg.activeSide === 'db' ? 'data-active' : '') + '>' + ico('hard-drive', 13) + '<span>DB Explorer</span></button>' + '<button class="sb-row" ' + (cfg.activeSide === 'settings' ? 'data-active' : '') + '>' + ico('settings', 13) + '<span>Settings</span></button></div>';
    }
    return tabs + filter + body + '<div class="sb-profile"><span class="sb-avatar">SH</span>' + '<span class="who"><span class="name">shammai hamilton</span><span class="mail">shammaihamilton@…</span></span>' + '<button class="sb-signout">Sign out</button></div>';
  }

  // ── collapsed icon rail ──
  function railSidebar() {
    var libTab = cfg.sidebarTab === 'library';
    function btn(icon, title, active, dot) {
      return '<button class="sb-railbtn" title="' + title + '" ' + (active ? 'data-active' : '') + '>' + (dot ? '<span class="sb-dot">●</span>' : ico(icon, 16)) + '</button>';
    }
    return '<div class="sb-rail">' + btn('diamond', 'Workspace', !libTab && cfg.activeSide !== 'monitor' && cfg.activeSide !== 'db' && cfg.activeSide !== 'settings') + btn('book-open', 'Library', libTab) + '<div class="sb-rail-divider"></div>' + btn(null, 'Monitor', cfg.activeSide === 'monitor', true) + btn('hard-drive', 'DB Explorer', cfg.activeSide === 'db') + btn('settings', 'Settings', cfg.activeSide === 'settings') + '<div class="sb-rail-foot"><span class="sb-rail-avatar" title="shammai hamilton">SH</span></div>' + '</div>';
  }
  var tb = document.getElementById('pathly-topbar');
  var sb = document.getElementById('pathly-sidebar');
  function renderTopbar() {
    if (!tb) return;
    tb.className = 'topbar';
    tb.innerHTML = topbar();
    PathlyIcons.inject(tb);
    var t = tb.querySelector('.js-sb-toggle');
    if (t) t.onclick = function () {
      manual = !isRail();
      renderSidebar();
    };
  }
  function renderSidebar() {
    if (!sb) return;
    var rail = isRail();
    sb.className = 'sidebar' + (rail ? ' rail' : '');
    sb.innerHTML = rail ? railSidebar() : fullSidebar();
    PathlyIcons.inject(sb);
  }
  renderTopbar();
  renderSidebar();
  var prevRail = isRail();
  window.addEventListener('resize', function () {
    manual = null;
    if (isRail() !== prevRail) {
      prevRail = isRail();
      renderSidebar();
    }
  });
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/_shell/shell.js", error: String((e && e.message) || e) }); }

// ui_kits/db-explorer/db-explorer.js
try { (() => {
/* Pathly Studio — DB Explorer kit logic (vanilla; static demo data). */
(function () {
  var ic = function (n, s) {
    return PathlyIcons.svg(n, {
      size: s || 14
    });
  };
  var STATE = {
    PLANNING: 'var(--state-planning)',
    BUILDING: 'var(--state-building)',
    REVIEWING: 'var(--state-reviewing)',
    TESTING: 'var(--state-testing)',
    RETRO: 'var(--state-retro)',
    DONE: 'var(--state-done)'
  };
  function pill(state) {
    var c = STATE[state] || 'var(--text-muted)';
    return '<span class="pill" style="color:' + c + ';background:color-mix(in srgb,' + c + ' 13%,transparent);border-color:color-mix(in srgb,' + c + ' 38%,transparent)">' + '<span class="pdot" style="background:' + c + '"></span>' + state + '</span>';
  }
  function progress(done, total, color) {
    var pct = Math.round(done / total * 100);
    return '<div class="prog"><div class="track"><div class="fill" style="width:' + pct + '%;background:' + color + '"></div></div>' + '<span class="frac">' + done + '/' + total + '</span></div>';
  }
  function dots(arr) {
    return '<div class="dots">' + arr.map(function (c) {
      return '<span style="flex:' + (c[1] || 1) + ';background:' + c[0] + '"></span>';
    }).join('') + '</div>';
  }

  // ── action buttons ──
  function actionBtns() {
    return [['refresh-cw', 'Refresh'], ['hard-drive', 'Run Migration'], ['download', 'Export JSON']].map(function (b) {
      return '<button class="btn-b">' + ic(b[0], 13) + b[1] + '</button>';
    }).join('');
  }
  document.getElementById('head-actions').innerHTML = actionBtns();

  // ── stats ──
  var stats = [['Features', '7'], ['Events', '202'], ['Invocations', '37'], ['Tokens', '1.05M'], ['Cost', '$14.20', 'cost']];
  document.getElementById('stats').innerHTML = stats.map(function (s) {
    return '<div class="stat"><div class="k">' + s[0] + '</div><div class="v ' + (s[2] || '') + '">' + s[1] + '</div></div>';
  }).join('');

  // ── features ──
  var G = 'var(--state-done)',
    B = 'var(--state-building)',
    R = 'var(--state-reviewing)',
    T = 'var(--state-testing)',
    P = 'var(--state-planning)',
    TE = 'var(--state-retro)';
  var features = [{
    name: 'fsm-sqlite',
    state: 'DONE',
    events: 35,
    inv: 8,
    tokens: '290,749',
    cost: '$3.64',
    ts: '10:06:05',
    done: 3,
    total: 3,
    pcol: T,
    dots: [[B], [R], [B], [T], [R], [B], [T], [R], [G, 1.4]]
  }, {
    name: 'auth-refactor',
    state: 'BUILDING',
    events: 23,
    inv: 4,
    tokens: '142,300',
    cost: '$1.97',
    ts: '11:14:02',
    done: 1,
    total: 3,
    pcol: B,
    dots: [[P], [B], [B, 1.6], [R]]
  }, {
    name: 'payments-webhook',
    state: 'REVIEWING',
    events: 28,
    inv: 6,
    tokens: '188,400',
    cost: '$2.41',
    ts: '09:31:50',
    done: 2,
    total: 3,
    pcol: R,
    dots: [[B], [R], [B], [T], [R, 1.5]]
  }, {
    name: 'search-index',
    state: 'TESTING',
    events: 19,
    inv: 5,
    tokens: '96,800',
    cost: '$1.12',
    ts: '13:20:11',
    done: 2,
    total: 4,
    pcol: T,
    dots: [[B], [R], [T, 1.6]]
  }, {
    name: 'cache-layer',
    state: 'DONE',
    events: 41,
    inv: 9,
    tokens: '214,600',
    cost: '$3.02',
    ts: '08:48:33',
    done: 4,
    total: 4,
    pcol: G,
    dots: [[B], [R], [T], [B], [R], [TE], [G, 1.4]]
  }, {
    name: 'notifications',
    state: 'PLANNING',
    events: 6,
    inv: 1,
    tokens: '18,900',
    cost: '$0.31',
    ts: '14:02:19',
    done: 0,
    total: 3,
    pcol: P,
    dots: [[P, 2]]
  }];
  document.getElementById('grid').innerHTML = features.map(function (f, i) {
    return '<div class="feat" data-i="' + i + '">' + '<div class="top"><span class="fname">' + f.name + '</span></div>' + dots(f.dots) + '<div class="metrics">' + '<div><div class="mk">Events</div><div class="mv">' + f.events + '</div></div>' + '<div><div class="mk">Invocations</div><div class="mv">' + f.inv + '</div></div>' + '<div><div class="mk">Tokens</div><div class="mv">' + f.tokens + '</div></div>' + '<div><div class="mk">Cost</div><div class="mv cost">' + f.cost + '</div></div>' + '</div>' + '<div class="foot"><span class="ts">' + f.ts + '</span>' + progress(f.done, f.total, f.pcol) + '</div>' + '<div style="margin-top:12px">' + pill(f.state) + '</div>' + '</div>';
  }).join('');

  // ── modal ──
  var TRANSITIONS = [['PLANNING', '09:02:11', '6m 29s'], ['BUILDING', '09:08:40', '12m 26s'], ['REVIEWING', '09:21:06', '6m 27s'], ['TESTING', '09:27:33', '6m 45s'], ['BUILDING', '09:34:18', '11m 44s'], ['REVIEWING', '09:46:02', '6m 47s'], ['TESTING', '09:52:49', '4m 38s'], ['RETRO', '09:57:27', '3m 12s'], ['DONE', '10:06:05', '—']];
  var AGENTS = [['builder', 'conv 1', B, 0.39], ['reviewer', 'conv 1', R, 0.71], ['builder', 'conv 2', B, 0.42], ['tester', 'conv 2', T, 0.23], ['reviewer', 'conv 2', R, 0.74], ['builder', 'conv 3', B, 0.33], ['tester', 'conv 3', T, 0.24], ['reviewer', 'conv 3', R, 0.58]];
  var maxCost = Math.max.apply(null, AGENTS.map(function (a) {
    return a[3];
  }));
  function timelineHTML() {
    var steps = TRANSITIONS.map(function (t, i) {
      var arrow = i < TRANSITIONS.length - 1 ? '<span class="tarrow">' + ic('chevron-right', 16) + '</span>' : '';
      return '<div class="tstep">' + pill(t[0]) + '<span class="tstamp">' + t[1] + '</span><span class="tdur">' + ic('chevrons-up', 11) + ' ' + t[2] + '</span></div>' + arrow;
    });
    // interleave arrows
    var html = '';
    TRANSITIONS.forEach(function (t, i) {
      html += '<div class="tstep">' + pill(t[0]) + '<span class="tstamp">' + t[1] + '</span><span class="tdur">' + t[2] + '</span></div>';
      if (i < TRANSITIONS.length - 1) html += '<span class="tarrow">' + ic('chevron-right', 16) + '</span>';
    });
    var legend = ['PLANNING', 'BUILDING', 'REVIEWING', 'TESTING', 'RETRO', 'DONE'].map(function (s) {
      return '<span><i style="background:' + STATE[s] + '"></i>' + s + '</span>';
    }).join('');
    return '<p class="m-sublabel">State machine · 9 transitions</p>' + '<div class="timeline">' + html + '</div>' + '<div class="legend">' + legend + '</div>';
  }
  function agentsHTML() {
    var rows = AGENTS.map(function (a) {
      var w = Math.round(a[3] / maxCost * 100);
      var grad = 'linear-gradient(90deg, color-mix(in srgb,' + a[2] + ' 55%,transparent), ' + a[2] + ')';
      return '<div class="arow"><span class="aname">' + a[0] + ' <span class="conv">(' + a[1] + ')</span></span>' + '<div class="abar" style="width:' + w + '%;background:' + grad + '"></div>' + '<span class="acost">$' + a[3].toFixed(2) + '</span></div>';
    }).join('');
    return '<p class="m-sublabel">Cost per invocation · 8 agents · $3.64 total</p><div class="agents">' + rows + '</div>';
  }
  function sqlHTML() {
    return '<p class="m-sublabel">SQL console</p>' + '<div style="font-family:var(--font-family-mono);font-size:var(--font-size-base);background:var(--bg-terminal);border:var(--border);border-radius:var(--radius-md);padding:14px;color:var(--text-secondary)">' + '<span style="color:var(--purple)">SELECT</span> stage, <span style="color:var(--purple)">count</span>(*) <span style="color:var(--purple)">FROM</span> events <span style="color:var(--purple)">GROUP BY</span> stage;</div>' + '<div style="margin-top:12px;color:var(--text-muted);font-size:var(--font-size-sm)">9 rows · 4ms</div>';
  }
  function eventsHTML() {
    var ev = [['09:02:11', 'STAGE_ENTER', 'PLANNING', B], ['09:08:40', 'AGENT_DONE', 'builder · $0.39', G], ['09:21:06', 'STAGE_ENTER', 'REVIEWING', R], ['09:34:18', 'STAGE_REROUTE', '→ BUILDING', 'var(--orange)'], ['10:06:05', 'PIPELINE_DONE', '290,749 tok · $3.64', G]];
    return '<p class="m-sublabel">Events · 47</p><div style="display:flex;flex-direction:column;gap:2px">' + ev.map(function (e) {
      return '<div style="display:grid;grid-template-columns:80px 150px 1fr;gap:12px;padding:8px 10px;border-radius:var(--radius-sm);font-size:var(--font-size-base)">' + '<span style="font-family:var(--font-family-mono);color:var(--text-muted)">' + e[0] + '</span>' + '<span style="font-family:var(--font-family-mono);color:' + e[3] + '">' + e[2] + '</span>' + '<span style="color:var(--text-secondary)">' + e[1] + '</span></div>';
    }).join('') + '</div>';
  }
  var TABS = [['timeline', 'Timeline', '9', timelineHTML], ['events', 'Events', '47', eventsHTML], ['agents', 'Agents', '8', agentsHTML], ['sql', 'SQL', '', sqlHTML]];
  var current = 'timeline';
  function renderModal(f) {
    var tabsHTML = TABS.map(function (t) {
      return '<button class="m-tab" data-tab="' + t[0] + '" ' + (t[0] === current ? 'data-active' : '') + '>' + t[1] + (t[2] ? '<span class="ct">' + t[2] + '</span>' : '') + '</button>';
    }).join('');
    var bodyFn = TABS.find(function (t) {
      return t[0] === current;
    })[3];
    document.getElementById('modal').innerHTML = '<div class="m-head">' + pill('DONE') + '<span class="m-name">' + f.name + '</span>' + '<span class="m-meta">convs <b>3/3</b></span>' + '<span class="m-meta">events <b>47</b></span>' + '<span class="m-meta">cost <b>$3.64</b></span>' + '<button class="tb-icon m-close" id="m-close">' + ic('x', 16) + '</button>' + '</div>' + '<div class="m-actions">' + actionBtns() + '<span class="m-runner">runner: finished · 290,749 tok · <b>$3.64</b></span>' + '</div>' + '<div class="m-tabs">' + tabsHTML + '</div>' + '<div class="m-body" id="m-body">' + bodyFn() + '</div>';
    document.getElementById('m-close').onclick = closeModal;
    document.querySelectorAll('.m-tab').forEach(function (b) {
      b.onclick = function () {
        current = b.getAttribute('data-tab');
        renderModal(f);
      };
    });
    PathlyIcons.inject(document.getElementById('modal'));
  }
  function openModal(f) {
    current = 'timeline';
    renderModal(f);
    document.getElementById('overlay').setAttribute('data-open', '');
  }
  function closeModal() {
    document.getElementById('overlay').removeAttribute('data-open');
  }
  document.querySelectorAll('.feat').forEach(function (el) {
    el.onclick = function () {
      openModal(features[+el.getAttribute('data-i')]);
    };
  });
  document.getElementById('overlay').onclick = function (e) {
    if (e.target === this) closeModal();
  };
  PathlyIcons.inject(document);
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/db-explorer/db-explorer.js", error: String((e && e.message) || e) }); }

// ui_kits/flow-canvas/canvas.js
try { (() => {
/* Pathly Studio — Flow Canvas kit logic (vanilla; static FSM graph). */
(function () {
  var ic = function (n, s) {
    return PathlyIcons.svg(n, {
      size: s || 14
    });
  };
  var NW = 160,
    NH = 52,
    CX = 250,
    LEFT = CX - NW / 2; // 170
  function accent(agent) {
    var a = agent.toLowerCase();
    if (a.indexOf('review') >= 0) return 'var(--purple)';
    if (a.indexOf('test') >= 0) return 'var(--yellow)';
    if (a.indexOf('retro') >= 0 || a.indexOf('done') >= 0) return 'var(--green)';
    return 'var(--blue)';
  }
  var NODES = [{
    id: 'STORMING',
    agent: 'planner',
    top: 30,
    start: true
  }, {
    id: 'PLANNING',
    agent: 'planner',
    top: 140
  }, {
    id: 'BUILDING',
    agent: 'builder',
    top: 250
  }, {
    id: 'REVIEWING',
    agent: 'reviewer',
    top: 360
  }, {
    id: 'TESTING',
    agent: 'tester',
    top: 470
  }, {
    id: 'DONE',
    agent: 'retro',
    top: 580
  }];
  var FWD = [[0, 1, 'storm_done'], [1, 2, 'plan_ready'], [2, 3, 'build_done'], [3, 4, 'pass'], [4, 5, 'green']];
  var BACK = [[3, 2, 'changes'], [4, 2, 'fail']];
  function nodeById(id) {
    return NODES.find(function (n) {
      return n.id === id;
    });
  }

  // ── render nodes ──
  function renderNodes() {
    var inner = document.getElementById('cv-inner');
    // remove existing nodes (keep svg)
    inner.querySelectorAll('.node').forEach(function (n) {
      n.remove();
    });
    NODES.forEach(function (n, i) {
      var el = document.createElement('div');
      el.className = 'node';
      el.style.left = LEFT + 'px';
      el.style.top = n.top + 'px';
      el.style.borderLeftColor = accent(n.agent);
      el.setAttribute('data-i', i);
      el.innerHTML = (n.start ? '<span class="start">' + ic('play', 8) + '</span>' : '') + '<span class="handle h-top"></span><span class="handle h-bot"></span><span class="handle h-right"></span>' + '<div class="nstate">' + n.id + '</div><div class="nagent">' + n.agent + '</div>';
      el.onclick = function () {
        selectNode(i);
      };
      inner.appendChild(el);
    });
    PathlyIcons.inject(inner);
  }

  // ── render edges ──
  function renderEdges() {
    var svg = document.getElementById('cv-edges');
    var blue = getComputedStyle(document.documentElement).getPropertyValue('--blue').trim() || '#60A5FA';
    var orange = getComputedStyle(document.documentElement).getPropertyValue('--orange').trim() || '#f97316';
    var defs = '<defs>' + '<marker id="ah-blue" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="' + blue + '"/></marker>' + '<marker id="ah-orange" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="' + orange + '"/></marker>' + '</defs>';
    var paths = '';
    FWD.forEach(function (e) {
      var a = NODES[e[0]],
        b = NODES[e[1]];
      var y1 = a.top + NH,
        y2 = b.top;
      paths += '<line x1="' + CX + '" y1="' + y1 + '" x2="' + CX + '" y2="' + (y2 - 7) + '" stroke="' + blue + '" stroke-width="2" marker-end="url(#ah-blue)"/>';
      paths += '<text x="' + (CX + 8) + '" y="' + ((y1 + y2) / 2 + 4) + '" fill="var(--text-muted)" font-family="var(--font-family-mono)" font-size="10">' + e[2] + '</text>';
    });
    BACK.forEach(function (e, k) {
      var a = NODES[e[0]],
        b = NODES[e[1]];
      var x = LEFT + NW; // right edge 460
      var y1 = a.top + NH / 2,
        y2 = b.top + NH / 2;
      var bow = 70 + k * 26;
      paths += '<path d="M' + x + ',' + y1 + ' C' + (x + bow) + ',' + y1 + ' ' + (x + bow) + ',' + y2 + ' ' + (x + 7) + ',' + y2 + '" fill="none" stroke="' + orange + '" stroke-width="2" stroke-dasharray="4 3" marker-end="url(#ah-orange)"/>';
      paths += '<text x="' + (x + bow + 6) + '" y="' + (y1 + y2) / 2 + '" fill="' + orange + '" font-family="var(--font-family-mono)" font-size="10">↩ ' + e[2] + '</text>';
    });
    svg.innerHTML = defs + paths;
  }

  // ── inspector ──
  var AGENTS = ['planner', 'builder', 'reviewer', 'tester', 'retro'];
  function transitionsFor(i) {
    var outs = [];
    FWD.forEach(function (e) {
      if (e[0] === i) outs.push({
        to: NODES[e[1]].id,
        cond: e[2],
        back: false
      });
    });
    BACK.forEach(function (e) {
      if (e[0] === i) outs.push({
        to: NODES[e[1]].id,
        cond: e[2],
        back: true
      });
    });
    return outs;
  }
  function selectNode(i) {
    document.querySelectorAll('.node').forEach(function (n) {
      n.removeAttribute('data-active');
    });
    document.querySelector('.node[data-i="' + i + '"]').setAttribute('data-active', '');
    var n = NODES[i];
    var trans = transitionsFor(i).map(function (t) {
      return '<div class="ins-tran' + (t.back ? ' back' : '') + '">' + ic(t.back ? 'rotate-ccw' : 'chevron-right', 13) + '<span class="to">' + t.to + '</span><span class="cond">on ' + t.cond + '</span></div>';
    }).join('') || '<div class="ins-tran"><span class="to" style="color:var(--text-muted)">terminal state</span></div>';
    var agentOpts = AGENTS.map(function (a) {
      return '<option' + (a === n.agent ? ' selected' : '') + '>' + a + '</option>';
    }).join('');
    var ins = document.getElementById('cv-inspect');
    ins.className = 'cv-inspect';
    ins.innerHTML = '<p class="ins-title">State</p><div class="ins-state">' + n.id + '</div>' + '<div class="ins-field"><span class="fl">Agent</span><select class="ins-select">' + agentOpts + '</select></div>' + '<div class="ins-field"><span class="fl">Transitions</span><div class="ins-trans">' + trans + '</div></div>' + '<div class="ins-field"><span class="fl">Gate</span><div class="ins-tran"><span class="to" style="font-family:var(--font-family-mono);font-size:var(--font-size-sm)">' + (n.id === 'BUILDING' ? 'lint:strict · types:strict' : n.id === 'TESTING' ? 'suite:green' : 'none') + '</span></div></div>';
    PathlyIcons.inject(ins);
  }

  // ── views ──
  document.getElementById('cv-views').innerHTML = '<button class="seg-tab" data-view="visual" data-active>' + ic('layout-grid', 13) + 'Visual</button>' + '<button class="seg-tab" data-view="yaml">' + ic('list', 13) + 'YAML</button>';
  document.getElementById('cv-valid').innerHTML = ic('circle-check', 13) + 'Valid · 6 states';
  document.getElementById('cv-export').innerHTML = ic('download', 13) + 'Export ▾';
  document.getElementById('cv-layout').innerHTML = ic('shuffle', 13) + 'Auto-layout';
  function yamlHTML() {
    var lines = ['<span class="yk">flow</span>: <span class="yv">team-build</span>', '<span class="yk">start</span>: <span class="yv">STORMING</span>', '<span class="yk">states</span>:'];
    NODES.forEach(function (n) {
      lines.push('  - <span class="yk">name</span>: <span class="yv">' + n.id + '</span>');
      lines.push('    <span class="yk">agent</span>: <span class="ys">' + n.agent + '</span>');
      var outs = transitionsFor(NODES.indexOf(n));
      if (outs.length) {
        lines.push('    <span class="yk">transitions</span>:');
        outs.forEach(function (t) {
          lines.push('      - <span class="yk">to</span>: <span class="yv">' + t.to + '</span>  <span class="yc"># on ' + t.cond + (t.back ? ' (reroute)' : '') + '</span>');
        });
      }
    });
    return '<pre>' + lines.join('\n') + '</pre>';
  }
  function setView(v) {
    document.querySelectorAll('[data-view]').forEach(function (b) {
      b.toggleAttribute('data-active', b.getAttribute('data-view') === v);
    });
    var stage = document.getElementById('cv-stage');
    if (v === 'yaml') {
      stage.innerHTML = '<div class="cv-yaml">' + yamlHTML() + '</div>';
    } else {
      location.reload();
    }
  }
  document.querySelectorAll('[data-view]').forEach(function (b) {
    b.onclick = function () {
      setView(b.getAttribute('data-view'));
    };
  });
  renderNodes();
  renderEdges();
  selectNode(2); // BUILDING selected by default
  PathlyIcons.inject(document);
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/flow-canvas/canvas.js", error: String((e && e.message) || e) }); }

// ui_kits/monitor/monitor.js
try { (() => {
/* Pathly Studio — Monitor kit logic (vanilla; static demo).
   Clicking a pipeline phase opens a config modal: prompt preview,
   CLI host, agent + skill selectors, and "open in notebook". */
(function () {
  var ic = function (n, s) {
    return PathlyIcons.svg(n, {
      size: s || 14
    });
  };
  var STATE = {
    STORMING: 'var(--text-muted)',
    PLANNING: 'var(--state-planning)',
    BUILDING: 'var(--state-building)',
    REVIEWING: 'var(--state-reviewing)',
    TESTING: 'var(--state-testing)',
    DONE: 'var(--state-done)'
  };
  function pill(state) {
    var c = STATE[state] || 'var(--text-muted)';
    return '<span class="pill" style="color:' + c + ';background:color-mix(in srgb,' + c + ' 13%,transparent);border-color:color-mix(in srgb,' + c + ' 38%,transparent)"><span class="pdot" style="background:' + c + '"></span>' + state + '</span>';
  }

  // ── pipeline definition ──
  var PIPELINE = [{
    state: 'STORMING',
    agent: 'planner',
    skill: 'plan/storm'
  }, {
    state: 'PLANNING',
    agent: 'planner',
    skill: 'plan/scope'
  }, {
    state: 'BUILDING',
    agent: 'builder',
    skill: 'fix/build'
  }, {
    state: 'REVIEWING',
    agent: 'reviewer',
    skill: 'review/quality'
  }, {
    state: 'TESTING',
    agent: 'tester',
    skill: 'test/verify'
  }, {
    state: 'DONE',
    agent: 'retro',
    skill: 'retro/archive'
  }];
  var ACTIVE = 2; // BUILDING

  var HOSTS = [{
    id: 'claude',
    label: 'Claude Code',
    dot: 'var(--orange)'
  }, {
    id: 'codex',
    label: 'Codex',
    dot: 'var(--green)'
  }, {
    id: 'copilot',
    label: 'Copilot',
    dot: 'var(--blue)'
  }];
  var AGENTS = ['planner', 'builder', 'reviewer', 'tester', 'retro'];
  var SKILLS = ['plan/storm', 'plan/scope', 'fix/build', 'team/build', 'review/quality', 'test/verify', 'retro/archive'];
  var SKILL_PROMPTS = {
    'fix/build': {
      role: 'Stage orchestrator — Quick Fix.',
      body: 'Apply a single, well-scoped change. No multi-conversation\nplanning, no PROGRESS.md churn.',
      steps: ['Read the issue description in plans/auth-refactor/', 'Locate the code', 'Apply the minimal change', 'Verify it passes'],
      gate: 'lint:strict, types:strict must pass before REVIEWING.'
    },
    'team/build': {
      role: 'Team orchestrator — Full Build.',
      body: 'Coordinate builder conversations across the feature plan.\nSplit work, track PROGRESS.md, hand off to review.',
      steps: ['Load the plan & conversation queue', 'Spawn builder per conversation', 'Reconcile diffs', 'Update PROGRESS.md'],
      gate: 'All conversations DONE before REVIEWING.'
    },
    'plan/scope': {
      role: 'Stage orchestrator — Planning.',
      body: 'Decompose the feature into a conversation plan.\nProduce plans/<feature>/PLAN.md.',
      steps: ['Read the feature brief', 'Draft conversation list', 'Define gates per stage', 'Write PLAN.md'],
      gate: 'PLAN.md present before BUILDING.'
    },
    'plan/storm': {
      role: 'Stage orchestrator — Storming.',
      body: 'Explore the problem space and surface unknowns before\ncommitting to a plan.',
      steps: ['Survey the codebase', 'List open questions', 'Propose 2–3 approaches'],
      gate: 'Approach chosen before PLANNING.'
    },
    'review/quality': {
      role: 'Stage orchestrator — Review.',
      body: 'Critique the diff against the plan and quality bar.\nRequest changes or pass to TESTING.',
      steps: ['Diff against PLAN.md', 'Run quality gates', 'Annotate findings', 'PASS or REROUTE → BUILDING'],
      gate: 'No blocking findings before TESTING.'
    },
    'test/verify': {
      role: 'Stage orchestrator — Test.',
      body: 'Run and extend the verification suite for the change.',
      steps: ['Run the test suite', 'Add coverage for the change', 'Report results'],
      gate: 'Green suite before DONE.'
    },
    'retro/archive': {
      role: 'Stage orchestrator — Retro.',
      body: 'Summarise the run, capture lessons, archive artifacts.',
      steps: ['Write the retro note', 'Capture lessons/', 'Archive the plan'],
      gate: '—'
    }
  };

  // ── stepper ──
  function renderStepper() {
    document.getElementById('conv-label').innerHTML = 'conv <b>2</b> · <b>2</b> done · <b>3</b> remaining';
    var html = '';
    PIPELINE.forEach(function (st, idx) {
      var status = idx < ACTIVE ? 'done' : idx === ACTIVE ? 'active' : 'pending';
      var inner = status === 'done' ? ic('check', 14) : '<span class="inner"></span>';
      html += '<div class="step">' + '<div class="dotcol" data-i="' + idx + '">' + '<div class="fsmdot ' + status + '">' + inner + '</div>' + '<span class="steplabel ' + status + '">' + st.state + '</span>' + '<span class="agenttag">' + st.agent + '</span>' + '</div>' + (idx < PIPELINE.length - 1 ? '<div class="connector ' + (idx < ACTIVE ? 'done' : '') + '"></div>' : '') + '</div>';
    });
    document.getElementById('stepper').innerHTML = html;
    document.querySelectorAll('.dotcol').forEach(function (el) {
      el.onclick = function () {
        openPhase(+el.getAttribute('data-i'));
      };
    });
  }

  // ── metrics ──
  document.getElementById('head-pill').innerHTML = pill('BUILDING');
  var METRICS = [['142.3k', 'Tokens'], ['6m 44s', 'Wall'], ['$1.97', 'Cost', 'cost'], ['23', 'Events']];
  document.getElementById('metrics').innerHTML = METRICS.map(function (m) {
    return '<div class="mtile"><span class="mval ' + (m[2] || '') + '">' + m[0] + '</span><span class="mlabel">' + m[1] + '</span></div>';
  }).join('');

  // ── view tabs ──
  document.getElementById('vtabs').innerHTML = '<button class="vtab" data-active>Events</button><button class="vtab">Output</button>';

  // ── event log ──
  function L(c, t) {
    return '<div class="evline ev-' + c + '">' + t + '</div>';
  }
  function pad(s, n) {
    s = String(s);
    while (s.length < n) s += ' ';
    return s;
  }
  var EVENTS = [['accent', '09:02:11  ' + pad('TRANSITION', 14) + '  IDLE → STORMING'], ['phase', '09:02:40  ' + pad('PHASE', 14) + '  planner #1  storm ▸'], ['blue', '09:04:12  ' + pad('AGENT_DONE', 14) + '  planner #1  DONE  9 tools  88s  12.4k↑3.1k↓  $0.34'], ['accent', '09:05:01  ' + pad('TRANSITION', 14) + '  STORMING → PLANNING'], ['phase', '09:05:20  ' + pad('PHASE', 14) + '  planner #1  scope ▸'], ['green', '09:08:33  ' + pad('AGENT_DONE', 14) + '  planner #1  PASS  14 tools  121s  16.0k↑4.2k↓  $0.41'], ['accent', '09:08:40  ' + pad('TRANSITION', 14) + '  PLANNING → BUILDING'], ['purple', '09:09:01  ' + pad('AGENT_SPAWNED', 14) + '  builder #1'], ['yellow', '09:11:20  ' + pad('FILE_CREATED', 14) + '  src/auth/session.ts'], ['muted', '09:12:05  ' + pad('·', 14) + '  implement'], ['green', '09:18:30  ' + pad('AGENT_DONE', 14) + '  builder #1  PASS  31 tools  214s  18.2k↑6.4k↓  $0.71'], ['accent', '09:21:06  ' + pad('TRANSITION', 14) + '  BUILDING → REVIEWING'], ['red', '09:24:18  ' + pad('GATE_FAILED', 14) + '  lint:strict → BUILDING'], ['retro', '09:24:19  ' + pad('TRANSITION', 14) + '  ↩ REVIEWING → BUILDING'], ['purple', '09:24:40  ' + pad('AGENT_SPAWNED', 14) + '  builder #2'], ['yellow', '09:27:11  ' + pad('FILE_CREATED', 14) + '  src/auth/guards.ts'], ['blue', '09:33:50  ' + pad('AGENT_DONE', 14) + '  builder #2  DONE  22 tools  168s  14.8k↑5.1k↓  $0.62']];
  document.getElementById('evlog').innerHTML = EVENTS.map(function (e) {
    return L(e[0], e[1]);
  }).join('');
  var lg = document.getElementById('evlog');
  lg.scrollTop = lg.scrollHeight;

  // ── phase config modal ──
  var sel = {
    host: 'claude',
    agent: 'builder',
    skill: 'fix/build',
    stage: 'BUILDING'
  };
  function promptHTML() {
    var p = SKILL_PROMPTS[sel.skill] || {
      role: '—',
      body: '',
      steps: [],
      gate: '—'
    };
    var host = HOSTS.find(function (h) {
      return h.id === sel.host;
    });
    var out = '';
    out += '<span class="ph-h"># ' + sel.skill + '</span>  <span class="ph-c">· ' + sel.stage + ' stage</span>\n';
    out += '<span class="ph-c">Host:</span> ' + host.label + '   <span class="ph-c">Agent:</span> ' + sel.agent + '   <span class="ph-c">Conversation #2</span>\n\n';
    out += '<span class="ph-k">Role:</span> ' + p.role + '\n' + p.body + '\n\n';
    out += p.steps.map(function (s) {
      return '  • ' + s;
    }).join('\n') + '\n\n';
    out += '<span class="ph-k">Gate:</span> ' + p.gate;
    return out;
  }
  function renderModal() {
    var hostSeg = HOSTS.map(function (host) {
      return '<button class="segbtn" data-host="' + host.id + '" ' + (sel.host === host.id ? 'data-active' : '') + '>' + '<span class="host-dot" style="background:' + host.dot + '"></span>' + host.label + '</button>';
    }).join('');
    var agentChips = AGENTS.map(function (a) {
      return '<button class="chip" data-agent="' + a + '" ' + (sel.agent === a ? 'data-active' : '') + '>' + a + '</button>';
    }).join('');
    var skillChips = SKILLS.map(function (s) {
      return '<button class="chip" data-skill="' + s + '" ' + (sel.skill === s ? 'data-active' : '') + '>' + s + '</button>';
    }).join('');
    document.getElementById('pmodal').innerHTML = '<div class="pm-head">' + ic('square-terminal', 16) + '<span class="pm-title">Configure phase<span class="sub">— what runs when the pipeline enters this stage</span></span>' + '<span style="margin-left:auto">' + pill(sel.stage) + '</span>' + '<button class="btn-b" id="pm-x" style="padding:6px;border:none;background:transparent">' + ic('x', 16) + '</button>' + '</div>' + '<div class="pm-body">' + '<div class="fieldrow"><span class="flabel">CLI host</span><div class="seg">' + hostSeg + '</div></div>' + '<div class="fieldrow"><span class="flabel">Agent</span><div class="chips">' + agentChips + '</div></div>' + '<div class="fieldrow"><span class="flabel">Skill</span><div class="chips">' + skillChips + '</div></div>' + '<div class="fieldrow"><span class="flabel">Prompt preview</span><div class="prompt-box">' + promptHTML() + '</div></div>' + '</div>' + '<div class="pm-foot">' + '<button class="btn-b" id="pm-notebook">' + ic('book-open', 14) + 'Open skill in Notebook</button>' + '<span class="spacer"></span>' + '<button class="btn-b" id="pm-cancel">Cancel</button>' + '<button class="btn-cta" id="pm-apply">' + ic('check', 14) + 'Apply</button>' + '</div>';
    document.querySelectorAll('[data-host]').forEach(function (b) {
      b.onclick = function () {
        sel.host = b.getAttribute('data-host');
        renderModal();
      };
    });
    document.querySelectorAll('[data-agent]').forEach(function (b) {
      b.onclick = function () {
        sel.agent = b.getAttribute('data-agent');
        renderModal();
      };
    });
    document.querySelectorAll('[data-skill]').forEach(function (b) {
      b.onclick = function () {
        sel.skill = b.getAttribute('data-skill');
        renderModal();
      };
    });
    document.getElementById('pm-x').onclick = closePhase;
    document.getElementById('pm-cancel').onclick = closePhase;
    document.getElementById('pm-apply').onclick = closePhase;
    document.getElementById('pm-notebook').onclick = function () {
      window.location.href = '../skill-notebook/index.html?skill=' + encodeURIComponent(sel.skill);
    };
    PathlyIcons.inject(document.getElementById('pmodal'));
  }
  function openPhase(i) {
    var st = PIPELINE[i];
    sel = {
      host: sel.host,
      agent: st.agent,
      skill: st.skill,
      stage: st.state
    };
    renderModal();
    document.getElementById('overlay').setAttribute('data-open', '');
  }
  function closePhase() {
    document.getElementById('overlay').removeAttribute('data-open');
  }
  document.getElementById('overlay').onclick = function (e) {
    if (e.target === this) closePhase();
  };
  renderStepper();
  PathlyIcons.inject(document);
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/monitor/monitor.js", error: String((e && e.message) || e) }); }

// ui_kits/skill-notebook/notebook.js
try { (() => {
/* Pathly Studio — Skill Notebook kit logic (vanilla; static demo).
   Reads ?skill=<name> (from the Monitor "Open in Notebook" action). */
(function () {
  var ic = function (n, s) {
    return PathlyIcons.svg(n, {
      size: s || 14
    });
  };
  function vp(t) {
    return t.replace(/\{([^}]+)\}/g, '<span class="var-pill">$1</span>');
  }
  var SKILLS = {
    'fix/build': {
      crumbs: ['Skills', 'fix', 'build'],
      cells: [{
        type: 'body',
        title: 'fix/build',
        lines: ['FIXING stage for the {quick-fix} flow. Fast, focused, minimal — one targeted change.', 'Invoked by the {team} orchestrator when the FSM state is {BUILDING}.']
      }, {
        type: 'fragment',
        title: 'Role',
        full: true,
        lines: ['Stage orchestrator: Quick Fix.', 'Apply a {single}, well-scoped change. No multi-conversation planning, no PROGRESS.md churn.']
      }, {
        type: 'fragment',
        title: 'Procedure',
        lines: ['Read the issue description · locate the code · apply the minimal change · verify it passes.']
      }],
      composed: [['h1', 'fix/build'], ['p', 'FIXING stage for the quick-fix flow. Fast, focused, minimal — one targeted change.'], ['p', 'Invoked by the <code>team</code> orchestrator when the FSM state is <code>BUILDING</code>.'], ['h2', 'Role'], ['p', 'Stage orchestrator: Quick Fix. Apply a single, well-scoped change.'], ['ul', ['Read the issue description', 'Locate the code', 'Apply the minimal change', 'Verify it passes']], ['h2', 'Gate'], ['p', '<code>lint:strict</code>, <code>types:strict</code> must pass before REVIEWING.']],
      count: 6
    },
    'review/quality': {
      crumbs: ['Skills', 'review', 'quality'],
      cells: [{
        type: 'body',
        title: 'review/quality',
        lines: ['REVIEWING stage. Critique the diff against the plan and the quality bar.', 'Invoked when the FSM state is {REVIEWING}.']
      }, {
        type: 'fragment',
        title: 'Role',
        full: true,
        lines: ['Stage orchestrator: Reviewer.', 'Annotate findings and either {PASS} to TESTING or {REROUTE} back to BUILDING.']
      }],
      composed: [['h1', 'review/quality'], ['p', 'REVIEWING stage. Critique the diff against the plan and the quality bar.'], ['h2', 'Role'], ['p', 'Stage orchestrator: Reviewer.'], ['ul', ['Diff against PLAN.md', 'Run quality gates', 'Annotate findings', 'PASS or REROUTE → BUILDING']], ['h2', 'Gate'], ['p', 'No blocking findings before <code>TESTING</code>.']],
      count: 5
    },
    'team/build': {
      crumbs: ['Skills', 'team', 'build'],
      cells: [{
        type: 'body',
        title: 'team/build',
        lines: ['BUILDING stage for the {full} flow. Coordinate builder conversations across the plan.', 'Invoked by the {team} orchestrator when the FSM state is {BUILDING}.']
      }, {
        type: 'fragment',
        title: 'Role',
        full: true,
        lines: ['Team orchestrator: Full Build.', 'Split work, track {PROGRESS.md}, hand off to review.']
      }],
      composed: [['h1', 'team/build'], ['p', 'BUILDING stage for the full flow. Coordinate builder conversations across the plan.'], ['h2', 'Role'], ['p', 'Team orchestrator: Full Build.'], ['ul', ['Load the plan & conversation queue', 'Spawn builder per conversation', 'Reconcile diffs', 'Update PROGRESS.md']], ['h2', 'Gate'], ['p', 'All conversations <code>DONE</code> before REVIEWING.']],
      count: 5
    }
  };
  var param = new URLSearchParams(location.search).get('skill');
  var skill = SKILLS[param] || SKILLS['fix/build'];

  // crumbs
  document.getElementById('nb-crumbs').innerHTML = skill.crumbs.map(function (c, i) {
    var last = i === skill.crumbs.length - 1;
    return '<span class="c' + (last ? ' last' : '') + '">' + c + '</span>' + (last ? '' : '<span class="sep">›</span>');
  }).join('');
  document.getElementById('nb-undo').innerHTML = ic('undo-2', 14);
  document.getElementById('nb-redo').innerHTML = ic('redo-2', 14);
  document.getElementById('nb-export').innerHTML = ic('download', 13) + 'Export Skill';
  document.querySelector('.nb-search .si').innerHTML = ic('search', 14);

  // cells (with insert zones between)
  function cellHTML(cell, i) {
    var badge = cell.type === 'fragment' ? '<span class="cell-badge frag">fragment</span>' : '<span class="cell-badge body">body</span>';
    var actions = ['chevron-up', 'chevron-down', 'pencil', 'trash-2', 'more-horizontal'].map(function (a) {
      return '<button title="' + a + '">' + ic(a, 14) + '</button>';
    }).join('');
    var body = cell.lines.map(function (l) {
      return '<p>' + vp(l) + '</p>';
    }).join('');
    var showFull = cell.full ? '<span class="show-full">Show full content</span>' : '';
    return '<div class="cell ' + cell.type + '" data-i="' + i + '">' + '<div class="cell-head"><span class="cell-title">' + cell.title + '</span>' + badge + '<div class="cell-actions">' + actions + '</div></div>' + '<div class="cell-body">' + body + showFull + '</div></div>';
  }
  function insertHTML() {
    return '<div class="insert"><span class="plus">' + ic('plus', 13) + '</span></div>';
  }
  var cellsHTML = '';
  skill.cells.forEach(function (c, i) {
    cellsHTML += insertHTML() + cellHTML(c, i);
  });
  cellsHTML += insertHTML();
  document.getElementById('nb-cells').innerHTML = cellsHTML;
  document.querySelectorAll('.cell').forEach(function (el) {
    el.onclick = function () {
      document.querySelectorAll('.cell').forEach(function (c) {
        c.removeAttribute('data-active');
      });
      el.setAttribute('data-active', '');
    };
  });

  // preview
  document.getElementById('nb-preview-head').textContent = 'Composed skill · ' + skill.count + ' cells';
  document.getElementById('nb-preview-body').innerHTML = skill.composed.map(function (b) {
    if (b[0] === 'ul') return '<ul>' + b[1].map(function (li) {
      return '<li>' + li + '</li>';
    }).join('') + '</ul>';
    return '<' + b[0] + '>' + b[1] + '</' + b[0] + '>';
  }).join('');
  PathlyIcons.inject(document);
})();
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/skill-notebook/notebook.js", error: String((e && e.message) || e) }); }

__ds_ns.Button = __ds_scope.Button;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.ProgressBar = __ds_scope.ProgressBar;

__ds_ns.Spinner = __ds_scope.Spinner;

__ds_ns.StatePill = __ds_scope.StatePill;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.ContextMenu = __ds_scope.ContextMenu;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Card = __ds_scope.Card;

})();
