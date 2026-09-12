/**
 * Offcanvas ARIA State Sync
 *
 * Keeps `aria-expanded` on an offcanvas trigger in step with the panel it
 * controls. Bootstrap manages the panel's own visibility and `aria-hidden`,
 * but it does not touch `aria-expanded` on the trigger — so without this a
 * screen-reader user is told the control is permanently collapsed, whatever
 * the panel is actually doing (WCAG 4.1.2; INV-ARC-020).
 *
 * Applies to every `[data-bs-toggle="offcanvas"]` trigger that names its panel
 * with `aria-controls`, so new offcanvas surfaces are covered without edits
 * here. Triggers are matched to panels by id, and several triggers may point
 * at one panel.
 *
 * The markup ships `aria-expanded="false"`, which is correct at load: an
 * offcanvas panel starts closed. This module only maintains it thereafter.
 */

(function () {
    'use strict';

    function triggersFor(panelId) {
        // Attribute selector rather than string concatenation into a query:
        // panel ids come from templates, but an id containing a quote or
        // bracket would otherwise break the selector.
        return Array.prototype.filter.call(
            document.querySelectorAll('[data-bs-toggle="offcanvas"][aria-controls]'),
            function (trigger) {
                return trigger.getAttribute('aria-controls') === panelId;
            }
        );
    }

    function setExpanded(panelId, isExpanded) {
        triggersFor(panelId).forEach(function (trigger) {
            trigger.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        });
    }

    function bind(panel) {
        if (!panel.id || panel.dataset.ariaSyncBound === 'true') {
            return;
        }
        panel.dataset.ariaSyncBound = 'true';

        // show/hide fire when the transition starts, which is when the state
        // has actually changed as far as assistive technology is concerned.
        panel.addEventListener('show.bs.offcanvas', function () {
            setExpanded(panel.id, true);
        });
        panel.addEventListener('hide.bs.offcanvas', function () {
            setExpanded(panel.id, false);
        });
    }

    function init() {
        document.querySelectorAll('.offcanvas').forEach(bind);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
