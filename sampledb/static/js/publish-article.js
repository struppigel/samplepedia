/**
 * Publish-article modal (samples/_publish_modal.html): search an analysis task
 * and attach a draft article to it as a solution.
 *
 * - openPublishModal(articleId, articleTitle) opens it for that article (the article
 *   pages call it from their data-publish-article buttons, js/pages/articles.js)
 *
 * The modal includes this script itself, so it may run before js/utils.js:
 * window.sp is only used once the page has loaded.
 */
(function() {
  'use strict';

  const SEARCH_DELAY_MS = 300;
  let currentArticleId = null;
  let searchTimeout = null;
  let latestQuery = '';

  function byId(id) {
    return document.getElementById(id);
  }

  function showOnly(visibleId) {
    ['searchResults', 'noResults', 'searchLoading'].forEach(id => window.sp.show(byId(id), id === visibleId));
  }

  function openPublishModal(articleId, articleTitle) {
    currentArticleId = articleId;
    byId('publishArticleTitle').textContent = articleTitle;
    byId('sampleSearch').value = '';
    showOnly(null);
    bootstrap.Modal.getOrCreateInstance(byId('publishModal')).show();
  }

  function search(query) {
    const url = `${byId('publishModal').dataset.searchUrl}?q=${encodeURIComponent(query)}`;
    window.sp.fetchJSON(url)
      .then(data => {
        if (query !== latestQuery) return; // answer to an older query
        if (data.results && data.results.length > 0) {
          renderResults(data.results);
          showOnly('searchResults');
        } else {
          showOnly('noResults');
        }
      })
      .catch(error => {
        console.error('Search error:', error);
        showOnly(null);
        alert('Error searching for analysis tasks. Please try again.');
      });
  }

  function renderResults(results) {
    const escapeHtml = window.sp.escapeHtml;
    // difficulty_class comes from the server (samples/design_tokens.py)
    byId('sampleList').innerHTML = results.map(sample => `
      <div class="list-group-item list-group-item-action">
        <div class="d-flex w-100 justify-content-between align-items-start">
          <div class="flex-grow-1">
            <h6 class="mb-1">
              <code class="text-smaller">${escapeHtml(sample.sha256_short)}...</code>
              <span class="badge ${escapeHtml(sample.difficulty_class)} ms-2">${escapeHtml(sample.difficulty_display)}</span>
            </h6>
            <p class="mb-1 text-muted text-smaller">${escapeHtml(sample.goal)}</p>
            <small class="text-muted">by ${escapeHtml(sample.author)}</small>
          </div>
          <button type="button" class="btn btn-sm btn-secondary ms-3 text-nowrap" data-publish-to-sample="${escapeHtml(sample.id)}">
            <i class="fas fa-check"></i> Select
          </button>
        </div>
      </div>
    `).join('');
  }

  function publishToSample(sampleId) {
    if (!currentArticleId) {
      alert('Error: Article ID not found');
      return;
    }
    // data-publish-url is the URL for article 0
    const url = byId('publishModal').dataset.publishUrl.replace('/0/', `/${encodeURIComponent(currentArticleId)}/`);
    window.sp.fetchJSON(url, { method: 'POST', data: { sample_id: sampleId } })
      .then(data => {
        if (data.success) {
          bootstrap.Modal.getOrCreateInstance(byId('publishModal')).hide();
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

  // Search as the user types, 300 ms after the last key
  document.addEventListener('input', function(e) {
    if (e.target.id !== 'sampleSearch') return;
    const query = e.target.value.trim();
    latestQuery = query;
    clearTimeout(searchTimeout);
    if (query.length < 2) {
      showOnly(null);
      return;
    }
    showOnly('searchLoading');
    searchTimeout = setTimeout(() => search(query), SEARCH_DELAY_MS);
  });

  document.addEventListener('click', function(e) {
    const select = e.target.closest('[data-publish-to-sample]');
    if (select) {
      e.preventDefault();
      publishToSample(select.dataset.publishToSample);
    }
  });

  window.openPublishModal = openPublishModal;
})();
