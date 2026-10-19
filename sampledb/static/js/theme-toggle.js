// Light/dark toggle in the user menu. Its icon and label switch via
// .theme-when-light / .theme-when-dark (css/base.css), so no DOM syncing here.
(function() {
  'use strict';

  const toggle = document.getElementById('themeToggle');
  if (!toggle) return;

  toggle.addEventListener('click', function(e) {
    e.preventDefault();
    window.spTheme.set(window.spTheme.get() === 'dark' ? 'light' : 'dark');
  });
})();
