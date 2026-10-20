/**
 * Browser drafts (localStorage), known by name so that page scripts, markup and
 * views (samples/utils/drafts.py) agree on what to forget:
 *
 *   task-form                        the submit-task form, one key per field (sp.drafts.taskForm),
 *                                    plus the markdown editor that writes its reference solution
 *   markdown-editor                  the stand-alone markdown editor
 *   article:<id|new>                 the article editor
 *   onsite-solution:<task>[:<sol>]   the on-site solution editor
 *
 * - sp.drafts.load(name):          an editor draft {title, content, savedAt}, or null
 * - sp.drafts.save(name, values):  store an editor draft (savedAt is added)
 * - sp.drafts.clear(name, ...):    forget drafts
 * - <a data-clears-drafts="task-form" href="...">   forget drafts when clicked
 * - <meta name="sp-clear-drafts" content="...">     forget them when the page loads; a view puts
 *   names there with clear_drafts() once the server has saved what the draft held
 *
 * Load it right after js/utils.js, before page scripts restore drafts.
 */
window.sp.drafts = (function() {
  'use strict';

  // Submit-task form field -> localStorage key (static/js/submit-task-form.js)
  const TASK_FORM = Object.freeze({
    title: 'draft_reference_solution_title',
    content: 'draft_reference_solution',
    solutionType: 'draft_form_solution_type',
    sha256: 'draft_form_sha256',
    goal: 'draft_form_goal',
    description: 'draft_form_description',
    downloadLink: 'draft_form_download_link',
    imageId: 'draft_form_image_id',
    imageUrl: 'draft_form_image_url',
    uploadedImage: 'draft_form_uploaded_image',
    tags: 'draft_form_tags',
    tools: 'draft_form_tools',
    difficulty: 'draft_form_difficulty'
  });

  const MARKDOWN_EDITOR_KEY = 'markdown_editor_content';

  const NAMED = {
    'task-form': [...Object.values(TASK_FORM), MARKDOWN_EDITOR_KEY],
    'markdown-editor': [MARKDOWN_EDITOR_KEY]
  };

  const PATTERNS = [
    [/^article:(new|\d+)$/, m => `article_draft_${m[1]}`],
    [/^onsite-solution:(\d+)(?::(\d+))?$/, m => `onsite_solution_${m[1]}` + (m[2] ? `_${m[2]}` : '')]
  ];

  function keys(name) {
    if (NAMED[name]) return NAMED[name];
    for (const [pattern, key] of PATTERNS) {
      const match = pattern.exec(name);
      if (match) return [key(match)];
    }
    console.warn('Unknown draft name:', name);
    return [];
  }

  // localStorage can be unavailable (private mode, blocked storage): drafts are a convenience
  function storage() {
    try {
      return window.localStorage;
    } catch (e) {
      return null;
    }
  }

  function get(key) {
    const store = storage();
    return store ? store.getItem(key) : null;
  }

  function set(key, value) {
    const store = storage();
    if (!store) return;
    try {
      if (value) store.setItem(key, value);
      else store.removeItem(key);
    } catch (e) {
      console.warn('Could not save draft:', e);
    }
  }

  function clear(...names) {
    names.forEach(name => keys(name).forEach(key => set(key, null)));
  }

  function load(name) {
    const raw = get(keys(name)[0]);
    if (!raw) return null;
    let data;
    try {
      data = JSON.parse(raw);
    } catch (e) {
      data = null;
    }
    // Drafts from before this format: plain text, or {title, content[, timestamp]}
    if (!data || typeof data !== 'object') data = { content: raw };
    return {
      title: data.title || '',
      content: data.content || '',
      savedAt: data.savedAt || data.timestamp || null
    };
  }

  function save(name, { title = '', content = '' }) {
    set(keys(name)[0], JSON.stringify({ title, content, savedAt: Date.now() }));
  }

  function namesIn(value) {
    return (value || '').split(/\s+/).filter(Boolean);
  }

  // A page shown again from history carries an old <meta>: drafts written since must stay
  function isHistoryNavigation() {
    const entry = window.performance && performance.getEntriesByType
      ? performance.getEntriesByType('navigation')[0]
      : null;
    return Boolean(entry && entry.type === 'back_forward');
  }

  // Runs as soon as this script loads, before any page script restores a draft
  const meta = document.querySelector('meta[name="sp-clear-drafts"]');
  if (meta && !isHistoryNavigation()) {
    clear(...namesIn(meta.content));
  }

  document.addEventListener('click', function(e) {
    const trigger = e.target.closest('[data-clears-drafts]');
    if (trigger) clear(...namesIn(trigger.dataset.clearsDrafts));
  });

  return { taskForm: TASK_FORM, keys, get, set, clear, load, save };
})();
