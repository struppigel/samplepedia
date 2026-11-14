/**
 * Markdown editor (sp.MarkdownEditor): Write/Preview tabs with a server-rendered
 * preview and, as configured, a title, character count, image upload, keyboard
 * shortcuts, autosave and checks before the surrounding form is submitted.
 * Every [data-md-editor] is set up on DOMContentLoaded; page scripts get one with
 * sp.MarkdownEditor.get(element). Needs js/utils.js and js/drafts.js (base.html).
 *
 *   <div data-md-editor data-preview-url="{% url 'markdown_preview' %}"
 *        data-upload-url="..."        image upload: a [data-md-upload] button opens a
 *                                     [data-md-upload-input] file input
 *        data-shortcuts               Tab indents, Ctrl/Cmd+S shows the preview
 *        data-draft="article:new"     autosave under this draft name (js/drafts.js) ...
 *        data-autosave="5"            ... every n seconds (default 5) and on leaving the page
 *        data-draft-max-age="24"      drop drafts older than n hours (default: keep them)
 *        data-draft-restore="silent"  restore a draft without asking (default: ask)
 *        data-required>               the surrounding form needs a title and content
 *     .markdown-tab[data-tab="write|preview|help"] and .markdown-pane[data-pane="..."]
 *     <textarea>                      the content (the editor's first textarea)
 *     <div data-md-preview>           where the preview is rendered
 *     optional: <input data-md-title>, [data-md-title-error], [data-md-count] (character
 *               count), [data-md-preview-header] (its <h1> shows the title)
 *   </div>
 *
 *   <button data-md-clear>  empty the editor and forget its draft (outside an editor it
 *                           acts on the page's first one)
 */
window.sp.MarkdownEditor = (function() {
  'use strict';

  const EMPTY_PREVIEW = '<p class="text-muted">Nothing to preview</p>';
  const LOADING_PREVIEW = '<p class="text-muted"><i class="fas fa-spinner fa-spin"></i> Loading preview...</p>';
  const PREVIEW_ERROR = '<p class="text-danger"><i class="fas fa-exclamation-triangle"></i> Error loading preview</p>';
  const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
  const MAX_IMAGE_SIZE = 5 * 1024 * 1024;
  const editors = new WeakMap();

  function isEmpty(values) {
    return !values.title.trim() && !values.content.trim();
  }

  function isSame(a, b) {
    return a.title.trim() === b.title.trim() && a.content.trim() === b.content.trim();
  }

  function toast(message, success) {
    const toastEl = document.createElement('div');
    toastEl.className = `alert alert-${success ? 'success' : 'danger'} alert-dismissible fade show upload-toast`;
    toastEl.innerHTML = `<i class="fas fa-${success ? 'check-circle' : 'exclamation-circle'}"></i> <span></span>
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
    // The message can contain server error text: insert it as text, not HTML
    toastEl.querySelector('span').textContent = message;
    document.body.appendChild(toastEl);
    setTimeout(() => toastEl.remove(), 5000);
  }

  class MarkdownEditor {
    static get(root) {
      let editor = editors.get(root);
      if (!editor) {
        editor = new MarkdownEditor(root);
        editors.set(root, editor);
      }
      return editor;
    }

    constructor(root) {
      this.root = root;
      this.textarea = root.querySelector('textarea');
      this.titleInput = root.querySelector('[data-md-title]');
      this.preview = root.querySelector('[data-md-preview]');
      this.previewTitle = root.querySelector('[data-md-preview-header] h1');
      this.untitled = this.previewTitle ? this.previewTitle.textContent.trim() : '';
      this.count = root.querySelector('[data-md-count]');
      this.renderedContent = null; // the content the preview shows

      root.querySelectorAll('.markdown-tab').forEach(tab => {
        tab.addEventListener('click', () => this.showTab(tab.dataset.tab));
      });
      this.textarea.addEventListener('input', () => this.updateCount());
      if (this.titleInput) {
        this.titleInput.addEventListener('input', () => this.updateTitle());
      }
      if ('shortcuts' in root.dataset) {
        this.textarea.addEventListener('keydown', e => this.onKeydown(e));
      }
      this.setUpUpload();
      this.setUpForm();
      this.setUpDraft();
      this.updateCount();
      this.updateTitle();
    }

    get values() {
      return {
        title: this.titleInput ? this.titleInput.value : '',
        content: this.textarea.value
      };
    }

    setValues({ title = '', content = '' }) {
      if (this.titleInput) this.titleInput.value = title;
      this.textarea.value = content;
      this.updateCount();
      this.updateTitle();
      if (this.activePane() === 'preview') this.renderPreview();
    }

    clear() {
      this.setValues({});
      if (this.draft) {
        window.sp.drafts.clear(this.draft);
        this.savedValues = this.values;
      }
    }

    updateCount() {
      if (!this.count) return;
      const count = this.textarea.value.length;
      this.count.textContent = `${count.toLocaleString()} character${count !== 1 ? 's' : ''}`;
    }

    updateTitle() {
      if (this.previewTitle && this.titleInput) {
        this.previewTitle.textContent = this.titleInput.value.trim() || this.untitled;
      }
    }

    activePane() {
      const pane = this.root.querySelector('.markdown-pane.active');
      return pane ? pane.dataset.pane : null;
    }

    showTab(name) {
      this.root.querySelectorAll('.markdown-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === name);
      });
      this.root.querySelectorAll('.markdown-pane').forEach(pane => {
        pane.classList.toggle('active', pane.dataset.pane === name);
      });
      if (name === 'preview') this.renderPreview();
    }

    async renderPreview() {
      const content = this.textarea.value;
      if (content === this.renderedContent) return;
      this.renderedContent = content;
      if (!content.trim()) {
        this.preview.innerHTML = EMPTY_PREVIEW;
        return;
      }
      this.preview.innerHTML = LOADING_PREVIEW;
      try {
        const data = await window.sp.fetchJSON(this.root.dataset.previewUrl, { method: 'POST', data: { content } });
        // A slow answer for older content must not replace a newer preview
        if (this.renderedContent === content) this.preview.innerHTML = data.html;
      } catch (error) {
        console.error('Preview error:', error);
        if (this.renderedContent === content) {
          this.preview.innerHTML = PREVIEW_ERROR;
          this.renderedContent = null;
        }
      }
    }

    // Replace the selection with text, as typing would
    insert(text) {
      this.textarea.setRangeText(text, this.textarea.selectionStart, this.textarea.selectionEnd, 'end');
      this.textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    onKeydown(e) {
      if (e.key === 'Tab') {
        e.preventDefault();
        this.insert('  ');
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        this.showTab('preview');
      }
    }

    setUpUpload() {
      const button = this.root.querySelector('[data-md-upload]');
      const input = this.root.querySelector('[data-md-upload-input]');
      if (!button || !input || !this.root.dataset.uploadUrl) return;
      button.addEventListener('click', () => input.click());
      input.addEventListener('change', () => {
        const file = input.files[0];
        input.value = '';
        if (file) this.upload(file, button);
      });
    }

    async upload(file, button) {
      if (!IMAGE_TYPES.includes(file.type)) {
        alert('Invalid file type. Please select a JPEG, PNG, GIF, or WEBP image.');
        return;
      }
      if (file.size > MAX_IMAGE_SIZE) {
        alert('File is too large. Maximum size is 5MB.');
        return;
      }
      const label = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
      try {
        const data = new FormData();
        data.append('image', file);
        const result = await window.sp.fetchJSON(this.root.dataset.uploadUrl, { method: 'POST', data });
        if (!result.success || !result.url) throw new Error(result.error || 'Upload failed');
        // The file name without its extension is the alt text
        this.insert(`![${file.name.replace(/\.[^/.]+$/, '')}](${result.url})`);
        this.textarea.focus();
        toast('Image uploaded successfully!', true);
      } catch (error) {
        console.error('Upload error:', error);
        toast('Upload failed: ' + error.message, false);
      } finally {
        button.disabled = false;
        button.innerHTML = label;
      }
    }

    setUpForm() {
      const form = this.root.closest('form');
      if (!form) return;
      if (this.titleInput) {
        // Enter in the title moves on to the content instead of submitting
        this.titleInput.addEventListener('keydown', e => {
          if (e.key === 'Enter') {
            e.preventDefault();
            this.textarea.focus();
          }
        });
      }
      if ('required' in this.root.dataset) {
        form.addEventListener('submit', e => this.checkBeforeSubmit(e));
      }
    }

    checkBeforeSubmit(event) {
      const { title, content } = this.values;
      const titleError = this.root.querySelector('[data-md-title-error]');
      if (this.titleInput && !title.trim()) {
        event.preventDefault();
        if (titleError) {
          titleError.textContent = 'Title is required';
          window.sp.show(titleError, true);
        }
        this.titleInput.focus();
        return;
      }
      window.sp.show(titleError, false);
      if (!content.trim()) {
        event.preventDefault();
        alert('Please write some content first.');
        this.showTab('write');
        this.textarea.focus();
        return;
      }
      // The draft is kept until the server has saved it (see js/drafts.js)
      this.saveDraft();
      if (event.submitter) {
        event.submitter.disabled = true;
        event.submitter.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
      }
    }

    setUpDraft() {
      const name = this.root.dataset.draft;
      if (!name) return;
      this.draft = name;
      const drafts = window.sp.drafts;
      const saved = drafts.load(name);
      const maxAge = Number(this.root.dataset.draftMaxAge || 0) * 60 * 60 * 1000;
      if (saved && maxAge && saved.savedAt && Date.now() - saved.savedAt > maxAge) {
        drafts.clear(name);
      } else if (saved && !isEmpty(saved) && !isSame(saved, this.values)) {
        if (this.root.dataset.draftRestore === 'silent'
            || confirm('Found auto-saved content. Would you like to restore it?')) {
          this.setValues(saved);
        } else {
          drafts.clear(name);
        }
      }
      this.savedValues = this.values;
      const seconds = Number(this.root.dataset.autosave) || 5;
      setInterval(() => this.saveDraft(), seconds * 1000);
      window.addEventListener('pagehide', () => this.saveDraft());
    }

    saveDraft() {
      if (!this.draft) return;
      const values = this.values;
      if (isEmpty(values) || isSame(values, this.savedValues)) return;
      window.sp.drafts.save(this.draft, values);
      this.savedValues = values;
    }
  }

  document.addEventListener('click', function(e) {
    const button = e.target.closest('[data-md-clear]');
    if (!button) return;
    const root = button.closest('[data-md-editor]') || document.querySelector('[data-md-editor]');
    if (!root) return;
    const editor = MarkdownEditor.get(root);
    if (isEmpty(editor.values) || confirm('Are you sure you want to clear all content?')) {
      editor.clear();
    }
  });

  function init() {
    document.querySelectorAll('[data-md-editor]').forEach(root => MarkdownEditor.get(root));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  return MarkdownEditor;
})();
