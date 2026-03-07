/**
 * Class Deletion Guardrails
 * 
 * Implements strict 2-step deletion UX:
 * 1. 30-second countdown before proceeding.
 * 2. Typed confirmation with copy/paste disabled.
 * 3. 10-second hold-to-confirm button.
 */

document.addEventListener('DOMContentLoaded', function () {
    // Shared state
    let countdownTimer = null;
    let holdTimer = null;
    let isHolding = false;
    let holdDuration = 10000; // 10 seconds
    let holdStart = 0;

    // Elements - Modal 1 (Warning & Countdown)
    const modal1 = document.getElementById('deleteClassModal');
    if (!modal1) return; // Exit if not on a page with deletion modals

    const bsModal1 = new bootstrap.Modal(modal1);
    const yesImSureBtn = document.getElementById('btn_yes_im_sure');
    const countdownText = document.getElementById('countdown_text');

    // Elements - Modal 2 (Type & Hold)
    const modal2 = document.getElementById('deleteClassConfirmModal');
    const bsModal2 = new bootstrap.Modal(modal2);
    const confirmInput = document.getElementById('delete_class_confirmation_input');
    const expectedConfirmText = document.getElementById('delete_class_expected_confirmation');
    const holdBtn = document.getElementById('btn_hold_to_confirm');
    const holdForm = document.getElementById('deleteClassForm');
    const holdProgressBlock = document.getElementById('hold_progress_block');
    const holdProgressBar = document.getElementById('hold_progress_bar');
    const holdInstructions = document.getElementById('hold_instructions');

    // Mute Return key to act as cancel
    function disableReturnKey(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            bsModal1.hide();
            bsModal2.hide();
        }
    }

    modal1.addEventListener('keydown', disableReturnKey);
    modal2.addEventListener('keydown', disableReturnKey);

    // Disable copy/paste on the confirmation input
    if (confirmInput) {
        confirmInput.addEventListener('paste', e => e.preventDefault());
        confirmInput.addEventListener('copy', e => e.preventDefault());
        confirmInput.addEventListener('cut', e => e.preventDefault());
        confirmInput.addEventListener('drop', e => e.preventDefault());

        // Input validation for the hold button
        confirmInput.addEventListener('input', function () {
            const expected = expectedConfirmText.textContent.trim();
            if (this.value === expected) {
                holdBtn.disabled = false;
                holdInstructions.style.display = 'block';
            } else {
                holdBtn.disabled = true;
                holdInstructions.style.display = 'none';
                resetHold();
            }
        });
    }

    // Modal 1 behavior
    modal1.addEventListener('show.bs.modal', function () {
        // Reset state
        yesImSureBtn.disabled = true;
        let timeLeft = 30; // 30 seconds

        countdownText.textContent = `(${timeLeft}s)`;

        if (countdownTimer) clearInterval(countdownTimer);

        countdownTimer = setInterval(() => {
            timeLeft--;
            if (timeLeft <= 0) {
                clearInterval(countdownTimer);
                countdownText.textContent = '';
                yesImSureBtn.disabled = false;
            } else {
                countdownText.textContent = `(${timeLeft}s)`;
            }
        }, 1000);
    });

    modal1.addEventListener('hide.bs.modal', function () {
        if (countdownTimer) clearInterval(countdownTimer);
    });

    yesImSureBtn.addEventListener('click', function () {
        bsModal1.hide();
        bsModal2.show();
    });

    // Modal 2 behavior
    modal2.addEventListener('show.bs.modal', function () {
        confirmInput.value = '';
        holdBtn.disabled = true;
        holdInstructions.style.display = 'none';
        resetHold();
    });

    function resetHold() {
        isHolding = false;
        holdProgressBlock.style.display = 'none';
        holdProgressBar.style.width = '0%';
        holdProgressBar.setAttribute('aria-valuenow', 0);
        if (holdTimer) cancelAnimationFrame(holdTimer);
    }

    function startHold(e) {
        if (holdBtn.disabled) return;

        // Only trigger on primary click (left mouse, or touch)
        if (e.type === 'mousedown' && e.button !== 0) return;

        e.preventDefault();
        isHolding = true;
        holdStart = performance.now();
        holdProgressBlock.style.display = 'block';

        function updateProgress(timestamp) {
            if (!isHolding) return;

            const elapsed = timestamp - holdStart;
            const progress = Math.min((elapsed / holdDuration) * 100, 100);

            holdProgressBar.style.width = `${progress}%`;
            holdProgressBar.setAttribute('aria-valuenow', progress);

            if (elapsed >= holdDuration) {
                isHolding = false;
                holdBtn.disabled = true;
                holdBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Deleting...';

                // Submit via requestSubmit to fire submit events and actually submit the form
                if (holdForm) {
                    if (typeof holdForm.requestSubmit === 'function') {
                        holdForm.requestSubmit();
                    } else {
                        holdForm.submit();
                    }
                }
            } else {
                holdTimer = requestAnimationFrame(updateProgress);
            }
        }

        holdTimer = requestAnimationFrame(updateProgress);
    }

    function endHold() {
        if (isHolding) {
            resetHold();
        }
    }

    // Bind hold events
    if (holdBtn) {
        holdBtn.addEventListener('mousedown', startHold);
        holdBtn.addEventListener('touchstart', startHold);

        document.addEventListener('mouseup', endHold);
        document.addEventListener('touchend', endHold);

        // Also cancel if mouse leaves the button
        holdBtn.addEventListener('mouseleave', endHold);
    }
});
