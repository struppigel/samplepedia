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
