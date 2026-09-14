// Store form interaction selects server-resolved contracts. It does not own
// the legality matrix; the Store form builder does.
//
// A hidden control is also disabled, so the browser does not submit it: the
// server rejects a meaningful value in a field outside the contract, and a
// merely hidden control still posted its stale value. A control that becomes
// illegal because the teacher changed the item's type or acquisition is also
// cleared, so switching back does not silently restore a value they can no
// longer see. First paint only disables; persisted values were already lawful.
(function () {
  function clearValue(control) {
    if (control.type === 'checkbox' || control.type === 'radio') {
      control.checked = false;
    } else if (control.tagName === 'SELECT') {
      control.value = '';
    } else {
      control.value = '';
    }
  }

  function install(form, contracts) {
    const type = form.querySelector('[name="item_type"]');
    const rent = form.querySelector('[name="is_rent_linked"]');
    const direct = form.querySelector('[name="direct_purchase_allowed"]');
    if (!type) return;

    function contract() {
      const linked = Boolean(rent && rent.checked);
      const purchasable = !linked || Boolean(direct && direct.checked);
      return contracts[`${type.value}|${linked ? 1 : 0}|${purchasable ? 1 : 0}`];
    }

    function render(initial) {
      const resolved = contract();
      if (!resolved) return;
      const legal = new Set(resolved.legal_fields);
      const fields = resolved.sections.flatMap(section => section.fields);
      form.querySelectorAll('[data-contract-field]').forEach(function (wrapper) {
        const name = wrapper.dataset.contractField;
        const field = fields.find(candidate => candidate.name === name);
        const dependency = field && field.depends_on;
        const [dependencyName, dependencyValue] = (dependency || '').split(':');
        const dependencyField = dependencyName && form.querySelector(`[name="${dependencyName}"]`);
        const dependencyEnabled = !dependency || Boolean(dependencyField && !dependencyField.disabled && (dependencyValue
          ? dependencyField.value === dependencyValue
          : dependencyField.checked));
        const isLegal = legal.has(name);
        const shown = isLegal && dependencyEnabled;
        wrapper.hidden = !shown;
        wrapper.querySelectorAll('input, select, textarea').forEach(function (control) {
          if (control.type === 'hidden') return;
          control.disabled = !shown;
          if (!isLegal && !initial) clearValue(control);
        });
      });
      form.querySelectorAll('[data-contract-section]').forEach(function (section) {
        section.hidden = !section.querySelector('[data-contract-field]:not([hidden])');
      });
    }

    [type, rent, direct,
      form.querySelector('[name="bulk_discount_enabled"]'),
      form.querySelector('[name="is_bundle"]'),
      form.querySelector('[name="redemption_prompt_enabled"]'),
      form.querySelector('[name="collective_goal_type"]'),
    ].filter(Boolean).forEach(function (field) {
      field.addEventListener('change', function () { render(false); });
    });
    render(true);
  }

  document.addEventListener('DOMContentLoaded', function () {
    const node = document.getElementById('storeFormContracts');
    if (!node) return;
    const contracts = JSON.parse(node.textContent);
    document.querySelectorAll('form[data-store-item-form]').forEach(function (form) {
      install(form, contracts);
    });
  });
})();
