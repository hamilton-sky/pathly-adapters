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
  function ico(name, size) { return window.PathlyIcons ? window.PathlyIcons.svg(name, { size: size || 14 }) : ''; }
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
  var SKILLS = ['plan/storm','plan/scope','fix/build','team/build','review/quality','test/verify','retro/archive'];
  function activeSkill() {
    return cfg.activeSkill || new URLSearchParams(location.search).get('skill') || null;
  }

  // ── topbar ──
  function topbar() {
    var nav = [['flow','Canvas','layout-grid'],['notebook','Notebook','book-open'],['monitor','Monitor','activity']]
      .map(function (n) { return '<button class="tb-navbtn" ' + (cfg.activeNav === n[0] ? 'data-active' : '') + '>' + ico(n[2], 13) + n[1] + '</button>'; }).join('');
    return '<button class="tb-icon js-sb-toggle" title="Toggle sidebar">' + ico('menu', 15) + '</button>' +
      '<button class="tb-back">Projects</button>' +
      '<div class="tb-center">' +
        '<div class="tb-project">' + ico('database', 13) + '<span>' + (cfg.project || 'fsm-server-sqlite') + '</span><span class="chev">' + ico('chevron-down', 13) + '</span></div>' +
        '<button class="tb-icon" title="New window">' + ico('copy', 14) + '</button>' +
        '<div class="tb-nav">' + nav + '</div>' +
      '</div>' +
      '<div class="tb-right">' +
        '<button class="tb-icon" title="HQ">' + ico('brain', 14) + '</button>' +
        '<button class="tb-icon" title="Theme">' + ico('moon', 14) + '</button>' +
        '<button class="tb-icon" title="Terminal">' + ico('square-terminal', 14) + '</button>' +
        '<button class="tb-icon" title="Account">' + ico('globe', 14) + '</button>' +
      '</div>';
  }

  // ── full sidebar (workspace OR library tab) ──
  function fullSidebar() {
    var tab = cfg.sidebarTab === 'library' ? 'library' : 'workspace';
    var tabs = '<div class="sb-tabs">' +
      '<button class="sb-tab" ' + (tab === 'workspace' ? 'data-active' : '') + '>Workspace</button>' +
      '<button class="sb-tab" ' + (tab === 'library' ? 'data-active' : '') + '>Library</button></div>';
    var filter = '<div class="sb-filter"><input placeholder="' + (tab === 'library' ? 'Search skills…' : 'Filter…') + '" /></div>';

    var body;
    if (tab === 'library') {
      var as = activeSkill();
      body = '<div class="sb-label">Library · skills</div><div class="sb-tree">' +
        SKILLS.map(function (s) {
          return '<button class="sb-row" ' + (s === as ? 'data-active' : '') + '>' + ico('file-text', 13) +
            '<span class="skillname">' + s + '</span></button>';
        }).join('') + '</div>';
    } else {
      var tree = [['plan','Plan','fsm-server-sqlite'],['debugs','Debugs'],['explorations','Explorations'],['lessons','Lessons'],['pipeline','Pipeline-walkthrough']]
        .map(function (r) {
          return '<button class="sb-row" ' + (cfg.activeSide === r[0] ? 'data-active' : '') + '>' + ico('diamond', 13) +
            '<span>' + r[1] + '</span>' + (r[2] ? '<span class="tag">[' + r[2] + ']</span>' : '') + '</button>';
        }).join('');
      body = '<div class="sb-label">Workspace</div><div class="sb-tree">' + tree +
        '<div class="sb-divider"></div>' +
        '<button class="sb-row" ' + (cfg.activeSide === 'monitor' ? 'data-active' : '') + '><span class="sb-dot">●</span><span>Monitor</span></button>' +
        '<button class="sb-row" ' + (cfg.activeSide === 'db' ? 'data-active' : '') + '>' + ico('hard-drive', 13) + '<span>DB Explorer</span></button>' +
        '<button class="sb-row" ' + (cfg.activeSide === 'settings' ? 'data-active' : '') + '>' + ico('settings', 13) + '<span>Settings</span></button></div>';
    }

    return tabs + filter + body +
      '<div class="sb-profile"><span class="sb-avatar">SH</span>' +
      '<span class="who"><span class="name">shammai hamilton</span><span class="mail">shammaihamilton@…</span></span>' +
      '<button class="sb-signout">Sign out</button></div>';
  }

  // ── collapsed icon rail ──
  function railSidebar() {
    var libTab = cfg.sidebarTab === 'library';
    function btn(icon, title, active, dot) {
      return '<button class="sb-railbtn" title="' + title + '" ' + (active ? 'data-active' : '') + '>' +
        (dot ? '<span class="sb-dot">●</span>' : ico(icon, 16)) + '</button>';
    }
    return '<div class="sb-rail">' +
      btn('diamond', 'Workspace', !libTab && cfg.activeSide !== 'monitor' && cfg.activeSide !== 'db' && cfg.activeSide !== 'settings') +
      btn('book-open', 'Library', libTab) +
      '<div class="sb-rail-divider"></div>' +
      btn(null, 'Monitor', cfg.activeSide === 'monitor', true) +
      btn('hard-drive', 'DB Explorer', cfg.activeSide === 'db') +
      btn('settings', 'Settings', cfg.activeSide === 'settings') +
      '<div class="sb-rail-foot"><span class="sb-rail-avatar" title="shammai hamilton">SH</span></div>' +
      '</div>';
  }

  var tb = document.getElementById('pathly-topbar');
  var sb = document.getElementById('pathly-sidebar');

  function renderTopbar() {
    if (!tb) return;
    tb.className = 'topbar'; tb.innerHTML = topbar();
    PathlyIcons.inject(tb);
    var t = tb.querySelector('.js-sb-toggle');
    if (t) t.onclick = function () { manual = !isRail(); renderSidebar(); };
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
    if (isRail() !== prevRail) { prevRail = isRail(); renderSidebar(); }
  });
})();
