/**
 * Article list and draft view (samples/article_list.html, samples/article_view.html)
 * <button data-publish-article="<id>" data-article-title="..."> opens the publish modal
 * (samples/_publish_modal.html, js/publish-article.js). Unpublish/delete are data-post-url
 * buttons and forms with data-confirm (js/utils.js).
 */
document.addEventListener('click', function(e) {
  const button = e.target.closest('[data-publish-article]');
  if (!button || typeof window.openPublishModal !== 'function') return;
  e.preventDefault();
  window.openPublishModal(button.dataset.publishArticle, button.dataset.articleTitle);
});
