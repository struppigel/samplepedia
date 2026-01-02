/**
 * Draft Storage Management
 * Handles clearing localStorage for form drafts
 */

/**
 * Clear all draft-related localStorage items
 */
function clearFormDrafts() {
  const draftKeys = [
    'draft_reference_solution_title',
    'draft_reference_solution',
    'draft_form_solution_type',
    'draft_form_sha256',
    'draft_form_goal',
    'draft_form_description',
    'draft_form_download_link',
    'draft_form_image_id',
    'draft_form_image_url',
    'draft_form_tags',
    'draft_form_tools',
    'draft_form_difficulty'
  ];
  
  draftKeys.forEach(key => localStorage.removeItem(key));
}
