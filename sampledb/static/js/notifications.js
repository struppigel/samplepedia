/**
 * Notifications functionality
 * - Polls for unread notification count every 60 seconds
 * - Updates bell icon badge
 * - Loads notifications into dropdown when clicked
 * URLs come from the bell (base.html): data-dropdown-url and data-unread-count-url;
 * each dropdown item links to the read_url the server sends with it.
 */

(function() {
    'use strict';
    
    const POLL_INTERVAL = 60000; // 60 seconds
    let pollTimer = null;
    let dropdownLoaded = false;

    /** An endpoint URL from the bell's data-* attribute (rendered with {% url %} in base.html) */
    function endpointUrl(attribute) {
        const bell = document.getElementById('notificationBell');
        return bell ? bell.dataset[attribute] : null;
    }
    
    /**
     * Update the notification badge with current count
     */
    function updateBadge(count) {
        const badge = document.getElementById('notificationBadge');
        const countSpan = document.getElementById('notificationCount');
        const pluralSpan = document.getElementById('notificationPlural');
        
        if (badge && countSpan) {
            badge.textContent = count;
            badge.hidden = !(count > 0);
            
            countSpan.textContent = count;
            if (pluralSpan) {
                pluralSpan.textContent = count === 1 ? '' : 's';
            }
        }
    }
    
    /**
     * Poll the server for unread notification count
     */
    function pollNotificationCount() {
        const url = endpointUrl('unreadCountUrl');
        if (!url) return;
        window.sp.fetchJSON(url)
            .then(data => {
                updateBadge(data.unread_count);
            })
            .catch(error => {
                console.error('Error polling notifications:', error);
            });
    }
    
    /**
     * Load notifications into dropdown
     */
    function loadNotifications() {
        if (dropdownLoaded) {
            return; // Already loaded
        }
        
        const listContainer = document.getElementById('notificationList');
        const url = endpointUrl('dropdownUrl');
        if (!listContainer || !url) return;
        
        window.sp.fetchJSON(url)
            .then(data => {
                dropdownLoaded = true;
                
                if (data.notifications.length === 0) {
                    listContainer.innerHTML = `
                        <div class="dropdown-item text-center text-muted">
                            No new notifications
                        </div>
                    `;
                } else {
                    const escapeHtml = window.sp.escapeHtml;
                    let html = '';
                    data.notifications.forEach(notification => {
                        const timeAgo = formatTimeAgo(new Date(notification.timestamp));
                        // The server picks the icon from the notification's verb
                        const icon = `<i class="${escapeHtml(notification.icon)} me-2"></i>`;

                        // Descriptions contain user-provided text (usernames, titles): always escape
                        html += `
                            <a href="${escapeHtml(notification.read_url)}" class="dropdown-item">
                                ${icon}
                                <span>${escapeHtml(notification.description)}</span>
                                ${notification.sha256 ? `<span class="text-muted small d-block">[SHA256: ${escapeHtml(notification.sha256)}...]</span>` : ''}
                                <span class="text-muted small d-block">
                                    <i class="far fa-clock"></i> ${timeAgo}
                                </span>
                            </a>
                        `;
                    });
                    
                    listContainer.innerHTML = html;
                }
                
                updateBadge(data.unread_count);
            })
            .catch(error => {
                console.error('Error loading notifications:', error);
                listContainer.innerHTML = `
                    <div class="dropdown-item text-center text-danger">
                        Error loading notifications
                    </div>
                `;
            });
    }
    
    /**
     * Format timestamp as relative time (e.g., "5 minutes ago")
     */
    function formatTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        
        const intervals = {
            year: 31536000,
            month: 2592000,
            week: 604800,
            day: 86400,
            hour: 3600,
            minute: 60
        };
        
        for (const [unit, secondsInUnit] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / secondsInUnit);
            if (interval >= 1) {
                return `${interval} ${unit}${interval === 1 ? '' : 's'} ago`;
            }
        }
        
        return 'just now';
    }
    
    /**
     * Initialize notification functionality
     */
    function init() {
        // Start polling for notification count
        pollTimer = setInterval(pollNotificationCount, POLL_INTERVAL);
        
        // Load notifications when dropdown is clicked (kept loaded afterwards)
        const notificationBell = document.getElementById('notificationBell');
        if (notificationBell) {
            notificationBell.addEventListener('click', function(e) {
                loadNotifications();
            });
        }

        // Do an initial poll after 5 seconds
        setTimeout(pollNotificationCount, 5000);
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Clean up timer when page unloads
    window.addEventListener('beforeunload', function() {
        if (pollTimer) {
            clearInterval(pollTimer);
        }
    });
    
})();
