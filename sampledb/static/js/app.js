// Syntax highlighting for rendered markdown code blocks
if (window.hljs) {
  hljs.highlightAll();
}

// Confirm before following a user-submitted external link.
// The URL is read from the DOM, never interpolated into JS by the template.
document.addEventListener('click', function(e) {
  const link = e.target.closest('a[data-external-confirm]');
  if (link && !confirm(`You are about to visit an external website:\n\n${link.href}\n\nDo you want to continue?`)) {
    e.preventDefault();
  }
});

// Generate consistent color for each tag based on tag name
function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash = hash & hash;
  }
  return Math.abs(hash);
}

// Only the hue is computed here; saturation/lightness live in css/tokens.css
document.querySelectorAll('.badge-tag').forEach(badge => {
  const tagName = badge.textContent.trim();
  badge.style.setProperty('--tag-hue', hashString(tagName) % 360);
});

// Kept as a global for page scripts that still call getCookie()
function getCookie(name) {
  return window.sp.getCookie(name);
}

// Favorite button filled functionality
document.querySelectorAll('.favorite-btn-filled').forEach(button => {
  button.addEventListener('click', function(e) {
    e.preventDefault();

    const url = `/sample/${this.dataset.sha256}/${this.dataset.taskId}/like/`;

    // Send AJAX request to toggle favorite
    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
      }
    })
    .then(response => response.json())
    .then(data => {
      // Check if login is required
      if (data.error && data.redirect) {
        window.location.href = data.redirect;
        return;
      }

      // Update button appearance
      const icon = this.querySelector('i');
      const countSpan = this.querySelector('.favorite-count');

      icon.classList.toggle('fas', data.liked);
      icon.classList.toggle('far', !data.liked);

      // Update counts
      this.dataset.liked = data.liked;
      this.title = `${data.like_count} favorite${data.like_count !== 1 ? 's' : ''}`;

      if (countSpan) {
        countSpan.textContent = data.like_count;
      }

      // Update the detail page count
      const detailCount = document.getElementById('detail-favorite-count');
      if (detailCount) {
        detailCount.textContent = data.like_count;
      }
    })
    .catch(error => console.error('Error:', error));
  });
});

// Consolidated like/favorite button functionality
document.querySelectorAll('.favorite-btn, .solution-like-btn').forEach(button => {
  button.addEventListener('click', function(e) {
    e.preventDefault();

    // Determine button type and construct URL
    const isSolution = this.classList.contains('solution-like-btn');
    const url = isSolution
      ? `/solution/${this.dataset.solutionId}/like/`
      : `/sample/${this.dataset.sha256}/${this.dataset.taskId}/like/`;
    const countClass = isSolution ? '.like-count' : '.favorite-count';
    const labelText = isSolution ? 'like' : 'favorite';

    // Send AJAX request to toggle like/favorite
    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/json'
      }
    })
    .then(response => response.json())
    .then(data => {
      // Check if login is required
      if (data.error && data.redirect) {
        window.location.href = data.redirect;
        return;
      }

      // Update button appearance (.like-state colors live in css/components.css)
      const state = this.querySelector('.like-state');
      const icon = this.querySelector('i');
      const countSpan = this.querySelector(countClass);

      state.classList.toggle('is-liked', data.liked);
      icon.classList.toggle('fas', data.liked);
      icon.classList.toggle('far', !data.liked);

      // Update count and dataset
      countSpan.textContent = data.like_count;
      this.dataset.liked = data.liked;
      state.title = `${data.like_count} ${labelText}${data.like_count !== 1 ? 's' : ''}`;

      // Update the detail page count (task favorites only)
      const detailCount = document.getElementById('detail-favorite-count');
      if (detailCount && !isSolution) {
        detailCount.textContent = data.like_count;
      }
    })
    .catch(error => console.error('Error:', error));
  });
});
