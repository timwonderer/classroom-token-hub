(function() {
  function renderBadgeLikeSelect(selectId, kind) {
    const selectEl = document.getElementById(selectId);
    if (!selectEl || selectEl.dataset.badgeRendered === 'true') return;

    const marketingStyles = {
      best_value: 'success',
      most_popular: 'primary',
      recommended: 'info',
      premium: 'warning text-dark',
      limited_time: 'danger',
      new: 'secondary',
      fan_favorite: 'primary',
      yolo: 'warning text-dark',
      trust_me: 'secondary',
      definitely_not_scam: 'danger',
      parents_approved: 'success',
      as_seen_on_tv: 'info',
      industry_leading: 'dark',
      chaos_insurance: 'danger',
      responsible_choice: 'success',
      your_friend_has_it: 'primary'
    };
    const tierStyles = {
      primary: 'primary',
      success: 'success',
      info: 'info',
      warning: 'warning text-dark',
      danger: 'danger',
      secondary: 'secondary',
      dark: 'dark'
    };

    const renderOption = (value, text) => {
      const label = document.createElement('span');
      if (!value) {
        label.className = 'text-muted';
        label.textContent = text;
        return label;
      }
      const style = kind === 'marketing' ? (marketingStyles[value] || 'secondary') : (tierStyles[value] || 'secondary');
      label.className = `badge bg-${style}`;
      label.textContent = text;
      return label;
    };

    selectEl.classList.add('d-none');
    const wrapper = document.createElement('div');
    wrapper.className = 'dropdown w-100 mt-1';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-outline-secondary dropdown-toggle w-100 text-start d-flex justify-content-between align-items-center';
    button.setAttribute('data-bs-toggle', 'dropdown');
    button.setAttribute('aria-expanded', 'false');

    const menu = document.createElement('ul');
    menu.className = 'dropdown-menu w-100';

    wrapper.appendChild(button);
    wrapper.appendChild(menu);
    selectEl.insertAdjacentElement('afterend', wrapper);

    const updateButton = () => {
      const selected = selectEl.options[selectEl.selectedIndex];
      button.replaceChildren(renderOption(selected ? selected.value : '', selected ? selected.text : 'Select'));
    };

    Array.from(selectEl.options).forEach(opt => {
      const li = document.createElement('li');
      const optionButton = document.createElement('button');
      optionButton.type = 'button';
      optionButton.className = 'dropdown-item';
      optionButton.appendChild(renderOption(opt.value, opt.text));
      optionButton.addEventListener('click', () => {
        selectEl.value = opt.value;
        selectEl.dispatchEvent(new Event('change', { bubbles: true }));
        updateButton();
      });
      li.appendChild(optionButton);
      menu.appendChild(li);
    });

    selectEl.addEventListener('change', updateButton);
    updateButton();
    selectEl.dataset.badgeRendered = 'true';
  }

  window.renderBadgeLikeSelect = renderBadgeLikeSelect;
})();
