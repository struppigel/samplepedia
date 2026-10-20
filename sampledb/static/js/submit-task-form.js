/**
 * Submit/edit task form (samples/submit_task.html)
 * - sample image: upload one (size checked here) or pick one from the gallery modal
 * - the SHA256 is filled in from the download link
 * - reference solution: a URL or on-site content depending on its type, or an
 *   existing draft article (picker from js/draft-selection.js)
 * - the "task-form" draft (js/drafts.js) of a new task: saved when opening the
 *   markdown editor, on image upload and on submit, restored into a fresh form
 *   (#form-data-attrs data-restore-draft); the server has it cleared once the
 *   task is saved
 * The description's Write/Preview tabs are js/md-editor.js; the Delete Task
 * button submits #deleteForm, which asks first (data-confirm, js/utils.js).
 */
document.addEventListener('DOMContentLoaded', function() {
  'use strict';

  const attrs = document.getElementById('form-data-attrs');
  if (!attrs) return;

  const byId = id => document.getElementById(id);
  const show = (id, visible) => window.sp.show(byId(id), visible);
  const drafts = window.sp.drafts;
  const keys = drafts.taskForm;
  const isNewTask = attrs.dataset.isEdit !== 'true';

  // Draft field (js/drafts.js taskForm) -> id of the form element it keeps
  const DRAFT_FIELDS = {
    title: 'id_reference_solution_title',
    content: 'reference_solution_content',
    solutionType: 'id_reference_solution_type',
    sha256: 'id_sha256',
    goal: 'id_goal',
    description: 'id_description',
    downloadLink: 'id_download_link',
    tags: 'id_tags',
    tools: 'id_tools',
    difficulty: 'id_difficulty'
  };

  // ------------------------------------------------------------------
  // Sample image
  // ------------------------------------------------------------------
  function showImageChoices(visible) {
    show('upload-section', visible);
    show('gallery-section', visible);
  }

  function markGalleryCard(imageId) {
    document.querySelectorAll('.image-select-card').forEach(card => {
      card.classList.toggle('selected', card.dataset.imageId === imageId);
    });
  }

  function showGalleryImage(url) {
    byId('preview_img').src = url;
    show('selected_image_preview', true);
    show('image_preview_area', true);
    showImageChoices(false);
  }

  function showUploadedImage(dataUrl) {
    byId('upload_preview_img').src = dataUrl;
    show('upload_image_preview', true);
    show('image_preview_area', true);
    showImageChoices(false);
  }

  function selectGalleryImage(card) {
    byId('selected_image').value = card.dataset.imageId;
    markGalleryCard(card.dataset.imageId);
    showGalleryImage(card.dataset.imageUrl);
    bootstrap.Modal.getOrCreateInstance(byId('imageGalleryModal')).hide();
  }

  function removeImage(kind) {
    if (kind === 'upload') {
      byId('id_image_upload').value = '';
      show('upload_image_preview', false);
      if (isNewTask) drafts.set(keys.uploadedImage, null);
    } else {
      byId('selected_image').value = '';
      show('selected_image_preview', false);
      markGalleryCard(null);
    }
    show('image_preview_area', false);
    byId('clear_image_flag').value = 'true';
    showImageChoices(true);
  }

  function checkUploadedImage(input) {
    const file = input.files[0];
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.addEventListener('load', () => {
      const img = new Image();
      img.addEventListener('load', () => {
        const { width, height } = img;
        if (width < 125 || height < 125) {
          alert(`Image is too small (${width}x${height}px). Minimum size is 125x125 pixels.`);
          input.value = '';
          return;
        }
        if (width > 1024 || height > 1024) {
          alert(`Image is too large (${width}x${height}px). Maximum size is 1024x1024 pixels.`);
          input.value = '';
          return;
        }
        showUploadedImage(reader.result);
        // An upload replaces a gallery choice
        byId('selected_image').value = '';
        if (isNewTask) {
          drafts.set(keys.imageId, null);
          drafts.set(keys.imageUrl, null);
          drafts.set(keys.uploadedImage, reader.result);
        }
        if (width !== height) {
          const cropSize = Math.min(width, height);
          alert(`Image will be center-cropped to ${cropSize}x${cropSize}px to maintain 1:1 aspect ratio.`);
        }
      });
      img.src = reader.result;
    });
    reader.readAsDataURL(file);
  }

  function showCurrentImage() {
    const { currentImageId, currentImageUrl } = attrs.dataset;
    if (currentImageId) {
      byId('selected_image').value = currentImageId;
      const card = document.querySelector(`.image-select-card[data-image-id="${CSS.escape(currentImageId)}"]`);
      if (card) {
        markGalleryCard(currentImageId);
        showGalleryImage(card.dataset.imageUrl);
      }
      showImageChoices(false);
    } else if (currentImageUrl) {
      showGalleryImage(currentImageUrl);
    }
  }

  // A data: URL back into a File, for the file input (fetch() would need connect-src data:)
  function dataUrlToFile(dataUrl, name) {
    const [header, base64] = dataUrl.split(',');
    const type = (header.match(/^data:([^;,]+)/) || [])[1] || 'image/png';
    const bytes = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
    return new File([bytes], name, { type });
  }

  // ------------------------------------------------------------------
  // SHA256 from the download link
  // ------------------------------------------------------------------
  function fillSha256() {
    const url = byId('id_download_link').value.trim();
    const sha256Input = byId('id_sha256');
    // MalShare: ?hash=<sha256>; MalwareBazaar: /sample/<sha256> or /download/<sha256>
    const match = url.match(/[?&]hash=([a-fA-F0-9]{64})/) || url.match(/\/(?:sample|download)\/([a-fA-F0-9]{64})/);
    if (match) {
      sha256Input.value = match[1].toLowerCase();
      sha256Input.classList.remove('is-invalid');
      sha256Input.classList.add('is-valid');
    } else if (url) {
      sha256Input.value = '';
      sha256Input.classList.remove('is-valid');
    }
  }

  // ------------------------------------------------------------------
  // Reference solution (new tasks only)
  // ------------------------------------------------------------------
  let draftPicked = false;

  function updateReferenceFields() {
    const typeSelect = byId('id_reference_solution_type');
    if (!typeSelect) return;
    const onsite = typeSelect.value === 'onsite';
    show('ref-title-group', !draftPicked);
    show('ref-type-group', !draftPicked);
    show('reference-url-field', !draftPicked && !onsite);
    show('reference-content-field', !draftPicked && onsite);
  }

  // ------------------------------------------------------------------
  // The task-form draft
  // ------------------------------------------------------------------
  function saveDraft() {
    Object.entries(DRAFT_FIELDS).forEach(([field, id]) => {
      const element = byId(id);
      if (element) drafts.set(keys[field], element.value);
    });
    const imageId = byId('selected_image').value;
    drafts.set(keys.imageId, imageId);
    drafts.set(keys.imageUrl, imageId ? byId('preview_img').src : null);
  }

  function restoreDraft() {
    const saved = {};
    Object.entries(keys).forEach(([field, key]) => {
      const value = drafts.get(key);
      if (value) saved[field] = value;
    });
    const typeSelect = byId('id_reference_solution_type');
    const content = byId('reference_solution_content');

    // Content from the markdown editor makes the reference solution an on-site one
    if (saved.content && content && !content.value) {
      if (typeSelect) typeSelect.value = 'onsite';
      content.value = saved.content;
    } else if (saved.solutionType && typeSelect && !typeSelect.value) {
      typeSelect.value = saved.solutionType;
    }
    ['title', 'sha256', 'goal', 'description', 'downloadLink', 'tags', 'tools'].forEach(field => {
      const element = byId(DRAFT_FIELDS[field]);
      if (saved[field] && element && !element.value) element.value = saved[field];
    });
    if (saved.difficulty && byId('id_difficulty')) {
      byId('id_difficulty').value = saved.difficulty;
    }

    if (saved.imageId && !byId('selected_image').value) {
      byId('selected_image').value = saved.imageId;
      markGalleryCard(saved.imageId);
      if (saved.imageUrl) showGalleryImage(saved.imageUrl);
    } else if (saved.uploadedImage) {
      showUploadedImage(saved.uploadedImage);
      try {
        const transfer = new DataTransfer();
        transfer.items.add(dataUrlToFile(saved.uploadedImage, 'restored_image.png'));
        byId('id_image_upload').files = transfer.files;
      } catch (error) {
        console.error('Error restoring file:', error);
      }
    }
  }

  // ------------------------------------------------------------------
  // Wiring
  // ------------------------------------------------------------------
  if (attrs.dataset.restoreDraft === 'true') {
    restoreDraft();
  }
  showCurrentImage();
  updateReferenceFields();

  document.querySelectorAll('.image-select-card').forEach(card => {
    card.addEventListener('click', () => selectGalleryImage(card));
  });
  document.querySelectorAll('[data-image-remove]').forEach(button => {
    button.addEventListener('click', () => removeImage(button.dataset.imageRemove));
  });

  const uploadInput = byId('id_image_upload');
  if (uploadInput) {
    uploadInput.addEventListener('change', () => checkUploadedImage(uploadInput));
  }

  const downloadLink = byId('id_download_link');
  if (downloadLink && byId('id_sha256')) {
    downloadLink.addEventListener('input', fillSha256);
    if (downloadLink.value) fillSha256();
  }

  const typeSelect = byId('id_reference_solution_type');
  if (typeSelect) {
    typeSelect.addEventListener('change', updateReferenceFields);
  }

  const picker = byId('reference-draft-picker');
  if (picker) {
    picker.addEventListener('draft-picker:change', e => {
      draftPicked = Boolean(e.detail.draft);
      updateReferenceFields();
      if (draftPicked) {
        const info = byId('selected-draft-info');
        window.scrollTo({ top: info.getBoundingClientRect().top + window.scrollY - 100, behavior: 'smooth' });
      }
    });
  }

  if (isNewTask) {
    const editorLink = byId('openMarkdownEditorLink');
    if (editorLink) editorLink.addEventListener('click', saveDraft);
    // Kept until the server has accepted the task (views/samples.py submit_task)
    byId('submit-task-form').addEventListener('submit', saveDraft);
  }
});
