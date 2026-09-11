/**
 * Timed destruction gate.
 *
 * Resolves to a proof-of-intent payload, or to null if the teacher backs out.
 * The payload carries no deletion target: the server resolves what is being
 * destroyed from the canonical context, never from anything this dialog sends.
 */
function showTimedDeleteGate(options) {
    return new Promise((resolve) => {
        const feedbackEl = document.getElementById('delete-gate-feedback');
        const modalEl = document.getElementById('timedDeleteGateModal');
        if (!modalEl || !window.bootstrap) {
            if (feedbackEl) {
                feedbackEl.textContent = 'The delete safety dialog is unavailable. Please refresh and try again.';
                feedbackEl.className = 'alert alert-danger';
                feedbackEl.classList.remove('visually-hidden');
                feedbackEl.focus();
            }
            resolve(null);
            return;
        }

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        const titleEl = document.getElementById('timedDeleteGateModalLabel');
        const warningEl = document.getElementById('timed-delete-gate-warning');
        const bulletsEl = document.getElementById('timed-delete-gate-bullets');
        const countdownText = document.getElementById('timed-delete-countdown-text');
        const countdownBar = document.getElementById('timed-delete-countdown-bar');
        const phraseInput = document.getElementById('timed-delete-phrase');
        const phraseHint = document.getElementById('timed-delete-phrase-hint');
        const holdBtn = document.getElementById('timed-delete-hold-btn');
        const holdStatus = document.getElementById('timed-delete-hold-status');
        const cancelBtn = modalEl.querySelector('[data-bs-dismiss="modal"]');

        const expectedPhrase = String(options.expectedPhrase || '').toUpperCase();
        const title = options.title || 'Confirm Deletion';
        const warning = options.warning || 'You are about to permanently delete this record.';
        const holdPrompt = options.holdPrompt || 'To proceed, hold this button for 10 seconds — press and hold with the pointer, or hold Space or Enter. Any interruption will reset the timer.';
        const countdownSeconds = 30;
        const holdMs = 10000;
        const holdSeconds = 10;

        let remaining = countdownSeconds;
        let countdownComplete = false;
        let resolved = false;
        let countdownTimer = null;
        let holdTimer = null;
        let holdTicker = null;
        let holdStartAt = null;
        let isHolding = false;
        let phraseUnlocked = false;

        titleEl.textContent = title;
        warningEl.textContent = warning;
        bulletsEl.replaceChildren(...(options.bullets || []).map(text => {
            const li = document.createElement('li');
            li.className = 'fw-bold text-danger mb-2';
            li.textContent = text;
            return li;
        }));
        phraseInput.value = '';
        phraseInput.disabled = true;
        phraseHint.textContent = `Required phrase: ${expectedPhrase}`;
        holdBtn.textContent = 'Hold to Confirm — click and hold, or hold Space or Enter';
        holdStatus.textContent = 'Hold button unlocks after countdown + exact phrase match.';

        const cleanup = () => {
            if (countdownTimer) clearInterval(countdownTimer);
            if (holdTimer) clearTimeout(holdTimer);
            if (holdTicker) clearInterval(holdTicker);
            phraseInput.removeEventListener('input', onPhraseInput);
            phraseInput.removeEventListener('paste', preventPasteLikeInput);
            phraseInput.removeEventListener('drop', preventPasteLikeInput);
            phraseInput.removeEventListener('beforeinput', onBeforePhraseInput);
            phraseInput.removeEventListener('keydown', onPhraseKeydown);
            holdBtn.removeEventListener('pointerdown', startHold);
            holdBtn.removeEventListener('pointerup', cancelHold);
            holdBtn.removeEventListener('pointerleave', cancelHold);
            holdBtn.removeEventListener('pointercancel', cancelHold);
            holdBtn.removeEventListener('keydown', onHoldKeydown);
            holdBtn.removeEventListener('keyup', onHoldKeyup);
            holdBtn.removeEventListener('blur', cancelHold);
            cancelBtn.removeEventListener('click', onCancelClick);
            modalEl.removeEventListener('hidden.bs.modal', onHidden);
        };

        const updateHoldAvailability = () => {
            const phraseOk = phraseInput.value.trim().toUpperCase() === expectedPhrase;
            holdBtn.disabled = !(countdownComplete && phraseOk);
        };

        const updateCountdownUi = () => {
            if (!countdownComplete) {
                countdownText.textContent = `Safety countdown: ${remaining}s remaining`;
                const pct = ((countdownSeconds - remaining) / countdownSeconds) * 100;
                countdownBar.style.width = `${pct}%`;
                countdownBar.parentElement.setAttribute('aria-valuenow', String(Math.round(pct)));
            } else {
                if (!phraseUnlocked) {
                    phraseUnlocked = true;
                    phraseInput.disabled = false;
                    setTimeout(() => phraseInput.focus(), 100);
                }
                countdownText.textContent = 'Countdown complete. Enter exact phrase and hold button for 10 seconds.';
                countdownBar.style.width = '100%';
                countdownBar.parentElement.setAttribute('aria-valuenow', '100');
            }
        };

        const resetHoldState = () => {
            if (holdTimer) clearTimeout(holdTimer);
            if (holdTicker) clearInterval(holdTicker);
            isHolding = false;
            holdBtn.textContent = holdPrompt;
            holdStatus.textContent = 'Hold must be continuous for 10 seconds.';
        };

        const preventPasteLikeInput = (event) => event.preventDefault();

        const onBeforePhraseInput = (event) => {
            if (event.inputType === 'insertFromPaste' || event.inputType === 'insertFromDrop') {
                event.preventDefault();
            }
        };

        const onPhraseKeydown = (event) => {
            const key = (event.key || '').toLowerCase();
            const isPasteShortcut = ((event.ctrlKey || event.metaKey) && key === 'v')
                || (event.shiftKey && key === 'insert');
            if (isPasteShortcut) {
                event.preventDefault();
            }
        };

        const onPhraseInput = () => updateHoldAvailability();

        const startHold = (event) => {
            if (holdBtn.disabled || isHolding) return;
            event.preventDefault();
            isHolding = true;
            holdStartAt = Date.now();
            holdStatus.textContent = 'Keep holding...';

            holdTicker = setInterval(() => {
                const elapsed = Date.now() - holdStartAt;
                const remainingMs = Math.max(0, holdMs - elapsed);
                holdBtn.textContent = `Keep Holding... ${(remainingMs / 1000).toFixed(1)}s`;
            }, 100);

            holdTimer = setTimeout(() => {
                if (resolved) return;
                resolved = true;
                cleanup();
                modal.hide();
                resolve({
                    gate_phrase: expectedPhrase,
                    gate_countdown_seconds: countdownSeconds,
                    gate_hold_seconds: holdSeconds,
                });
            }, holdMs);
        };

        // WCAG 2.1.1 Keyboard (Level A). The hold listened for pointer events only,
        // so a keyboard-only teacher could clear the countdown and type the phrase
        // and then had no way to finish the gate — no path to deleting their own
        // class or account at all. Space and Enter mirror press-and-hold: key
        // auto-repeat must not restart the timer, and losing focus counts as
        // releasing, so the hold stays genuinely continuous either way.
        const isHoldKey = (event) => event.key === ' ' || event.key === 'Spacebar' || event.key === 'Enter';

        const onHoldKeydown = (event) => {
            if (!isHoldKey(event)) return;
            if (event.repeat) {
                event.preventDefault();
                return;
            }
            startHold(event);
        };

        const onHoldKeyup = (event) => {
            if (!isHoldKey(event) || resolved) return;
            event.preventDefault();
            cancelHold();
        };

        const cancelHold = () => {
            if (!isHolding) return;
            resetHoldState();
            updateHoldAvailability();
        };

        const onCancelClick = () => {
            if (resolved) return;
            resolved = true;
            cleanup();
            resolve(null);
        };

        const onHidden = () => {
            if (resolved) return;
            resolved = true;
            cleanup();
            resolve(null);
        };

        phraseInput.addEventListener('input', onPhraseInput);
        phraseInput.addEventListener('paste', preventPasteLikeInput);
        phraseInput.addEventListener('drop', preventPasteLikeInput);
        phraseInput.addEventListener('beforeinput', onBeforePhraseInput);
        phraseInput.addEventListener('keydown', onPhraseKeydown);
        holdBtn.addEventListener('pointerdown', startHold);
        holdBtn.addEventListener('pointerup', cancelHold);
        holdBtn.addEventListener('pointerleave', cancelHold);
        holdBtn.addEventListener('pointercancel', cancelHold);
        holdBtn.addEventListener('keydown', onHoldKeydown);
        holdBtn.addEventListener('keyup', onHoldKeyup);
        holdBtn.addEventListener('blur', cancelHold);
        cancelBtn.addEventListener('click', onCancelClick);
        modalEl.addEventListener('hidden.bs.modal', onHidden);

        updateCountdownUi();
        updateHoldAvailability();

        countdownTimer = setInterval(() => {
            remaining -= 1;
            if (remaining <= 0) {
                remaining = 0;
                countdownComplete = true;
                clearInterval(countdownTimer);
                countdownTimer = null;
            }
            updateCountdownUi();
            updateHoldAvailability();
        }, 1000);

        modal.show();
    });
}
