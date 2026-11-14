/**
 * Picking one of the user's draft articles (samples/_draft_selection_modal.html).
 *
 * - openDraftSelectionModal(modalId, onSelect): list the user's drafts in that modal;
 *   onSelect receives {id, title, preview, updated_at, view_count} of the one clicked
 * - A picker that keeps the choice in a (hidden) form field:
 *     <div data-draft-picker="modal id" data-draft-input="id of the field">
 *       <button type="button" data-draft-picker-open>...</button>
 *       <div data-draft-picker-selected hidden>     shown while a draft is picked, with
 *         [data-draft-picker-title], [data-draft-picker-preview] and
 *         <button type="button" data-draft-picker-clear>
 *     </div>
 *   It fires a bubbling "draft-picker:change" event (event.detail.draft: the draft,
 *   or null once cleared); sp.draftPicker.clear(picker) clears it from page scripts.
 */
(function() {
  'use strict';

  let onSelect = null;
  let currentModal = null;
  let draftsById = {};

  function part(modal, name) {
    return modal.querySelector(`[data-drafts-${name}]`);
  }

  function openDraftSelectionModal(modalId, onSelectCallback) {
    const modal = document.getElementById(modalId || 'draftSelectionModal');
    const list = part(modal, 'list');
    const loading = part(modal, 'loading');
    const empty = part(modal, 'empty');
    currentModal = modal;
    onSelect = onSelectCallback;

    bootstrap.Modal.getOrCreateInstance(modal).show();
    window.sp.show(loading, true);
    window.sp.show(list, false);
    window.sp.show(empty, false);

    window.sp.fetchJSON(modal.dataset.draftsUrl)
      .then(data => {
        const drafts = data.results || data.drafts || [];
        window.sp.show(loading, false);
        if (drafts.length) {
          renderDrafts(list, drafts);
          window.sp.show(list, true);
        } else {
          window.sp.show(empty, true);
        }
      })
      .catch(error => {
        console.error('Error fetching drafts:', error);
        window.sp.show(loading, false);
        list.innerHTML = '<div class="alert alert-danger">Error loading drafts. Please try again.</div>';
        window.sp.show(list, true);
      });
  }

  function renderDrafts(list, drafts) {
    const escapeHtml = window.sp.escapeHtml;
    draftsById = {};
    list.innerHTML = drafts.map(draft => {
      const content = draft.content || '';
      const info = {
        id: draft.id,
        title: draft.title,
        preview: draft.content_preview
          || (content ? content.substring(0, 150) + (content.length > 150 ? '...' : '') : 'No content'),
        updated_at: draft.updated_at || 'Unknown date',
        view_count: draft.view_count || 0
      };
      draftsById[info.id] = info;
      return `
        <div class="list-group-item list-group-item-action cursor-pointer" data-draft-id="${escapeHtml(info.id)}">
          <div class="d-flex justify-content-between align-items-start">
            <div class="flex-grow-1">
              <h6 class="mb-1"><i class="fas fa-file-alt text-primary"></i> ${escapeHtml(info.title)}</h6>
              <p class="mb-1 small text-muted">${escapeHtml(info.preview)}</p>
              <small class="text-muted">
                <i class="fas fa-clock"></i> ${escapeHtml(info.updated_at)}
                <span class="mx-2">|</span>
                <i class="fas fa-eye"></i> ${escapeHtml(info.view_count)} views
              </small>
            </div>
            <button type="button" class="btn btn-sm btn-primary ms-3 text-nowrap">
              <i class="fas fa-check"></i> Select
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  // Clicking a draft (or its Select button) picks it
  document.addEventListener('click', function(e) {
    const item = e.target.closest('[data-drafts-list] [data-draft-id]');
    if (!item) return;
    e.preventDefault();
    const draft = draftsById[item.dataset.draftId];
    if (!draft || typeof onSelect !== 'function') return;
    onSelect(draft);
    bootstrap.Modal.getOrCreateInstance(currentModal).hide();
  });

  function setPicked(picker, draft) {
    const input = document.getElementById(picker.dataset.draftInput);
    const title = picker.querySelector('[data-draft-picker-title]');
    const preview = picker.querySelector('[data-draft-picker-preview]');
    if (input) input.value = draft ? draft.id : '';
    if (title) title.textContent = draft ? draft.title : '';
    if (preview) preview.textContent = draft ? draft.preview : '';
    window.sp.show(picker.querySelector('[data-draft-picker-selected]'), Boolean(draft));
    picker.dispatchEvent(new CustomEvent('draft-picker:change', { bubbles: true, detail: { draft } }));
  }

  document.addEventListener('click', function(e) {
    const open = e.target.closest('[data-draft-picker-open]');
    if (open) {
      const picker = open.closest('[data-draft-picker]');
      openDraftSelectionModal(picker.dataset.draftPicker, draft => setPicked(picker, draft));
      return;
    }
    const clear = e.target.closest('[data-draft-picker-clear]');
    if (clear) {
      setPicked(clear.closest('[data-draft-picker]'), null);
    }
  });

  window.openDraftSelectionModal = openDraftSelectionModal;
  if (window.sp) {
    window.sp.draftPicker = { clear: picker => setPicked(picker, null) };
  }
})();
