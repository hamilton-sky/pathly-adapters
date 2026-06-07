/* Pathly Studio — Skill Notebook kit logic (vanilla; static demo).
   Reads ?skill=<name> (from the Monitor "Open in Notebook" action). */
(function () {
  var ic = function (n, s) { return PathlyIcons.svg(n, { size: s || 14 }); };
  function vp(t){ return t.replace(/\{([^}]+)\}/g, '<span class="var-pill">$1</span>'); }

  var SKILLS = {
    'fix/build': {
      crumbs: ['Skills','fix','build'],
      cells: [
        { type:'body', title:'fix/build', lines:[
          'FIXING stage for the {quick-fix} flow. Fast, focused, minimal — one targeted change.',
          'Invoked by the {team} orchestrator when the FSM state is {BUILDING}.' ] },
        { type:'fragment', title:'Role', full:true, lines:[
          'Stage orchestrator: Quick Fix.',
          'Apply a {single}, well-scoped change. No multi-conversation planning, no PROGRESS.md churn.' ] },
        { type:'fragment', title:'Procedure', lines:[
          'Read the issue description · locate the code · apply the minimal change · verify it passes.' ] },
      ],
      composed: [
        ['h1','fix/build'],
        ['p','FIXING stage for the quick-fix flow. Fast, focused, minimal — one targeted change.'],
        ['p','Invoked by the <code>team</code> orchestrator when the FSM state is <code>BUILDING</code>.'],
        ['h2','Role'],
        ['p','Stage orchestrator: Quick Fix. Apply a single, well-scoped change.'],
        ['ul',['Read the issue description','Locate the code','Apply the minimal change','Verify it passes']],
        ['h2','Gate'],
        ['p','<code>lint:strict</code>, <code>types:strict</code> must pass before REVIEWING.'],
      ],
      count: 6,
    },
    'review/quality': {
      crumbs: ['Skills','review','quality'],
      cells: [
        { type:'body', title:'review/quality', lines:[
          'REVIEWING stage. Critique the diff against the plan and the quality bar.',
          'Invoked when the FSM state is {REVIEWING}.' ] },
        { type:'fragment', title:'Role', full:true, lines:[
          'Stage orchestrator: Reviewer.',
          'Annotate findings and either {PASS} to TESTING or {REROUTE} back to BUILDING.' ] },
      ],
      composed: [
        ['h1','review/quality'],
        ['p','REVIEWING stage. Critique the diff against the plan and the quality bar.'],
        ['h2','Role'],
        ['p','Stage orchestrator: Reviewer.'],
        ['ul',['Diff against PLAN.md','Run quality gates','Annotate findings','PASS or REROUTE → BUILDING']],
        ['h2','Gate'],
        ['p','No blocking findings before <code>TESTING</code>.'],
      ],
      count: 5,
    },
    'team/build': {
      crumbs: ['Skills','team','build'],
      cells: [
        { type:'body', title:'team/build', lines:[
          'BUILDING stage for the {full} flow. Coordinate builder conversations across the plan.',
          'Invoked by the {team} orchestrator when the FSM state is {BUILDING}.' ] },
        { type:'fragment', title:'Role', full:true, lines:[
          'Team orchestrator: Full Build.',
          'Split work, track {PROGRESS.md}, hand off to review.' ] },
      ],
      composed: [
        ['h1','team/build'],
        ['p','BUILDING stage for the full flow. Coordinate builder conversations across the plan.'],
        ['h2','Role'],
        ['p','Team orchestrator: Full Build.'],
        ['ul',['Load the plan & conversation queue','Spawn builder per conversation','Reconcile diffs','Update PROGRESS.md']],
        ['h2','Gate'],
        ['p','All conversations <code>DONE</code> before REVIEWING.'],
      ],
      count: 5,
    },
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
    var badge = cell.type === 'fragment'
      ? '<span class="cell-badge frag">fragment</span>'
      : '<span class="cell-badge body">body</span>';
    var actions = ['chevron-up','chevron-down','pencil','trash-2','more-horizontal'].map(function (a) {
      return '<button title="' + a + '">' + ic(a, 14) + '</button>';
    }).join('');
    var body = cell.lines.map(function (l) { return '<p>' + vp(l) + '</p>'; }).join('');
    var showFull = cell.full ? '<span class="show-full">Show full content</span>' : '';
    return '<div class="cell ' + cell.type + '" data-i="' + i + '">' +
      '<div class="cell-head"><span class="cell-title">' + cell.title + '</span>' + badge +
        '<div class="cell-actions">' + actions + '</div></div>' +
      '<div class="cell-body">' + body + showFull + '</div></div>';
  }
  function insertHTML() { return '<div class="insert"><span class="plus">' + ic('plus', 13) + '</span></div>'; }

  var cellsHTML = '';
  skill.cells.forEach(function (c, i) { cellsHTML += insertHTML() + cellHTML(c, i); });
  cellsHTML += insertHTML();
  document.getElementById('nb-cells').innerHTML = cellsHTML;

  document.querySelectorAll('.cell').forEach(function (el) {
    el.onclick = function () {
      document.querySelectorAll('.cell').forEach(function (c) { c.removeAttribute('data-active'); });
      el.setAttribute('data-active', '');
    };
  });

  // preview
  document.getElementById('nb-preview-head').textContent = 'Composed skill · ' + skill.count + ' cells';
  document.getElementById('nb-preview-body').innerHTML = skill.composed.map(function (b) {
    if (b[0] === 'ul') return '<ul>' + b[1].map(function (li) { return '<li>' + li + '</li>'; }).join('') + '</ul>';
    return '<' + b[0] + '>' + b[1] + '</' + b[0] + '>';
  }).join('');

  PathlyIcons.inject(document);
})();
