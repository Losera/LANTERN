/* Offline frontend regressions. No packages or model calls required. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/app.js'), 'utf8');
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'frontend/data/export.json'), 'utf8'));

function harness(protocol = 'http:', fetchImpl = async () => ({ ok: true, json: async () => fixture })) {
  const nodes = new Map();
  function node() {
    return {
      children: [], listeners: {}, listenerCounts: {}, hidden: true,
      replaceChildren(...children) { this.children = children; },
      appendChild(child) { this.children.push(child); },
      addEventListener(name, handler) {
        this.listeners[name] = handler;
        this.listenerCounts[name] = (this.listenerCounts[name] || 0) + 1;
      },
      setAttribute() {}, removeAttribute() {}
    };
  }
  const document = {
    readyState: 'loading', addEventListener() {},
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, node());
      return nodes.get(id);
    },
    createElement: node, querySelectorAll: () => [],
    documentElement: node(), head: node()
  };
  const calls = [];
  let reloads = 0;
  const window = { location: { protocol, reload() { reloads++; } } };
  const context = vm.createContext({
    document, window, Node: Object,
    fetch: (...args) => { calls.push(args); return fetchImpl(...args); }
  });
  vm.runInContext(source, context);
  return { context, document, window, calls, get reloads() { return reloads; } };
}

function text(node) {
  return (node.textContent || '') + node.children.map(text).join('');
}

const settle = () => new Promise(resolve => setImmediate(resolve));

test('record labels distinguish empty, synthetic, mixed and non-synthetic exports', () => {
  const h = harness();
  for (const [total, synthetic, expected] of [
    [0, 0, 'No records'],
    [2, 2, 'All 2 records synthetic'],
    [2, 1, '1 of 2 records synthetic'],
    [2, 0, 'All 2 records non-synthetic']
  ]) {
    h.context.renderMasthead({
      ...fixture, attempts: Array(total).fill({}),
      synthetic_records: synthetic, all_records_synthetic: total > 0 && synthetic === total
    });
    assert.equal(h.document.getElementById('synthetic-chip').textContent, expected);
  }
});

test('HTTP fetch bypasses caches and ignores a preloaded wrapper', async () => {
  const h = harness();
  let rendered;
  h.window.LANTERN_EXPORT = { label: 'stale wrapper' };
  h.context.renderOrFail = data => { rendered = data; };
  h.context.load();
  await settle();
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0][0], 'data/export.json');
  assert.equal(h.calls[0][1].cache, 'no-store');
  assert.equal(rendered, fixture);
  assert.equal(h.document.head.children.length, 0);
  h.document.getElementById('refresh-results').listeners.click();
  assert.equal(h.reloads, 1);
  assert.match(fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8'),
    /<button[^>]*id="refresh-results"[^>]*>Refresh results<\/button>/);
});

test('HTTP failures surface instead of loading a potentially stale wrapper', async () => {
  for (const fetchImpl of [
    async () => { throw new Error('offline'); },
    async () => ({ ok: false, status: 404 }),
    async () => ({ ok: true, json: async () => { throw new SyntaxError('invalid JSON'); } })
  ]) {
    const h = harness('http:', fetchImpl);
    h.window.LANTERN_EXPORT = fixture;
    h.context.load();
    await settle();
    assert.equal(h.document.getElementById('load-error').hidden, false);
    assert.match(text(h.document.getElementById('load-error')), /latest snapshot could not be read/);
    assert.equal(h.document.head.children.length, 0);
  }
});

test('a structurally invalid export surfaces its missing fields', async () => {
  const h = harness('http:', async () => ({ ok: true, json: async () => ({}) }));
  h.context.load();
  await settle();
  assert.equal(h.document.getElementById('load-error').hidden, false);
  assert.match(text(h.document.getElementById('load-error')), /missing field/);
  assert.equal(h.document.head.children.length, 0);
});

test('file pages use the wrapper without fetching JSON', () => {
  const h = harness('file:');
  let rendered;
  h.context.renderOrFail = data => { rendered = data; };
  h.context.load();
  assert.equal(h.calls.length, 0);
  const script = h.document.head.children[0];
  assert.equal(script.src, 'data/export.js');
  h.window.LANTERN_EXPORT = fixture;
  script.onload();
  assert.equal(rendered, fixture);
});

test('file pages report missing or unreadable wrappers', () => {
  for (const event of ['onload', 'onerror']) {
    const h = harness('file:');
    h.context.load();
    h.document.head.children[0][event]();
    assert.equal(h.document.getElementById('load-error').hidden, false);
  }
});

test('file pages can render an already loaded wrapper', () => {
  const h = harness('file:');
  let rendered;
  h.context.renderOrFail = data => { rendered = data; };
  h.window.LANTERN_EXPORT = fixture;
  h.context.load();
  assert.equal(rendered, fixture);
  assert.equal(h.calls.length, 0);
  assert.equal(h.document.head.children.length, 0);
});

function exportFile(data = fixture, name = 'pilot.json') {
  return { name, text: async () => JSON.stringify(data) };
}

test('a local export renders without uploading and identifies the file as its source', async () => {
  const h = harness();
  await h.context.openResultsFile(exportFile(fixture, '<pilot>.json'));
  assert.equal(h.document.getElementById('load-error').hidden, true);
  assert.equal(h.document.getElementById('meta-source').textContent, 'Opened file: <pilot>.json');
  assert.equal(h.document.getElementById('refresh-results').textContent, 'Return to served results');
  assert.match(h.document.getElementById('source-note').textContent, /Reopen it after regeneration/);
  assert.equal(h.calls.length, 0);
  assert.equal(h.document.getElementById('case-status-chip').hidden, false);
  assert.equal(h.document.getElementById('case-status-chip').textContent, 'Fictional case — pilot');
});

test('unreadable, malformed, JSONL and structurally invalid files retain the prior snapshot', async () => {
  const badSchema = { ...fixture, schema_version: 1 };
  const badNested = structuredClone(fixture);
  badNested.attempts[0].mentions = null;
  const badCases = structuredClone(fixture);
  badCases.cases[0].options = {};
  const badAnalysis = structuredClone(fixture);
  badAnalysis.analysis.coverage[0].pending = null;
  const h = harness();
  await h.context.openResultsFile(exportFile());
  const before = h.document.getElementById('attempts-table').children;
  for (const file of [
    { name: 'broken.json', text: async () => '{' },
    { name: 'unreadable.json', text: async () => { throw new Error('read failed'); } },
    exportFile(fixture, 'attempts.jsonl'),
    exportFile(null), exportFile([]), exportFile({}),
    exportFile(badSchema), exportFile(badNested), exportFile(badCases), exportFile(badAnalysis)
  ]) {
    await h.context.openResultsFile(file);
    assert.equal(h.document.getElementById('load-error').hidden, false);
    assert.match(text(h.document.getElementById('load-error')), /Previously loaded results remain active/);
    assert.equal(h.document.getElementById('meta-source').textContent, 'Opened file: pilot.json');
    assert.equal(h.document.getElementById('attempts-table').children, before);
  }
});

test('repeated imports clear filters and attempt details without rebinding controls', async () => {
  const h = harness();
  h.context.load();
  await settle();
  h.document.getElementById('filter-arm').listeners.change({ target: { value: 'baseline' } });
  h.document.getElementById('attempt-detail').textContent = 'Old attempt details';
  await h.context.openResultsFile(exportFile());
  await h.context.openResultsFile(exportFile());
  assert.equal(h.document.getElementById('filter-count').textContent, 'showing all 8 recorded attempts');
  assert.match(h.document.getElementById('attempt-detail').textContent, /^Select an attempt/);
  assert.equal(h.document.getElementById('filter-arm').listenerCounts.change, 1);
  assert.equal(h.document.getElementById('filter-reset').listenerCounts.click, 1);
  assert.equal(h.document.getElementById('load-error').hidden, true);
});

test('opening a file works after the served snapshot fails; return control reloads', async () => {
  const h = harness('http:', async () => ({ ok: false, status: 404 }));
  h.context.load();
  await settle();
  assert.equal(h.document.getElementById('load-error').hidden, false);
  const input = h.document.getElementById('results-file');
  const target = { files: [exportFile()], value: 'pilot.json' };
  input.listeners.change({ target });
  await settle();
  assert.equal(target.value, '');
  assert.equal(h.document.getElementById('load-error').hidden, true);
  h.document.getElementById('refresh-results').listeners.click();
  assert.equal(h.reloads, 1);
});

test('a late served response cannot replace the selected file', async () => {
  let resolveFetch;
  const h = harness('http:', () => new Promise(resolve => { resolveFetch = resolve; }));
  h.context.load();
  await h.context.openResultsFile(exportFile());
  resolveFetch({ ok: true, json: async () => ({ ...fixture, label: 'OLD RESPONSE' }) });
  await settle();
  assert.equal(h.document.getElementById('label-chip').textContent, fixture.label);
  assert.equal(h.document.getElementById('meta-source').textContent, 'Opened file: pilot.json');
});

test('the latest selected file wins even when earlier reads finish later', async () => {
  const h = harness();
  let finishRead;
  const pending = h.context.openResultsFile({ name: 'old.json', text: () => new Promise(resolve => { finishRead = resolve; }) });
  await h.context.openResultsFile(exportFile(fixture, 'new.json'));
  finishRead(JSON.stringify({ ...fixture, label: 'OLD FILE' }));
  await pending;
  assert.equal(h.document.getElementById('label-chip').textContent, fixture.label);
  assert.equal(h.document.getElementById('meta-source').textContent, 'Opened file: new.json');
});
