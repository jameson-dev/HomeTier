
from flask import Flask, render_template, request, jsonify, make_response
from flask_socketio import SocketIO, emit
from backend.database import (
    init_db, get_db_connection, get_categories, add_category, 
    update_category, delete_category
)
from backend.scanner import NetworkScanner
from config import Config
import json
import threading
import time
import csv
import io
from datetime import datetime, timedelta

app = Flask(__name__, 
           template_folder='frontend/templates',
           static_folder='frontend/static')
app.config.from_object(Config)

# Initialize SocketIO with threading mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
init_db()

# Initialize network scanner
scanner = NetworkScanner()

# Error handling
@app.errorhandler(500)
def handle_internal_error(e):
    print(f"Internal error: {e}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {e}")
    return jsonify({'status': 'error', 'message': str(e)}), 500

# Real-time monitoring class
class RealtimeMonitor:
    def __init__(self):
        self.previous_device_status = {}
        self.scan_in_progress = False
        self.monitoring_active = False
        
    def start_monitoring(self):
        """Start real-time device monitoring"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        
        def monitor_loop():
            while self.monitoring_active:
                try:
                    self.check_device_status_changes()
                    self.check_new_devices()
                    time.sleep(15)  # Check every 15 seconds
                except Exception as e:
                    print(f"Error in monitoring loop: {e}")
                    time.sleep(30)
                    
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        print("Real-time monitoring started")
        
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.monitoring_active = False
        
    def check_device_status_changes(self):
        """Check for device status changes and emit updates"""
        try:
            conn = get_db_connection()
            devices = conn.execute('SELECT * FROM devices').fetchall()
            conn.close()
            
            current_status = {}
            status_changes = []
            now = datetime.now()
            
            for device in devices:
                device_dict = dict(device)
                device_id = device_dict['id']
                last_seen_str = device_dict['last_seen']
                
                if last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                    except:
                        last_seen = datetime.fromisoformat(last_seen_str)
                else:
                    last_seen = now
                
                time_diff = (now - last_seen).total_seconds()
                if time_diff < 3600:
                    status = 'online'
                elif time_diff < 86400:
                    status = 'unknown'
                else:
                    status = 'offline'
                
                current_status[device_id] = {
                    'status': status,
                    'last_seen': device_dict['last_seen'],
                    'ip_address': device_dict['ip_address'],
                    'hostname': device_dict['hostname'],
                    'vendor': device_dict['vendor']
                }
                
                if device_id in self.previous_device_status:
                    old_status = self.previous_device_status[device_id]['status']
                    if old_status != status:
                        status_changes.append({
                            'device_id': device_id,
                            'device_info': current_status[device_id],
                            'old_status': old_status,
                            'new_status': status,
                            'timestamp': now.isoformat()
                        })
            
            if status_changes:
                socketio.emit('device_status_changes', {
                    'changes': status_changes,
                    'timestamp': now.isoformat()
                })
                
            self.previous_device_status = current_status
            
            status_counts = {'online': 0, 'offline': 0, 'unknown': 0}
            for device_status in current_status.values():
                status_counts[device_status['status']] += 1
                
            socketio.emit('device_status_counts', status_counts)
            
        except Exception as e:
            print(f"Error checking device status: {e}")
            
    def check_new_devices(self):
        """Check for newly discovered devices"""
        try:
            conn = get_db_connection()
            recent_devices = conn.execute('''
                SELECT * FROM devices 
                WHERE datetime(first_seen) > datetime('now', '-1 minute')
                ORDER BY first_seen DESC
            ''').fetchall()
            conn.close()
            
            if recent_devices:
                new_devices = []
                for device in recent_devices:
                    device_dict = dict(device)
                    new_devices.append({
                        'id': device_dict['id'],
                        'ip_address': device_dict['ip_address'],
                        'mac_address': device_dict['mac_address'],
                        'hostname': device_dict['hostname'],
                        'vendor': device_dict['vendor'],
                        'first_seen': device_dict['first_seen']
                    })
                
                socketio.emit('new_devices_discovered', {
                    'devices': new_devices,
                    'count': len(new_devices),
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"Error checking new devices: {e}")

# Initialize real-time monitor
realtime_monitor = RealtimeMonitor()

# =============================================================================
# WEBSOCKET EVENTS
# =============================================================================

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to HomeTier real-time updates'})
    
    if not realtime_monitor.monitoring_active:
        realtime_monitor.start_monitoring()

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('request_device_status')
def handle_device_status_request():
    """Send current device status to requesting client"""
    try:
        conn = get_db_connection()
        devices = conn.execute('SELECT * FROM devices').fetchall()
        conn.close()
        
        status_counts = {'online': 0, 'offline': 0, 'unknown': 0}
        now = datetime.now()
        
        for device in devices:
            device_dict = dict(device)
            last_seen_str = device_dict['last_seen']
            
            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                except:
                    last_seen = datetime.fromisoformat(last_seen_str)
            else:
                last_seen = now
                
            time_diff = (now - last_seen).total_seconds()
            
            if time_diff < 3600:
                status_counts['online'] += 1
            elif time_diff < 86400:
                status_counts['unknown'] += 1
            else:
                status_counts['offline'] += 1
                
        emit('device_status_counts', status_counts)
        
    except Exception as e:
        emit('error', {'message': f'Error getting device status: {str(e)}'})

@socketio.on('start_network_scan')
def handle_start_scan():
    """Handle real-time network scan with progress updates"""
    if realtime_monitor.scan_in_progress:
        emit('scan_error', {'message': 'Scan already in progress'})
        return
        
    def scan_with_progress():
        try:
            realtime_monitor.scan_in_progress = True
            emit('scan_started', {
                'message': 'Network scan started', 
                'timestamp': datetime.now().isoformat()
            })
            
            network_ranges = scanner.get_network_ranges()
            
            for i, network_range in enumerate(network_ranges):
                emit('scan_progress', {
                    'progress': int((i / len(network_ranges)) * 100),
                    'current_range': network_range,
                    'message': f'Scanning {network_range}...'
                })
                
                devices = scanner.ping_scan(network_range)
                
                if devices:
                    emit('scan_devices_found', {
                        'devices': devices,
                        'range': network_range,
                        'count': len(devices)
                    })
            
            emit('scan_completed', {
                'message': 'Network scan completed',
                'timestamp': datetime.now().isoformat(),
                'total_ranges': len(network_ranges)
            })
            
        except Exception as e:
            emit('scan_error', {'message': f'Scan failed: {str(e)}'})
        finally:
            realtime_monitor.scan_in_progress = False
            
    scan_thread = threading.Thread(target=scan_with_progress)
    scan_thread.start()

# =============================================================================
# ROUTES - PAGES
# =============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/inventory')
def inventory():
    return render_template('inventory.html')

@app.route('/scanning')
def scanning():
    return render_template('scanning.html')

@app.route('/categories')
def categories():
    return render_template('categories.html')

# =============================================================================
# API ROUTES - DEVICES
# =============================================================================

@app.route('/api/devices', methods=['GET'])
def get_devices():
    conn = get_db_connection()
    devices = conn.execute('SELECT * FROM devices ORDER BY last_seen DESC').fetchall()
    conn.close()
    
    return jsonify([dict(device) for device in devices])

@app.route('/api/devices/timeline', methods=['GET'])
def get_devices_timeline():
    """Get device discovery timeline data"""
    try:
        days = request.args.get('days', 7, type=int)
        days = max(1, min(days, 365))  # Limit between 1 and 365 days
        
        conn = get_db_connection()
        
        timeline_data = conn.execute('''
            SELECT 
                DATE(first_seen) as date,
                COUNT(*) as count
            FROM devices 
            WHERE datetime(first_seen) > datetime('now', '-{} days')
            GROUP BY DATE(first_seen)
            ORDER BY date ASC
        '''.format(days)).fetchall()
        
        conn.close()
        
        # Fill in missing dates with zero counts
        start_date = datetime.now() - timedelta(days=days)
        timeline = []
        
        data_dict = {row['date']: row['count'] for row in timeline_data}
        
        for i in range(days + 1):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            timeline.append({
                'date': date_str,
                'count': data_dict.get(date_str, 0)
            })
        
        return jsonify({
            'status': 'success',
            'timeline': timeline,
            'period_days': days
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/<int:device_id>/ignore', methods=['POST'])
def ignore_device(device_id):
    try:
        conn = get_db_connection()
        conn.execute('UPDATE devices SET is_ignored = 1 WHERE id = ?', (device_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/<int:device_id>/unignore', methods=['POST'])
def unignore_device(device_id):
    try:
        conn = get_db_connection()
        
        device = conn.execute(
            'SELECT * FROM devices WHERE id = ? AND is_ignored = 1', 
            (device_id,)
        ).fetchone()
        
        if not device:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Device not found or not currently ignored'}), 404
        
        conn.execute('UPDATE devices SET is_ignored = 0 WHERE id = ?', (device_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Device unignored successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/bulk/ignore', methods=['POST'])
def bulk_ignore_devices():
    try:
        data = request.get_json()
        device_ids = data.get('device_ids', [])
        
        if not device_ids:
            return jsonify({'status': 'error', 'message': 'No devices specified'}), 400
        
        conn = get_db_connection()
        
        placeholders = ','.join(['?' for _ in device_ids])
        conn.execute(f'UPDATE devices SET is_ignored = 1 WHERE id IN ({placeholders})', device_ids)
        
        affected_rows = conn.total_changes
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully ignored {affected_rows} device(s)',
            'affected_count': affected_rows
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/bulk/unignore', methods=['POST'])
def bulk_unignore_devices():
    try:
        data = request.get_json()
        device_ids = data.get('device_ids', [])
        
        if not device_ids:
            return jsonify({'status': 'error', 'message': 'No devices specified'}), 400
        
        conn = get_db_connection()
        
        placeholders = ','.join(['?' for _ in device_ids])
        conn.execute(f'UPDATE devices SET is_ignored = 0 WHERE id IN ({placeholders})', device_ids)
        
        affected_rows = conn.total_changes
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully unignored {affected_rows} device(s)',
            'affected_count': affected_rows
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/bulk/add-to-inventory', methods=['POST'])
def bulk_add_to_inventory():
    try:
        data = request.get_json()
        device_ids = data.get('device_ids', [])
        mode = data.get('mode', 'common')
        
        if not device_ids:
            return jsonify({'status': 'error', 'message': 'No devices specified'}), 400
        
        conn = get_db_connection()
        
        # Get device information
        placeholders = ','.join(['?' for _ in device_ids])
        devices = conn.execute(f'''
            SELECT id, ip_address, hostname, mac_address, vendor 
            FROM devices 
            WHERE id IN ({placeholders})
        ''', device_ids).fetchall()
        
        # Check for devices already in active inventory
        existing_active = conn.execute(f'''
            SELECT device_id FROM inventory 
            WHERE device_id IN ({placeholders}) AND deleted_at IS NULL
        ''', device_ids).fetchall()
        
        # Check for devices in soft-deleted inventory
        existing_deleted = conn.execute(f'''
            SELECT device_id, id FROM inventory 
            WHERE device_id IN ({placeholders}) AND deleted_at IS NOT NULL
        ''', device_ids).fetchall()
        
        active_device_ids = set(row['device_id'] for row in existing_active)
        deleted_device_map = {row['device_id']: row['id'] for row in existing_deleted}
        
        added_count = 0
        restored_count = 0
        skipped_count = 0
        
        if mode == 'common':
            common_data = data.get('common_data', {})
            use_auto_names = data.get('use_auto_names', True)
            
            for device in devices:
                if device['id'] in active_device_ids:
                    skipped_count += 1
                    continue
                
                if use_auto_names:
                    if device['hostname'] and device['hostname'] != 'Unknown':
                        device_name = device['hostname']
                    else:
                        device_name = f"Device {device['ip_address']}"
                else:
                    device_name = f"Device {device['ip_address']}"
                
                category_id = common_data.get('category_id')
                category_name = common_data.get('category')
                
                if device['id'] in deleted_device_map:
                    conn.execute('''
                        UPDATE inventory 
                        SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                            warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                            notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        device_name, category_id, category_name,
                        common_data.get('brand'), common_data.get('model'),
                        common_data.get('purchase_date') or None,
                        common_data.get('warranty_expiry') or None,
                        common_data.get('store_vendor'),
                        float(common_data.get('price')) if common_data.get('price') else None,
                        common_data.get('serial_number'), common_data.get('notes'),
                        deleted_device_map[device['id']]
                    ))
                    restored_count += 1
                else:
                    conn.execute('''
                        INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                             warranty_expiry, store_vendor, price, serial_number, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device['id'], device_name, category_id, category_name,
                        common_data.get('brand'), common_data.get('model'),
                        common_data.get('purchase_date') or None,
                        common_data.get('warranty_expiry') or None,
                        common_data.get('store_vendor'),
                        float(common_data.get('price')) if common_data.get('price') else None,
                        common_data.get('serial_number'), common_data.get('notes')
                    ))
                    added_count += 1
                
        else:  # Individual mode
            device_data = data.get('device_data', {})
            
            for device in devices:
                if device['id'] in active_device_ids:
                    skipped_count += 1
                    continue
                
                device_id_str = str(device['id'])
                individual_data = device_data.get(device_id_str, {})
                
                device_name = individual_data.get('name') or f"Device {device['ip_address']}"
                category_id = individual_data.get('category_id')
                category_name = individual_data.get('category')
                
                if device['id'] in deleted_device_map:
                    conn.execute('''
                        UPDATE inventory 
                        SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                            warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                            notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        device_name, category_id, category_name,
                        individual_data.get('brand'), individual_data.get('model'),
                        individual_data.get('purchase_date') or None,
                        individual_data.get('warranty_expiry') or None,
                        individual_data.get('store_vendor'),
                        float(individual_data.get('price')) if individual_data.get('price') else None,
                        individual_data.get('serial_number'), individual_data.get('notes'),
                        deleted_device_map[device['id']]
                    ))
                    restored_count += 1
                else:
                    conn.execute('''
                        INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                             warranty_expiry, store_vendor, price, serial_number, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device['id'], device_name, category_id, category_name,
                        individual_data.get('brand'), individual_data.get('model'),
                        individual_data.get('purchase_date') or None,
                        individual_data.get('warranty_expiry') or None,
                        individual_data.get('store_vendor'),
                        float(individual_data.get('price')) if individual_data.get('price') else None,
                        individual_data.get('serial_number'), individual_data.get('notes')
                    ))
                    added_count += 1
        
        conn.commit()
        conn.close()
        
        # Emit real-time update
        socketio.emit('inventory_updated', {
            'action': 'bulk_added',
            'added_count': added_count,
            'restored_count': restored_count,
            'timestamp': datetime.now().isoformat()
        })
        
        message_parts = []
        if added_count > 0:
            message_parts.append(f'Added {added_count} new device(s)')
        if restored_count > 0:
            message_parts.append(f'restored {restored_count} previously deleted device(s)')
        if skipped_count > 0:
            message_parts.append(f'{skipped_count} already in inventory')
            
        if message_parts:
            message = 'Successfully ' + ', '.join(message_parts) + ' to inventory'
        else:
            message = 'No devices were processed'
        
        return jsonify({
            'status': 'success',
            'message': message,
            'added_count': added_count,
            'restored_count': restored_count,
            'skipped_count': skipped_count
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================================================
# API ROUTES - CATEGORIES
# =============================================================================

@app.route('/api/categories', methods=['GET'])
def get_categories_api():
    """Get all categories"""
    try:
        categories = get_categories()
        return jsonify({'status': 'success', 'categories': categories})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/categories', methods=['POST'])
def add_category_api():
    """Add a new category"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'status': 'error', 'message': 'Category name is required'}), 400
        
        name = data['name'].strip()
        description = data.get('description', '').strip() or None
        icon = data.get('icon', 'fas fa-desktop')
        color = data.get('color', '#0d6efd')
        
        if len(name) < 2:
            return jsonify({'status': 'error', 'message': 'Category name must be at least 2 characters'}), 400
        
        if len(name) > 50:
            return jsonify({'status': 'error', 'message': 'Category name must be less than 50 characters'}), 400
        
        category_id = add_category(name, description, icon, color)
        
        return jsonify({
            'status': 'success', 
            'message': 'Category created successfully',
            'category_id': category_id
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/categories/<int:category_id>', methods=['PUT'])
def update_category_api(category_id):
    """Update an existing category"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        if 'name' in data:
            name = data['name'].strip()
            if len(name) < 2:
                return jsonify({'status': 'error', 'message': 'Category name must be at least 2 characters'}), 400
            if len(name) > 50:
                return jsonify({'status': 'error', 'message': 'Category name must be less than 50 characters'}), 400
            data['name'] = name
        
        if 'description' in data:
            data['description'] = data['description'].strip() or None
        
        update_category(
            category_id,
            name=data.get('name'),
            description=data.get('description'),
            icon=data.get('icon'),
            color=data.get('color')
        )
        
        return jsonify({
            'status': 'success', 
            'message': 'Category updated successfully'
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
def delete_category_api(category_id):
    """Delete a category"""
    try:
        delete_category(category_id)
        
        return jsonify({
            'status': 'success', 
            'message': 'Category deleted successfully'
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================================================
# API ROUTES - DASHBOARD STATS
# =============================================================================

@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics including category breakdown and warranty alerts"""
    try:
        conn = get_db_connection()
        
        # Category statistics with proper joins
        category_stats = conn.execute('''
            SELECT 
                COALESCE(c.name, i.category, 'Uncategorized') as category,
                COUNT(*) as count,
                COALESCE(c.color, '#6c757d') as color,
                COALESCE(c.icon, 'fas fa-question') as icon
            FROM inventory i
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.deleted_at IS NULL 
            GROUP BY COALESCE(c.name, i.category, 'Uncategorized')
            ORDER BY count DESC
        ''').fetchall()
        
        # Warranty alerts (expiring in 30 days or expired)
        warranty_alerts = conn.execute('''
            SELECT name, warranty_expiry,
                   CASE 
                       WHEN warranty_expiry < date('now') THEN 'expired'
                       WHEN warranty_expiry <= date('now', '+30 days') THEN 'expiring'
                       ELSE 'active'
                   END as status
            FROM inventory 
            WHERE deleted_at IS NULL 
            AND warranty_expiry IS NOT NULL
            AND warranty_expiry <= date('now', '+30 days')
            ORDER BY warranty_expiry ASC
        ''').fetchall()
        
        conn.close()
        
        result = {
            'category_stats': [dict(row) for row in category_stats],
            'warranty_alerts': [dict(row) for row in warranty_alerts]
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in dashboard stats: {e}")
        if 'conn' in locals():
            conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/network-health', methods=['GET'])
def get_network_health():
    """Get network health metrics for dashboard"""
    try:
        conn = get_db_connection()
        
        device_status = conn.execute('''
            SELECT 
                CASE 
                    WHEN datetime(last_seen) > datetime('now', '-1 hour') THEN 'online'
                    WHEN datetime(last_seen) > datetime('now', '-1 day') THEN 'unknown'
                    ELSE 'offline'
                END as status,
                COUNT(*) as count
            FROM devices
            GROUP BY status
        ''').fetchall()
        
        scan_success_rate = 95  # Placeholder
        
        avg_discovery_time = conn.execute('''
            SELECT AVG(
                (julianday(last_seen) - julianday(first_seen)) * 24 * 60
            ) as avg_minutes
            FROM devices
            WHERE datetime(first_seen) > datetime('now', '-7 days')
        ''').fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'device_status': [dict(row) for row in device_status],
            'scan_success_rate': scan_success_rate,
            'avg_discovery_time': avg_discovery_time['avg_minutes'] if avg_discovery_time else 0
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/dashboard/inventory-metrics', methods=['GET'])
def get_inventory_metrics():
    """Get inventory value and metrics"""
    try:
        conn = get_db_connection()
        
        inventory_values = conn.execute('''
            SELECT 
                COALESCE(c.name, i.category, 'Unknown') as category,
                COALESCE(c.color, '#6c757d') as color,
                COALESCE(c.icon, 'fas fa-question') as icon,
                COUNT(i.id) as item_count,
                COALESCE(SUM(CAST(i.price as REAL)), 0) as total_value,
                COALESCE(AVG(CAST(i.price as REAL)), 0) as avg_value
            FROM inventory i
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.deleted_at IS NULL 
            AND i.price IS NOT NULL 
            AND CAST(i.price as REAL) > 0
            GROUP BY COALESCE(c.name, i.category, 'Unknown')
            ORDER BY total_value DESC
        ''').fetchall()
        
        warranty_status = conn.execute('''
            SELECT 
                CASE 
                    WHEN warranty_expiry IS NULL THEN 'unknown'
                    WHEN DATE(warranty_expiry) < DATE('now') THEN 'expired'
                    WHEN DATE(warranty_expiry) <= DATE('now', '+30 days') THEN 'expiring'
                    ELSE 'active'
                END as status,
                COUNT(*) as count
            FROM inventory
            WHERE deleted_at IS NULL
            GROUP BY status
        ''').fetchall()
        
        recent_additions = conn.execute('''
            SELECT COUNT(*) as count
            FROM inventory
            WHERE deleted_at IS NULL
            AND datetime(created_at) > datetime('now', '-30 days')
        ''').fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'inventory_values': [dict(row) for row in inventory_values],
            'warranty_status': [dict(row) for row in warranty_status],
            'recent_additions': recent_additions['count'] if recent_additions else 0
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================================================
# API ROUTES - SCANNING
# =============================================================================

@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    """Trigger a network scan with real-time progress"""
    try:
        # Start scan in background thread with proper context
        def scan_with_progress():
            try:
                with app.app_context():
                    socketio.emit('scan_start', {'message': 'Starting network scan...'})
                    
                    # Get network ranges first
                    ranges = scanner.get_network_ranges()
                    total_ranges = len(ranges)
                    
                    socketio.emit('scan_progress', {
                        'message': f'Scanning {total_ranges} network range(s)...',
                        'ranges': ranges
                    })
                    
                    all_devices = []
                    
                    for i, network_range in enumerate(ranges):
                        socketio.emit('scan_progress', {
                            'message': f'Scanning range {i+1}/{total_ranges}: {network_range}',
                            'current_range': network_range,
                            'range_progress': i + 1,
                            'total_ranges': total_ranges
                        })
                        
                        # Scan this range
                        if scanner.detect_wsl2():
                            devices = scanner.wsl2_ping_scan(network_range)
                        else:
                            devices = scanner.ping_scan(network_range)
                        
                        # Emit each discovered device immediately
                        for device in devices:
                            if device['mac']:
                                device_id = scanner.add_device(
                                    mac_address=device['mac'],
                                    ip_address=device['ip'],
                                    hostname=device['hostname'],
                                    vendor=device['vendor']
                                )
                                device['id'] = device_id
                                all_devices.append(device)
                                
                                socketio.emit('device_discovered', {
                                    'device': device,
                                    'total_found': len(all_devices)
                                })
                    
                    socketio.emit('scan_complete', {
                        'message': f'Scan completed! Found {len(all_devices)} devices.',
                        'devices_found': len(all_devices),
                        'devices': all_devices
                    })
                    
            except Exception as e:
                socketio.emit('scan_error', {'message': f'Scan failed: {str(e)}'})
        
        # Start the scan in a background thread
        scan_thread = threading.Thread(target=scan_with_progress)
        scan_thread.daemon = True
        scan_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Network scan started. Watch for real-time updates.'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scanning/stats', methods=['GET'])
def get_scanning_stats():
    """Get scanning-specific statistics"""
    try:
        conn = get_db_connection()
        
        total_devices = conn.execute('SELECT COUNT(*) as count FROM devices').fetchone()['count']
        
        managed_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices d
            INNER JOIN inventory i ON d.id = i.device_id
            WHERE i.deleted_at IS NULL
        ''').fetchone()['count']
        
        unmanaged_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices d
            LEFT JOIN inventory i ON d.id = i.device_id
            WHERE (i.device_id IS NULL OR i.deleted_at IS NOT NULL)
            AND d.is_ignored = 0
        ''').fetchone()['count']
        
        ignored_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices 
            WHERE is_ignored = 1
        ''').fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'total_devices': total_devices,
            'managed_devices': managed_devices,
            'unmanaged_devices': unmanaged_devices,
            'ignored_devices': ignored_devices
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================================================
# API ROUTES - INVENTORY
# =============================================================================

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db_connection()
    inventory = conn.execute('''
        SELECT 
            i.*, 
            d.ip_address, 
            d.mac_address,
            c.name as category_name,
            c.icon as category_icon,
            c.color as category_color
        FROM inventory i
        LEFT JOIN devices d ON i.device_id = d.id
        LEFT JOIN categories c ON i.category_id = c.id
        WHERE i.deleted_at IS NULL
        ORDER BY i.created_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(item) for item in inventory])

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    try:
        data = request.form
        conn = get_db_connection()
        
        # Handle category - could be category_id or legacy category text
        category_id = data.get('category_id')
        category_text = data.get('category')
        
        if category_id and category_id.isdigit():
            category_id = int(category_id)
            category = conn.execute('SELECT name FROM categories WHERE id = ?', (category_id,)).fetchone()
            category_text = category['name'] if category else None
        elif category_text:
            category = conn.execute('SELECT id FROM categories WHERE name = ?', (category_text,)).fetchone()
            category_id = category['id'] if category else None
        else:
            category_id = None
            category_text = None
        
        # Check if device is already in inventory
        if data.get('device_id'):
            existing_active = conn.execute('''
                SELECT id FROM inventory 
                WHERE device_id = ? AND deleted_at IS NULL
            ''', (data.get('device_id'),)).fetchone()
            
            if existing_active:
                conn.close()
                return jsonify({
                    'status': 'error', 
                    'message': 'This device is already in your inventory'
                }), 400
            
            existing_deleted = conn.execute('''
                SELECT id FROM inventory 
                WHERE device_id = ? AND deleted_at IS NOT NULL
            ''', (data.get('device_id'),)).fetchone()
            
            if existing_deleted:
                conn.execute('''
                    UPDATE inventory 
                    SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                        warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                        notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    data.get('name'), category_id, category_text,
                    data.get('brand'), data.get('model'),
                    data.get('purchase_date') or None,
                    data.get('warranty_expiry') or None,
                    data.get('store_vendor'),
                    data.get('price') or None,
                    data.get('serial_number'),
                    data.get('notes'),
                    existing_deleted['id']
                ))
                
                conn.commit()
                conn.close()
                
                # Emit real-time update
                socketio.emit('inventory_updated', {
                    'action': 'restored',
                    'item_id': existing_deleted['id'],
                    'timestamp': datetime.now().isoformat()
                })
                
                return jsonify({'status': 'success', 'id': existing_deleted['id'], 'action': 'restored'})
        
        # Create new inventory item
        cursor = conn.execute('''
            INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                 warranty_expiry, store_vendor, price, serial_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('device_id') or None,
            data.get('name'),
            category_id,
            category_text,
            data.get('brand'),
            data.get('model'),
            data.get('purchase_date') or None,
            data.get('warranty_expiry') or None,
            data.get('store_vendor'),
            data.get('price') or None,
            data.get('serial_number'),
            data.get('notes')
        ))
        
        conn.commit()
        conn.close()
        
        # Emit real-time update
        socketio.emit('inventory_updated', {
            'action': 'added',
            'item_id': cursor.lastrowid,
            'timestamp': datetime.now().isoformat()
        })
        
        return jsonify({'status': 'success', 'id': cursor.lastrowid, 'action': 'created'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/<int:inventory_id>', methods=['DELETE'])
def delete_inventory_item(inventory_id):
    try:
        conn = get_db_connection()
        
        item = conn.execute(
            'SELECT * FROM inventory WHERE id = ? AND deleted_at IS NULL', 
            (inventory_id,)
        ).fetchone()
        
        if not item:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Item not found or already deleted'}), 404
        
        conn.execute(
            'UPDATE inventory SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', 
            (inventory_id,)
        )
        conn.commit()
        conn.close()
        
        # Emit real-time update
        socketio.emit('inventory_updated', {
            'action': 'deleted',
            'item_id': inventory_id,
            'timestamp': datetime.now().isoformat()
        })
        
        return jsonify({'status': 'success', 'message': 'Item deleted successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/export/<format>', methods=['GET'])
def export_inventory(format):
    try:
        conn = get_db_connection()
        inventory = conn.execute('''
            SELECT i.*, d.ip_address, d.mac_address, d.hostname, c.name as category_name
            FROM inventory i
            LEFT JOIN devices d ON i.device_id = d.id
            LEFT JOIN categories c ON i.category_id = c.id
            WHERE i.deleted_at IS NULL
            ORDER BY i.created_at DESC
        ''').fetchall()
        conn.close()
        
        if format.lower() == 'csv':
            return export_to_csv(inventory)
        elif format.lower() == 'json':
            return export_to_json(inventory)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid format'}), 400
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def export_to_csv(inventory):
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        'ID', 'Name', 'Category', 'Brand', 'Model', 'Purchase Date', 
        'Warranty Expiry', 'Store/Vendor', 'Price', 'Serial Number', 
        'IP Address', 'MAC Address', 'Hostname', 'Notes', 'Created At'
    ])
    
    for item in inventory:
        writer.writerow([
            item['id'],
            item['name'],
            item['category_name'] or item['category'] or '',
            item['brand'] or '',
            item['model'] or '',
            item['purchase_date'] or '',
            item['warranty_expiry'] or '',
            item['store_vendor'] or '',
            item['price'] or '',
            item['serial_number'] or '',
            item['ip_address'] or '',
            item['mac_address'] or '',
            item['hostname'] or '',
            item['notes'] or '',
            item['created_at']
        ])
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

def export_to_json(inventory):
    data = []
    for item in inventory:
        data.append({
            'id': item['id'],
            'name': item['name'],
            'category': item['category_name'] or item['category'],
            'brand': item['brand'],
            'model': item['model'],
            'purchase_date': item['purchase_date'],
            'warranty_expiry': item['warranty_expiry'],
            'store_vendor': item['store_vendor'],
            'price': item['price'],
            'serial_number': item['serial_number'],
            'ip_address': item['ip_address'],
            'mac_address': item['mac_address'],
            'hostname': item['hostname'],
            'notes': item['notes'],
            'created_at': item['created_at'],
            'updated_at': item['updated_at']
        })
    
    export_data = {
        'export_date': datetime.now().isoformat(),
        'total_items': len(data),
        'inventory': data
    }
    
    response = make_response(json.dumps(export_data, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = f'attachment; filename=inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    return response

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({'status': 'error', 'message': 'Bad request'}), 400

# =============================================================================
# STARTUP
# =============================================================================

if __name__ == '__main__':
    host = app.config['HOST']
    port = app.config['PORT']
    
    print("Starting HomeTier Application...")
    print(f"Dashboard: http://{host}:{port}")
    print(f"Real-time features: {'Enabled' if socketio else 'Disabled'}")
    print(f"Debug mode: {'On' if app.config['DEBUG'] else 'Off'}")
    print("Async mode: threading")
    
    # Start the application with SocketIO using threading mode
    socketio.run(
        app, 
        host=host, 
        port=port, 
        debug=app.config['DEBUG'],
        allow_unsafe_werkzeug=True
    )