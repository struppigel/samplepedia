/**
 * Publish-article modal (samples/_publish_modal.html)
 * Search an analysis task and attach a draft article to it as a solution.
 */

// Publish modal functionality
let currentArticleId = null;
let searchTimeout = null;

function setPublishVisible(id, visible) {
  document.getElementById(id).style.display = visible ? '' : 'none';
}

function openPublishModal(articleId, articleTitle) {
  currentArticleId = articleId;
  document.getElementById('publishArticleTitle').textContent = articleTitle;
  document.getElementById('sampleSearch').value = '';
  setPublishVisible('searchResults', false);
  setPublishVisible('noResults', false);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('publishModal')).show();
}

// Search samples with debouncing
document.addEventListener('DOMContentLoaded', function() {
  const searchInput = document.getElementById('sampleSearch');
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      const query = this.value.trim();

      // Clear previous timeout
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }

      // Hide results if query is too short
      if (query.length < 2) {
        setPublishVisible('searchResults', false);
        setPublishVisible('noResults', false);
        return;
      }

      // Show loading
      setPublishVisible('searchLoading', true);
      setPublishVisible('searchResults', false);
      setPublishVisible('noResults', false);

      // Debounce: wait 300ms after user stops typing
      searchTimeout = setTimeout(() => {
        fetch(`/ajax/search-samples/?q=${encodeURIComponent(query)}`)
          .then(response => response.json())
          .then(data => {
            setPublishVisible('searchLoading', false);

            if (data.results && data.results.length > 0) {
              displaySearchResults(data.results);
            } else {
              setPublishVisible('searchResults', false);
              setPublishVisible('noResults', true);
            }
          })
          .catch(error => {
            console.error('Search error:', error);
            setPublishVisible('searchLoading', false);
            alert('Error searching for analysis tasks. Please try again.');
          });
      }, 300);
    });
  }
});

function displaySearchResults(results) {
  const escapeHtml = window.sp.escapeHtml;
  const sampleList = document.getElementById('sampleList');
  sampleList.innerHTML = '';

  results.forEach(sample => {
    // difficulty_class comes from the server (samples/design_tokens.py)
    const item = document.createElement('a');
    item.href = '#';
    item.className = 'list-group-item list-group-item-action';
    item.innerHTML = `
      <div class="d-flex w-100 justify-content-between align-items-start">
        <div class="flex-grow-1">
          <h6 class="mb-1">
            <code class="text-smaller">${escapeHtml(sample.sha256_short)}...</code>
            <span class="badge ${escapeHtml(sample.difficulty_class)} ms-2">${escapeHtml(sample.difficulty_display)}</span>
          </h6>
          <p class="mb-1 text-muted text-smaller">${escapeHtml(sample.goal)}</p>
          <small class="text-muted">by ${escapeHtml(sample.author)}</small>
        </div>
        <button class="btn btn-sm btn-secondary ms-3 text-nowrap" onclick="publishToSample(event, ${Number(sample.id)})">
          <i class="fas fa-check"></i> Select
        </button>
      </div>
    `;
    sampleList.appendChild(item);
  });

  setPublishVisible('searchResults', true);
  setPublishVisible('noResults', false);
}

function publishToSample(event, sampleId) {
  event.preventDefault();
  event.stopPropagation();

  if (!currentArticleId) {
    alert('Error: Article ID not found');
    return;
  }

  // Get CSRF token
  const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                    window.sp.getCookie('csrftoken');

  if (!csrfToken) {
    alert('Error: CSRF token not found');
    return;
  }

  // Create form data
  const formData = new FormData();
  formData.append('sample_id', sampleId);
  formData.append('csrfmiddlewaretoken', csrfToken);

  // Submit
  fetch(`/articles/${currentArticleId}/publish/`, {
    method: 'POST',
    body: formData,
    headers: {
      'X-CSRFToken': csrfToken
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      bootstrap.Modal.getOrCreateInstance(document.getElementById('publishModal')).hide();
      // Redirect to the sample detail page
      window.location.href = data.redirect_url;
    } else {
      alert('Error: ' + (data.error || 'Failed to publish article'));
    }
  })
  .catch(error => {
    console.error('Publish error:', error);
    alert('Error publishing article. Please try again.');
  });
}
