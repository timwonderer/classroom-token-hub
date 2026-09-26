/**
 * EasyMDE Editor Labeling
 *
 * EasyMDE hides the original, properly-labeled `<textarea>` and replaces it
 * with a CodeMirror-managed editor whose own internal input proxy -- the
 * element that actually receives keystrokes and is what a screen reader
 * lands on -- has no accessible name of its own (axe's `label` rule,
 * critical impact; WCAG 4.1.2). Confirmed live across every current
 * EasyMDE call site in the app (admin_process_claim.html, admin_store.html,
 * admin_edit_item.html, student_submit_issue.html), each of which
 * initializes its own editor independently rather than through a shared
 * helper -- five instances of the identical defect. Fixing it once here
 * instead of per call site, and per instance, via a MutationObserver so it
 * also covers any editor constructed after this script's own load pass,
 * without depending on script-tag ordering relative to a page's own
 * `new EasyMDE(...)` calls (INV-ARC-020).
 *
 * EasyMDE always inserts its `.EasyMDEContainer` as the immediately
 * following sibling of the `<textarea>` it hides -- that original element
 * keeps its `id`, so the visible `<label for="...">` that already exists is
 * still findable; its text becomes the aria-label on the real input.
 */

(function () {
    'use strict';

    function labelEditor(container) {
        var input = container.querySelector('.CodeMirror textarea');
        if (!input || input.hasAttribute('aria-label') || input.hasAttribute('aria-labelledby')) {
            return;
        }
        var original = container.previousElementSibling;
        if (!original || !original.id) {
            return;
        }
        var label = document.querySelector('label[for="' + original.id + '"]');
        if (label && label.textContent.trim()) {
            input.setAttribute('aria-label', label.textContent.trim());
        }
    }

    function scanAll() {
        document.querySelectorAll('.EasyMDEContainer').forEach(labelEditor);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', scanAll);
    } else {
        scanAll();
    }

    new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType !== 1) {
                    return;
                }
                if (node.classList && node.classList.contains('EasyMDEContainer')) {
                    labelEditor(node);
                }
                var nested = node.querySelectorAll ? node.querySelectorAll('.EasyMDEContainer') : [];
                nested.forEach(labelEditor);
            });
        });
    }).observe(document.body, { childList: true, subtree: true });
})();
