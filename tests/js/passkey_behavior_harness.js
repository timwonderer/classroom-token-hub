// Behavior harness for static/js/passkey.js, driven by tests/dom/identity/test_passkey_lifecycle.py.
// Loads the script into a vm context with stubbed window/document/fetch and prints a JSON report.
const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync(process.argv[2], 'utf8');

function jsonResponse(status, body) {
    return { ok: status < 400, status, redirected: false, json: async () => body };
}

async function scenario(name, fetchImpl, { codes = ['123456'], deleteButtons = [] } = {}) {
    const handlers = {};
    const elements = {};
    const state = { hrefs: [], reloads: 0, fetches: [], timers: 0, shown: [], prompts: [] };
    const queue = [...codes];
    const element = (id) => elements[id] || (elements[id] = {
        id, value: '123456', dataset: {}, disabled: false, innerHTML: '',
        addEventListener: (event, fn) => { handlers[id] = fn; },
        focus() {}, replaceChildren() {}, className: '',
    });
    const location = {
        set href(v) { state.hrefs.push(v); },
        get href() { return ''; },
        reload() { state.reloads += 1; },
    };
    const window = {
        location,
        setTimeout: (fn) => { state.timers += 1; fn(); return 0; },
        AppCore: {
            buildAlertCard: (a) => { state.shown.push(a); return {}; },
            prompt: async (message, options) => {
                state.prompts.push({ message, title: options && options.title, inputmode: options && options.inputmode,
                                     autocomplete: options && options.autocomplete });
                if (options && options.title === 'Authenticator code') { return queue.length ? queue.shift() : null; }
                return 'My key';
            },
            confirm: async () => true,
        },
    };
    const document = {
        getElementById: (id) => element(id),
        querySelector: () => ({ getAttribute: () => 'csrf' }),
        querySelectorAll: (selector) => (selector === '.delete-passkey-btn' ? deleteButtons.map((b) => {
            const id = `delete-${b.id}`;
            const el = element(id);
            Object.assign(el.dataset, { credentialId: String(b.id), credentialName: b.name });
            return el;
        }) : []),
    };
    class Client {
        async register() { return { error: 'ceremony failed' }; }
    }
    const context = vm.createContext({
        window, document, console, setTimeout: window.setTimeout, JSON, Promise, Error, TypeError,
        Passwordless: { Client },
        fetch: async (url, init) => {
            const body = init && init.body ? JSON.parse(init.body) : null;
            state.fetches.push({ url, body });
            return fetchImpl(url, body);
        },
    });
    vm.runInContext(source, context);
    vm.runInContext(`setupPasskeyManager(${JSON.stringify({
        feedbackId: 'feedback', codeInputId: 'code', registerButtonId: 'register',
        resumeButtonId: 'resume', cancelButtonId: 'cancel', loginUrl: '/admin/login',
        startUrl: '/start', finishUrl: '/finish', cancelUrl: '/cancel', resumeUrl: '/resume', deleteUrl: '/passkey/0/delete',
    })})`, context);
    return { handlers, state, name };
}

const unreadable = { ok: true, status: 200, redirected: false, json: async () => { throw new Error('not json'); } };
const settle = () => new Promise((r) => setImmediate(r));

(async () => {
    const report = {};

    // A JSON 401 (session ended) shows the server's message and sends the user to sign in.
    let s = await scenario('401', async () => jsonResponse(401, { error: 'authentication_required', message: 'Your session ended. Sign in again.' }));
    await s.handlers.resume();
    await settle();
    report.unauthorized = { hrefs: s.state.hrefs, reloads: s.state.reloads, body: s.state.shown.map((a) => a.body) };

    // The ceremony fails: the error is shown, nothing is cancelled, and the page reloads to show the pending operation.
    s = await scenario('ceremony', async (url) => (url === '/start'
        ? jsonResponse(200, { token: 't', apiKey: 'k', binding: 'b'.repeat(64) }) : jsonResponse(200, { success: true })));
    await s.handlers.register();
    await settle();
    report.ceremonyFailure = {
        reloads: s.state.reloads, hrefs: s.state.hrefs, urls: s.state.fetches.map((f) => f.url),
        body: s.state.shown.map((a) => a.body),
    };

    // Registering asks for the code in a dialog, after the name; the code goes to start unchanged.
    s = await scenario('register-code', async (url) => (url === '/start'
        ? jsonResponse(200, { token: 't', apiKey: 'k', binding: 'b'.repeat(64) }) : jsonResponse(200, { success: true })));
    await s.handlers.register();
    await settle();
    report.registerCode = {
        prompts: s.state.prompts.map((p) => p.title),
        modal: s.state.prompts.filter((p) => p.title === 'Authenticator code').map((p) => [p.inputmode, p.autocomplete]),
        start: s.state.fetches.filter((f) => f.url === '/start').map((f) => f.body),
    };

    // A malformed code is refused in the dialog and asked for again: no request carries it.
    s = await scenario('bad-code', async () => jsonResponse(200, { success: true }), { codes: ['12345', 'abcdef', '1234567', '654321'] });
    await s.handlers.register();
    await settle();
    report.badCodes = {
        asked: s.state.prompts.filter((p) => p.title === 'Authenticator code').length,
        startBodies: s.state.fetches.filter((f) => f.url === '/start').map((f) => f.body),
    };

    // Cancelling the code dialog sends nothing.
    s = await scenario('cancel-code', async () => jsonResponse(200, { success: true }), { codes: [] });
    await s.handlers.register();
    await settle();
    report.cancelledCode = { fetches: s.state.fetches.length };

    // Delete asks for confirmation, then the code, and sends it with the delete request.
    s = await scenario('delete', async () => jsonResponse(200, { redirect: '/admin/login' }),
        { deleteButtons: [{ id: 7, name: 'Laptop' }], codes: ['246810'] });
    await s.handlers['delete-7']();
    await settle();
    report.deleteCode = {
        fetches: s.state.fetches.map((f) => [f.url, f.body]), hrefs: s.state.hrefs,
        prompts: s.state.prompts.map((p) => p.title),
    };

    // Cancelling the code dialog on delete sends nothing.
    s = await scenario('delete-cancel', async () => jsonResponse(200, {}), { deleteButtons: [{ id: 7, name: 'Laptop' }], codes: [] });
    await s.handlers['delete-7']();
    await settle();
    report.deleteCancelled = { fetches: s.state.fetches.length };

    console.log(JSON.stringify(report));
})().catch((e) => { console.error(e); process.exit(1); });
