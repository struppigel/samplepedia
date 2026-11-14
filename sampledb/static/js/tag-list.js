/**
 * Expandable tag lists (samples/_expandable_tag_list.html)
 * Tags that don't fit on the first line get .is-overflow and are summarized
 * in a "+N more" badge; hovering it expands the list (.expanded).
 */
(function() {
  'use strict';

  function lastVisibleBadge(badges) {
    for (let i = badges.length - 1; i >= 0; i--) {
      if (!badges[i].classList.contains('is-overflow')) {
        return badges[i];
      }
    }
    return null;
  }

  function checkOverflow(wrapper) {
    if (wrapper.getAttribute('data-initialized') === 'true') return;

    const content = wrapper.querySelector('.tag-list-content');
    const badges = content.querySelectorAll('.badge-tag');

    if (badges.length === 0) return;

    // Remove any existing +more badge
    const existingMoreBadge = content.querySelector('.tag-more-badge');
    if (existingMoreBadge) {
      existingMoreBadge.remove();
    }

    // Temporarily expand to check full height
    const originalMaxHeight = wrapper.style.maxHeight;
    wrapper.style.maxHeight = 'none';

    const fullHeight = wrapper.scrollHeight;
    wrapper.style.maxHeight = originalMaxHeight;

    // Check if content overflows (more than one line)
    if (fullHeight > 30) {  // Roughly 1.6em in pixels
      const firstLineBottom = badges[0].getBoundingClientRect().bottom;
      let hiddenCount = 0;

      // First pass: identify which badges overflow to second line
      badges.forEach(badge => {
        if (badge.getBoundingClientRect().top > firstLineBottom + 5) {
          badge.classList.add('is-overflow');
          hiddenCount++;
        }
      });

      if (hiddenCount > 0) {
        // Create +more badge and append it at the end
        const moreBadge = document.createElement('span');
        moreBadge.className = 'badge text-bg-secondary tag-more-badge';
        moreBadge.textContent = '+' + hiddenCount + ' more';
        content.appendChild(moreBadge);

        // If the +more badge is not on the first line, keep hiding badges from the end until it is
        while (moreBadge.getBoundingClientRect().top > firstLineBottom + 5) {
          const badge = lastVisibleBadge(badges);
          if (!badge) break; // Safety check

          badge.classList.add('is-overflow');
          hiddenCount++;
          moreBadge.textContent = '+' + hiddenCount + ' more';
        }

        // Add hover listeners to expand/collapse
        moreBadge.addEventListener('mouseenter', function() {
          wrapper.classList.add('expanded');
        });
        wrapper.addEventListener('mouseleave', function() {
          wrapper.classList.remove('expanded');
        });
      }
    }

    wrapper.setAttribute('data-initialized', 'true');
  }

  function initAll() {
    document.querySelectorAll('.tag-list-wrapper').forEach(wrapper => {
      // Small delay to ensure layout is complete
      setTimeout(() => checkOverflow(wrapper), 100);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Recalculate on window resize
  let resizeTimer;
  window.addEventListener('resize', function() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function() {
      document.querySelectorAll('.tag-list-wrapper').forEach(wrapper => {
        wrapper.setAttribute('data-initialized', 'false');
        wrapper.querySelectorAll('.badge-tag').forEach(badge => {
          badge.classList.remove('is-overflow');
        });
        const moreBadge = wrapper.querySelector('.tag-more-badge');
        if (moreBadge) moreBadge.remove();
        checkOverflow(wrapper);
      });
    }, 150);
  });
})();
