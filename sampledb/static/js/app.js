// Syntax highlighting for rendered markdown code blocks
if (window.hljs) {
  hljs.highlightAll();
}

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

// POST to a like button's data-like-url; sends anonymous visitors to the login page.
// Resolves with the server's {liked, like_count}, or null when there is nothing to update.
function toggleLike(button) {
  return window.sp.fetchJSON(button.dataset.likeUrl, { method: 'POST' })
    .then(data => {
      if (data.error && data.redirect) {
        window.location.href = data.redirect;
        return null;
      }
      return data;
    })
    .catch(error => {
      console.error('Error:', error);
      return null;
    });
}

function updateDetailFavoriteCount(count) {
  const detailCount = document.getElementById('detail-favorite-count');
  if (detailCount) {
    detailCount.textContent = count;
  }
}

// The detail page's large favorite button (samples/_favorite_button_filled.html)
document.querySelectorAll('.favorite-btn-filled').forEach(button => {
  button.addEventListener('click', function(e) {
    e.preventDefault();

    toggleLike(this).then(data => {
      if (!data) return;

      const icon = this.querySelector('i');
      const countSpan = this.querySelector('.favorite-count');

      icon.classList.toggle('fas', data.liked);
      icon.classList.toggle('far', !data.liked);

      this.dataset.liked = data.liked;
      this.title = `${data.like_count} favorite${data.like_count !== 1 ? 's' : ''}`;

      if (countSpan) {
        countSpan.textContent = data.like_count;
      }
      updateDetailFavoriteCount(data.like_count);
    });
  });
});

// Task favorite and solution like buttons with a count
// (samples/_favorite_button.html, samples/_solution_like_button.html)
document.querySelectorAll('.favorite-btn, .solution-like-btn').forEach(button => {
  button.addEventListener('click', function(e) {
    e.preventDefault();

    const isSolution = this.classList.contains('solution-like-btn');
    const countClass = isSolution ? '.like-count' : '.favorite-count';
    const labelText = isSolution ? 'like' : 'favorite';

    toggleLike(this).then(data => {
      if (!data) return;

      // .like-state colors live in css/components.css
      const state = this.querySelector('.like-state');
      const icon = this.querySelector('i');
      const countSpan = this.querySelector(countClass);

      state.classList.toggle('is-liked', data.liked);
      icon.classList.toggle('fas', data.liked);
      icon.classList.toggle('far', !data.liked);

      countSpan.textContent = data.like_count;
      this.dataset.liked = data.liked;
      state.title = `${data.like_count} ${labelText}${data.like_count !== 1 ? 's' : ''}`;

      // The detail page shows the task's count (task favorites only)
      if (!isSolution) {
        updateDetailFavoriteCount(data.like_count);
      }
    });
  });
});

// "My ♥" toggle of the filter bar (samples/_filter_bar.html): flip the hidden
// favorites field and apply the filter
document.addEventListener('click', function(e) {
  const button = e.target.closest('[data-favorites-toggle]');
  if (!button || !button.form) return;
  const input = button.form.querySelector('input[name="favorites"]');
  input.value = input.value === 'true' ? 'false' : 'true';
  button.form.submit();
});
