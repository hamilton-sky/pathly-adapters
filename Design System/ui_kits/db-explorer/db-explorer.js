/* Pathly Studio — DB Explorer kit logic (vanilla; static demo data). */
(function () {
  var ic = function (n, s) { return PathlyIcons.svg(n, { size: s || 14 }); };

  var STATE_COLOR = {
    PLANNING:  'var(--state-planning)',
    BUILDING:  'var(--state-building)',
    REVIEWING: 'var(--state-reviewing)',
    TESTING:   'var(--state-testing)',
    RETRO:     'var(--state-retro)',
    DONE:      'var(--state-done)',
    ERROR:     'var(--state-error)',
  };

  function pill(state) {
    var c = STATE_COLOR[state] || 'var(--text-muted)';
    return '<span class="pill" style="color:' + c + ';background:color-mix(in srgb,' + c + ' 13%,transparent);border-color:color-mix(in srgb,' + c + ' 38%,transparent)">' +
      '<span class="pdot" style="background:' + c + '"></span>' + state + '</span>';
  }

  function progress(done, total, color) {
    var pct = Math.round((done / total) * 100);
    return '<div class="prog"><div class="track"><div class="fill" style="width:' + pct + '%;background:' + color + '"></div></div>' +
      '<span class="frac">' + done + '/' + total + '</span></div>';
  }

  function dots(arr) {
    return '<div class="dots">' + arr.map(function (c) {
      return '<span style="flex:' + (c[1] || 1) + ';background:' + c[0] + '"></span>';
    }).join('') + '</div>';
  }

  // ── action buttons ──
  function actionBtns() {
    return [
      ['refresh-cw', 'Refresh'], ['hard-drive', 'Run Migration'], ['download', 'Export JSON'],
    ].map(function (b) { return '<button type="button" class="btn-b">' + ic(b[0], 13) + b[1] + '</button>'; }).join('');
  }
  document.getElementById('head-actions').innerHTML = actionBtns();

  // ── stats ──
  var stats = [
    ['Databases', '7'], ['Events', '202'], ['Invocations', '37'],
    ['Tokens', '1.05M'], ['Cost', '$14.20', 'cost'],
  ];
  document.getElementById('stats').innerHTML = stats.map(function (s) {
    return '<div class="stat"><div class="k">' + s[0] + '</div><div class="v ' + (s[2] || '') + '">' + s[1] + '</div></div>';
  }).join('');

  // ── feature data ──
  var G = 'var(--state-done)', B = 'var(--state-building)', R = 'var(--state-reviewing)',
      T = 'var(--state-testing)', P = 'var(--state-planning)', TE = 'var(--state-retro)';

  var features = [
    {
      name: 'fsm-sqlite', state: 'DONE', events: 35, inv: 8,
      tokens: '290,749', cost: '$3.64', ts: '10:06:05', done: 3, total: 3, pcol: G,
      dots: [[B],[R],[B],[T],[R],[B],[T],[R],[G,1.4]],
      convs: [
        { n: 1, phase: 'PLANNING → BUILDING', status: 'done', tokens: '78,442', cost: '$0.89' },
        { n: 2, phase: 'BUILDING → REVIEWING → BUILDING', status: 'done', tokens: '112,307', cost: '$1.42' },
        { n: 3, phase: 'TESTING → RETRO → DONE', status: 'done', tokens: '100,000', cost: '$1.33' },
      ],
    },
    {
      name: 'auth-refactor', state: 'BUILDING', events: 23, inv: 4,
      tokens: '142,300', cost: '$1.97', ts: '11:14:02', done: 1, total: 3, pcol: B,
      dots: [[P],[B],[B,1.6],[R]],
      convs: [
        { n: 1, phase: 'PLANNING → BUILDING', status: 'done', tokens: '45,200', cost: '$0.62' },
        { n: 2, phase: 'BUILDING', status: 'active', tokens: '97,100', cost: '$1.35' },
        { n: 3, phase: 'REVIEWING → TESTING → DONE', status: 'todo', tokens: '—', cost: '—' },
      ],
    },
    {
      name: 'payments-webhook', state: 'REVIEWING', events: 28, inv: 6,
      tokens: '188,400', cost: '$2.41', ts: '09:31:50', done: 2, total: 3, pcol: R,
      dots: [[B],[R],[B],[T],[R,1.5]],
      convs: [
        { n: 1, phase: 'PLANNING → BUILDING → REVIEWING', status: 'done', tokens: '62,100', cost: '$0.78' },
        { n: 2, phase: 'BUILDING → REVIEWING', status: 'done', tokens: '81,400', cost: '$1.04' },
        { n: 3, phase: 'REVIEWING', status: 'active', tokens: '44,900', cost: '$0.59' },
      ],
    },
    {
      name: 'search-index', state: 'TESTING', events: 19, inv: 5,
      tokens: '96,800', cost: '$1.12', ts: '13:20:11', done: 2, total: 4, pcol: T,
      dots: [[B],[R],[T,1.6]],
      convs: [
        { n: 1, phase: 'PLANNING → BUILDING', status: 'done', tokens: '28,400', cost: '$0.31' },
        { n: 2, phase: 'BUILDING → REVIEWING → TESTING', status: 'done', tokens: '68,400', cost: '$0.81' },
        { n: 3, phase: 'TESTING', status: 'active', tokens: '—', cost: '—' },
        { n: 4, phase: 'RETRO → DONE', status: 'todo', tokens: '—', cost: '—' },
      ],
    },
    {
      name: 'cache-layer', state: 'DONE', events: 41, inv: 9,
      tokens: '214,600', cost: '$3.02', ts: '08:48:33', done: 4, total: 4, pcol: G,
      dots: [[B],[R],[T],[B],[R],[TE],[G,1.4]],
      convs: [
        { n: 1, phase: 'PLANNING → BUILDING', status: 'done', tokens: '44,200', cost: '$0.57' },
        { n: 2, phase: 'BUILDING → REVIEWING → TESTING', status: 'done', tokens: '68,900', cost: '$0.89' },
        { n: 3, phase: 'BUILDING → REVIEWING → TESTING', status: 'done', tokens: '71,300', cost: '$0.95' },
        { n: 4, phase: 'RETRO → DONE', status: 'done', tokens: '30,200', cost: '$0.61' },
      ],
    },
    {
      name: 'notifications', state: 'PLANNING', events: 6, inv: 1,
      tokens: '18,900', cost: '$0.31', ts: '14:02:19', done: 0, total: 3, pcol: P,
      dots: [[P,2]],
      convs: [
        { n: 1, phase: 'PLANNING', status: 'active', tokens: '18,900', cost: '$0.31' },
        { n: 2, phase: 'BUILDING → REVIEWING', status: 'todo', tokens: '—', cost: '—' },
        { n: 3, phase: 'TESTING → RETRO → DONE', status: 'todo', tokens: '—', cost: '—' },
      ],
    },
  ];

  // ── render feature grid ──
  function renderGrid(list) {
    document.getElementById('grid').innerHTML = list.map(function (f, i) {
      return '<div class="feat" data-i="' + features.indexOf(f) + '" data-state="' + f.state + '">' +
        '<div class="top"><span class="fname">' + f.name + '</span>' + pill(f.state) + '</div>' +
        dots(f.dots) +
        '<div class="metrics">' +
          '<div><div class="mk">Events</div><div class="mv">' + f.events + '</div></div>' +
          '<div><div class="mk">Invocations</div><div class="mv">' + f.inv + '</div></div>' +
          '<div><div class="mk">Tokens</div><div class="mv">' + f.tokens + '</div></div>' +
          '<div><div class="mk">Cost</div><div class="mv cost">' + f.cost + '</div></div>' +
        '</div>' +
        '<div class="foot"><span class="ts">' + f.ts + '</span>' + progress(f.done, f.total, f.pcol) + '</div>' +
      '</div>';
    }).join('');

    document.querySelectorAll('.feat').forEach(function (el) {
      el.onclick = function () { openModal(features[+el.getAttribute('data-i')]); };
    });
    PathlyIcons.inject(document.getElementById('grid'));
  }

  // ── filter bar ──
  var filterBar = document.getElementById('db-filter-bar');
  filterBar.innerHTML =
    '<div class="db-search-wrap">' +
      ic('search', 13) +
      '<input type="text" id="db-search" placeholder="Filter features…" autocomplete="off">' +
    '</div>' +
    '<span class="db-count" id="db-count"></span>';

  function updateCount(n) {
    document.getElementById('db-count').textContent = n + ' of ' + features.length;
  }

  renderGrid(features);
  updateCount(features.length);

  document.getElementById('db-search').addEventListener('input', function () {
    var q = this.value.toLowerCase().trim();
    var filtered = q ? features.filter(function (f) {
      return f.name.toLowerCase().includes(q) || f.state.toLowerCase().includes(q);
    }) : features;
    renderGrid(filtered);
    updateCount(filtered.length);
  });

  // ── modal tab content ──
  var TRANSITIONS = [
    ['PLANNING','09:02:11','6m 29s'], ['BUILDING','09:08:40','12m 26s'], ['REVIEWING','09:21:06','6m 27s'],
    ['TESTING','09:27:33','6m 45s'], ['BUILDING','09:34:18','11m 44s'], ['REVIEWING','09:46:02','6m 47s'],
    ['TESTING','09:52:49','4m 38s'], ['RETRO','09:57:27','3m 12s'], ['DONE','10:06:05','—'],
  ];
  var AGENTS = [
    ['builder','conv 1', B, 0.39], ['reviewer','conv 1', R, 0.71], ['builder','conv 2', B, 0.42],
    ['tester','conv 2', T, 0.23], ['reviewer','conv 2', R, 0.74], ['builder','conv 3', B, 0.33],
    ['tester','conv 3', T, 0.24], ['reviewer','conv 3', R, 0.58],
  ];
  var maxCost = Math.max.apply(null, AGENTS.map(function (a) { return a[3]; }));

  function convsHTML(f) {
    var CONV_COLOR = {
      done: 'var(--state-done)', active: 'var(--state-building)',
      blocked: 'var(--red)', todo: 'var(--text-muted)',
    };
    var rows = f.convs.map(function (c) {
      var col = CONV_COLOR[c.status] || 'var(--text-muted)';
      return '<div class="conv-row" data-status="' + c.status + '">' +
        '<span class="conv-n" style="color:' + col + '">conv ' + c.n + '</span>' +
        '<span class="conv-phase">' + c.phase + '</span>' +
        '<span class="conv-stats">' + c.tokens + ' · ' + c.cost + '</span>' +
        '</div>';
    }).join('');
    return '<p class="m-sublabel">Conversations · ' + f.convs.length + '</p>' +
      '<div class="conv-list">' + rows + '</div>';
  }

  function timelineHTML() {
    var html = '';
    TRANSITIONS.forEach(function (t, i) {
      html += '<div class="tstep">' + pill(t[0]) + '<span class="tstamp">' + t[1] + '</span><span class="tdur">' + t[2] + '</span></div>';
      if (i < TRANSITIONS.length - 1) html += '<span class="tarrow">' + ic('chevron-right', 16) + '</span>';
    });
    var legend = ['PLANNING','BUILDING','REVIEWING','TESTING','RETRO','DONE'].map(function (s) {
      return '<span><i style="background:' + STATE_COLOR[s] + '"></i>' + s + '</span>';
    }).join('');
    return '<p class="m-sublabel">State machine · 9 transitions</p>' +
      '<div class="timeline">' + html + '</div>' +
      '<div class="legend">' + legend + '</div>';
  }

  function agentsHTML() {
    var rows = AGENTS.map(function (a) {
      var w = Math.round((a[3] / maxCost) * 100);
      var grad = 'linear-gradient(90deg, color-mix(in srgb,' + a[2] + ' 55%,transparent), ' + a[2] + ')';
      return '<div class="arow"><span class="aname">' + a[0] + ' <span class="conv">(' + a[1] + ')</span></span>' +
        '<div class="abar" style="width:' + w + '%;background:' + grad + '"></div>' +
        '<span class="acost">$' + a[3].toFixed(2) + '</span></div>';
    }).join('');
    return '<p class="m-sublabel">Cost per invocation · 8 agents · $3.64 total</p><div class="agents">' + rows + '</div>';
  }

  function sqlHTML() {
    return '<p class="m-sublabel">SQL console</p>' +
      '<div style="font-family:var(--font-family-mono);font-size:var(--font-size-base);background:var(--bg-terminal);border:var(--border);border-radius:var(--radius-md);padding:14px;color:var(--text-secondary)">' +
      '<span style="color:var(--purple)">SELECT</span> stage, <span style="color:var(--purple)">count</span>(*) <span style="color:var(--purple)">FROM</span> events <span style="color:var(--purple)">GROUP BY</span> stage;</div>' +
      '<div style="margin-top:12px;color:var(--text-muted);font-size:var(--font-size-sm)">9 rows · 4ms</div>';
  }

  function eventsHTML() {
    var ev = [
      ['09:02:11','STAGE_ENTER','PLANNING', B],
      ['09:08:40','AGENT_DONE','builder · $0.39', G],
      ['09:21:06','STAGE_ENTER','REVIEWING', R],
      ['09:34:18','STAGE_REROUTE','→ BUILDING', 'var(--orange)'],
      ['10:06:05','PIPELINE_DONE','290,749 tok · $3.64', G],
    ];
    return '<p class="m-sublabel">Events · 47</p><div style="display:flex;flex-direction:column;gap:2px">' +
      ev.map(function (e) {
        return '<div style="display:grid;grid-template-columns:80px 150px 1fr;gap:12px;padding:8px 10px;border-radius:var(--radius-sm);font-size:var(--font-size-base)">' +
          '<span style="font-family:var(--font-family-mono);color:var(--text-muted)">' + e[0] + '</span>' +
          '<span style="font-family:var(--font-family-mono);color:' + e[3] + '">' + e[1] + '</span>' +
          '<span style="color:var(--text-secondary)">' + e[2] + '</span></div>';
      }).join('') + '</div>';
  }

  // ── modal ──
  var activeFeature = null;
  var currentTab = 'convs';

  function buildTabs(f) {
    return [
      ['convs',     'Conversations', String(f.convs.length), function () { return convsHTML(f); }],
      ['timeline',  'Timeline',      '9',                    timelineHTML],
      ['events',    'Events',        '47',                   eventsHTML],
      ['agents',    'Agents',        '8',                    agentsHTML],
      ['sql',       'SQL',           '',                     sqlHTML],
    ];
  }

  function renderModal(f) {
    var tabs = buildTabs(f);
    var tabsHTML = tabs.map(function (t) {
      return '<button type="button" class="m-tab" data-tab="' + t[0] + '" ' + (t[0] === currentTab ? 'data-active' : '') + '>' +
        t[1] + (t[2] ? '<span class="ct">' + t[2] + '</span>' : '') + '</button>';
    }).join('');
    var bodyFn = tabs.find(function (t) { return t[0] === currentTab; })[3];

    document.getElementById('modal').innerHTML =
      '<div class="m-head">' + pill(f.state) +
        '<span class="m-name">' + f.name + '</span>' +
        '<span class="m-meta">convs <b>' + f.done + '/' + f.total + '</b></span>' +
        '<span class="m-meta">events <b>' + f.events + '</b></span>' +
        '<span class="m-meta">cost <b>' + f.cost + '</b></span>' +
        '<button type="button" class="tb-icon m-close" id="m-close">' + ic('x', 16) + '</button>' +
      '</div>' +
      '<div class="m-actions">' + actionBtns() +
        '<span class="m-runner">runner: ' + (f.state === 'DONE' ? 'finished' : 'running') +
        ' · ' + f.tokens + ' tok · <b>' + f.cost + '</b></span>' +
      '</div>' +
      '<div class="m-tabs">' + tabsHTML + '</div>' +
      '<div class="m-body" id="m-body">' + bodyFn() + '</div>';

    document.getElementById('m-close').onclick = closeModal;
    document.querySelectorAll('.m-tab').forEach(function (b) {
      b.onclick = function () { currentTab = b.getAttribute('data-tab'); renderModal(f); };
    });
    PathlyIcons.inject(document.getElementById('modal'));
  }

  function openModal(f) {
    activeFeature = f;
    currentTab = 'convs';
    renderModal(f);
    document.getElementById('overlay').setAttribute('data-open', '');
  }

  function closeModal() {
    document.getElementById('overlay').removeAttribute('data-open');
  }

  document.getElementById('overlay').onclick = function (e) {
    if (e.target === this) closeModal();
  };

  PathlyIcons.inject(document);
})();
