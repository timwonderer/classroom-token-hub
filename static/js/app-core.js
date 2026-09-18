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

  window.AppCore = {
    getCsrfToken,
    csrfFetch,
    toast,
    buildAlertCard,
  };
  window.toast = toast;
})();
