/**
 * Analytics Class Selector
 * 
 * Handles the class selection dropdown for analytics pages.
 * When a user selects a different class, redirects to the same page
 * with the new join_code parameter.
 */
(function(window) {
  /**
   * Initialize the analytics class selector
   * Automatically finds the select element with id 'analyticsClassSelect'
   * and sets up the change event listener
   */
  function initAnalyticsClassSelector() {
    document.addEventListener('DOMContentLoaded', function() {
      const classSelect = document.getElementById('analyticsClassSelect');
      if (!classSelect) {
        return;
      }

      classSelect.addEventListener('change', function() {
        const baseUrl = classSelect.dataset.switchUrl;
        if (!baseUrl) {
          console.error('analyticsClassSelect missing data-switch-url attribute');
          return;
        }

        const targetUrl = new URL(baseUrl, window.location.origin);
        targetUrl.searchParams.set('join_code', classSelect.value);
        window.location.assign(targetUrl.toString());
      });
    });
  }

  // Auto-initialize when script loads
  initAnalyticsClassSelector();

  // Also expose as global function in case manual initialization is needed
  window.initAnalyticsClassSelector = initAnalyticsClassSelector;
})(window);
