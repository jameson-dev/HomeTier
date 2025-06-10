// Main JavaScript Functions

// Global variables
let currentDevices = [];
let currentInventory = [];
let scanInProgress = false;
let currentFilter = 'all';

// Utility functions
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString();
}

function formatDateTime(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show notification`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Dashboard functions
async function loadDashboardData() {
    try {
        const [devicesResponse, inventoryResponse] = await Promise.all([
            fetch('/api/devices'),
            fetch('/api/inventory')
        ]);
        
        const devices = await devicesResponse.json();
        const inventory = await inventoryResponse.json();

        const activeDevices = devices.filter(d =>
            new Date() - new Date(d.last_seen) < 3600000 // Last hour
        ).length;

        const newDevices = devices.filter(d =>
            new Date() - new Date(d.first_seen) < 3600000 // Last hour
        ).length;

        // Safely update elements if they exist
        const activeCount = document.getElementById('active-devices-count');
        if (activeCount) activeCount.textContent = activeDevices;

        const newCount = document.getElementById('new-devices-count');
        if (newCount) newCount.textContent = newDevices;

        const inventoryCount = document.getElementById('inventory-count');
        if (inventoryCount) inventoryCount.textContent = inventory.length;

        // Update last scan time
        if (devices.length > 0) {
            const lastScan = Math.max(...devices.map(d => new Date(d.last_seen)));
            const lastScanTime = document.getElementById('last-scan-time');
            const lastScanDisplay = document.getElementById('last-scan-display');

            if (lastScanTime) lastScanTime.textContent = formatDateTime(lastScan);
            if (lastScanDisplay) lastScanDisplay.textContent = formatDateTime(lastScan);
        }

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showNotification('Error loading dashboard data', 'danger');
    }
}

async function loadCategoryStats() {
    try {
        const response = await fetch('/api/dashboard/stats');
        const stats = await response.json();
        
        const categoryStatsDiv = document.getElementById('category-stats');
        if (!categoryStatsDiv) return;

        if (stats.category_stats.length === 0) {
            categoryStatsDiv.innerHTML = '<p class="text-muted">No inventory items yet</p>';
            return;
        }

        categoryStatsDiv.innerHTML = stats.category_stats.map(item => `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span>${item.category || 'Uncategorized'}</span>
                <span class="badge bg-primary">${item.count}</span>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading category stats:', error);
        const categoryStatsDiv = document.getElementById('category-stats');
        if (categoryStatsDiv) {
            categoryStatsDiv.innerHTML = '<p class="text-danger">Error loading data</p>';
        }
    }
}

async function loadWarrantyAlerts() {
    try {
        const response = await fetch('/api/dashboard/stats');
        const stats = await response.json();
        
        const warrantyAlertsDiv = document.getElementById('warranty-alerts');
        if (!warrantyAlertsDiv) return;

        if (stats.warranty_alerts.length === 0) {
            warrantyAlertsDiv.innerHTML = '<p class="text-success"><i class="fas fa-check-circle me-2"></i>No warranty issues</p>';
            return;
        }

        warrantyAlertsDiv.innerHTML = stats.warranty_alerts.map(item => {
            const badgeClass = item.status === 'expired' ? 'bg-danger' : 'bg-warning';
            const iconClass = item.status === 'expired' ? 'fa-times-circle' : 'fa-exclamation-triangle';
            
            return `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div>
                        <strong>${item.name}</strong>
                        <br><small class="text-muted">${formatDate(item.warranty_expiry)}</small>
                    </div>
                    <span class="badge ${badgeClass}">
                        <i class="fas ${iconClass} me-1"></i>${item.status}
                    </span>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading warranty alerts:', error);
        const warrantyAlertsDiv = document.getElementById('warranty-alerts');
        if (warrantyAlertsDiv) {
            warrantyAlertsDiv.innerHTML = '<p class="text-danger">Error loading data</p>';
        }
    }
}

// Scanning page functions
async function loadScanningData() {
    try {
        const [devicesResponse, statsResponse] = await Promise.all([
            fetch('/api/devices'),
            fetch('/api/scanning/stats')
        ]);
        
        const devices = await devicesResponse.json();
        const stats = await statsResponse.json();

        // Update scan statistics
        const totalCount = document.getElementById('total-devices-count');
        if (totalCount) totalCount.textContent = stats.total_devices;

        const managedCount = document.getElementById('managed-devices-count');
        if (managedCount) managedCount.textContent = stats.managed_devices;

        const unmanagedCount = document.getElementById('unmanaged-devices-count');
        if (unmanagedCount) unmanagedCount.textContent = stats.unmanaged_devices;

        const ignoredCount = document.getElementById('ignored-devices-count');
        if (ignoredCount) ignoredCount.textContent = stats.ignored_devices;

        // Update last scan time
        if (devices.length > 0) {
            const lastScan = Math.max(...devices.map(d => new Date(d.last_seen)));
            const lastScanDisplay = document.getElementById('last-scan-display');
            if (lastScanDisplay) lastScanDisplay.textContent = formatDateTime(lastScan);
        }

    } catch (error) {
        console.error('Error loading scanning data:', error);
        showNotification('Error loading scanning data', 'danger');
    }
}

async function loadRecentDevices() {
    try {
        const [devicesResponse, inventoryResponse] = await Promise.all([
            fetch('/api/devices'),
            fetch('/api/inventory')
        ]);
        
        const devices = await devicesResponse.json();
        const inventory = await inventoryResponse.json();
        currentDevices = devices;
        currentInventory = inventory; // Make sure we update the global inventory state
        
        // Create set of device IDs already in inventory
        const inventoryDeviceIds = new Set(
            inventory.map(item => item.device_id).filter(id => id !== null)
        );
        
        const tbody = document.getElementById('devices-table');
        if (!tbody) return;

        if (devices.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center text-muted">
                        No devices found. Click "Start Manual Scan" to discover devices.
                    </td>
                </tr>
            `;
            return;
        }
        
        // Apply current filter and render devices
        filterDevices(currentFilter);
        
    } catch (error) {
        console.error('Error loading devices:', error);
        showNotification('Error loading devices', 'danger');
    }
}

function filterDevices(filter) {
    currentFilter = filter;
    
    if (!currentDevices || currentDevices.length === 0) return;
    
    // Get inventory device IDs from the current inventory state
    const inventoryDeviceIds = new Set();
    if (currentInventory && currentInventory.length > 0) {
        currentInventory.forEach(item => {
            if (item.device_id) inventoryDeviceIds.add(item.device_id);
        });
    }
    
    let filteredDevices = currentDevices;
    
    switch (filter) {
        case 'new':
            filteredDevices = currentDevices.filter(device => 
                new Date() - new Date(device.first_seen) < 24 * 3600000 && // Last 24 hours
                !inventoryDeviceIds.has(device.id) && 
                !device.is_ignored
            );
            break;
        case 'managed':
            filteredDevices = currentDevices.filter(device => 
                inventoryDeviceIds.has(device.id)
            );
            break;
        case 'ignored':
            filteredDevices = currentDevices.filter(device => 
                device.is_ignored
            );
            break;
        default: // 'all'
            break;
    }
    
    renderDevicesTable(filteredDevices, inventoryDeviceIds);
}

function renderDevicesTable(devices, inventoryDeviceIds) {
    const tbody = document.getElementById('devices-table');
    if (!tbody) return;
    
    if (devices.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center text-muted">
                    No devices found for the selected filter.
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = devices.map(device => {
        const isInInventory = inventoryDeviceIds.has(device.id);
        const isIgnored = device.is_ignored;
        const isNew = new Date() - new Date(device.first_seen) < 24 * 3600000;
        
        let statusBadge = '';
        let actions = '';
        
        if (isIgnored) {
            statusBadge = '<span class="badge bg-secondary">Ignored</span>';
            actions = `
                <button class="btn btn-sm btn-outline-success" onclick="unignoreDevice(${device.id})" title="Unignore device">
                    <i class="fas fa-eye"></i>
                </button>
            `;
        } else if (isInInventory) {
            statusBadge = '<span class="badge bg-success">In Inventory</span>';
            actions = `
                <button class="btn btn-sm btn-outline-secondary" onclick="ignoreDevice(${device.id})" title="Ignore device">
                    <i class="fas fa-eye-slash"></i>
                </button>
            `;
        } else {
            if (isNew) {
                statusBadge = '<span class="badge bg-warning">New</span>';
            } else {
                statusBadge = '<span class="badge bg-light text-dark">Discovered</span>';
            }
            actions = `
                <button class="btn btn-sm btn-success me-1" onclick="addToInventory(${device.id})" title="Add to inventory">
                    <i class="fas fa-plus"></i>
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="ignoreDevice(${device.id})" title="Ignore device">
                    <i class="fas fa-eye-slash"></i>
                </button>
            `;
        }
        
        return `
            <tr>
                <td>${statusBadge}</td>
                <td>${device.ip_address || 'N/A'}</td>
                <td><code>${device.mac_address}</code></td>
                <td>${device.hostname && device.hostname !== 'Unknown' ? device.hostname : '<span class="text-muted">Unknown</span>'}</td>
                <td>${device.vendor || '<span class="text-muted">Unknown</span>'}</td>
                <td>${formatDateTime(device.first_seen)}</td>
                <td>${formatDateTime(device.last_seen)}</td>
                <td>${actions}</td>
            </tr>
        `;
    }).join('');
}

async function startNetworkScan() {
    if (scanInProgress) return;

    scanInProgress = true;
    const scanBtn = document.getElementById('scan-btn');
    const scanProgress = document.getElementById('scan-progress');

    // Update UI
    if (scanBtn) {
        scanBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Scanning...';
        scanBtn.disabled = true;
    }
    if (scanProgress) {
        scanProgress.style.display = 'block';
    }

    try {
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        if (result.status === 'success') {
            showNotification(
                `Scan completed! Found ${result.devices_found} devices.`,
                'success'
            );

            // Refresh data based on current page
            if (window.location.pathname.includes('scanning')) {
                await loadScanningData();
                await loadRecentDevices();
            } else {
                await loadDashboardData();
            }
        } else {
            showNotification(`Scan failed: ${result.message}`, 'danger');
        }

    } catch (error) {
        console.error('Error during scan:', error);
        showNotification('Error during network scan', 'danger');
    } finally {
        // Reset UI
        scanInProgress = false;
        if (scanBtn) {
            scanBtn.innerHTML = '<i class="fas fa-search me-2"></i>Start Manual Scan';
            scanBtn.disabled = false;
        }
        if (scanProgress) {
            scanProgress.style.display = 'none';
        }
    }
}

// Device management functions
function addToInventory(deviceId) {
    const device = currentDevices.find(d => d.id === deviceId);
    if (!device) return;

    // Populate modal with device info
    document.getElementById('deviceId').value = deviceId;
    document.getElementById('deviceName').value = device.hostname || `Device ${device.ip_address}`;

    // Pre-select category based on vendor
    const category = document.getElementById('category');
    if (device.vendor && category) {
        const vendor = device.vendor.toLowerCase();
        if (vendor.includes('cisco') || vendor.includes('netgear') || vendor.includes('linksys')) {
            category.value = 'Router';
        } else if (vendor.includes('ubiquiti')) {
            category.value = 'Access Point';
        } else if (vendor.includes('raspberry') || vendor.includes('intel')) {
            category.value = 'Computer';
        }
    }

    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('addToInventoryModal'));
    modal.show();
}

async function saveToInventory() {
    const form = document.getElementById('inventoryForm');
    const formData = new FormData(form);

    try {
        const response = await fetch('/api/inventory', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.status === 'success') {
            showNotification('Device added to inventory successfully!', 'success');

            // Close modal and refresh data
            const modal = bootstrap.Modal.getInstance(document.getElementById('addToInventoryModal'));
            modal.hide();

            // Refresh appropriate data based on current page
            if (window.location.pathname.includes('scanning')) {
                // For scanning page, we need to refresh both inventory and devices data
                await Promise.all([
                    loadScanningData(),
                    fetch('/api/inventory').then(res => res.json()).then(inventory => {
                        currentInventory = inventory;
                        return loadRecentDevices();
                    })
                ]);
            } else if (window.location.pathname.includes('inventory')) {
                await loadInventoryData();
            } else {
                await loadDashboardData();
            }
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }

    } catch (error) {
        console.error('Error saving to inventory:', error);
        showNotification('Error saving device to inventory', 'danger');
    }
}

async function ignoreDevice(deviceId) {
    if (!confirm('Are you sure you want to ignore this device?')) return;

    try {
        const response = await fetch(`/api/devices/${deviceId}/ignore`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.status === 'success') {
            showNotification('Device ignored successfully', 'info');
            
            // Refresh data based on current page
            if (window.location.pathname.includes('scanning')) {
                await Promise.all([
                    loadScanningData(),
                    loadRecentDevices()
                ]);
            } else {
                await loadRecentDevices();
            }
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }

    } catch (error) {
        console.error('Error ignoring device:', error);
        showNotification('Error ignoring device', 'danger');
    }
}

async function unignoreDevice(deviceId) {
    try {
        // Add unignore endpoint call here when implemented
        showNotification('Unignore functionality coming soon', 'info');
        
    } catch (error) {
        console.error('Error unignoring device:', error);
        showNotification('Error unignoring device', 'danger');
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function () {
    // Bind scan button
    const scanBtn = document.getElementById('scan-btn');
    if (scanBtn) {
        scanBtn.addEventListener('click', startNetworkScan);
    }
});

// Auto-refresh every 30 seconds
setInterval(() => {
    if (!scanInProgress) {
        if (window.location.pathname.includes('scanning')) {
            loadScanningData();
        } else {
            loadDashboardData();
        }
    }
}, 30000);

// Inventory-specific functions
async function loadInventoryData() {
    try {
        const response = await fetch('/api/inventory');
        const inventory = await response.json();
        currentInventory = inventory;

        updateInventoryTable(inventory);
        updateInventoryCount(inventory.length);

    } catch (error) {
        console.error('Error loading inventory:', error);
        showNotification('Error loading inventory data', 'danger');
    }
}

function updateInventoryTable(inventory) {
    const tbody = document.getElementById('inventory-table');
    if (!tbody) return;

    if (inventory.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted">
                    No inventory items found. Add devices to get started.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = inventory.map(item => `
        <tr>
            <td>
                <strong>${item.name}</strong>
                ${item.serial_number ? `<br><small class="text-muted">S/N: ${item.serial_number}</small>` : ''}
            </td>
            <td>
                <span class="badge bg-secondary">${item.category || 'Uncategorized'}</span>
            </td>
            <td>
                ${item.brand ? `<strong>${item.brand}</strong>` : ''}
                ${item.model ? `<br>${item.model}` : ''}
            </td>
            <td>${formatDate(item.purchase_date)}</td>
            <td>
                ${getWarrantyStatus(item.warranty_expiry)}
            </td>
            <td>
                ${item.ip_address ? `IP: ${item.ip_address}<br>` : ''}
                ${item.mac_address ? `<code>${item.mac_address}</code>` : 'Not connected'}
                ${item.hostname && item.hostname !== 'Unknown' ? `<br>${item.hostname}` : ''}
            </td>
            <td>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="editInventoryItem(${item.id})">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteInventoryItem(${item.id})" 
                    title="Delete this item">
                <i class="fas fa-trash"></i> Delete
            </button>
            </td>
        </tr>
    `).join('');
}

function getWarrantyStatus(warrantyExpiry) {
    if (!warrantyExpiry) return '<span class="text-muted">Unknown</span>';

    const expiry = new Date(warrantyExpiry);
    const now = new Date();
    const daysUntilExpiry = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));

    if (daysUntilExpiry < 0) {
        return '<span class="text-danger"><i class="fas fa-times-circle"></i> Expired</span>';
    } else if (daysUntilExpiry <= 30) {
        return `<span class="text-warning"><i class="fas fa-exclamation-triangle"></i> ${daysUntilExpiry} days</span>`;
    } else {
        return `<span class="text-success"><i class="fas fa-check-circle"></i> ${Math.floor(daysUntilExpiry / 30)} months</span>`;
    }
}

function updateInventoryCount(count) {
    const countElement = document.getElementById('inventory-count');
    if (countElement) {
        countElement.textContent = count;
    }
}

async function saveNewInventory() {
    const form = document.getElementById('newInventoryForm');
    const formData = new FormData(form);

    try {
        const response = await fetch('/api/inventory', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.status === 'success') {
            showNotification('Device added to inventory successfully!', 'success');

            // Close modal and refresh data
            const modal = bootstrap.Modal.getInstance(document.getElementById('addInventoryModal'));
            modal.hide();
            form.reset();

            await loadInventoryData();

        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }

    } catch (error) {
        console.error('Error saving inventory:', error);
        showNotification('Error saving to inventory', 'danger');
    }
}

function applyFilters() {
    showNotification('Filters applied', 'info');
}

async function exportInventory(format) {
    try {
        showNotification(`Preparing ${format.toUpperCase()} export...`, 'info');
        
        const response = await fetch(`/api/inventory/export/${format}`);
        
        if (response.ok) {
            // Get filename from response headers
            const contentDisposition = response.headers.get('Content-Disposition');
            const filename = contentDisposition 
                ? contentDisposition.split('filename=')[1].replace(/"/g, '')
                : `inventory_export.${format}`;
            
            // Create blob and download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showNotification(`${format.toUpperCase()} export completed successfully!`, 'success');
        } else {
            const error = await response.json();
            showNotification(`Export failed: ${error.message}`, 'danger');
        }
        
    } catch (error) {
        console.error('Export error:', error);
        showNotification(`Export failed: ${error.message}`, 'danger');
    }
}

function editInventoryItem(id) {
    showNotification('Edit functionality coming soon', 'info');
}

async function deleteInventoryItem(id) {
    if (!confirm('Are you sure you want to delete this inventory item? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/inventory/${id}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification('Inventory item deleted successfully', 'success');
            await loadInventoryData(); // Refresh the inventory table
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }
        
    } catch (error) {
        console.error('Error deleting inventory item:', error);
        showNotification('Error deleting inventory item', 'danger');
    }
}