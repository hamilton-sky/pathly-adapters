/* Pathly Studio — Monitor kit logic (vanilla; static demo).
   Clicking a pipeline phase opens a config modal: prompt preview,
   CLI host, agent + skill selectors, and "open in notebook". */
(function () {
  var ic = function (n, s) { return PathlyIcons.svg(n, { size: s || 14 }); };

  var STATE = {
    STORMING:'var(--text-muted)', PLANNING:'var(--state-planning)', BUILDING:'var(--state-building)',
    REVIEWING:'var(--state-reviewing)', TESTING:'var(--state-testing)', DONE:'var(--state-done)',
  };
  function pill(state){ var c=STATE[state]||'var(--text-muted)';
    return '<span class="pill" style="color:'+c+';background:color-mix(in srgb,'+c+' 13%,transparent);border-color:color-mix(in srgb,'+c+' 38%,transparent)"><span class="pdot" style="background:'+c+'"></span>'+state+'</span>'; }

  // ── pipeline definition ──
  var PIPELINE = [
    { state:'STORMING',  agent:'planner',  skill:'plan/storm' },
    { state:'PLANNING',  agent:'planner',  skill:'plan/scope' },
    { state:'BUILDING',  agent:'builder',  skill:'fix/build' },
    { state:'REVIEWING', agent:'reviewer', skill:'review/quality' },
    { state:'TESTING',   agent:'tester',   skill:'test/verify' },
    { state:'DONE',      agent:'retro',    skill:'retro/archive' },
  ];
  var ACTIVE = 2; // BUILDING

  var HOSTS = [
    { id:'claude',  label:'Claude Code', dot:'var(--orange)' },
    { id:'codex',   label:'Codex',       dot:'var(--green)' },
    { id:'copilot', label:'Copilot',     dot:'var(--blue)' },
  ];
  var AGENTS = ['planner','builder','reviewer','tester','retro'];
  var SKILLS = ['plan/storm','plan/scope','fix/build','team/build','review/quality','test/verify','retro/archive'];

  var SKILL_PROMPTS = {
    'fix/build': { role:'Stage orchestrator — Quick Fix.',
      body:'Apply a single, well-scoped change. No multi-conversation\nplanning, no PROGRESS.md churn.',
      steps:['Read the issue description in plans/auth-refactor/','Locate the code','Apply the minimal change','Verify it passes'],
      gate:'lint:strict, types:strict must pass before REVIEWING.' },
    'team/build': { role:'Team orchestrator — Full Build.',
      body:'Coordinate builder conversations across the feature plan.\nSplit work, track PROGRESS.md, hand off to review.',
      steps:['Load the plan & conversation queue','Spawn builder per conversation','Reconcile diffs','Update PROGRESS.md'],
      gate:'All conversations DONE before REVIEWING.' },
    'plan/scope': { role:'Stage orchestrator — Planning.',
      body:'Decompose the feature into a conversation plan.\nProduce plans/<feature>/PLAN.md.',
      steps:['Read the feature brief','Draft conversation list','Define gates per stage','Write PLAN.md'],
      gate:'PLAN.md present before BUILDING.' },
    'plan/storm': { role:'Stage orchestrator — Storming.',
      body:'Explore the problem space and surface unknowns before\ncommitting to a plan.',
      steps:['Survey the codebase','List open questions','Propose 2–3 approaches'],
      gate:'Approach chosen before PLANNING.' },
    'review/quality': { role:'Stage orchestrator — Review.',
      body:'Critique the diff against the plan and quality bar.\nRequest changes or pass to TESTING.',
      steps:['Diff against PLAN.md','Run quality gates','Annotate findings','PASS or REROUTE → BUILDING'],
      gate:'No blocking findings before TESTING.' },
    'test/verify': { role:'Stage orchestrator — Test.',
      body:'Run and extend the verification suite for the change.',
      steps:['Run the test suite','Add coverage for the change','Report results'],
      gate:'Green suite before DONE.' },
    'retro/archive': { role:'Stage orchestrator — Retro.',
      body:'Summarise the run, capture lessons, archive artifacts.',
      steps:['Write the retro note','Capture lessons/','Archive the plan'],
      gate:'—' },
  };

  // ── stepper ──
  function renderStepper() {
    document.getElementById('conv-label').innerHTML = 'conv <b>2</b> · <b>2</b> done · <b>3</b> remaining';
    var html = '';
    PIPELINE.forEach(function (st, idx) {
      var status = idx < ACTIVE ? 'done' : idx === ACTIVE ? 'active' : 'pending';
      var inner = status === 'done' ? ic('check', 14) : '<span class="inner"></span>';
      html += '<div class="step">' +
        '<div class="dotcol" data-i="' + idx + '">' +
          '<div class="fsmdot ' + status + '">' + inner + '</div>' +
          '<span class="steplabel ' + status + '">' + st.state + '</span>' +
          '<span class="agenttag">' + st.agent + '</span>' +
        '</div>' +
        (idx < PIPELINE.length - 1 ? '<div class="connector ' + (idx < ACTIVE ? 'done' : '') + '"></div>' : '') +
      '</div>';
    });
    document.getElementById('stepper').innerHTML = html;
    document.querySelectorAll('.dotcol').forEach(function (el) {
      el.onclick = function () { openPhase(+el.getAttribute('data-i')); };
    });
  }

  // ── metrics ──
  document.getElementById('head-pill').innerHTML = pill('BUILDING');
  var METRICS = [['142.3k','Tokens'],['6m 44s','Wall'],['$1.97','Cost','cost'],['23','Events']];
  document.getElementById('metrics').innerHTML = METRICS.map(function (m) {
    return '<div class="mtile"><span class="mval ' + (m[2]||'') + '">' + m[0] + '</span><span class="mlabel">' + m[1] + '</span></div>';
  }).join('');

  // ── view tabs ──
  document.getElementById('vtabs').innerHTML =
    '<button class="vtab" data-active>Events</button><button class="vtab">Output</button>';

  // ── event log ──
  function L(c, t){ return '<div class="evline ev-' + c + '">' + t + '</div>'; }
  function pad(s,n){ s=String(s); while(s.length<n) s+=' '; return s; }
  var EVENTS = [
    ['accent','09:02:11  '+pad('TRANSITION',14)+'  IDLE → STORMING'],
    ['phase','09:02:40  '+pad('PHASE',14)+'  planner #1  storm ▸'],
    ['blue','09:04:12  '+pad('AGENT_DONE',14)+'  planner #1  DONE  9 tools  88s  12.4k↑3.1k↓  $0.34'],
    ['accent','09:05:01  '+pad('TRANSITION',14)+'  STORMING → PLANNING'],
    ['phase','09:05:20  '+pad('PHASE',14)+'  planner #1  scope ▸'],
    ['green','09:08:33  '+pad('AGENT_DONE',14)+'  planner #1  PASS  14 tools  121s  16.0k↑4.2k↓  $0.41'],
    ['accent','09:08:40  '+pad('TRANSITION',14)+'  PLANNING → BUILDING'],
    ['purple','09:09:01  '+pad('AGENT_SPAWNED',14)+'  builder #1'],
    ['yellow','09:11:20  '+pad('FILE_CREATED',14)+'  src/auth/session.ts'],
    ['muted','09:12:05  '+pad('·',14)+'  implement'],
    ['green','09:18:30  '+pad('AGENT_DONE',14)+'  builder #1  PASS  31 tools  214s  18.2k↑6.4k↓  $0.71'],
    ['accent','09:21:06  '+pad('TRANSITION',14)+'  BUILDING → REVIEWING'],
    ['red','09:24:18  '+pad('GATE_FAILED',14)+'  lint:strict → BUILDING'],
    ['retro','09:24:19  '+pad('TRANSITION',14)+'  ↩ REVIEWING → BUILDING'],
    ['purple','09:24:40  '+pad('AGENT_SPAWNED',14)+'  builder #2'],
    ['yellow','09:27:11  '+pad('FILE_CREATED',14)+'  src/auth/guards.ts'],
    ['blue','09:33:50  '+pad('AGENT_DONE',14)+'  builder #2  DONE  22 tools  168s  14.8k↑5.1k↓  $0.62'],
  ];
  document.getElementById('evlog').innerHTML = EVENTS.map(function (e) { return L(e[0], e[1]); }).join('');
  var lg = document.getElementById('evlog'); lg.scrollTop = lg.scrollHeight;

  // ── phase config modal ──
  var sel = { host:'claude', agent:'builder', skill:'fix/build', stage:'BUILDING' };

  function promptHTML() {
    var p = SKILL_PROMPTS[sel.skill] || { role:'—', body:'', steps:[], gate:'—' };
    var host = HOSTS.find(function(h){return h.id===sel.host;});
    var out = '';
    out += '<span class="ph-h"># ' + sel.skill + '</span>  <span class="ph-c">· ' + sel.stage + ' stage</span>\n';
    out += '<span class="ph-c">Host:</span> ' + host.label + '   <span class="ph-c">Agent:</span> ' + sel.agent + '   <span class="ph-c">Conversation #2</span>\n\n';
    out += '<span class="ph-k">Role:</span> ' + p.role + '\n' + p.body + '\n\n';
    out += p.steps.map(function (s) { return '  • ' + s; }).join('\n') + '\n\n';
    out += '<span class="ph-k">Gate:</span> ' + p.gate;
    return out;
  }

  function renderModal() {
    var hostSeg = HOSTS.map(function (host) {
      return '<button class="segbtn" data-host="' + host.id + '" ' + (sel.host === host.id ? 'data-active' : '') + '>' +
        '<span class="host-dot" style="background:' + host.dot + '"></span>' + host.label + '</button>';
    }).join('');
    var agentChips = AGENTS.map(function (a) {
      return '<button class="chip" data-agent="' + a + '" ' + (sel.agent === a ? 'data-active' : '') + '>' + a + '</button>';
    }).join('');
    var skillChips = SKILLS.map(function (s) {
      return '<button class="chip" data-skill="' + s + '" ' + (sel.skill === s ? 'data-active' : '') + '>' + s + '</button>';
    }).join('');

    document.getElementById('pmodal').innerHTML =
      '<div class="pm-head">' + ic('square-terminal', 16) +
        '<span class="pm-title">Configure phase<span class="sub">— what runs when the pipeline enters this stage</span></span>' +
        '<span style="margin-left:auto">' + pill(sel.stage) + '</span>' +
        '<button class="btn-b" id="pm-x" style="padding:6px;border:none;background:transparent">' + ic('x', 16) + '</button>' +
      '</div>' +
      '<div class="pm-body">' +
        '<div class="fieldrow"><span class="flabel">CLI host</span><div class="seg">' + hostSeg + '</div></div>' +
        '<div class="fieldrow"><span class="flabel">Agent</span><div class="chips">' + agentChips + '</div></div>' +
        '<div class="fieldrow"><span class="flabel">Skill</span><div class="chips">' + skillChips + '</div></div>' +
        '<div class="fieldrow"><span class="flabel">Prompt preview</span><div class="prompt-box">' + promptHTML() + '</div></div>' +
      '</div>' +
      '<div class="pm-foot">' +
        '<button class="btn-b" id="pm-notebook">' + ic('book-open', 14) + 'Open skill in Notebook</button>' +
        '<span class="spacer"></span>' +
        '<button class="btn-b" id="pm-cancel">Cancel</button>' +
        '<button class="btn-cta" id="pm-apply">' + ic('check', 14) + 'Apply</button>' +
      '</div>';

    document.querySelectorAll('[data-host]').forEach(function (b) { b.onclick = function () { sel.host = b.getAttribute('data-host'); renderModal(); }; });
    document.querySelectorAll('[data-agent]').forEach(function (b) { b.onclick = function () { sel.agent = b.getAttribute('data-agent'); renderModal(); }; });
    document.querySelectorAll('[data-skill]').forEach(function (b) { b.onclick = function () { sel.skill = b.getAttribute('data-skill'); renderModal(); }; });
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
    sel = { host: sel.host, agent: st.agent, skill: st.skill, stage: st.state };
    renderModal();
    document.getElementById('overlay').setAttribute('data-open', '');
  }
  function closePhase() { document.getElementById('overlay').removeAttribute('data-open'); }
  document.getElementById('overlay').onclick = function (e) { if (e.target === this) closePhase(); };

  renderStepper();
  PathlyIcons.inject(document);
})();
