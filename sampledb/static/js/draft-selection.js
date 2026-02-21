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

/**
 * Open draft selection modal and fetch user's drafts
 * @param {string} modalId - The ID of the modal to open (default: 'draftSelectionModal')
 * @param {function} onSelectCallback - Function to call when a draft is selected, receives draft object
 */
function openDraftSelectionModal(modalId, onSelectCallback) {
  currentModalId = modalId || 'draftSelectionModal';
  currentDraftSelectionCallback = onSelectCallback;
  
  const modal = $('#' + currentModalId);
  modal.modal('show');
  
  // Show loading state
  $('#draftsLoading').show();
  $('#draftList').hide();
  $('#noDrafts').hide();
  
  // Fetch user's drafts via AJAX
  fetch('/ajax/get-user-drafts/')
    .then(response => response.json())
    .then(data => {
      $('#draftsLoading').hide();
      
      if (data.results && data.results.length > 0) {
        displayDraftsList(data.results);
      } else if (data.drafts && data.drafts.length > 0) {
        // Handle alternative response format
        displayDraftsList(data.drafts);
      } else {
        $('#draftList').hide();
        $('#noDrafts').show();
      }
    })
    .catch(error => {
      console.error('Error fetching drafts:', error);
      $('#draftsLoading').hide();
      $('#draftList').html('<div class="alert alert-danger">Error loading drafts. Please try again.</div>').show();
    });
}

/**
 * Display list of draft articles in modal
 */
function displayDraftsList(drafts) {
  const container = $('#draftList');
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
    
    const preview = currentDraftsData[draft.id].preview;
    
    html += `
      <div class="list-group-item list-group-item-action" style="cursor: pointer;" onclick="handleDraftSelection(event, ${draft.id})">
        <div class="d-flex justify-content-between align-items-start">
          <div class="flex-grow-1">
            <h6 class="mb-1"><i class="fas fa-file-alt text-primary"></i> ${escapeHtml(draft.title)}</h6>
            <p class="mb-1 small text-muted">${escapeHtml(preview)}</p>
            <small class="text-muted">
              <i class="fas fa-clock"></i> ${currentDraftsData[draft.id].updated_at}
              <span class="mx-2">|</span>
              <i class="fas fa-eye"></i> ${currentDraftsData[draft.id].view_count} views
            </small>
          </div>
          <button type="button" class="btn btn-sm btn-primary ml-3" style="min-width: 85px; white-space: nowrap;" onclick="event.stopPropagation(); handleDraftSelection(event, ${draft.id})">
            <i class="fas fa-check"></i> Select
          </button>
        </div>
      </div>
    `;
  });
  
  container.html(html).show();
  $('#noDrafts').hide();
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
    $('#' + currentModalId).modal('hide');
  } else {
    console.error('No draft selection callback defined');
  }
}

/**
 * Helper function to escape HTML in strings
 */
function escapeHtml(text) {
  if (!text) return '';
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
    '\\': '&#92;'
  };
  return text.toString().replace(/[&<>"'\\]/g, m => map[m]);
}
