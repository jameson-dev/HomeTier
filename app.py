from flask import Flask, render_template, request, jsonify
from backend.database import init_db, get_db_connection, get_categories, add_category, update_category, delete_category
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

@app.route('/categories')
def categories():
    return render_template('categories.html')


@app.route('/api/devices', methods=['GET'])
def get_devices():
    conn = get_db_connection()
    devices = conn.execute('SELECT * FROM devices ORDER BY last_seen DESC').fetchall()
    conn.close()
    
    return jsonify([dict(device) for device in devices])

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
        
        # Validate name if provided
        if 'name' in data:
            name = data['name'].strip()
            if len(name) < 2:
                return jsonify({'status': 'error', 'message': 'Category name must be at least 2 characters'}), 400
            if len(name) > 50:
                return jsonify({'status': 'error', 'message': 'Category name must be less than 50 characters'}), 400
            data['name'] = name
        
        # Validate description if provided
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
        
        # If category_id is provided, use it; otherwise try to find category by name
        if category_id and category_id.isdigit():
            category_id = int(category_id)
            # Verify category exists
            category = conn.execute('SELECT name FROM categories WHERE id = ?', (category_id,)).fetchone()
            category_text = category['name'] if category else None
        elif category_text:
            # Try to find category by name
            category = conn.execute('SELECT id FROM categories WHERE name = ?', (category_text,)).fetchone()
            category_id = category['id'] if category else None
        else:
            category_id = None
            category_text = None
        
        # Check if device is already in inventory (only if device_id provided)
        if data.get('device_id'):
            # First check for active (non-deleted) inventory items
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
            
            # Check for soft-deleted inventory items
            existing_deleted = conn.execute('''
                SELECT id FROM inventory 
                WHERE device_id = ? AND deleted_at IS NOT NULL
            ''', (data.get('device_id'),)).fetchone()
            
            if existing_deleted:
                # Restore the soft-deleted item with new data
                conn.execute('''
                    UPDATE inventory 
                    SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                        warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                        notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
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
                    data.get('notes'),
                    existing_deleted['id']
                ))
                
                conn.commit()
                conn.close()
                
                return jsonify({'status': 'success', 'id': existing_deleted['id'], 'action': 'restored'})
        
        # Create new inventory item if no existing record found
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
        
        return jsonify({'status': 'success', 'id': cursor.lastrowid, 'action': 'created'})
        
    except Exception as e:
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
    from flask import make_response
    
    # Convert to list of dictionaries
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
            # Common mode - same settings for all devices
            common_data = data.get('common_data', {})
            use_auto_names = data.get('use_auto_names', True)
            
            for device in devices:
                if device['id'] in active_device_ids:
                    skipped_count += 1
                    continue
                
                # Determine device name
                if use_auto_names:
                    if device['hostname'] and device['hostname'] != 'Unknown':
                        device_name = device['hostname']
                    else:
                        device_name = f"Device {device['ip_address']}"
                else:
                    device_name = f"Device {device['ip_address']}"
                
                # Handle category
                category_id = common_data.get('category_id')
                category_name = common_data.get('category')
                
                # Check if this device was soft-deleted
                if device['id'] in deleted_device_map:
                    # Restore the soft-deleted item
                    conn.execute('''
                        UPDATE inventory 
                        SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                            warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                            notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        device_name,
                        category_id,
                        category_name,
                        common_data.get('brand'),
                        common_data.get('model'),
                        common_data.get('purchase_date') or None,
                        common_data.get('warranty_expiry') or None,
                        common_data.get('store_vendor'),
                        float(common_data.get('price')) if common_data.get('price') else None,
                        common_data.get('serial_number'),
                        common_data.get('notes'),
                        deleted_device_map[device['id']]
                    ))
                    restored_count += 1
                else:
                    # Insert new inventory item
                    conn.execute('''
                        INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                             warranty_expiry, store_vendor, price, serial_number, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device['id'],
                        device_name,
                        category_id,
                        category_name,
                        common_data.get('brand'),
                        common_data.get('model'),
                        common_data.get('purchase_date') or None,
                        common_data.get('warranty_expiry') or None,
                        common_data.get('store_vendor'),
                        float(common_data.get('price')) if common_data.get('price') else None,
                        common_data.get('serial_number'),
                        common_data.get('notes')
                    ))
                    added_count += 1
                
        else:
            # Individual mode - unique settings for each device
            device_data = data.get('device_data', {})
            
            for device in devices:
                if device['id'] in active_device_ids:
                    skipped_count += 1
                    continue
                
                device_id_str = str(device['id'])
                individual_data = device_data.get(device_id_str, {})
                
                # Use provided name or generate fallback
                device_name = individual_data.get('name') or f"Device {device['ip_address']}"
                
                # Handle category
                category_id = individual_data.get('category_id')
                category_name = individual_data.get('category')
                
                # Check if this device was soft-deleted
                if device['id'] in deleted_device_map:
                    # Restore the soft-deleted item
                    conn.execute('''
                        UPDATE inventory 
                        SET name = ?, category_id = ?, category = ?, brand = ?, model = ?, purchase_date = ?, 
                            warranty_expiry = ?, store_vendor = ?, price = ?, serial_number = ?, 
                            notes = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        device_name,
                        category_id,
                        category_name,
                        individual_data.get('brand'),
                        individual_data.get('model'),
                        individual_data.get('purchase_date') or None,
                        individual_data.get('warranty_expiry') or None,
                        individual_data.get('store_vendor'),
                        float(individual_data.get('price')) if individual_data.get('price') else None,
                        individual_data.get('serial_number'),
                        individual_data.get('notes'),
                        deleted_device_map[device['id']]
                    ))
                    restored_count += 1
                else:
                    # Insert new inventory item
                    conn.execute('''
                        INSERT INTO inventory (device_id, name, category_id, category, brand, model, purchase_date, 
                                             warranty_expiry, store_vendor, price, serial_number, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        device['id'],
                        device_name,
                        category_id,
                        category_name,
                        individual_data.get('brand'),
                        individual_data.get('model'),
                        individual_data.get('purchase_date') or None,
                        individual_data.get('warranty_expiry') or None,
                        individual_data.get('store_vendor'),
                        float(individual_data.get('price')) if individual_data.get('price') else None,
                        individual_data.get('serial_number'),
                        individual_data.get('notes')
                    ))
                    added_count += 1
        
        conn.commit()
        conn.close()
        
        # Build message based on what happened
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
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=app.config['DEBUG'])