// Comment editing functions
function editComment(commentId) {
  document.getElementById('comment-body-' + commentId).style.display = 'none';
  document.getElementById('edit-form-' + commentId).style.display = 'block';
}

function cancelEdit(commentId) {
  document.getElementById('comment-body-' + commentId).style.display = 'block';
  document.getElementById('edit-form-' + commentId).style.display = 'none';
}

function deleteComment(commentId, returnUrl) {
  if (confirm('Are you sure you want to delete this comment? This action cannot be undone.')) {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/comments/' + commentId + '/delete/';
    
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrfmiddlewaretoken';
    const csrfCookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
    if (csrfCookie) {
      csrfInput.value = csrfCookie.split('=')[1];
    }
    form.appendChild(csrfInput);
    
    const nextInput = document.createElement('input');
    nextInput.type = 'hidden';
    nextInput.name = 'next';
    nextInput.value = returnUrl;
    form.appendChild(nextInput);
    
    document.body.appendChild(form);
    form.submit();
  }
}

// Highlight newly posted comment
document.addEventListener('DOMContentLoaded', function() {
  const urlParams = new URLSearchParams(window.location.search);
  const highlightParam = urlParams.get('highlight');
  
  if (highlightParam) {
    const commentElement = document.getElementById(highlightParam);
    if (commentElement) {
      // Add highlight class
      commentElement.classList.add('comment-highlighted');
      
      // Smooth scroll to the comment
      setTimeout(() => {
        commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
      
      // Remove highlight after animation
      setTimeout(() => {
        commentElement.classList.remove('comment-highlighted');
        // Clean up URL without reloading page
        const url = new URL(window.location);
        url.searchParams.delete('highlight');
        window.history.replaceState({}, '', url);
      }, 3000);
    }
  }
  
  // Initialize @ mention autocomplete for comment textareas
  initializeMentionAutocomplete();
  
  // Convert @mentions to clickable links in existing comments
  convertMentionsToLinks();
});

// @ Mention Autocomplete functionality
function initializeMentionAutocomplete() {
  const commentTextareas = document.querySelectorAll('textarea[name="comment"]');
  
  commentTextareas.forEach(textarea => {
    let autocompleteDiv = null;
    let currentMentionStart = -1;
    let currentQuery = '';
    let selectedIndex = -1;
    let userSuggestions = [];
    
    // Create autocomplete dropdown
    function createAutocomplete() {
      if (!autocompleteDiv) {
        autocompleteDiv = document.createElement('div');
        autocompleteDiv.className = 'mention-autocomplete';
        autocompleteDiv.style.display = 'none';
        textarea.parentElement.style.position = 'relative';
        textarea.parentElement.appendChild(autocompleteDiv);
      }
      return autocompleteDiv;
    }
    
    // Position autocomplete dropdown
    function positionAutocomplete() {
      const div = createAutocomplete();
      const rect = textarea.getBoundingClientRect();
      const parentRect = textarea.parentElement.getBoundingClientRect();
      
      // Position below textarea
      div.style.top = (rect.bottom - parentRect.top + 5) + 'px';
      div.style.left = '0px';
      div.style.width = textarea.offsetWidth + 'px';
    }
    
    // Show suggestions
    function showSuggestions(users) {
      const div = createAutocomplete();
      userSuggestions = users;
      selectedIndex = -1;
      
      if (users.length === 0) {
        div.style.display = 'none';
        return;
      }
      
      div.innerHTML = users.map((user, index) => 
        `<div class="mention-item" data-index="${index}">@${user}</div>`
      ).join('');
      
      positionAutocomplete();
      div.style.display = 'block';
      
      // Add click handlers
      div.querySelectorAll('.mention-item').forEach(item => {
        item.addEventListener('click', function() {
          insertMention(this.textContent.substring(1)); // Remove @ prefix
        });
        
        item.addEventListener('mouseenter', function() {
          selectedIndex = parseInt(this.dataset.index);
          updateSelection();
        });
      });
    }
    
    // Update visual selection
    function updateSelection() {
      const items = autocompleteDiv.querySelectorAll('.mention-item');
      items.forEach((item, index) => {
        if (index === selectedIndex) {
          item.classList.add('selected');
        } else {
          item.classList.remove('selected');
        }
      });
    }
    
    // Insert selected mention
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
    
    // Hide autocomplete
    function hideAutocomplete() {
      if (autocompleteDiv) {
        autocompleteDiv.style.display = 'none';
      }
      currentMentionStart = -1;
      currentQuery = '';
      selectedIndex = -1;
      userSuggestions = [];
    }
    
    // Fetch user suggestions
    async function fetchUsers(query) {
      try {
        const response = await fetch(`/comments/search-users/?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        showSuggestions(data.users || []);
      } catch (error) {
        console.error('Error fetching users:', error);
        hideAutocomplete();
      }
    }
    
    // Handle input
    textarea.addEventListener('input', function(e) {
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
      
      if (mentionStart !== -1) {
        const query = text.substring(mentionStart + 1, cursorPos);
        
        // Check if valid mention query (alphanumeric and underscore only)
        if (/^[a-zA-Z0-9_]*$/.test(query)) {
          currentMentionStart = mentionStart;
          currentQuery = query;
          
          if (query.length >= 1) {
            fetchUsers(query);
          } else {
            hideAutocomplete();
          }
        } else {
          hideAutocomplete();
        }
      } else {
        hideAutocomplete();
      }
    });
    
    // Handle keyboard navigation
    textarea.addEventListener('keydown', function(e) {
      if (!autocompleteDiv || autocompleteDiv.style.display === 'none') {
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
      setTimeout(() => hideAutocomplete(), 200);
    });
  });
}

// Convert @mentions to clickable profile links
function convertMentionsToLinks() {
  // Find all comment bodies
  const commentBodies = document.querySelectorAll('.comment-body');
  
  commentBodies.forEach(commentBody => {
    // Skip if already processed
    if (commentBody.dataset.mentionsProcessed === 'true') {
      return;
    }
    
    // Get the HTML content
    let html = commentBody.innerHTML;
    
    // Replace @username patterns with links
    // Match @username (alphanumeric and underscore)
    const mentionRegex = /(@([a-zA-Z0-9_]+))/g;
    
    html = html.replace(mentionRegex, function(match, fullMention, username) {
      // Don't replace if already inside an anchor tag
      const beforeMatch = html.substring(0, html.indexOf(match));
      if (/<a[^>]*$/.test(beforeMatch)) {
        return match;
      }
      
      return `<a href="/profile/${username}/" class="mention-link">${fullMention}</a>`;
    });
    
    commentBody.innerHTML = html;
    commentBody.dataset.mentionsProcessed = 'true';
  });
}
