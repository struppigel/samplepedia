/**
 * Stand-alone markdown editor (samples/markdown_editor.html), where the
 * reference solution of the submit-task form can be written (js/md-editor.js):
 * - starts with the reference solution the task form handed over (task-form draft)
 * - #copyMarkdown copies the content
 * - #useInSubmitForm hands title and content back to the task form and opens it
 */
document.addEventListener('DOMContentLoaded', function() {
  'use strict';

  const root = document.querySelector('[data-md-editor]');
  if (!root) return;
  const editor = window.sp.MarkdownEditor.get(root);
  const drafts = window.sp.drafts;
  const fields = drafts.taskForm;

  // The task form's reference solution wins over this editor's own autosave
  const handedOver = { title: drafts.get(fields.title), content: drafts.get(fields.content) };
  if (handedOver.title || handedOver.content) {
    const current = editor.values;
    editor.setValues({
      title: handedOver.title || current.title,
      content: handedOver.content || current.content
    });
  }

  function flash(button, html, fromClass, ms, done) {
    const label = button.innerHTML;
    button.innerHTML = html;
    button.classList.replace(fromClass, 'btn-secondary');
    setTimeout(() => {
      if (done) {
        done();
        return;
      }
      button.innerHTML = label;
      button.classList.replace('btn-secondary', fromClass);
    }, ms);
  }

  const copyButton = document.getElementById('copyMarkdown');
  copyButton.addEventListener('click', function() {
    const content = editor.values.content;
    if (!content) {
      alert('Nothing to copy!');
      return;
    }
    editor.textarea.select();
    navigator.clipboard.writeText(content)
      .then(() => flash(copyButton, '<i class="fas fa-check"></i> Copied!', 'btn-primary', 2000))
      .catch(error => {
        console.error('Copy failed:', error);
        alert('Failed to copy to clipboard');
      });
  });

  const useButton = document.getElementById('useInSubmitForm');
  useButton.addEventListener('click', function(e) {
    e.preventDefault();
    const { title, content } = editor.values;
    if (!content.trim()) {
      alert('Please write some content first!');
      return;
    }
    drafts.set(fields.content, content);
    if (title) drafts.set(fields.title, title);
    flash(useButton, '<i class="fas fa-check"></i> Saved!', 'btn-danger', 500, () => {
      window.location.href = useButton.href;
    });
  });
});
