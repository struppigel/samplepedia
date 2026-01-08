/**
 * Submit Task Form - Image and Draft Management
 * Handles image selection, upload, preview, and localStorage draft persistence
 */

/**
 * Form Draft Manager - Centralized localStorage handling
 */
const FormDraftManager = {
  keys: {
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
  },

  getField(key) {
    return localStorage.getItem(this.keys[key]);
  },

  setField(key, value) {
    if (value) {
      localStorage.setItem(this.keys[key], value);
    }
  },

  removeField(key) {
    localStorage.removeItem(this.keys[key]);
  },

  save(data) {
    Object.keys(data).forEach(key => {
      if (data[key] && this.keys[key]) {
        this.setField(key, data[key]);
      }
    });
  },

  restore() {
    const restored = {};
    Object.keys(this.keys).forEach(key => {
      const value = this.getField(key);
      if (value) {
        restored[key] = value;
      }
    });
    return restored;
  },

  clear() {
    Object.values(this.keys).forEach(key => {
      localStorage.removeItem(key);
    });
  }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  initializeEditModeImages();
  initializeGallerySelection();
  initializeImageUpload();
  initializeSHA256AutoFill();
  initializeMarkdownEditorIntegration();
  initializeMarkdownPreviewTabs();
  initializeFormSubmission();
});

/**
 * Show existing images when editing a task
 */
function initializeEditModeImages() {
  const dataAttrs = document.getElementById('form-data-attrs');
  if (!dataAttrs) return;
  
  // Gallery image in edit mode
  const currentImageId = dataAttrs.dataset.currentImageId;
  if (currentImageId) {
    document.getElementById('selected_image').value = currentImageId;
    
    const imageCard = document.querySelector(`[data-image-id="${currentImageId}"]`);
    if (imageCard) {
      const imgSrc = imageCard.getAttribute('data-image-url');
      document.getElementById('preview_img').src = imgSrc;
      document.getElementById('selected_image_preview').style.display = 'block';
      document.getElementById('image_preview_area').style.display = 'block';
      imageCard.classList.add('selected');
    }
    
    hideImageSelectionSections();
  }
  
  // Uploaded image in edit mode (non-gallery)
  const currentImageUrl = dataAttrs.dataset.currentImageUrl;
  if (currentImageUrl && !currentImageId) {
    const previewImg = document.getElementById('preview_img');
    const previewDiv = document.getElementById('selected_image_preview');
    if (previewImg && previewDiv) {
      previewImg.src = currentImageUrl;
      previewDiv.style.display = 'block';
      document.getElementById('image_preview_area').style.display = 'block';
    }
    
    hideImageSelectionSections();
  }
}

/**
 * Handle gallery image card clicks
 */
function initializeGallerySelection() {
  document.querySelectorAll('.image-select-card').forEach(card => {
    const imageUrl = card.getAttribute('data-image-url');
    const imageId = card.getAttribute('data-image-id');
    
    card.addEventListener('click', function() {
      selectImage(imageUrl, imageId);
    });
  });
}

/**
 * Select image from gallery
 */
function selectImage(imageUrl, imageId) {
  document.getElementById('selected_image').value = imageId;
  
  const previewDiv = document.getElementById('selected_image_preview');
  const previewImg = document.getElementById('preview_img');
  previewImg.src = imageUrl;
  previewDiv.style.display = 'block';
  document.getElementById('image_preview_area').style.display = 'block';
  
  // Highlight selected card
  document.querySelectorAll('.image-select-card').forEach(card => {
    if (card.getAttribute('data-image-id') === imageId) {
      card.classList.add('selected');
    } else {
      card.classList.remove('selected');
    }
  });
  
  hideImageSelectionSections();
  
  // Close modal
  $('#imageGalleryModal').modal('hide');
}

/**
 * Clear common preview elements
 */
function clearAllPreviews() {
  document.getElementById('image_preview_area').style.display = 'none';
  document.getElementById('clear_image_flag').value = 'true';
  showImageSelectionSections();
}

/**
 * Clear gallery image selection
 */
function clearImageSelection() {
  document.getElementById('selected_image').value = '';
  document.getElementById('selected_image_preview').style.display = 'none';
  
  document.querySelectorAll('.image-select-card').forEach(card => {
    card.classList.remove('selected');
  });
  
  clearAllPreviews();
}

/**
 * Handle image upload with validation
 */
function initializeImageUpload() {
  const uploadInput = document.getElementById('id_image_upload');
  if (uploadInput) {
    uploadInput.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = function(e) {
          const img = new Image();
          img.onload = function() {
            const width = this.width;
            const height = this.height;
            
            // Validate dimensions
            if (width < 125 || height < 125) {
              alert(`Image is too small (${width}x${height}px). Minimum size is 125x125 pixels.`);
              uploadInput.value = '';
              return;
            }
            
            if (width > 1024 || height > 1024) {
              alert(`Image is too large (${width}x${height}px). Maximum size is 1024x1024 pixels.`);
              uploadInput.value = '';
              return;
            }
            
            // Show preview
            const previewImg = document.getElementById('upload_preview_img');
            const previewDiv = document.getElementById('upload_image_preview');
            if (previewImg && previewDiv) {
              previewImg.src = e.target.result;
              previewDiv.style.display = 'block';
              document.getElementById('image_preview_area').style.display = 'block';
              
              hideImageSelectionSections();
              
              // Clear gallery selection and save upload
              FormDraftManager.removeField('imageId');
              FormDraftManager.removeField('imageUrl');
              document.getElementById('selected_image').value = '';
              FormDraftManager.setField('uploadedImage', e.target.result);
              
              // Warn if non-square
              if (width !== height) {
                const cropSize = Math.min(width, height);
                alert(`Image will be center-cropped to ${cropSize}x${cropSize}px to maintain 1:1 aspect ratio.`);
              }
            }
          };
          img.src = e.target.result;
        };
        reader.readAsDataURL(file);
      }
    });
  }
}

/**
 * Clear uploaded image preview
 */
function clearUploadPreview() {
  const uploadInput = document.getElementById('id_image_upload');
  const previewDiv = document.getElementById('upload_image_preview');
  
  if (uploadInput) {
    uploadInput.value = '';
  }
  if (previewDiv) {
    previewDiv.style.display = 'none';
  }
  
  FormDraftManager.removeField('uploadedImage');
  clearAllPreviews();
}

/**
 * Hide image selection sections
 */
function hideImageSelectionSections() {
  document.getElementById('upload-section').style.display = 'none';
  document.getElementById('gallery-section').style.display = 'none';
}

/**
 * Show image selection sections
 */
function showImageSelectionSections() {
  document.getElementById('upload-section').style.display = 'block';
  document.getElementById('gallery-section').style.display = 'block';
}

/**
 * Auto-fill SHA256 from download link
 */
function initializeSHA256AutoFill() {
  const downloadLinkInput = document.getElementById('id_download_link');
  const sha256Input = document.getElementById('id_sha256');
  
  if (downloadLinkInput && sha256Input) {
    downloadLinkInput.addEventListener('input', function() {
      const url = this.value.trim();
      let sha256 = '';
      
      // Extract SHA256 from MalShare URL
      const malshareMatch = url.match(/[?&]hash=([a-fA-F0-9]{64})/);
      if (malshareMatch) {
        sha256 = malshareMatch[1].toLowerCase();
      }
      
      // Extract SHA256 from MalwareBazaar URL
      const bazaarMatch = url.match(/\/sample\/([a-fA-F0-9]{64})/);
      if (bazaarMatch) {
        sha256 = bazaarMatch[1].toLowerCase();
      }
      
      // Update SHA256 field
      if (sha256) {
        sha256Input.value = sha256;
        sha256Input.classList.remove('is-invalid');
        sha256Input.classList.add('is-valid');
      } else if (url) {
        sha256Input.value = '';
        sha256Input.classList.remove('is-valid');
      }
    });
    
    // Trigger extraction on page load if value exists (edit mode)
    if (downloadLinkInput.value) {
      downloadLinkInput.dispatchEvent(new Event('input'));
    }
  }
}

/**
 * Markdown editor integration with localStorage
 */
function initializeMarkdownEditorIntegration() {
  const elements = {
    titleInput: document.getElementById('id_reference_solution_title'),
    contentTextarea: document.getElementById('reference_solution_content'),
    solutionTypeSelect: document.getElementById('id_reference_solution_type'),
    markdownEditorLink: document.getElementById('openMarkdownEditorLink'),
    sha256Input: document.getElementById('id_sha256'),
    goalInput: document.getElementById('id_goal'),
    descriptionTextarea: document.getElementById('id_description'),
    downloadLinkInput: document.getElementById('id_download_link'),
    selectedImageInput: document.getElementById('selected_image'),
    tagsInput: document.getElementById('id_tags'),
    toolsInput: document.getElementById('id_tools'),
    difficultySelect: document.getElementById('id_difficulty')
  };
  
  const dataAttrs = document.getElementById('form-data-attrs');
  const isEditMode = dataAttrs && dataAttrs.dataset.isEdit === 'true';
  
  // Restore form data from localStorage
  restoreFormData(elements, isEditMode);
  
  // Save data when navigating to markdown editor
  if (elements.markdownEditorLink) {
    elements.markdownEditorLink.addEventListener('click', function() {
      saveFormDataToLocalStorage(elements);
    });
  }
}

/**
 * Restore form data from localStorage
 */
function restoreFormData(elements, isEditMode) {
  const saved = FormDraftManager.restore();
  
  // Restore text fields
  if (saved.title && elements.titleInput && !elements.titleInput.value) {
    elements.titleInput.value = saved.title;
  }
  
  // Restore solution type and content
  if (saved.content && elements.contentTextarea && !elements.contentTextarea.value) {
    if (elements.solutionTypeSelect) {
      elements.solutionTypeSelect.value = 'onsite';
      elements.solutionTypeSelect.dispatchEvent(new Event('change'));
    }
    elements.contentTextarea.value = saved.content;
  } else if (saved.solutionType && elements.solutionTypeSelect && !elements.solutionTypeSelect.value) {
    elements.solutionTypeSelect.value = saved.solutionType;
    elements.solutionTypeSelect.dispatchEvent(new Event('change'));
  }
  
  // Restore other fields
  if (saved.sha256 && elements.sha256Input && !elements.sha256Input.value) {
    elements.sha256Input.value = saved.sha256;
  }
  if (saved.goal && elements.goalInput && !elements.goalInput.value) {
    elements.goalInput.value = saved.goal;
  }
  if (saved.description && elements.descriptionTextarea && !elements.descriptionTextarea.value) {
    elements.descriptionTextarea.value = saved.description;
  }
  if (saved.downloadLink && elements.downloadLinkInput && !elements.downloadLinkInput.value) {
    elements.downloadLinkInput.value = saved.downloadLink;
  }
  if (saved.tags && elements.tagsInput && !elements.tagsInput.value) {
    elements.tagsInput.value = saved.tags;
  }
  if (saved.tools && elements.toolsInput && !elements.toolsInput.value) {
    elements.toolsInput.value = saved.tools;
  }
  if (saved.difficulty && elements.difficultySelect) {
    elements.difficultySelect.value = saved.difficulty;
  }
  
  // Restore images only if NOT in edit mode
  if (!isEditMode) {
    restoreImageFromLocalStorage(saved, elements);
  }
}

/**
 * Restore image from localStorage
 */
function restoreImageFromLocalStorage(saved, elements) {
  if (saved.imageId && elements.selectedImageInput && !elements.selectedImageInput.value) {
    elements.selectedImageInput.value = saved.imageId;
    if (saved.imageUrl) {
      const previewImg = document.getElementById('preview_img');
      const previewDiv = document.getElementById('selected_image_preview');
      if (previewImg && previewDiv) {
        previewImg.src = saved.imageUrl;
        previewDiv.style.display = 'block';
        document.getElementById('image_preview_area').style.display = 'block';
        hideImageSelectionSections();
      }
    }
  } else if (saved.uploadedImage) {
    const previewImg = document.getElementById('upload_preview_img');
    const previewDiv = document.getElementById('upload_image_preview');
    const uploadInput = document.getElementById('id_image_upload');
    if (previewImg && previewDiv) {
      previewImg.src = saved.uploadedImage;
      previewDiv.style.display = 'block';
      document.getElementById('image_preview_area').style.display = 'block';
      hideImageSelectionSections();
      
      // Restore file to input
      if (uploadInput) {
        fetch(saved.uploadedImage)
          .then(res => res.blob())
          .then(blob => {
            const file = new File([blob], "restored_image.png", { type: blob.type });
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            uploadInput.files = dataTransfer.files;
          })
          .catch(err => console.error('Error restoring file:', err));
      }
    }
  }
}

/**
 * Save form data to localStorage
 */
function saveFormDataToLocalStorage(elements) {
  const data = {
    title: elements.titleInput?.value,
    content: elements.contentTextarea?.value,
    solutionType: elements.solutionTypeSelect?.value,
    sha256: elements.sha256Input?.value,
    goal: elements.goalInput?.value,
    description: elements.descriptionTextarea?.value,
    downloadLink: elements.downloadLinkInput?.value,
    tags: elements.tagsInput?.value,
    tools: elements.toolsInput?.value,
    difficulty: elements.difficultySelect?.value
  };
  
  if (elements.selectedImageInput?.value) {
    data.imageId = elements.selectedImageInput.value;
    const previewImg = document.getElementById('preview_img');
    if (previewImg?.src) {
      data.imageUrl = previewImg.src;
    }
  }
  
  FormDraftManager.save(data);
}

/**
 * Initialize markdown preview tabs
 */
function initializeMarkdownPreviewTabs() {
  const tabs = document.querySelectorAll('.markdown-tab');
  const panes = document.querySelectorAll('.markdown-pane');
  const textarea = document.getElementById('id_description');
  const previewContent = document.querySelector('.markdown-preview-content');
  let previewCache = '';
  
  // Toggle reference solution fields
  const refSolutionTypeSelect = document.getElementById('id_reference_solution_type');
  const refUrlField = document.getElementById('reference-url-field');
  const refContentField = document.getElementById('reference-content-field');
  
  if (refSolutionTypeSelect && refUrlField && refContentField) {
    function toggleRefFields() {
      const selectedType = refSolutionTypeSelect.value;
      if (selectedType === 'onsite') {
        refUrlField.style.display = 'none';
        refContentField.style.display = 'block';
      } else {
        refUrlField.style.display = 'block';
        refContentField.style.display = 'none';
      }
    }
    
    toggleRefFields();
    refSolutionTypeSelect.addEventListener('change', toggleRefFields);
  }
  
  // Handle tab clicks
  tabs.forEach(tab => {
    tab.addEventListener('click', function() {
      const targetTab = this.getAttribute('data-tab');
      
      tabs.forEach(t => t.classList.remove('active'));
      this.classList.add('active');
      
      panes.forEach(p => {
        if (p.getAttribute('data-pane') === targetTab) {
          p.classList.add('active');
        } else {
          p.classList.remove('active');
        }
      });
      
      // Render markdown preview
      if (targetTab === 'preview') {
        const content = textarea.value;
        
        if (content !== previewCache) {
          previewCache = content;
          
          if (!content.trim()) {
            previewContent.innerHTML = '<p class="text-muted">Nothing to preview</p>';
            return;
          }
          
          previewContent.innerHTML = '<p class="text-muted"><i class="fas fa-spinner fa-spin"></i> Loading preview...</p>';
          
          const dataAttrs = document.getElementById('form-data-attrs');
          const markdownPreviewUrl = dataAttrs ? dataAttrs.dataset.markdownPreviewUrl : '/markdown-preview/';
          const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
          
          fetch(markdownPreviewUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
              'X-CSRFToken': csrfToken
            },
            body: 'content=' + encodeURIComponent(content)
          })
          .then(response => response.json())
          .then(data => {
            previewContent.innerHTML = data.html;
          })
          .catch(error => {
            console.error('Preview error:', error);
            previewContent.innerHTML = '<p class="text-danger">Error loading preview</p>';
          });
        }
      }
    });
  });
}

/**
 * Clear localStorage on form submission
 */
function initializeFormSubmission() {
  const form = document.querySelector('form[method="post"]');
  if (form) {
    form.addEventListener('submit', function() {
      // Use external clearFormDrafts if available, otherwise use FormDraftManager
      if (typeof clearFormDrafts === 'function') {
        clearFormDrafts();
      } else {
        FormDraftManager.clear();
      }
    });
  }
}

/**
 * Confirm task deletion
 */
function confirmDelete() {
  if (confirm('Are you sure you want to delete this analysis task? This action cannot be undone.')) {
    document.getElementById('deleteForm').submit();
  }
}