(function () {
  'use strict';

  function hideDecorativeIcons(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (scope.matches && scope.matches('.material-symbols-outlined') && !scope.hasAttribute('aria-hidden')) {
      scope.setAttribute('aria-hidden', 'true');
    }
    scope.querySelectorAll('.material-symbols-outlined').forEach((icon) => {
      if (!icon.hasAttribute('aria-hidden')) icon.setAttribute('aria-hidden', 'true');
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    hideDecorativeIcons(document);
    const iconObserver = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) hideDecorativeIcons(node);
        });
      });
    });
    iconObserver.observe(document.body, { childList: true, subtree: true });
  });

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  function buildToastElement(message, variant) {
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${variant} border-0 mb-2`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');

    const flexDiv = document.createElement('div');
    flexDiv.className = 'd-flex';

    const toastBody = document.createElement('div');
    toastBody.className = 'toast-body';
    toastBody.textContent = String(message);

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close btn-close-white me-2 m-auto';
    closeBtn.setAttribute('data-bs-dismiss', 'toast');
    closeBtn.setAttribute('aria-label', 'Close');

    flexDiv.appendChild(toastBody);
    flexDiv.appendChild(closeBtn);
    toastEl.appendChild(flexDiv);
    return toastEl;
  }

  function resolveToastContainer() {
    let container = document.getElementById('flashToastContainer') || document.getElementById('toast-container');
    if (container) {
      return container;
    }

    container = document.createElement('div');
    container.id = 'flashToastContainer';
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    container.style.zIndex = '1100';
    document.body.appendChild(container);
    return container;
  }

  function mapToastType(type) {
    if (type === 'error') return 'danger';
    if (type === 'warning') return 'warning';
    if (type === 'danger') return 'danger';
    return 'success';
  }

  function toast(message, type = 'success', options = {}) {
    const container = resolveToastContainer();
    if (!container || typeof bootstrap === 'undefined' || !bootstrap.Toast) {
      let fallback = document.getElementById('app-live-feedback');
      if (!fallback) {
        fallback = document.createElement('div');
        fallback.id = 'app-live-feedback';
        fallback.tabIndex = -1;
        fallback.setAttribute('role', 'alert');
        fallback.setAttribute('aria-live', 'assertive');
        fallback.setAttribute('aria-atomic', 'true');
        document.body.appendChild(fallback);
      }
      const variant = mapToastType(type);
      fallback.className = '';
      fallback.replaceChildren(buildAlertCard({
        level: variant,
        title: variant === 'success' ? 'Done' : 'Action needed',
        icon: variant === 'success' ? 'check_circle' : (variant === 'warning' ? 'warning' : 'error'),
        body: String(message),
      }));
      fallback.focus();
      return;
    }

    const variant = mapToastType(type);
    const toastEl = buildToastElement(message, variant);
    container.appendChild(toastEl);

    const delay = typeof options.delay === 'number' ? options.delay : 3000;
    const instance = new bootstrap.Toast(toastEl, { delay });
    instance.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
  }

  // Alert-as-card builder. DOM twin of the `alert_card` macro in
  // templates/macros/cards.html — keep the two in lockstep.
  //
  // Text and elements arrive through separate parameters, and the split is
  // deliberate. `body` is text only: a string or number, or an array of them,
  // set through textContent and never parsed. `bodyNodes` is element content
  // the caller has already built. Callers routinely pass an exception message
  // or a server error string as `body` (showToast's no-Bootstrap fallback, the
  // passkey and roster surfaces), so keeping that value away from every DOM
  // insertion point is what makes "never parsed as HTML" checkable rather than
  // merely intended.
  //
  // Returns the card element; the caller inserts it.
  const ALERT_CARD_LEVELS = ['success', 'warning', 'danger', 'info'];
  let alertCardSeq = 0;

  function buildAlertCard({ level = 'info', title, icon, body, bodyNodes, role, id, dismissible = false, className = '' } = {}) {
    const resolvedLevel = ALERT_CARD_LEVELS.includes(level) ? level : 'info';
    const textClass = resolvedLevel === 'warning' ? 'text-dark' : 'text-white';

    const card = document.createElement('div');
    card.className = `card alert-card border-${resolvedLevel}${className ? ` ${className}` : ''}${dismissible ? ' fade show' : ''}`;
    const cardId = id || (dismissible ? `alert-card-js-${++alertCardSeq}` : '');
    if (cardId) card.id = cardId;
    if (role) card.setAttribute('role', role);

    const header = document.createElement('div');
    header.className = `card-header bg-${resolvedLevel} ${textClass} d-flex align-items-center`;
    if (icon) {
      const iconEl = document.createElement('span');
      iconEl.className = 'material-symbols-outlined me-2';
      iconEl.setAttribute('aria-hidden', 'true');
      iconEl.textContent = icon;
      header.appendChild(iconEl);
    }
    const heading = document.createElement('h3');
    heading.className = `h5 fw-bold mb-0 ${textClass}`;
    heading.textContent = String(title || '');
    header.appendChild(heading);
    if (dismissible) {
      const closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.className = `btn-close${resolvedLevel === 'warning' ? '' : ' btn-close-white'} ms-auto`;
      closeBtn.setAttribute('data-bs-dismiss', 'alert');
      closeBtn.setAttribute('data-bs-target', `#${cardId}`);
      closeBtn.setAttribute('aria-label', 'Close');
      header.appendChild(closeBtn);
    }

    const cardBody = document.createElement('div');
    cardBody.className = 'card-body';
    (Array.isArray(body) ? body : [body]).forEach((part) => {
      if (part === undefined || part === null || part === '') return;
      // Text only. Anything that is not a string or number is dropped rather
      // than coerced, so this branch has no path to a DOM insertion.
      if (typeof part !== 'string' && typeof part !== 'number') return;
      const p = document.createElement('p');
      p.className = 'mb-0';
      p.textContent = String(part);
      cardBody.appendChild(p);
    });

    (Array.isArray(bodyNodes) ? bodyNodes : [bodyNodes]).forEach((node) => {
      // Elements the caller built. Every in-repo caller composes these with
      // textContent or append(); none parses markup.
      if (node instanceof Node) cardBody.appendChild(node);
    });

    card.appendChild(header);
    card.appendChild(cardBody);
    return card;
  }

  async function csrfFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const token = getCsrfToken();
    if (token && !headers.has('X-CSRFToken')) {
      headers.set('X-CSRFToken', token);
    }

    return fetch(url, {
      ...options,
      headers,
    });
  }

  // Every Bootstrap modal: make everything outside it `inert` while it is open.
  // Chromium keeps content outside an aria-modal element in the accessibility
  // tree, so a screen reader's browse mode could leave the dialog, and Tab past
  // the last control reached the page behind it. Inert closes both. Live
  // regions stay live so a toast raised behind the modal is still announced.
  const INERT_EXEMPT = '#flashToastContainer, #toast-container, #app-live-feedback, [aria-live]';
  const inertedBy = new WeakMap();

  function isolateModal(modalEl) {
    const inerted = [];
    for (let node = modalEl; node && node !== document.body; node = node.parentElement) {
      const parent = node.parentElement;
      if (!parent) break;
      Array.from(parent.children).forEach((sibling) => {
        if (sibling === node || sibling.inert || sibling.matches(INERT_EXEMPT)) return;
        if (sibling.tagName === 'SCRIPT' || sibling.classList.contains('modal-backdrop')) return;
        sibling.inert = true;
        inerted.push(sibling);
      });
    }
    inertedBy.set(modalEl, inerted);
  }

  function releaseModal(modalEl) {
    (inertedBy.get(modalEl) || []).forEach((el) => { el.inert = false; });
    inertedBy.delete(modalEl);
  }

  // Released on `hide`, not `hidden`: focus goes back to the opener on
  // `hidden`, and an inert element cannot take it. A vetoed event changes nothing.
  document.addEventListener('show.bs.modal', (event) => {
    if (!event.defaultPrevented) isolateModal(event.target);
  });
  document.addEventListener('hide.bs.modal', (event) => {
    if (!event.defaultPrevented) releaseModal(event.target);
  });

  // In-app replacements for the browser's own confirm and prompt dialogs
  // (SPEC-DES-001 §X). Those are drawn by the browser, not the page: they are
  // off-system visually, and in-app browsers may not show them at all. On
  // 2026-10-20 the Google app's iOS browser returned an empty PIN from one
  // without displaying it, and a student's hall-pass request never left the page.
  //
  // `message` is text only (set through textContent, never parsed), a string
  // or an array of strings, one paragraph each. Resolves true/false for a
  // confirm, the entered string or null for a prompt; never rejects.
  let dialogSeq = 0;

  // The error is linked only once it applies: aria-describedby reads hidden
  // text too, so a static link would announce the error on first focus.
  function markInvalid(field, errorId) {
    field.classList.add('is-invalid');
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', errorId);
    field.focus();
  }

  function clearInvalid(field) {
    field.classList.remove('is-invalid');
    field.removeAttribute('aria-invalid');
    field.removeAttribute('aria-describedby');
  }

  function openDialog(message, { title = 'Please confirm', confirmLabel = 'OK', cancelLabel = 'Cancel', danger = false, input = null } = {}) {
    return new Promise((resolve) => {
      // Programmatic Bootstrap modals do not hand focus back, so a screen
      // reader would be left on <body>. Return it to whatever opened the dialog.
      const opener = document.activeElement;
      const id = `app-dialog-${++dialogSeq}`;
      const modalEl = document.createElement('div');
      modalEl.className = 'modal fade';
      modalEl.id = id;
      modalEl.tabIndex = -1;
      modalEl.setAttribute('aria-labelledby', `${id}-title`);
      modalEl.setAttribute('aria-describedby', `${id}-body`);

      const dialogEl = document.createElement('div');
      dialogEl.className = 'modal-dialog modal-dialog-centered';
      const content = document.createElement('form');
      content.className = 'modal-content';
      content.noValidate = true;

      const header = document.createElement('div');
      header.className = 'modal-header';
      const heading = document.createElement('h2');
      heading.className = 'modal-title h5';
      heading.id = `${id}-title`;
      heading.textContent = String(title);
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'btn-close';
      close.setAttribute('data-bs-dismiss', 'modal');
      close.setAttribute('aria-label', 'Close');
      header.append(heading, close);

      const body = document.createElement('div');
      body.className = 'modal-body';
      const text = document.createElement('div');
      text.id = `${id}-body`;
      (Array.isArray(message) ? message : [message]).forEach((part) => {
        if (part === undefined || part === null || part === '') return;
        const p = document.createElement('p');
        p.className = 'mb-2';
        p.textContent = String(part);
        text.appendChild(p);
      });
      body.appendChild(text);

      let field = null;
      if (input) {
        const label = document.createElement('label');
        label.className = 'form-label';
        label.htmlFor = `${id}-input`;
        label.textContent = String(input.label || 'Value');
        field = document.createElement('input');
        field.className = 'form-control';
        field.id = `${id}-input`;
        field.type = input.type || 'text';
        field.autocomplete = input.autocomplete || 'off';
        if (input.inputmode) field.inputMode = input.inputmode;
        if (input.placeholder) field.placeholder = input.placeholder;
        const error = document.createElement('div');
        error.className = 'invalid-feedback';
        error.id = `${id}-error`;
        error.textContent = String(input.requiredMessage || 'This field is required.');
        body.append(label, field, error);
      }

      const footer = document.createElement('div');
      footer.className = 'modal-footer';
      const cancel = document.createElement('button');
      cancel.type = 'button';
      cancel.className = 'btn btn-outline-secondary';
      cancel.setAttribute('data-bs-dismiss', 'modal');
      cancel.textContent = String(cancelLabel);
      const ok = document.createElement('button');
      ok.type = 'submit';
      ok.className = `btn ${danger ? 'btn-danger' : 'btn-primary'}`;
      ok.textContent = String(confirmLabel);
      footer.append(cancel, ok);

      content.append(header, body, footer);
      dialogEl.appendChild(content);
      modalEl.appendChild(dialogEl);
      document.body.appendChild(modalEl);

      let result = input ? null : false;
      content.addEventListener('submit', (event) => {
        event.preventDefault();
        if (field) {
          const value = field.value.trim();
          if (!value) {
            markInvalid(field, `${id}-error`);
            return;
          }
          result = value;
        } else {
          result = true;
        }
        instance.hide();
      });

      // A destructive action starts on Cancel, so Enter alone cannot confirm it.
      modalEl.addEventListener('shown.bs.modal', () => (field || (danger ? cancel : ok)).focus());
      modalEl.addEventListener('hidden.bs.modal', () => {
        instance.dispose();
        modalEl.remove();
        if (opener && opener !== document.body && opener.isConnected && typeof opener.focus === 'function') {
          opener.focus();
        }
        resolve(result);
      });
      const instance = new bootstrap.Modal(modalEl);
      instance.show();
    });
  }

  function confirmDialog(message, options = {}) {
    return openDialog(message, options);
  }

  function promptDialog(message, options = {}) {
    const { label, type, inputmode, autocomplete, placeholder, requiredMessage, ...rest } = options;
    return openDialog(message, {
      title: 'Enter a value', confirmLabel: 'Continue', ...rest,
      input: { label, type, inputmode, autocomplete, placeholder, requiredMessage },
    });
  }

  // Declarative confirm for plain form posts: `data-confirm="…"` on the form
  // or its submit button (optional data-confirm-title, -label, -danger, and
  // -value-from="<input id>" to fill a "{value}" placeholder). Capture phase,
  // so it runs before any other submit listener and cancelling leaves the
  // form untouched.
  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const submitter = event.submitter || null;
    const source = submitter && submitter.dataset.confirm ? submitter : (form.dataset.confirm ? form : null);
    if (!source) return;
    if (form.dataset.confirmed === '1') {
      delete form.dataset.confirmed;
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    let message = source.dataset.confirm;
    if (source.dataset.confirmValueFrom) {
      const valueEl = document.getElementById(source.dataset.confirmValueFrom);
      message = message.replace('{value}', valueEl ? valueEl.value : '');
    }
    const confirmed = await confirmDialog(message, {
      title: source.dataset.confirmTitle || 'Please confirm',
      confirmLabel: source.dataset.confirmLabel || 'OK',
      danger: 'confirmDanger' in source.dataset,
    });
    if (!confirmed) return;
    form.dataset.confirmed = '1';
    form.requestSubmit(submitter);
  }, true);

  window.AppCore = {
    getCsrfToken,
    csrfFetch,
    toast,
    buildAlertCard,
    confirm: confirmDialog,
    prompt: promptDialog,
    markInvalid,
    clearInvalid,
  };
  window.toast = toast;
})();
