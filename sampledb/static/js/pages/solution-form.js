/**
 * Add/edit solution form (samples/solution_form.html): show the fields that
 * belong to the chosen solution type. An on-site solution is either written
 * here (title + markdown content, js/md-editor.js) or an existing draft article
 * (js/draft-selection.js picker); external solutions need a title and a URL.
 */
document.addEventListener('DOMContentLoaded', function() {
  'use strict';

  const typeSelect = document.getElementById('id_solution_type');
  if (!typeSelect) return;

  const show = window.sp.show;
  const byId = id => document.getElementById(id);
  const draftField = byId('draft-selection-field');
  const useDraftRadio = byId('choice-use-draft');
  const draftInput = byId('id_draft_article_id');

  function update() {
    const onsite = typeSelect.value === 'onsite';
    const useDraft = onsite && useDraftRadio.checked;
    show(byId('onsite-choice-field'), onsite);
    show(draftField, useDraft);
    show(byId('manual-fields'), !useDraft);
    show(byId('title-field'), !useDraft);
    show(byId('url-field'), !onsite);
    show(byId('content-field'), onsite && !useDraft);
    // A draft only counts while "Publish an existing draft" is chosen
    if (!useDraft && draftInput && draftInput.value) {
      window.sp.draftPicker.clear(draftField);
    }
  }

  typeSelect.addEventListener('change', update);
  byId('choice-write-new').addEventListener('change', update);
  useDraftRadio.addEventListener('change', update);
  update();
});
