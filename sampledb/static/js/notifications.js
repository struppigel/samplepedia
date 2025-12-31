/**
 * Notifications functionality
 * - Polls for unread notification count every 60 seconds
 * - Updates bell icon badge
 * - Loads notifications into dropdown when clicked
 */

(function() {
    'use strict';
    
    const POLL_INTERVAL = 60000; // 60 seconds
    let pollTimer = null;
    let dropdownLoaded = false;
    
    /**
     * Update the notification badge with current count
     */
    function updateBadge(count) {
        const badge = document.getElementById('notificationBadge');
        const countSpan = document.getElementById('notificationCount');
        const pluralSpan = document.getElementById('notificationPlural');
        
        if (badge && countSpan) {
            if (count > 0) {
                badge.textContent = count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
            
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
        fetch('/notifications/unread-count/')
            .then(response => response.json())
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
        if (!listContainer) return;
        
        fetch('/notifications/dropdown/')
            .then(response => response.json())
            .then(data => {
                dropdownLoaded = true;
                
                if (data.notifications.length === 0) {
                    listContainer.innerHTML = `
                        <div class="dropdown-item text-center text-muted">
                            No new notifications
                        </div>
                    `;
                } else {
                    let html = '';
                    data.notifications.forEach(notification => {
                        const timeAgo = formatTimeAgo(new Date(notification.timestamp));
                        let icon = '';
                        
                        if (notification.description.includes('liked')) {
                            icon = '<i class="fas fa-heart text-danger mr-2"></i>';
                        } else if (notification.description.includes('commented')) {
                            icon = '<i class="fas fa-comment text-info mr-2"></i>';
                        } else if (notification.description.includes('solution')) {
                            icon = '<i class="fas fa-lightbulb text-warning mr-2"></i>';
                        }
                        
                        html += `
                            <a href="/notifications/${notification.id}/read/" class="dropdown-item">
                                ${icon}
                                <span>${notification.description}</span>
                                ${notification.sha256 ? `<span class="text-muted small d-block">[SHA256: ${notification.sha256}...]</span>` : ''}
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
        
        // Load notifications when dropdown is clicked
        const notificationBell = document.getElementById('notificationBell');
        if (notificationBell) {
            notificationBell.addEventListener('click', function(e) {
                loadNotifications();
            });
        }
        
        // Reset dropdown loaded flag when dropdown is closed
        $('#notificationDropdown').parent().on('hide.bs.dropdown', function() {
            // Don't reset - keep loaded for better UX
            // dropdownLoaded = false;
        });
        
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
