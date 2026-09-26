/**
 * Scrollable Table Keyboard Access
 *
 * Bootstrap's `.table-responsive` wraps a table in a horizontally-scrolling
 * div when it overflows, but the wrapper itself is not in the tab order --
 * a keyboard-only user has no way to reach or scroll it (WCAG 2.1.1 /
 * axe's scrollable-region-focusable; INV-ARC-020).
 *
 * Applies `tabindex="0"` and a `role="region"` + `aria-label` to every
 * `.table-responsive` (Bootstrap always gives it `overflow-x: auto`, so it
 * is a potential scroll container independent of the current viewport), so
 * new tables are covered without per-template edits. The label prefers the
 * table's own `<caption>`, then a heading inside the same card, then a
 * generic fallback -- in that order, first non-empty wins.
 */

(function () {
    'use strict';

    function labelFor(wrapper) {
        var caption = wrapper.querySelector('table > caption');
        if (caption && caption.textContent.trim()) {
            return caption.textContent.trim();
        }
        var card = wrapper.closest('.card');
        var heading = card && card.querySelector('.card-header, h1, h2, h3, h4, h5, h6');
        if (heading && heading.textContent.trim()) {
            return heading.textContent.trim() + ' table';
        }
        return 'Scrollable data table';
    }

    function makeFocusable(wrapper) {
        // Bootstrap's .table-responsive always sets overflow-x: auto, so it
        // is a potential scroll container regardless of whether the current
        // viewport happens to need it right now -- axe's rule (and a user
        // who later resizes) cares about that CSS capability, not only
        // today's scrollWidth/clientWidth snapshot, so this makes every
        // instance focusable rather than only ones already overflowing.
        if (!wrapper.hasAttribute('tabindex')) {
            wrapper.setAttribute('tabindex', '0');
        }
        if (!wrapper.hasAttribute('role')) {
            wrapper.setAttribute('role', 'region');
        }
        if (!wrapper.hasAttribute('aria-label') && !wrapper.hasAttribute('aria-labelledby')) {
            wrapper.setAttribute('aria-label', labelFor(wrapper));
        }
    }

    function scanAll() {
        document.querySelectorAll('.table-responsive').forEach(makeFocusable);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scanAll);
    } else {
        scanAll();
    }
})();
