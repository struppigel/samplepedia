/**
 * Theme initialization - runs in <head> before the page renders.
 * The theme lives on <html data-bs-theme="light|dark">; all colors switch
 * through the tokens in css/tokens.css. Exposes window.spTheme.get()/set().
 */
(function() {
  'use strict';

  const KEY = 'samplepedia-theme';
  const LEGACY_KEY = 'adminlte-dark'; // "on"/"off", stored before the Bootstrap 5 refactor
  const root = document.documentElement;

  function readSavedTheme() {
    try {
      const theme = localStorage.getItem(KEY);
      if (theme === 'light' || theme === 'dark') {
        return theme;
      }
      const legacy = localStorage.getItem(LEGACY_KEY);
      if (legacy !== null) {
        const migrated = legacy === 'on' ? 'dark' : 'light';
        localStorage.setItem(KEY, migrated);
        localStorage.removeItem(LEGACY_KEY);
        return migrated;
      }
    } catch (e) {
      // localStorage unavailable (private mode, blocked storage)
    }
    return 'light';
  }

  function apply(theme) {
    root.setAttribute('data-bs-theme', theme);
    // highlight.js has separate light/dark stylesheets
    const hljsTheme = document.getElementById('hljsTheme');
    if (hljsTheme) {
      hljsTheme.href = theme === 'dark' ? hljsTheme.dataset.darkHref : hljsTheme.dataset.lightHref;
    }
  }

  window.spTheme = {
    get() {
      return root.getAttribute('data-bs-theme');
    },
    set(theme) {
      apply(theme);
      try {
        localStorage.setItem(KEY, theme);
      } catch (e) {
        // not persisted, still applied for this page
      }
    }
  };

  apply(readSavedTheme());
})();
