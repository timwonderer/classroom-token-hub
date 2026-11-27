// Behavior harness for static/js/passkey.js, driven by tests/dom/identity/test_passkey_lifecycle.py.
// Loads the script into a vm context with stubbed window/document/fetch and prints a JSON report.
const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync(process.argv[2], 'utf8');

function jsonResponse(status, body) {
    return { ok: status < 400, status, redirected: false, json: async () => body };
}

async function scenario(name, fetchImpl) {
    const handlers = {};
    const elements = {};
    const state = { hrefs: [], reloads: 0, fetches: [], timers: 0, shown: [] };
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
            prompt: async () => 'My key',
            confirm: async () => true,
        },
    };
    const document = {
        getElementById: (id) => element(id),
        querySelector: () => ({ getAttribute: () => 'csrf' }),
        querySelectorAll: () => [],
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
        startUrl: '/start', finishUrl: '/finish', cancelUrl: '/cancel', resumeUrl: '/resume',
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

    // The ceremony fails: the error is shown, nothing is cancelled and the page does not reload.
    s = await scenario('ceremony', async (url) => (url === '/start'
        ? jsonResponse(200, { token: 't', apiKey: 'k', binding: 'b'.repeat(64) }) : jsonResponse(200, { success: true })));
    await s.handlers.register();
    await settle();
    report.ceremonyFailure = {
        reloads: s.state.reloads, hrefs: s.state.hrefs, urls: s.state.fetches.map((f) => f.url),
        body: s.state.shown.map((a) => a.body),
    };

    console.log(JSON.stringify(report));
})().catch((e) => { console.error(e); process.exit(1); });
