// Main JavaScript Functions

// Global variables
let currentDevices = [];
let currentInventory = [];
let scanInProgress = false;

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
        const response = await fetch('/api/devices');
        const devices = await response.json();
        
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

async function loadRecentDevices() {
    try {
        const response = await fetch('/api/devices');
        const devices = await response.json();
        currentDevices = devices;
        
        const tbody = document.getElementById('devices-table');
        if (devices.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted">
                        No devices found. Click "Start Scan" to discover devices.
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = devices.slice(0, 10).map(device => `
            <tr>
                <td>${device.ip_address || 'N/A'}</td>
                <td><code>${device.mac_address}</code></td>
                <td>${device.hostname || 'Unknown'}</td>
                <td>${device.vendor || 'Unknown'}</td>
                <td>${formatDateTime(device.first_seen)}</td>
                <td>
                    <button class="btn btn-sm btn-success me-1" onclick="addToInventory(${device.id})">
                        <i class="fas fa-plus"></i> Add
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="ignoreDevice(${device.id})">
                        <i class="fas fa-eye-slash"></i> Ignore
                    </button>
                </td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error loading devices:', error);
        showNotification('Error loading devices', 'danger');
    }
}

async function startNetworkScan() {
    if (scanInProgress) return;
    
    scanInProgress = true;
    const scanBtn = document.getElementById('scan-btn');
    const scanProgress = document.getElementById('scan-progress');
    
    // Update UI
    scanBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Scanning...';
    scanBtn.disabled = true;
    scanProgress.style.display = 'block';
    
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
            
            // Refresh dashboard and device list
            await loadDashboardData();
            await loadRecentDevices();
        } else {
            showNotification(`Scan failed: ${result.message}`, 'danger');
        }
        
    } catch (error) {
        console.error('Error during scan:', error);
        showNotification('Error during network scan', 'danger');
    } finally {
        // Reset UI
        scanInProgress = false;
        scanBtn.innerHTML = '<i class="fas fa-search me-2"></i>Start Scan';
        scanBtn.disabled = false;
        scanProgress.style.display = 'none';
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
    if (device.vendor) {
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
            
            await loadDashboardData();
            await loadRecentDevices();
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
            await loadRecentDevices();
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }
        
    } catch (error) {
        console.error('Error ignoring device:', error);
        showNotification('Error ignoring device', 'danger');
    }
}

function refreshDevices() {
    loadRecentDevices();
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Bind scan button
    const scanBtn = document.getElementById('scan-btn');
    if (scanBtn) {
        scanBtn.addEventListener('click', startNetworkScan);
    }
});

// Auto-refresh every 30 seconds
setInterval(() => {
    if (!scanInProgress) {
        loadDashboardData();
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
            </td>
            <td>
                <button class="btn btn-sm btn-outline-primary me-1" onclick="editInventoryItem(${item.id})">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteInventoryItem(${item.id})">
                    <i class="fas fa-trash"></i>
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

function exportInventory(format) {
    showNotification(`Exporting inventory as ${format.toUpperCase()}...`, 'info');
}

function editInventoryItem(id) {
    showNotification('Edit functionality coming soon', 'info');
}

function deleteInventoryItem(id) {
    showNotification('Delete functionality coming soon', 'info');
}