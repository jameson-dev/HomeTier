// WebSocket Client for Real-time Updates

class HomeTierRealtime {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.heartbeatInterval = null;
        
        this.initializeConnection();
        this.setupEventHandlers();
    }
    
    initializeConnection() {
        try {
            this.socket = io({
                transports: ['websocket', 'polling'],
                upgrade: true,
                rememberUpgrade: true
            });
            
            this.setupSocketEvents();
        } catch (error) {
            console.error('Failed to initialize WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }
    
    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Connected to HomeTier real-time server');
            this.connected = true;
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            
            this.showConnectionStatus('connected');
            this.requestInitialData();
            this.startHeartbeat();
        });
        
        this.socket.on('disconnect', (reason) => {
            console.log('Disconnected from server:', reason);
            this.connected = false;
            this.showConnectionStatus('disconnected');
            this.stopHeartbeat();
            
            // Auto-reconnect unless disconnected intentionally
            if (reason !== 'io client disconnect') {
                this.scheduleReconnect();
            }
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.connected = false;
            this.showConnectionStatus('error');
            this.scheduleReconnect();
        });
        
        // Real-time event handlers
        this.socket.on('device_status_changes', (data) => {
            this.handleDeviceStatusChanges(data);
        });
        
        this.socket.on('device_status_counts', (data) => {
            this.updateDeviceStatusCounts(data);
        });
        
        this.socket.on('new_devices_discovered', (data) => {
            this.handleNewDevicesDiscovered(data);
        });
        
        this.socket.on('scan_started', (data) => {
            this.handleScanStarted(data);
        });
        
        this.socket.on('scan_progress', (data) => {
            this.handleScanProgress(data);
        });
        
        this.socket.on('scan_completed', (data) => {
            this.handleScanCompleted(data);
        });
        
        this.socket.on('scan_error', (data) => {
            this.handleScanError(data);
        });
        
        this.socket.on('inventory_updated', (data) => {
            this.handleInventoryUpdate(data);
        });
    }
    
    setupEventHandlers() {
        // Add connection status indicator to UI
        this.createConnectionStatusIndicator();
        
        // Override scan button to use WebSocket
        const scanBtn = document.getElementById('scan-btn');
        if (scanBtn) {
            scanBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.startNetworkScan();
            });
        }
    }
    
    createConnectionStatusIndicator() {
        // Add connection status to navbar
        const navbar = document.querySelector('.navbar-nav');
        if (navbar) {
            const statusItem = document.createElement('li');
            statusItem.className = 'nav-item';
            statusItem.innerHTML = `
                <div class="nav-link" id="connection-status">
                    <i class="fas fa-circle" id="status-icon"></i>
                    <span id="status-text">Connecting...</span>
                </div>
            `;
            navbar.appendChild(statusItem);
        }
    }
    
    showConnectionStatus(status) {
        const statusIcon = document.getElementById('status-icon');
        const statusText = document.getElementById('status-text');
        
        if (!statusIcon || !statusText) return;
        
        switch (status) {
            case 'connected':
                statusIcon.className = 'fas fa-circle text-success';
                statusText.textContent = 'Live';
                statusText.className = 'text-success';
                break;
            case 'disconnected':
                statusIcon.className = 'fas fa-circle text-warning';
                statusText.textContent = 'Reconnecting...';
                statusText.className = 'text-warning';
                break;
            case 'error':
                statusIcon.className = 'fas fa-circle text-danger';
                statusText.textContent = 'Offline';
                statusText.className = 'text-danger';
                break;
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached');
            this.showConnectionStatus('error');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            if (!this.connected) {
                this.socket.connect();
            }
        }, delay);
    }
    
    requestInitialData() {
        if (this.connected) {
            this.socket.emit('request_device_status');
        }
    }
    
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (this.connected) {
                this.socket.emit('ping');
            }
        }, 30000); // Ping every 30 seconds
    }
    
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    // Event Handlers
    handleDeviceStatusChanges(data) {
        console.log('Device status changes:', data);
        
        data.changes.forEach(change => {
            // Show notification for significant changes
            if (change.old_status === 'online' && change.new_status === 'offline') {
                showNotification(
                    `Device went offline: ${change.device_info.hostname || change.device_info.ip_address}`,
                    'warning'
                );
            } else if (change.old_status === 'offline' && change.new_status === 'online') {
                showNotification(
                    `Device came online: ${change.device_info.hostname || change.device_info.ip_address}`,
                    'success'
                );
            }
            
            // Update device row in table if visible
            this.updateDeviceRowStatus(change.device_id, change.new_status);
        });
        
        // Update charts if they exist
        this.updateChartsFromRealtime();
    }
    
    updateDeviceStatusCounts(counts) {
    // Update status count displays
        const onlineCount = document.getElementById('online-count');
        const offlineCount = document.getElementById('offline-count');
        const unknownCount = document.getElementById('unknown-count');
        
        if (onlineCount) onlineCount.textContent = counts.online || 0;
        if (offlineCount) offlineCount.textContent = counts.offline || 0;
        if (unknownCount) unknownCount.textContent = counts.unknown || 0;
        
        // Update device status chart if it exists and is properly initialized
        if (typeof deviceStatusChart !== 'undefined' && 
            deviceStatusChart && 
            deviceStatusChart.data && 
            deviceStatusChart.data.datasets && 
            deviceStatusChart.data.datasets[0]) {
            deviceStatusChart.data.datasets[0].data = [
                counts.online || 0,
                counts.offline || 0,
                counts.unknown || 0
            ];
            deviceStatusChart.update('none'); // No animation for real-time updates
        }
    }
    
    handleNewDevicesDiscovered(data) {
        console.log('New devices discovered:', data);
        
        // Show notification
        if (data.count === 1) {
            const device = data.devices[0];
            showNotification(
                `New device discovered: ${device.hostname || device.ip_address}`,
                'info'
            );
        } else {
            showNotification(
                `${data.count} new devices discovered`,
                'info'
            );
        }
        
        // Update device count
        const newDevicesCount = document.getElementById('new-devices-count');
        if (newDevicesCount) {
            const currentCount = parseInt(newDevicesCount.textContent) || 0;
            newDevicesCount.textContent = currentCount + data.count;
        }
        
        // Refresh device table if on scanning page
        if (window.location.pathname.includes('scanning')) {
            setTimeout(() => {
                loadRecentDevices();
            }, 1000);
        }
        
        // Add to activity feed if visible
        this.addToActivityFeed({
            type: 'device_discovered',
            count: data.count,
            devices: data.devices,
            timestamp: data.timestamp
        });
    }
    
    handleScanStarted(data) {
        console.log('Scan started:', data);
        
        // Update scan button
        const scanBtn = document.getElementById('scan-btn');
        if (scanBtn) {
            scanBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Scanning...';
            scanBtn.disabled = true;
        }
        
        // Show progress bar
        const scanProgress = document.getElementById('scan-progress');
        if (scanProgress) {
            scanProgress.style.display = 'block';
        }
        
        showNotification('Network scan started', 'info');
    }
    
    handleScanProgress(data) {
        console.log('Scan progress:', data);
        
        // Update progress bar
        const progressBar = document.querySelector('#scan-progress .progress-bar');
        if (progressBar) {
            progressBar.style.width = `${data.progress}%`;
            progressBar.textContent = data.message || `${data.progress}%`;
        }
    }
    
    handleScanCompleted(data) {
        console.log('Scan completed:', data);
        
        // Reset scan button
        const scanBtn = document.getElementById('scan-btn');
        if (scanBtn) {
            scanBtn.innerHTML = '<i class="fas fa-search me-2"></i>Start Manual Scan';
            scanBtn.disabled = false;
        }
        
        // Hide progress bar
        const scanProgress = document.getElementById('scan-progress');
        if (scanProgress) {
            scanProgress.style.display = 'none';
        }
        
        showNotification(
            `Scan completed! Found ${data.devices_found || 0} devices.`,
            'success'
        );
        
        // Refresh data
        if (window.location.pathname.includes('scanning')) {
            loadScanningData();
            loadRecentDevices();
        } else {
            loadDashboardData();
        }
    }
    
    handleScanError(data) {
        console.error('Scan error:', data);
        
        // Reset scan button
        const scanBtn = document.getElementById('scan-btn');
        if (scanBtn) {
            scanBtn.innerHTML = '<i class="fas fa-search me-2"></i>Start Manual Scan';
            scanBtn.disabled = false;
        }
        
        // Hide progress bar
        const scanProgress = document.getElementById('scan-progress');
        if (scanProgress) {
            scanProgress.style.display = 'none';
        }
        
        showNotification(`Scan failed: ${data.message}`, 'danger');
    }
    
    handleInventoryUpdate(data) {
        console.log('Inventory updated:', data);
        
        // Show notification
        showNotification('Inventory updated', 'success');
        
        // Refresh inventory if on inventory page
        if (window.location.pathname.includes('inventory')) {
            setTimeout(() => {
                loadInventoryData();
            }, 500);
        }
        
        // Update dashboard counts
        const inventoryCount = document.getElementById('inventory-count');
        if (inventoryCount && data.action === 'added') {
            const currentCount = parseInt(inventoryCount.textContent) || 0;
            inventoryCount.textContent = currentCount + 1;
        }
    }
    
    // Utility methods
    updateDeviceRowStatus(deviceId, status) {
        const deviceRow = document.querySelector(`tr[data-device-id="${deviceId}"]`);
        if (!deviceRow) return;
        
        const statusCell = deviceRow.querySelector('.badge');
        if (statusCell) {
            // Update status badge
            statusCell.className = 'badge';
            switch (status) {
                case 'online':
                    statusCell.classList.add('bg-success');
                    statusCell.textContent = 'Online';
                    break;
                case 'offline':
                    statusCell.classList.add('bg-danger');
                    statusCell.textContent = 'Offline';
                    break;
                case 'unknown':
                    statusCell.classList.add('bg-warning');
                    statusCell.textContent = 'Unknown';
                    break;
            }
            
            // Add flash effect
            statusCell.style.animation = 'flash 0.5s ease-in-out';
            setTimeout(() => {
                statusCell.style.animation = '';
            }, 500);
        }
    }
    
    updateChartsFromRealtime() {
        // Update charts without full data reload, but only if they exist
        if (typeof loadChartData === 'function') {
            // Only load chart data if we're on a page that has charts
            if (document.getElementById('deviceStatusChart') || 
                document.getElementById('categoryChart') || 
                document.getElementById('discoveryTimelineChart')) {
                loadChartData();
            }
        }
    }
    
    addToActivityFeed(activity) {
        const activityFeed = document.getElementById('recent-activity');
        if (!activityFeed) return;
        
        let activityHtml = '';
        
        switch (activity.type) {
            case 'device_discovered':
                const deviceName = activity.devices[0]?.hostname || activity.devices[0]?.ip_address || 'Unknown';
                activityHtml = `
                    <div class="mb-3 pb-2 border-bottom new-activity">
                        <div class="d-flex align-items-center">
                            <div class="bg-primary text-white rounded-circle me-3 d-flex align-items-center justify-content-center" style="width: 32px; height: 32px;">
                                <i class="fas fa-wifi fa-sm"></i>
                            </div>
                            <div>
                                <strong>Device Discovered</strong>
                                <br><small class="text-muted">${deviceName}</small>
                            </div>
                        </div>
                        <div class="mt-1">
                            <small class="text-muted">Just now</small>
                        </div>
                    </div>
                `;
                break;
        }
        
        if (activityHtml) {
            activityFeed.insertAdjacentHTML('afterbegin', activityHtml);
            
            // Remove animation class after a delay
            setTimeout(() => {
                const newActivity = activityFeed.querySelector('.new-activity');
                if (newActivity) {
                    newActivity.classList.remove('new-activity');
                }
            }, 3000);
            
            // Limit to 10 activities
            const activities = activityFeed.querySelectorAll('.mb-3');
            if (activities.length > 10) {
                activities[activities.length - 1].remove();
            }
        }
    }
    
    // Public methods
    startNetworkScan() {
        if (this.connected) {
            this.socket.emit('start_network_scan');
        } else {
            showNotification('Not connected to real-time server. Using fallback scan.', 'warning');
            startNetworkScan(); // Fallback to HTTP scan
        }
    }
    
    disconnect() {
        this.connected = false;
        this.stopHeartbeat();
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// CSS for real-time effects
const realtimeStyles = `
<style>
@keyframes flash {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.new-activity {
    background: linear-gradient(90deg, rgba(0,123,255,0.1) 0%, transparent 100%);
    animation: slideInRight 0.5s ease-out;
    border-left: 3px solid #007bff !important;
}

@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

#connection-status {
    font-size: 0.875rem;
    padding: 0.25rem 0.5rem;
}

#status-icon {
    font-size: 0.75rem;
    margin-right: 0.25rem;
}

.status-pulse {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}
</style>
`;

// Add styles to head
document.head.insertAdjacentHTML('beforeend', realtimeStyles);

// Initialize real-time connection when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if Socket.IO is available
    if (typeof io !== 'undefined') {
        window.homeTierRealtime = new HomeTierRealtime();
        console.log('HomeTier real-time features enabled');
    } else {
        console.warn('Socket.IO not available. Real-time features disabled.');
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.homeTierRealtime) {
        window.homeTierRealtime.disconnect();
    }
});