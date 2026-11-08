/* LANTERN evidence view.
 *
 * Renders frontend/data/export.json. No dependencies, no network access, no
 * build step. The page presents the exported analysis and tallies choices
 * directly from retained records. It makes no new effect or grading judgments. Where a value is unknown the page says "unknown" rather than 0.
 *
 * Every string that reaches the DOM goes through textContent. Model output and
 * other supplied text is never parsed as markup.
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
  measured: ['The recommendation changed with framing', 'At least one case had a different recorded choice with the framing prompt. This alone does not establish bias or explain why it changed.'],
  none_measured: ['The framing prompt did not change the recommendation', 'For every case that could be compared, the original and framing prompts produced the same choice. This finding applies only to these records.'],
  insufficient: ['We cannot compare the recommendations yet', 'We need consistent, usable choices from both the original and framing prompts for a case. These records do not support that comparison.']
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

const ALL = '__all__';

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

function mono(value) {
  return el('code', null, show(value));
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
    const th = el('th', [column.wrap ? 'wrap' : '', column.numeric ? 'num' : ''].join(' ').trim() || null, column.label);
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
    if (settings.rowClass) tr.className = settings.rowClass(row, index) || '';
    columns.forEach(function (column) {
      const value = column.render(row, index, tr);
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
  return body;
}

function tiles(target, rows) {
  const host = document.getElementById(target);
  host.replaceChildren();
  rows.forEach(function (row) {
    const tile = el('div', 'tile');
    tile.appendChild(el('div', 'name', row[0]));
    tile.appendChild(el('div', row[3] ? 'value text' : 'value', row[1]));
    tile.appendChild(el('div', 'denominator', row[2]));
    host.appendChild(tile);
  });
}

function renderMasthead(data) {
  document.getElementById('label-chip').textContent = data.label;
  document.getElementById('meta-lane').textContent = show(data.lane);
  document.getElementById('meta-generated').textContent = show(data.generated_utc);
  document.getElementById('meta-conformance').textContent = show(data.oracle_conformance);
  document.getElementById('meta-schema').textContent =
    'v' + data.schema_version + ' (proposed)';

  /* The label already names the dataset, and the checker refuses an
   * all-synthetic export whose label omits it. These two fields carry how many
   * records that covers, which the label alone does not say. A mixed dataset
   * must not read as a fully synthetic one, so the two cases differ. */
  const chip = document.getElementById('synthetic-chip');
  chip.hidden = false;
  if (data.attempts.length === 0) {
    chip.textContent = 'No records';
  } else if (data.synthetic_records === 0) {
    chip.textContent = data.attempts.length + ' attempts · 0 synthetic';
  } else if (data.all_records_synthetic) {
    chip.textContent =
      'All ' + show(data.synthetic_records) + ' records synthetic';
  } else {
    chip.textContent =
      show(data.synthetic_records) + ' of ' + data.attempts.length +
      ' records synthetic';
  }
}

const ARM_NAMES = {
  baseline: 'Original prompt', unchanged_rerun: 'Exact repeat',
  neutral_edit: 'Neutral addition', framing: 'Framing prompt', correction: 'Correction prompt'
};
const ARM_EXPLANATIONS = {
  baseline: 'Decision evidence and instructions.',
  unchanged_rerun: 'The exact same prompt, sent again.',
  neutral_edit: 'Extra presentation guidance of roughly similar length; no changed facts.',
  framing: 'Adds cues declared irrelevant beforehand, such as an endorsement.',
  correction: 'Adds an explicit correction after framing; compared separately.'
};
function armName(value) { return ARM_NAMES[value] || value; }
function optionName(data, value, caseId) {
  for (const item of data.cases) {
    if (caseId && item.id !== caseId) continue;
    const match = item.options.find(function (option) { return option.id === value; });
    if (match) return match.label;
  }
  return show(value);
}
function findingSummary(data) {
  const host = document.getElementById('finding-summary');
  host.replaceChildren();
  const example = data.all_records_synthetic;
  host.appendChild(el('p', 'eyebrow', example ? 'Example data — not experiment findings' : 'What these records show'));
  const records = data.attempts;
  const first = records[0];
  const sameChoice = data.cases.length === 1 && first && records.every(function (r) {
    return r.case_id === data.cases[0].id && r.outcome === 'decision' && r.option_id && r.option_id === first.option_id;
  });
  const headline = sameChoice
    ? 'All ' + records.length + ' recorded responses chose ' + optionName(data, first.option_id) + '.'
    : records.length + ' model calls are recorded in this dataset.';
  host.appendChild(el('h2', null, (example ? 'Example: ' : '') + headline));
  const arms = data.analysis.arms;
  const repetitions = arms.length && arms.every(function (r) { return r.attempts === arms[0].attempts; })
    ? ' · ' + arms[0].attempts + ' calls per version' : '';
  const fictional = data.cases.length && data.cases.every(function (c) { return c.status.includes('FICTIONAL_EXAMPLE'); });
  host.appendChild(el('p', 'finding-scope', data.cases.length + (fictional ? ' fictional case' : ' case') +
    (data.cases.length === 1 ? '' : 's') + ' · ' + arms.length + ' prompt versions' + repetitions));
  const identities = [...new Set(records.map(function (r) {
    return r.provenance ? show(r.provenance.model_id) + ' · ' + show(r.provenance.execution_site) : 'unknown';
  }))];
  host.appendChild(el('p', 'finding-scope', 'Model / execution site: ' + (identities.length ? identities.join('; ') : 'not recorded')));
  const framingText = EFFECT_TEXT[data.analysis.effect];
  if (framingText) host.appendChild(el('p', null, framingText[0] + '.'));
  const correction = data.analysis.correction_pairs;
  const correctionText = correction.length && correction.every(function (r) { return r.verdict === 'stable'; })
    ? 'The correction prompt also left the choice unchanged in every comparable case.'
    : correction.some(function (r) { return r.verdict === 'flip'; })
      ? 'The correction prompt changed the choice in at least one case; see its separate comparison below.'
      : 'The correction result is not fully established; see its separate comparison below.';
  host.appendChild(el('p', null, correctionText));
  const ungraded = records.length && records.every(function (r) { return r.correctness === 'unknown'; });
  host.appendChild(el('p', 'finding-limit', ungraded
    ? 'We have not graded whether these choices are correct. An unchanged choice does not prove the model is resistant to framing in general.'
    : 'Agreement between choices does not establish correctness. Check the grading field on each response.'));
  if (data.synthetic_records && !example) host.appendChild(el('p', 'finding-limit', 'This dataset includes synthetic records. Do not treat all displayed responses as real model outputs.'));
  const link = el('a', 'lt-btn ghost', 'Inspect a recorded response');
  link.href = '#attempts'; host.appendChild(link);
}

/* Pair columns are shared by the framing-only and correction tables so the two
 * are visibly the same measurement reported in two places, never merged. */
const PAIR_COLUMNS = [
  { label: 'Case', render: function (r) { return r.case_id; } },
  { label: 'Original choice', render: function (r) { return mono(r.baseline_option); } },
  { label: 'Changed-prompt choice', render: function (r) { return mono(r.contrast_option); } },
  { label: 'Choice changed?', render: function (r) { return badge(r.verdict === 'stable' ? 'No' : r.verdict === 'flip' ? 'Yes' : 'Cannot tell', r.verdict); } },
  { label: 'What this means', wrap: true, render: function (r) { return r.verdict === 'stable' ? 'Both prompts led to the same choice.' : r.verdict === 'flip' ? 'The recorded choices differ.' : r.reason; } }
];

function renderComparison(data) {
  findingSummary(data);
  const analysis = data.analysis;
  const counts = analysis.framing_counts;
  const copy = EFFECT_TEXT[analysis.effect] || ['Unrecognised effect value', analysis.effect];
  const banner = document.getElementById('effect-banner');
  banner.className = 'verdict-banner ' + analysis.effect;
  banner.replaceChildren(el('strong', null, (data.all_records_synthetic ? 'Example only: ' : '') + copy[0]), el('span', null, copy[1]));

  /* Every figure below is read from the export. None is recomputed here. */
  tiles('comparison-tiles', [
    ['Model calls recorded', analysis.attempts, 'all prompt versions; includes errors'],
    ['Cases compared', counts.pairs, 'original prompt vs framing prompt'],
    ['Changed choice', counts.flip, 'of ' + counts.pairs + ' case comparisons'],
    ['Same choice', counts.stable, 'of ' + counts.pairs + ' case comparisons'],
    ['Cannot compare', counts.unresolved, 'a usable choice is missing or inconsistent']
  ]);

  const pairColumns = PAIR_COLUMNS.map(function (column, index) {
    if (index !== 1 && index !== 2) return column;
    return Object.assign({}, column, { render: function (r) {
      return optionName(data, index === 1 ? r.baseline_option : r.contrast_option, r.case_id);
    }});
  });
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
}

function renderArms(data) {
  table('arms-table', [
    { label: 'Prompt version', render: function (r) { return armName(r.arm); } },
    { label: 'What changed', wrap: true, render: function (r) { return ARM_EXPLANATIONS[r.arm] || 'See prompt details.'; } },
    { label: 'Recorded choices', wrap: true, render: function (r) {
      const choices = Object.create(null);
      data.attempts.filter(function (a) { return a.arm === r.arm && a.outcome === 'decision'; }).forEach(function (a) {
        const name = optionName(data, a.option_id, a.case_id); choices[name] = (choices[name] || 0) + 1;
      });
      return Object.keys(choices).map(function (name) { return name + ' × ' + choices[name]; }).join('; ') || 'No usable choice';
    } },
    { label: 'Attempts', numeric: true, render: function (r) { return r.attempts; } },
    { label: 'Usable choices', numeric: true, render: function (r) { return r.decisions; } },
    { label: 'Still unknown', numeric: true, render: function (r) { return r.unresolved; } },
    { label: 'Failures', numeric: true, render: function (r) { return r.failure_total; } },
    { label: 'Error types', wrap: true, render: function (r) {
        const kinds = Object.keys(r.failures).sort();
        if (!kinds.length) return '—';
        const host = el('span', 'legend');
        kinds.forEach(function (kind) {
          host.appendChild(badge(kind + ' × ' + r.failures[kind], OUTCOME_CLASS[kind] || 'neutral'));
        });
        return host;
      } }
  ], data.analysis.arms, { empty: 'No arm recorded an attempt.' });
}

function renderCoverage(data) {
  const analysis = data.analysis;

  /* Run-level figures come from analysis.coverage, which the runner computes.
   * The design's "readable / failures / unresolved" run totals have no export
   * field; summing the per-arm table here would be this page inventing a
   * metric, so the per-arm pane reports those instead. */
  const runs = analysis.coverage;
  const registered = runs.length === 1 ? runs[0].registered : 'see table';
  const definitive = runs.length === 1 ? runs[0].definitive : 'see table';
  const pending = runs.length === 1 ? runs[0].pending.length : 'see table';
  const coveredRuns = runs.filter(function (row) { return row.covered; }).length;

  tiles('coverage-tiles', [
    ['Runs fully accounted for', coveredRuns, 'of ' + runs.length + ' runs'],
    ['Expected responses', registered, runs.length === 1 ? 'in this run' : 'per run'],
    ['Known outcomes', definitive, runs.length === 1 ? 'of ' + registered : 'per run'],
    ['Outcomes still unknown', pending, 'completion has not been established']
  ]);

  table('coverage-table', [
    { label: 'Run', render: function (r) { return r.run_id; } },
    { label: 'Expected', numeric: true, render: function (r) { return r.registered; } },
    { label: 'Known outcomes', numeric: true, render: function (r) { return r.definitive; } },
    { label: 'All outcomes known?', render: function (r) {
        return badge(r.covered ? 'Yes' : 'No', r.covered ? 'stable' : 'unresolved');
      } },
    { label: 'Outcomes still unknown', wrap: true, render: function (r) {
        if (!r.pending.length) return 'none';
        const host = el('span');
        r.pending.forEach(function (id, index) {
          if (index) host.appendChild(el('span', null, ', '));
          host.appendChild(mono(id));
        });
        return host;
      } }
  ], runs, { empty: 'No run was registered.' });

  const notes = document.getElementById('counting-notes');
  notes.replaceChildren();
  analysis.notes.forEach(function (note) { notes.appendChild(el('li', null, note)); });
}

function renderCases(data) {
  const host = document.getElementById('cases');
  host.replaceChildren();
  if (!data.cases.length) {
    host.appendChild(el('p', 'detail-empty', 'No case is included in this dataset.'));
    return;
  }
  data.cases.forEach(function (item) {
    const card = el('div', 'case');
    const head = el('div', 'case-head');
    head.appendChild(el('div', 'q', item.question));
    head.appendChild(el('div', 'case-status', item.id + ' · ' + item.status));
    card.appendChild(head);

    const body = el('div', 'case-body');

    /* The export has carried the option vocabulary all along; the page did not
     * show it, so a reader could not tell what the model was choosing between. */
    body.appendChild(el('h3', null, 'Available choices — ' + item.options.length + ' offered'));
    const options = el('div', 'options-row');
    item.options.forEach(function (option) {
      options.appendChild(badge(option.id + ' · ' + option.label, 'neutral'));
    });
    body.appendChild(options);

    body.appendChild(el('h3', null,
      'Evidence — ' + item.relevant_count + ' declared relevant, ' +
      item.irrelevant_count + ' declared irrelevant'));
    const evidenceTable = el('table');
    evidenceTable.id = 'evidence-' + item.id;
    const evidenceScroll = el('div', 'table-scroll');
    evidenceScroll.appendChild(evidenceTable);
    body.appendChild(evidenceScroll);

    body.appendChild(el('h3', null, 'Decision requirements: ' + item.rubric.id));
    const rubric = el('ul', 'rubric');
    item.rubric.requirements.forEach(function (line) {
      rubric.appendChild(el('li', null, line));
    });
    body.appendChild(rubric);

    card.appendChild(body);
    host.appendChild(card);

    table('evidence-' + item.id, [
      { label: 'Item', render: function (r) { return mono(r.id); } },
      { label: 'Relevance', render: function (r) {
          return badge(r.relevant ? 'relevant' : 'irrelevant', r.relevant ? 'stable' : 'neutral');
        } },
      { label: 'Claim', wrap: true, render: function (r) { return r.claim; } },
      { label: 'Source', wrap: true, render: function (r) { return r.source; } },
      { label: 'Authority', wrap: true, render: function (r) { return r.source_authority; } }
    ], item.evidence, {
      caption: 'Relevance is declared in advance; source authority is preserved, not stripped.',
      empty: 'This case declares no evidence item.'
    });
  });
}

/* prompt_sha256 is recorded per attempt, not per condition. Looking it up is a
 * projection of an exported field; it is not a computed measurement. The value
 * stays unknown while prompt rendering is an unapproved seam. */
function conditionPromptHash(attempts, conditionId) {
  const seen = [];
  attempts.forEach(function (row) {
    if (row.condition_id !== conditionId) return;
    const value = row.prompt_sha256;
    if (value === null || value === undefined || value === '') return;
    if (seen.indexOf(value) === -1) seen.push(value);
  });
  if (!seen.length) return 'unknown';
  if (seen.length > 1) return 'mixed';
  return seen[0];
}

function renderConditions(data) {
  const host = document.getElementById('condition-sets');
  host.replaceChildren();
  if (!data.cases.length) {
    host.appendChild(el('p', 'detail-empty', 'This export carries no case, so no condition was expanded.'));
    return;
  }
  data.cases.forEach(function (item) {
    const wrap = el('div');
    wrap.appendChild(el('h3', null,
      item.id + ' — ' + item.conditions.length + ' conditions'));
    const conditionTable = el('table');
    conditionTable.id = 'conditions-' + item.id;
    const scroll = el('div', 'table-scroll');
    scroll.appendChild(conditionTable);
    wrap.appendChild(scroll);
    wrap.appendChild(el('p', 'detail-empty',
      'Prompt hashes identify the rendered input recorded for each condition. ' +
      'Unknown means no prompt hash was recorded.'));
    host.appendChild(wrap);

    table('conditions-' + item.id, [
      { label: 'Prompt ID', render: function (r) { return mono(r.id); } },
      { label: 'Prompt version', render: function (r) { return armName(r.arm); } },
      { label: 'Changes evidence', render: function (r) {
          return el('span', 'flag' + (r.changes_evidence ? ' on' : ''), r.changes_evidence ? 'yes' : 'no');
        } },
      { label: 'In framing comparison?', render: function (r) {
          return el('span', 'flag' + (r.framing_only_eligible ? '' : ' on'), r.framing_only_eligible ? 'yes' : 'no');
        } },
      { label: 'Reason excluded', wrap: true, render: function (r) {
          return r.confounded ? r.confound_reason : '—';
        } },
      { label: 'Prompt sha256', numeric: true, render: function (r) {
          return conditionPromptHash(data.attempts, r.id);
        } }
    ], item.conditions, { empty: 'No conditions expanded for this case.' });
  });
}

/* ---------- attempts ---------- */

let attemptState = { records: [], arm: ALL, outcome: ALL, selected: null };

function uniqueSorted(values) {
  const seen = [];
  values.forEach(function (value) {
    if (seen.indexOf(value) === -1) seen.push(value);
  });
  return seen.sort();
}

function fillSelect(id, values, allLabel) {
  const node = document.getElementById(id);
  node.replaceChildren();
  const first = el('option', null, allLabel);
  first.value = ALL;
  node.appendChild(first);
  values.forEach(function (value) {
    const option = el('option', null, value);
    if (id === 'filter-arm') option.textContent = armName(value);
    option.value = value;
    node.appendChild(option);
  });
}

function renderAttempts(data) {
  attemptState = { records: data.attempts, arm: ALL, outcome: ALL, selected: null };

  /* The legend is a tally of every record in the export, shown so the outcome
   * vocabulary is visible. The filter below never narrows it. */
  const legend = document.getElementById('outcome-legend');
  legend.replaceChildren();
  const seen = {};
  data.attempts.forEach(function (row) { seen[row.outcome] = (seen[row.outcome] || 0) + 1; });
  Object.keys(seen).sort().forEach(function (kind) {
    legend.appendChild(badge(kind + ' × ' + seen[kind], OUTCOME_CLASS[kind] || 'neutral'));
  });

  fillSelect('filter-arm', uniqueSorted(data.attempts.map(function (r) { return r.arm; })), 'All prompt versions');
  fillSelect('filter-outcome', uniqueSorted(data.attempts.map(function (r) { return r.outcome; })), 'All outcomes');

  document.getElementById('filter-arm').addEventListener('change', function (event) {
    attemptState.arm = event.target.value;
    drawAttempts();
  });
  document.getElementById('filter-outcome').addEventListener('change', function (event) {
    attemptState.outcome = event.target.value;
    drawAttempts();
  });
  document.getElementById('filter-reset').addEventListener('click', function () {
    attemptState.arm = ALL;
    attemptState.outcome = ALL;
    document.getElementById('filter-arm').value = ALL;
    document.getElementById('filter-outcome').value = ALL;
    drawAttempts();
  });

  drawAttempts();
}

function drawAttempts() {
  const all = attemptState.records;
  const rows = all.filter(function (row) {
    return (attemptState.arm === ALL || row.arm === attemptState.arm) &&
           (attemptState.outcome === ALL || row.outcome === attemptState.outcome);
  });

  const filtered = rows.length !== all.length;
  document.getElementById('filter-count').textContent = filtered
    ? 'showing ' + rows.length + ' of ' + all.length + ' recorded attempts'
    : 'showing all ' + all.length + ' recorded attempts';

  table('attempts-table', [
    { label: 'Attempt', render: function (r) {
        const button = el('button', 'attempt-pick', r.attempt_id);
        button.type = 'button';
        button.setAttribute('aria-controls', 'attempt-detail');
        button.setAttribute('aria-pressed', String(attemptState.selected === r.attempt_id));
        button.addEventListener('click', function () {
          attemptState.selected = r.attempt_id;
          drawAttempts();
          renderDetail(r);
          document.getElementById('attempt-detail').focus();
        });
        return button;
      } },
    { label: 'Prompt version', render: function (r) { return armName(r.arm); } },
    { label: 'Prompt ID', render: function (r) { return mono(r.condition_id); } },
    { label: 'Outcome', render: function (r) {
        return badge(r.outcome, OUTCOME_CLASS[r.outcome] || 'neutral');
      } },
    { label: 'Choice', render: function (r) { return mono(r.option_id); } },
    { label: 'Grading result', render: function (r) {
        /* Readability and correctness are different questions. A readable
         * decision whose correctness was never graded says so. */
        const value = show(r.correctness);
        return badge(value, value === 'unknown' ? 'neutral' : 'decision');
      } },
    { label: 'Site', render: function (r) { return r.provenance ? r.provenance.execution_site : null; } },
    { label: 'Unmeasured', numeric: true, render: function (r) { return r.unknown.length; } }
  ], rows, {
    empty: filtered
      ? 'No recorded attempt matches these filters. Clear them to see all ' + all.length + '.'
      : 'No attempts recorded.',
    rowClass: function (r) {
      return attemptState.selected === r.attempt_id ? 'selectable selected' : 'selectable';
    }
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
  raw.appendChild(el('h4', null, 'Explanation supplied by the model'));
  raw.appendChild(el('pre', null, show(record.received_explanation)));
  raw.appendChild(el('p', 'pane-note',
    'A stated explanation is received text. It is not evidence about the ' +
    'model’s internal computation.'));
  body.appendChild(raw);

  const signal = el('div');
  signal.appendChild(el('h4', null, 'Recorded choice and grading'));
  const verdictList = el('dl', 'kv');
  [
    ['outcome', record.outcome],
    ['option_id', record.option_id],
    ['correctness', record.correctness],
    ['prompt_sha256', record.prompt_sha256]
  ].forEach(function (pair) {
    verdictList.appendChild(el('dt', null, pair[0]));
    const value = show(pair[1]);
    verdictList.appendChild(el('dd', value === 'unknown' ? 'unknown' : null, value));
  });
  signal.appendChild(verdictList);

  signal.appendChild(el('h4', null, 'How the response was read (technical details)'));
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
  provenance.appendChild(el('h4', null, 'Model, settings and timestamps'));
  const provList = el('dl', 'kv');
  Object.keys(record.provenance || {}).sort().forEach(function (key) {
    const value = record.provenance[key];
    provList.appendChild(el('dt', null, key));
    provList.appendChild(el('dd', value === null ? 'unknown' : null, show(value)));
  });
  provenance.appendChild(provList);
  body.appendChild(provenance);

  const unknown = el('div');
  unknown.appendChild(el('h4', null, 'Fields not measured (' + record.unknown.length + ')'));
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
  if (!data.boundaries.length) {
    host.appendChild(el('p', 'detail-empty',
      'This export carries no boundary statement. Treat that as missing, not as an absence of limits.'));
    return;
  }
  data.boundaries.forEach(function (item) {
    const node = el('div', 'boundary');
    node.appendChild(el('div', 'title', item.title));
    node.appendChild(el('p', 'detail-text', item.detail));
    node.appendChild(el('div', 'source', item.source));
    host.appendChild(node);
  });
}

/* A structurally valid export that recorded nothing must say so, rather than
 * presenting empty panes that look like a finding. */
function renderEmptyState(data) {
  const node = document.getElementById('empty-state');
  const gaps = [];
  if (!data.attempts.length) gaps.push('no attempt was recorded');
  if (!data.cases.length) gaps.push('no case is present');
  if (!data.analysis.framing_pairs.length) gaps.push('no framing-only pair could be formed');
  if (!gaps.length) {
    node.hidden = true;
    return;
  }
  node.hidden = false;
  node.replaceChildren();
  node.appendChild(el('strong', null, 'This export is readable but incomplete. '));
  node.appendChild(el('span', null,
    gaps.join('; ') + '. The panes below report that absence; they do not report a result.'));
}

/* ---------- theme ---------- */

const THEME_KEY = 'lantern-theme';

function applyTheme(choice) {
  const root = document.documentElement;
  if (choice === 'light' || choice === 'dark') {
    root.setAttribute('data-theme', choice);
  } else {
    root.removeAttribute('data-theme');
  }
}

function setUpTheme() {
  let stored = null;
  try {
    stored = window.localStorage.getItem(THEME_KEY);
  } catch (error) {
    stored = null;
  }
  const choice = (stored === 'light' || stored === 'dark') ? stored : 'auto';
  applyTheme(choice);
  const inputs = document.querySelectorAll('input[name="theme"]');
  Array.prototype.forEach.call(inputs, function (input) {
    input.checked = input.value === choice;
    input.addEventListener('change', function () {
      if (!input.checked) return;
      applyTheme(input.value);
      try {
        if (input.value === 'auto') {
          window.localStorage.removeItem(THEME_KEY);
        } else {
          window.localStorage.setItem(THEME_KEY, input.value);
        }
      } catch (error) {
        /* A viewer with storage denied still gets the theme for this visit. */
      }
    });
  });
}

/* ---------- section nav ---------- */

function setUpNav() {
  const links = document.querySelectorAll('.section-nav a');
  const mark = function (hash) {
    Array.prototype.forEach.call(links, function (link) {
      link.classList.toggle('here', link.hash === hash);
    });
  };
  Array.prototype.forEach.call(links, function (link) {
    link.addEventListener('click', function () { mark(link.hash); });
  });
  if (window.location.hash) mark(window.location.hash);
}

function render(data) {
  const missing = FIELDS.filter(function (name) { return !(name in data); });
  if (missing.length) {
    throw new Error('export is missing field(s): ' + missing.join(', '));
  }
  renderMasthead(data);
  renderEmptyState(data);
  renderComparison(data);
  renderArms(data);
  renderCoverage(data);
  renderCases(data);
  renderConditions(data);
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

/* A structural problem must surface on the page, not only in the console. */
function renderOrFail(data) {
  try {
    render(data);
    document.getElementById('load-error').hidden = true;
  } catch (error) {
    fail(String(error && error.message ? error.message : error));
  }
}

/* Two load paths. fetch() works over http; a file:// page is blocked from
 * fetching its own directory, so the generated data/export.js wrapper is
 * loaded by <script> instead. Both carry the same bytes and the checker
 * verifies they agree. */
function load() {
  setUpTheme();
  setUpNav();

  if (window.LANTERN_EXPORT) {
    renderOrFail(window.LANTERN_EXPORT);
    return;
  }
  fetch('data/export.json')
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(renderOrFail)
    .catch(function () {
      const script = document.createElement('script');
      script.src = 'data/export.js';
      script.onload = function () {
        if (window.LANTERN_EXPORT) {
          renderOrFail(window.LANTERN_EXPORT);
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
