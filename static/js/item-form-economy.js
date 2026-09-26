document.addEventListener('DOMContentLoaded', function() {
  const economyDataEl = document.getElementById('economy-data');
  if (!economyDataEl || typeof EconomyBalanceChecker === 'undefined') {
    return;
  }

  const expectedWeeklyHours = parseFloat(economyDataEl.dataset.expectedWeeklyHours);
  const economyChecker = new EconomyBalanceChecker({
    warningsContainer: '#economy-warnings',
    expectedWeeklyHours: isNaN(expectedWeeklyHours) ? undefined : expectedWeeklyHours,
  });

  economyChecker
    .analyzeEconomy()
    .then((analysis) => {
      // NOTE: the rent CWI renderer produces a rent-specific "Pricing
      // Recommendation" card and has no lawful place on the Store surface. Store
      // pricing guidance is expressed exclusively through the economic role
      // reference range below (SPEC-ECON-003 §4.7). Do NOT mount the rent panel here.
      const roleSelect = document.querySelector('[data-economic-role-select]');
      const roleRecommendation = document.getElementById('role-recommendation');
      const roleRangeText = document.getElementById('role-range-text');

      const roleRanges = analysis?.recommendations?.store_roles;

      if (roleSelect && roleRecommendation && roleRangeText && roleRanges) {
        function updateRoleRecommendation() {
          const range = roleRanges[roleSelect.value];

          if (range && typeof range.min === 'number' && typeof range.max === 'number') {
            roleRangeText.textContent = `$${range.min.toFixed(2)} - $${range.max.toFixed(2)}`;
            roleRecommendation.hidden = false;
          } else {
            roleRecommendation.hidden = true;
          }
        }

        roleSelect.addEventListener('change', updateRoleRecommendation);
        updateRoleRecommendation();
      }
    })
    .catch(() => {
      console.log('Payroll not configured yet, skipping CWI display');
    });
});
