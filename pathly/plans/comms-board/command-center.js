/* Pathly Studio — Command Center (comms board) kit.
   Vanilla JS, design-system tokens, self-hosted lucide. No emoji in product UI:
   message types are classified by left-accent bar + uppercase mono type label.
   Interactions: toggle board sections, presets, side-by-side/stacked, resize,
   sidebar accordion + "set as main feature", answer questions, compose & post,
   per-feature read-scope toggles, resolve warnings/escalations. */
(function () {
  function ico(n, s) { return window.PathlyIcons ? window.PathlyIcons.svg(n, { size: s || 14 }) : ''; }
  var $ = function (sel, r) { return (r || document).querySelector(sel); };
  var uid = 0; var nid = function () { return 'm' + (++uid); };

  // ── agent identity ──
  var AGENTS = {
    you:       { label: 'you',       cls: 'you',  icon: null },
    builder:   { label: 'builder',   color: 'var(--state-building)',  icon: 'square-terminal' },
    reviewer:  { label: 'reviewer',  color: 'var(--state-reviewing)', icon: 'search' },
    architect: { label: 'architect', color: 'var(--state-planning)',  icon: 'git-branch' },
    tester:    { label: 'tester',    color: 'var(--state-testing)',   icon: 'circle-check' },
    retro:     { label: 'retro',     color: 'var(--state-retro)',     icon: 'history' }
  };
  function avatar(who) {
    var a = AGENTS[who] || AGENTS.builder;
    if (who === 'you') return '<span class="avatar you">YOU</span>';
    return '<span class="avatar" style="background:' + a.color + '">' + ico(a.icon, 13) + '</span>';
  }
  var STAGE_COLOR = {
    PLANNING: 'var(--state-planning)', BUILDING: 'var(--state-building)', REVIEWING: 'var(--state-reviewing)',
    TESTING: 'var(--state-testing)', RETRO: 'var(--state-retro)', DONE: 'var(--state-done)'
  };

  // ── feature roster (the All-Features sidebar) ──
  var features = [
    { id: 'send-to-agent-diff', stage: 'BUILDING', conv: 3, status: 'running', agent: 'builder',
      last: '<b>builder:</b> phases 7–9 complete. Wiring DiffViewer scroll sync.', scope: { feature: true, project: true, global: true } },
    { id: 'comms-board', stage: 'PLANNING', conv: 1, status: 'idle', agent: 'architect',
      last: '<b>architect:</b> drafting comms_messages + sqlite-vec schema.', scope: { feature: true, project: true, global: true } },
    { id: 'event-phase-summary', stage: 'REVIEWING', conv: 2, status: 'blocked', agent: 'reviewer',
      last: '<b>reviewer:</b> 3 failures — missing null guards in summary writer.', scope: { feature: true, project: true, global: false } },
    { id: 'otel-export-cli', stage: 'DONE', conv: 4, status: 'done', agent: 'retro',
      last: '<b>retro:</b> archived. 64.8k tok · $3.64 · 6m 29s.', scope: { feature: true, project: true, global: true } }
  ];

  // ── board messages, keyed by scope ──
  var boards = {
    'send-to-agent-diff': [
      { id: nid(), type: 'decision', from: 'you', stage: 'REVIEWING', time: '2h', pinned: true,
        text: 'Skip rename detection — that is v2 scope.' },
      { id: nid(), type: 'status', from: 'builder', stage: 'BUILDING', time: '8m',
        text: 'Phases 7–9 complete. <code>DiffViewer.tsx</code> created. Starting scroll-sync.' },
      { id: nid(), type: 'discovery', from: 'builder', stage: 'BUILDING', time: '6m',
        text: 'Virtual scroll is needed when a diff exceeds ~500 lines, or the panes jank.' },
      { id: nid(), type: 'question', from: 'builder', stage: 'BUILDING', time: '4m', status: 'pending',
        text: 'Two approaches for scroll sync between the diff panes. Preference?',
        options: [
          { id: 'a', label: 'CSS scroll-snap', desc: 'simple, native' },
          { id: 'b', label: 'JS IntersectionObserver', desc: 'more control' }
        ] }
    ],
    'comms-board': [
      { id: nid(), type: 'decision', from: 'you', stage: 'PLANNING', time: '1h', pinned: true,
        text: 'Embeddings: <code>all-MiniLM-L6-v2</code>, 384-dim. No external API cost.' },
      { id: nid(), type: 'status', from: 'architect', stage: 'PLANNING', time: '12m',
        text: 'Schema drafted: <code>comms_messages</code> + <code>comms_embeddings</code> (vec0).' }
    ],
    'event-phase-summary': [
      { id: nid(), type: 'warning', from: 'reviewer', stage: 'REVIEWING', time: '3m', status: 'open',
        text: 'Rename detection missing and 2 null-guard failures in the summary writer.' }
    ],
    'otel-export-cli': [
      { id: nid(), type: 'status', from: 'retro', stage: 'RETRO', time: '1d',
        text: 'Run archived. Lessons written to <code>pathly/lessons/</code>.' }
    ],
    'project': [
      { id: nid(), type: 'decision', from: 'you', time: '4d', pinned: true, text: 'Use <code>shadcn/ui</code> for all new components.' },
      { id: nid(), type: 'decision', from: 'you', time: '4d', pinned: true, text: 'Auth is handled by <code>/lib/auth.ts</code> — never roll custom auth.' },
      { id: nid(), type: 'decision', from: 'you', time: '6d', pinned: true, text: 'TypeScript <code>strict</code> mode across the repo.' },
      { id: nid(), type: 'artifact', from: 'you', time: '3d', artifact: 'ARCHITECTURE.md', atype: 'md',
        text: 'Adapter surfaces per host, deployment structure, host detection, installed manifests…' },
      { id: nid(), type: 'status', from: 'reviewer', stage: 'REVIEWING', time: '20m', text: 'Found 2 issues in <code>event-phase-summary</code>; surfaced to its board.' }
    ],
    'global': [
      { id: nid(), type: 'decision', from: 'you', time: '2w', pinned: true, text: 'Use <code>Zod</code> for all schema validation.' },
      { id: nid(), type: 'decision', from: 'you', time: '3w', pinned: true, text: 'No class components anywhere in the org.' },
      { id: nid(), type: 'decision', from: 'you', time: '5w', pinned: true, text: 'All user-facing errors must include an error code.' },
      { id: nid(), type: 'artifact', from: 'you', time: '5w', artifact: 'auth-pattern.ts', atype: 'code',
        text: 'export async function withAuth(req: Request) { /* always use this pattern */ }' }
    ]
  };

  var SCOPES = {
    feature: { icon: 'git-branch', label: 'Feature board', title: 'FEATURE BOARD' },
    project: { icon: 'folder',     label: 'Project',       title: 'PROJECT BOARD' },
    global:  { icon: 'globe',      label: 'Global',        title: 'GLOBAL BOARD' }
  };
  var TYPE_ORDER = ['nudge', 'decision', 'question', 'task', 'discovery', 'warning'];

  // ── UI state ──
  var st = {
    sections: ['feature'],          // visible board sections, click-order
    direction: 'row',               // 'row' (side-by-side) | 'column' (stacked)
    preset: 'focus',
    mainFeature: 'send-to-agent-diff',
    sidebarCollapsed: false,
    openFeature: 'send-to-agent-diff',
    sizes: {},                      // flex-basis px per section
    flash: null
  };

  var PRESETS = {
    board:    { sections: ['global', 'project', 'feature'], direction: 'row',    desc: 'G·P·F' },
    pipeline: { sections: ['feature'], direction: 'row', sidebar: false,         desc: 'F + nav' },
    focus:    { sections: ['feature'], direction: 'row', sidebarCollapse: true,  desc: 'F only' }
  };

  // ════ render ════
  var root = document.getElementById('cc-root');

  function scopeData(scope) {
    if (scope === 'feature') return boards[st.mainFeature] || [];
    return boards[scope] || [];
  }

  function render() {
    root.innerHTML =
      headerHTML() +
      '<div class="cc-body">' + sidebarHTML() + sectionsHTML() + '</div>';
    PathlyIcons.inject(root);
    bind();
    st.flash = null;
  }

  function headerHTML() {
    var tabs = ['feature', 'project', 'global'].map(function (s) {
      var on = st.sections.indexOf(s) > -1;
      var sc = SCOPES[s];
      var pend = s === 'feature' ? pendingCount(st.mainFeature) : 0;
      return '<button class="cc-tab" data-tab="' + s + '" ' + (on ? 'data-on' : '') + '>' +
        ico(sc.icon, 13) + '<span>' + sc.label + '</span>' +
        '<span class="st">' + (on ? '\u25CF' : '\u25CB') + '</span>' +
        (pend ? '<span class="feat-badge msg">' + pend + '</span>' : '') + '</button>';
    }).join('');
    var dirLabel = st.direction === 'row' ? 'side by side' : 'stacked';
    var dirIcon = st.direction === 'row' ? 'columns-2' : 'list';
    var showDir = st.sections.length >= 2;
    return '<div class="cc-head">' +
      '<div class="cc-brand"><span class="dot">\u25C8</span>Command Center</div>' +
      '<div class="cc-tabs">' + tabs +
        '<button class="cc-tab add" data-addhint title="Toggle a board section">' + ico('plus', 13) + 'Add</button>' +
      '</div>' +
      '<div class="cc-head-right">' +
        (showDir ? '<button class="cc-ctl" data-dir>' + ico(dirIcon, 13) + dirLabel + '</button>' : '') +
        '<div class="cc-menu-wrap">' +
          '<button class="cc-ctl" data-presets>' + ico('layout-grid', 13) + 'Presets' + ico('chevron-down', 12) + '</button>' +
          '<div class="cc-menu" id="presetMenu">' +
            presetItem('board', 'Board view', 'Global · Project · Feature') +
            presetItem('pipeline', 'Pipeline view', 'Feature + features rail') +
            presetItem('focus', 'Focus', 'Feature board, full width') +
          '</div>' +
        '</div>' +
        '<button class="cc-ctl cc-exit" data-exit title="Exit Command Center">' + ico('x', 15) + '</button>' +
      '</div></div>';
  }
  function presetItem(id, name, desc) {
    return '<button class="cc-menu-item" data-preset="' + id + '" ' + (st.preset === id ? 'data-active' : '') + '>' +
      (st.preset === id ? ico('check', 13) : '<span style="width:13px"></span>') +
      '<span>' + name + '</span><span class="desc">' + desc + '</span></button>';
  }

  function pendingCount(fid) {
    return (boards[fid] || []).filter(function (m) {
      return (m.type === 'question' && m.status === 'pending') || (m.type === 'warning' && m.status === 'open') || m.type === 'escalation';
    }).length;
  }

  // ── sidebar ──
  function sidebarHTML() {
    if (st.sidebarCollapsed) {
      var rail = features.map(function (f) {
        var pend = pendingCount(f.id);
        var blocked = f.status === 'blocked';
        return '<button class="cc-railbtn" data-feat="' + f.id + '" title="' + f.id + '">' +
          '<span class="feat-stdot st-' + f.status + '"></span>' +
          (pend ? '<span class="rail-badge ' + (blocked ? 'blk' : '') + '">' + (blocked ? '!' : pend) + '</span>' : '') + '</button>';
      }).join('');
      return '<div class="cc-sidebar collapsed">' +
        '<div class="cc-sb-head"><button class="cc-sb-collapse" data-sbtoggle title="Expand">' + ico('panel-left', 15) + '</button></div>' +
        '<div class="cc-sb-rail">' + rail + '</div></div>';
    }
    var cards = features.map(featureCard).join('');
    return '<div class="cc-sidebar">' +
      '<div class="cc-sb-head"><span class="cc-sb-title">All Features</span>' +
        '<span class="cc-sb-count">' + features.length + '</span>' +
        '<button class="cc-sb-collapse" data-sbtoggle title="Collapse">' + ico('panel-left', 15) + '</button></div>' +
      '<div class="cc-sb-list">' + cards + '</div></div>';
  }

  function featureCard(f) {
    var open = st.openFeature === f.id;
    var isMain = st.mainFeature === f.id;
    var pend = pendingCount(f.id);
    var badges = '';
    if (f.status === 'blocked') badges += '<span class="feat-badge blk">' + ico('history', 9) + 'blocked</span>';
    else if (pend) badges += '<span class="feat-badge msg">' + ico('message-square', 9) + pend + '</span>';
    var acts = '';
    if (!isMain) acts += '<button class="feat-act primary" data-setmain="' + f.id + '">' + ico('external-link', 12) + 'Set as main</button>';
    else acts += '<span class="feat-act" style="cursor:default;color:var(--accent);border-color:var(--accent-border)">' + ico('check', 12) + 'Main feature</span>';
    if (f.status === 'blocked') {
      acts += '<button class="feat-act warn" data-unblock="' + f.id + '">' + ico('play', 12) + 'Unblock</button>';
      acts += '<button class="feat-act" data-skip="' + f.id + '">' + ico('skip-forward', 12) + 'Skip</button>';
    } else if (f.status === 'running') {
      acts += '<button class="feat-act" data-pause="' + f.id + '">' + ico('pause', 12) + 'Pause</button>';
    }
    return '<div class="feat' + (open ? ' open' : '') + (isMain ? ' main' : '') + '" data-fcard="' + f.id + '">' +
      '<button class="feat-bar" data-toggle="' + f.id + '">' +
        '<span class="feat-stdot st-' + f.status + '"></span>' +
        '<span class="feat-name">' + f.id + '</span>' +
        '<span class="feat-badges">' + badges + '</span>' +
        '<span class="feat-chev">' + ico(open ? 'chevron-up' : 'chevron-down', 14) + '</span>' +
      '</button>' +
      '<div class="feat-body">' +
        '<div class="feat-stage"><span class="stg" style="color:' + (STAGE_COLOR[f.stage] || 'var(--text-muted)') + '">' + f.stage + '</span>' +
          '<span class="feat-conv">conv ' + f.conv + ' · ' + f.status + '</span></div>' +
        '<div class="feat-last">' + f.last + '</div>' +
        '<div class="feat-acts">' + acts + '</div>' +
      '</div></div>';
  }

  // ── sections ──
  function sectionsHTML() {
    if (!st.sections.length) {
      return '<div class="cc-sections"><div class="cc-empty">' + ico('layout-grid', 30) +
        '<p>No board sections open. Use the tabs above to show the <b>Feature</b>, <b>Project</b>, or <b>Global</b> board.</p></div></div>';
    }
    var parts = [];
    st.sections.forEach(function (s, i) {
      if (i > 0) parts.push('<div class="cc-resize" data-resize="' + i + '"></div>');
      parts.push(boardHTML(s, i));
    });
    return '<div class="cc-sections ' + (st.direction === 'column' ? 'stacked' : '') + '">' + parts.join('') + '</div>';
  }

  function flexBasis(scope, i) {
    if (st.sizes[scope]) return 'flex:0 0 ' + st.sizes[scope] + 'px;';
    // Board view default asymmetric widths: Feature 50 / Project 30 / Global 20
    if (st.preset === 'board' && st.direction === 'row') {
      var w = { feature: 50, project: 30, global: 20 }[scope] || 33;
      return 'flex:' + w + ' 1 0;';
    }
    return 'flex:1 1 0;';
  }

  function boardHTML(scope, i) {
    var sc = SCOPES[scope];
    var data = scopeData(scope);
    var name = scope === 'feature' ? st.mainFeature : (scope === 'project' ? 'pathly-adapters' : 'all projects · all features');
    var pins = data.filter(function (m) { return m.pinned; });
    var thread = data.filter(function (m) { return !m.pinned; });

    var pinHTML = pins.length ? '<div class="bs-pins">' + pins.map(function (m) {
      return '<div class="pin' + (st.flash === m.id ? ' flash' : '') + '">' + ico('star', 14) +
        '<div><div class="pin-txt">' + m.text + '</div>' +
        '<div class="pin-meta">' + (AGENTS[m.from] || {}).label + (m.stage ? ' · ' + m.stage : '') + ' · ' + m.time + ' ago · <span class="pin-scope">' + scope + ' scope</span></div></div></div>';
    }).join('') + '</div>' : '';

    var msgs = thread.map(messageHTML).join('') ||
      '<div class="cc-empty" style="padding:24px">' + ico('message-square', 22) + '<p>No messages on this board yet.</p></div>';

    return '<div class="board" data-board="' + scope + '" style="' + flexBasis(scope, i) + '">' +
      '<div class="bs-head">' +
        '<span class="bs-icon" style="color:var(--accent)">' + ico(sc.icon, 15) + '</span>' +
        '<span class="bs-scope">' + sc.title + '</span><span class="bs-sep">—</span><span class="bs-name">' + name + '</span>' +
        '<div class="bs-head-acts">' +
          '<button class="bs-iconbtn" data-attach="' + scope + '" title="Attach artifact">' + ico('plus', 15) + '</button>' +
          '<button class="bs-iconbtn close" data-close="' + scope + '" title="Hide section">' + ico('x', 15) + '</button>' +
        '</div></div>' +
      '<div class="bs-thread">' + pinHTML + msgs + '</div>' +
      footerHTML(scope) + '</div>';
  }

  function messageHTML(m) {
    var a = AGENTS[m.from] || AGENTS.builder;
    var meta = '<div class="msg-meta">' + avatar(m.from) +
      '<span class="msg-author">' + a.label + '</span>' +
      (m.stage ? '<span class="msg-stage" style="color:' + (STAGE_COLOR[m.stage] || 'var(--text-muted)') + '">' + m.stage + '</span>' : '') +
      (m.ack ? '<span class="msg-ack">' + ico('check', 11) + 'acknowledged</span>' : '') +
      '<span class="msg-time">' + m.time + ' ago</span></div>';

    var body = '';
    if (m.type === 'artifact') {
      body = '<div class="art"><span class="art-ico">' + ico(m.atype === 'code' ? 'file-text' : 'file-text', 15) + '</span>' +
        '<span class="art-name">' + m.artifact + '</span></div>' +
        '<div class="art-excerpt">' + m.text + '</div>' +
        '<div class="art-q">' + ico('search', 11) + 'agents can query this by content</div>';
    } else if (m.type === 'question') {
      var opts = (m.options || []).map(function (o) {
        var chosen = m.answer === o.id;
        return '<button class="opt' + (chosen ? ' chosen' : '') + '" data-answer="' + m.id + '" data-opt="' + o.id + '">' +
          '<span class="ring"></span><span>' + o.label + '</span><span class="odesc">' + (o.desc || '') + '</span></button>';
      }).join('');
      var foot = m.status === 'answered'
        ? '<div class="q-foot"><span class="q-status answered">' + ico('check', 11) + 'answered · injected at next /next_action</span></div>'
        : '<div class="q-foot"><span class="q-status pending"><span class="q-spin"></span>awaiting answer · non-blocking</span></div>';
      body = '<div class="msg-text">' + m.text + '</div><div class="opts">' + opts + '</div>' + foot;
    } else if ((m.type === 'warning' || m.type === 'escalation')) {
      body = '<div class="msg-text">' + m.text + '</div>';
      if (m.status === 'resolved') {
        body += '<div class="msg-resolved">' + ico('check', 11) + (m.resolution || 'resolved') + '</div>';
      } else {
        body += '<div class="msg-acts">' +
          '<button class="msg-act danger" data-resolve="' + m.id + '" data-mode="block">' + ico('history', 12) + 'Block stage</button>' +
          '<button class="msg-act go" data-resolve="' + m.id + '" data-mode="note">' + ico('check', 12) + 'Note as future work</button>' +
          '<button class="msg-act" data-resolve="' + m.id + '" data-mode="ignore">' + ico('eye-off', 12) + 'Ignore</button>' +
        '</div>';
      }
    } else {
      body = '<div class="msg-text">' + m.text + '</div>';
    }
    var typeIco = m.type === 'decision' ? ico('star', 10) : (m.type === 'artifact' ? ico('file-text', 10) : '');
    return '<div class="msg' + (st.flash === m.id ? ' flash' : '') + '" data-msg="' + m.id + '">' + meta +
      '<div class="msg-card" data-type="' + m.type + '"><div class="msg-type">' + typeIco + m.type + '</div>' + body + '</div></div>';
  }

  function footerHTML(scope) {
    var scopes = '';
    if (scope === 'feature') {
      var f = features.filter(function (x) { return x.id === st.mainFeature; })[0] || { scope: {} };
      scopes = '<div class="bs-scopes"><span class="lbl">Reads:</span>' +
        ['feature', 'project', 'global'].map(function (k) {
          var on = f.scope[k];
          return '<button class="scope-chk" data-scope="' + k + '" ' + (on ? 'data-on' : '') + '>' +
            '<span class="box">' + (on ? ico('check', 8) : '') + '</span>' + k.charAt(0).toUpperCase() + k.slice(1) + '</button>';
        }).join('') + '</div>';
    }
    var opts = TYPE_ORDER.map(function (t) { return '<option value="' + t + '">' + t + '</option>'; }).join('');
    var def = scope === 'global' || scope === 'project' ? 'decision' : 'nudge';
    var ph = scope === 'feature' ? 'Message ' + st.mainFeature + '…' : (scope === 'project' ? 'Project decision or broadcast…' : 'Global policy (permanent, all agents)…');
    return '<div class="bs-foot">' + scopes +
      '<div class="compose"><div class="compose-field">' +
        '<textarea data-ta="' + scope + '" rows="1" placeholder="' + ph + '"></textarea>' +
        '<div class="compose-bar"><select class="type-pick" data-typesel="' + scope + '">' + opts.replace('value="' + def + '"', 'value="' + def + '" selected') + '</select></div>' +
      '</div>' +
      '<button class="compose-send" data-send="' + scope + '" disabled>' + ico('send', 13) + 'Send</button></div></div>';
  }

  // ════ interactions ════
  function applyPreset(id) {
    var p = PRESETS[id]; if (!p) return;
    st.preset = id; st.sections = p.sections.slice(); st.direction = p.direction || 'row'; st.sizes = {};
    if (p.sidebarCollapse) st.sidebarCollapsed = true;
    if (p.sidebar === false) st.sidebarCollapsed = false;
    if (id === 'pipeline' || id === 'board') st.sidebarCollapsed = false;
    render();
  }
  function toggleSection(s) {
    var i = st.sections.indexOf(s);
    if (i > -1) st.sections.splice(i, 1); else st.sections.push(s);
    st.preset = 'custom'; st.sizes = {};
    render();
  }

  function bind() {
    // header tabs
    root.querySelectorAll('[data-tab]').forEach(function (b) { b.onclick = function () { toggleSection(b.dataset.tab); }; });
    root.querySelectorAll('[data-close]').forEach(function (b) { b.onclick = function () { toggleSection(b.dataset.close); }; });
    var addHint = root.querySelector('[data-addhint]');
    if (addHint) addHint.onclick = function () {
      var all = ['feature', 'project', 'global'];
      var missing = all.filter(function (s) { return st.sections.indexOf(s) < 0; })[0];
      if (missing) toggleSection(missing);
    };
    var dir = root.querySelector('[data-dir]');
    if (dir) dir.onclick = function () { st.direction = st.direction === 'row' ? 'column' : 'row'; st.sizes = {}; render(); };
    var exit = root.querySelector('[data-exit]'); if (exit) exit.onclick = function () { exit.style.opacity = 0.5; };

    // presets menu
    var pBtn = root.querySelector('[data-presets]'); var pMenu = root.querySelector('#presetMenu');
    if (pBtn) pBtn.onclick = function (e) { e.stopPropagation(); pMenu.toggleAttribute('data-open'); };
    document.addEventListener('click', function () { if (pMenu) pMenu.removeAttribute('data-open'); });
    root.querySelectorAll('[data-preset]').forEach(function (b) { b.onclick = function () { applyPreset(b.dataset.preset); }; });

    // sidebar
    var sbT = root.querySelector('[data-sbtoggle]'); if (sbT) sbT.onclick = function () { st.sidebarCollapsed = !st.sidebarCollapsed; render(); };
    root.querySelectorAll('[data-toggle]').forEach(function (b) { b.onclick = function () {
      st.openFeature = st.openFeature === b.dataset.toggle ? null : b.dataset.toggle; render(); }; });
    root.querySelectorAll('[data-feat]').forEach(function (b) { b.onclick = function () {
      st.mainFeature = b.dataset.feat; if (st.sections.indexOf('feature') < 0) st.sections.push('feature');
      st.sidebarCollapsed = false; st.openFeature = b.dataset.feat; render(); }; });
    root.querySelectorAll('[data-setmain]').forEach(function (b) { b.onclick = function (e) {
      e.stopPropagation(); st.mainFeature = b.dataset.setmain;
      if (st.sections.indexOf('feature') < 0) st.sections.push('feature'); render(); }; });
    root.querySelectorAll('[data-unblock]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); setStatus(b.dataset.unblock, 'running', 'BUILDING'); }; });
    root.querySelectorAll('[data-skip]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); setStatus(b.dataset.skip, 'running', 'TESTING'); }; });
    root.querySelectorAll('[data-pause]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); setStatus(b.dataset.pause, 'idle', null); }; });

    // answer question
    root.querySelectorAll('[data-answer]').forEach(function (b) { b.onclick = function () { answer(b.dataset.answer, b.dataset.opt); }; });
    // resolve warning/escalation
    root.querySelectorAll('[data-resolve]').forEach(function (b) { b.onclick = function () { resolve(b.dataset.resolve, b.dataset.mode); }; });
    // scope toggles
    root.querySelectorAll('[data-scope]').forEach(function (b) { b.onclick = function () {
      var f = features.filter(function (x) { return x.id === st.mainFeature; })[0];
      if (f) { f.scope[b.dataset.scope] = !f.scope[b.dataset.scope]; render(); } }; });

    // compose
    root.querySelectorAll('[data-ta]').forEach(function (ta) {
      var scope = ta.dataset.ta;
      var sendBtn = root.querySelector('[data-send="' + scope + '"]');
      ta.addEventListener('input', function () {
        ta.style.height = 'auto'; ta.style.height = Math.min(ta.scrollHeight, 96) + 'px';
        sendBtn.disabled = !ta.value.trim();
      });
      ta.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); if (ta.value.trim()) post(scope); }
      });
    });
    root.querySelectorAll('[data-send]').forEach(function (b) { b.onclick = function () { post(b.dataset.send); }; });

    bindResize();
  }

  function setStatus(fid, status, stage) {
    var f = features.filter(function (x) { return x.id === fid; })[0]; if (!f) return;
    f.status = status; if (stage) f.stage = stage;
    // clear an open warning when unblocked
    if (status === 'running') (boards[fid] || []).forEach(function (m) { if (m.type === 'warning' && m.status === 'open') { m.status = 'resolved'; m.resolution = 'unblocked → builder retry'; } });
    render();
  }

  function answer(mid, opt) {
    var arr = boards[st.mainFeature]; var m = find(arr, mid); if (!m || m.status === 'answered') return;
    m.status = 'answered'; m.answer = opt;
    var chosen = (m.options || []).filter(function (o) { return o.id === opt; })[0] || {};
    var ans = { id: nid(), type: 'answer', from: 'you', stage: m.stage, time: 'now', reply_to: mid,
      text: 'Use <code>' + chosen.label + '</code>. Keep it simple.' };
    arr.push(ans);
    // builder acks
    arr.push({ id: nid(), type: 'status', from: 'builder', stage: m.stage, time: 'now', ack: true,
      text: 'Got it — implementing <code>' + chosen.label + '</code>.' });
    st.flash = ans.id; render();
  }

  function resolve(mid, mode) {
    // find the message across feature boards
    var fid = st.mainFeature; var arr = boards[fid]; var m = find(arr, mid);
    if (!m) { Object.keys(boards).forEach(function (k) { var hit = find(boards[k], mid); if (hit) { m = hit; arr = boards[k]; fid = k; } }); }
    if (!m) return;
    m.status = 'resolved';
    if (mode === 'block') { m.resolution = 'blocked → RETRY (builder)'; setFeatStatus(fid, 'running', 'BUILDING'); }
    else if (mode === 'note') {
      m.resolution = 'noted as v2 → REVIEWING advances';
      boards[fid].push({ id: nid(), type: 'decision', from: 'you', stage: 'REVIEWING', time: 'now', pinned: true,
        text: 'Rename detection is v2 scope. Do not block.' });
      setFeatStatus(fid, 'running', 'TESTING');
    } else { m.resolution = 'ignored → REVIEWING advances'; setFeatStatus(fid, 'running', 'TESTING'); }
    st.flash = m.id; render();
  }
  function setFeatStatus(fid, status, stage) { var f = features.filter(function (x) { return x.id === fid; })[0]; if (f) { f.status = status; if (stage) f.stage = stage; } }

  function post(scope) {
    var ta = root.querySelector('[data-ta="' + scope + '"]'); var sel = root.querySelector('[data-typesel="' + scope + '"]');
    if (!ta || !ta.value.trim()) return;
    var type = sel.value;
    var key = scope === 'feature' ? st.mainFeature : scope;
    var m = { id: nid(), type: type, from: 'you', stage: scope === 'feature' ? curStage() : null, time: 'now',
      text: escapeHtml(ta.value.trim()), pinned: type === 'decision' };
    if (type === 'question') { m.status = 'pending'; m.options = [{ id: 'a', label: 'Option A' }, { id: 'b', label: 'Option B' }]; }
    boards[key] = boards[key] || []; boards[key].push(m);
    ta.value = ''; st.flash = m.id; render();
  }
  function curStage() { var f = features.filter(function (x) { return x.id === st.mainFeature; })[0]; return f ? f.stage : null; }

  function find(arr, id) { return (arr || []).filter(function (m) { return m.id === id; })[0]; }
  function escapeHtml(s) { return s.replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }

  // drag-resize between sections
  function bindResize() {
    root.querySelectorAll('[data-resize]').forEach(function (h) {
      h.onmousedown = function (e) {
        e.preventDefault();
        var idx = +h.dataset.resize; var prev = st.sections[idx - 1]; var next = st.sections[idx];
        var container = h.parentElement; var vertical = st.direction === 'column';
        var prevEl = h.previousElementSibling; var nextEl = h.nextElementSibling;
        var startPos = vertical ? e.clientY : e.clientX;
        var startPrev = vertical ? prevEl.offsetHeight : prevEl.offsetWidth;
        var startNext = vertical ? nextEl.offsetHeight : nextEl.offsetWidth;
        function move(ev) {
          var d = (vertical ? ev.clientY : ev.clientX) - startPos;
          var np = Math.max(220, startPrev + d), nn = Math.max(220, startNext - d);
          st.sizes[prev] = np; st.sizes[next] = nn;
          prevEl.style.flex = '0 0 ' + np + 'px'; nextEl.style.flex = '0 0 ' + nn + 'px';
        }
        function up() { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); document.body.style.cursor = ''; }
        document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
        document.body.style.cursor = vertical ? 'row-resize' : 'col-resize';
      };
    });
  }

  render();
})();
