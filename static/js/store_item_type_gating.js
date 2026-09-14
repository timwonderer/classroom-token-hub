// Store form interaction selects server-resolved contracts. It does not own
// the legality matrix; the Store form builder does.
(function () {
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

    function render() {
      const resolved = contract();
      if (!resolved) return;
      const legal = new Set(resolved.legal_fields);
      const fields = resolved.sections.flatMap(section => section.fields);
      form.querySelectorAll('[data-contract-field]').forEach(function (wrapper) {
        const field = fields.find(candidate => candidate.name === wrapper.dataset.contractField);
        const dependency = field && field.depends_on;
        const [dependencyName, dependencyValue] = (dependency || '').split(':');
        const dependencyField = dependencyName && form.querySelector(`[name="${dependencyName}"]`);
        const dependencyEnabled = !dependency || Boolean(dependencyField && (dependencyValue
          ? dependencyField.value === dependencyValue
          : dependencyField.checked));
        wrapper.hidden = !legal.has(wrapper.dataset.contractField) || !dependencyEnabled;
      });
      form.querySelectorAll('[data-contract-section]').forEach(function (section) {
        section.hidden = !section.querySelector('[data-contract-field]:not([hidden])');
      });
    }

    [type, rent, direct,
      form.querySelector('[name="bulk_discount_enabled"]'),
      form.querySelector('[name="is_bundle"]'),
      form.querySelector('[name="redemption_prompt_enabled"]')
      , form.querySelector('[name="collective_goal_type"]')
    ].filter(Boolean).forEach(function (field) {
      field.addEventListener('change', render);
    });
    render();
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
