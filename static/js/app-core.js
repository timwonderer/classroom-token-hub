(function () {
  'use strict';

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
      alert(String(message));
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
  };
  window.toast = toast;
})();
