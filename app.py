from flask import Flask, render_template, request, jsonify
from backend.database import init_db, get_db_connection
from backend.scanner import NetworkScanner
from config import Config
import json
from datetime import datetime

app = Flask(__name__, 
           template_folder='frontend/templates',
           static_folder='frontend/static')
app.config.from_object(Config)

# Initialize database
init_db()

# Initialize network scanner
scanner = NetworkScanner()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/inventory')
def inventory():
    return render_template('inventory.html')

@app.route('/scanning')
def scanning():
    return render_template('scanning.html')

@app.route('/api/devices', methods=['GET'])
def get_devices():
    conn = get_db_connection()
    devices = conn.execute('SELECT * FROM devices ORDER BY last_seen DESC').fetchall()
    conn.close()
    
    return jsonify([dict(device) for device in devices])

@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics including category breakdown and warranty alerts"""
    try:
        conn = get_db_connection()
        
        # Category statistics
        category_stats = conn.execute('''
            SELECT category, COUNT(*) as count
            FROM inventory 
            WHERE deleted_at IS NULL 
            GROUP BY category
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
        
        return jsonify({
            'category_stats': [dict(row) for row in category_stats],
            'warranty_alerts': [dict(row) for row in warranty_alerts]
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    try:
        devices = scanner.scan_network()
        return jsonify({
            'status': 'success',
            'devices_found': len(devices),
            'devices': devices
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/scanning/stats', methods=['GET'])
def get_scanning_stats():
    """Get scanning-specific statistics"""
    try:
        conn = get_db_connection()
        
        # Total devices
        total_devices = conn.execute('SELECT COUNT(*) as count FROM devices').fetchone()['count']
        
        # Devices in inventory
        managed_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices d
            INNER JOIN inventory i ON d.id = i.device_id
            WHERE i.deleted_at IS NULL
        ''').fetchone()['count']
        
        # Devices not in inventory (excluding ignored)
        unmanaged_devices = conn.execute('''
            SELECT COUNT(*) as count FROM devices d
            LEFT JOIN inventory i ON d.id = i.device_id
            WHERE (i.device_id IS NULL OR i.deleted_at IS NOT NULL)
            AND d.is_ignored = 0
        ''').fetchone()['count']
        
        # Ignored devices
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
    
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    conn = get_db_connection()
    inventory = conn.execute('''
        SELECT i.*, d.ip_address, d.mac_address 
        FROM inventory i
        LEFT JOIN devices d ON i.device_id = d.id
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
        
        # Check if device is already in inventory (only if device_id provided)
        if data.get('device_id'):
            existing = conn.execute('''
                SELECT id FROM inventory 
                WHERE device_id = ? AND deleted_at IS NULL
            ''', (data.get('device_id'),)).fetchone()
            
            if existing:
                conn.close()
                return jsonify({
                    'status': 'error', 
                    'message': 'This device is already in your inventory'
                }), 400
        
        cursor = conn.execute('''
            INSERT INTO inventory (device_id, name, category, brand, model, purchase_date, 
                                 warranty_expiry, store_vendor, price, serial_number, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('device_id') or None,
            data.get('name'),
            data.get('category'),
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
        
        return jsonify({'status': 'success', 'id': cursor.lastrowid})
        
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({
                'status': 'error', 
                'message': 'This device is already in your inventory'
            }), 400
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/<int:inventory_id>', methods=['DELETE'])
def delete_inventory_item(inventory_id):
    try:
        conn = get_db_connection()
        
        # Check if item exists and is not already deleted
        item = conn.execute(
            'SELECT * FROM inventory WHERE id = ? AND deleted_at IS NULL', 
            (inventory_id,)
        ).fetchone()
        
        if not item:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Item not found or already deleted'}), 404
        
        # Soft delete - mark as deleted instead of removing
        conn.execute(
            'UPDATE inventory SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?', 
            (inventory_id,)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success', 'message': 'Item deleted successfully'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/export/<format>', methods=['GET'])
def export_inventory(format):
    try:
        conn = get_db_connection()
        inventory = conn.execute('''
            SELECT i.*, d.ip_address, d.mac_address, d.hostname
            FROM inventory i
            LEFT JOIN devices d ON i.device_id = d.id
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
    import csv
    import io
    from flask import make_response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'ID', 'Name', 'Category', 'Brand', 'Model', 'Purchase Date', 
        'Warranty Expiry', 'Store/Vendor', 'Price', 'Serial Number', 
        'IP Address', 'MAC Address', 'Hostname', 'Notes', 'Created At'
    ])
    
    # Write data
    for item in inventory:
        writer.writerow([
            item['id'],
            item['name'],
            item['category'] or '',
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
    from flask import make_response
    
    # Convert to list of dictionaries
    data = []
    for item in inventory:
        data.append({
            'id': item['id'],
            'name': item['name'],
            'category': item['category'],
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
        
        # Check if device exists and is currently ignored
        device = conn.execute(
            'SELECT * FROM devices WHERE id = ? AND is_ignored = 1', 
            (device_id,)
        ).fetchone()
        
        if not device:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Device not found or not currently ignored'}), 404
        
        # Unignore the device
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
        
        # Update all specified devices
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
        
        # Update all specified devices
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
        common_data = data.get('common_data', {})
        use_device_names = data.get('use_device_names', True)
        
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
        
        # Check for devices already in inventory
        existing = conn.execute(f'''
            SELECT device_id FROM inventory 
            WHERE device_id IN ({placeholders}) AND deleted_at IS NULL
        ''', device_ids).fetchall()
        
        existing_ids = set(row['device_id'] for row in existing)
        
        added_count = 0
        skipped_count = 0
        
        for device in devices:
            if device['id'] in existing_ids:
                skipped_count += 1
                continue
            
            # Generate device name
            if use_device_names and device['hostname'] and device['hostname'] != 'Unknown':
                device_name = device['hostname']
            else:
                device_name = f"Device {device['ip_address']}"
            
            # Insert into inventory
            conn.execute('''
                INSERT INTO inventory (device_id, name, category, brand, purchase_date, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                device['id'],
                device_name,
                common_data.get('category'),
                common_data.get('brand'),
                common_data.get('purchase_date') or None,
                common_data.get('notes')
            ))
            added_count += 1
        
        conn.commit()
        conn.close()
        
        message = f'Successfully added {added_count} device(s) to inventory'
        if skipped_count > 0:
            message += f' ({skipped_count} already in inventory)'
        
        return jsonify({
            'status': 'success',
            'message': message,
            'added_count': added_count,
            'skipped_count': skipped_count
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=app.config['DEBUG'])