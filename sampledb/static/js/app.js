// Generate consistent color for each tag based on tag name
function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash = hash & hash;
  }
  return Math.abs(hash);
}

document.querySelectorAll('.badge-tag').forEach(badge => {
  const tagName = badge.textContent.trim();
  const hue = hashString(tagName) % 360;
  const saturation = 65;
  const lightness = 50;
  badge.style.backgroundColor = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
});

// Helper function to get CSRF token
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Consolidated favorite button functionality (works for both list and detail views)
document.querySelectorAll('.favorite-btn').forEach(button => {
  button.addEventListener('click', function(e) {
    e.preventDefault();
    const sha256 = this.dataset.sha256;
    const taskId = this.dataset.taskId;
    
    // Send AJAX request to toggle favorite
    fetch(`/sample/${sha256}/${taskId}/like/`, {
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
      const span = this.querySelector('span');
      const icon = this.querySelector('i');
      const countSpan = this.querySelector('.favorite-count');
      
      if (data.liked) {
        span.classList.remove('text-muted');
        span.classList.add('text-danger');
        icon.classList.remove('far');
        icon.classList.add('fas');
      } else {
        span.classList.remove('text-danger');
        span.classList.add('text-muted');
        icon.classList.remove('fas');
        icon.classList.add('far');
      }
      
      // Update count and dataset
      countSpan.textContent = data.like_count;
      this.dataset.liked = data.liked;
      span.title = `${data.like_count} favorite${data.like_count !== 1 ? 's' : ''}`;
    })
    .catch(error => console.error('Error:', error));
  });
});
