/*
 * Username retention check (student account setup).
 *
 * The student proves they saved their username by typing it back after it
 * leaves the screen. This script only moves the interaction along; the server
 * decides whether the typed value matches, and the PIN/passphrase step refuses
 * any request that has not passed that check.
 *
 * Paste is blocked on the one input marked [data-retention-check-input] and
 * nowhere else. Typing, dictation, on-screen keyboards and IME composition
 * arrive as ordinary text input and are not affected. The "Can't type in this
 * box?" control turns paste back on for assistive technology that enters text
 * by pasting.
 */
(function () {
    'use strict';

    const BLOCKED_INPUT_TYPES = new Set([
        'insertFromPaste', 'insertFromPasteAsQuotation', 'insertFromDrop',
    ]);
    const PASTE_NOTICE = 'Pasting is turned off here. Type your username from the copy you saved.';

    function guardPaste(form) {
        const input = form.querySelector('[data-retention-check-input]');
        if (!input) {
            return;
        }
        const notice = form.querySelector('#retention-paste-notice');
        const accommodation = form.querySelector('[data-paste-accommodation]');
        const allowPaste = form.querySelector('[data-allow-paste]');
        let pasteAllowed = false;

        function refuse(event) {
            if (pasteAllowed) {
                return;
            }
            event.preventDefault();
            if (notice) {
                notice.textContent = PASTE_NOTICE;
            }
        }

        input.addEventListener('paste', refuse);
        input.addEventListener('drop', refuse);
        input.addEventListener('beforeinput', function (event) {
            if (BLOCKED_INPUT_TYPES.has(event.inputType)) {
                refuse(event);
            }
        });

        // Do not expose an unguarded ordinary input if the script fails to load.
        form.querySelector('[data-retention-controls]').disabled = false;

        if (allowPaste) {
            allowPaste.addEventListener('click', function () {
                pasteAllowed = true;
                if (accommodation) {
                    accommodation.value = '1';
                }
                allowPaste.disabled = true;
                allowPaste.textContent = 'Pasting is on for this check';
                input.setAttribute('aria-describedby', 'saved-username-hint retention-paste-notice');
                if (notice) {
                    notice.textContent = 'Pasting is on for this box.';
                }
                input.focus();
            });
        }
    }

    function setupCopy() {
        const button = document.querySelector('[data-copy-username]');
        const source = document.querySelector('[data-generated-username]');
        const status = document.getElementById('copy-status');
        if (!button || !source) {
            return;
        }
        button.addEventListener('click', function () {
            const text = source.textContent.trim();
            const announce = function (message) {
                if (status) {
                    status.textContent = message;
                }
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(
                    function () { announce('Username copied.'); },
                    function () { announce('Copy did not work. Select the username and copy it yourself.'); }
                );
            } else {
                const range = document.createRange();
                range.selectNodeContents(source);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                announce('Username selected. Copy it with your keyboard or menu.');
            }
        });
    }

    function setupModal() {
        const dialog = document.getElementById('retention-check-dialog');
        const opener = document.querySelector('[data-open-retention-check]');
        const source = document.querySelector('[data-generated-username]');
        if (!dialog || !opener || !source || typeof dialog.showModal !== 'function') {
            // Without <dialog> support the opener stays a link to the standalone page.
            return;
        }
        const form = dialog.querySelector('[data-retention-check-form]');
        const input = dialog.querySelector('[data-retention-check-input]');
        const result = document.getElementById('retention-check-result');
        const resultMessage = document.getElementById('retention-check-result-message');
        const showAgain = dialog.querySelector('[data-show-username-again]');
        const saveSection = document.querySelector('[data-username-save]');
        const verifiedNote = document.querySelector('[data-username-verified-note]');
        const setupFields = document.getElementById('setup-fields');
        const passInput = document.getElementById('passphrase');
        const pinInput = document.getElementById('pin');
        const submitButton = form.querySelector('button[type="submit"]');
        let verified = false;

        // Take the username out of the page while the check is open, so hiding
        // it never depends on how a browser paints the modal backdrop.
        const username = source.textContent.trim();

        function hideUsername() {
            source.textContent = '';
        }

        function showUsername() {
            source.textContent = username;
        }

        function closeAndReveal() {
            showUsername();
            if (dialog.open) {
                dialog.close();
            }
        }

        function showResult(message) {
            resultMessage.textContent = message;
            result.classList.remove('d-none');
            result.focus();
        }

        opener.addEventListener('click', function (event) {
            event.preventDefault();
            result.classList.add('d-none');
            input.value = '';
            input.setAttribute('aria-invalid', 'false');
            hideUsername();
            dialog.showModal();
            input.focus();
        });

        // Escape and "Show my username again" both simply reveal it again.
        dialog.addEventListener('close', function () {
            if (!verified) {
                showUsername();
            }
        });
        if (showAgain) {
            showAgain.addEventListener('click', function () {
                closeAndReveal();
                opener.focus();
            });
        }

        const csrfField = form.querySelector('[name="csrf_token"]');

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            submitButton.disabled = true;
            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    Accept: 'application/json',
                    'X-CSRFToken': csrfField ? csrfField.value : '',
                },
                credentials: 'same-origin',
            })
                .then(function (response) {
                    return response.json().then(function (body) {
                        return { ok: response.ok, body: body };
                    });
                })
                .then(function (reply) {
                    if (reply.body.redirect) {
                        window.location.assign(reply.body.redirect);
                        return;
                    }
                    if (reply.body.verified) {
                        verified = true;
                        dialog.close();
                        if (saveSection) {
                            saveSection.remove();
                        }
                        if (verifiedNote) {
                            verifiedNote.hidden = false;
                        }
                        setupFields.disabled = false;
                        setupFields.classList.remove('disabled-fields');
                        passInput.dispatchEvent(new Event('input'));
                        pinInput.focus();
                        return;
                    }
                    input.value = '';
                    input.setAttribute('aria-invalid', 'true');
                    showResult(reply.body.message || 'That did not work. Try again.');
                })
                .catch(function () {
                    showResult('Your answer could not be checked. Try again.');
                })
                .finally(function () {
                    submitButton.disabled = false;
                });
        });
    }

    document.querySelectorAll('[data-retention-check-form]').forEach(guardPaste);
    setupCopy();
    setupModal();
})();
