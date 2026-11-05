"""Execute the bulk UI command through lost-response and concurrent-click cases."""
from pathlib import Path
import subprocess


def test_bulk_retry_retains_payload_and_id():
    template = Path('templates/admin_students.html').read_text()
    source = template[template.index('  let pendingHallPassAdjustment'):template.index('  function deletePendingStudent')]
    script = r'''
const assert = require('node:assert/strict');
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
const fetch = async (url, options) => {
  requests.push(JSON.parse(options.body));
  if (requests.length === 1) {
    await new Promise(resolve => {release = resolve});
    throw new Error('server committed; response lost');
  }
  return { status: 200, json: async () => ({status: 'success', message: 'Done'}) };
};
''' + source + r'''
(async () => {
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
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
