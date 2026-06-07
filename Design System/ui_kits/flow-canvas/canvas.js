/* Pathly Studio — Flow Canvas kit logic (vanilla; static FSM graph). */
(function () {
  var ic = function (n, s) { return PathlyIcons.svg(n, { size: s || 14 }); };

  var NW = 160, NH = 52, CX = 250, LEFT = CX - NW / 2; // 170
  function accent(agent) {
    var a = agent.toLowerCase();
    if (a.indexOf('review') >= 0) return 'var(--purple)';
    if (a.indexOf('test') >= 0) return 'var(--yellow)';
    if (a.indexOf('retro') >= 0 || a.indexOf('done') >= 0) return 'var(--green)';
    return 'var(--blue)';
  }
  var NODES = [
    { id:'STORMING',  agent:'planner',  top:30,  start:true },
    { id:'PLANNING',  agent:'planner',  top:140 },
    { id:'BUILDING',  agent:'builder',  top:250 },
    { id:'REVIEWING', agent:'reviewer', top:360 },
    { id:'TESTING',   agent:'tester',   top:470 },
    { id:'DONE',      agent:'retro',    top:580 },
  ];
  var FWD = [[0,1,'storm_done'],[1,2,'plan_ready'],[2,3,'build_done'],[3,4,'pass'],[4,5,'green']];
  var BACK = [[3,2,'changes'],[4,2,'fail']];

  function nodeById(id){ return NODES.find(function(n){return n.id===id;}); }

  // ── render nodes ──
  function renderNodes() {
    var inner = document.getElementById('cv-inner');
    // remove existing nodes (keep svg)
    inner.querySelectorAll('.node').forEach(function(n){ n.remove(); });
    NODES.forEach(function (n, i) {
      var el = document.createElement('div');
      el.className = 'node';
      el.style.left = LEFT + 'px'; el.style.top = n.top + 'px';
      el.style.borderLeftColor = accent(n.agent);
      el.setAttribute('data-i', i);
      el.innerHTML =
        (n.start ? '<span class="start">' + ic('play', 8) + '</span>' : '') +
        '<span class="handle h-top"></span><span class="handle h-bot"></span><span class="handle h-right"></span>' +
        '<div class="nstate">' + n.id + '</div><div class="nagent">' + n.agent + '</div>';
      el.onclick = function () { selectNode(i); };
      inner.appendChild(el);
    });
    PathlyIcons.inject(inner);
  }

  // ── render edges ──
  function renderEdges() {
    var svg = document.getElementById('cv-edges');
    var blue = getComputedStyle(document.documentElement).getPropertyValue('--blue').trim() || '#60A5FA';
    var orange = getComputedStyle(document.documentElement).getPropertyValue('--orange').trim() || '#f97316';
    var defs = '<defs>' +
      '<marker id="ah-blue" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="' + blue + '"/></marker>' +
      '<marker id="ah-orange" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="' + orange + '"/></marker>' +
      '</defs>';
    var paths = '';
    FWD.forEach(function (e) {
      var a = NODES[e[0]], b = NODES[e[1]];
      var y1 = a.top + NH, y2 = b.top;
      paths += '<line x1="' + CX + '" y1="' + y1 + '" x2="' + CX + '" y2="' + (y2 - 7) + '" stroke="' + blue + '" stroke-width="2" marker-end="url(#ah-blue)"/>';
      paths += '<text x="' + (CX + 8) + '" y="' + ((y1 + y2) / 2 + 4) + '" fill="var(--text-muted)" font-family="var(--font-family-mono)" font-size="10">' + e[2] + '</text>';
    });
    BACK.forEach(function (e, k) {
      var a = NODES[e[0]], b = NODES[e[1]];
      var x = LEFT + NW; // right edge 460
      var y1 = a.top + NH / 2, y2 = b.top + NH / 2;
      var bow = 70 + k * 26;
      paths += '<path d="M' + x + ',' + y1 + ' C' + (x + bow) + ',' + y1 + ' ' + (x + bow) + ',' + y2 + ' ' + (x + 7) + ',' + y2 + '" fill="none" stroke="' + orange + '" stroke-width="2" stroke-dasharray="4 3" marker-end="url(#ah-orange)"/>';
      paths += '<text x="' + (x + bow + 6) + '" y="' + ((y1 + y2) / 2) + '" fill="' + orange + '" font-family="var(--font-family-mono)" font-size="10">↩ ' + e[2] + '</text>';
    });
    svg.innerHTML = defs + paths;
  }

  // ── inspector ──
  var AGENTS = ['planner','builder','reviewer','tester','retro'];
  function transitionsFor(i) {
    var outs = [];
    FWD.forEach(function (e) { if (e[0] === i) outs.push({ to: NODES[e[1]].id, cond: e[2], back: false }); });
    BACK.forEach(function (e) { if (e[0] === i) outs.push({ to: NODES[e[1]].id, cond: e[2], back: true }); });
    return outs;
  }
  function selectNode(i) {
    document.querySelectorAll('.node').forEach(function (n) { n.removeAttribute('data-active'); });
    document.querySelector('.node[data-i="' + i + '"]').setAttribute('data-active', '');
    var n = NODES[i];
    var trans = transitionsFor(i).map(function (t) {
      return '<div class="ins-tran' + (t.back ? ' back' : '') + '">' + ic(t.back ? 'rotate-ccw' : 'chevron-right', 13) +
        '<span class="to">' + t.to + '</span><span class="cond">on ' + t.cond + '</span></div>';
    }).join('') || '<div class="ins-tran"><span class="to" style="color:var(--text-muted)">terminal state</span></div>';
    var agentOpts = AGENTS.map(function (a) { return '<option' + (a === n.agent ? ' selected' : '') + '>' + a + '</option>'; }).join('');
    var ins = document.getElementById('cv-inspect');
    ins.className = 'cv-inspect';
    ins.innerHTML =
      '<p class="ins-title">State</p><div class="ins-state">' + n.id + '</div>' +
      '<div class="ins-field"><span class="fl">Agent</span><select class="ins-select">' + agentOpts + '</select></div>' +
      '<div class="ins-field"><span class="fl">Transitions</span><div class="ins-trans">' + trans + '</div></div>' +
      '<div class="ins-field"><span class="fl">Gate</span><div class="ins-tran"><span class="to" style="font-family:var(--font-family-mono);font-size:var(--font-size-sm)">' +
        (n.id === 'BUILDING' ? 'lint:strict · types:strict' : n.id === 'TESTING' ? 'suite:green' : 'none') + '</span></div></div>';
    PathlyIcons.inject(ins);
  }

  // ── views ──
  document.getElementById('cv-views').innerHTML =
    '<button class="seg-tab" data-view="visual" data-active>' + ic('layout-grid', 13) + 'Visual</button>' +
    '<button class="seg-tab" data-view="yaml">' + ic('list', 13) + 'YAML</button>';
  document.getElementById('cv-valid').innerHTML = ic('circle-check', 13) + 'Valid · 6 states';
  document.getElementById('cv-export').innerHTML = ic('download', 13) + 'Export ▾';
  document.getElementById('cv-layout').innerHTML = ic('shuffle', 13) + 'Auto-layout';

  function yamlHTML() {
    var lines = ['<span class="yk">flow</span>: <span class="yv">team-build</span>',
      '<span class="yk">start</span>: <span class="yv">STORMING</span>',
      '<span class="yk">states</span>:'];
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
    b.onclick = function () { setView(b.getAttribute('data-view')); };
  });

  renderNodes();
  renderEdges();
  selectNode(2); // BUILDING selected by default
  PathlyIcons.inject(document);
})();
