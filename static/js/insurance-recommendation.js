/*
 * Insurance policy form — keep the Economic Engine recommendation panel in step
 * with the insurance type, tier group, tier, and charge frequency controls.
 *
 * Advisory only: this script never writes to a form field. Every figure and
 * sentence comes from the server-rendered blob (FEAT-CLASS-003
 * recommend_insurance_terms); the script only chooses what to show.
 *
 * Accessibility: the tables toggle with the `hidden` attribute, and only the
 * one-sentence summary is a live region. It is written only when its text
 * actually changes, so a screen reader hears each change once and nothing on
 * page load.
 */
(function () {
  'use strict';

  var panel = document.getElementById('insurance-reco');
  var dataEl = document.getElementById('insurance-reco-data');
  var typeSelect = document.getElementById('insurance_type');
  if (!panel || !dataEl || !typeSelect) return;

  var reco;
  try {
    reco = JSON.parse(dataEl.textContent || '{}');
  } catch (e) {
    return;
  }
  var summaries = (reco && reco.summaries) || {};

  var freqSelect = document.getElementById('charge_frequency');
  var tierToggle = document.getElementById('tiered_toggle');
  var rankSelect = document.getElementById('tier_level');
  var summary = document.getElementById('insurance-reco-summary');
  var TIER_BY_LEVEL = { '1': 'basic', '2': 'mid', '3': 'premium' };

  function currentState() {
    var tiered = !!(tierToggle && tierToggle.checked);
    var tier = tiered ? (TIER_BY_LEVEL[rankSelect ? rankSelect.value : ''] || null) : 'single';
    return {
      product: typeSelect.value,
      tiered: tiered,
      tier: tier,
      selection: tier || 'tiered',
      frequency: (freqSelect && freqSelect.value) || 'WEEKLY'
    };
  }

  function render() {
    var state = currentState();

    panel.querySelectorAll('[data-reco-product]').forEach(function (el) {
      var layout = el.getAttribute('data-reco-layout');
      var sameProduct = el.getAttribute('data-reco-product') === state.product;
      var sameLayout = !layout || (layout === 'tiered') === state.tiered;
      el.hidden = !(sameProduct && sameLayout);
    });

    panel.querySelectorAll('[data-reco-selected-marker]').forEach(function (el) {
      el.hidden = el.getAttribute('data-reco-selected-marker') !== state.tier;
    });

    panel.querySelectorAll('[data-reco-monthly-note]').forEach(function (el) {
      el.hidden = state.frequency !== 'MONTHLY';
    });

    if (summary) {
      var text = summaries[state.product + '|' + state.selection + '|' + state.frequency];
      if (typeof text === 'string' && summary.textContent !== text) {
        summary.textContent = text;
      }
    }
  }

  [typeSelect, freqSelect, tierToggle, rankSelect].forEach(function (el) {
    if (el) el.addEventListener('change', render);
  });
  render();
})();
