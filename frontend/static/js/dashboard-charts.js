// Dashboard Charts JavaScript Functions

// Check if charts are already initialized to avoid redeclaration
if (typeof window.chartsInitialized === 'undefined') {
    window.chartsInitialized = false;
    
    // Chart configurations
    window.chartConfigs = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'bottom'
            }
        }
    };

    // Chart instances - use window object to avoid redeclaration
    window.dashboardCharts = {
        deviceStatus: null,
        category: null,
        discoveryTimeline: null,
        warranty: null,
        inventoryValue: null
    };
}

// Initialize all charts
function initializeCharts() {
    // Only initialize charts if their canvas elements exist
    if (document.getElementById('deviceStatusChart')) {
        initDeviceStatusChart();
    }
    if (document.getElementById('categoryChart')) {
        initCategoryChart();
    }
    if (document.getElementById('discoveryTimelineChart')) {
        initDiscoveryTimelineChart();
    }
    if (document.getElementById('warrantyChart')) {
        initWarrantyChart();
    }
    if (document.getElementById('inventoryValueChart')) {
        initInventoryValueChart();
    }
}

// Device Status Donut Chart
function initDeviceStatusChart() {
    const canvas = document.getElementById('deviceStatusChart');
    if (!canvas) {
        console.warn('Device status chart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    window.dashboardCharts.deviceStatus = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Online', 'Offline', 'Unknown'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: [
                    '#28a745', // Green for online
                    '#dc3545', // Red for offline
                    '#ffc107'  // Yellow for unknown
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            ...window.chartConfigs,
            cutout: '60%',
            plugins: {
                legend: {
                    display: false // We have custom legend below
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label;
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const status = ['online', 'offline', 'unknown'][index];
                    filterDevicesByStatus(status);
                }
            }
        }
    });
}

// Category Distribution Pie Chart
function initCategoryChart() {
    const canvas = document.getElementById('categoryChart');
    if (!canvas) {
        console.warn('Category chart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    window.dashboardCharts.category = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            ...window.chartConfigs,
            plugins: {
                legend: {
                    display: false // We'll create a custom legend
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label;
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                            return `${label}: ${value} devices (${percentage}%)`;
                        }
                    }
                }
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const category = window.dashboardCharts.category.data.labels[index];
                    filterInventoryByCategory(category);
                }
            }
        }
    });
}

// Discovery Timeline Chart
function initDiscoveryTimelineChart() {
    const canvas = document.getElementById('discoveryTimelineChart');
    if (!canvas) {
        console.warn('Discovery timeline chart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    window.dashboardCharts.discoveryTimeline = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'New Devices',
                data: [],
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            ...window.chartConfigs,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Warranty Status Chart
function initWarrantyChart() {
    const canvas = document.getElementById('warrantyChart');
    if (!canvas) {
        console.warn('Warranty chart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    window.dashboardCharts.warranty = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Active', 'Expiring Soon', 'Expired', 'Unknown'],
            datasets: [{
                data: [0, 0, 0, 0],
                backgroundColor: [
                    '#28a745', // Green for active
                    '#ffc107', // Yellow for expiring
                    '#dc3545', // Red for expired
                    '#6c757d'  // Gray for unknown
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            ...window.chartConfigs,
            cutout: '50%',
            plugins: {
                legend: {
                    display: true,
                    position: 'bottom',
                    labels: {
                        fontSize: 10,
                        usePointStyle: true
                    }
                }
            }
        }
    });
}

// Inventory Value Gauge Chart
function initInventoryValueChart() {
    const canvas = document.getElementById('inventoryValueChart');
    if (!canvas) {
        console.warn('Inventory value chart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    window.dashboardCharts.inventoryValue = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            ...window.chartConfigs,
            cutout: '70%',
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label;
                            const value = context.parsed;
                            return `${label}: $${value.toLocaleString()}`;
                        }
                    }
                }
            }
        }
    });
}

// Load and update chart data
async function loadChartData() {
    try {
        // Add a small delay to ensure DOM is ready
        await new Promise(resolve => setTimeout(resolve, 100));
        
        const [devicesResponse, inventoryResponse, statsResponse] = await Promise.all([
            fetch('/api/devices'),
            fetch('/api/inventory'),
            fetch('/api/dashboard/stats')
        ]);
        
        if (!devicesResponse.ok || !inventoryResponse.ok || !statsResponse.ok) {
            throw new Error('One or more API requests failed');
        }
        
        const devices = await devicesResponse.json();
        const inventory = await inventoryResponse.json();
        const stats = await statsResponse.json();
        
        if (typeof updateDeviceStatusChart !== 'undefined') {
            updateDeviceStatusChart(devices);
        }
        if (typeof updateCategoryChart !== 'undefined' && stats.category_stats) {
            updateCategoryChart(stats.category_stats);
        }
        if (typeof updateDiscoveryTimeline !== 'undefined') {
            updateDiscoveryTimeline(7); // Default to 7 days
        }
        if (typeof updateWarrantyChart !== 'undefined') {
            updateWarrantyChart(inventory);
        }
        if (typeof updateInventoryValueChart !== 'undefined') {
            updateInventoryValueChart(inventory);
        }
        if (typeof updateRecentActivity !== 'undefined') {
            updateRecentActivity(devices, inventory);
        }
        
    } catch (error) {
        console.error('Error loading chart data:', error);
        // Don't show user notification for chart loading errors
    }
}

// Update Device Status Chart
function updateDeviceStatusChart(devices) {
    const chart = window.dashboardCharts.deviceStatus;
    if (!chart) return;
    
    const now = new Date();
    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    
    let online = 0, offline = 0, unknown = 0;
    
    devices.forEach(device => {
        const lastSeen = new Date(device.last_seen);
        
        if (lastSeen > oneHourAgo) {
            online++;
        } else if (lastSeen > oneDayAgo) {
            unknown++;
        } else {
            offline++;
        }
    });
    
    chart.data.datasets[0].data = [online, offline, unknown];
    chart.update('none');
    
    // Update status counts
    const onlineCount = document.getElementById('online-count');
    const offlineCount = document.getElementById('offline-count');
    const unknownCount = document.getElementById('unknown-count');
    
    if (onlineCount) onlineCount.textContent = online;
    if (offlineCount) offlineCount.textContent = offline;
    if (unknownCount) unknownCount.textContent = unknown;
}

// Update Category Chart
function updateCategoryChart(categoryStats) {
    const chart = window.dashboardCharts.category;
    if (!chart) return;
    
    if (!categoryStats || categoryStats.length === 0) {
        chart.data.labels = ['No Data'];
        chart.data.datasets[0].data = [1];
        chart.data.datasets[0].backgroundColor = ['#e9ecef'];
        chart.update('none');
        
        // Clear legend
        const legendContainer = document.getElementById('category-legend');
        if (legendContainer) {
            legendContainer.innerHTML = '<p class="text-muted">No inventory items yet</p>';
        }
        return;
    }
    
    const labels = categoryStats.map(stat => stat.category);
    const data = categoryStats.map(stat => stat.count);
    const colors = categoryStats.map(stat => stat.color || '#6c757d');
    
    chart.data.labels = labels;
    chart.data.datasets[0].data = data;
    chart.data.datasets[0].backgroundColor = colors;
    chart.update('none');
    
    // Create custom legend
    createCategoryLegend(categoryStats);
}

// Create custom category legend
function createCategoryLegend(categoryStats) {
    const legendContainer = document.getElementById('category-legend');
    if (!legendContainer) return;
    
    legendContainer.innerHTML = categoryStats.map(stat => `
        <div class="d-flex justify-content-between align-items-center mb-1">
            <div class="d-flex align-items-center">
                <div class="category-icon me-2" style="background-color: ${stat.color}; color: white; width: 16px; height: 16px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.6rem;">
                    <i class="${stat.icon}"></i>
                </div>
                <small>${stat.category}</small>
            </div>
            <small class="fw-bold">${stat.count}</small>
        </div>
    `).join('');
}

// Update Discovery Timeline
async function updateDiscoveryTimeline(days = 7) {
    const chart = window.dashboardCharts.discoveryTimeline;
    if (!chart) return;
    
    try {
        const response = await fetch(`/api/devices/timeline?days=${days}`);
        const timelineData = await response.json();
        
        if (timelineData.status === 'success') {
            const labels = timelineData.timeline.map(point => {
                const date = new Date(point.date);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            });
            const data = timelineData.timeline.map(point => point.count);
            
            chart.data.labels = labels;
            chart.data.datasets[0].data = data;
            chart.update('none');
        }
    } catch (error) {
        console.error('Error loading timeline data:', error);
        // Fallback to empty chart
        chart.data.labels = [];
        chart.data.datasets[0].data = [];
        chart.update('none');
    }
}

// Update Warranty Chart
function updateWarrantyChart(inventory) {
    const chart = window.dashboardCharts.warranty;
    if (!chart) return;
    
    const now = new Date();
    const thirtyDaysFromNow = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
    
    let active = 0, expiring = 0, expired = 0, unknown = 0;
    
    inventory.forEach(item => {
        if (!item.warranty_expiry) {
            unknown++;
        } else {
            const warrantyDate = new Date(item.warranty_expiry);
            
            if (warrantyDate < now) {
                expired++;
            } else if (warrantyDate <= thirtyDaysFromNow) {
                expiring++;
            } else {
                active++;
            }
        }
    });
    
    chart.data.datasets[0].data = [active, expiring, expired, unknown];
    chart.update('none');
}

// Update Inventory Value Chart
function updateInventoryValueChart(inventory) {
    const chart = window.dashboardCharts.inventoryValue;
    if (!chart) return;
    
    const categoryValues = {};
    let totalValue = 0;
    
    inventory.forEach(item => {
        const price = parseFloat(item.price) || 0;
        const category = item.category_name || item.category || 'Unknown';
        
        categoryValues[category] = (categoryValues[category] || 0) + price;
        totalValue += price;
    });
    
    const sortedCategories = Object.entries(categoryValues)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 5); // Top 5 categories
    
    if (sortedCategories.length > 0) {
        const labels = sortedCategories.map(([category]) => category);
        const data = sortedCategories.map(([, value]) => value);
        const colors = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6c757d'];
        
        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
        chart.data.datasets[0].backgroundColor = colors.slice(0, labels.length);
        chart.update('none');
        
        // Update value statistics
        const totalValueEl = document.getElementById('total-value');
        const avgValueEl = document.getElementById('average-value');
        const topCategoryEl = document.getElementById('top-category');
        
        if (totalValueEl) totalValueEl.textContent = `$${totalValue.toLocaleString()}`;
        if (avgValueEl) avgValueEl.textContent = `$${Math.round(totalValue / inventory.length || 0).toLocaleString()}`;
        if (topCategoryEl) topCategoryEl.textContent = sortedCategories[0]?.[0] || 'None';
    } else {
        // No data case
        chart.data.labels = ['No Data'];
        chart.data.datasets[0].data = [1];
        chart.data.datasets[0].backgroundColor = ['#e9ecef'];
        chart.update('none');
        
        const totalValueEl = document.getElementById('total-value');
        const avgValueEl = document.getElementById('average-value');
        const topCategoryEl = document.getElementById('top-category');
        
        if (totalValueEl) totalValueEl.textContent = '$0';
        if (avgValueEl) avgValueEl.textContent = '$0';
        if (topCategoryEl) topCategoryEl.textContent = 'None';
    }
}

// Update Recent Activity Feed
function updateRecentActivity(devices, inventory) {
    const activityContainer = document.getElementById('recent-activity');
    if (!activityContainer) return;
    
    // Get recent devices (last 7 days)
    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const recentDevices = devices
        .filter(device => new Date(device.first_seen) > sevenDaysAgo)
        .sort((a, b) => new Date(b.first_seen) - new Date(a.first_seen))
        .slice(0, 10);
    
    // Get recent inventory additions (last 7 days)
    const recentInventory = inventory
        .filter(item => new Date(item.created_at) > sevenDaysAgo)
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 5);
    
    const activities = [];
    
    // Add device discoveries
    recentDevices.forEach(device => {
        activities.push({
            type: 'device_discovered',
            date: new Date(device.first_seen),
            content: `
                <div class="d-flex align-items-center">
                    <div class="bg-primary text-white rounded-circle me-3 d-flex align-items-center justify-content-center" style="width: 32px; height: 32px;">
                        <i class="fas fa-wifi fa-sm"></i>
                    </div>
                    <div>
                        <strong>Device Discovered</strong>
                        <br><small class="text-muted">${device.hostname || device.ip_address} (${device.vendor || 'Unknown vendor'})</small>
                    </div>
                </div>
            `
        });
    });
    
    // Add inventory additions
    recentInventory.forEach(item => {
        activities.push({
            type: 'inventory_added',
            date: new Date(item.created_at),
            content: `
                <div class="d-flex align-items-center">
                    <div class="bg-success text-white rounded-circle me-3 d-flex align-items-center justify-content-center" style="width: 32px; height: 32px;">
                        <i class="fas fa-plus fa-sm"></i>
                    </div>
                    <div>
                        <strong>Added to Inventory</strong>
                        <br><small class="text-muted">${item.name} (${item.category_name || item.category || 'Uncategorized'})</small>
                    </div>
                </div>
            `
        });
    });
    
    // Sort all activities by date
    activities.sort((a, b) => b.date - a.date);
    
    if (activities.length === 0) {
        activityContainer.innerHTML = `
            <div class="text-center text-muted">
                <i class="fas fa-history fa-2x mb-2"></i>
                <p>No recent activity</p>
                <small>Scan your network to discover devices</small>
            </div>
        `;
        return;
    }
    
    activityContainer.innerHTML = activities.slice(0, 8).map(activity => `
        <div class="mb-3 pb-2 border-bottom">
            ${activity.content}
            <div class="mt-1">
                <small class="text-muted">${formatRelativeTime(activity.date)}</small>
            </div>
        </div>
    `).join('');
}

// Utility function to format relative time
function formatRelativeTime(date) {
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) return 'Just now';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
    if (diffInSeconds < 604800) return `${Math.floor(diffInSeconds / 86400)} days ago`;
    
    return date.toLocaleDateString();
}

// Filter functions for chart interactivity
function filterDevicesByStatus(status) {
    // Navigate to scanning page with status filter
    window.location.href = `/scanning?filter=${status}`;
}

function filterInventoryByCategory(category = null) {
    // Navigate to inventory page with category filter
    const url = category ? `/inventory?category=${encodeURIComponent(category)}` : '/inventory';
    window.location.href = url;
}

// Load Dashboard Data function with chart integration
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
            if (lastScanTime) lastScanTime.textContent = formatDateTime(lastScan);
        }

        // Update charts if they exist
        if (typeof updateDeviceStatusChart !== 'undefined') {
            updateDeviceStatusChart(devices);
        }
        if (typeof updateWarrantyChart !== 'undefined') {
            updateWarrantyChart(inventory);
        }
        if (typeof updateRecentActivity !== 'undefined') {
            updateRecentActivity(devices, inventory);
        }

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        if (typeof showNotification !== 'undefined') {
            showNotification('Error loading dashboard data', 'danger');
        }
    }
}

// Utility function to format date time
function formatDateTime(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Ensure charts are responsive
function resizeCharts() {
    if (window.dashboardCharts) {
        Object.values(window.dashboardCharts).forEach(chart => {
            if (chart && typeof chart.resize === 'function') {
                chart.resize();
            }
        });
    }
}

// Handle window resize
window.addEventListener('resize', resizeCharts);