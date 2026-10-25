// Hidden mobile navigation must also leave the tab order (INV-ARC-020).
document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('.hextra-sidebar-container');
  const syncSidebar = () => { sidebar.inert = sidebar.getAttribute('aria-hidden') === 'true'; };
  new MutationObserver(syncSidebar).observe(sidebar, { attributes: true, attributeFilter: ['aria-hidden'] });
  syncSidebar();

  // Keyboard users must be able to scroll wide contract tables.
  const tables = document.querySelectorAll('.content table');
  const syncTables = () => tables.forEach(table => {
    if (table.scrollWidth > table.clientWidth) table.tabIndex = 0;
    else table.removeAttribute('tabindex');
  });
  const observer = new ResizeObserver(syncTables);
  tables.forEach(table => observer.observe(table));
  syncTables();
});
