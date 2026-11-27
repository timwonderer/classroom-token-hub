/**
 * Passwordless.dev Frontend Integration
 * Official JavaScript SDK Implementation
 * https://docs.passwordless.dev/guide/frontend/javascript.html
 */

/**
 * POST a JSON body with the CSRF token. Resolves with the parsed body; rejects with an
 * Error carrying the server's coarse `code` so callers can tell a pending retirement
 * (`provider_unavailable`) from a refusal.
 */
async function postPasskeyJson(url, body) {
    let response;
    try {
        response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify(body || {})
        });
    } catch (e) {
        const error = new Error('The connection was lost. Reload the page to see where the change stands.');
        error.code = 'transport';
        throw error;
    }
    return readPasskeyResponse(response);
}

async function readPasskeyResponse(response) {
    let data = null;
    // A redirected or non-JSON answer (an expired sign-in lands on an HTML login page) is not
    // a result this page can act on: report it as unreadable, never as success.
    if (!response.redirected) {
        try { data = await response.json(); } catch (e) { data = null; }
    }
    if (data === null || typeof data !== 'object') {
        const error = new Error('The response could not be read. Reload the page to see where the change stands.');
        error.code = 'unreadable';
        throw error;
    }
    if (!response.ok) {
        // Prefer the human message (a session-ended answer carries a code in `error`).
        const error = new Error(data.message || data.error || 'The request failed.');
        error.status = response.status;
        error.code = data.code || (response.status === 401 ? 'authentication_required' : undefined);
        throw error;
    }
    return data;
}

/**
 * Register a new passkey.
 * Backend steps: start (fresh TOTP code in, registration token out) -> p.register(token) ->
 * finish. A failure is shown as an error and the page then reloads, so it renders the pending
 * operation with its Cancel control; the operation stays until it is finished, cancelled, or expires.
 */
// Failures after which the server's state is unknown or pending: reload to see it.
const KEEP_PENDING_CODES = new Set(['provider_unavailable', 'unreadable', 'transport']);

async function registerPasskey(config, authenticatorName, totpCode) {
    const startBody = { totp_code: totpCode };
    const { token, apiKey, binding } = await postPasskeyJson(config.startUrl, startBody);

    let result;
    try {
        const p = new Passwordless.Client({ apiKey });
        // The binding is stored as the credential's nickname, so the server can tell which
        // operation this registration was made for.
        result = await p.register(token, binding);
        if (!result || result.error) {
            throw new Error((result && result.error) || 'Registration failed');
        }
    } catch (error) {
        error.code = 'ceremony';
        throw error;
    }

    try {
        return await postPasskeyJson(config.finishUrl, {
            token: result.token,
            binding: binding,
            authenticatorName: authenticatorName
        });
    } catch (error) {
        error.pendingOperation = true;  // the operation is still pending: reload to show its Cancel control
        throw error;
    }
}

/**
 * Sign in with passkey
 * Official SDK Pattern: call p.signinWithAlias(username) → send token to backend
 */
async function signinWithPasskey(username, startUrl, finishUrl) {
    try {
        // Step 1: Get public API key from backend
        const startResponse = await fetch(startUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ username })
        });

        if (!startResponse.ok) {
            const error = await startResponse.json();
            throw new Error(error.error || 'Authentication failed');
        }

        const { apiKey } = await startResponse.json();

        // Step 2: Initialize Passwordless.dev client (Official SDK)
        const p = new Passwordless.Client({ apiKey });

        // Step 3: Perform WebAuthn authentication (Official SDK)
        const result = await p.signinWithAlias(username);

        if (!result || result.error) {
            throw new Error(result?.error || 'Authentication failed');
        }

        // Step 4: Send authentication token to backend for verification
        const finishResponse = await fetch(finishUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                token: result.token
            })
        });

        if (!finishResponse.ok) {
            const error = await finishResponse.json();
            throw new Error(error.error || 'Authentication failed');
        }

        const finishData = await finishResponse.json();
        return finishData;

    } catch (error) {
        console.error('Passkey signin error:', error);
        throw error;
    }
}

/**
 * Sign in with discoverable credential (no username required)
 * Official SDK Pattern: call p.signinWithDiscoverable()
 */
async function signinWithDiscoverable(finishUrl) {
    try {
        // For discoverable signin, we need the public API key
        // This should be provided in the page or fetched first
        const apiKey = window.PASSWORDLESS_PUBLIC_KEY;
        if (!apiKey) {
            throw new Error('Public API key not configured');
        }

        // Initialize Passwordless.dev client (Official SDK)
        const p = new Passwordless.Client({ apiKey });

        // Perform WebAuthn authentication with discoverable credential
        const result = await p.signinWithDiscoverable();

        if (!result || result.error) {
            throw new Error(result?.error || 'Authentication failed');
        }

        // Send authentication token to backend for verification
        const finishResponse = await fetch(finishUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                token: result.token
            })
        });

        if (!finishResponse.ok) {
            const error = await finishResponse.json();
            throw new Error(error.error || 'Authentication failed');
        }

        const finishData = await finishResponse.json();
        return finishData;

    } catch (error) {
        console.error('Passkey discoverable signin error:', error);
        throw error;
    }
}

/**
 * Get CSRF token from meta tag
 */
function getCsrfToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : '';
}

/**
 * Passkey settings page: register, delete, retry and cancel.
 * Every action but retry and cancel needs a fresh authenticator code from the input
 * named by config.codeInputId. A completed change ends the sign-in; the server answers
 * with the sign-in page to go to.
 */
function setupPasskeyManager(config) {
    const feedback = document.getElementById(config.feedbackId);
    const codeInput = document.getElementById(config.codeInputId);

    function show(level, title, message) {
        if (!feedback || !window.AppCore) { return; }
        feedback.replaceChildren(window.AppCore.buildAlertCard({
            level: level, title: title, icon: level === 'danger' ? 'error' : 'info', body: message,
        }));
        feedback.className = 'mb-4';
        feedback.focus();
    }

    function readCode() {
        const code = (codeInput && codeInput.value || '').trim();
        if (!/^[0-9]{6}$/.test(code)) {
            show('danger', 'Authenticator code needed', 'Enter the current 6-digit code from your authenticator app, then try again.');
            if (codeInput) { codeInput.focus(); }
            return null;
        }
        return code;
    }

    function finished(data) {
        // Only a server answer that names the sign-in page is a completed change.
        if (data && data.redirect) { window.location.href = data.redirect; return; }
        window.location.reload();
    }

    function failed(title, error, button, restoreHTML) {
        if (error instanceof TypeError && !error.code) { error.code = 'transport'; error.message = 'The connection was lost. Reload the page to see where the change stands.'; }
        const pending = KEEP_PENDING_CODES.has(error.code) || error.code === 'ceremony' || error.pendingOperation === true;
        if (error.status === 401 || error.code === 'authentication_required') {
            show('danger', 'Sign in again', error.message);
            if (config.loginUrl) { window.setTimeout(() => { window.location.href = config.loginUrl; }, 4000); }
            return;
        }
        show('danger', error.code === 'provider_unavailable' ? 'Change saved, not yet confirmed' : title, error.message);
        if (pending) {
            window.setTimeout(() => window.location.reload(), 4000);
            return;
        }
        if (button) { button.disabled = false; button.innerHTML = restoreHTML; }
    }

    async function enroll(button) {
        const code = readCode();
        if (!code) { return; }
        const authenticatorName = await window.AppCore.prompt(
            'Give this passkey a name you will recognise, such as "YubiKey" or "Touch ID".',
            { title: 'Name this passkey', label: 'Passkey name', confirmLabel: 'Continue', requiredMessage: 'Enter a name.' }
        );
        if (!authenticatorName) { return; }
        const originalHTML = button.innerHTML;
        try {
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Registering...';
            finished(await registerPasskey(config, authenticatorName, code));
        } catch (error) {
            failed('Could not register passkey', error, button, originalHTML);
        }
    }

    const registerButton = document.getElementById(config.registerButtonId);
    if (registerButton) {
        registerButton.addEventListener('click', () => enroll(registerButton));
    }

    document.querySelectorAll('.delete-passkey-btn').forEach(button => {
        button.addEventListener('click', async () => {
            const code = readCode();
            if (!code) { return; }
            const name = button.dataset.credentialName;
            if (!(await window.AppCore.confirm(`Delete "${name}"?`, { title: 'Delete passkey', confirmLabel: 'Delete', danger: true }))) {
                return;
            }
            const originalHTML = button.innerHTML;
            try {
                button.disabled = true;
                button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
                const response = await fetch(config.deleteUrl.replace('/0/', `/${button.dataset.credentialId}/`), {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ totp_code: code })
                });
                finished(await readPasskeyResponse(response));
            } catch (error) {
                failed('Could not delete passkey', error, button, originalHTML);
            }
        });
    });

    [[config.resumeButtonId, config.resumeUrl, 'Could not finish the change'],
     [config.cancelButtonId, config.cancelUrl, 'Could not cancel the change']].forEach(([id, url, title]) => {
        const button = id && document.getElementById(id);
        if (!button) { return; }
        button.addEventListener('click', async () => {
            const originalHTML = button.innerHTML;
            try {
                button.disabled = true;
                const body = {};
                if (button.dataset.binding) { body.binding = button.dataset.binding; }
                const data = await postPasskeyJson(url, body);
                if (data.redirect) { finished(data); } else { window.location.reload(); }
            } catch (error) {
                failed(title, error, button, originalHTML);
            }
        });
    });
}

/**
 * Authenticator replacement (FEAT-IDEN-106) on the passkey settings pages.
 * Steps: challenge -> passkey assertion answering it -> start (server stages the new seed and
 * returns its QR and key) -> the user confirms with a code from the new authenticator.
 * The old authenticator keeps working until confirm succeeds, which ends the sign-in.
 */
function setupTotpReplacement(config) {
    const byId = (id) => (id ? document.getElementById(id) : null);
    const feedback = byId(config.feedbackId);

    function show(title, message) {
        if (!feedback || !window.AppCore) { return; }
        feedback.replaceChildren(window.AppCore.buildAlertCard({ level: 'danger', title: title, icon: 'error', body: message }));
        feedback.className = 'mb-4';
        feedback.focus();
    }

    function failed(title, error) {
        if (error.status === 401 || error.code === 'authentication_required' || error.code === 'session_not_current') {
            show('Sign in again', error.message);
            if (config.loginUrl) { window.setTimeout(() => { window.location.href = config.loginUrl; }, 4000); }
            return;
        }
        show(title, error.message);
    }

    const replaceButton = byId(config.replaceButtonId);
    if (replaceButton) {
        replaceButton.addEventListener('click', async () => {
            const originalHTML = replaceButton.innerHTML;
            try {
                replaceButton.disabled = true;
                const { challenge, apiKey, alias } = await postPasskeyJson(config.challengeUrl, {});
                const p = new Passwordless.Client({ apiKey });
                const result = await p.signinWithAlias(alias);
                if (!result || result.error) { throw new Error((result && result.error) || 'Passkey check failed'); }
                const staged = await postPasskeyJson(config.startUrl, { token: result.token, challenge: challenge });
                byId(config.qrId).src = staged.qr;
                byId(config.secretId).textContent = staged.secret;
                const abandon = byId(config.abandonButtonId);
                if (abandon && staged.binding) { abandon.dataset.binding = staged.binding; }
                byId(config.setupId).hidden = false;
                const codeInput = byId(config.codeInputId);
                if (codeInput) { codeInput.focus(); }
            } catch (error) {
                replaceButton.disabled = false;
                replaceButton.innerHTML = originalHTML;
                failed('Could not start the replacement', error);
            }
        });
    }

    const confirmButton = byId(config.confirmButtonId);
    if (confirmButton) {
        confirmButton.addEventListener('click', async () => {
            const input = byId(config.codeInputId);
            const code = (input && input.value || '').trim();
            if (!/^[0-9]{6}$/.test(code)) {
                show('Authenticator code needed', 'Enter the 6-digit code from the new authenticator, then try again.');
                return;
            }
            try {
                confirmButton.disabled = true;
                const data = await postPasskeyJson(config.confirmUrl, { code: code });
                if (data && data.redirect) { window.location.href = data.redirect; } else { window.location.reload(); }
            } catch (error) {
                confirmButton.disabled = false;
                failed('Could not replace the authenticator', error);
            }
        });
    }

    [config.cancelButtonId, config.abandonButtonId].forEach((id) => {
        const button = byId(id);
        if (!button) { return; }
        button.addEventListener('click', async () => {
            try {
                button.disabled = true;
                const body = button.dataset.binding ? { binding: button.dataset.binding } : {};
                await postPasskeyJson(config.cancelUrl, body);
                window.location.reload();
            } catch (error) {
                button.disabled = false;
                failed('Could not cancel the replacement', error);
            }
        });
    });
}

/**
 * Setup passkey signin button
 */
function setupPasskeySignin(config) {
    const button = document.getElementById(config.buttonId);
    const usernameField = document.getElementById(config.usernameFieldId);

    if (!button || !usernameField) return;

    button.addEventListener('click', async function() {
        const username = usernameField.value.trim();

        if (!username) {
            window.AppCore?.toast('Please enter your username.', 'error');
            return;
        }

        const originalHTML = this.innerHTML;

        try {
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Authenticating...';

            const result = await signinWithPasskey(username, config.startUrl, config.finishUrl);

            if (result.success && result.redirect) {
                window.location.href = result.redirect;
            }

        } catch (error) {
            window.AppCore?.toast('Error: ' + error.message, 'error');
            this.disabled = false;
            this.innerHTML = originalHTML;
        }
    });
}
