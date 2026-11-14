/**
 * "Comment deleted" page (comments/deleted.html)
 * <a data-follow-after="1000" href="..."> is followed automatically after that many milliseconds.
 */
document.querySelectorAll('a[data-follow-after]').forEach(function(link) {
  setTimeout(function() {
    window.location.href = link.href;
  }, Number(link.dataset.followAfter) || 0);
});
