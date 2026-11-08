"""Execute the bulk UI command through lost-response and concurrent-click cases."""
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("scenario", [
    "lost-response", "csrf", "redirect", "server-error", "unreadable",
    "partial-refresh", "partial-stay", "add-limit", "remove-limit",
])
def test_bulk_adjustment_ui(scenario):
    template = (Path(__file__).resolve().parents[1] / 'templates' / 'admin_students.html').read_text()
    source = template[template.index('  let pendingHallPassAdjustment'):template.index('  function deletePendingStudent')]
    script = r'''
const assert = require('node:assert/strict');
const scenario = process.argv[1];
let prompts = 0, ids = 0, reloads = 0;
let selection = 12;
const requests = [];
const messages = [];
const crypto = { randomUUID: () => `request-${++ids}` };
const currentClassStudentTable = () => ({ querySelectorAll: () => [{dataset: {seatId: String(selection)}}] });
const document = { querySelector: () => ({getAttribute: () => 'csrf'}) };
const window = { AppCore: {prompt: async () => { prompts++; return '+2'; }} };
const announceStudentManagement = (message) => messages.push(message);
const location = {reload: () => reloads++};
let release;
let rejection = null;
let dismissResult;
window.AppCore.confirm = async (message) => {
  assert.ok(message.includes('Student A: no passes'));
  assert.ok(message.includes('Student B: no passes'));
  return new Promise(resolve => {dismissResult = resolve});
};
const fetch = async (url, options) => {
  requests.push(JSON.parse(options.body));
  if (rejection) return rejection;
  if (scenario === 'lost-response' && requests.length === 1) {
    await new Promise(resolve => {release = resolve});
    throw new Error('server committed; response lost');
  }
  return { status: 200, json: async () => ({status: 'success', message: 'Done'}) };
};
''' + source + r'''
(async () => {
  if (scenario === 'lost-response') {
  const first = bulkUpdateHallPass();
  await new Promise(resolve => setImmediate(resolve));
  await bulkUpdateHallPass();
  assert.equal(requests.length, 1, 'concurrent click must not duplicate the request');
  release();
  await first;
  selection = 99;
  await bulkUpdateHallPass();
  assert.deepEqual(requests[0], requests[1], 'retry must preserve the target, amount and key');
  assert.equal(prompts, 1, 'uncertain adjustment is retried, not replaced');
  assert.equal(reloads, 1);
  await bulkUpdateHallPass();
  assert.notEqual(requests[2].request_id, requests[1].request_id);
  assert.deepEqual(requests[2].student_ids, [99]);
  assert.equal(prompts, 2);
  return;
  }
  const responses = {
    csrf: {status: 400, json: async () => {throw new Error('HTML CSRF rejection');}},
    redirect: {status: 200, redirected: true, json: async () => {throw new Error('HTML login');}},
    'server-error': {status: 500, json: async () => ({status: 'error'})},
    unreadable: {status: 200, json: async () => {throw new Error('unreadable response');}},
  };
  if (responses[scenario]) {
    rejection = responses[scenario];
    await bulkUpdateHallPass();
    const originalPayload = requests.at(-1);
    rejection = null;
    await bulkUpdateHallPass();
    if (['csrf', 'redirect'].includes(scenario)) {
      assert.notEqual(requests.at(-1).request_id, originalPayload.request_id);
    } else {
      assert.deepEqual(requests.at(-1), originalPayload);
    }
    return;
  }
  if (scenario.startsWith('partial-')) {
  rejection = {status: 200, json: async () => ({
    status: 'success', message: 'One updated, two failed',
    errors: ['Student A: no passes', 'Student B: no passes'],
  })};
  const beforePartial = reloads;
  const partial = bulkUpdateHallPass();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(reloads, beforePartial, 'partial result must stay readable before refreshing');
  assert.ok(messages.at(-1).includes('Student B: no passes'));
  const refresh = scenario === 'partial-refresh';
  dismissResult(refresh);
  await partial;
  assert.equal(reloads, beforePartial + Number(refresh));
  return;
  }
  const beforeInvalid = requests.length;
  const input = scenario === 'add-limit' ? '+101' : '-101';
    window.AppCore.prompt = async () => input;
    await bulkUpdateHallPass();
    assert.equal(requests.length, beforeInvalid);
    assert.ok(messages.at(-1).includes('1 to 100'));
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    result = subprocess.run(['node', '-e', script, scenario], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
