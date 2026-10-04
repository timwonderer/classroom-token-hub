/* FEAT-PROD-005/003: server-owned preview, explicit confirmation and durable retry key. */
document.addEventListener('DOMContentLoaded', () => {
  const element = document.getElementById('attendanceCorrectionModal');
  if (!element) return;
  const modal = new bootstrap.Modal(element);
  const reason = document.getElementById('attendanceCorrectionReasonCode');
  const confirm = document.getElementById('attendanceCorrectionConfirm');
  const error = document.getElementById('attendanceCorrectionError');
  const consequence = document.getElementById('attendanceCorrectionConsequence');
  let action, identity, key, trigger, submitting = false, generation = 0;
  const uncertain = new Map();
  const actionKey = () => JSON.stringify([action.post,action.opening,action.closing,reason.value]);
  function controls(disabled) { reason.disabled = disabled; document.getElementById('attendanceCorrectionRefresh').disabled = disabled; }
  const money = cents => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(cents / 100);
  async function preview() {
    if (submitting) return;
    const saved = uncertain.get(actionKey());
    if (saved) { identity = saved.identity; key = saved.key; consequence.textContent = saved.consequence; error.textContent = 'The previous response is uncertain. Confirm again to safely retry the same command.'; confirm.disabled = false; return; }
    const current = ++generation;
    identity = null; confirm.disabled = true; error.textContent = ''; consequence.textContent = 'Loading preview…';
    key = crypto.randomUUID();
    const url = new URL(action.preview, window.location.origin);
    if (action.opening) {
      url.searchParams.set('opening_event_id', action.opening); url.searchParams.set('closing_event_id', action.closing);
      url.searchParams.set('reason_code', reason.value);
    }
    try {
      const response = await AppCore.csrfFetch(url.toString()); const data = await response.json();
      if (current !== generation) return;
      if (!response.ok) { consequence.textContent = ''; error.textContent = data.message || 'Preview unavailable.'; return; }
      identity = data.expected_preview_identity;
      consequence.textContent = data.disposition === 'UNPAID' ? 'This interval will be removed from unpaid earnings.' :
        ['RECOVERED','ZERO_CENT'].includes(data.disposition) ? 'This interval will become ineligible. No additional money will be recovered.' :
        `${data.recovery_kind === 'EXACT_REVERSAL' ? 'This fully recovers the original payment of' : data.recovery_kind === 'RESIDUAL' ? 'This recovers the remaining payment credit of' : 'This correction will recover'} ${money(data.recovery_cents)}. Checking after: $${data.checking_after}. Savings after: $${data.savings_after}. Savings transfer: $${data.protection_transfer}.`;
      confirm.disabled = false;
    } catch (_) { if (current === generation) { consequence.textContent = ''; error.textContent = 'Preview could not load. Try again.'; } }
  }
  document.querySelectorAll('[data-attendance-correction]').forEach(button => button.addEventListener('click', () => {
    if (submitting) return;
    trigger = button;
    action = {preview:button.dataset.preview, post:button.dataset.post, opening:button.dataset.opening, closing:button.dataset.closing};
    reason.value = button.dataset.lastReason || 'INVALID_ATTENDANCE'; document.getElementById('attendanceCorrectionReason').hidden = !action.opening;
    document.getElementById('attendanceCorrectionTitle').textContent = action.opening ? 'Invalidate work interval' : 'Recover payroll payment';
    document.getElementById('attendanceCorrectionPermanent').textContent = action.opening ? 'Original attendance and payment records remain in the history. Invalidation is permanent.' : 'This recovers the remaining payment credit. The original payment stays in the history.';
    modal.show(); preview();
  }));
  reason.addEventListener('change', preview);
  document.getElementById('attendanceCorrectionRefresh').addEventListener('click', preview);
  confirm.addEventListener('click', async () => {
    if (!identity || submitting) return;
    submitting = true; controls(true);
    const originalAction = action, originalKey = actionKey();
    uncertain.set(originalKey, {identity,key,consequence:consequence.textContent});
    if (trigger) trigger.dataset.lastReason = reason.value;
    confirm.disabled = true; error.textContent = '';
    const payload = {idempotency_key:key,expected_preview_identity:identity};
    if (action.opening) Object.assign(payload,{opening_event_id:action.opening,closing_event_id:action.closing,reason_code:reason.value});
    try {
      const response = await AppCore.csrfFetch(originalAction.post,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      const data = await response.json();
      if (response.ok && data.status === 'accepted') { window.location.reload(); return; }
      uncertain.delete(originalKey);
      error.textContent = data.message || 'Correction was not accepted.';
      if (data.code === 'PREVIEW_CHANGED') identity = null;
    } catch (_) { error.textContent = 'The response could not be confirmed. Retry with the same command key.'; }
    submitting = false; controls(false);
    confirm.disabled = !identity;
  });
  element.addEventListener('hide.bs.modal', event => { if (submitting) event.preventDefault(); });
  element.addEventListener('shown.bs.modal', () => (action.opening ? reason : document.getElementById('attendanceCorrectionRefresh')).focus());
  element.addEventListener('hidden.bs.modal', () => { generation++; identity = null; if (trigger) trigger.focus(); });
});
