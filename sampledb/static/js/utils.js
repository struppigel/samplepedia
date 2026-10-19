/**
 * Shared helpers (window.sp) and behaviours declared in markup.
 *
 * Helpers:
 * - sp.escapeHtml(value):        escape text before putting it into innerHTML
 * - sp.getCookie(name):          read a cookie
 * - sp.csrfToken():              the CSRF token (from <meta name="csrf-token"> in base.html)
 * - sp.postForm(url, fields):    submit a POST form, as a link can't (CSRF token included)
 * - sp.fetchJSON(url, options):  fetch() JSON with the CSRF header; options: method, data (object)
 * - sp.show(element, visible):   show or hide an element through the hidden attribute
 *
 * Behaviours (no inline handlers needed):
 * - <a data-external-confirm href="...">    ask before following a user-submitted link
 * - <form data-confirm="Really?">           ask before submitting
 * - <select data-autosubmit>, <input ...>   submit the surrounding form when changed
 * - <button data-post-url="..." [data-confirm="..."] [data-post-next="..."]>
 *                                           POST to the URL (optionally after a confirm)
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

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : getCookie('csrftoken');
  }

  function postForm(url, fields = {}) {
    const form = document.createElement('form');
    form.method = 'post';
    form.action = url;
    form.hidden = true;
    const values = Object.assign({ csrfmiddlewaretoken: csrfToken() }, fields);
    Object.entries(values).forEach(([name, value]) => {
      const input = document.createElement('input');
      input.type = 'hidden';
      input.name = name;
      input.value = value;
      form.appendChild(input);
    });
    document.body.appendChild(form);
    form.submit();
  }

  async function fetchJSON(url, { method = 'GET', data } = {}) {
    const options = {
      method,
      headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    };
    if (data !== undefined) {
      options.body = new URLSearchParams(data);
    }
    const response = await fetch(url, options);
    return response.json();
  }

  function show(element, visible = true) {
    if (element) element.hidden = !visible;
  }

  return { escapeHtml, getCookie, csrfToken, postForm, fetchJSON, show };
})();

// Confirm before following a user-submitted external link.
// The URL is read from the DOM, never interpolated into JS by the template.
document.addEventListener('click', function(e) {
  const link = e.target.closest('a[data-external-confirm]');
  if (link && !confirm(`You are about to visit an external website:\n\n${link.href}\n\nDo you want to continue?`)) {
    e.preventDefault();
  }
});

// POST buttons: <button data-post-url="/x/delete/" data-confirm="Delete?">
document.addEventListener('click', function(e) {
  const button = e.target.closest('[data-post-url]');
  if (!button) return;
  e.preventDefault();
  if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
  const fields = button.dataset.postNext ? { next: button.dataset.postNext } : {};
  window.sp.postForm(button.dataset.postUrl, fields);
});

// Ask before submitting destructive forms: <form data-confirm="Really delete?">
document.addEventListener('submit', function(e) {
  const form = e.target;
  if (form.dataset.confirm && !confirm(form.dataset.confirm)) {
    e.preventDefault();
  }
});

// Filters that apply immediately: <select data-autosubmit>
document.addEventListener('change', function(e) {
  if (e.target.matches('[data-autosubmit]') && e.target.form) {
    e.target.form.requestSubmit();
  }
});
