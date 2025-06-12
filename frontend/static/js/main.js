// Main JavaScript Functions with Categories Support

// Global variables
let currentDevices = [];
let currentInventory = [];
let availableCategories = [];
let scanInProgress = false;
let currentFilter = 'all';
let selectedDevices = new Set(); // Track selected device IDs
let selectedInventoryItems = new Set(); // Track selected inventory item IDs

// Initialize SocketIO
const socket = io();

// Socket event listeners for real-time scan updates
socket.on('scan_start', function(data) {
    console.log('Scan started:', data.message);
    showScanProgress(data.message);
});

socket.on('scan_progress', function(data) {
    console.log('Scan progress:', data.message);
    updateScanProgress(data.message, data);
});

socket.on('device_discovered', function(data) {
    console.log('Device discovered:', data.device);
    addDeviceToTable(data.device);
    updateDeviceCount(data.total_found);
});

socket.on('scan_complete', function(data) {
    console.log('Scan complete:', data.message);
    hideScanProgress();
    showNotification(data.message, 'success');
    refreshAllData();
});

socket.on('scan_error', function(data) {
    console.log('Scan error:', data.message);
    hideScanProgress();
    showNotification(data.message, 'danger');
});

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

// Categories management functions
async function loadCategoriesForForms() {
    try {
        const response = await fetch('/api/categories');
        const result = await response.json();
        
        if (result.status === 'success') {
            availableCategories = result.categories;
            updateCategoryDropdowns();
            updateCategoryFilters();
        }
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

function updateCategoryDropdowns() {
    const dropdowns = [
        'category',           // Single add modal
        'newCategory',        // New inventory modal
        'bulkCategory'        // Bulk add modal
    ];
    
    dropdowns.forEach(dropdownId => {
        const dropdown = document.getElementById(dropdownId);
        if (dropdown) {
            updateSingleCategoryDropdown(dropdown);
        }
    });
    
    // Update individual device forms in bulk modal if they exist
    document.querySelectorAll('.device-field[data-field="category"]').forEach(dropdown => {
        updateSingleCategoryDropdown(dropdown);
    });
}

function updateSingleCategoryDropdown(dropdown) {
    const currentValue = dropdown.value;
    
    // Clear existing options except first
    dropdown.innerHTML = '<option value="">Select category...</option>';
    
    // Add categories
    availableCategories.forEach(category => {
        const option = document.createElement('option');
        option.value = category.id;
        option.textContent = category.name;
        option.dataset.categoryName = category.name;
        
        // Add visual indicator for default categories
        if (category.is_default) {
            option.style.fontWeight = 'bold';
        }
        
        dropdown.appendChild(option);
    });
    
    // Restore previous selection if it still exists
    if (currentValue) {
        dropdown.value = currentValue;
    }
}

function updateCategoryFilters() {
    const categoryFilter = document.getElementById('categoryFilter');
    if (categoryFilter) {
        const currentValue = categoryFilter.value;
        
        // Clear existing options except first
        categoryFilter.innerHTML = '<option value="">All Categories</option>';
        
        // Add categories
        availableCategories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.name;
            option.textContent = category.name;
            categoryFilter.appendChild(option);
        });
        
        // Restore previous selection
        if (currentValue) {
            categoryFilter.value = currentValue;
        }
    }
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
                <div class="d-flex align-items-center">
                    <div class="category-icon me-2" style="background-color: ${item.color}; color: white; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.7rem;">
                        <i class="${item.icon}"></i>
                    </div>
                    <span>${item.category}</span>
                </div>
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
        currentInventory = inventory;
        
        const tbody = document.getElementById('devices-table');
        if (!tbody) return;

        if (devices.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-muted">
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
    clearSelection(); // Clear selection when changing filters
    
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
                <td colspan="9" class="text-center text-muted">
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
        const isSelected = selectedDevices.has(device.id);
        
        let statusBadge = '';
        let actions = '';
        let selectableClass = '';
        
        if (isIgnored) {
            statusBadge = '<span class="badge bg-secondary">Ignored</span>';
            actions = `
                <button class="btn btn-sm btn-success me-1" onclick="unignoreDevice(${device.id})" title="Unignore device">
                    <i class="fas fa-eye"></i> Unignore
                </button>
            `;
            selectableClass = 'selectable-ignored';
        } else if (isInInventory) {
            statusBadge = '<span class="badge bg-success">In Inventory</span>';
            actions = `
                <button class="btn btn-sm btn-outline-secondary" onclick="ignoreDevice(${device.id})" title="Ignore device">
                    <i class="fas fa-eye-slash"></i>
                </button>
            `;
            selectableClass = 'selectable-managed';
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
            selectableClass = 'selectable-unmanaged';
        }
        
        return `
            <tr class="${selectableClass}" data-device-id="${device.id}">
                <td>
                    <input type="checkbox" class="device-checkbox" 
                           data-device-id="${device.id}" 
                           ${isSelected ? 'checked' : ''}
                           onchange="toggleDeviceSelection(${device.id}, this.checked)">
                </td>
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
    
    // Update select all checkbox state
    updateSelectAllCheckbox();
}

// Bulk selection functions for devices
function toggleDeviceSelection(deviceId, isSelected) {
    if (isSelected) {
        selectedDevices.add(deviceId);
    } else {
        selectedDevices.delete(deviceId);
    }
    updateBulkActionsBar();
    updateSelectAllCheckbox();
}

function toggleSelectAll(checkbox) {
    const deviceCheckboxes = document.querySelectorAll('.device-checkbox');
    const visibleDeviceIds = Array.from(deviceCheckboxes).map(cb => parseInt(cb.dataset.deviceId));
    
    if (checkbox.checked) {
        // Select all visible devices
        visibleDeviceIds.forEach(id => selectedDevices.add(id));
        deviceCheckboxes.forEach(cb => cb.checked = true);
    } else {
        // Deselect all visible devices
        visibleDeviceIds.forEach(id => selectedDevices.delete(id));
        deviceCheckboxes.forEach(cb => cb.checked = false);
    }
    updateBulkActionsBar();
}

function updateSelectAllCheckbox() {
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const deviceCheckboxes = document.querySelectorAll('.device-checkbox');
    
    if (!selectAllCheckbox || deviceCheckboxes.length === 0) return;
    
    const checkedCount = Array.from(deviceCheckboxes).filter(cb => cb.checked).length;
    
    if (checkedCount === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedCount === deviceCheckboxes.length) {
        selectAllCheckbox.checked = true;
        selectAllCheckbox.indeterminate = false;
    } else {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = true;
    }
}

function updateBulkActionsBar() {
    const bulkActionsBar = document.getElementById('bulk-actions-bar');
    const selectedCountSpan = document.getElementById('selected-count');
    const bulkAddBtn = document.getElementById('bulk-add-btn');
    const bulkIgnoreBtn = document.getElementById('bulk-ignore-btn');
    const bulkUnignoreBtn = document.getElementById('bulk-unignore-btn');
    
    if (!bulkActionsBar) return;
    
    const selectedCount = selectedDevices.size;
    
    if (selectedCount === 0) {
        bulkActionsBar.style.display = 'none';
        return;
    }
    
    bulkActionsBar.style.display = 'block';
    selectedCountSpan.textContent = selectedCount;
    
    // Determine which actions are available based on selected devices
    const selectedDeviceData = Array.from(selectedDevices).map(id => 
        currentDevices.find(d => d.id === id)
    ).filter(d => d);
    
    const inventoryDeviceIds = new Set(
        currentInventory.map(item => item.device_id).filter(id => id !== null)
    );
    
    const hasUnmanaged = selectedDeviceData.some(d => !inventoryDeviceIds.has(d.id) && !d.is_ignored);
    const hasNonIgnored = selectedDeviceData.some(d => !d.is_ignored);
    const hasIgnored = selectedDeviceData.some(d => d.is_ignored);
    
    // Show/hide buttons based on selection
    if (bulkAddBtn) bulkAddBtn.style.display = hasUnmanaged ? 'inline-block' : 'none';
    if (bulkIgnoreBtn) bulkIgnoreBtn.style.display = hasNonIgnored ? 'inline-block' : 'none';
    if (bulkUnignoreBtn) bulkUnignoreBtn.style.display = hasIgnored ? 'inline-block' : 'none';
}

function clearSelection() {
    selectedDevices.clear();
    document.querySelectorAll('.device-checkbox').forEach(cb => cb.checked = false);
    updateBulkActionsBar();
    updateSelectAllCheckbox();
}

// Bulk operation functions with category support
async function bulkAddToInventory() {
    if (selectedDevices.size === 0) {
        showNotification('No devices selected', 'warning');
        return;
    }
    
    // Filter only unmanaged devices
    const inventoryDeviceIds = new Set(
        currentInventory.map(item => item.device_id).filter(id => id !== null)
    );
    
    const eligibleDeviceIds = Array.from(selectedDevices).filter(id => {
        const device = currentDevices.find(d => d.id === id);
        return device && !inventoryDeviceIds.has(id) && !device.is_ignored;
    });
    
    if (eligibleDeviceIds.length === 0) {
        showNotification('No eligible devices selected for adding to inventory', 'warning');
        return;
    }
    
    // Update modal with count and show it
    document.getElementById('bulk-device-count').textContent = eligibleDeviceIds.length;
    
    // Store eligible device IDs and data for later use
    window.bulkEligibleDeviceIds = eligibleDeviceIds;
    window.bulkEligibleDevices = eligibleDeviceIds.map(id => 
        currentDevices.find(d => d.id === id)
    );
    
    // Load categories and update dropdowns
    await loadCategoriesForForms();
    
    // Reset to common mode
    document.getElementById('commonMode').checked = true;
    toggleConfigMode();
    
    const modal = new bootstrap.Modal(document.getElementById('bulkAddToInventoryModal'));
    modal.show();
}

function toggleConfigMode() {
    const isCommonMode = document.getElementById('commonMode').checked;
    const infoDiv = document.getElementById('config-mode-info');
    const commonSection = document.getElementById('common-settings-section');
    const individualSection = document.getElementById('individual-settings-section');
    
    if (isCommonMode) {
        infoDiv.innerHTML = `
            <i class="fas fa-layer-group me-1"></i>
            <strong>Common Settings Mode:</strong> Apply the same configuration to all selected devices quickly.
        `;
        commonSection.style.display = 'block';
        individualSection.style.display = 'none';
    } else {
        infoDiv.innerHTML = `
            <i class="fas fa-edit me-1"></i>
            <strong>Individual Settings Mode:</strong> Customize each device with unique settings and details.
        `;
        commonSection.style.display = 'none';
        individualSection.style.display = 'block';
        populateIndividualDevicesList();
    }
}

function populateIndividualDevicesList() {
    const container = document.getElementById('individual-devices-list');
    
    // Build category options
    const categoryOptions = availableCategories.map(category => 
        `<option value="${category.id}" data-category-name="${category.name}">${category.name}</option>`
    ).join('');
    
    container.innerHTML = window.bulkEligibleDevices.map((device, index) => {
        const suggestedName = device.hostname && device.hostname !== 'Unknown' 
            ? device.hostname 
            : `Device ${device.ip_address}`;
            
        return `
            <div class="card mb-2 device-config-card border-primary" data-device-id="${device.id}" style="border-width: 1px;">
                <div class="card-header bg-primary text-white py-2">
                    <div class="d-flex align-items-center">
                        <div class="bg-white text-primary rounded-circle me-2 d-flex align-items-center justify-content-center" style="width: 28px; height: 28px; font-size: 0.9rem;">
                            <i class="fas fa-desktop"></i>
                        </div>
                        <div class="flex-grow-1">
                            <h6 class="mb-0">${device.ip_address}</h6>
                            <small class="text-white-50">${device.vendor || 'Unknown'} • <code>${device.mac_address}</code></small>
                        </div>
                        <small class="text-white-50">${index + 1}/${window.bulkEligibleDevices.length}</small>
                    </div>
                </div>
                <div class="card-body py-2">
                    <!-- Row 1: Name and Category -->
                    <div class="row">
                        <div class="col-md-7 mb-2">
                            <label class="form-label mb-1 fw-bold text-primary small">Device Name *</label>
                            <input type="text" 
                                   class="form-control form-control-sm device-field" 
                                   data-field="name"
                                   value="${suggestedName}" 
                                   required>
                        </div>
                        <div class="col-md-5 mb-2">
                            <label class="form-label mb-1 fw-bold text-primary small">Category</label>
                            <select class="form-select form-select-sm device-field" data-field="category">
                                <option value="">Select category...</option>
                                ${categoryOptions}
                            </select>
                        </div>
                    </div>
                    
                    <!-- Row 2: Brand, Model, Serial -->
                    <div class="row">
                        <div class="col-md-4 mb-2">
                            <label class="form-label mb-1 small">Brand</label>
                            <input type="text" class="form-control form-control-sm device-field" data-field="brand">
                        </div>
                        <div class="col-md-4 mb-2">
                            <label class="form-label mb-1 small">Model</label>
                            <input type="text" class="form-control form-control-sm device-field" data-field="model">
                        </div>
                        <div class="col-md-4 mb-2">
                            <label class="form-label mb-1 small">Serial Number</label>
                            <input type="text" class="form-control form-control-sm device-field" data-field="serial_number">
                        </div>
                    </div>
                    
                    <!-- Row 3: Dates and Price -->
                    <div class="row">
                        <div class="col-md-4 mb-2">
                            <label class="form-label mb-1 small">Purchase Date</label>
                            <input type="date" class="form-control form-control-sm device-field" data-field="purchase_date">
                        </div>
                        <div class="col-md-4 mb-2">
                            <label class="form-label mb-1 small">Warranty Expiry</label>
                            <input type="date" class="form-control form-control-sm device-field" data-field="warranty_expiry">
                        </div>
                        <div class="col-md-4 mb-2">
                            <label class="form-label mb-1 small">Price</label>
                            <input type="number" step="0.01" class="form-control form-control-sm device-field" data-field="price" placeholder="0.00">
                        </div>
                    </div>
                    
                    <!-- Row 4: Store and Notes -->
                    <div class="row">
                        <div class="col-md-6 mb-2">
                            <label class="form-label mb-1 small">Store/Vendor</label>
                            <input type="text" class="form-control form-control-sm device-field" data-field="store_vendor">
                        </div>
                        <div class="col-md-6 mb-2">
                            <label class="form-label mb-1 small">Notes</label>
                            <textarea class="form-control form-control-sm device-field" data-field="notes" rows="1"></textarea>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function copyCommonToAll() {
    const commonForm = document.getElementById('bulkInventoryForm');
    const formData = new FormData(commonForm);
    
    // Get common values including category
    const commonValues = {
        brand: formData.get('brand'),
        model: formData.get('model'),
        purchase_date: formData.get('purchase_date'),
        warranty_expiry: formData.get('warranty_expiry'),
        store_vendor: formData.get('store_vendor'),
        price: formData.get('price'),
        serial_number: formData.get('serial_number'),
        notes: formData.get('notes')
    };
    
    // Handle category specially
    const categoryDropdown = document.getElementById('bulkCategory');
    if (categoryDropdown && categoryDropdown.value) {
        commonValues.category = categoryDropdown.value;
    }
    
    // Apply to all individual device forms
    document.querySelectorAll('.device-config-card').forEach(card => {
        Object.keys(commonValues).forEach(field => {
            if (field !== 'serial_number' || !commonValues[field]) { // Don't copy serial number if it's set
                const input = card.querySelector(`[data-field="${field}"]`);
                if (input && commonValues[field]) {
                    input.value = commonValues[field];
                }
            }
        });
    });
    
    showNotification('Common settings copied to all devices', 'success');
}

async function saveBulkToInventory() {
    const isCommonMode = document.getElementById('commonMode').checked;
    
    if (isCommonMode) {
        return saveBulkToInventoryCommon();
    } else {
        return saveBulkToInventoryIndividual();
    }
}

async function saveBulkToInventoryCommon() {
    const form = document.getElementById('bulkInventoryForm');
    const formData = new FormData(form);
    const useAutoNames = document.getElementById('useDeviceNames').checked;
    
    const commonData = {
        brand: formData.get('brand'),
        model: formData.get('model'),
        purchase_date: formData.get('purchase_date'),
        warranty_expiry: formData.get('warranty_expiry'),
        store_vendor: formData.get('store_vendor'),
        price: formData.get('price'),
        serial_number: formData.get('serial_number'),
        notes: formData.get('notes')
    };
    
    // Handle category
    const categoryDropdown = document.getElementById('bulkCategory');
    if (categoryDropdown && categoryDropdown.value) {
        commonData.category_id = categoryDropdown.value;
        const selectedOption = categoryDropdown.options[categoryDropdown.selectedIndex];
        if (selectedOption) {
            commonData.category = selectedOption.dataset.categoryName || selectedOption.textContent;
        }
    }
    
    try {
        const response = await fetch('/api/devices/bulk/add-to-inventory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                device_ids: window.bulkEligibleDeviceIds,
                common_data: commonData,
                use_auto_names: useAutoNames,
                mode: 'common'
            })
        });

        const result = await response.json();
        await handleBulkInventoryResult(result);

    } catch (error) {
        console.error('Error bulk adding to inventory:', error);
        showNotification('Error adding devices to inventory', 'danger');
    }
}

async function saveBulkToInventoryIndividual() {
    // Collect individual device data
    const deviceData = {};
    let hasErrors = false;
    
    document.querySelectorAll('.device-config-card').forEach(card => {
        const deviceId = card.dataset.deviceId;
        const data = {};
        
        card.querySelectorAll('.device-field').forEach(field => {
            const fieldName = field.dataset.field;
            const value = field.value.trim();
            
            // Validate required fields
            if (fieldName === 'name' && !value) {
                field.classList.add('is-invalid');
                hasErrors = true;
            } else {
                field.classList.remove('is-invalid');
                
                // Handle category specially
                if (fieldName === 'category' && value) {
                    data.category_id = value;
                    const selectedOption = field.options[field.selectedIndex];
                    if (selectedOption) {
                        data.category = selectedOption.dataset.categoryName || selectedOption.textContent;
                    }
                } else {
                    data[fieldName] = value || null;
                }
            }
        });
        
        deviceData[deviceId] = data;
    });
    
    if (hasErrors) {
        showNotification('Please provide names for all devices', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/devices/bulk/add-to-inventory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                device_ids: window.bulkEligibleDeviceIds,
                device_data: deviceData,
                mode: 'individual'
            })
        });

        const result = await response.json();
        await handleBulkInventoryResult(result);

    } catch (error) {
        console.error('Error bulk adding to inventory:', error);
        showNotification('Error adding devices to inventory', 'danger');
    }
}

async function handleBulkInventoryResult(result) {
    if (result.status === 'success') {
        showNotification(result.message, 'success');

        // Close modal and refresh data
        const modal = bootstrap.Modal.getInstance(document.getElementById('bulkAddToInventoryModal'));
        modal.hide();
        
        // Reset form
        document.getElementById('bulkInventoryForm').reset();
        document.getElementById('commonMode').checked = true;
        
        clearSelection();
        
        await Promise.all([
            loadScanningData(),
            fetch('/api/inventory').then(res => res.json()).then(inventory => {
                currentInventory = inventory;
                return loadRecentDevices();
            })
        ]);
    } else {
        showNotification(`Error: ${result.message}`, 'danger');
    }
}

async function bulkIgnoreDevices() {
    if (selectedDevices.size === 0) {
        showNotification('No devices selected', 'warning');
        return;
    }
    
    // Filter only non-ignored devices
    const eligibleDeviceIds = Array.from(selectedDevices).filter(id => {
        const device = currentDevices.find(d => d.id === id);
        return device && !device.is_ignored;
    });
    
    if (eligibleDeviceIds.length === 0) {
        showNotification('No eligible devices selected for ignoring', 'warning');
        return;
    }
    
    if (!confirm(`Are you sure you want to ignore ${eligibleDeviceIds.length} device(s)?`)) {
        return;
    }

    try {
        const response = await fetch('/api/devices/bulk/ignore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                device_ids: eligibleDeviceIds
            })
        });

        const result = await response.json();

        if (result.status === 'success') {
            showNotification(result.message, 'success');
            clearSelection();
            
            await Promise.all([
                loadScanningData(),
                loadRecentDevices()
            ]);
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }

    } catch (error) {
        console.error('Error bulk ignoring devices:', error);
        showNotification('Error ignoring devices', 'danger');
    }
}

async function bulkUnignoreDevices() {
    if (selectedDevices.size === 0) {
        showNotification('No devices selected', 'warning');
        return;
    }
    
    // Filter only ignored devices
    const eligibleDeviceIds = Array.from(selectedDevices).filter(id => {
        const device = currentDevices.find(d => d.id === id);
        return device && device.is_ignored;
    });
    
    if (eligibleDeviceIds.length === 0) {
        showNotification('No ignored devices selected', 'warning');
        return;
    }
    
    if (!confirm(`Are you sure you want to unignore ${eligibleDeviceIds.length} device(s)? They will appear in scans again.`)) {
        return;
    }

    try {
        const response = await fetch('/api/devices/bulk/unignore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                device_ids: eligibleDeviceIds
            })
        });

        const result = await response.json();

        if (result.status === 'success') {
            showNotification(result.message, 'success');
            clearSelection();
            
            await Promise.all([
                loadScanningData(),
                loadRecentDevices()
            ]);
        } else {
            showNotification(`Error: ${result.message}`, 'danger');
        }

    } catch (error) {
        console.error('Error bulk unignoring devices:', error);
        showNotification('Error unignoring devices', 'danger');
    }
}

// Network Scanning
async function startNetworkScan() {
    if (scanInProgress) return;

    scanInProgress = true;
    const scanBtn = document.getElementById('scan-btn');
    const dashboardScanBtn = document.getElementById('dashboard-scan-btn');
    const scanProgress = document.getElementById('scan-progress');

    // Update UI for all scan buttons
    [scanBtn, dashboardScanBtn].forEach(btn => {
        if (btn) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Scanning...';
            btn.disabled = true;
        }
    });

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
                // Also refresh chart data if on dashboard
                if (typeof loadChartData !== 'undefined') {
                    await loadChartData();
                }
            }
        } else {
            showNotification(`Scan failed: ${result.message}`, 'danger');
        }

    } catch (error) {
        console.error('Error during scan:', error);
        showNotification('Error during network scan', 'danger');
    } finally {
        // Reset UI for all scan buttons
        scanInProgress = false;
        [scanBtn, dashboardScanBtn].forEach(btn => {
            if (btn) {
                btn.innerHTML = '<i class="fas fa-search me-2"></i>Start Manual Scan';
                btn.disabled = false;
            }
        });
        
        if (scanProgress) {
            scanProgress.style.display = 'none';
        }
    }
}

// Individual device management functions with category support
function addToInventory(deviceId) {
    const device = currentDevices.find(d => d.id === deviceId);
    if (!device) return;

    // Load categories first, then populate modal
    loadCategoriesForForms().then(() => {
        // Populate modal with device info
        document.getElementById('deviceId').value = deviceId;
        document.getElementById('deviceName').value = device.hostname || `Device ${device.ip_address}`;

        // Pre-select category based on vendor
        const categoryDropdown = document.getElementById('category');
        if (device.vendor && categoryDropdown && availableCategories.length > 0) {
            const vendor = device.vendor.toLowerCase();
            let suggestedCategoryName = null;
            
            if (vendor.includes('cisco') || vendor.includes('netgear') || vendor.includes('linksys')) {
                suggestedCategoryName = 'Router';
            } else if (vendor.includes('ubiquiti')) {
                suggestedCategoryName = 'Access Point';
            } else if (vendor.includes('raspberry') || vendor.includes('intel')) {
                suggestedCategoryName = 'Computer';
            }
            
            if (suggestedCategoryName) {
                const suggestedCategory = availableCategories.find(cat => cat.name === suggestedCategoryName);
                if (suggestedCategory) {
                    categoryDropdown.value = suggestedCategory.id;
                }
            }
        }

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('addToInventoryModal'));
        modal.show();
    });
}

async function saveToInventory() {
    const form = document.getElementById('inventoryForm');
    const formData = new FormData(form);
    
    // Handle category selection
    const categoryDropdown = document.getElementById('category');
    if (categoryDropdown && categoryDropdown.value) {
        formData.set('category_id', categoryDropdown.value);
        
        // Also set category name for backward compatibility
        const selectedOption = categoryDropdown.options[categoryDropdown.selectedIndex];
        if (selectedOption) {
            formData.set('category', selectedOption.dataset.categoryName || selectedOption.textContent);
        }
    }

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
            form.reset();

            // Refresh appropriate data based on current page
            if (window.location.pathname.includes('scanning')) {
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
    if (!confirm('Are you sure you want to unignore this device? It will appear in scans again.')) return;

    try {
        const response = await fetch(`/api/devices/${deviceId}/unignore`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.status === 'success') {
            showNotification('Device unignored successfully', 'success');
            
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
        console.error('Error unignoring device:', error);
        showNotification('Error unignoring device', 'danger');
    }
}

// Inventory-specific functions with category support
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
                <td colspan="8" class="text-center text-muted">
                    No inventory items found. Add devices to get started.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = inventory.map(item => {
        const isSelected = selectedInventoryItems.has(item.id);
        const categoryDisplay = item.category_name || item.category || 'Uncategorized';
        const categoryColor = item.category_color || '#6c757d';
        const categoryIcon = item.category_icon || 'fas fa-question';
        
        return `
            <tr data-inventory-id="${item.id}">
                <td>
                    <input type="checkbox" class="inventory-checkbox" 
                           data-inventory-id="${item.id}" 
                           ${isSelected ? 'checked' : ''}
                           onchange="toggleInventorySelection(${item.id}, this.checked)">
                </td>
                <td>
                    <strong>${item.name}</strong>
                    ${item.serial_number ? `<br><small class="text-muted">S/N: ${item.serial_number}</small>` : ''}
                </td>
                <td>
                    <span class="badge d-inline-flex align-items-center" style="background-color: ${categoryColor}; color: white;">
                        <i class="${categoryIcon} me-1"></i>${categoryDisplay}
                    </span>
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
                    <i class="fas fa-trash"></i>
                </button>
                </td>
            </tr>
        `;
    }).join('');
    
    // Update select all checkbox state
    updateSelectAllInventoryCheckbox();
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

// Inventory bulk selection functions
function toggleInventorySelection(inventoryId, isSelected) {
    if (isSelected) {
        selectedInventoryItems.add(inventoryId);
    } else {
        selectedInventoryItems.delete(inventoryId);
    }
    updateInventoryBulkActionsBar();
    updateSelectAllInventoryCheckbox();
}

function toggleSelectAllInventory(checkbox) {
    const inventoryCheckboxes = document.querySelectorAll('.inventory-checkbox');
    const visibleInventoryIds = Array.from(inventoryCheckboxes).map(cb => parseInt(cb.dataset.inventoryId));
    
    if (checkbox.checked) {
        // Select all visible inventory items
        visibleInventoryIds.forEach(id => selectedInventoryItems.add(id));
        inventoryCheckboxes.forEach(cb => cb.checked = true);
    } else {
        // Deselect all visible inventory items
        visibleInventoryIds.forEach(id => selectedInventoryItems.delete(id));
        inventoryCheckboxes.forEach(cb => cb.checked = false);
    }
    updateInventoryBulkActionsBar();
}

function updateSelectAllInventoryCheckbox() {
    const selectAllCheckbox = document.getElementById('select-all-inventory-checkbox');
    const inventoryCheckboxes = document.querySelectorAll('.inventory-checkbox');
    
    if (!selectAllCheckbox || inventoryCheckboxes.length === 0) return;
    
    const checkedCount = Array.from(inventoryCheckboxes).filter(cb => cb.checked).length;
    
    if (checkedCount === 0) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    } else if (checkedCount === inventoryCheckboxes.length) {
        selectAllCheckbox.checked = true;
        selectAllCheckbox.indeterminate = false;
    } else {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = true;
    }
}

function updateInventoryBulkActionsBar() {
    const bulkActionsBar = document.getElementById('inventory-bulk-actions-bar');
    const selectedCountSpan = document.getElementById('inventory-selected-count');
    
    if (!bulkActionsBar) return;
    
    const selectedCount = selectedInventoryItems.size;
    
    if (selectedCount === 0) {
        bulkActionsBar.style.display = 'none';
        return;
    }
    
    bulkActionsBar.style.display = 'block';
    selectedCountSpan.textContent = selectedCount;
}

function clearInventorySelection() {
    selectedInventoryItems.clear();
    document.querySelectorAll('.inventory-checkbox').forEach(cb => cb.checked = false);
    updateInventoryBulkActionsBar();
    updateSelectAllInventoryCheckbox();
}

async function bulkDeleteInventoryItems() {
    if (selectedInventoryItems.size === 0) {
        showNotification('No items selected', 'warning');
        return;
    }
    
    const selectedCount = selectedInventoryItems.size;
    
    if (!confirm(`Are you sure you want to delete ${selectedCount} inventory item(s)? This action cannot be undone.`)) {
        return;
    }

    try {
        // Delete items one by one (could be optimized with a bulk endpoint)
        const deletionPromises = Array.from(selectedInventoryItems).map(async (itemId) => {
            const response = await fetch(`/api/inventory/${itemId}`, {
                method: 'DELETE'
            });
            return response.json();
        });

        const results = await Promise.all(deletionPromises);
        
        // Check if all deletions were successful
        const successCount = results.filter(result => result.status === 'success').length;
        const failureCount = results.length - successCount;
        
        if (successCount > 0) {
            showNotification(`Successfully deleted ${successCount} item(s)${failureCount > 0 ? ` (${failureCount} failed)` : ''}`, 'success');
            
            clearInventorySelection();
            await loadInventoryData(); // Refresh the inventory table
        } else {
            showNotification('Failed to delete selected items', 'danger');
        }

    } catch (error) {
        console.error('Error bulk deleting inventory items:', error);
        showNotification('Error deleting inventory items', 'danger');
    }
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

async function saveNewInventory() {
    const form = document.getElementById('newInventoryForm');
    const formData = new FormData(form);
    
    // Handle category selection
    const categoryDropdown = document.getElementById('newCategory');
    if (categoryDropdown && categoryDropdown.value) {
        formData.set('category_id', categoryDropdown.value);
        
        // Also set category name for backward compatibility
        const selectedOption = categoryDropdown.options[categoryDropdown.selectedIndex];
        if (selectedOption) {
            formData.set('category', selectedOption.dataset.categoryName || selectedOption.textContent);
        }
    }

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

// Event listeners and initialization
document.addEventListener('DOMContentLoaded', function () {
    // Load categories for forms on all pages
    loadCategoriesForForms();
    
    // Bind scan button
    const scanBtn = document.getElementById('scan-btn');
    if (scanBtn) {
        scanBtn.addEventListener('click', startNetworkScan);
    }
    
    // Load appropriate data based on current page
    const currentPath = window.location.pathname;
    
    if (currentPath.includes('scanning')) {
        loadScanningData();
        loadRecentDevices();
        
        // Add event listeners for filter buttons
        document.querySelectorAll('input[name="deviceFilter"]').forEach(radio => {
            radio.addEventListener('change', function() {
                filterDevices(this.value);
            });
        });
    } else if (currentPath.includes('inventory')) {
        loadInventoryData();
    } else if (currentPath === '/' || currentPath.includes('index')) {
        loadDashboardData();
        loadCategoryStats();
        loadWarrantyAlerts();
    }
    
    // Load categories when modals are shown
    document.getElementById('addToInventoryModal')?.addEventListener('shown.bs.modal', loadCategoriesForForms);
    document.getElementById('addInventoryModal')?.addEventListener('shown.bs.modal', loadCategoriesForForms);
    document.getElementById('bulkAddToInventoryModal')?.addEventListener('shown.bs.modal', loadCategoriesForForms);
});

// Auto-refresh every 30 seconds
setInterval(() => {
    if (!scanInProgress) {
        const currentPath = window.location.pathname;
        
        if (currentPath.includes('scanning')) {
            loadScanningData();
        } else if (currentPath === '/' || currentPath.includes('index')) {
            loadDashboardData();
        }
        // Don't auto-refresh inventory page to avoid disrupting user input
    }
}, 30000);