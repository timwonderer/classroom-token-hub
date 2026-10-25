// Economic Engine Helper for the insurance policy form (SPEC-ECON-003 §4.4.8, §4.9).
// Reads the server-resolved figures embedded by templates/macros/insurance_premium_helper.html
// and reports the typed premium against them. Display only; nothing is submitted.
(function () {
  const box = document.getElementById('insurance-premium-helper');
  const dataEl = document.getElementById('insurance-premium-helper-data');
  if (!box || !dataEl) return;
  const data = JSON.parse(dataEl.textContent);
  const body = box.querySelector('[data-helper-body]');
  const form = box.closest('form');
  if (!form || !body) return;

  const TIERS = { '1': ['basic', 'Basic'], '2': ['mid', 'Mid'], '3': ['premium', 'Premium'] };
  const money = (n) => '$' + n.toFixed(2);
  const pct = (n) => (n * 100).toFixed(0) + '%';
  const field = (name) => form.elements.namedItem(name);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function render() {
    const frequency = (field('charge_frequency')?.value || 'WEEKLY').toUpperCase();
    const f = data.frequencies[frequency] || data.frequencies.WEEKLY;
    const per = frequency === 'MONTHLY' ? 'month' : 'week';
    const tierSel = field('tier_level');
    const tier = tierSel && !tierSel.disabled ? TIERS[tierSel.value] : null;
    const [tierKey, tierLabel] = tier || ['single', 'a single plan'];
    const suggested = f.recommended[tierKey];
    const premium = parseFloat(field('premium')?.value);
    const type = (field('insurance_type')?.value || '').toUpperCase();
    const multiple = parseFloat(field('payout_multiple')?.value);

    const lines = [];
    lines.push(`Suggested premium for ${esc(tierLabel)}, billed per ${per}: <strong>${money(suggested)}</strong> ` +
      `<span class="text-muted">(${pct(suggested / f.income)} of a ${per}'s income)</span>`);
    lines.push(`Suggested range in ${esc(data.mode)} mode: ${money(f.band_min)}–${money(f.band_max)} a ${per}.`);

    if (premium > 0) {
      const position = premium < f.band_min ? 'below' : premium > f.band_max ? 'above' : 'within';
      lines.push(`Your premium, <strong>${money(premium)}</strong>, is <strong>${position}</strong> that range. ` +
        `It takes ${pct(premium / f.income)} of a student's ${money(f.income)} income for the ${per}.`);
      if (data.rent) {
        const left = f.income - data.rent[frequency] - premium;
        lines.push(`After rent (${money(data.rent[frequency])}) and this premium, a student has <strong>${money(left)}</strong> left for the ${per}.`);
      }
      if (type === 'NON_MONETARY') {
        lines.push('This plan pays no money, so it has no payout figure. Check that the premium is affordable.');
      } else if (multiple > 0) {
        lines.push(`Protection: pays out at most <strong>${money(premium * multiple)}</strong> a ${per} (${money(premium)} × ${multiple}).`);
      }
    }
    lineBox.innerHTML = lines.map((l) => `<p class="small mb-1">${l}</p>`).join('');
    useButton.dataset.suggested = suggested.toFixed(2);
    useButton.textContent = `Use ${money(suggested)}`;
  }

  // The button lives outside the re-rendered lines: blurring the premium field fires
  // `change`, and a button rebuilt mid-click never receives the click.
  const lineBox = document.createElement('div');
  const useButton = document.createElement('button');
  useButton.type = 'button';
  useButton.className = 'btn btn-outline-primary btn-sm';
  useButton.addEventListener('click', () => {
    field('premium').value = useButton.dataset.suggested;
    render();
  });
  body.append(lineBox, useButton);

  form.addEventListener('input', render);
  form.addEventListener('change', render);
  render();
})();
