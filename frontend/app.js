/* LANTERN evidence view.
 *
 * Renders frontend/data/export.json. No dependencies, no network access, no
 * build step. The page is a projection of the export: it adds no numbers of
 * its own, so whatever the runner could not establish stays unestablished
 * here. Where a value is unknown the page says "unknown" rather than 0.
 */

'use strict';

/* Every top-level export field this page reads. tools/check_app.py
 * cross-checks this list against a generated export so a renamed field fails
 * the lane instead of silently rendering an empty pane. */
const FIELDS = [
  'schema_version',
  'label',
  'lane',
  'generated_utc',
  'oracle_conformance',
  'synthetic_records',
  'all_records_synthetic',
  'cases',
  'attempts',
  'analysis',
  'boundaries'
];

const EFFECT_TEXT = {
  measured: ['Framing effect measured', 'At least one framing-only pair changed its recommendation.'],
  none_measured: ['No framing effect measured', 'Every readable framing-only pair agreed with its baseline. This is a reportable result, not a missing one.'],
  insufficient: ['Insufficient readable pairs', 'No pair had a readable decision on both sides, so these records support no statement about framing either way.']
};

const OUTCOME_CLASS = {
  decision: 'decision',
  timeout: 'timeout',
  malformed: 'decision-no',
  truncated: 'decision-no',
  refusal: 'decision-no',
  invalid_choice: 'decision-no',
  error: 'decision-no'
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function badge(value, className) {
  return el('span', 'badge ' + (className || 'neutral'), value);
}

/* Unknown must never render as a plausible value. */
function show(value) {
  if (value === null || value === undefined || value === '') return 'unknown';
  return String(value);
}

function table(target, columns, rows, options) {
  const settings = options || {};
  const node = document.getElementById(target);
  node.replaceChildren();
  if (settings.caption) {
    node.appendChild(el('caption', null, settings.caption));
  }
  const head = el('thead');
  const headRow = el('tr');
  columns.forEach(function (column) {
    const th = el('th', column.wrap ? 'wrap' : null, column.label);
    headRow.appendChild(th);
  });
  head.appendChild(headRow);
  node.appendChild(head);

  const body = el('tbody');
  if (!rows.length) {
    const empty = el('tr');
    const cell = el('td', 'wrap', settings.empty || 'No rows.');
    cell.colSpan = columns.length;
    empty.appendChild(cell);
    body.appendChild(empty);
  }
  rows.forEach(function (row, index) {
    const tr = el('tr');
    if (settings.onSelect) {
      tr.className = 'selectable';
      tr.tabIndex = 0;
      const choose = function () {
        Array.prototype.forEach.call(body.children, function (other) {
          other.classList.remove('selected');
        });
        tr.classList.add('selected');
        settings.onSelect(row, index);
      };
      tr.addEventListener('click', choose);
      tr.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          choose();
        }
      });
    }
    columns.forEach(function (column) {
      const value = column.render(row, index);
      const td = el('td', [column.wrap ? 'wrap' : '', column.numeric ? 'num' : ''].join(' ').trim() || null);
      if (value instanceof Node) {
        td.appendChild(value);
      } else {
        td.textContent = show(value);
      }
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
  node.appendChild(body);
}

function renderMasthead(data) {
  const chip = document.getElementById('label-chip');
  chip.textContent = data.label;
  document.getElementById('meta-lane').textContent = data.lane;
  document.getElementById('meta-generated').textContent = data.generated_utc;
  document.getElementById('meta-conformance').textContent = data.oracle_conformance;
  document.getElementById('meta-schema').textContent =
    'v' + data.schema_version + ' (proposed)';
}

function renderComparison(data) {
  const analysis = data.analysis;
  const counts = analysis.framing_counts;
  const copy = EFFECT_TEXT[analysis.effect] || ['Unrecognised effect value', analysis.effect];
  const banner = document.getElementById('effect-banner');
  banner.className = 'verdict-banner ' + analysis.effect;
  banner.replaceChildren(el('strong', null, copy[0]), el('span', null, copy[1]));

  const covered = analysis.coverage.filter(function (row) { return row.covered; }).length;
  const tiles = [
    ['Attempts recorded', analysis.attempts, 'all arms, failures included'],
    ['Framing pairs', counts.pairs, 'baseline vs framing'],
    ['Flips', counts.flip, 'of ' + counts.pairs + ' pairs'],
    ['Stable', counts.stable, 'of ' + counts.pairs + ' pairs'],
    ['Unresolved pairs', counts.unresolved, 'no readable decision'],
    ['Runs fully covered', covered, 'of ' + analysis.coverage.length + ' runs']
  ];
  const host = document.getElementById('comparison-tiles');
  host.replaceChildren();
  tiles.forEach(function (row) {
    const tile = el('div', 'tile');
    tile.appendChild(el('div', 'name', row[0]));
    tile.appendChild(el('div', 'value', row[1]));
    tile.appendChild(el('div', 'denominator', row[2]));
    host.appendChild(tile);
  });

  const pairColumns = [
    { label: 'Case', render: function (r) { return r.case_id; } },
    { label: 'Baseline choice', render: function (r) { return r.baseline_option; } },
    { label: 'Contrast choice', render: function (r) { return r.contrast_option; } },
    { label: 'Verdict', render: function (r) { return badge(r.verdict, r.verdict); } },
    { label: 'Reason', wrap: true, render: function (r) { return r.reason; } }
  ];
  table('framing-table', pairColumns, analysis.framing_pairs, {
    empty: 'No framing-only pair could be formed from these records.'
  });
  table('correction-table', pairColumns, analysis.correction_pairs, {
    empty: 'No correction-arm attempt was recorded.'
  });

  const excluded = document.getElementById('excluded-block');
  excluded.replaceChildren();
  if (analysis.excluded.length) {
    excluded.appendChild(el('h3', null, 'Excluded from the framing-only comparison'));
    const list = el('ul', 'rubric');
    analysis.excluded.forEach(function (row) {
      list.appendChild(el('li', null, row.condition_id + ' — ' + row.reason));
    });
    excluded.appendChild(list);
  }

  const notesHost = el('div');
  notesHost.appendChild(el('h3', null, 'How these numbers are counted'));
  const notes = el('ul', 'rubric');
  analysis.notes.forEach(function (note) { notes.appendChild(el('li', null, note)); });
  notesHost.appendChild(notes);
  excluded.appendChild(notesHost);

  const armColumns = [
    { label: 'Arm', render: function (r) { return r.arm; } },
    { label: 'Attempts', numeric: true, render: function (r) { return r.attempts; } },
    { label: 'Readable decisions', numeric: true, render: function (r) { return r.decisions; } },
    { label: 'Unresolved', numeric: true, render: function (r) { return r.unresolved; } },
    { label: 'Failures', numeric: true, render: function (r) { return r.failure_total; } },
    { label: 'Failure kinds', wrap: true, render: function (r) {
        const kinds = Object.keys(r.failures);
        return kinds.length ? kinds.map(function (k) { return k + ': ' + r.failures[k]; }).join(', ') : 'none';
      } }
  ];
  const armsHost = el('div');
  armsHost.appendChild(el('h3', null, 'Per-arm counts'));
  const armTable = el('table');
  armTable.id = 'arms-table';
  const scroll = el('div', 'table-scroll');
  scroll.appendChild(armTable);
  armsHost.appendChild(scroll);
  excluded.appendChild(armsHost);
  table('arms-table', armColumns, analysis.arms, {});

  const coverageColumns = [
    { label: 'Run', render: function (r) { return r.run_id; } },
    { label: 'Registered', numeric: true, render: function (r) { return r.registered; } },
    { label: 'Definitive', numeric: true, render: function (r) { return r.definitive; } },
    { label: 'Coverage', render: function (r) {
        return badge(r.covered ? 'covered' : 'incomplete', r.covered ? 'stable' : 'unresolved');
      } },
    { label: 'Pending attempts', wrap: true, render: function (r) {
        return r.pending.length ? r.pending.join(', ') : 'none';
      } }
  ];
  const coverageHost = el('div');
  coverageHost.appendChild(el('h3', null, 'Coverage — not task success'));
  coverageHost.appendChild(el('p', 'pane-note',
    'Coverage asks whether every registered attempt reached a definitive outcome. A fully recorded failure is covered; an empty run is vacuously covered.'));
  const coverageTable = el('table');
  coverageTable.id = 'coverage-table';
  const coverageScroll = el('div', 'table-scroll');
  coverageScroll.appendChild(coverageTable);
  coverageHost.appendChild(coverageScroll);
  excluded.appendChild(coverageHost);
  table('coverage-table', coverageColumns, analysis.coverage, {});
}

function renderCases(data) {
  const host = document.getElementById('cases');
  host.replaceChildren();
  data.cases.forEach(function (item) {
    const card = el('div', 'case');
    const head = el('div', 'case-head');
    head.appendChild(el('div', 'q', item.question));
    head.appendChild(el('div', 'case-status', item.id + ' · ' + item.status));
    card.appendChild(head);

    const body = el('div', 'case-body');
    body.appendChild(el('h3', null, 'Rubric: ' + item.rubric.id));
    const rubric = el('ul', 'rubric');
    item.rubric.requirements.forEach(function (line) {
      rubric.appendChild(el('li', null, line));
    });
    body.appendChild(rubric);

    body.appendChild(el('h3', null,
      'Evidence — ' + item.relevant_count + ' declared relevant, ' +
      item.irrelevant_count + ' declared irrelevant'));
    const evidenceTable = el('table');
    evidenceTable.id = 'evidence-' + item.id;
    const evidenceScroll = el('div', 'table-scroll');
    evidenceScroll.appendChild(evidenceTable);
    body.appendChild(evidenceScroll);

    body.appendChild(el('h3', null, 'Condition matrix'));
    const conditionTable = el('table');
    conditionTable.id = 'conditions-' + item.id;
    const conditionScroll = el('div', 'table-scroll');
    conditionScroll.appendChild(conditionTable);
    body.appendChild(conditionScroll);
    card.appendChild(body);
    host.appendChild(card);

    table('evidence-' + item.id, [
      { label: 'Relevance', render: function (r) {
          return badge(r.relevant ? 'relevant' : 'irrelevant', r.relevant ? 'stable' : 'neutral');
        } },
      { label: 'Claim', wrap: true, render: function (r) { return r.claim; } },
      { label: 'Source', wrap: true, render: function (r) { return r.source; } },
      { label: 'Authority', wrap: true, render: function (r) { return r.source_authority; } }
    ], item.evidence, { caption: 'Relevance is declared in advance; source authority is preserved, not stripped.' });

    table('conditions-' + item.id, [
      { label: 'Condition', render: function (r) { return r.id; } },
      { label: 'Arm', render: function (r) { return r.arm; } },
      { label: 'Changes evidence', render: function (r) {
          return el('span', 'flag' + (r.changes_evidence ? ' on' : ''), r.changes_evidence ? 'yes' : 'no');
        } },
      { label: 'Framing-only eligible', render: function (r) {
          return el('span', 'flag' + (r.framing_only_eligible ? '' : ' on'), r.framing_only_eligible ? 'yes' : 'no');
        } },
      { label: 'Confound reason', wrap: true, render: function (r) {
          return r.confounded ? r.confound_reason : '—';
        } }
    ], item.conditions, { empty: 'No conditions expanded for this case.' });
  });
}

function renderAttempts(data) {
  const legend = document.getElementById('outcome-legend');
  legend.replaceChildren();
  const seen = {};
  data.attempts.forEach(function (row) { seen[row.outcome] = (seen[row.outcome] || 0) + 1; });
  Object.keys(seen).sort().forEach(function (kind) {
    legend.appendChild(badge(kind + ' × ' + seen[kind], OUTCOME_CLASS[kind] || 'neutral'));
  });

  table('attempts-table', [
    { label: 'Attempt', render: function (r) { return r.attempt_id; } },
    { label: 'Arm', render: function (r) { return r.arm; } },
    { label: 'Outcome', render: function (r) {
        return badge(r.outcome, OUTCOME_CLASS[r.outcome] || 'neutral');
      } },
    { label: 'Choice', render: function (r) { return r.option_id; } },
    { label: 'Correctness', render: function (r) { return r.correctness; } },
    { label: 'Site', render: function (r) { return r.provenance ? r.provenance.execution_site : null; } },
    { label: 'Unmeasured', numeric: true, render: function (r) { return r.unknown.length; } }
  ], data.attempts, {
    empty: 'No attempts recorded.',
    onSelect: renderDetail
  });
}

function renderDetail(record) {
  const host = document.getElementById('attempt-detail');
  host.className = 'detail';
  host.replaceChildren();

  const head = el('div', 'detail-head',
    record.attempt_id + ' · ' + record.condition_id + ' · outcome ' + record.outcome);
  host.appendChild(head);

  const body = el('div', 'detail-body');

  const raw = el('div');
  raw.appendChild(el('h4', null, 'Raw output, retained verbatim'));
  raw.appendChild(el('pre', null, show(record.raw_output)));
  raw.appendChild(el('h4', null, 'Received explanation'));
  raw.appendChild(el('pre', null, show(record.received_explanation)));
  body.appendChild(raw);

  const signal = el('div');
  signal.appendChild(el('h4', null, 'Parse signal'));
  const signalList = el('dl', 'kv');
  Object.keys(record.parse_signal).sort().forEach(function (key) {
    signalList.appendChild(el('dt', null, key));
    signalList.appendChild(el('dd', null, record.parse_signal[key]));
  });
  signal.appendChild(signalList);

  signal.appendChild(el('h4', null, 'Source mentions'));
  if (!record.mentions.length) {
    signal.appendChild(el('p', 'pane-note', 'None recorded.'));
  } else {
    const mentions = el('dl', 'kv');
    record.mentions.forEach(function (mention) {
      mentions.appendChild(el('dt', null, mention.supported ? 'observed' : 'unsupported'));
      mentions.appendChild(el('dd', null, mention.source));
    });
    signal.appendChild(mentions);
    signal.appendChild(el('p', 'pane-note',
      'An unsupported mention stays visible here and is never promoted to observed evidence.'));
  }
  body.appendChild(signal);

  const provenance = el('div');
  provenance.appendChild(el('h4', null, 'Provenance'));
  const provList = el('dl', 'kv');
  Object.keys(record.provenance || {}).sort().forEach(function (key) {
    const value = record.provenance[key];
    provList.appendChild(el('dt', null, key));
    const dd = el('dd', value === null ? 'unknown' : null, show(value));
    provList.appendChild(dd);
  });
  provenance.appendChild(provList);
  body.appendChild(provenance);

  const unknown = el('div');
  unknown.appendChild(el('h4', null, 'Never measured (' + record.unknown.length + ')'));
  if (!record.unknown.length) {
    unknown.appendChild(el('p', 'pane-note', 'Every field was observed.'));
  } else {
    const list = el('div', 'unknown-list');
    record.unknown.forEach(function (name) { list.appendChild(el('span', null, name)); });
    unknown.appendChild(list);
    unknown.appendChild(el('p', 'pane-note',
      'These values were not observed. They are recorded as unknown rather than defaulted.'));
  }
  if (record.errors && record.errors.length) {
    unknown.appendChild(el('h4', null, 'Errors'));
    unknown.appendChild(el('pre', null, record.errors.join('\n')));
  }
  body.appendChild(unknown);

  host.appendChild(body);
}

function renderBoundaries(data) {
  const host = document.getElementById('boundary-grid');
  host.replaceChildren();
  data.boundaries.forEach(function (item) {
    const node = el('div', 'boundary');
    node.appendChild(el('div', 'title', item.title));
    node.appendChild(el('p', 'detail-text', item.detail));
    node.appendChild(el('div', 'source', item.source));
    host.appendChild(node);
  });
}

function render(data) {
  const missing = FIELDS.filter(function (name) { return !(name in data); });
  if (missing.length) {
    throw new Error('export is missing field(s): ' + missing.join(', '));
  }
  renderMasthead(data);
  renderComparison(data);
  renderCases(data);
  renderAttempts(data);
  renderBoundaries(data);
}

function fail(message) {
  const node = document.getElementById('load-error');
  node.hidden = false;
  node.replaceChildren();
  node.appendChild(el('strong', null, 'Could not load the export. '));
  node.appendChild(el('span', null, message));
}

/* Two load paths. fetch() works over http; a file:// page is blocked from
 * fetching its own directory, so the generated data/export.js wrapper is
 * loaded by <script> instead. Both carry the same bytes and the checker
 * verifies they agree. */
function load() {
  if (window.LANTERN_EXPORT) {
    render(window.LANTERN_EXPORT);
    return;
  }
  fetch('data/export.json')
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(render)
    .catch(function () {
      const script = document.createElement('script');
      script.src = 'data/export.js';
      script.onload = function () {
        if (window.LANTERN_EXPORT) {
          document.getElementById('load-error').hidden = true;
          render(window.LANTERN_EXPORT);
        } else {
          fail('data/export.js loaded but defined no export. Regenerate with ' +
               '`python3 -m runner.cli export`.');
        }
      };
      script.onerror = function () {
        fail('Neither data/export.json nor data/export.js could be read. ' +
             'Run `python3 -m runner.cli export`, or serve the directory with ' +
             '`python3 -m http.server --directory frontend`.');
      };
      document.head.appendChild(script);
    });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', load);
} else {
  load();
}
