/**
 * WhatsApp AI Dashboard JavaScript
 * Handles dynamic content updates, AJAX calls, and user interactions
 */

class WhatsAppDashboard {
    constructor() {
        this.autoRefreshInterval = null;
        this.notificationPermission = null;
        this.lastMessageCount = 0;
        this.init();
    }

    init() {
        this.requestNotificationPermission();
        this.setupEventListeners();
        this.initializeTooltips();
        this.checkForUpdates();
        
        // Start auto-refresh for dashboard pages
        if (this.isDashboardPage()) {
            this.startAutoRefresh();
        }
    }

    isDashboardPage() {
        const path = window.location.pathname;
        return path === '/' || path.includes('/conversation/') || path.includes('/conversations');
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('conversationSearch');
        if (searchInput) {
            let searchTimeout;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.searchConversations(e.target.value);
                }, 300);
            });
        }

        // Filter buttons
        document.querySelectorAll('[data-filter]').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const filter = e.target.dataset.filter;
                this.filterConversations(filter);
            });
        });

        // Pagination
        document.querySelectorAll('[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = e.target.dataset.page;
                this.loadPage(page);
            });
        });

        // Message actions
        document.querySelectorAll('[data-action]').forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const action = e.target.dataset.action;
                const messageId = e.target.dataset.messageId;
                this.handleMessageAction(action, messageId);
            });
        });

        // Media viewer
        document.querySelectorAll('.media-thumbnail').forEach(img => {
            img.addEventListener('click', (e) => {
                this.openMediaViewer(e.target.src, e.target.alt);
            });
        });

        // Copy to clipboard
        document.querySelectorAll('[data-copy]').forEach(button => {
            button.addEventListener('click', (e) => {
                const text = e.target.dataset.copy;
                this.copyToClipboard(text);
            });
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });

        // Window visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pauseAutoRefresh();
            } else {
                this.resumeAutoRefresh();
            }
        });
    }

    initializeTooltips() {
        // Initialize Bootstrap tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Auto-refresh functionality
    startAutoRefresh(interval = 30000) {
        this.stopAutoRefresh();
        this.autoRefreshInterval = setInterval(() => {
            this.refreshContent();
        }, interval);
    }

    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }

    pauseAutoRefresh() {
        this.stopAutoRefresh();
    }

    resumeAutoRefresh() {
        if (this.isDashboardPage()) {
            this.startAutoRefresh();
        }
    }

    async refreshContent() {
        try {
            if (window.location.pathname === '/') {
                await this.refreshDashboardStats();
                await this.refreshRecentActivity();
            } else if (window.location.pathname.includes('/conversation/')) {
                await this.refreshConversationMessages();
            } else if (window.location.pathname.includes('/conversations')) {
                await this.refreshConversationsList();
            }
        } catch (error) {
            console.error('Error refreshing content:', error);
        }
    }

    async refreshDashboardStats() {
        try {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            if (data.error) {
                console.error('Stats API error:', data.error);
                return;
            }

            this.updateStatsCards(data);
            this.checkForNewMessages(data.totals.messages);
        } catch (error) {
            console.error('Error refreshing dashboard stats:', error);
        }
    }

    updateStatsCards(data) {
        const totals = data.totals || {};
        
        // Update stats cards
        const statsCards = {
            'total-conversations': totals.conversations || 0,
            'total-messages': totals.messages || 0,
            'total-media': totals.media_files || 0,
            'active-conversations': totals.active_conversations || 0
        };

        Object.entries(statsCards).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                this.animateNumber(element, parseInt(element.textContent) || 0, value);
            }
        });

        // Update success rates if available
        if (data.success_rates) {
            const processingRate = document.getElementById('processing-rate');
            const responseRate = document.getElementById('response-rate');
            
            if (processingRate) {
                processingRate.textContent = `${data.success_rates.processing.toFixed(1)}%`;
            }
            if (responseRate) {
                responseRate.textContent = `${data.success_rates.ai_responses.toFixed(1)}%`;
            }
        }
    }

    animateNumber(element, start, end, duration = 1000) {
        if (start === end) return;
        
        const range = end - start;
        const startTime = Date.now();
        
        const updateNumber = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const current = Math.floor(start + (range * progress));
            
            element.textContent = current;
            
            if (progress < 1) {
                requestAnimationFrame(updateNumber);
            }
        };
        
        updateNumber();
    }

    checkForNewMessages(currentCount) {
        if (this.lastMessageCount > 0 && currentCount > this.lastMessageCount) {
            const newMessages = currentCount - this.lastMessageCount;
            this.showNotification(`${newMessages} new message${newMessages > 1 ? 's' : ''} received`);
        }
        this.lastMessageCount = currentCount;
    }

    async refreshRecentActivity() {
        // This would refresh the recent conversations and media sections
        // For now, we'll just update timestamps
        this.updateRelativeTimestamps();
    }

    async refreshConversationMessages() {
        const conversationId = this.getConversationIdFromUrl();
        if (!conversationId) return;

        try {
            const response = await fetch(`/api/conversation/${conversationId}/messages?per_page=50`);
            const data = await response.json();
            
            if (data.error) {
                console.error('Messages API error:', data.error);
                return;
            }

            // Check for new messages and update if needed
            this.updateMessagesIfNeeded(data.messages);
        } catch (error) {
            console.error('Error refreshing conversation messages:', error);
        }
    }

    getConversationIdFromUrl() {
        const match = window.location.pathname.match(/\/conversation\/(\d+)/);
        return match ? match[1] : null;
    }

    updateMessagesIfNeeded(messages) {
        const container = document.getElementById('messagesContainer');
        if (!container) return;

        const currentMessages = container.querySelectorAll('.message-bubble');
        
        if (messages.length > currentMessages.length) {
            // New messages detected, refresh the page for now
            // In a more sophisticated implementation, we'd append only new messages
            const scrollPosition = container.scrollTop;
            const wasAtBottom = scrollPosition >= container.scrollHeight - container.clientHeight - 100;
            
            if (wasAtBottom) {
                setTimeout(() => {
                    this.scrollToBottom();
                }, 100);
            }
        }
    }

    async refreshConversationsList() {
        // This would update the conversations list
        this.updateRelativeTimestamps();
    }

    // Search and filtering
    async searchConversations(query) {
        const resultsContainer = document.getElementById('searchResults');
        if (!resultsContainer) return;

        if (!query.trim()) {
            resultsContainer.innerHTML = '';
            return;
        }

        try {
            const response = await fetch(`/api/conversations?search=${encodeURIComponent(query)}&per_page=10`);
            const data = await response.json();
            
            if (data.error) {
                resultsContainer.innerHTML = `<div class="alert alert-danger">Error: ${data.error}</div>`;
                return;
            }

            this.renderSearchResults(data.conversations, resultsContainer);
        } catch (error) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">Search failed: ${error.message}</div>`;
        }
    }

    renderSearchResults(conversations, container) {
        if (conversations.length === 0) {
            container.innerHTML = '<div class="text-muted p-3">No conversations found</div>';
            return;
        }

        const html = conversations.map(conv => `
            <div class="list-group-item list-group-item-action">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${conv.contact_name || 'Unknown'}</h6>
                        <p class="mb-1 text-muted small">${conv.phone_number}</p>
                        <small class="text-muted">${conv.message_count} messages</small>
                    </div>
                    <div>
                        <a href="${conv.url}" class="btn btn-sm btn-outline-primary">View</a>
                    </div>
                </div>
            </div>
        `).join('');

        container.innerHTML = html;
    }

    filterConversations(filter) {
        // Implementation for filtering conversations by type/status
        const filterButtons = document.querySelectorAll('[data-filter]');
        filterButtons.forEach(btn => btn.classList.remove('active'));
        
        const activeButton = document.querySelector(`[data-filter="${filter}"]`);
        if (activeButton) {
            activeButton.classList.add('active');
        }

        // Apply filter to conversation list
        this.applyConversationFilter(filter);
    }

    applyConversationFilter(filter) {
        const conversationRows = document.querySelectorAll('[data-conversation]');
        
        conversationRows.forEach(row => {
            const conversationData = JSON.parse(row.dataset.conversation || '{}');
            let shouldShow = true;

            switch (filter) {
                case 'active':
                    shouldShow = conversationData.is_active;
                    break;
                case 'inactive':
                    shouldShow = !conversationData.is_active;
                    break;
                case 'media':
                    shouldShow = conversationData.has_media;
                    break;
                case 'all':
                default:
                    shouldShow = true;
                    break;
            }

            row.style.display = shouldShow ? '' : 'none';
        });
    }

    // Message actions
    handleMessageAction(action, messageId) {
        switch (action) {
            case 'retry':
                this.retryMessage(messageId);
                break;
            case 'regenerate':
                this.regenerateResponse(messageId);
                break;
            case 'copy':
                this.copyMessage(messageId);
                break;
            default:
                console.warn('Unknown action:', action);
        }
    }

    async retryMessage(messageId) {
        try {
            const response = await fetch(`/api/message/${messageId}/retry`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showToast('Message retry initiated', 'success');
                setTimeout(() => this.refreshContent(), 2000);
            } else {
                this.showToast('Failed to retry message: ' + result.error, 'error');
            }
        } catch (error) {
            this.showToast('Error retrying message: ' + error.message, 'error');
        }
    }

    async regenerateResponse(messageId) {
        try {
            const response = await fetch(`/api/message/${messageId}/regenerate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();
            
            if (result.success) {
                this.showToast('Response regeneration initiated', 'success');
                setTimeout(() => this.refreshContent(), 2000);
            } else {
                this.showToast('Failed to regenerate response: ' + result.error, 'error');
            }
        } catch (error) {
            this.showToast('Error regenerating response: ' + error.message, 'error');
        }
    }

    copyMessage(messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
        if (messageElement) {
            const content = messageElement.querySelector('.message-content')?.textContent || '';
            this.copyToClipboard(content);
        }
    }

    // Utility functions
    copyToClipboard(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                this.showToast('Copied to clipboard', 'success');
            }).catch(err => {
                console.error('Failed to copy:', err);
                this.showToast('Failed to copy to clipboard', 'error');
            });
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            
            try {
                document.execCommand('copy');
                this.showToast('Copied to clipboard', 'success');
            } catch (err) {
                this.showToast('Failed to copy to clipboard', 'error');
            }
            
            document.body.removeChild(textArea);
        }
    }

    openMediaViewer(src, alt) {
        const modal = document.getElementById('mediaModal') || this.createMediaModal();
        const img = modal.querySelector('#mediaModalImg');
        const title = modal.querySelector('#mediaModalTitle');
        const download = modal.querySelector('#mediaModalDownload');

        img.src = src;
        title.textContent = alt || 'Media Preview';
        download.href = src;

        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }

    createMediaModal() {
        const modalHtml = `
            <div class="modal fade" id="mediaModal" tabindex="-1">
                <div class="modal-dialog modal-lg modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="mediaModalTitle">Media Preview</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body text-center">
                            <img id="mediaModalImg" src="" alt="Media preview" class="img-fluid">
                        </div>
                        <div class="modal-footer">
                            <a id="mediaModalDownload" href="" target="_blank" class="btn btn-primary">
                                <i data-feather="download" class="me-1"></i>
                                Download
                            </a>
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        feather.replace();
        
        return document.getElementById('mediaModal');
    }

    scrollToBottom() {
        const container = document.getElementById('messagesContainer');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    scrollToTop() {
        const container = document.getElementById('messagesContainer');
        if (container) {
            container.scrollTop = 0;
        }
    }

    updateRelativeTimestamps() {
        document.querySelectorAll('[data-timestamp]').forEach(element => {
            const timestamp = new Date(element.dataset.timestamp);
            const now = new Date();
            const diff = now - timestamp;
            
            let formatted = '';
            if (diff < 60000) { // Less than 1 minute
                formatted = 'Just now';
            } else if (diff < 3600000) { // Less than 1 hour
                formatted = Math.floor(diff / 60000) + 'm ago';
            } else if (diff < 86400000) { // Less than 1 day
                formatted = Math.floor(diff / 3600000) + 'h ago';
            } else if (diff < 604800000) { // Less than 1 week
                formatted = Math.floor(diff / 86400000) + 'd ago';
            } else {
                formatted = timestamp.toLocaleDateString();
            }
            
            element.textContent = formatted;
        });
    }

    handleKeyboardShortcuts(e) {
        // Ctrl/Cmd + R: Refresh content
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            this.refreshContent();
        }
        
        // Escape: Close modals
        if (e.key === 'Escape') {
            const openModals = document.querySelectorAll('.modal.show');
            openModals.forEach(modal => {
                const bootstrapModal = bootstrap.Modal.getInstance(modal);
                if (bootstrapModal) {
                    bootstrapModal.hide();
                }
            });
        }
        
        // Ctrl/Cmd + F: Focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            const searchInput = document.getElementById('conversationSearch');
            if (searchInput) {
                e.preventDefault();
                searchInput.focus();
            }
        }
    }

    // Notifications
    requestNotificationPermission() {
        if ('Notification' in window) {
            if (Notification.permission === 'default') {
                Notification.requestPermission().then(permission => {
                    this.notificationPermission = permission;
                });
            } else {
                this.notificationPermission = Notification.permission;
            }
        }
    }

    showNotification(message, title = 'WhatsApp AI System') {
        if (this.notificationPermission === 'granted' && document.hidden) {
            new Notification(title, {
                body: message,
                icon: '/static/img/notification-icon.png'
            });
        }
        
        // Also show in-app toast
        this.showToast(message, 'info');
    }

    showToast(message, type = 'info') {
        const toastContainer = this.getOrCreateToastContainer();
        const toast = this.createToast(message, type);
        
        toastContainer.appendChild(toast);
        
        const bootstrapToast = new bootstrap.Toast(toast);
        bootstrapToast.show();
        
        // Auto-remove after hiding
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    getOrCreateToastContainer() {
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1055';
            document.body.appendChild(container);
        }
        return container;
    }

    createToast(message, type) {
        const typeClasses = {
            success: 'text-bg-success',
            error: 'text-bg-danger',
            warning: 'text-bg-warning',
            info: 'text-bg-info'
        };

        const typeIcons = {
            success: 'check-circle',
            error: 'alert-circle',
            warning: 'alert-triangle',
            info: 'info'
        };

        const toast = document.createElement('div');
        toast.className = `toast ${typeClasses[type] || typeClasses.info}`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="toast-header">
                <i data-feather="${typeIcons[type] || typeIcons.info}" class="me-2"></i>
                <strong class="me-auto">WhatsApp AI</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;

        // Replace feather icons
        setTimeout(() => feather.replace(), 0);

        return toast;
    }

    checkForUpdates() {
        // Check if there are any pending updates or system messages
        this.updateRelativeTimestamps();
    }

    async loadPage(page) {
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('page', page);
        
        try {
            const response = await fetch(currentUrl.href);
            if (response.ok) {
                window.location.href = currentUrl.href;
            }
        } catch (error) {
            console.error('Error loading page:', error);
            this.showToast('Failed to load page', 'error');
        }
    }
}

// Global functions for backward compatibility
window.whatsappDashboard = new WhatsAppDashboard();

// Export commonly used functions to global scope
window.refreshDashboard = () => window.whatsappDashboard.refreshContent();
window.scrollToBottom = () => window.whatsappDashboard.scrollToBottom();
window.scrollToTop = () => window.whatsappDashboard.scrollToTop();
window.openImageModal = (url, title) => window.whatsappDashboard.openMediaViewer(url, title);

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('WhatsApp AI Dashboard initialized');
});
