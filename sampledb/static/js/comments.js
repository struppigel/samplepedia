/**
 * Comments (comments/list.html, comments/form.html)
 * - Edit in place: [data-comment-edit] / [data-comment-cancel] inside a .comment swap
 *   its .comment-body and .comment-edit-form (delete is a data-post-url button, see utils.js)
 * - ?highlight=comment-<id> (set after posting) scrolls to and highlights that comment
 * - @mention autocomplete on textarea[data-mention-search-url]
 * Mentions in posted comments are linked by the server (|mention_links, templatetags/comment_tags.py).
 */
(function() {
  'use strict';

  function showEditForm(comment, editing) {
    window.sp.show(comment.querySelector('.comment-body'), !editing);
    window.sp.show(comment.querySelector('.comment-edit-form'), editing);
  }

  document.addEventListener('click', function(e) {
    const edit = e.target.closest('[data-comment-edit]');
    const cancel = e.target.closest('[data-comment-cancel]');
    const button = edit || cancel;
    if (!button) return;
    const comment = button.closest('.comment');
    if (comment) {
      showEditForm(comment, Boolean(edit));
    }
  });

  // Highlight newly posted comment
  function highlightComment() {
    const highlightParam = new URLSearchParams(window.location.search).get('highlight');
    if (!highlightParam) return;

    const commentElement = document.getElementById(highlightParam);
    if (!commentElement) return;

    commentElement.classList.add('comment-highlighted');

    setTimeout(() => {
      commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);

    // Remove highlight after animation and clean up the URL without reloading
    setTimeout(() => {
      commentElement.classList.remove('comment-highlighted');
      const url = new URL(window.location);
      url.searchParams.delete('highlight');
      window.history.replaceState({}, '', url);
    }, 3000);
  }

  // @ Mention autocomplete
  function initializeMentionAutocomplete(textarea) {
    const searchUrl = textarea.dataset.mentionSearchUrl;
    let autocompleteDiv = null;
    let currentMentionStart = -1;
    let selectedIndex = -1;
    let userSuggestions = [];

    function createAutocomplete() {
      if (!autocompleteDiv) {
        autocompleteDiv = document.createElement('div');
        autocompleteDiv.className = 'mention-autocomplete';
        autocompleteDiv.hidden = true;
        textarea.parentElement.classList.add('position-relative');
        textarea.parentElement.appendChild(autocompleteDiv);
      }
      return autocompleteDiv;
    }

    // Position the dropdown below the textarea (layout only, no design values)
    function positionAutocomplete() {
      const div = createAutocomplete();
      const rect = textarea.getBoundingClientRect();
      const parentRect = textarea.parentElement.getBoundingClientRect();

      div.style.top = (rect.bottom - parentRect.top + 5) + 'px';
      div.style.left = '0px';
      div.style.width = textarea.offsetWidth + 'px';
    }

    function showSuggestions(users) {
      const div = createAutocomplete();
      userSuggestions = users;
      selectedIndex = -1;

      if (users.length === 0) {
        window.sp.show(div, false);
        return;
      }

      div.innerHTML = users.map((user, index) =>
        `<div class="mention-item" data-index="${index}">@${window.sp.escapeHtml(user)}</div>`
      ).join('');

      positionAutocomplete();
      window.sp.show(div, true);

      div.querySelectorAll('.mention-item').forEach(item => {
        item.addEventListener('click', function() {
          insertMention(userSuggestions[Number(this.dataset.index)]);
        });

        item.addEventListener('mouseenter', function() {
          selectedIndex = Number(this.dataset.index);
          updateSelection();
        });
      });
    }

    function updateSelection() {
      autocompleteDiv.querySelectorAll('.mention-item').forEach((item, index) => {
        item.classList.toggle('selected', index === selectedIndex);
      });
    }

    function insertMention(username) {
      const text = textarea.value;
      const beforeMention = text.substring(0, currentMentionStart);
      const afterMention = text.substring(textarea.selectionStart);

      textarea.value = beforeMention + '@' + username + ' ' + afterMention;
      const newPos = beforeMention.length + username.length + 2;
      textarea.setSelectionRange(newPos, newPos);
      textarea.focus();

      hideAutocomplete();
    }

    function hideAutocomplete() {
      window.sp.show(autocompleteDiv, false);
      currentMentionStart = -1;
      selectedIndex = -1;
      userSuggestions = [];
    }

    async function fetchUsers(query) {
      try {
        const url = new URL(searchUrl, window.location.href);
        url.searchParams.set('q', query);
        const data = await window.sp.fetchJSON(url);
        showSuggestions(data.users || []);
      } catch (error) {
        console.error('Error fetching users:', error);
        hideAutocomplete();
      }
    }

    textarea.addEventListener('input', function() {
      const cursorPos = this.selectionStart;
      const text = this.value;

      // Find if we're in a mention
      let mentionStart = -1;
      for (let i = cursorPos - 1; i >= 0; i--) {
        if (text[i] === '@') {
          mentionStart = i;
          break;
        }
        if (text[i] === ' ' || text[i] === '\n') {
          break;
        }
      }

      if (mentionStart === -1) {
        hideAutocomplete();
        return;
      }

      const query = text.substring(mentionStart + 1, cursorPos);
      // A valid mention query is alphanumeric and underscore only
      if (/^[a-zA-Z0-9_]+$/.test(query)) {
        currentMentionStart = mentionStart;
        fetchUsers(query);
      } else {
        hideAutocomplete();
      }
    });

    textarea.addEventListener('keydown', function(e) {
      if (!autocompleteDiv || autocompleteDiv.hidden) {
        return;
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, userSuggestions.length - 1);
        updateSelection();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        updateSelection();
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        if (selectedIndex >= 0 && selectedIndex < userSuggestions.length) {
          e.preventDefault();
          insertMention(userSuggestions[selectedIndex]);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        hideAutocomplete();
      }
    });

    // Hide on blur (with delay for click handling)
    textarea.addEventListener('blur', function() {
      setTimeout(hideAutocomplete, 200);
    });
  }

  function init() {
    highlightComment();
    document.querySelectorAll('textarea[data-mention-search-url]').forEach(initializeMentionAutocomplete);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
