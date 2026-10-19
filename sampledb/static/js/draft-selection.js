/**
 * Shared Draft Article Selection Component
 * Handles selecting existing draft articles in both detail.html and submit_task.html
 *
 * Usage:
 *   1. Include the _draft_selection_modal.html partial in your template
 *   2. Call openDraftSelectionModal(modalId, onSelectCallback) to open modal
 *   3. Provide a callback function that receives the selected draft object
 */

// Store the callback function for the current modal instance
let currentDraftSelectionCallback = null;
let currentModalId = 'draftSelectionModal';
let currentDraftsData = {}; // Store draft data by ID to avoid inline JS issues

function setVisible(id, visible) {
  const el = document.getElementById(id);
  if (el) el.style.display = visible ? '' : 'none';
}

/**
 * Open draft selection modal and fetch user's drafts
 * @param {string} modalId - The ID of the modal to open (default: 'draftSelectionModal')
 * @param {function} onSelectCallback - Function to call when a draft is selected, receives draft object
 */
function openDraftSelectionModal(modalId, onSelectCallback) {
  currentModalId = modalId || 'draftSelectionModal';
  currentDraftSelectionCallback = onSelectCallback;

  bootstrap.Modal.getOrCreateInstance(document.getElementById(currentModalId)).show();

  // Show loading state
  setVisible('draftsLoading', true);
  setVisible('draftList', false);
  setVisible('noDrafts', false);

  // Fetch user's drafts via AJAX
  fetch('/ajax/get-user-drafts/')
    .then(response => response.json())
    .then(data => {
      setVisible('draftsLoading', false);

      if (data.results && data.results.length > 0) {
        displayDraftsList(data.results);
      } else if (data.drafts && data.drafts.length > 0) {
        // Handle alternative response format
        displayDraftsList(data.drafts);
      } else {
        setVisible('draftList', false);
        setVisible('noDrafts', true);
      }
    })
    .catch(error => {
      console.error('Error fetching drafts:', error);
      setVisible('draftsLoading', false);
      document.getElementById('draftList').innerHTML = '<div class="alert alert-danger">Error loading drafts. Please try again.</div>';
      setVisible('draftList', true);
    });
}

/**
 * Display list of draft articles in modal
 */
function displayDraftsList(drafts) {
  const container = document.getElementById('draftList');
  let html = '';

  // Clear and store draft data
  currentDraftsData = {};

  drafts.forEach(draft => {
    // Store draft data by ID
    currentDraftsData[draft.id] = {
      id: draft.id,
      title: draft.title,
      preview: draft.content_preview || (draft.content ? (draft.content.substring(0, 150) + (draft.content.length > 150 ? '...' : '')) : 'No content'),
      updated_at: draft.updated_at || 'Unknown date',
      view_count: draft.view_count || 0
    };

    const info = currentDraftsData[draft.id];
    const draftId = Number(draft.id);

    html += `
      <div class="list-group-item list-group-item-action cursor-pointer" onclick="handleDraftSelection(event, ${draftId})">
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
          <button type="button" class="btn btn-sm btn-primary ms-3 text-nowrap" style="min-width: 85px;" onclick="event.stopPropagation(); handleDraftSelection(event, ${draftId})">
            <i class="fas fa-check"></i> Select
          </button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
  setVisible('draftList', true);
  setVisible('noDrafts', false);
}

/**
 * Handle draft selection - calls the provided callback
 */
function handleDraftSelection(event, draftId) {
  event.preventDefault();
  event.stopPropagation();

  // Look up draft data
  const draftData = currentDraftsData[draftId];

  if (!draftData) {
    console.error('Draft data not found for ID:', draftId);
    return;
  }

  if (currentDraftSelectionCallback && typeof currentDraftSelectionCallback === 'function') {
    // Call the callback with draft data
    currentDraftSelectionCallback(draftData);

    // Close the modal
    bootstrap.Modal.getOrCreateInstance(document.getElementById(currentModalId)).hide();
  } else {
    console.error('No draft selection callback defined');
  }
}

/**
 * Helper function to escape HTML in strings
 */
function escapeHtml(text) {
  return window.sp.escapeHtml(text);
}
