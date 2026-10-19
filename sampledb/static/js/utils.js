/**
 * Small shared helpers, available as window.sp
 * - sp.escapeHtml(value): escape text before putting it into innerHTML
 * - sp.getCookie(name):   read a cookie (e.g. csrftoken)
 */
window.sp = (function() {
  'use strict';

  const HTML_ESCAPES = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value).replace(/[&<>"']/g, c => HTML_ESCAPES[c]);
  }

  function getCookie(name) {
    const prefix = name + '=';
    const cookie = document.cookie
      .split(';')
      .map(c => c.trim())
      .find(c => c.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.substring(prefix.length)) : null;
  }

  return { escapeHtml, getCookie };
})();
