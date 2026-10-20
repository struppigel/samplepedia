/**
 * Sample detail page (samples/detail.html)
 * - <a data-scroll-to="id">: scroll smoothly to that element
 * - #copySha256 copies #sha256Text
 * - ?highlight_solution=<id> (from a notification): scroll to and highlight that solution
 * - <button data-attach-draft-url="..." data-draft-modal="modal id">: pick a draft
 *   (js/draft-selection.js) and publish it to this task
 * Solution delete and back buttons are declared in markup (js/utils.js).
 */
(function() {
  'use strict';

  document.querySelectorAll('[data-scroll-to]').forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      const target = document.getElementById(this.dataset.scrollTo);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  const copyButton = document.getElementById('copySha256');
  if (copyButton) {
    copyButton.addEventListener('click', function() {
      const sha256Text = document.getElementById('sha256Text').textContent;
      navigator.clipboard.writeText(sha256Text).then(() => {
        const icon = this.querySelector('i');
        icon.classList.replace('fa-copy', 'fa-check');
        this.blur(); // Remove focus to prevent outline
        setTimeout(() => icon.classList.replace('fa-check', 'fa-copy'), 2000);
      });
    });
  }

  function highlightSolution() {
    const solutionId = new URLSearchParams(window.location.search).get('highlight_solution');
    if (!solutionId) return;

    const solutionElement = document.querySelector(`.solution-item[data-solution-id="${CSS.escape(solutionId)}"]`);
    if (!solutionElement) return;

    // A slight delay so the page has its final layout
    setTimeout(() => {
      solutionElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      solutionElement.classList.add('solution-highlight');
      setTimeout(() => solutionElement.classList.remove('solution-highlight'), 3000);
    }, 100);

    // Clean up URL without reloading page
    window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
  }

  function attachDraft(url, draft) {
    window.sp.fetchJSON(url, { method: 'POST', data: { article_id: draft.id } })
      .then(data => {
        if (data.success) {
          // Reload the page to show the new solution
          if (data.reload) {
            window.location.reload();
          }
        } else {
          alert('Error: ' + (data.error || 'Failed to publish draft'));
        }
      })
      .catch(error => {
        console.error('Attach error:', error);
        alert('Error publishing draft. Please try again.');
      });
  }

  document.querySelectorAll('[data-attach-draft-url]').forEach(button => {
    button.addEventListener('click', function() {
      const url = this.dataset.attachDraftUrl;
      openDraftSelectionModal(this.dataset.draftModal, draft => attachDraft(url, draft));
    });
  });

  highlightSolution();
})();
